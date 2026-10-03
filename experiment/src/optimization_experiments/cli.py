from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analysis import create_configuration_manifest
from .artifacts import ArtifactStore
from .campaigns import run_campaign
from .experiments.cso import create_cso_smoke_experiment
from .experiments.cso_campaign import create_cso_grid_experiment
from .experiments.zoadamm import create_zoadamm_smoke_experiment
from .experiments.zoadamm_campaign import create_zoadamm_grid_experiment


def _format_duration(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 60.0:
        return f"{seconds:.2f}s"
    whole = int(seconds)
    days, remainder = divmod(whole, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def main() -> None:
    parser = argparse.ArgumentParser(prog="opt-experiments")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("cso-smoke", "cso-grid", "zoadamm-smoke", "zoadamm-grid"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--artifact-root", type=Path, default=Path("_artifacts"))
        command_parser.add_argument("--workers", type=int, default=None)
        command_parser.add_argument("--start-method", choices=("fork", "forkserver", "spawn"), default="forkserver")
        command_parser.add_argument("--no-analysis", action="store_true")
        command_parser.add_argument(
            "--durable-artifacts",
            action="store_true",
            help="fsync every artifact; safer against power loss but slower",
        )
        command_parser.add_argument(
            "--compress-convergence",
            action="store_true",
            help="compress convergence arrays; saves disk space but costs CPU",
        )

    for command in ("cso-analyze", "zoadamm-analyze"):
        analyze = subparsers.add_parser(command)
        analyze.add_argument("--artifact-root", type=Path, default=Path("_artifacts"))
        analyze.add_argument("--experiment-id", required=True)

    for command in ("cso-grid-manifest", "zoadamm-grid-manifest"):
        manifest = subparsers.add_parser(command)
    manifest.add_argument("--output", type=Path, default=Path("cso_configuration_grid.csv"))

    args = parser.parse_args()

    if args.command in {"cso-grid-manifest", "zoadamm-grid-manifest"}:
        experiment = (
            create_cso_grid_experiment()
            if args.command == "cso-grid-manifest"
            else create_zoadamm_grid_experiment()
        )
        frame = create_configuration_manifest(experiment)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.output, index=False)
        print(f"wrote {len(frame):,} configurations to {args.output}", flush=True)
        return

    if args.command in {"cso-analyze", "zoadamm-analyze"}:
        experiment_root = args.artifact_root / args.experiment_id
        experiment_path = experiment_root / "experiment.json"
        if not experiment_path.is_file():
            raise FileNotFoundError(f"Experiment artifact not found: {experiment_path}")
        payload = json.loads(experiment_path.read_text(encoding="utf-8"))
        from .artifacts.store import ArtifactPaths
        store = ArtifactStore.__new__(ArtifactStore)
        store.root = args.artifact_root
        store.experiment_root = experiment_root
        store.paths = ArtifactPaths(
            experiment=experiment_path,
            runs=experiment_root / "runs",
            convergence=experiment_root / "convergence",
            failures=experiment_root / "failures",
            analysis=experiment_root / "analysis",
        )
        experiment = (
            create_cso_grid_experiment()
            if args.command == "cso-analyze"
            else create_zoadamm_grid_experiment()
        )
        store.experiment = experiment
        if args.command == "cso-analyze":
            from .analysis import analyze_cso, write_cso_analysis_artifacts
            result = analyze_cso(experiment, store)
            write_cso_analysis_artifacts(result, store.paths.analysis)
        else:
            from .analysis import analyze_zoadamm, write_zoadamm_analysis_artifacts
            result = analyze_zoadamm(experiment, store)
            write_zoadamm_analysis_artifacts(result, store.paths.analysis)
        print(f"analysis completed: {store.paths.analysis}", flush=True)
        _ = payload
        return

    if args.command == "cso-smoke":
        experiment = create_cso_smoke_experiment()
    elif args.command == "cso-grid":
        experiment = create_cso_grid_experiment()
    elif args.command == "zoadamm-smoke":
        experiment = create_zoadamm_smoke_experiment()
    elif args.command == "zoadamm-grid":
        experiment = create_zoadamm_grid_experiment()
    else:
        raise AssertionError(f"Unhandled command: {args.command!r}")

    print(
        f"Prepared '{experiment.name}': {experiment.run_count:,} runs "
        f"| {len(experiment.configurations):,} configurations "
        f"| {len(experiment.scenarios)} scenarios "
        f"| {len(experiment.seeds.seeds)} seeds "
        f"| {experiment.budget.max_function_evaluations:,} FEs/run",
        flush=True,
    )

    report = run_campaign(
        experiment,
        artifact_root=args.artifact_root,
        max_workers=args.workers,
        start_method=args.start_method,
        generate_analysis=not args.no_analysis,
        durable_artifacts=args.durable_artifacts,
        compress_convergence=args.compress_convergence,
    )
    execution = report.execution
    print(
        "CampaignReport:"
        f" experiment_id={execution.experiment_id} | "
        f"completed={execution.completed_run_count:,} | "
        f"failed={execution.failed_run_count:,} | "
        f"skipped={execution.skipped_completed_count:,} | "
        f"elapsed={_format_duration(execution.wall_seconds)} | "
        f"rate={execution.runs_per_second:.2f} runs/s | "
        f"CPU={_format_duration(execution.cpu_seconds)} | "
        f"persist={_format_duration(execution.persistence_seconds)} | "
        f"valid={report.validation.valid}",
        flush=True,
    )


if __name__ == "__main__":
    main()

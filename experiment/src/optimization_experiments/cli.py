from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import create_configuration_manifest, generate_cso_analysis
from .artifacts import ArtifactStore
from .campaigns import run_campaign
from .experiments.cso import create_cso_smoke_experiment
from .experiments.cso_campaign import create_cso_grid_experiment
from .experiments.zoadamm import create_zoadamm_smoke_experiment


def _format_duration(seconds: float) -> str:
    seconds = max(0.0, seconds)
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

    for command in ("cso-smoke", "cso-grid", "zoadamm-smoke"):
        smoke = subparsers.add_parser(command)
        smoke.add_argument("--artifact-root", type=Path, default=Path("_artifacts"))
        smoke.add_argument("--workers", type=int, default=None)

    analyze = subparsers.add_parser("cso-analyze")
    analyze.add_argument("--artifact-root", type=Path, default=Path("_artifacts"))
    analyze.add_argument("--experiment-id", required=True)

    manifest = subparsers.add_parser("cso-grid-manifest")
    manifest.add_argument("--output", type=Path, default=Path("cso_configuration_grid.csv"))

    args = parser.parse_args()

    if args.command == "cso-grid-manifest":
        experiment = create_cso_grid_experiment()
        frame = create_configuration_manifest(experiment)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.output, index=False)
        print(f"wrote {len(frame):,} configurations to {args.output}", flush=True)
        return

    if args.command == "cso-analyze":
        experiment_root = args.artifact_root / args.experiment_id
        experiment_path = experiment_root / "experiment.json"
        if not experiment_path.is_file():
            raise FileNotFoundError(f"Experiment artifact not found: {experiment_path}")
        import json
        payload = json.loads(experiment_path.read_text(encoding="utf-8"))
        # The canonical experiment specification is reconstructed by the store;
        # analysis itself reads only completed run metadata.
        store = ArtifactStore.__new__(ArtifactStore)
        store.root = args.artifact_root
        store.experiment_root = experiment_root
        from .artifacts.store import ArtifactPaths
        store.paths = ArtifactPaths(
            experiment=experiment_path,
            runs=experiment_root / "runs",
            convergence=experiment_root / "convergence",
            failures=experiment_root / "failures",
            analysis=experiment_root / "analysis",
        )
        records = store.load_run_records()
        from .analysis.runs import create_run_table_from_records
        run_table = create_run_table_from_records(records)
        artifacts = generate_cso_analysis(run_table, store.paths.analysis)
        for name, frame in artifacts.items():
            print(f"{name}: {len(frame):,} rows", flush=True)
        return

    if args.command == "cso-smoke":
        experiment = create_cso_smoke_experiment()
    elif args.command == "cso-grid":
        experiment = create_cso_grid_experiment()
    elif args.command == "zoadamm-smoke":
        experiment = create_zoadamm_smoke_experiment()
    else:
        raise AssertionError(f"Unhandled command: {args.command!r}")

    report = run_campaign(
        experiment,
        artifact_root=args.artifact_root,
        max_workers=args.workers,
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
        f"valid={report.validation.valid}",
        flush=True,
    )


if __name__ == "__main__":
    main()

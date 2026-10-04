from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .analysis import (
    analyze_algorithm_comparison,
    analyze_results,
    create_configuration_manifest,
    write_algorithm_comparison_artifacts,
    write_analysis_artifacts,
)
from .artifacts import ArtifactStore
from .core.ids import experiment_id
from .campaigns import run_campaign
from .experiments.cso import create_cso_smoke_experiment
from .experiments.cso_campaign import create_cso_grid_experiment
from .experiments.zoadamm import create_zoadamm_smoke_experiment
from .experiments.zoadamm_campaign import create_zoadamm_grid_experiment
from .experiments.cso_zoadamm import (
    create_cso_zoadamm_campaign_experiment,
    create_cso_zoadamm_smoke_experiment,
)


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

    for command in ("cso-smoke", "cso-grid", "zoadamm-smoke", "zoadamm-grid", "hybrid-smoke", "hybrid-campaign"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--artifact-root", type=Path, default=Path("_artifacts"))
        command_parser.add_argument("--workers", type=int, default=None)
        command_parser.add_argument(
            "--start-method", choices=("fork", "forkserver", "spawn"), default="forkserver"
        )
        command_parser.add_argument("--no-analysis", action="store_true")
        command_parser.add_argument("--durable-artifacts", action="store_true")
        command_parser.add_argument("--compress-convergence", action="store_true")

    for command in ("cso-analyze", "zoadamm-analyze", "hybrid-analyze"):
        analyze = subparsers.add_parser(command)
        analyze.add_argument("--artifact-root", type=Path, default=Path("_artifacts"))
        analyze.add_argument("--experiment-id", required=True)

    for command in ("cso-grid-manifest", "zoadamm-grid-manifest"):
        manifest = subparsers.add_parser(command)
        manifest.add_argument("--output", type=Path, default=None)

    compare = subparsers.add_parser("compare")
    compare.add_argument("--artifact-root", type=Path, default=Path("_artifacts"))
    compare.add_argument("--cso-experiment-id", required=True)
    compare.add_argument("--zoadamm-experiment-id", required=True)
    compare.add_argument("--output-dir", type=Path, default=None)

    args = parser.parse_args()

    if args.command in {"cso-grid-manifest", "zoadamm-grid-manifest"}:
        experiment = (
            create_cso_grid_experiment()
            if args.command == "cso-grid-manifest"
            else create_zoadamm_grid_experiment()
        )
        output = args.output
        if output is None:
            output = Path("cso_configuration_grid.csv" if args.command == "cso-grid-manifest" else "zoadamm_configuration_grid.csv")
        frame = create_configuration_manifest(experiment)
        output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output, index=False)
        print(f"wrote {len(frame):,} configurations to {output}", flush=True)
        return

    if args.command in {"cso-analyze", "zoadamm-analyze"}:
        experiment = (
            create_cso_grid_experiment()
            if args.command == "cso-analyze"
            else create_zoadamm_grid_experiment()
            if args.command == "zoadamm-analyze"
            else create_cso_zoadamm_campaign_experiment()
        )
        expected_experiment_id = experiment_id(experiment)
        if args.experiment_id != expected_experiment_id:
            raise ValueError(
                f"Experiment ID {args.experiment_id!r} does not match the "
                f"requested campaign specification {expected_experiment_id!r}."
            )
        experiment_root = args.artifact_root / args.experiment_id
        experiment_path = experiment_root / "experiment.json"
        if not experiment_path.is_file():
            raise FileNotFoundError(f"Experiment artifact not found: {experiment_path}")
        store = ArtifactStore(args.artifact_root, experiment)
        from .validation import validate_experiment
        validation = validate_experiment(experiment, store)
        if not validation.valid:
            raise RuntimeError("Experiment validation failed:\n" + "\n".join(validation.errors))
        tables = analyze_results(store.experiment, store)
        write_analysis_artifacts(tables, store.experiment, store.paths.analysis)
        print(f"analysis completed: {store.paths.analysis}", flush=True)
        return

    if args.command == "compare":
        cso_root = args.artifact_root / args.cso_experiment_id / "analysis"
        zoadamm_root = args.artifact_root / args.zoadamm_experiment_id / "analysis"
        cso_index = cso_root / "runs.parquet"
        zoadamm_index = zoadamm_root / "runs.parquet"
        if not cso_index.is_file():
            raise FileNotFoundError(f"CSO analysis index not found: {cso_index}")
        if not zoadamm_index.is_file():
            raise FileNotFoundError(f"ZO-AdaMM analysis index not found: {zoadamm_index}")
        cso_frame = pd.read_parquet(cso_index)
        zoadamm_frame = pd.read_parquet(zoadamm_index)
        comparison = analyze_algorithm_comparison({"CSO": cso_frame, "ZO-AdaMM": zoadamm_frame})
        output = args.output_dir or (args.artifact_root / "comparison")
        write_algorithm_comparison_artifacts(comparison, output)
        print(f"comparison completed: {output}", flush=True)
        return

    if args.command == "cso-smoke":
        experiment = create_cso_smoke_experiment()
    elif args.command == "cso-grid":
        experiment = create_cso_grid_experiment()
    elif args.command == "zoadamm-smoke":
        experiment = create_zoadamm_smoke_experiment()
    elif args.command == "zoadamm-grid":
        experiment = create_zoadamm_grid_experiment()
    elif args.command == "hybrid-smoke":
        experiment = create_cso_zoadamm_smoke_experiment()
    elif args.command == "hybrid-campaign":
        experiment = create_cso_zoadamm_campaign_experiment()
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

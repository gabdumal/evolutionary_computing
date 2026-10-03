from __future__ import annotations

"""Generate raw and statistical tables from completed experiment runs."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Final

import pandas as pd

from experiment_artifacts import ExperimentArtifactStore, ExperimentRunResult
from experiment_specifications import ExperimentSpecification, ParameterValue

DEFAULT_PROGRESS_INTERVAL_SECONDS: Final[float] = 15.0


class ResultsAnalysisError(RuntimeError):
    """Raised when result-table generation cannot be completed safely."""


def create_run_results_table(
    results: list[ExperimentRunResult],
    experiment: ExperimentSpecification,
) -> pd.DataFrame:
    """Create one row per completed run."""
    parameter_names = tuple(experiment.parameter_grid)
    rows: list[dict[str, object]] = []

    for result in results:
        run = result.run_specification
        parameters = run.configuration.parameters
        row: dict[str, object] = {
            "run_id": run.run_id,
            "configuration_id": run.configuration_id,
            "algorithm": run.configuration.name,
            "objective_function": run.problem.name,
            "optimization": run.problem.optimization,
            "dimension": run.dimension,
            "dimension_definition": f"D={run.dimension}",
            "seed": run.seed,
        }
        for parameter in parameter_names:
            row[parameter] = _csv_parameter_value(parameters[parameter])
        row.update(
            {
                "calculated_value": result.best_value,
                "iterations": result.iterations,
                "cpu_time_seconds": result.cpu_seconds,
                "function_evaluations": result.function_evaluations,
            }
        )
        rows.append(row)

    columns = [
        "run_id",
        "configuration_id",
        "algorithm",
        "objective_function",
        "optimization",
        "dimension",
        "dimension_definition",
        "seed",
        *parameter_names,
        "calculated_value",
        "iterations",
        "cpu_time_seconds",
        "function_evaluations",
    ]
    return pd.DataFrame.from_records(rows, columns=columns)


def create_run_statistics_table(
    run_results: pd.DataFrame,
    experiment: ExperimentSpecification,
) -> pd.DataFrame:
    """Create min/max/mean/std statistics across seeds per run configuration."""
    if run_results.empty:
        return pd.DataFrame()

    parameter_names = tuple(experiment.parameter_grid)
    group_columns = [
        "configuration_id",
        "algorithm",
        "objective_function",
        "optimization",
        "dimension",
        "dimension_definition",
        *parameter_names,
    ]
    metric_columns = [
        "calculated_value",
        "iterations",
        "cpu_time_seconds",
        "function_evaluations",
    ]

    grouped = run_results.groupby(
        group_columns,
        sort=True,
        dropna=False,
    )
    statistics = grouped[metric_columns].agg(["min", "max", "mean", "std"])
    statistics = statistics.reset_index()

    metric_stat_columns = [
        f"{metric}_{statistic}"
        for metric in metric_columns
        for statistic in ("min", "max", "mean", "std")
    ]
    statistics.columns = [*group_columns, *metric_stat_columns]
    statistics.insert(
        len(group_columns),
        "run_count",
        grouped.size().to_numpy(),
    )
    statistics[metric_stat_columns] = statistics[metric_stat_columns].fillna(0.0)

    return statistics.loc[
        :,
        [*group_columns, "run_count", *metric_stat_columns],
    ].reset_index(drop=True)


def generate_result_artifacts(
    artifact_store: ExperimentArtifactStore,
    experiment: ExperimentSpecification,
    *,
    output_directory: str | Path | None = None,
    require_complete: bool = True,
    progress_interval_seconds: float = DEFAULT_PROGRESS_INTERVAL_SECONDS,
) -> tuple[Path, Path]:
    """Generate the two requested CSV artifacts from persisted run results."""
    _validate_progress_interval(progress_interval_seconds)

    run_ids = artifact_store.completed_run_ids()
    expected_run_count = experiment.run_count
    completed_run_count = len(run_ids)

    if require_complete and completed_run_count != expected_run_count:
        raise ResultsAnalysisError(
            "The experiment is incomplete: "
            f"{completed_run_count:,}/{expected_run_count:,} completed runs."
        )

    directory = (
        artifact_store.experiment_directory / "analysis"
        if output_directory is None
        else Path(output_directory)
    )
    directory.mkdir(parents=True, exist_ok=True)

    print(
        f"[{_timestamp()}] Loading completed runs: 0/{completed_run_count:,}",
        flush=True,
    )

    results: list[ExperimentRunResult] = []
    started_at = time.monotonic()
    last_progress = started_at

    for index, run_id in enumerate(run_ids, start=1):
        results.append(artifact_store.load_run_result(run_id))
        now = time.monotonic()
        if (
            index == completed_run_count
            or now - last_progress >= progress_interval_seconds
        ):
            elapsed = now - started_at
            percentage = (
                100.0 * index / completed_run_count if completed_run_count else 100.0
            )
            print(
                f"[{_timestamp()}] Loaded {index:,}/{completed_run_count:,} "
                f"({percentage:.1f}%) | elapsed={elapsed:.1f}s",
                flush=True,
            )
            last_progress = now

    print(f"[{_timestamp()}] Building run-results table...", flush=True)
    run_table = create_run_results_table(results, experiment)
    run_results_path = directory / "run_results.csv"
    run_table.to_csv(run_results_path, index=False)

    print(f"[{_timestamp()}] Building run-statistics table...", flush=True)
    statistics_table = create_run_statistics_table(run_table, experiment)
    run_statistics_path = directory / "run_statistics.csv"
    statistics_table.to_csv(run_statistics_path, index=False)

    elapsed = time.monotonic() - started_at
    print(
        f"[{_timestamp()}] Finished in {elapsed:.1f}s | "
        f"runs={len(run_table):,} | "
        f"groups={len(statistics_table):,}",
        flush=True,
    )
    print(f"[{_timestamp()}] {run_results_path}", flush=True)
    print(f"[{_timestamp()}] {run_statistics_path}", flush=True)

    return run_results_path, run_statistics_path


def _validate_progress_interval(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("progress_interval_seconds must be a real number.")
    if value <= 0.0:
        raise ValueError("progress_interval_seconds must be greater than zero.")


def _timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _csv_parameter_value(value: ParameterValue) -> object:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


__all__ = [
    "DEFAULT_PROGRESS_INTERVAL_SECONDS",
    "ResultsAnalysisError",
    "create_run_results_table",
    "create_run_statistics_table",
    "generate_result_artifacts",
]

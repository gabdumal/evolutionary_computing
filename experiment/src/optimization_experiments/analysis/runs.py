from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd

from ..core.ids import algorithm_id, configuration_id, run_id, scenario_id
from ..core.models import RunResult


ANALYSIS_METRICS = (
    "calculated_value",
    "function_evaluations",
    "iterations",
    "cpu_seconds",
)


def create_run_table(results: Sequence[RunResult]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()

    parameter_names = tuple(
        sorted(
            {
                parameter
                for result in results
                for parameter in result.specification.algorithm.parameters
            }
        )
    )

    rows: list[dict[str, Any]] = []
    for result in results:
        specification = result.specification
        configuration = specification.algorithm
        scenario = specification.scenario

        row: dict[str, Any] = {
            "run_id": run_id(specification),
            "experiment_id": specification.experiment_id,
            "algorithm_id": algorithm_id(configuration.algorithm),
            "algorithm": configuration.algorithm.name,
            "configuration_id": configuration_id(configuration),
            "scenario_id": scenario_id(scenario),
            "objective_function": scenario.objective,
            "problem": scenario.problem,
            "dimension": scenario.dimension,
            "seed": specification.seed,
            "calculated_value": result.objective.best_value,
            "function_evaluations": result.function_evaluations,
            "iterations": result.iterations,
            "cpu_seconds": result.timing.cpu_seconds,
        }

        for parameter in parameter_names:
            row[parameter] = configuration.parameters.get(parameter)

        rows.append(row)

    columns = [
        "run_id",
        "experiment_id",
        "algorithm_id",
        "algorithm",
        "configuration_id",
        "scenario_id",
        "objective_function",
        "problem",
        "dimension",
        "seed",
        *parameter_names,
        *ANALYSIS_METRICS,
    ]
    return pd.DataFrame.from_records(rows, columns=columns)



def create_run_table_from_records(records: Sequence[dict[str, Any]]) -> pd.DataFrame:
    """Create the canonical run table without loading convergence arrays."""
    if not records:
        return pd.DataFrame()

    parameter_names = tuple(sorted({
        parameter
        for record in records
        for parameter in record["run"]["algorithm"]["parameters"]
    }))

    rows: list[dict[str, Any]] = []
    for record in records:
        run = record["run"]
        configuration = run["algorithm"]
        algorithm = configuration["algorithm"]
        scenario = run["scenario"]
        metrics = record["metrics"]
        configuration_id = _configuration_id_from_record(configuration)
        scenario_id = _scenario_id_from_record(scenario)
        algorithm_id = _algorithm_id_from_record(algorithm)
        run_id_value = _run_id_from_record(run)

        row: dict[str, Any] = {
            "run_id": run_id_value,
            "experiment_id": run["experiment_id"],
            "algorithm_id": algorithm_id,
            "algorithm": algorithm["name"],
            "configuration_id": configuration_id,
            "scenario_id": scenario_id,
            "objective_function": scenario["objective"],
            "problem": scenario["problem"],
            "dimension": int(scenario["dimension"]),
            "seed": int(run["seed"]),
            "calculated_value": float(metrics["best_value"]),
            "function_evaluations": int(metrics["function_evaluations"]),
            "iterations": int(metrics["iterations"]),
            "cpu_seconds": float(metrics["cpu_seconds"]),
        }
        row.update({parameter: configuration["parameters"].get(parameter) for parameter in parameter_names})
        rows.append(row)

    columns = [
        "run_id", "experiment_id", "algorithm_id", "algorithm", "configuration_id",
        "scenario_id", "objective_function", "problem", "dimension", "seed",
        *parameter_names, *ANALYSIS_METRICS,
    ]
    return pd.DataFrame.from_records(rows, columns=columns)


def _digest_record(value: Any, prefix: str) -> str:
    import hashlib
    import json
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:16]}"


def _algorithm_id_from_record(algorithm: dict[str, Any]) -> str:
    return _digest_record(algorithm, "alg")


def _configuration_id_from_record(configuration: dict[str, Any]) -> str:
    return _digest_record(configuration, "cfg")


def _scenario_id_from_record(scenario: dict[str, Any]) -> str:
    return _digest_record(scenario, "scn")


def _run_id_from_record(run: dict[str, Any]) -> str:
    return _digest_record(run, "run")

def create_run_statistics_table(
    run_table: pd.DataFrame,
    *,
    group_by: Sequence[str] = (
        "algorithm_id",
        "algorithm",
        "configuration_id",
        "scenario_id",
        "objective_function",
        "problem",
        "dimension",
    ),
    metrics: Sequence[str] = ANALYSIS_METRICS,
) -> pd.DataFrame:
    if run_table.empty:
        return pd.DataFrame()

    groups = list(group_by)
    metric_list = list(metrics)

    missing = [
        column
        for column in [*groups, *metric_list]
        if column not in run_table.columns
    ]
    if missing:
        raise KeyError(f"Missing columns: {missing}")

    grouped = run_table.groupby(
        groups,
        sort=True,
        dropna=False,
    )
    statistics = grouped[metric_list].agg(["min", "max", "mean", "std"])
    statistics.columns = [
        f"{metric}__{statistic}"
        for metric, statistic in statistics.columns.to_flat_index()
    ]
    statistics = statistics.reset_index()
    statistics.insert(
        len(groups),
        "run_count",
        grouped.size().to_numpy(),
    )
    return statistics


def generate_result_artifacts(
    experiment: ExperimentSpecification,
    store,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    records = store.load_run_records()
    run_table = create_run_table_from_records(records)
    statistics = create_run_statistics_table(run_table)

    output = store.paths.analysis
    output.mkdir(parents=True, exist_ok=True)
    run_table.to_csv(output / "run_results.csv", index=False)
    statistics.to_csv(output / "run_statistics.csv", index=False)
    run_table.to_parquet(output / "runs.parquet", index=False)
    statistics.to_parquet(output / "run_statistics.parquet", index=False)
    return run_table, statistics


def aggregate_runs(
    frame: pd.DataFrame,
    *,
    group_by: Sequence[str],
    metrics: Sequence[str] = ANALYSIS_METRICS,
) -> pd.DataFrame:
    return create_run_statistics_table(
        frame,
        group_by=group_by,
        metrics=metrics,
    )


__all__ = [
    "ANALYSIS_METRICS",
    "RunDataset",
    "aggregate_runs",
    "create_run_table_from_records",
    "create_run_table",
    "create_run_statistics_table",
    "generate_result_artifacts",
]


class RunDataset:
    """Small facade around the canonical run-results table."""

    def __init__(self, frame: pd.DataFrame):
        self.frame = frame

    @classmethod
    def from_parquet(cls, path: str) -> "RunDataset":
        return cls(pd.read_parquet(path))

    def aggregate(
        self,
        group_by: Sequence[str],
        *,
        metrics: Sequence[str] = ANALYSIS_METRICS,
    ) -> pd.DataFrame:
        return aggregate_runs(
            self.frame,
            group_by=group_by,
            metrics=metrics,
        )

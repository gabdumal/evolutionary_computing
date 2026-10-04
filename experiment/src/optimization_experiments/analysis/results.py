from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd

from ..core.ids import experiment_id
from ..core.models import ExperimentSpecification
from ..core.serialization import to_primitive


RUN_COLUMNS_BASE = (
    "run_id",
    "seed",
    "algorithm",
    "objective_function",
    "dimension",
    "configuration_id",
)

RUN_METRIC_COLUMNS = (
    "calculated_value",
    "function_evaluations",
    "iterations",
    "cpu_seconds",
)

AGGREGATION_METRICS = RUN_METRIC_COLUMNS


@dataclass(frozen=True, slots=True)
class AnalysisTables:
    """The four user-facing analysis products for one experiment."""

    run_results: pd.DataFrame
    configuration_results: pd.DataFrame
    best_configuration_results: pd.DataFrame
    parameter_effects: pd.DataFrame


@dataclass(frozen=True, slots=True)
class AnalysisMetadata:
    experiment_id: str
    experiment_name: str
    algorithm: str
    seeds: tuple[int, ...]
    run_count: int
    configuration_count: int
    scenario_count: int
    budget_function_evaluations: int
    parameter_names: tuple[str, ...]
    objective_direction: str = "minimize"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "experiment_id": self.experiment_id,
            "experiment_name": self.experiment_name,
            "algorithm": self.algorithm,
            "seeds": list(self.seeds),
            "run_count": self.run_count,
            "configuration_count": self.configuration_count,
            "scenario_count": self.scenario_count,
            "budget_function_evaluations": self.budget_function_evaluations,
            "parameter_names": list(self.parameter_names),
            "objective_direction": self.objective_direction,
            "configuration_grouping": [
                "algorithm",
                "objective_function",
                "dimension",
                "configuration_id",
            ],
            "best_configuration_grouping": [
                "algorithm",
                "objective_function",
                "dimension",
                "configuration_id",
            ],
            "best_configuration_selection": "minimum calculated_value_mean across configurations; ties retain all tied configurations",
            "best_parameter_level_definition": (
                "The best_parameter_level column identifies the parameter level with the lowest "
                "mean_calculated_value among the levels of that parameter within the same "
                "algorithm×objective_function×dimension group. It is a marginal result and "
                "must not be interpreted as the globally best configuration."
            ),
            "seed_aggregation": {
                "statistics": ["mean", "std"],
                "std_definition": "sample standard deviation (ddof=1) across the executed seeds",
            },
            "parameter_effect_definition": (
                "For each algorithm×objective_function×dimension×parameter×parameter_value, "
                "average calculated_value over all configurations carrying that level and over all seeds. "
                "mean_normalized_effect is normalized within parameter levels: 0=best level, 1=worst level. "
                "The reported standard deviation is calculated over the run-level values contributing to the level."
            ),
        }


def create_configuration_manifest(experiment: ExperimentSpecification) -> pd.DataFrame:
    """Materialize resolved configurations for inspection without executing runs."""
    parameter_names = tuple(sorted({name for c in experiment.configurations for name in c.parameters}))
    rows: list[dict[str, Any]] = []
    for configuration in experiment.configurations:
        rows.append({
            "configuration_id": _configuration_id(to_primitive(configuration)),
            **configuration.parameters,
        })
    return pd.DataFrame.from_records(rows, columns=["configuration_id", *parameter_names])


def create_run_results(records: Sequence[dict[str, Any]]) -> pd.DataFrame:
    """Build the lean run-level table requested by the experiment workflow."""
    if not records:
        return pd.DataFrame(columns=RUN_COLUMNS_BASE)

    parameter_names = _parameter_names_from_records(records)
    rows: list[dict[str, Any]] = []
    for payload in records:
        run = payload["run"]
        algorithm_cfg = run["algorithm"]
        algorithm_spec = algorithm_cfg["algorithm"]
        scenario = run["scenario"]
        metrics = payload["metrics"]

        configuration = _configuration_id(algorithm_cfg)
        row: dict[str, Any] = {
            "run_id": _run_id(run),
            "seed": int(run["seed"]),
            "algorithm": algorithm_spec["name"],
            "objective_function": scenario["objective"],
            "dimension": int(scenario["dimension"]),
            "configuration_id": configuration,
            "calculated_value": float(metrics["best_value"]),
            "function_evaluations": int(metrics["function_evaluations"]),
            "iterations": int(metrics["iterations"]),
            "cpu_seconds": float(metrics["cpu_seconds"]),
        }
        for parameter in parameter_names:
            row[parameter] = algorithm_cfg["parameters"].get(parameter)
        rows.append(row)

    columns = [
        *RUN_COLUMNS_BASE,
        *parameter_names,
        *RUN_METRIC_COLUMNS,
    ]
    return pd.DataFrame.from_records(rows, columns=columns).sort_values(
        ["algorithm", "objective_function", "dimension", "configuration_id", "seed", "run_id"],
        kind="stable",
    ).reset_index(drop=True)


def create_configuration_results(run_results: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the repeated seeds of each algorithm/configuration/scenario.

    Every metric measured across seeds is represented by its mean and sample
    standard deviation. The three-seed design therefore remains explicit in
    ``seed_count`` and no seed-level information is silently discarded.
    """
    if run_results.empty:
        return pd.DataFrame()

    parameter_names = _parameter_columns(run_results)
    groups = [
        "algorithm",
        "objective_function",
        "dimension",
        "configuration_id",
    ]

    grouped = run_results.groupby(groups, sort=True, dropna=False)
    aggregations: dict[str, tuple[str, str]] = {}
    for metric in AGGREGATION_METRICS:
        aggregations[f"{metric}_mean"] = (metric, "mean")
        aggregations[f"{metric}_std"] = (metric, lambda s: float(s.std(ddof=1)) if len(s) > 1 else 0.0)

    result = grouped.agg(**aggregations).reset_index()
    result["seed_count"] = grouped["seed"].nunique().to_numpy()

    parameters = (
        run_results[["configuration_id", *parameter_names]]
        .drop_duplicates("configuration_id", keep="first")
    )
    result = result.merge(parameters, on="configuration_id", how="left", validate="many_to_one")

    ordered = [
        *groups,
        "seed_count",
        *parameter_names,
    ]
    ordered += [
        f"{metric}_{stat}"
        for metric in AGGREGATION_METRICS
        for stat in ("mean", "std")
    ]
    return result.loc[:, ordered].sort_values(
        ["algorithm", "objective_function", "dimension", "configuration_id"],
        kind="stable",
    ).reset_index(drop=True)


def create_best_configuration_results(configuration_results: pd.DataFrame) -> pd.DataFrame:
    """Select the best configuration after aggregating its executed seeds.

    Selection is therefore performed on ``calculated_value_mean`` rather than
    on an individual seed.  One or more configurations are retained only when
    they are tied for the best aggregated mean within an
    algorithm×objective_function×dimension scenario.
    """
    if configuration_results.empty:
        return pd.DataFrame(columns=configuration_results.columns)

    groups = ["algorithm", "objective_function", "dimension"]
    selected: list[pd.DataFrame] = []
    for _, group in configuration_results.groupby(groups, sort=True, dropna=False):
        best_mean = group["calculated_value_mean"].min()
        selected.append(group.loc[group["calculated_value_mean"] == best_mean])

    return (
        pd.concat(selected, ignore_index=True)
        .sort_values([*groups, "configuration_id"], kind="stable")
        .reset_index(drop=True)
    )


def create_parameter_effects(run_results: pd.DataFrame) -> pd.DataFrame:
    """Measure each parameter's marginal effect with seeds as replicates.

    For every algorithm×objective_function×dimension×parameter×level, the
    configurations carrying that level are first averaged *within each seed*.
    The reported ``mean_calculated_value`` and ``std_calculated_value`` are
    then computed across those seed-level means.  Thus ``std`` measures
    variability between the experimental repetitions, rather than variability
    between individual configurations.
    """
    if run_results.empty:
        return pd.DataFrame()

    parameters = _parameter_columns(run_results)
    scenario_columns = ["algorithm", "objective_function", "dimension"]
    rows: list[dict[str, Any]] = []

    for parameter in parameters:
        seed_level = (
            run_results.groupby(
                [*scenario_columns, "seed", parameter],
                sort=True,
                dropna=False,
            )
            .agg(
                seed_mean_calculated_value=("calculated_value", "mean"),
                seed_configuration_count=("configuration_id", "nunique"),
            )
            .reset_index()
        )

        for scenario_key, scenario_levels in seed_level.groupby(
            scenario_columns, sort=True, dropna=False
        ):
            level_stats = (
                scenario_levels.groupby(parameter, sort=True, dropna=False)
                .agg(
                    mean_calculated_value=("seed_mean_calculated_value", "mean"),
                    std_calculated_value=(
                        "seed_mean_calculated_value",
                        lambda s: float(s.std(ddof=1)) if len(s) > 1 else 0.0,
                    ),
                    seed_count=("seed", "nunique"),
                    configuration_count=("seed_configuration_count", "mean"),
                )
                .reset_index()
            )

            best_mean = float(level_stats["mean_calculated_value"].min())
            worst_mean = float(level_stats["mean_calculated_value"].max())
            effect_range = worst_mean - best_mean
            if effect_range == 0.0:
                normalized = pd.Series(0.0, index=level_stats.index)
            else:
                normalized = (
                    level_stats["mean_calculated_value"] - best_mean
                ) / effect_range

            best_rows = level_stats.loc[
                level_stats["mean_calculated_value"] == best_mean
            ]
            best_value = min(
                (_parameter_sort_key(v) for v in best_rows[parameter].tolist())
            )
            best_values = [
                v
                for v in best_rows[parameter].tolist()
                if _parameter_sort_key(v) == best_value
            ]
            best_parameter = best_values[0]

            algorithm, objective_function, dimension = scenario_key
            for index, level in level_stats.iterrows():
                rows.append(
                    {
                        "algorithm": algorithm,
                        "objective_function": objective_function,
                        "dimension": int(dimension),
                        "parameter": parameter,
                        "parameter_value": level[parameter],
                        "mean_calculated_value": float(level["mean_calculated_value"]),
                        "std_calculated_value": float(level["std_calculated_value"]),
                        "seed_count": int(level["seed_count"]),
                        "configuration_count": int(level["configuration_count"]),
                        "mean_normalized_effect": float(normalized.loc[index]),
                        "parameter_effect_range": effect_range,
                        "best_parameter_level": best_parameter,
                    }
                )

    result = pd.DataFrame.from_records(rows)
    if result.empty:
        return result
    return result.sort_values(
        [*scenario_columns, "parameter", "mean_normalized_effect", "parameter_value"],
        kind="stable",
    ).reset_index(drop=True)


def analyze_results(
    experiment: ExperimentSpecification,
    store: Any,
) -> AnalysisTables:
    records = store.load_run_records()
    run_results = create_run_results(records)
    configuration_results = create_configuration_results(run_results)
    best_configuration_results = create_best_configuration_results(configuration_results)
    parameter_effects = create_parameter_effects(run_results)
    return AnalysisTables(
        run_results=run_results,
        configuration_results=configuration_results,
        best_configuration_results=best_configuration_results,
        parameter_effects=parameter_effects,
    )


def write_analysis_artifacts(
    tables: AnalysisTables,
    experiment: ExperimentSpecification,
    output: str | Path,
    *,
    write_parquet: bool = True,
) -> None:
    """Persist only the four requested CSVs plus optional Parquet intermediates."""
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    csvs = {
        "run_results.csv": tables.run_results,
        "configuration_results.csv": tables.configuration_results,
        "best_configuration_results.csv": tables.best_configuration_results,
        "parameter_effects.csv": tables.parameter_effects,
    }
    for filename, frame in csvs.items():
        frame.to_csv(output_path / filename, index=False)

    parquet_written = False
    if write_parquet:
        try:
            tables.run_results.to_parquet(output_path / "runs.parquet", index=False)
            parquet_written = True
        except ImportError:
            parquet_written = False

    metadata = AnalysisMetadata(
        experiment_id=experiment_id(experiment),
        experiment_name=experiment.name,
        algorithm=experiment.algorithm.name,
        seeds=experiment.seeds.seeds,
        run_count=len(tables.run_results),
        configuration_count=len(experiment.configurations),
        scenario_count=len(experiment.scenarios),
        budget_function_evaluations=experiment.budget.max_function_evaluations,
        parameter_names=tuple(sorted({p for c in experiment.configurations for p in c.parameters})),
    ).to_dict()
    metadata["parquet_intermediate_written"] = parquet_written
    (output_path / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parameter_columns(frame: pd.DataFrame) -> list[str]:
    known = set(RUN_COLUMNS_BASE) | set(RUN_METRIC_COLUMNS)
    known.add("wall_seconds")
    return [column for column in frame.columns if column not in known]


def _parameter_names_from_records(records: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    names = {
        parameter
        for payload in records
        for parameter in payload["run"]["algorithm"]["parameters"]
    }
    return tuple(sorted(names))


def _digest(value: Any, prefix: str) -> str:
    import hashlib
    payload = json.dumps(to_primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:16]}"


def _configuration_id(configuration: dict[str, Any]) -> str:
    return _digest(configuration, "cfg")


def _scenario_id(scenario: dict[str, Any]) -> str:
    return _digest(scenario, "scn")


def _run_id(run: dict[str, Any]) -> str:
    return _digest(run, "run")


def _parameter_sort_key(value: Any) -> str:
    return json.dumps(to_primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)



__all__ = [
    "AnalysisTables",
    "create_configuration_manifest",
    "create_run_results",
    "create_configuration_results",
    "create_best_configuration_results",
    "create_parameter_effects",
    "analyze_results",
    "write_analysis_artifacts",
]

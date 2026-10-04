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
    """The five user-facing analysis products for one experiment."""

    run_results: pd.DataFrame
    configuration_results: pd.DataFrame
    best_configuration_results: pd.DataFrame
    parameter_effects: pd.DataFrame
    parameter_effect_summary: pd.DataFrame


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
            "schema_version": 3,
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
            "seed_aggregation": {
                "statistics": ["mean", "std"],
                "std_definition": "sample standard deviation (ddof=1) across the executed seeds",
            },
            "parameter_effect_definition": (
                "For each algorithm×objective_function×dimension×parameter×parameter_value, "
                "average calculated_value over all configurations carrying that level and over all seeds. "
                "The level-wise table contains only observed marginal statistics for each parameter level. "
                "The consolidated parameter-effect summary reports the absolute level range and its normalization "
                "by the absolute scenario mean objective value."
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
    """Create the level-wise marginal parameter-effect table.

    The table intentionally contains only observations aggregated for a
    particular parameter level.  Interpretation across levels (best/worst
    level, effect magnitude, normalization, etc.) belongs in
    :func:`create_parameter_effect_summary`.

    Seeds are the experimental replicates: configurations carrying the same
    parameter level are first averaged within each seed, then the reported
    mean and sample standard deviation are computed across those seed-level
    means.
    """
    columns = [
        "algorithm",
        "objective_function",
        "dimension",
        "parameter",
        "parameter_value",
        "mean_calculated_value",
        "std_calculated_value",
        "seed_count",
        "configuration_count",
    ]
    if run_results.empty:
        return pd.DataFrame(columns=columns)

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
                scenario_levels.groupby(parameter, sort=False, dropna=False)
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

            algorithm, objective_function, dimension = scenario_key
            for _, level in level_stats.iterrows():
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
                        "configuration_count": int(round(float(level["configuration_count"]))),
                    }
                )

    result = pd.DataFrame.from_records(rows, columns=columns)
    if result.empty:
        return result

    result["_parameter_sort_order"] = result["parameter_value"].map(_parameter_sort_order)
    result = result.sort_values(
        [*scenario_columns, "parameter", "_parameter_sort_order"],
        kind="stable",
    )
    return result.drop(columns="_parameter_sort_order").reset_index(drop=True)


def create_parameter_effect_summary(
    run_results: pd.DataFrame,
    parameter_effects: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Consolidate marginal parameter effects to one row per parameter.

    For each algorithm×objective_function×dimension×parameter group, the
    absolute effect is the range between the worst and best marginal mean.
    The normalized effect divides that range by the absolute mean objective
    value for the complete scenario.  This makes effect magnitudes comparable
    across benchmark functions with different objective-value scales.

    A parameter with only one evaluated level has no measurable sensitivity;
    its effect and normalized effect are therefore ``NaN`` rather than zero.
    """
    columns = [
        "algorithm",
        "objective_function",
        "dimension",
        "parameter",
        "level_count",
        "best_marginal_parameter_value",
        "best_marginal_mean",
        "best_marginal_std",
        "worst_marginal_parameter_value",
        "worst_marginal_mean",
        "worst_marginal_std",
        "parameter_effect_range",
        "normalized_parameter_effect",
        "normalized_parameter_effect_percent",
    ]
    if run_results.empty:
        return pd.DataFrame(columns=columns)

    effects = parameter_effects if parameter_effects is not None else create_parameter_effects(run_results)
    if effects.empty:
        return pd.DataFrame(columns=columns)

    scenario_columns = ["algorithm", "objective_function", "dimension"]

    # The denominator uses the same seed-as-replicate convention as the
    # level-wise effects: first average all runs within each seed, then average
    # those seed means for the scenario scale.
    scenario_seed_means = (
        run_results.groupby([*scenario_columns, "seed"], sort=True, dropna=False)
        .agg(seed_mean_calculated_value=("calculated_value", "mean"))
        .reset_index()
    )
    scenario_scales = (
        scenario_seed_means.groupby(scenario_columns, sort=True, dropna=False)
        ["seed_mean_calculated_value"]
        .mean()
        .rename("scenario_mean_calculated_value")
        .reset_index()
    )

    rows: list[dict[str, Any]] = []
    for key, group in effects.groupby(
        [*scenario_columns, "parameter"], sort=True, dropna=False
    ):
        algorithm, objective_function, dimension, parameter = key
        group = group.reset_index(drop=True)
        level_count = int(group["parameter_value"].nunique(dropna=False))

        # Stable tie handling uses the parameter's natural ordering, rather
        # than the order in which configurations happened to be generated.
        best_mean = float(group["mean_calculated_value"].min())
        worst_mean = float(group["mean_calculated_value"].max())
        best_candidates = group.loc[group["mean_calculated_value"] == best_mean].copy()
        worst_candidates = group.loc[group["mean_calculated_value"] == worst_mean].copy()
        best_row = best_candidates.sort_values(
            "parameter_value",
            key=lambda s: s.map(_parameter_sort_order),
            kind="stable",
        ).iloc[0]
        worst_row = worst_candidates.sort_values(
            "parameter_value",
            key=lambda s: s.map(_parameter_sort_order),
            kind="stable",
        ).iloc[0]

        if level_count > 1:
            effect_range = worst_mean - best_mean
            scenario_mean = float(
                scenario_scales.loc[
                    (scenario_scales["algorithm"] == algorithm)
                    & (scenario_scales["objective_function"] == objective_function)
                    & (scenario_scales["dimension"] == dimension),
                    "scenario_mean_calculated_value",
                ].iloc[0]
            )
            if scenario_mean == 0.0:
                normalized_effect = float("nan")
            else:
                normalized_effect = effect_range / abs(scenario_mean)
        else:
            effect_range = float("nan")
            normalized_effect = float("nan")

        rows.append(
            {
                "algorithm": algorithm,
                "objective_function": objective_function,
                "dimension": int(dimension),
                "parameter": parameter,
                "level_count": level_count,
                "best_marginal_parameter_value": best_row["parameter_value"],
                "best_marginal_mean": float(best_row["mean_calculated_value"]),
                "best_marginal_std": float(best_row["std_calculated_value"]),
                "worst_marginal_parameter_value": worst_row["parameter_value"],
                "worst_marginal_mean": float(worst_row["mean_calculated_value"]),
                "worst_marginal_std": float(worst_row["std_calculated_value"]),
                "parameter_effect_range": effect_range,
                "normalized_parameter_effect": normalized_effect,
                "normalized_parameter_effect_percent": (
                    normalized_effect * 100.0 if pd.notna(normalized_effect) else float("nan")
                ),
            }
        )

    return pd.DataFrame.from_records(rows, columns=columns).sort_values(
        [*scenario_columns, "parameter"], kind="stable"
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
    parameter_effect_summary = create_parameter_effect_summary(run_results, parameter_effects)
    return AnalysisTables(
        run_results=run_results,
        configuration_results=configuration_results,
        best_configuration_results=best_configuration_results,
        parameter_effects=parameter_effects,
        parameter_effect_summary=parameter_effect_summary,
    )


def write_analysis_artifacts(
    tables: AnalysisTables,
    experiment: ExperimentSpecification,
    output: str | Path,
    *,
    write_parquet: bool = True,
) -> None:
    """Persist the five user-facing CSVs plus optional Parquet intermediates."""
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    csvs = {
        "run_results.csv": tables.run_results,
        "configuration_results.csv": tables.configuration_results,
        "best_configuration_results.csv": tables.best_configuration_results,
        "parameter_effects.csv": tables.parameter_effects,
        "parameter_effect_summary.csv": tables.parameter_effect_summary,
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


def _parameter_sort_order(value: Any) -> tuple[int, Any]:
    """Return a stable natural sort key for parameter levels."""
    if isinstance(value, bool):
        return (1, int(value))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, float(value))
    return (2, _parameter_sort_key(value))


def _parameter_sort_key(value: Any) -> str:
    return json.dumps(to_primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)



__all__ = [
    "AnalysisTables",
    "create_configuration_manifest",
    "create_run_results",
    "create_configuration_results",
    "create_best_configuration_results",
    "create_parameter_effects",
    "create_parameter_effect_summary",
    "analyze_results",
    "write_analysis_artifacts",
]

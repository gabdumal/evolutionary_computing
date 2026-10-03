from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd

from ..core.ids import configuration_id


PARAMETER_COLUMNS = (
    "population_size",
    "mixture_ratio",
    "c1",
    "smp",
    "spc",
    "cdc",
    "srd",
    "max_velocity",
)

SCENARIO_COLUMNS = (
    "scenario_id",
    "problem",
    "objective_function",
    "dimension",
)

METRIC = "calculated_value"



def create_configuration_manifest(experiment) -> pd.DataFrame:
    """Materialize the deterministic configuration grid before execution."""
    rows = []
    for configuration in experiment.configurations:
        rows.append({
            "configuration_id": configuration_id(configuration),
            **dict(configuration.parameters),
        })
    return pd.DataFrame(rows, columns=["configuration_id", *PARAMETER_COLUMNS])


def create_configuration_results(run_table: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the three independent seeds for each configuration/scenario."""
    required = [*SCENARIO_COLUMNS, "configuration_id", "seed", METRIC]
    missing = [column for column in required if column not in run_table.columns]
    if missing:
        raise KeyError(f"Missing columns: {missing}")

    group_columns = [*SCENARIO_COLUMNS, "configuration_id", *PARAMETER_COLUMNS]
    grouped = run_table.groupby(group_columns, sort=True, dropna=False)[METRIC]
    result = grouped.agg(
        seed_count="count",
        minimum="min",
        maximum="max",
        mean="mean",
        std="std",
    ).reset_index()
    return result.sort_values(
        ["problem", "dimension", "mean", "std", "configuration_id"],
        kind="stable",
    ).reset_index(drop=True)


def create_parameter_results(run_table: pd.DataFrame) -> pd.DataFrame:
    """Measure the response distribution at every level of every parameter."""
    required = [*SCENARIO_COLUMNS, METRIC, *PARAMETER_COLUMNS]
    missing = [column for column in required if column not in run_table.columns]
    if missing:
        raise KeyError(f"Missing columns: {missing}")

    frames: list[pd.DataFrame] = []
    for parameter in PARAMETER_COLUMNS:
        group_columns = [*SCENARIO_COLUMNS, parameter]
        grouped = run_table.groupby(group_columns, sort=True, dropna=False)[METRIC]
        frame = grouped.agg(
            run_count="count",
            minimum="min",
            maximum="max",
            mean="mean",
            std="std",
        ).reset_index()
        frame.insert(len(SCENARIO_COLUMNS), "parameter", parameter)
        frame = frame.rename(columns={parameter: "parameter_value"})
        frames.append(frame)

    return pd.concat(frames, ignore_index=True).sort_values(
        ["problem", "dimension", "parameter", "mean"],
        kind="stable",
    ).reset_index(drop=True)


def create_parameter_effect_summary(parameter_results: pd.DataFrame) -> pd.DataFrame:
    """Summarize the observed main effect of each parameter per scenario.

    ``mean_range`` is max(level mean) - min(level mean). Because all objectives
    are minimization problems, a smaller level mean is the better observed
    direction. This is descriptive, not a model-based importance estimate.
    """
    rows: list[dict[str, object]] = []
    for keys, group in parameter_results.groupby(
        [*SCENARIO_COLUMNS, "parameter"], sort=True, dropna=False
    ):
        scenario_id, problem, objective, dimension, parameter = keys
        means = group["mean"]
        best_index = means.idxmin()
        worst_index = means.idxmax()
        rows.append(
            {
                "scenario_id": scenario_id,
                "problem": problem,
                "objective_function": objective,
                "dimension": dimension,
                "parameter": parameter,
                "level_count": int(group["parameter_value"].nunique()),
                "best_observed_level": group.loc[best_index, "parameter_value"],
                "best_observed_mean": float(means.loc[best_index]),
                "worst_observed_level": group.loc[worst_index, "parameter_value"],
                "worst_observed_mean": float(means.loc[worst_index]),
                "mean_range": float(means.max() - means.min()),
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["problem", "dimension", "mean_range", "parameter"],
        ascending=[True, True, False, True],
        kind="stable",
    ).reset_index(drop=True)


def select_configurations(configuration_results: pd.DataFrame) -> pd.DataFrame:
    """Select one configuration per benchmark scenario.

    Selection is deliberately transparent: lowest three-seed mean first,
    then lowest standard deviation, then lowest worst-seed result, then the
    deterministic configuration id. No composite score is introduced.
    """
    rows: list[pd.Series] = []
    for _, group in configuration_results.groupby(list(SCENARIO_COLUMNS), sort=True, dropna=False):
        ordered = group.sort_values(
            ["mean", "std", "maximum", "configuration_id"],
            ascending=[True, True, True, True],
            kind="stable",
        )
        rows.append(ordered.iloc[0])

    if not rows:
        return pd.DataFrame(columns=configuration_results.columns)
    return pd.DataFrame(rows).reset_index(drop=True)


def generate_cso_analysis(
    run_table: pd.DataFrame,
    output_directory: str | Path,
) -> dict[str, pd.DataFrame]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    configuration_results = create_configuration_results(run_table)
    parameter_results = create_parameter_results(run_table)
    parameter_effect_summary = create_parameter_effect_summary(parameter_results)
    selected_configurations = select_configurations(configuration_results)

    artifacts = {
        "configuration_results": configuration_results,
        "parameter_results": parameter_results,
        "parameter_effect_summary": parameter_effect_summary,
        "selected_configurations": selected_configurations,
    }
    for name, frame in artifacts.items():
        frame.to_csv(output / f"{name}.csv", index=False)

    return artifacts


__all__ = [
    "PARAMETER_COLUMNS",
    "create_configuration_manifest",
    "create_configuration_results",
    "create_parameter_effect_summary",
    "create_parameter_results",
    "generate_cso_analysis",
    "select_configurations",
]

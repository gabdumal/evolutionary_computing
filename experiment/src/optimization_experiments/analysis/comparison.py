from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import json

import pandas as pd


DEFAULT_SEED_COUNT = 3
DEFAULT_SELECTION_TOLERANCE = 1e-12


@dataclass(frozen=True, slots=True)
class AlgorithmComparison:
    """Comparison of the selected configuration of each algorithm per scenario."""

    table: pd.DataFrame
    formatted_table: pd.DataFrame
    wide_table: pd.DataFrame


def _safe_std(series: pd.Series) -> float:
    return float(series.std(ddof=1)) if len(series) > 1 else 0.0


def _aggregate_configurations(run_table: pd.DataFrame) -> pd.DataFrame:
    required = {
        "algorithm",
        "objective_function",
        "dimension",
        "configuration_id",
        "seed",
        "calculated_value",
        "iterations",
        "cpu_seconds",
        "function_evaluations",
    }
    missing = sorted(required - set(run_table.columns))
    if missing:
        raise KeyError(f"Missing comparison columns: {missing}")
    if run_table.empty:
        return pd.DataFrame()

    grouped = run_table.groupby(
        ["algorithm", "objective_function", "dimension", "configuration_id"],
        sort=True,
        dropna=False,
    )
    return grouped.agg(
        calculated_value_mean=("calculated_value", "mean"),
        calculated_value_std=("calculated_value", _safe_std),
        iterations_mean=("iterations", "mean"),
        iterations_std=("iterations", _safe_std),
        cpu_seconds_mean=("cpu_seconds", "mean"),
        cpu_seconds_std=("cpu_seconds", _safe_std),
        function_evaluations_mean=("function_evaluations", "mean"),
        function_evaluations_std=("function_evaluations", _safe_std),
        seed_count=("seed", "nunique"),
    ).reset_index()


def _select_scenario_configuration(
    aggregated: pd.DataFrame,
    *,
    expected_seed_count: int,
    tolerance: float,
) -> pd.DataFrame:
    if aggregated.empty:
        return aggregated

    selected = []
    for (algorithm, objective_function, dimension), group in aggregated.groupby(
        ["algorithm", "objective_function", "dimension"], sort=True
    ):
        if (group["seed_count"] != expected_seed_count).any():
            bad = group.loc[
                group["seed_count"] != expected_seed_count,
                ["configuration_id", "seed_count"],
            ]
            raise ValueError(
                f"Expected {expected_seed_count} seeds for "
                f"{algorithm}/{objective_function}/D{dimension}; "
                f"invalid seed counts: {bad.to_dict(orient='records')}"
            )
        minimum = float(group["calculated_value_mean"].min())
        candidates = group.loc[
            group["calculated_value_mean"] <= minimum + tolerance
        ].copy()
        candidates = candidates.sort_values(
            ["calculated_value_std", "cpu_seconds_mean", "configuration_id"],
            kind="stable",
        )
        selected.append(candidates.iloc[0])

    return pd.DataFrame(selected).reset_index(drop=True)


def create_algorithm_comparison_table(
    run_tables: Mapping[str, pd.DataFrame],
    *,
    expected_seed_count: int = DEFAULT_SEED_COUNT,
    tolerance: float = DEFAULT_SELECTION_TOLERANCE,
) -> pd.DataFrame:
    if not run_tables:
        return pd.DataFrame()

    frames = []
    for label, frame in run_tables.items():
        if frame.empty:
            continue
        working = frame.copy()
        working["algorithm"] = str(label)
        frames.append(working)
    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    aggregated = _aggregate_configurations(combined)
    selected = _select_scenario_configuration(
        aggregated,
        expected_seed_count=expected_seed_count,
        tolerance=tolerance,
    )
    return selected.sort_values(
        ["objective_function", "dimension", "algorithm"], kind="stable"
    ).reset_index(drop=True)


def create_formatted_comparison_table(table: pd.DataFrame) -> pd.DataFrame:
    if table.empty:
        return pd.DataFrame()
    result = table.copy()
    result["value"] = result.apply(
        lambda row: f"{row.calculated_value_mean:.6f} ± {row.calculated_value_std:.6f}",
        axis=1,
    )
    result["iterations"] = result["iterations_mean"].round().astype(int).astype(str)
    result["time_seconds"] = result.apply(
        lambda row: f"{row.cpu_seconds_mean:.6f} ± {row.cpu_seconds_std:.6f}",
        axis=1,
    )
    return result[
        [
            "algorithm",
            "objective_function",
            "dimension",
            "configuration_id",
            "value",
            "iterations",
            "time_seconds",
            "seed_count",
        ]
    ].sort_values(
        ["objective_function", "dimension", "algorithm"], kind="stable"
    ).reset_index(drop=True)


def create_wide_comparison_table(formatted_table: pd.DataFrame) -> pd.DataFrame:
    if formatted_table.empty:
        return pd.DataFrame()
    frames = []
    for algorithm, group in formatted_table.groupby("algorithm", sort=True):
        frame = group[
            [
                "objective_function",
                "dimension",
                "value",
                "iterations",
                "time_seconds",
                "configuration_id",
            ]
        ].copy()
        prefix = str(algorithm).lower().replace(" ", "_").replace("-", "_")
        frame = frame.rename(
            columns={
                "value": f"{prefix}_value",
                "iterations": f"{prefix}_iterations",
                "time_seconds": f"{prefix}_time_seconds",
                "configuration_id": f"{prefix}_configuration_id",
            }
        )
        frames.append(frame)
    result = frames[0]
    for frame in frames[1:]:
        result = result.merge(
            frame,
            on=["objective_function", "dimension"],
            how="outer",
            validate="one_to_one",
        )
    return result.sort_values(
        ["objective_function", "dimension"], kind="stable"
    ).reset_index(drop=True)


def analyze_algorithm_comparison(
    run_tables: Mapping[str, pd.DataFrame],
    *,
    expected_seed_count: int = DEFAULT_SEED_COUNT,
    tolerance: float = DEFAULT_SELECTION_TOLERANCE,
) -> AlgorithmComparison:
    table = create_algorithm_comparison_table(
        run_tables,
        expected_seed_count=expected_seed_count,
        tolerance=tolerance,
    )
    formatted = create_formatted_comparison_table(table)
    return AlgorithmComparison(
        table=table,
        formatted_table=formatted,
        wide_table=create_wide_comparison_table(formatted),
    )


def write_algorithm_comparison_artifacts(
    comparison: AlgorithmComparison,
    output: str | Path,
) -> Path:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    comparison.table.to_csv(output / "algorithm_comparison_results.csv", index=False)
    comparison.formatted_table.to_csv(output / "algorithm_comparison_table.csv", index=False)
    comparison.wide_table.to_csv(output / "algorithm_comparison_wide.csv", index=False)
    try:
        comparison.table.to_parquet(output / "algorithm_comparison_results.parquet", index=False)
    except ImportError:
        pass
    metadata = {
        "seed_count": DEFAULT_SEED_COUNT,
        "selection": (
            "minimum mean objective value per algorithm×objective_function×dimension; "
            "ties within tolerance are resolved by objective std, mean CPU seconds, "
            "then configuration ID"
        ),
        "time_metric": "cpu_seconds",
        "artifacts": [
            "algorithm_comparison_results.csv",
            "algorithm_comparison_table.csv",
            "algorithm_comparison_wide.csv",
        ],
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


__all__ = [
    "AlgorithmComparison",
    "analyze_algorithm_comparison",
    "create_algorithm_comparison_table",
    "create_formatted_comparison_table",
    "create_wide_comparison_table",
    "write_algorithm_comparison_artifacts",
]

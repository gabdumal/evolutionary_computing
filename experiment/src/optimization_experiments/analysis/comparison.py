from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

from .runs import create_run_table_from_records


DEFAULT_SEED_COUNT = 3
DEFAULT_SELECTION_TOLERANCE = 1e-12
COMPARISON_METRICS = (
    "calculated_value",
    "iterations",
    "wall_seconds",
    "cpu_seconds",
    "function_evaluations",
)


@dataclass(frozen=True, slots=True)
class AlgorithmComparison:
    table: pd.DataFrame
    formatted_table: pd.DataFrame


def _safe_std(series: pd.Series) -> float:
    return float(series.std(ddof=1)) if len(series) > 1 else 0.0


def _aggregate_configurations(run_table: pd.DataFrame) -> pd.DataFrame:
    required = {
        "algorithm",
        "problem",
        "dimension",
        "configuration_id",
        "seed",
        *COMPARISON_METRICS,
    }
    missing = sorted(required - set(run_table.columns))
    if missing:
        raise KeyError(f"Missing columns: {missing}")
    if run_table.empty:
        return pd.DataFrame()

    grouped = run_table.groupby(
        ["algorithm", "problem", "dimension", "configuration_id"],
        sort=True,
        dropna=False,
    )
    return grouped.agg(
        value_mean=("calculated_value", "mean"),
        value_std=("calculated_value", _safe_std),
        iterations_mean=("iterations", "mean"),
        iterations_std=("iterations", _safe_std),
        wall_seconds_mean=("wall_seconds", "mean"),
        wall_seconds_std=("wall_seconds", _safe_std),
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
    for (algorithm, problem, dimension), group in aggregated.groupby(
        ["algorithm", "problem", "dimension"], sort=True
    ):
        if (group["seed_count"] != expected_seed_count).any():
            bad = group.loc[group["seed_count"] != expected_seed_count, ["configuration_id", "seed_count"]]
            raise ValueError(
                f"Expected {expected_seed_count} seeds for {algorithm}/{problem}/D{dimension}; "
                f"found invalid seed counts: {bad.to_dict(orient='records')}"
            )

        minimum = float(group["value_mean"].min())
        candidates = group.loc[group["value_mean"] <= minimum + tolerance].copy()
        candidates = candidates.sort_values(
            ["value_std", "wall_seconds_mean", "configuration_id"],
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
    """Compare selected configurations of multiple algorithms per problem×dimension.

    Selection is made independently for each algorithm and problem×dimension using:
    minimum mean objective value; ties within ``tolerance`` use value standard
    deviation, mean wall time, then configuration ID as deterministic tie-breakers.
    """
    if not run_tables:
        return pd.DataFrame()

    frames = []
    for label, frame in run_tables.items():
        if frame.empty:
            continue
        working = frame.copy()
        # Use the canonical algorithm label supplied by the caller. This makes
        # comparison robust to display-name changes inside individual adapters.
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

    selected = selected.sort_values(
        ["problem", "dimension", "algorithm"], kind="stable"
    ).reset_index(drop=True)
    return selected


def create_formatted_comparison_table(table: pd.DataFrame) -> pd.DataFrame:
    """Create presentation-ready fields matching the thesis comparison table."""
    if table.empty:
        return pd.DataFrame()

    result = table.copy()
    result["value"] = result.apply(
        lambda row: f"{row.value_mean:.6f} ± {row.value_std:.6f}", axis=1
    )
    result["iterations"] = result["iterations_mean"].round().astype(int).astype(str)
    result["time_seconds"] = result.apply(
        lambda row: f"{row.wall_seconds_mean:.6f} ± {row.wall_seconds_std:.6f}", axis=1
    )
    return result[
        [
            "algorithm",
            "problem",
            "dimension",
            "configuration_id",
            "value",
            "iterations",
            "time_seconds",
            "seed_count",
        ]
    ].sort_values(["problem", "dimension", "algorithm"], kind="stable").reset_index(drop=True)


def create_wide_comparison_table(formatted_table: pd.DataFrame) -> pd.DataFrame:
    """Create one row per problem×dimension with one metric block per algorithm."""
    if formatted_table.empty:
        return pd.DataFrame()

    base = ["problem", "dimension"]
    frames = []
    for algorithm, group in formatted_table.groupby("algorithm", sort=True):
        frame = group[
            ["problem", "dimension", "value", "iterations", "time_seconds", "configuration_id"]
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
        result = result.merge(frame, on=base, how="outer", validate="one_to_one")
    return result.sort_values(base, kind="stable").reset_index(drop=True)


def analyze_algorithm_comparison(
    cso_run_table: pd.DataFrame,
    zoadamm_run_table: pd.DataFrame,
    *,
    expected_seed_count: int = DEFAULT_SEED_COUNT,
    tolerance: float = DEFAULT_SELECTION_TOLERANCE,
) -> AlgorithmComparison:
    table = create_algorithm_comparison_table(
        {"CSO": cso_run_table, "ZO-AdaMM": zoadamm_run_table},
        expected_seed_count=expected_seed_count,
        tolerance=tolerance,
    )
    return AlgorithmComparison(
        table=table,
        formatted_table=create_formatted_comparison_table(table),
    )


def write_algorithm_comparison_artifacts(
    comparison: AlgorithmComparison,
    output: str | Path,
) -> tuple[Path, Path]:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)

    raw_path = output / "algorithm_comparison_results.csv"
    formatted_path = output / "algorithm_comparison_table.csv"
    wide_path = output / "algorithm_comparison_wide.csv"
    wide_parquet_path = output / "algorithm_comparison_wide.parquet"

    comparison.table.to_csv(raw_path, index=False)
    comparison.formatted_table.to_csv(formatted_path, index=False)
    wide = create_wide_comparison_table(comparison.formatted_table)
    wide.to_csv(wide_path, index=False)
    wide.to_parquet(wide_parquet_path, index=False)

    metadata = {
        "selection": "minimum mean objective value per algorithm×problem×dimension; ties within 1e-12 by value std, mean wall seconds, configuration ID",
        "seed_count": int(comparison.table["seed_count"].iloc[0]) if not comparison.table.empty else 0,
        "algorithms": sorted(comparison.table["algorithm"].unique().tolist()) if not comparison.table.empty else [],
        "rows": int(len(comparison.table)),
        "artifact_files": [raw_path.name, formatted_path.name, wide_path.name, wide_parquet_path.name],
    }
    import json
    (output / "algorithm_comparison_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return raw_path, formatted_path


def run_table_from_store_records(store) -> pd.DataFrame:
    return create_run_table_from_records(store.load_run_records())


__all__ = [
    "AlgorithmComparison",
    "COMPARISON_METRICS",
    "DEFAULT_SEED_COUNT",
    "analyze_algorithm_comparison",
    "create_algorithm_comparison_table",
    "create_formatted_comparison_table",
    "create_wide_comparison_table",
    "run_table_from_store_records",
    "write_algorithm_comparison_artifacts",
]

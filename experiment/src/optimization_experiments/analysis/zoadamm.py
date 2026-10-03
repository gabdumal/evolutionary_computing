from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from ..core.ids import configuration_id, experiment_id
from ..core.serialization import to_primitive
from ..core.models import ExperimentSpecification

DEFAULT_PERFORMANCE_TOLERANCE = 1e-12


@dataclass(frozen=True, slots=True)
class ZOAdaMMAnalysis:
    experiment_id: str
    parameter_names: tuple[str, ...]
    problems: tuple[str, ...]
    run_table: pd.DataFrame
    scenario_table: pd.DataFrame
    problem_configuration_table: pd.DataFrame
    problem_parameter_table: pd.DataFrame
    selected_configuration_table: pd.DataFrame
    selected_scenario_configuration_table: pd.DataFrame
    dimension_parameter_effects: pd.DataFrame


def _safe_std(values: pd.Series) -> float:
    return float(values.std(ddof=1)) if len(values) > 1 else 0.0


def _value_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _python_scalar(value: Any) -> Any:
    return value.item() if hasattr(value, "item") else value


def _varying_parameter_names(experiment: ExperimentSpecification) -> tuple[str, ...]:
    """Return only parameters that actually vary across the experimental grid."""
    names = tuple(sorted({p for c in experiment.configurations for p in c.parameters}))
    return tuple(
        name
        for name in names
        if len({_value_key(c.parameters[name]) for c in experiment.configurations}) > 1
    )


def _configuration_id_from_payload(configuration: dict[str, Any]) -> str:
    payload = json.dumps(
        to_primitive(configuration),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"cfg_{hashlib.sha256(payload).hexdigest()[:16]}"


def _scenario_id_from_payload(scenario: dict[str, Any]) -> str:
    payload = json.dumps(
        to_primitive(scenario),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"scn_{hashlib.sha256(payload).hexdigest()[:16]}"


def _run_id_from_payload(run: dict[str, Any]) -> str:
    payload = json.dumps(
        to_primitive(run),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"run_{hashlib.sha256(payload).hexdigest()[:16]}"


def create_configuration_manifest(experiment: ExperimentSpecification) -> pd.DataFrame:
    parameter_names = tuple(
        sorted({name for configuration in experiment.configurations for name in configuration.parameters})
    )
    rows = []
    for configuration in experiment.configurations:
        row = {"configuration_id": configuration_id(configuration)}
        row.update(configuration.parameters)
        rows.append(row)
    return pd.DataFrame.from_records(rows, columns=["configuration_id", *parameter_names])


def _run_table_from_records(records: Iterable[dict[str, Any]]) -> pd.DataFrame:
    records = tuple(records)
    if not records:
        return pd.DataFrame()

    parameter_names = tuple(sorted({
        parameter
        for payload in records
        for parameter in payload["run"]["algorithm"]["parameters"]
    }))
    rows = []
    for payload in records:
        run = payload["run"]
        algorithm = run["algorithm"]
        scenario = run["scenario"]
        metrics = payload["metrics"]
        row = {
            "run_id": _run_id_from_payload(run),
            "experiment_id": run["experiment_id"],
            "configuration_id": _configuration_id_from_payload(algorithm),
            "scenario_id": _scenario_id_from_payload(scenario),
            "algorithm": algorithm["algorithm"]["name"],
            "problem": scenario["problem"],
            "objective_function": scenario["objective"],
            "dimension": int(scenario["dimension"]),
            "seed": int(run["seed"]),
            "calculated_value": float(metrics["best_value"]),
            "function_evaluations": int(metrics["function_evaluations"]),
            "iterations": int(metrics["iterations"]),
            "cpu_seconds": float(metrics["cpu_seconds"]),
            "wall_seconds": float(metrics["wall_seconds"]),
        }
        row.update(algorithm["parameters"])
        rows.append(row)

    return pd.DataFrame.from_records(
        rows,
        columns=[
            "run_id", "experiment_id", "configuration_id", "scenario_id", "algorithm",
            "problem", "objective_function", "dimension", "seed", *parameter_names,
            "calculated_value", "function_evaluations", "iterations", "cpu_seconds",
            "wall_seconds",
        ],
    )


def create_scenario_table(run_table: pd.DataFrame) -> pd.DataFrame:
    if run_table.empty:
        return pd.DataFrame()

    grouped = run_table.groupby(
        ["problem", "dimension", "configuration_id"], sort=True, dropna=False
    )
    table = grouped.agg(
        mean_best_value=("calculated_value", "mean"),
        std_best_value=("calculated_value", lambda values: _safe_std(values)),
        median_best_value=("calculated_value", "median"),
        min_best_value=("calculated_value", "min"),
        max_best_value=("calculated_value", "max"),
        mean_cpu_seconds=("cpu_seconds", "mean"),
        std_cpu_seconds=("cpu_seconds", lambda values: _safe_std(values)),
        mean_wall_seconds=("wall_seconds", "mean"),
        std_wall_seconds=("wall_seconds", lambda values: _safe_std(values)),
        mean_function_evaluations=("function_evaluations", "mean"),
        seed_count=("seed", "nunique"),
    ).reset_index()

    table["scenario_rank"] = table.groupby(["problem", "dimension"])["mean_best_value"].rank(
        method="average", ascending=True
    )
    table["normalized_gap"] = 0.0
    table["std_normalized_gap_across_seeds"] = 0.0

    for (problem, dimension), indices in table.groupby(["problem", "dimension"], sort=False).groups.items():
        values = table.loc[indices, "mean_best_value"].astype(float)
        best = float(values.min())
        worst = float(values.max())
        spread = worst - best
        if spread > DEFAULT_PERFORMANCE_TOLERANCE:
            table.loc[indices, "normalized_gap"] = (values - best) / spread

        for index in indices:
            config_id = str(table.loc[index, "configuration_id"])
            seed_values = run_table.loc[
                (run_table["problem"] == problem)
                & (run_table["dimension"] == dimension)
                & (run_table["configuration_id"] == config_id),
                "calculated_value",
            ].astype(float)
            normalized_seed = (
                (seed_values - best) / spread
                if spread > DEFAULT_PERFORMANCE_TOLERANCE
                else pd.Series(0.0, index=seed_values.index)
            )
            table.loc[index, "std_normalized_gap_across_seeds"] = _safe_std(normalized_seed)

    return table.sort_values(
        ["problem", "dimension", "normalized_gap", "configuration_id"], kind="stable"
    ).reset_index(drop=True)


def create_problem_configuration_table(
    scenario_table: pd.DataFrame,
    experiment: ExperimentSpecification,
) -> pd.DataFrame:
    if scenario_table.empty:
        return pd.DataFrame()

    expected = {configuration_id(c): c for c in experiment.configurations}
    parameter_names = tuple(sorted({p for c in experiment.configurations for p in c.parameters}))
    rows = []
    for (problem, config_id), group in scenario_table.groupby(["problem", "configuration_id"], sort=True):
        config = expected[str(config_id)]
        row = {
            "problem": problem,
            "configuration_id": config_id,
            "algorithm": config.algorithm.name,
            "dimension_count": len(group),
            "mean_normalized_gap": float(group["normalized_gap"].mean()),
            "std_normalized_gap": _safe_std(group["normalized_gap"]),
            "mean_seed_std_normalized_gap": float(group["std_normalized_gap_across_seeds"].mean()),
            "max_seed_std_normalized_gap": float(group["std_normalized_gap_across_seeds"].max()),
            "mean_rank": float(group["scenario_rank"].mean()),
            "worst_normalized_gap": float(group["normalized_gap"].max()),
            "mean_cpu_seconds": float(group["mean_cpu_seconds"].mean()),
            "mean_wall_seconds": float(group["mean_wall_seconds"].mean()),
            "mean_function_evaluations": float(group["mean_function_evaluations"].mean()),
        }
        for name in parameter_names:
            value = config.parameters[name]
            row[name] = value
            row[f"{name}__key"] = _value_key(value)
        rows.append(row)

    columns = [
        "problem", "configuration_id", "algorithm", *parameter_names,
        *[f"{name}__key" for name in parameter_names],
        "dimension_count", "mean_normalized_gap", "std_normalized_gap",
        "mean_seed_std_normalized_gap", "max_seed_std_normalized_gap", "mean_rank",
        "worst_normalized_gap", "mean_cpu_seconds", "mean_wall_seconds",
        "mean_function_evaluations",
    ]
    return pd.DataFrame.from_records(rows, columns=columns).sort_values(
        ["problem", "mean_normalized_gap", "mean_rank", "configuration_id"], kind="stable"
    ).reset_index(drop=True)


def create_problem_parameter_table(
    problem_configuration_table: pd.DataFrame,
    experiment: ExperimentSpecification,
) -> pd.DataFrame:
    if problem_configuration_table.empty:
        return pd.DataFrame()

    parameter_names = _varying_parameter_names(experiment)
    rows = []
    for problem, problem_rows in problem_configuration_table.groupby("problem", sort=False):
        for parameter in parameter_names:
            key = f"{parameter}__key"
            for value_key, level_rows in problem_rows.groupby(key, sort=False):
                rows.append({
                    "problem": problem,
                    "parameter": parameter,
                    "parameter_value": _python_scalar(level_rows[parameter].iloc[0]),
                    "parameter_value_key": str(value_key),
                    "configuration_count": len(level_rows),
                    "mean_normalized_gap": float(level_rows["mean_normalized_gap"].mean()),
                    "std_normalized_gap": _safe_std(level_rows["mean_normalized_gap"]),
                    "mean_seed_std_normalized_gap": float(level_rows["mean_seed_std_normalized_gap"].mean()),
                    "worst_seed_std_normalized_gap": float(level_rows["max_seed_std_normalized_gap"].max()),
                    "mean_rank": float(level_rows["mean_rank"].mean()),
                    "worst_configuration_gap": float(level_rows["worst_normalized_gap"].max()),
                    "mean_cpu_seconds": float(level_rows["mean_cpu_seconds"].mean()),
                    "mean_wall_seconds": float(level_rows["mean_wall_seconds"].mean()),
                    "mean_function_evaluations": float(level_rows["mean_function_evaluations"].mean()),
                })

    table = pd.DataFrame.from_records(rows)
    if table.empty:
        return table

    table["parameter_effect_range"] = table.groupby(["problem", "parameter"])["mean_normalized_gap"].transform(
        lambda values: float(values.max() - values.min())
    )
    table["level_mean_rank"] = table.groupby(["problem", "parameter"])["mean_normalized_gap"].rank(
        method="average", ascending=True
    )
    return table.sort_values(
        ["problem", "parameter", "mean_normalized_gap", "parameter_value_key"], kind="stable"
    ).reset_index(drop=True)


def create_dimension_parameter_effect_table(
    run_table: pd.DataFrame,
    experiment: ExperimentSpecification,
) -> pd.DataFrame:
    if run_table.empty:
        return pd.DataFrame()

    # Dimension-local normalized performance. Parameter-level means are over all
    # configurations at that level, preserving the balanced full-factorial design.
    scenario_table = create_scenario_table(run_table)
    config_map = {
        configuration_id(c): c.parameters for c in experiment.configurations
    }
    rows = []
    parameter_names = _varying_parameter_names(experiment)

    for (problem, dimension), scenario_rows in scenario_table.groupby(["problem", "dimension"], sort=False):
        expanded = scenario_rows.copy()
        for parameter in parameter_names:
            expanded[parameter] = expanded["configuration_id"].map(
                lambda identifier: config_map[str(identifier)][parameter]
            )
        for parameter in parameter_names:
            levels = expanded.groupby(parameter, sort=False)["normalized_gap"].agg(["mean", "std", "count"]).reset_index()
            levels["std"] = levels["std"].fillna(0.0)
            effect_range = float(levels["mean"].max() - levels["mean"].min())
            effect_std = _safe_std(levels["mean"])
            levels["level_mean_rank"] = levels["mean"].rank(method="average", ascending=True)
            best = levels.sort_values(["mean", parameter], kind="stable").iloc[0]
            for _, level in levels.iterrows():
                value = _python_scalar(level[parameter])
                rows.append({
                    "problem": problem,
                    "dimension": int(dimension),
                    "parameter": parameter,
                    "parameter_value": value,
                    "parameter_value_key": _value_key(value),
                    "mean_normalized_gap": float(level["mean"]),
                    "std_normalized_gap": float(level["std"]),
                    "configuration_count": int(level["count"]),
                    "level_mean_rank": float(level["level_mean_rank"]),
                    "parameter_effect_range": effect_range,
                    "effect_std": effect_std,
                    "best_parameter": _python_scalar(best[parameter]),
                    "best_parameter_value_key": _value_key(_python_scalar(best[parameter])),
                    "best_parameter_mean_normalized_gap": float(best["mean"]),
                    "best_parameter_std_normalized_gap": float(best["std"]),
                })

    return pd.DataFrame.from_records(rows).sort_values(
        ["problem", "dimension", "parameter", "mean_normalized_gap", "parameter_value_key"],
        kind="stable",
    ).reset_index(drop=True)


def select_scenario_configurations(
    scenario_table: pd.DataFrame,
    experiment: ExperimentSpecification,
    *,
    performance_tolerance: float = DEFAULT_PERFORMANCE_TOLERANCE,
) -> pd.DataFrame:
    """Select one concrete configuration independently for each problem×dimension."""
    if scenario_table.empty:
        return pd.DataFrame()

    expected = {configuration_id(c): c for c in experiment.configurations}
    selected = []
    for (problem, dimension), rows in scenario_table.groupby(["problem", "dimension"], sort=True):
        minimum = float(rows["normalized_gap"].min())
        candidates = rows.loc[rows["normalized_gap"] <= minimum + performance_tolerance].copy()
        candidates = candidates.sort_values(
            ["std_normalized_gap_across_seeds", "mean_wall_seconds", "configuration_id"],
            kind="stable",
        )
        row = candidates.iloc[0].copy()
        config = expected[str(row["configuration_id"])]
        row["algorithm"] = config.algorithm.name
        selected.append(row)

    if not selected:
        return pd.DataFrame()
    result = pd.DataFrame(selected).reset_index(drop=True)
    result.insert(3, "selection_status", "selected")
    return result


def select_problem_configurations(
    problem_configuration_table: pd.DataFrame,
    *,
    performance_tolerance: float = DEFAULT_PERFORMANCE_TOLERANCE,
) -> pd.DataFrame:
    selected = []
    for problem, rows in problem_configuration_table.groupby("problem", sort=True):
        minimum = float(rows["mean_normalized_gap"].min())
        candidates = rows.loc[rows["mean_normalized_gap"] <= minimum + performance_tolerance].copy()
        candidates = candidates.sort_values(
            ["worst_normalized_gap", "mean_wall_seconds", "configuration_id"], kind="stable"
        )
        selected.append(candidates.iloc[0])

    if not selected:
        return pd.DataFrame()
    result = pd.DataFrame(selected).reset_index(drop=True)
    result.insert(3, "selection_status", "selected")
    return result


def create_dimension_parameter_summary_table(analysis: ZOAdaMMAnalysis) -> pd.DataFrame:
    detail = analysis.dimension_parameter_effects
    if detail.empty:
        return pd.DataFrame()
    rows = []
    for problem in analysis.problems:
        for parameter in analysis.parameter_names:
            group = detail[(detail["problem"] == problem) & (detail["parameter"] == parameter)]
            if group.empty:
                continue
            for dimension in sorted(group["dimension"].unique()):
                levels = group[group["dimension"] == dimension]
                first = levels.iloc[0]
                rows.append({
                    "problem": problem,
                    "dimension": int(dimension),
                    "parameter": parameter,
                    "effect_range": float(first["parameter_effect_range"]),
                    "effect_std": float(first["effect_std"]),
                    "best_parameter": first["best_parameter"],
                    "best_parameter_mean_normalized_gap": float(first["best_parameter_mean_normalized_gap"]),
                })
    return pd.DataFrame.from_records(rows)


def create_selected_parameters_by_dimension_table(analysis: ZOAdaMMAnalysis) -> pd.DataFrame:
    detail = analysis.dimension_parameter_effects
    rows = []
    for parameter in analysis.parameter_names:
        row = {"parameter": parameter}
        for problem in analysis.problems:
            for dimension in sorted(analysis.run_table["dimension"].unique()):
                levels = detail[
                    (detail["problem"] == problem)
                    & (detail["dimension"] == dimension)
                    & (detail["parameter"] == parameter)
                ]
                row[f"{problem}_D{dimension}"] = None if levels.empty else levels.iloc[0]["best_parameter"]
        rows.append(row)
    return pd.DataFrame.from_records(rows)


def analyze_zoadamm(
    experiment: ExperimentSpecification,
    store,
    *,
    performance_tolerance: float = DEFAULT_PERFORMANCE_TOLERANCE,
) -> ZOAdaMMAnalysis:
    records = store.load_run_records()
    run_table = _run_table_from_records(records)
    scenario_table = create_scenario_table(run_table)
    problem_configuration = create_problem_configuration_table(scenario_table, experiment)
    problem_parameter = create_problem_parameter_table(problem_configuration, experiment)
    analysis = ZOAdaMMAnalysis(
        experiment_id=experiment_id(experiment),
        parameter_names=_varying_parameter_names(experiment),
        problems=tuple(sorted(run_table["problem"].unique())) if not run_table.empty else (),
        run_table=run_table,
        scenario_table=scenario_table,
        problem_configuration_table=problem_configuration,
        problem_parameter_table=problem_parameter,
        selected_configuration_table=select_problem_configurations(
            problem_configuration,
            performance_tolerance=performance_tolerance,
        ),
        selected_scenario_configuration_table=select_scenario_configurations(
            scenario_table,
            experiment,
            performance_tolerance=performance_tolerance,
        ),
        dimension_parameter_effects=pd.DataFrame(),
    )
    return ZOAdaMMAnalysis(
        experiment_id=analysis.experiment_id,
        parameter_names=analysis.parameter_names,
        problems=analysis.problems,
        run_table=analysis.run_table,
        scenario_table=analysis.scenario_table,
        problem_configuration_table=analysis.problem_configuration_table,
        problem_parameter_table=analysis.problem_parameter_table,
        selected_configuration_table=analysis.selected_configuration_table,
        selected_scenario_configuration_table=analysis.selected_scenario_configuration_table,
        dimension_parameter_effects=create_dimension_parameter_effect_table(run_table, experiment),
    )


def write_zoadamm_analysis_artifacts(analysis: ZOAdaMMAnalysis, output: str | Path) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)

    analysis.run_table.to_csv(output / "run_results.csv", index=False)
    analysis.run_table.to_parquet(output / "run_results.parquet", index=False)
    analysis.scenario_table.to_csv(output / "scenario_results.csv", index=False)
    analysis.scenario_table.to_parquet(output / "scenario_results.parquet", index=False)
    analysis.problem_configuration_table.to_csv(output / "problem_configuration_results.csv", index=False)
    analysis.problem_configuration_table.to_parquet(output / "problem_configuration_results.parquet", index=False)
    analysis.problem_parameter_table.to_csv(output / "problem_parameter_results.csv", index=False)
    analysis.problem_parameter_table.to_parquet(output / "problem_parameter_results.parquet", index=False)
    analysis.selected_configuration_table.to_csv(output / "selected_configurations.csv", index=False)
    analysis.selected_scenario_configuration_table.to_csv(
        output / "selected_scenario_configurations.csv", index=False
    )
    analysis.dimension_parameter_effects.to_csv(output / "problem_parameter_dimension_results.csv", index=False)
    create_dimension_parameter_summary_table(analysis).to_csv(
        output / "problem_parameter_dimension_summary.csv", index=False
    )
    selected_parameters = create_selected_parameters_by_dimension_table(analysis)
    selected_parameters.to_csv(output / "selected_parameters_by_dimension.csv", index=False)
    selected_parameters.to_json(output / "selected_parameters_by_dimension.json", orient="records", indent=2)

    effect_summary = (
        analysis.problem_parameter_table
        .groupby(["problem", "parameter"], sort=True)["mean_normalized_gap"]
        .agg(
            level_count="count",
            minimum_mean_normalized_gap="min",
            maximum_mean_normalized_gap="max",
        )
        .assign(
            effect_range=lambda frame: frame.maximum_mean_normalized_gap - frame.minimum_mean_normalized_gap
        )
        .reset_index()
    )
    effect_summary.to_csv(output / "problem_parameter_effect_summary.csv", index=False)

    metadata = {
        "experiment_id": analysis.experiment_id,
        "algorithm": "ZO-AdaMM",
        "parameter_names": list(analysis.parameter_names),
        "problems": list(analysis.problems),
        "selection_rule": (
            "minimum mean normalized gap per problem; ties within tolerance by "
            "minimum worst normalized gap, then mean wall seconds, then configuration ID"
        ),
        "normalized_gap": "(configuration mean - scenario minimum) / (scenario maximum - scenario minimum), per problem×dimension",
        "performance_tolerance": DEFAULT_PERFORMANCE_TOLERANCE,
        "run_count": len(analysis.run_table),
        "configuration_count": analysis.run_table["configuration_id"].nunique() if not analysis.run_table.empty else 0,
        "scenario_count": len(analysis.scenario_table),
        "scenario_selection_count": len(analysis.selected_scenario_configuration_table),
        "varying_parameter_count": len(analysis.parameter_names),
        "fixed_parameters": [
            column for column in (
                "epsilon",
            ) if column not in analysis.parameter_names
        ],
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

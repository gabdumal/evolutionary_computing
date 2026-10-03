from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd

from ..core.ids import configuration_id, experiment_id, run_id, scenario_id
from ..core.models import ExperimentSpecification, RunResult

DEFAULT_PERFORMANCE_TOLERANCE = 1e-12
PRESENTATION_PROBLEM_ORDER = ("Rosenbrock", "Schwefel", "HappyCat")
PRESENTATION_PARAMETER_ORDER = (
    "population_size", "smp", "srd", "cdc", "spc", "max_velocity", "c1", "mixture_ratio",
)
PRESENTATION_DIMENSIONS = (10, 100)


@dataclass(frozen=True, slots=True)
class CSOAnalysis:
    experiment_id: str
    parameter_names: tuple[str, ...]
    problems: tuple[str, ...]
    run_table: pd.DataFrame
    scenario_table: pd.DataFrame
    problem_configuration_table: pd.DataFrame
    problem_parameter_table: pd.DataFrame
    selected_configuration_table: pd.DataFrame
    dimension_parameter_effects: pd.DataFrame


def _safe_std(values: pd.Series) -> float:
    return float(values.std(ddof=1)) if len(values) > 1 else 0.0


def _value_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _python_scalar(value: Any) -> Any:
    return value.item() if hasattr(value, "item") else value



def create_configuration_manifest(experiment: ExperimentSpecification) -> pd.DataFrame:
    """Materialize the resolved CSO configuration grid without running it."""
    parameter_names = tuple(
        sorted({name for configuration in experiment.configurations for name in configuration.parameters})
    )
    rows = []
    for configuration in experiment.configurations:
        row = {"configuration_id": configuration_id(configuration)}
        row.update(configuration.parameters)
        rows.append(row)
    return pd.DataFrame.from_records(
        rows,
        columns=["configuration_id", *parameter_names],
    )


def create_cso_run_table(results: list[RunResult] | tuple[RunResult, ...]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    parameter_names = tuple(
        sorted({p for result in results for p in result.specification.algorithm.parameters})
    )
    records = []
    for result in results:
        spec = result.specification
        config = spec.algorithm
        scenario = spec.scenario
        record = {
            "run_id": run_id(spec),
            "experiment_id": spec.experiment_id,
            "configuration_id": configuration_id(config),
            "scenario_id": scenario_id(scenario),
            "algorithm": config.algorithm.name,
            "problem": scenario.problem,
            "objective_function": scenario.objective,
            "dimension": scenario.dimension,
            "seed": spec.seed,
            "calculated_value": float(result.objective.best_value),
            "function_evaluations": result.function_evaluations,
            "iterations": result.iterations,
            "cpu_seconds": result.timing.cpu_seconds,
            "wall_seconds": result.timing.wall_seconds,
        }
        record.update({name: config.parameters[name] for name in parameter_names})
        records.append(record)
    return pd.DataFrame.from_records(records)


def create_scenario_table(run_table: pd.DataFrame) -> pd.DataFrame:
    if run_table.empty:
        return pd.DataFrame()
    grouped = run_table.groupby(
        ["problem", "dimension", "configuration_id"], sort=True, dropna=False
    )
    table = grouped.agg(
        mean_best_value=("calculated_value", "mean"),
        std_best_value=("calculated_value", lambda s: _safe_std(s)),
        median_best_value=("calculated_value", "median"),
        min_best_value=("calculated_value", "min"),
        max_best_value=("calculated_value", "max"),
        mean_cpu_seconds=("cpu_seconds", "mean"),
        mean_wall_seconds=("wall_seconds", "mean"),
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
        if spread <= DEFAULT_PERFORMANCE_TOLERANCE:
            table.loc[indices, "normalized_gap"] = 0.0
        else:
            table.loc[indices, "normalized_gap"] = (values - best) / spread

        for index in indices:
            config_id = str(table.loc[index, "configuration_id"])
            seed_values = run_table.loc[
                (run_table["problem"] == problem)
                & (run_table["dimension"] == dimension)
                & (run_table["configuration_id"] == config_id),
                "calculated_value",
            ].astype(float)
            if spread <= DEFAULT_PERFORMANCE_TOLERANCE:
                normalized_seed = pd.Series(0.0, index=seed_values.index)
            else:
                normalized_seed = (seed_values - best) / spread
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
    records = []
    for (problem, config_id), rows in scenario_table.groupby(["problem", "configuration_id"], sort=True):
        config = expected[str(config_id)]
        record = {
            "problem": problem,
            "configuration_id": config_id,
            "algorithm": config.algorithm.name,
            "dimension_count": len(rows),
            "mean_normalized_gap": float(rows["normalized_gap"].mean()),
            "std_normalized_gap": _safe_std(rows["normalized_gap"]),
            "mean_seed_std_normalized_gap": float(rows["std_normalized_gap_across_seeds"].mean()),
            "max_seed_std_normalized_gap": float(rows["std_normalized_gap_across_seeds"].max()),
            "mean_rank": float(rows["scenario_rank"].mean()),
            "worst_normalized_gap": float(rows["normalized_gap"].max()),
            "mean_cpu_seconds": float(rows["mean_cpu_seconds"].mean()),
            "mean_wall_seconds": float(rows["mean_wall_seconds"].mean()),
            "mean_function_evaluations": float(rows["mean_function_evaluations"].mean()),
        }
        for name in parameter_names:
            value = config.parameters[name]
            record[name] = value
            record[f"{name}__key"] = _value_key(value)
        records.append(record)
    columns = ["problem", "configuration_id", "algorithm", *parameter_names,
               *[f"{n}__key" for n in parameter_names], "dimension_count",
               "mean_normalized_gap", "std_normalized_gap", "mean_seed_std_normalized_gap",
               "max_seed_std_normalized_gap", "mean_rank", "worst_normalized_gap",
               "mean_cpu_seconds", "mean_wall_seconds", "mean_function_evaluations"]
    return pd.DataFrame.from_records(records, columns=columns).sort_values(
        ["problem", "mean_normalized_gap", "mean_rank", "configuration_id"], kind="stable"
    ).reset_index(drop=True)


def create_problem_parameter_table(problem_configuration_table: pd.DataFrame, experiment: ExperimentSpecification) -> pd.DataFrame:
    if problem_configuration_table.empty:
        return pd.DataFrame()
    parameter_names = tuple(sorted({p for c in experiment.configurations for p in c.parameters}))
    records = []
    for problem, problem_rows in problem_configuration_table.groupby("problem", sort=False):
        for parameter in parameter_names:
            key = f"{parameter}__key"
            for value_key, rows in problem_rows.groupby(key, sort=False):
                mean_gap = rows["mean_normalized_gap"].mean()
                records.append({
                    "problem": problem,
                    "parameter": parameter,
                    "parameter_value": _python_scalar(rows[parameter].iloc[0]),
                    "parameter_value_key": str(value_key),
                    "configuration_count": len(rows),
                    "mean_normalized_gap": float(mean_gap),
                    "std_normalized_gap": _safe_std(rows["mean_normalized_gap"]),
                    "mean_seed_std_normalized_gap": float(rows["mean_seed_std_normalized_gap"].mean()),
                    "worst_seed_std_normalized_gap": float(rows["max_seed_std_normalized_gap"].max()),
                    "mean_rank": float(rows["mean_rank"].mean()),
                    "worst_configuration_gap": float(rows["worst_normalized_gap"].max()),
                    "mean_cpu_seconds": float(rows["mean_cpu_seconds"].mean()),
                    "mean_function_evaluations": float(rows["mean_function_evaluations"].mean()),
                })
    table = pd.DataFrame.from_records(records)
    if table.empty:
        return table
    table["parameter_effect_range"] = table.groupby(["problem", "parameter"])["mean_normalized_gap"].transform(
        lambda s: float(s.max() - s.min())
    )
    table["level_mean_rank"] = table.groupby(["problem", "parameter"])["mean_normalized_gap"].rank(
        method="average", ascending=True
    )
    return table.sort_values(
        ["problem", "parameter", "mean_normalized_gap", "parameter_value_key"], kind="stable"
    ).reset_index(drop=True)


def create_dimension_parameter_effect_table(cso: CSOAnalysis) -> pd.DataFrame:
    if cso.scenario_table.empty:
        return pd.DataFrame()
    rows = []
    for (problem, dimension, parameter), group in _parameter_dimension_groups(cso):
        levels = group.groupby(parameter, sort=False)["normalized_gap"].agg(["mean", "std", "count"]).reset_index()
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
                "level_mean_rank": float(level["level_mean_rank"]),
                "parameter_effect_range": effect_range,
                "effect_std": effect_std,
                "best_parameter": _python_scalar(best[parameter]),
                "best_parameter_value_key": _value_key(_python_scalar(best[parameter])),
                "best_parameter_mean_normalized_gap": float(best["mean"]),
                "best_parameter_std_normalized_gap": float(best["std"]),
            })
    return pd.DataFrame.from_records(rows).sort_values(
        ["problem", "dimension", "parameter", "mean_normalized_gap", "parameter_value_key"], kind="stable"
    ).reset_index(drop=True)


def _parameter_dimension_groups(cso: CSOAnalysis):
    # Expand scenario-level configuration data with resolved parameter values.
    config_rows = cso.problem_configuration_table.copy()
    parameter_names = cso.parameter_names
    for name in parameter_names:
        config_rows[name] = config_rows[name]
    merged = cso.scenario_table.merge(
        config_rows[["problem", "configuration_id", *parameter_names]],
        on=["problem", "configuration_id"],
        how="left",
        validate="many_to_one",
    )
    for parameter in parameter_names:
        yield from [
            ((problem, dimension, parameter), group)
            for (problem, dimension), scenario_group in merged.groupby(["problem", "dimension"], sort=False)
            for group in [scenario_group[[parameter, "normalized_gap"]]]
        ]


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
            ["worst_normalized_gap", "mean_cpu_seconds", "configuration_id"], kind="stable"
        )
        selected.append(candidates.iloc[0])
    if not selected:
        return pd.DataFrame()
    table = pd.DataFrame(selected).reset_index(drop=True)
    table.insert(3, "selection_status", "selected")
    return table


def create_dimension_parameter_summary_table(cso: CSOAnalysis) -> pd.DataFrame:
    detail = cso.dimension_parameter_effects
    if detail.empty:
        return pd.DataFrame()
    rows = []
    for problem in PRESENTATION_PROBLEM_ORDER:
        for parameter in PRESENTATION_PARAMETER_ORDER:
            group = detail[(detail.problem == problem) & (detail.parameter == parameter)]
            if group.empty:
                continue
            record = {"problem": problem, "parameter": parameter}
            for dimension in PRESENTATION_DIMENSIONS:
                d = group[group.dimension == dimension]
                if d.empty:
                    record[f"effect_interval_D{dimension}"] = None
                    record[f"best_parameter_D{dimension}"] = None
                else:
                    first = d.iloc[0]
                    record[f"effect_interval_D{dimension}"] = f"{first.parameter_effect_range:.6f} ± {first.effect_std:.6f}"
                    record[f"best_parameter_D{dimension}"] = first.best_parameter
            rows.append(record)
    return pd.DataFrame.from_records(rows)


def create_selected_parameters_by_dimension_table(cso: CSOAnalysis) -> pd.DataFrame:
    detail = cso.dimension_parameter_effects
    rows = []
    for parameter in PRESENTATION_PARAMETER_ORDER:
        record = {"parameter": parameter}
        for problem in PRESENTATION_PROBLEM_ORDER:
            for dimension in PRESENTATION_DIMENSIONS:
                d = detail[(detail.problem == problem) & (detail.dimension == dimension) & (detail.parameter == parameter)]
                record[f"{problem}_D{dimension}"] = None if d.empty else d.iloc[0].best_parameter
        rows.append(record)
    return pd.DataFrame.from_records(rows)




def _create_cso_run_table_from_records(records: tuple[dict[str, Any], ...]) -> pd.DataFrame:
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
            "dimension": scenario["dimension"],
            "seed": run["seed"],
            "calculated_value": float(metrics["best_value"]),
            "function_evaluations": int(metrics["function_evaluations"]),
            "iterations": int(metrics["iterations"]),
            "cpu_seconds": float(metrics["cpu_seconds"]),
            "wall_seconds": (
                float(metrics["wall_seconds"])
                if metrics.get("wall_seconds") is not None
                else float("nan")
            ),
        }
        row.update(algorithm["parameters"])
        rows.append(row)
    return pd.DataFrame.from_records(rows, columns=[
        "run_id", "experiment_id", "configuration_id", "scenario_id", "algorithm",
        "problem", "objective_function", "dimension", "seed", *parameter_names,
        "calculated_value", "function_evaluations", "iterations", "cpu_seconds",
        "wall_seconds",
    ])


def _configuration_id_from_payload(configuration: dict[str, Any]) -> str:
    import hashlib
    from ..core.serialization import to_primitive
    payload = json.dumps(to_primitive(configuration), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"cfg_{hashlib.sha256(payload).hexdigest()[:16]}"


def _scenario_id_from_payload(scenario: dict[str, Any]) -> str:
    import hashlib
    from ..core.serialization import to_primitive
    payload = json.dumps(to_primitive(scenario), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"scn_{hashlib.sha256(payload).hexdigest()[:16]}"


def _run_id_from_payload(run: dict[str, Any]) -> str:
    # The serialized RunSpecification is already sufficient to reproduce the
    # public deterministic ID without loading its convergence trace.
    import hashlib
    from ..core.serialization import to_primitive
    payload = json.dumps(to_primitive(run), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"run_{hashlib.sha256(payload).hexdigest()[:16]}"


def analyze_cso(
    experiment: ExperimentSpecification,
    store,
    *,
    performance_tolerance: float = DEFAULT_PERFORMANCE_TOLERANCE,
) -> CSOAnalysis:
    records = store.load_run_records()
    run_table = _create_cso_run_table_from_records(records)
    scenario_table = create_scenario_table(run_table)
    problem_configuration = create_problem_configuration_table(scenario_table, experiment)
    problem_parameter = create_problem_parameter_table(problem_configuration, experiment)
    base = CSOAnalysis(
        experiment_id=experiment_id(experiment),
        parameter_names=tuple(sorted({p for c in experiment.configurations for p in c.parameters})),
        problems=tuple(problem for problem in PRESENTATION_PROBLEM_ORDER if problem in run_table["problem"].unique()),
        run_table=run_table,
        scenario_table=scenario_table,
        problem_configuration_table=problem_configuration,
        problem_parameter_table=problem_parameter,
        selected_configuration_table=select_problem_configurations(problem_configuration, performance_tolerance=performance_tolerance),
        dimension_parameter_effects=pd.DataFrame(),
    )
    return replace(base, dimension_parameter_effects=create_dimension_parameter_effect_table(base))


def write_cso_analysis_artifacts(cso: CSOAnalysis, output: str | Path) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    cso.run_table.to_csv(output / "run_results.csv", index=False)
    cso.run_table.to_parquet(output / "run_results.parquet", index=False)
    cso.scenario_table.to_csv(output / "scenario_results.csv", index=False)
    cso.scenario_table.to_parquet(output / "scenario_results.parquet", index=False)
    cso.problem_configuration_table.to_csv(output / "problem_configuration_results.csv", index=False)
    cso.problem_configuration_table.to_parquet(output / "problem_configuration_results.parquet", index=False)
    cso.problem_parameter_table.to_csv(output / "problem_parameter_results.csv", index=False)
    cso.problem_parameter_table.to_parquet(output / "problem_parameter_results.parquet", index=False)
    cso.selected_configuration_table.to_csv(output / "selected_configurations.csv", index=False)
    cso.dimension_parameter_effects.to_csv(output / "problem_parameter_dimension_results.csv", index=False)
    create_dimension_parameter_summary_table(cso).to_csv(output / "problem_parameter_dimension_summary.csv", index=False)
    selected_parameters = create_selected_parameters_by_dimension_table(cso)
    selected_parameters.to_csv(output / "selected_parameters_by_dimension.csv", index=False)
    selected_parameters.to_json(output / "selected_parameters_by_dimension.json", orient="records", indent=2)
    cso.problem_parameter_table.groupby(["problem", "parameter"], sort=True)["mean_normalized_gap"].agg(
        level_count="count", minimum_mean_normalized_gap="min", maximum_mean_normalized_gap="max"
    ).assign(effect_range=lambda x: x.maximum_mean_normalized_gap - x.minimum_mean_normalized_gap).reset_index().to_csv(
        output / "problem_parameter_effect_summary.csv", index=False
    )
    metadata = {
        "experiment_id": cso.experiment_id,
        "algorithm": "CSO",
        "sensitivity_scope": "problem",
        "parameter_names": list(cso.parameter_names),
        "problems": list(cso.problems),
        "selection_rule": "minimum mean normalized gap per problem; ties within 1e-12 by minimum worst normalized gap, then mean CPU seconds, then configuration ID",
        "normalized_gap": "(configuration mean - scenario minimum) / (scenario maximum - scenario minimum), per problem×dimension",
        "performance_tolerance": DEFAULT_PERFORMANCE_TOLERANCE,
        "run_count": len(cso.run_table),
        "configuration_count": len(cso.problem_configuration_table) // max(1, len(cso.problems)),
        "scenario_count": len(cso.scenario_table),
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

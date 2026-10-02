from __future__ import annotations

"""Deterministic parameter-sensitivity analysis for optimization experiments.

The analysis layer consumes completed experiment artifacts only. It never
executes an optimizer and it never changes the stored experiment results.

The primary performance measure is a scenario-normalized performance gap:

    gap = (oriented_value - scenario_best) / (scenario_worst - scenario_best)

where ``oriented_value`` is the reported objective value for minimization and
its negation for maximization. Consequently, lower values are always better,
and each problem/dimension scenario contributes equally to macro averages.

The analysis first aggregates replications for each configuration within each
problem/dimension scenario, then computes normalized scenario performance,
then computes configuration-level macro performance, and finally computes
marginal parameter effects from those configuration-level results.

This is intentionally descriptive rather than inferential. With a full
factorial parameter grid, marginal effects average over the other parameters;
they should therefore not be interpreted as causal effects when interactions
are substantial. A single-parameter grid provides a cleaner one-parameter
sensitivity experiment.
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Final, Literal, TypeAlias, cast

import pandas as pd

from experiment_artifacts import (
    ExperimentArtifactStore,
    ExperimentRunResult,
)
from experiment_specifications import (
    ExperimentRunSpecification,
    ExperimentSpecification,
    ParameterValue,
)
from validation_analysis import (
    ValidationIssue,
    ValidationReport,
    validate_experiment,
    validate_run_result,
)

SensitivityDesign: TypeAlias = Literal["single_parameter", "factorial"]

DEFAULT_PERFORMANCE_TOLERANCE: Final[float] = 1e-12


class SensitivityAnalysisError(RuntimeError):
    """Raised when sensitivity analysis cannot be performed safely."""


@dataclass(frozen=True, slots=True)
class SensitivityAnalysis:
    """Contain all deterministic sensitivity-analysis tables and metadata."""

    experiment_id: str
    algorithm_name: str
    parameter_names: tuple[str, ...]
    design: SensitivityDesign
    completed_run_count: int
    analyzed_run_count: int
    validation_report: ValidationReport
    run_table: pd.DataFrame
    scenario_table: pd.DataFrame
    configuration_table: pd.DataFrame
    parameter_table: pd.DataFrame

    @property
    def is_complete(self) -> bool:
        """Return whether every expected run was available and valid."""
        return self.analyzed_run_count == self.validation_report.expected_run_count

    @property
    def configuration_count(self) -> int:
        """Return the number of algorithm configurations represented."""
        return len(self.configuration_table)

    @property
    def scenario_count(self) -> int:
        """Return the number of problem/dimension scenarios represented."""
        return len(self.scenario_table[["problem", "dimension"]].drop_duplicates())

    def parameter_effect(self, parameter_name: str) -> pd.DataFrame:
        """Return sensitivity results for one configured parameter."""
        if parameter_name not in self.parameter_names:
            raise KeyError(
                f"Parameter {parameter_name!r} is not part of the sensitivity grid."
            )

        return self.parameter_table.loc[
            self.parameter_table["parameter"] == parameter_name
        ].reset_index(drop=True)


def analyze_sensitivity(
    artifact_store: ExperimentArtifactStore,
    expected_experiment: ExperimentSpecification,
    *,
    require_complete: bool = True,
    performance_tolerance: float = DEFAULT_PERFORMANCE_TOLERANCE,
) -> SensitivityAnalysis:
    """Analyze parameter sensitivity from a completed experiment.

    ``expected_experiment`` is required deliberately. Sensitivity analysis
    needs the declared Cartesian parameter grid to distinguish parameter
    levels from fixed algorithm parameters and to verify that the available
    artifacts correspond to the intended experiment.

    By default every expected run must exist and be valid. Setting
    ``require_complete=False`` permits analysis of the valid subset, while the
    returned validation report still records missing or invalid runs.
    """
    _validate_performance_tolerance(performance_tolerance)
    _validate_sensitivity_grid(expected_experiment)

    validation_report = validate_experiment(
        artifact_store,
        expected_experiment=expected_experiment,
    )

    if require_complete and not validation_report.is_valid:
        raise SensitivityAnalysisError(_format_validation_failure(validation_report))

    expected_runs_by_id = {
        run.run_id: run for run in expected_experiment.iter_run_specifications()
    }

    completed_results = tuple(artifact_store.iter_completed_run_results())
    analyzed_results = _select_analyzable_results(
        completed_results,
        expected_runs_by_id=expected_runs_by_id,
        require_complete=require_complete,
        performance_tolerance=performance_tolerance,
    )

    if not analyzed_results:
        raise SensitivityAnalysisError(
            "No valid completed runs are available for sensitivity analysis."
        )

    run_table = _create_run_table(analyzed_results, expected_experiment)
    scenario_table = _create_scenario_table(
        analyzed_results,
        performance_tolerance=performance_tolerance,
    )
    configuration_table = _create_configuration_table(
        scenario_table,
        expected_experiment,
    )
    parameter_table = _create_parameter_table(
        configuration_table,
        expected_experiment,
    )

    design = (
        "single_parameter"
        if len(expected_experiment.parameter_grid) == 1
        else "factorial"
    )

    return SensitivityAnalysis(
        experiment_id=expected_experiment.experiment_id,
        algorithm_name=expected_experiment.algorithm.display_name,
        parameter_names=tuple(expected_experiment.parameter_grid),
        design=design,
        completed_run_count=len(completed_results),
        analyzed_run_count=len(analyzed_results),
        validation_report=validation_report,
        run_table=run_table,
        scenario_table=scenario_table,
        configuration_table=configuration_table,
        parameter_table=parameter_table,
    )


def create_parameter_effect_table(
    sensitivity_analysis: SensitivityAnalysis,
) -> pd.DataFrame:
    """Return one compact row per parameter with its observed marginal range."""
    if sensitivity_analysis.parameter_table.empty:
        return pd.DataFrame(
            columns=(
                "parameter",
                "level_count",
                "minimum_mean_normalized_gap",
                "maximum_mean_normalized_gap",
                "effect_range",
            )
        )

    records: list[dict[str, object]] = []

    parameter_groups = sensitivity_analysis.parameter_table.groupby(
        "parameter",
        sort=False,
    )

    for parameter_name, parameter_levels in parameter_groups:
        mean_gaps = parameter_levels["mean_normalized_gap"]
        records.append(
            {
                "parameter": parameter_name,
                "level_count": int(parameter_levels["parameter_value"].nunique()),
                "minimum_mean_normalized_gap": float(mean_gaps.min()),
                "maximum_mean_normalized_gap": float(mean_gaps.max()),
                "effect_range": float(mean_gaps.max() - mean_gaps.min()),
            }
        )

    return pd.DataFrame.from_records(records)


def create_configuration_comparison_table(
    sensitivity_analysis: SensitivityAnalysis,
) -> pd.DataFrame:
    """Return configuration performance together with its parameter values."""
    if sensitivity_analysis.configuration_table.empty:
        return sensitivity_analysis.configuration_table.copy()

    parameter_names = sensitivity_analysis.parameter_names
    columns = [
        "configuration_id",
        "algorithm",
        *parameter_names,
        "scenario_count",
        "mean_normalized_gap",
        "std_normalized_gap",
        "mean_seed_std_normalized_gap",
        "max_seed_std_normalized_gap",
        "mean_rank",
        "worst_normalized_gap",
    ]

    return sensitivity_analysis.configuration_table.loc[:, columns].copy()


def _validate_sensitivity_grid(
    experiment: ExperimentSpecification,
) -> None:
    parameter_grid = experiment.parameter_grid

    if not parameter_grid:
        raise ValueError(
            "Sensitivity analysis requires at least one parameter in "
            "ExperimentSpecification.parameter_grid."
        )

    single_level_parameters = tuple(
        parameter_name
        for parameter_name, values in parameter_grid.items()
        if len(values) < 2
    )

    if single_level_parameters:
        names = ", ".join(single_level_parameters)
        raise ValueError(
            "Every sensitivity parameter must have at least two candidate "
            f"values; {names} has fewer than two."
        )


def _validate_performance_tolerance(tolerance: float) -> None:
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        raise TypeError("performance_tolerance must be a real number.")

    if not isfinite(float(tolerance)) or tolerance < 0.0:
        raise ValueError("performance_tolerance must be finite and non-negative.")


def _select_analyzable_results(
    completed_results: tuple[ExperimentRunResult, ...],
    *,
    expected_runs_by_id: Mapping[str, ExperimentRunSpecification],
    require_complete: bool,
    performance_tolerance: float,
) -> tuple[ExperimentRunResult, ...]:
    selected: list[ExperimentRunResult] = []

    for result in completed_results:
        run_id = result.run_specification.run_id
        expected_run = expected_runs_by_id.get(run_id)

        if expected_run is None:
            if require_complete:
                raise SensitivityAnalysisError(
                    f"Completed artifact {run_id!r} is not part of the "
                    "supplied experiment specification."
                )
            continue

        issues = validate_run_result(
            result,
            expected_run_specification=expected_run,
            relative_tolerance=performance_tolerance,
            absolute_tolerance=performance_tolerance,
        )

        if any(issue.is_error for issue in issues):
            if require_complete:
                raise SensitivityAnalysisError(
                    _format_run_validation_failure(run_id, issues)
                )
            continue

        selected.append(result)

    selected.sort(key=lambda result: result.run_specification.run_id)
    return tuple(selected)


def _create_run_table(
    results: Iterable[ExperimentRunResult],
    experiment: ExperimentSpecification,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    parameter_names = tuple(experiment.parameter_grid)

    for result in results:
        run = result.run_specification
        parameter_values = run.configuration.parameters

        record: dict[str, object] = {
            "run_id": run.run_id,
            "configuration_id": run.configuration_id,
            "algorithm": run.configuration.name,
            "problem": run.problem.name,
            "dimension": run.dimension,
            "seed": run.seed,
            "best_value": float(result.best_value),
            "function_evaluations": int(result.function_evaluations),
            "iterations": int(result.iterations),
            "cpu_seconds": float(result.cpu_seconds),
            "scenario": _scenario_identifier(run),
        }

        for parameter_name in parameter_names:
            if parameter_name not in parameter_values:
                raise SensitivityAnalysisError(
                    f"Run {run.run_id!r} is missing sensitivity parameter "
                    f"{parameter_name!r}."
                )

            record[parameter_name] = parameter_values[parameter_name]
            record[f"{parameter_name}__key"] = _parameter_value_key(
                parameter_values[parameter_name]
            )

        records.append(record)

    columns = [
        "run_id",
        "configuration_id",
        "algorithm",
        "problem",
        "dimension",
        "seed",
        "scenario",
        *parameter_names,
        *[f"{name}__key" for name in parameter_names],
        "best_value",
        "function_evaluations",
        "iterations",
        "cpu_seconds",
    ]

    return pd.DataFrame.from_records(records, columns=columns)


def _create_scenario_table(
    results: Iterable[ExperimentRunResult],
    *,
    performance_tolerance: float,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    grouped_results: dict[tuple[str, int, str], list[ExperimentRunResult]] = {}

    for result in results:
        run = result.run_specification
        key = (run.problem.name, run.dimension, run.configuration_id)
        grouped_results.setdefault(key, []).append(result)

    for (problem_name, dimension, configuration_id), group in sorted(
        grouped_results.items()
    ):
        first_run = group[0].run_specification
        optimization = first_run.problem.optimization
        raw_values = [float(result.best_value) for result in group]
        oriented_values = [_orient_value(value, optimization) for value in raw_values]

        records.append(
            {
                "configuration_id": configuration_id,
                "algorithm": first_run.configuration.name,
                "problem": problem_name,
                "dimension": dimension,
                "scenario": _scenario_identifier(first_run),
                "optimization": optimization,
                "replications": len(group),
                "mean_best_value": float(pd.Series(raw_values).mean()),
                "std_best_value": _safe_standard_deviation(raw_values),
                "median_best_value": float(pd.Series(raw_values).median()),
                "minimum_best_value": float(min(raw_values)),
                "maximum_best_value": float(max(raw_values)),
                "mean_function_evaluations": float(
                    pd.Series([result.function_evaluations for result in group]).mean()
                ),
                "mean_cpu_seconds": float(
                    pd.Series([result.cpu_seconds for result in group]).mean()
                ),
                "oriented_mean_best_value": float(pd.Series(oriented_values).mean()),
            }
        )

    table = pd.DataFrame.from_records(records)

    if table.empty:
        return table

    table["normalized_gap"] = 0.0
    table["std_normalized_gap_across_seeds"] = 0.0
    table["scenario_rank"] = 0.0

    for scenario, scenario_rows in table.groupby(
        ["problem", "dimension"],
        sort=False,
    ):
        indices = scenario_rows.index
        oriented_values = scenario_rows["oriented_mean_best_value"]
        scenario_best = float(oriented_values.min())
        scenario_worst = float(oriented_values.max())
        spread = scenario_worst - scenario_best

        if spread <= performance_tolerance:
            normalized_gaps = pd.Series(
                0.0,
                index=indices,
                dtype="float64",
            )
        else:
            normalized_gaps = (oriented_values - scenario_best) / spread

        table.loc[indices, "normalized_gap"] = normalized_gaps
        table.loc[indices, "scenario_rank"] = oriented_values.rank(
            method="average",
            ascending=True,
        )

        for index, row in scenario_rows.iterrows():
            configuration_id = str(row["configuration_id"])
            scenario_problem = str(cast(str, scenario[0]))
            scenario_dimension = int(cast(int, row["dimension"]))
            group = grouped_results[
                (scenario_problem, scenario_dimension, configuration_id)
            ]
            seed_oriented_values = [
                _orient_value(
                    float(result.best_value),
                    group[0].run_specification.problem.optimization,
                )
                for result in group
            ]

            if spread <= performance_tolerance:
                seed_normalized_gaps = [0.0] * len(seed_oriented_values)
            else:
                seed_normalized_gaps = [
                    (value - scenario_best) / spread for value in seed_oriented_values
                ]

            table.loc[index, "std_normalized_gap_across_seeds"] = (
                _safe_standard_deviation(seed_normalized_gaps)
            )

    return table.sort_values(
        ["problem", "dimension", "normalized_gap", "configuration_id"],
        kind="stable",
    ).reset_index(drop=True)


def _create_configuration_table(
    scenario_table: pd.DataFrame,
    experiment: ExperimentSpecification,
) -> pd.DataFrame:
    if scenario_table.empty:
        return pd.DataFrame()

    parameter_names = tuple(experiment.parameter_grid)
    configuration_records: list[dict[str, object]] = []

    configuration_rows = scenario_table.groupby(
        "configuration_id",
        sort=True,
    )

    expected_configurations = {
        configuration.configuration_id: configuration
        for configuration in experiment.iter_algorithm_configurations()
    }

    for configuration_id, rows in configuration_rows:
        configuration = expected_configurations.get(str(configuration_id))
        if configuration is None:
            raise SensitivityAnalysisError(
                f"Configuration {configuration_id!r} was not found in the "
                "expected experiment specification."
            )

        normalized_gaps = rows["normalized_gap"]
        ranks = rows["scenario_rank"]

        record: dict[str, object] = {
            "configuration_id": configuration_id,
            "algorithm": configuration.name,
            "scenario_count": len(rows),
            "mean_normalized_gap": float(normalized_gaps.mean()),
            "std_normalized_gap": _safe_series_standard_deviation(normalized_gaps),
            "mean_seed_std_normalized_gap": float(
                rows["std_normalized_gap_across_seeds"].mean()
            ),
            "max_seed_std_normalized_gap": float(
                rows["std_normalized_gap_across_seeds"].max()
            ),
            "mean_rank": float(ranks.mean()),
            "worst_normalized_gap": float(normalized_gaps.max()),
        }

        for parameter_name in parameter_names:
            value = configuration.parameters[parameter_name]
            record[parameter_name] = value
            record[f"{parameter_name}__key"] = _parameter_value_key(value)

        configuration_records.append(record)

    columns = [
        "configuration_id",
        "algorithm",
        *parameter_names,
        *[f"{name}__key" for name in parameter_names],
        "scenario_count",
        "mean_normalized_gap",
        "std_normalized_gap",
        "mean_seed_std_normalized_gap",
        "max_seed_std_normalized_gap",
        "mean_rank",
        "worst_normalized_gap",
    ]

    return (
        pd.DataFrame.from_records(
            configuration_records,
            columns=columns,
        )
        .sort_values(
            ["mean_normalized_gap", "mean_rank", "configuration_id"],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def _create_parameter_table(
    configuration_table: pd.DataFrame,
    experiment: ExperimentSpecification,
) -> pd.DataFrame:
    if configuration_table.empty:
        return pd.DataFrame()

    records: list[dict[str, object]] = []

    for parameter_name in experiment.parameter_grid:
        parameter_key = f"{parameter_name}__key"
        grouped = configuration_table.groupby(
            parameter_key,
            sort=False,
        )

        levels: list[dict[str, object]] = []

        for value_key, rows in grouped:
            first_value = rows[parameter_name].iloc[0]
            mean_gap = float(rows["mean_normalized_gap"].mean())
            std_gap = _safe_series_standard_deviation(rows["mean_normalized_gap"])
            mean_seed_std_gap = float(rows["mean_seed_std_normalized_gap"].mean())
            worst_seed_std_gap = float(rows["max_seed_std_normalized_gap"].max())
            mean_rank = float(rows["mean_rank"].mean())

            levels.append(
                {
                    "parameter": parameter_name,
                    "parameter_value": first_value,
                    "parameter_value_key": str(value_key),
                    "configuration_count": len(rows),
                    "mean_normalized_gap": mean_gap,
                    "std_normalized_gap": std_gap,
                    "mean_seed_std_normalized_gap": mean_seed_std_gap,
                    "worst_seed_std_normalized_gap": worst_seed_std_gap,
                    "mean_rank": mean_rank,
                    "worst_configuration_gap": float(
                        rows["worst_normalized_gap"].max()
                    ),
                }
            )

        if not levels:
            continue

        level_table = pd.DataFrame.from_records(levels)
        mean_gaps = level_table["mean_normalized_gap"]
        effect_range = float(mean_gaps.max() - mean_gaps.min())

        for level in levels:
            level["parameter_effect_range"] = effect_range
            level["level_mean_rank"] = float(
                mean_gaps.rank(method="average", ascending=True)
                .loc[level_table["parameter_value_key"] == level["parameter_value_key"]]
                .iloc[0]
            )
            records.append(level)

    if not records:
        return pd.DataFrame()

    return (
        pd.DataFrame.from_records(records)
        .sort_values(
            ["parameter", "mean_normalized_gap", "parameter_value_key"],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def _safe_standard_deviation(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0

    return float(pd.Series(values, dtype="float64").std(ddof=1))


def _safe_series_standard_deviation(values: pd.Series) -> float:
    if len(values) <= 1:
        return 0.0

    return float(values.std(ddof=1))


def _orient_value(value: float, optimization: Literal["minimize", "maximize"]) -> float:
    return value if optimization == "minimize" else -value


def _scenario_identifier(run: ExperimentRunSpecification) -> str:
    return f"{run.problem.name}__D{run.dimension}"


def _parameter_value_key(value: ParameterValue) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _format_validation_failure(report: ValidationReport) -> str:
    error_messages = [issue.message for issue in report.error_issues[:5]]
    detail = " ".join(error_messages)

    if report.error_count > 5:
        detail += f" (+{report.error_count - 5} additional errors)."

    return (
        "Sensitivity analysis requires a complete, valid experiment. "
        f"Found {report.error_count} validation errors. {detail}"
    )


def _format_run_validation_failure(
    run_id: str,
    issues: Iterable[ValidationIssue],
) -> str:
    messages = [issue.message for issue in issues]
    detail = " ".join(messages[:5])

    return f"Run {run_id!r} failed sensitivity validation: {detail}"


__all__ = [
    "DEFAULT_PERFORMANCE_TOLERANCE",
    "SensitivityAnalysis",
    "SensitivityAnalysisError",
    "SensitivityDesign",
    "analyze_sensitivity",
    "create_configuration_comparison_table",
    "create_parameter_effect_table",
]

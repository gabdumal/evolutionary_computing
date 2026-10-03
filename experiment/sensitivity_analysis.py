from __future__ import annotations

"""Deterministic, problem-specific parameter-sensitivity analysis.

The analysis layer consumes completed experiment artifacts only. It never
executes an optimizer and never modifies persisted results.

The primary performance measure is a scenario-normalized performance gap:

    gap = (oriented_value - scenario_best) / (scenario_worst - scenario_best)

where ``oriented_value`` is the reported objective value for minimization and
its negation for maximization. Lower values are always better.

The aggregation is deliberately problem-specific:

1. Replications are aggregated for each configuration within each
   problem/dimension scenario.
2. Configurations are compared only against other configurations from the
   same problem and dimension.
3. A configuration's problem-level performance is the equally weighted mean
   across that problem's dimensions.
4. Parameter effects are calculated independently for each problem.
5. One configuration is selected independently for each problem using a
   deterministic lexicographic rule.

No performance value is averaged across different benchmark problems.
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any, Final, Literal, TypeAlias, cast

import pandas as pd

from experiment_artifacts import ExperimentArtifactStore, ExperimentRunResult
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
    """Contain all deterministic problem-specific sensitivity tables."""

    experiment_id: str
    algorithm_name: str
    parameter_names: tuple[str, ...]
    problems: tuple[str, ...]
    design: SensitivityDesign
    completed_run_count: int
    analyzed_run_count: int
    validation_report: ValidationReport
    run_table: pd.DataFrame
    scenario_table: pd.DataFrame
    problem_configuration_table: pd.DataFrame
    problem_parameter_table: pd.DataFrame
    selected_configuration_table: pd.DataFrame

    @property
    def is_complete(self) -> bool:
        """Return whether every expected run was available and valid."""
        return self.analyzed_run_count == self.validation_report.expected_run_count

    @property
    def configuration_count(self) -> int:
        """Return the number of algorithm configurations represented."""
        if self.problem_configuration_table.empty:
            return 0
        return int(self.problem_configuration_table["configuration_id"].nunique())

    @property
    def problem_configuration_count(self) -> int:
        """Return the number of problem/configuration combinations represented."""
        return len(self.problem_configuration_table)

    @property
    def scenario_count(self) -> int:
        """Return the number of problem/dimension scenarios represented."""
        if self.scenario_table.empty:
            return 0
        return len(self.scenario_table[["problem", "dimension"]].drop_duplicates())

    def configuration_results(self, problem: str) -> pd.DataFrame:
        """Return problem-specific configuration results."""
        _validate_problem_name(problem, self.problems)
        return self.problem_configuration_table.loc[
            self.problem_configuration_table["problem"] == problem
        ].reset_index(drop=True)

    def parameter_effect(
        self,
        problem: str,
        parameter_name: str,
    ) -> pd.DataFrame:
        """Return sensitivity results for one parameter within one problem."""
        _validate_problem_name(problem, self.problems)

        if parameter_name not in self.parameter_names:
            raise KeyError(
                f"Parameter {parameter_name!r} is not part of the sensitivity grid."
            )

        return self.problem_parameter_table.loc[
            (self.problem_parameter_table["problem"] == problem)
            & (self.problem_parameter_table["parameter"] == parameter_name)
        ].reset_index(drop=True)

    def selected_configuration(self, problem: str) -> pd.Series:
        """Return the selected configuration row for one problem."""
        _validate_problem_name(problem, self.problems)
        rows = self.selected_configuration_table.loc[
            self.selected_configuration_table["problem"] == problem
        ]
        if len(rows) != 1:
            raise SensitivityAnalysisError(
                f"Expected exactly one selected configuration for {problem!r}; "
                f"found {len(rows)}."
            )
        return rows.iloc[0].copy()


# ---------------------------------------------------------------------------
# Public analysis entry point
# ---------------------------------------------------------------------------


def analyze_sensitivity(
    artifact_store: ExperimentArtifactStore,
    expected_experiment: ExperimentSpecification,
    *,
    require_complete: bool = True,
    performance_tolerance: float = DEFAULT_PERFORMANCE_TOLERANCE,
) -> SensitivityAnalysis:
    """Analyze parameter sensitivity independently for every problem.

    The supplied experiment must declare a Cartesian sensitivity grid. The
    analysis never computes a configuration score by pooling different
    problems together. Dimensions within the same problem are equally weighted.

    By default every expected run must exist and be valid. Setting
    ``require_complete=False`` permits analysis of the valid completed subset,
    while the validation report still records missing or invalid runs.
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
    problem_configuration_table = _create_problem_configuration_table(
        scenario_table,
        expected_experiment,
    )
    problem_parameter_table = _create_problem_parameter_table(
        problem_configuration_table,
        expected_experiment,
    )
    selected_configuration_table = _select_problem_configurations(
        problem_configuration_table,
        performance_tolerance=performance_tolerance,
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
        problems=tuple(problem.name for problem in expected_experiment.problems),
        design=design,
        completed_run_count=len(completed_results),
        analyzed_run_count=len(analyzed_results),
        validation_report=validation_report,
        run_table=run_table,
        scenario_table=scenario_table,
        problem_configuration_table=problem_configuration_table,
        problem_parameter_table=problem_parameter_table,
        selected_configuration_table=selected_configuration_table,
    )


# ---------------------------------------------------------------------------
# Public table helpers
# ---------------------------------------------------------------------------


def create_configuration_comparison_table(
    sensitivity_analysis: SensitivityAnalysis,
) -> pd.DataFrame:
    """Return problem-specific configuration performance."""
    return sensitivity_analysis.problem_configuration_table.copy()


def create_parameter_effect_table(
    sensitivity_analysis: SensitivityAnalysis,
) -> pd.DataFrame:
    """Return observed parameter-effect ranges separately for each problem."""
    table = sensitivity_analysis.problem_parameter_table
    if table.empty:
        return pd.DataFrame(
            columns=(
                "problem",
                "parameter",
                "level_count",
                "minimum_mean_normalized_gap",
                "maximum_mean_normalized_gap",
                "effect_range",
            )
        )

    records: list[dict[str, object]] = []
    for (problem, parameter), rows in table.groupby(
        ["problem", "parameter"],
        sort=False,
    ):
        mean_gaps = rows["mean_normalized_gap"]
        records.append(
            {
                "problem": problem,
                "parameter": parameter,
                "level_count": int(rows["parameter_value"].nunique()),
                "minimum_mean_normalized_gap": float(mean_gaps.min()),
                "maximum_mean_normalized_gap": float(mean_gaps.max()),
                "effect_range": float(mean_gaps.max() - mean_gaps.min()),
            }
        )

    return (
        pd.DataFrame.from_records(records)
        .sort_values(
            ["problem", "parameter"],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def create_selected_configuration_table(
    sensitivity_analysis: SensitivityAnalysis,
) -> pd.DataFrame:
    """Return one deterministically selected configuration per problem."""
    return sensitivity_analysis.selected_configuration_table.copy()


# ---------------------------------------------------------------------------
# Validation and result selection
# ---------------------------------------------------------------------------


def _validate_sensitivity_grid(experiment: ExperimentSpecification) -> None:
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


# ---------------------------------------------------------------------------
# Run and scenario tables
# ---------------------------------------------------------------------------


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
                "mean_best_value": float(pd.Series(raw_values, dtype="float64").mean()),
                "std_best_value": _safe_standard_deviation(raw_values),
                "median_best_value": float(
                    pd.Series(raw_values, dtype="float64").median()
                ),
                "minimum_best_value": float(min(raw_values)),
                "maximum_best_value": float(max(raw_values)),
                "mean_function_evaluations": float(
                    pd.Series(
                        [result.function_evaluations for result in group],
                        dtype="float64",
                    ).mean()
                ),
                "mean_cpu_seconds": float(
                    pd.Series(
                        [result.cpu_seconds for result in group],
                        dtype="float64",
                    ).mean()
                ),
                "oriented_mean_best_value": float(
                    pd.Series(oriented_values, dtype="float64").mean()
                ),
            }
        )

    table = pd.DataFrame.from_records(records)
    if table.empty:
        return table

    table["normalized_gap"] = 0.0
    table["std_normalized_gap_across_seeds"] = 0.0
    table["scenario_rank"] = 0.0

    grouped_scenarios = table.groupby(["problem", "dimension"], sort=False)
    for (problem_name, dimension), scenario_rows in grouped_scenarios:
        indices = scenario_rows.index
        oriented_values = scenario_rows["oriented_mean_best_value"]
        scenario_best = float(oriented_values.min())
        scenario_worst = float(oriented_values.max())
        spread = scenario_worst - scenario_best

        if spread <= performance_tolerance:
            normalized_gaps = pd.Series(0.0, index=indices, dtype="float64")
        else:
            normalized_gaps = (oriented_values - scenario_best) / spread

        table.loc[indices, "normalized_gap"] = normalized_gaps
        table.loc[indices, "scenario_rank"] = oriented_values.rank(
            method="average",
            ascending=True,
        )

        scenario_key = (str(problem_name), int(cast(Any, dimension)))
        for index, row in scenario_rows.iterrows():
            configuration_id = str(row["configuration_id"])
            group = grouped_results[
                (scenario_key[0], scenario_key[1], configuration_id)
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


# ---------------------------------------------------------------------------
# Problem-specific aggregation and parameter effects
# ---------------------------------------------------------------------------


def _create_problem_configuration_table(
    scenario_table: pd.DataFrame,
    experiment: ExperimentSpecification,
) -> pd.DataFrame:
    if scenario_table.empty:
        return pd.DataFrame()

    parameter_names = tuple(experiment.parameter_grid)
    expected_configurations = {
        configuration.configuration_id: configuration
        for configuration in experiment.iter_algorithm_configurations()
    }

    configuration_records: list[dict[str, object]] = []

    grouped = scenario_table.groupby(
        ["problem", "configuration_id"],
        sort=True,
    )

    for (problem_name, configuration_id), rows in grouped:
        configuration = expected_configurations.get(str(configuration_id))
        if configuration is None:
            raise SensitivityAnalysisError(
                f"Configuration {configuration_id!r} was not found in the "
                "expected experiment specification."
            )

        normalized_gaps = rows["normalized_gap"]
        ranks = rows["scenario_rank"]

        record: dict[str, object] = {
            "problem": problem_name,
            "configuration_id": configuration_id,
            "algorithm": configuration.name,
            "dimension_count": len(rows),
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
            "mean_cpu_seconds": float(rows["mean_cpu_seconds"].mean()),
            "mean_function_evaluations": float(
                rows["mean_function_evaluations"].mean()
            ),
        }

        for parameter_name in parameter_names:
            value = configuration.parameters[parameter_name]
            record[parameter_name] = value
            record[f"{parameter_name}__key"] = _parameter_value_key(value)

        configuration_records.append(record)

    columns = [
        "problem",
        "configuration_id",
        "algorithm",
        *parameter_names,
        *[f"{name}__key" for name in parameter_names],
        "dimension_count",
        "mean_normalized_gap",
        "std_normalized_gap",
        "mean_seed_std_normalized_gap",
        "max_seed_std_normalized_gap",
        "mean_rank",
        "worst_normalized_gap",
        "mean_cpu_seconds",
        "mean_function_evaluations",
    ]

    return (
        pd.DataFrame.from_records(configuration_records, columns=columns)
        .sort_values(
            ["problem", "mean_normalized_gap", "mean_rank", "configuration_id"],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def _create_problem_parameter_table(
    problem_configuration_table: pd.DataFrame,
    experiment: ExperimentSpecification,
) -> pd.DataFrame:
    if problem_configuration_table.empty:
        return pd.DataFrame()

    records: list[dict[str, object]] = []

    for problem, problem_rows in problem_configuration_table.groupby(
        "problem", sort=False
    ):
        for parameter_name in experiment.parameter_grid:
            parameter_key = f"{parameter_name}__key"
            grouped = problem_rows.groupby(parameter_key, sort=False)
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
                        "problem": problem,
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
                        "mean_cpu_seconds": float(rows["mean_cpu_seconds"].mean()),
                        "mean_function_evaluations": float(
                            rows["mean_function_evaluations"].mean()
                        ),
                    }
                )

            if not levels:
                continue

            level_table = pd.DataFrame.from_records(levels)
            mean_gaps = level_table["mean_normalized_gap"]
            effect_range = float(mean_gaps.max() - mean_gaps.min())
            level_ranks = mean_gaps.rank(method="average", ascending=True)

            for level_index, level in enumerate(levels):
                level["parameter_effect_range"] = effect_range
                level["level_mean_rank"] = float(level_ranks.iloc[level_index])
                records.append(level)

    return (
        pd.DataFrame.from_records(records)
        .sort_values(
            ["problem", "parameter", "mean_normalized_gap", "parameter_value_key"],
            kind="stable",
        )
        .reset_index(drop=True)
        if records
        else pd.DataFrame()
    )


def _select_problem_configurations(
    problem_configuration_table: pd.DataFrame,
    *,
    performance_tolerance: float,
) -> pd.DataFrame:
    """Select one configuration per problem deterministically.

    Selection priority:

    1. lower mean normalized gap;
    2. among configurations within ``performance_tolerance`` of the best mean,
       lower worst normalized gap;
    3. among remaining ties, lower mean CPU time;
    4. finally, lower configuration ID for reproducibility.
    """
    if problem_configuration_table.empty:
        return pd.DataFrame()

    selected_rows: list[pd.Series] = []

    for problem, rows in problem_configuration_table.groupby("problem", sort=True):
        minimum_gap = float(rows["mean_normalized_gap"].min())
        candidates = rows.loc[
            rows["mean_normalized_gap"] <= minimum_gap + performance_tolerance
        ].copy()

        candidates = candidates.sort_values(
            ["worst_normalized_gap", "mean_cpu_seconds", "configuration_id"],
            kind="stable",
        )
        selected_rows.append(candidates.iloc[0])

    selected = pd.DataFrame(selected_rows).reset_index(drop=True)
    selected.insert(3, "selection_status", "selected")
    return selected


# ---------------------------------------------------------------------------
# Small deterministic helpers
# ---------------------------------------------------------------------------


def _validate_problem_name(problem: str, expected_problems: tuple[str, ...]) -> None:
    if problem not in expected_problems:
        raise KeyError(
            f"Problem {problem!r} is not part of the analyzed experiment. "
            f"Expected one of: {', '.join(expected_problems)}."
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
    "create_selected_configuration_table",
]

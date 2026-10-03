"""Problem- and dimension-specific parameter sensitivity analysis."""

import multiprocessing as mp
from collections.abc import Iterable, Mapping
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from math import isfinite
from typing import Final, cast

import pandas as pd

from experiment_artifacts import ExperimentArtifactStore, ExperimentRunResult
from experiment_specifications import (
    ExperimentRunSpecification,
    ExperimentSpecification,
)
from validation_analysis import (
    ValidationIssue,
    ValidationReport,
    validate_experiment,
    validate_run_result,
)

DEFAULT_PERFORMANCE_TOLERANCE: Final[float] = 1e-12
DEFAULT_MAX_WORKERS: Final[int] = 8
PRESENTATION_PROBLEM_ORDER: Final[tuple[str, ...]] = (
    "Rosenbrock",
    "Schwefel",
    "HappyCat",
)
PRESENTATION_PARAMETER_ORDER: Final[tuple[str, ...]] = (
    "population_size",
    "smp",
    "srd",
    "cdc",
    "spc",
    "max_velocity",
    "c1",
    "mixture_ratio",
)
PRESENTATION_DIMENSIONS: Final[tuple[int, ...]] = (10, 100)


class SensitivityAnalysisError(RuntimeError):
    """Raised when sensitivity analysis cannot be performed safely."""


@dataclass(frozen=True, slots=True)
class SensitivityAnalysis:
    """Contain only the data required by the requested sensitivity tables."""

    parameter_names: tuple[str, ...]
    problems: tuple[str, ...]
    dimension_parameter_effects: pd.DataFrame
    selected_configurations: pd.DataFrame


# ---------------------------------------------------------------------------
# Public analysis
# ---------------------------------------------------------------------------


def analyze_sensitivity(
    artifact_store: ExperimentArtifactStore,
    expected_experiment: ExperimentSpecification,
    *,
    require_complete: bool = True,
    performance_tolerance: float = DEFAULT_PERFORMANCE_TOLERANCE,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> SensitivityAnalysis:
    """Analyze parameter effects independently for every problem/dimension."""
    _validate_performance_tolerance(performance_tolerance)
    _validate_worker_count(max_workers)
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
        raise SensitivityAnalysisError("No valid completed runs are available.")

    dimension_parameter_effects, selected_configurations = (
        _create_dimension_analysis_tables(
            analyzed_results,
            expected_experiment,
            performance_tolerance=performance_tolerance,
            max_workers=max_workers,
        )
    )

    return SensitivityAnalysis(
        parameter_names=tuple(expected_experiment.parameter_grid),
        problems=tuple(problem.name for problem in expected_experiment.problems),
        dimension_parameter_effects=dimension_parameter_effects,
        selected_configurations=selected_configurations,
    )


# ---------------------------------------------------------------------------
# Requested artifacts
# ---------------------------------------------------------------------------


def create_dimension_parameter_summary_table(
    analysis: SensitivityAnalysis,
) -> pd.DataFrame:
    """Create the slide table with effect interval and best level per dimension."""
    rows: list[dict[str, object]] = []
    effects = analysis.dimension_parameter_effects
    problems = _ordered(analysis.problems, PRESENTATION_PROBLEM_ORDER)
    parameters = _ordered(
        analysis.parameter_names,
        PRESENTATION_PARAMETER_ORDER,
    )

    for problem in problems:
        for parameter in parameters:
            parameter_rows = effects.loc[
                (effects["problem"] == problem) & (effects["parameter"] == parameter)
            ]
            record: dict[str, object] = {
                "problem": problem,
                "parameter": parameter,
            }
            for dimension in PRESENTATION_DIMENSIONS:
                dimension_rows = parameter_rows.loc[
                    parameter_rows["dimension"] == dimension
                ]
                if dimension_rows.empty:
                    record[f"effect_interval_D{dimension}"] = None
                    record[f"best_parameter_D{dimension}"] = None
                    continue

                effect_range = float(dimension_rows["effect_range"].iloc[0])
                effect_std = float(dimension_rows["effect_std"].iloc[0])
                best_value = dimension_rows["best_parameter"].iloc[0]
                record[f"effect_interval_D{dimension}"] = (
                    f"{effect_range:.6f} ± {effect_std:.6f}"
                )
                record[f"best_parameter_D{dimension}"] = _format_value(best_value)
            rows.append(record)

    return pd.DataFrame.from_records(
        rows,
        columns=(
            "problem",
            "parameter",
            "effect_interval_D10",
            "effect_interval_D100",
            "best_parameter_D10",
            "best_parameter_D100",
        ),
    )


def create_selected_parameters_by_dimension_table(
    analysis: SensitivityAnalysis,
) -> pd.DataFrame:
    """Create the parameter table from the selected joint configurations."""
    problems = _ordered(analysis.problems, PRESENTATION_PROBLEM_ORDER)
    parameters = _ordered(
        analysis.parameter_names,
        PRESENTATION_PARAMETER_ORDER,
    )

    rows: list[dict[str, object]] = []
    for parameter in parameters:
        record: dict[str, object] = {"parameter": parameter}
        for problem in problems:
            for dimension in PRESENTATION_DIMENSIONS:
                match = analysis.selected_configurations.loc[
                    (analysis.selected_configurations["problem"] == problem)
                    & (analysis.selected_configurations["dimension"] == dimension)
                ]
                record[f"{problem}_D{dimension}"] = (
                    _format_value(match[parameter].iloc[0]) if not match.empty else None
                )
        rows.append(record)

    columns = ["parameter"] + [
        f"{problem}_D{dimension}"
        for problem in problems
        for dimension in PRESENTATION_DIMENSIONS
    ]
    return pd.DataFrame.from_records(rows, columns=columns)


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------


def _create_dimension_analysis_tables(
    results: tuple[ExperimentRunResult, ...],
    experiment: ExperimentSpecification,
    *,
    performance_tolerance: float,
    max_workers: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    parameter_names = tuple(experiment.parameter_grid)

    run_records = _create_run_records(results, experiment)
    runs = pd.DataFrame.from_records(run_records)
    if runs.empty:
        return pd.DataFrame(), pd.DataFrame()

    scenario = _aggregate_configurations(runs)
    parameters = runs[
        ["problem", "configuration_id", *parameter_names]
    ].drop_duplicates(["problem", "configuration_id"])
    scenario = scenario.merge(
        parameters,
        on=["problem", "configuration_id"],
        how="left",
        validate="many_to_one",
    )

    scenario = _normalize_gaps(scenario, performance_tolerance)

    selected_configurations = _select_configurations_by_dimension(
        scenario,
        parameter_names,
    )

    jobs: list[tuple[str, str, int, pd.DataFrame]] = []
    for parameter in parameter_names:
        for (problem, dimension), group in scenario.groupby(
            ["problem", "dimension"],
            sort=False,
        ):
            jobs.append(
                (
                    parameter,
                    str(problem),
                    int(cast(int, dimension)),
                    group[[parameter, "normalized_gap"]].copy(),
                )
            )

    records: list[dict[str, object]] = []
    context = mp.get_context("forkserver")
    with ProcessPoolExecutor(
        max_workers=max_workers,
        mp_context=context,
    ) as executor:
        for parameter_rows in executor.map(
            _analyze_parameter_dimension,
            jobs,
            chunksize=1,
        ):
            records.extend(parameter_rows)

    effects = (
        pd.DataFrame.from_records(records)
        .sort_values(
            ["problem", "dimension", "parameter", "mean_normalized_gap"],
            kind="stable",
        )
        .reset_index(drop=True)
    )
    return effects, selected_configurations


def _analyze_parameter_dimension(
    job: tuple[str, str, int, pd.DataFrame],
) -> list[dict[str, object]]:
    parameter, problem, dimension, group = job
    level_rows: list[dict[str, object]] = []

    for parameter_value, level_group in group.groupby(
        parameter,
        sort=False,
        dropna=False,
    ):
        gaps = level_group["normalized_gap"]
        typed_value = _python_scalar(parameter_value)
        level_rows.append(
            {
                "problem": problem,
                "dimension": dimension,
                "parameter": parameter,
                "parameter_value": typed_value,
                "parameter_value_key": _parameter_value_key(typed_value),
                "mean_normalized_gap": float(gaps.mean()),
                "std_normalized_gap": (
                    float(gaps.std(ddof=1)) if len(gaps) > 1 else 0.0
                ),
            }
        )

    if not level_rows:
        return []

    means = pd.Series(
        [cast(float, row["mean_normalized_gap"]) for row in level_rows],
        dtype="float64",
    )
    effect_range = float(means.max() - means.min())
    effect_std = _safe_std(means)
    best_row = min(
        level_rows,
        key=lambda row: (
            cast(float, row["mean_normalized_gap"]),
            cast(str, row["parameter_value_key"]),
        ),
    )
    best_parameter = _python_scalar(best_row["parameter_value"])

    for row in level_rows:
        row["effect_range"] = effect_range
        row["effect_std"] = effect_std
        row["best_parameter"] = best_parameter

    return level_rows


def _select_configurations_by_dimension(
    scenario: pd.DataFrame,
    parameter_names: tuple[str, ...],
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for (problem, dimension), group in scenario.groupby(
        ["problem", "dimension"],
        sort=False,
    ):
        rows = group.to_dict(orient="records")
        best = min(
            rows,
            key=lambda row: (
                cast(float, row["normalized_gap"]),
                str(row["configuration_id"]),
            ),
        )
        records.append(
            {
                "problem": str(problem),
                "dimension": int(cast(int, dimension)),
                "configuration_id": str(best["configuration_id"]),
                "normalized_gap": cast(float, best["normalized_gap"]),
                **{parameter: best[parameter] for parameter in parameter_names},
            }
        )

    return (
        pd.DataFrame.from_records(
            records,
            columns=(
                "problem",
                "dimension",
                "configuration_id",
                "normalized_gap",
                *parameter_names,
            ),
        )
        .sort_values(
            ["problem", "dimension"],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def _create_run_records(
    results: Iterable[ExperimentRunResult],
    experiment: ExperimentSpecification,
) -> list[dict[str, object]]:
    parameter_names = tuple(experiment.parameter_grid)
    records: list[dict[str, object]] = []

    for result in results:
        run = result.run_specification
        parameters = run.configuration.parameters
        record: dict[str, object] = {
            "problem": run.problem.name,
            "dimension": run.dimension,
            "configuration_id": run.configuration_id,
            "optimization": run.problem.optimization,
            "best_value": float(result.best_value),
        }
        for parameter in parameter_names:
            if parameter not in parameters:
                raise SensitivityAnalysisError(
                    f"Run {run.run_id!r} is missing parameter {parameter!r}."
                )
            record[parameter] = parameters[parameter]
        records.append(record)

    return records


def _aggregate_configurations(runs: pd.DataFrame) -> pd.DataFrame:
    return runs.groupby(
        ["problem", "dimension", "configuration_id"],
        as_index=False,
        sort=False,
    ).agg(
        mean_best_value=("best_value", "mean"),
        optimization=("optimization", "first"),
    )


def _normalize_gaps(
    scenario: pd.DataFrame,
    performance_tolerance: float,
) -> pd.DataFrame:
    result = scenario.copy()
    result["normalized_gap"] = 0.0

    for indices in result.groupby(
        ["problem", "dimension"],
        sort=False,
    ).groups.values():
        group = result.loc[indices]
        values = group["mean_best_value"].astype(float)
        if group["optimization"].iloc[0] == "maximize":
            values = -values
        best = float(values.min())
        worst = float(values.max())
        spread = worst - best
        if spread <= performance_tolerance:
            result.loc[indices, "normalized_gap"] = 0.0
        else:
            result.loc[indices, "normalized_gap"] = (values - best) / spread

    return result


# ---------------------------------------------------------------------------
# Validation and formatting
# ---------------------------------------------------------------------------


def _validate_worker_count(max_workers: int) -> None:
    if isinstance(max_workers, bool) or not isinstance(max_workers, int):
        raise TypeError("max_workers must be a positive integer.")
    if max_workers <= 0:
        raise ValueError("max_workers must be a positive integer.")


def _validate_sensitivity_grid(experiment: ExperimentSpecification) -> None:
    if not experiment.parameter_grid:
        raise ValueError("Sensitivity analysis requires a non-empty parameter grid.")

    invalid = tuple(
        name for name, values in experiment.parameter_grid.items() if len(values) < 2
    )
    if invalid:
        names = ", ".join(invalid)
        raise ValueError(f"Sensitivity parameters need at least two levels: {names}.")


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
                    f"Completed artifact {run_id!r} is not expected."
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


def _ordered(
    names: Iterable[str],
    preferred: tuple[str, ...],
) -> tuple[str, ...]:
    available = tuple(names)
    first = tuple(name for name in preferred if name in available)
    remaining = tuple(name for name in available if name not in first)
    return first + remaining


def _python_scalar(value: object) -> object:
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except (TypeError, ValueError):
            return value
    return value


def _parameter_value_key(value: object) -> str:
    return repr(value)


def _format_value(value: object) -> str:
    value = _python_scalar(value)
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    return str(value)


def _safe_std(values: pd.Series) -> float:
    return float(values.std(ddof=1)) if len(values) > 1 else 0.0


def _format_validation_failure(report: ValidationReport) -> str:
    messages = [issue.message for issue in report.error_issues[:5]]
    detail = " ".join(messages)
    if report.error_count > 5:
        detail += f" (+{report.error_count - 5} additional errors)."
    return f"Sensitivity validation failed. {detail}"


def _format_run_validation_failure(
    run_id: str,
    issues: Iterable[ValidationIssue],
) -> str:
    messages = " ".join(issue.message for issue in issues)
    return f"Run {run_id!r} failed validation. {messages}"


__all__ = [
    "DEFAULT_MAX_WORKERS",
    "DEFAULT_PERFORMANCE_TOLERANCE",
    "PRESENTATION_DIMENSIONS",
    "SensitivityAnalysis",
    "SensitivityAnalysisError",
    "analyze_sensitivity",
    "create_dimension_parameter_summary_table",
    "create_selected_parameters_by_dimension_table",
]

from __future__ import annotations

from dataclasses import dataclass
import math

from ..artifacts import ArtifactStore
from ..core.ids import configuration_id, experiment_id, run_id, scenario_id
from ..core.models import ExperimentSpecification, RunResult


@dataclass(frozen=True, slots=True)
class ValidationReport:
    experiment_id: str
    expected_runs: int
    observed_runs: int
    missing_run_ids: tuple[str, ...]
    unexpected_run_ids: tuple[str, ...]
    invalid_run_ids: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def completed_runs(self) -> int:
        return self.observed_runs


def validate_experiment(
    experiment: ExperimentSpecification,
    store: ArtifactStore,
) -> ValidationReport:
    expected_specs = tuple(experiment.iter_run_specifications())
    expected_ids = {run_id(specification) for specification in expected_specs}
    observed_ids = set(store.completed_run_ids())

    errors: list[str] = []
    invalid: set[str] = set()

    if experiment_id(experiment) != experiment_id(store.experiment):
        errors.append("Artifact store experiment does not match supplied experiment.")

    missing = tuple(sorted(expected_ids - observed_ids))
    unexpected = tuple(sorted(observed_ids - expected_ids))

    if missing:
        errors.append(f"Missing completed runs: {len(missing)}.")
    if unexpected:
        errors.append(f"Unexpected completed runs: {len(unexpected)}.")

    for identifier in sorted(observed_ids & expected_ids):
        try:
            result = store.load_run(identifier)
            run_errors = _validate_result(result)
        except Exception as exc:
            run_errors = (f"{identifier}: unable to load run: {exc}",)

        if run_errors:
            invalid.add(identifier)
            errors.extend(run_errors)

    if invalid:
        errors.append(f"Invalid runs: {len(invalid)}.")

    return ValidationReport(
        experiment_id=experiment_id(experiment),
        expected_runs=len(expected_specs),
        observed_runs=len(observed_ids),
        missing_run_ids=missing,
        unexpected_run_ids=unexpected,
        invalid_run_ids=tuple(sorted(invalid)),
        errors=tuple(errors),
    )


def _validate_result(result: RunResult) -> tuple[str, ...]:
    specification = result.specification
    identifier = run_id(specification)
    errors: list[str] = []

    if specification.experiment_id == "":
        errors.append(f"{identifier}: empty experiment_id.")

    if result.function_evaluations > specification.budget.max_function_evaluations:
        errors.append(f"{identifier}: function-evaluation budget exceeded.")

    if len(result.objective.best_solution) != specification.scenario.dimension:
        errors.append(f"{identifier}: best solution has wrong dimension.")

    if not math.isfinite(result.objective.best_value):
        errors.append(f"{identifier}: best value is not finite.")

    convergence_evaluations = result.convergence.function_evaluations
    convergence_values = result.convergence.best_values

    if convergence_evaluations[-1] > result.function_evaluations:
        errors.append(f"{identifier}: convergence exceeds reported evaluations.")

    if abs(convergence_values[-1] - result.objective.best_value) > 1e-10:
        errors.append(f"{identifier}: convergence does not end at best value.")

    for previous, current in zip(convergence_values, convergence_values[1:]):
        if current > previous + 1e-10:
            errors.append(f"{identifier}: convergence is not best-so-far monotone.")
            break

    if configuration_id(specification.algorithm) == "":
        errors.append(f"{identifier}: invalid configuration identity.")
    if scenario_id(specification.scenario) == "":
        errors.append(f"{identifier}: invalid scenario identity.")

    return tuple(errors)


__all__ = ["ValidationReport", "validate_experiment"]

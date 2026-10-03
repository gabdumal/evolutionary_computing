from __future__ import annotations

from dataclasses import dataclass

from ..artifacts import ArtifactStore
from ..core.models import ExperimentSpecification


@dataclass(frozen=True, slots=True)
class ValidationReport:
    expected_runs: int
    observed_runs: int
    missing_runs: int
    invalid_runs: int
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def validate_experiment(
    experiment: ExperimentSpecification,
    store: ArtifactStore,
) -> ValidationReport:
    expected = tuple(experiment.iter_run_specifications())
    expected_ids = {__import__(
        "optimization_experiments.core.ids",
        fromlist=["run_id"],
    ).run_id(spec) for spec in expected}

    dataframe = store.load_runs(experiment)
    observed_ids = set()
    errors: list[str] = []

    if not dataframe.empty and "specification" in dataframe.columns:
        # Kept deliberately conservative; detailed schema validation belongs here
        # once the first concrete adapter is installed.
        observed_runs = len(dataframe)
    else:
        observed_runs = len(dataframe)

    for spec in expected:
        identifier = __import__(
            "optimization_experiments.core.ids",
            fromlist=["run_id"],
        ).run_id(spec)
        if store.has_run(identifier):
            observed_ids.add(identifier)

    missing = expected_ids - observed_ids

    return ValidationReport(
        expected_runs=len(expected),
        observed_runs=observed_runs,
        missing_runs=len(missing),
        invalid_runs=len(errors),
        errors=tuple(errors),
    )

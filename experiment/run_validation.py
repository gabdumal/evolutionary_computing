from __future__ import annotations

"""Run and validate a CSO hyperparameter-grid experiment."""

from experiment_artifacts import DEFAULT_ARTIFACT_ROOT, ExperimentArtifactStore
from experiment_execution import DEFAULT_MAX_WORKERS, execute_experiment
from experiment_specifications import (
    DEFAULT_PARAMETERS_FOR_CSO,
    DEFAULT_PROBLEMS,
    AlgorithmSpecification,
    ExperimentSpecification,
    SeedSpecification,
    TerminationSpecification,
)
from validation_analysis import validate_experiment

ARTIFACT_ROOT = DEFAULT_ARTIFACT_ROOT

ALGORITHM_IMPORT_PATH = "niapy.algorithms.basic.CatSwarmOptimization"


HYPERPARAMETER_GRID = {
    "c1": (1.05, 2.05, 3.05),
    "cdc": (0.65, 0.85, 1.0),
    "max_velocity": (0.9, 1.9, 2.9),
    "mixture_ratio": (0.05, 0.1, 0.2),
    "population_size": (15, 30, 60),
    "smp": (2, 3, 4),
    "spc": (True, False),
    "srd": (0.1, 0.2, 0.4),
}

PROBLEMS = DEFAULT_PROBLEMS

SEEDS = SeedSpecification(
    replications=3,
)

TERMINATION = TerminationSpecification(
    max_evaluations=10_000,
)


def create_validation_experiment() -> ExperimentSpecification:
    """Create the hyperparameter-grid experiment specification."""
    return ExperimentSpecification(
        name="cat-swarm-hyperparameter-validation",
        algorithm=AlgorithmSpecification(
            import_path=ALGORITHM_IMPORT_PATH,
            parameters=DEFAULT_PARAMETERS_FOR_CSO,
        ),
        problems=PROBLEMS,
        parameter_grid=HYPERPARAMETER_GRID,
        seeds=SEEDS,
        termination=TERMINATION,
        description=(
            "Validation campaign for a small Cartesian grid of Cat Swarm "
            "Optimization hyperparameters."
        ),
    )


def main() -> None:
    """Execute the grid and validate all persisted results."""
    experiment = create_validation_experiment()

    print("Experiment:", experiment.name)
    print("Experiment ID:", experiment.experiment_id)
    print("Configurations:", experiment.configuration_count)
    print("Expected runs:", experiment.run_count)
    print("Parameter grid:", dict(experiment.parameter_grid))
    print()

    execution_report = execute_experiment(
        experiment,
        artifact_root=ARTIFACT_ROOT,
        max_workers=DEFAULT_MAX_WORKERS,
    )

    print(execution_report)
    print()

    artifact_store = ExperimentArtifactStore(
        ARTIFACT_ROOT,
        experiment,
    )

    validation_report = validate_experiment(
        artifact_store,
        expected_experiment=experiment,
    )

    print(f"Valid: {validation_report.is_valid}")
    print(f"Expected runs: {validation_report.expected_run_count}")
    print(f"Completed runs: {validation_report.completed_run_count}")
    print(f"Missing runs: {validation_report.missing_run_count}")
    print(f"Invalid runs: {validation_report.invalid_run_count}")
    print(f"Errors: {validation_report.error_count}")
    print(f"Warnings: {validation_report.warning_count}")

    for issue in validation_report.issues:
        print(issue)

    if not validation_report.is_valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

from __future__ import annotations

"""Run and validate a CSO hyperparameter-grid experiment."""

from experiment_artifacts import ExperimentArtifactStore
from experiment_execution import execute_experiment
from experiment_specifications import (
    AlgorithmSpecification,
    ExperimentSpecification,
    ProblemSpecification,
    SeedSpecification,
    TerminationSpecification,
)
from validation_analysis import validate_experiment

ARTIFACT_ROOT = "_artifacts"

ALGORITHM_IMPORT_PATH = "niapy.algorithms.basic.CatSwarmOptimization"

BASE_ALGORITHM_PARAMETERS = {
    "population_size": 30,
    "mixture_ratio": 0.1,
    "c1": 2.05,
    "smp": 3,
    "spc": True,
    "cdc": 0.85,
    "srd": 0.2,
    "max_velocity": 1.9,
}

# Keep this grid deliberately small for the first validation campaign.
# The Cartesian product below produces 9 configurations.
HYPERPARAMETER_GRID = {
    "mixture_ratio": (0.1, 0.3, 0.5),
    "c1": (1.0, 2.05, 3.0),
}

PROBLEMS = (
    ProblemSpecification("Sphere", (10, 100)),
    ProblemSpecification("Rastrigin", (10, 100)),
    ProblemSpecification("Step", (10, 100)),
)

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
            parameters=BASE_ALGORITHM_PARAMETERS,
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
        max_workers=6,
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

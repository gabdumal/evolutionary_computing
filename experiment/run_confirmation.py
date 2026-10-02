from __future__ import annotations

"""Run and validate the selected Cat Swarm Optimization configurations.

Unlike the sensitivity campaigns, this experiment uses an explicit list of
configurations rather than a Cartesian parameter grid. Every listed
configuration is evaluated on the same benchmark scenarios and five seeds.
"""

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
    "cdc": 1.0,
    "srd": 0.2,
    "max_velocity": 1.9,
}

# These are the representative configurations selected from the two-stage
# sensitivity analysis. Values omitted here inherit from the fixed baseline
# parameters above.
CONFIRMATION_CONFIGURATIONS = (
    {
        # A: high srd, larger population, upper max velocity / mixture ratio.
        "population_size": 30,
        "mixture_ratio": 0.2,
        "srd": 1.0,
        "max_velocity": 1.0,
    },
    {
        # B: high srd with a medium population.
        "population_size": 15,
        "mixture_ratio": 0.1,
        "srd": 1.0,
        "max_velocity": 1.0,
    },
    {
        # C: high srd with the smallest population tested in the refinement.
        "population_size": 5,
        "mixture_ratio": 0.1,
        "srd": 1.0,
        "max_velocity": 0.5,
    },
    {
        # D: low srd boundary paired with a small population.
        "population_size": 10,
        "mixture_ratio": 0.0,
        "srd": 0.4,
        "max_velocity": 0.25,
    },
    {
        # E: representative point from the strong-performing mid/high-srd
        # region of the refinement campaign.
        "population_size": 30,
        "mixture_ratio": 0.05,
        "srd": 0.8,
        "max_velocity": 0.5,
    },
)

PROBLEMS = (
    ProblemSpecification("Sphere", (10, 100)),
    ProblemSpecification("Rastrigin", (10, 100)),
    ProblemSpecification("Step", (10, 100)),
)

SEEDS = SeedSpecification(
    replications=5,
)

TERMINATION = TerminationSpecification(
    max_evaluations=10_000,
)


def create_confirmation_experiment() -> ExperimentSpecification:
    """Create the explicit representative-configuration experiment."""
    return ExperimentSpecification(
        name="cat-swarm-confirmation",
        algorithm=AlgorithmSpecification(
            import_path=ALGORITHM_IMPORT_PATH,
            parameters=BASE_ALGORITHM_PARAMETERS,
        ),
        problems=PROBLEMS,
        configurations=CONFIRMATION_CONFIGURATIONS,
        seeds=SEEDS,
        termination=TERMINATION,
        description=(
            "Confirmatory comparison of representative Cat Swarm Optimization "
            "configurations selected after two-stage sensitivity analysis."
        ),
    )


def main() -> None:
    """Execute the confirmation experiment and validate persisted results."""
    experiment = create_confirmation_experiment()

    print("Experiment:", experiment.name)
    print("Experiment ID:", experiment.experiment_id)
    print("Configurations:", experiment.configuration_count)
    print("Expected runs:", experiment.run_count)
    print("Seeds:", experiment.seeds.selected_seeds)
    print("Explicit configurations:")
    for index, configuration in enumerate(
        experiment.iter_algorithm_configurations(),
        start=1,
    ):
        print(
            f"  {index}. {configuration.configuration_id}: {configuration.parameters}"
        )
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

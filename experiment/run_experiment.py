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


PROBLEMS = DEFAULT_PROBLEMS

SEEDS = SeedSpecification(
    replications=3,
)

TERMINATION = TerminationSpecification(
    max_evaluations=10_000,
)


def main() -> None:
    experiment = ExperimentSpecification(
        name="cat-swarm-baseline",
        algorithm=AlgorithmSpecification(
            import_path=ALGORITHM_IMPORT_PATH,
            parameters={
                **DEFAULT_PARAMETERS_FOR_CSO,
            },
        ),
        problems=PROBLEMS,
        seeds=SEEDS,
        termination=TERMINATION,
    )

    report = execute_experiment(
        experiment,
        artifact_root=ARTIFACT_ROOT,
        max_workers=DEFAULT_MAX_WORKERS,
    )

    print(report)

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


if __name__ == "__main__":
    main()

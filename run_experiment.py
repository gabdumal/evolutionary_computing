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


def main() -> None:
    experiment = ExperimentSpecification(
        name="cat-swarm-baseline",
        algorithm=AlgorithmSpecification(
            import_path="niapy.algorithms.basic.CatSwarmOptimization",
            parameters={
                "population_size": 30,
                "mixture_ratio": 0.1,
                "c1": 2.05,
                "smp": 3,
                "spc": True,
                "cdc": 0.85,
                "srd": 0.2,
                "max_velocity": 1.9,
            },
        ),
        problems=(
            ProblemSpecification("Sphere", (10, 100)),
            ProblemSpecification("Rastrigin", (10, 100)),
            ProblemSpecification("Step", (10, 100)),
        ),
        seeds=SeedSpecification(
            replications=5,
        ),
        termination=TerminationSpecification(
            max_evaluations=10_000,
        ),
    )

    report = execute_experiment(
        experiment,
        artifact_root="_artifacts",
        max_workers=6,
    )

    print(report)

    artifact_store = ExperimentArtifactStore(
        "_artifacts",
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

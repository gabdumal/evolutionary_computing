from experiment_execution import execute_experiment
from experiment_specifications import (
    AlgorithmSpecification,
    ExperimentSpecification,
    ProblemSpecification,
    SeedSpecification,
    TerminationSpecification,
)


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


if __name__ == "__main__":
    main()

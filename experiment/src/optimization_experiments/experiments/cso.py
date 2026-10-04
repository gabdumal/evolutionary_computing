from __future__ import annotations

from ..algorithms.cso import cso_algorithm_specification
from ..core.models import AlgorithmConfiguration, EvaluationBudget, ExperimentSpecification, SeedPlan
from .benchmark import default_benchmark_scenarios


SMOKE_SEEDS = SeedPlan((27, 32, 59))


def create_cso_smoke_experiment() -> ExperimentSpecification:
    algorithm = cso_algorithm_specification()
    configuration = AlgorithmConfiguration(
        algorithm=algorithm,
        parameters=dict(algorithm.fixed_parameters),
    )

    return ExperimentSpecification(
        name="cso-smoke",
        algorithm=algorithm,
        scenarios=default_benchmark_scenarios(dimensions=(10, 100)),
        configurations=(configuration,),
        seeds=SMOKE_SEEDS,
        budget=EvaluationBudget(1_000),
        metadata={
            "purpose": "post-refactor smoke validation",
        },
    )


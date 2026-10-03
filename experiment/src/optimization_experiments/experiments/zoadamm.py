from __future__ import annotations

from ..algorithms.zoadamm_spec import zoadamm_algorithm_specification
from ..core.models import (
    AlgorithmConfiguration,
    EvaluationBudget,
    ExperimentSpecification,
    SeedPlan,
)
from .benchmark import default_benchmark_scenarios


SMOKE_SEEDS = SeedPlan((27, 32, 59))


def create_zoadamm_smoke_experiment() -> ExperimentSpecification:
    algorithm = zoadamm_algorithm_specification()
    configuration = AlgorithmConfiguration(
        algorithm=algorithm,
        parameters=dict(algorithm.fixed_parameters),
    )

    return ExperimentSpecification(
        name="zoadamm-smoke",
        algorithm=algorithm,
        scenarios=default_benchmark_scenarios(dimensions=(10, 100)),
        configurations=(configuration,),
        seeds=SMOKE_SEEDS,
        budget=EvaluationBudget(1_000),
        metadata={
            "purpose": "post-implementation smoke validation",
            "reference": "Chen et al., NeurIPS 2019",
        },
    )

from __future__ import annotations

from ..algorithms.cso_zoadamm_spec import cso_zoadamm_algorithm_specification
from ..core.models import (
    AlgorithmConfiguration,
    EvaluationBudget,
    ExperimentSpecification,
    SeedPlan,
)
from .benchmark import default_benchmark_scenarios


CSO_ZOADAMM_SMOKE_BUDGET = 1_000
CSO_ZOADAMM_BUDGET = 10_000
CSO_ZOADAMM_SEEDS = (27, 32, 59)
CSO_ZOADAMM_DIMENSIONS = (10, 100)
CSO_ZOADAMM_CSO_FRACTION = 0.8


def create_cso_zoadamm_smoke_experiment() -> ExperimentSpecification:
    algorithm = cso_zoadamm_algorithm_specification()
    configuration = AlgorithmConfiguration(
        algorithm=algorithm,
        parameters=dict(algorithm.fixed_parameters),
    )
    return ExperimentSpecification(
        name="cso-zoadamm-smoke",
        algorithm=algorithm,
        scenarios=default_benchmark_scenarios(dimensions=CSO_ZOADAMM_DIMENSIONS),
        configurations=(configuration,),
        seeds=SeedPlan(CSO_ZOADAMM_SEEDS),
        budget=EvaluationBudget(CSO_ZOADAMM_SMOKE_BUDGET),
        metadata={
            "purpose": "post-implementation smoke validation",
            "design": "sequential_hybrid",
            "hybrid": "CSO exploration -> ZO-AdaMM refinement",
            "cso_budget_fraction": CSO_ZOADAMM_CSO_FRACTION,
        },
    )


def create_cso_zoadamm_campaign_experiment() -> ExperimentSpecification:
    algorithm = cso_zoadamm_algorithm_specification()
    configuration = AlgorithmConfiguration(
        algorithm=algorithm,
        parameters=dict(algorithm.fixed_parameters),
    )
    return ExperimentSpecification(
        name="cso-zoadamm-80-20-3seed",
        algorithm=algorithm,
        scenarios=default_benchmark_scenarios(dimensions=CSO_ZOADAMM_DIMENSIONS),
        configurations=(configuration,),
        seeds=SeedPlan(CSO_ZOADAMM_SEEDS),
        budget=EvaluationBudget(CSO_ZOADAMM_BUDGET),
        metadata={
            "purpose": "final CSO-ZO-AdaMM hybrid benchmark campaign",
            "design": "sequential_hybrid",
            "hybrid": "CSO exploration -> ZO-AdaMM refinement",
            "cso_budget_fraction": CSO_ZOADAMM_CSO_FRACTION,
            "cso_budget_fraction_description": "80% of total function evaluations",
            "zoadamm_budget_fraction_description": "20% of total function evaluations",
            "seeds": ",".join(str(seed) for seed in CSO_ZOADAMM_SEEDS),
            "dimensions": ",".join(str(dimension) for dimension in CSO_ZOADAMM_DIMENSIONS),
            "function_evaluations_per_run": CSO_ZOADAMM_BUDGET,
            "parameter_source": "canonical CSO and ZO-AdaMM default parameters",
        },
    )
    return experiment

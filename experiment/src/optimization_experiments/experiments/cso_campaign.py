from __future__ import annotations

from itertools import product

from ..algorithms.cso import cso_algorithm_specification
from ..core.models import (
    AlgorithmConfiguration,
    EvaluationBudget,
    ExperimentSpecification,
    SeedPlan,
)
from .benchmark import default_benchmark_scenarios


CSO_GRID = {
    "population_size": (15, 30, 60),
    "mixture_ratio": (0.1, 0.3, 0.5),
    "c1": (1.05, 2.05, 3.05),
    "smp": (2, 3, 5),
    "spc": (False, True),
    "cdc": (0.6, 0.85, 1.0),
    "srd": (0.1, 0.2, 0.4),
    "max_velocity": (1.0, 1.9, 3.0),
}

CSO_PARAMETER_ORDER = tuple(CSO_GRID)
CSO_SEEDS = (27, 32, 59)
CSO_DIMENSIONS = (10, 100)
CSO_BUDGET = 10_000
CSO_EXPECTED_CONFIGURATION_COUNT = 4_374
CSO_EXPECTED_RUN_COUNT = 78_732

# The implementation backend is part of experiment identity through metadata.
# This deliberately prevents mixing runs produced by the previous generic
# Python objective wrapper with the native-NiaPy backend used in this campaign.
CSO_EVALUATION_BACKEND = "niapy-native-benchmarks-v1"


def _grid_configurations() -> tuple[AlgorithmConfiguration, ...]:
    algorithm = cso_algorithm_specification()
    configurations = []
    for values in product(*(CSO_GRID[name] for name in CSO_PARAMETER_ORDER)):
        parameters = dict(zip(CSO_PARAMETER_ORDER, values, strict=True))
        configurations.append(
            AlgorithmConfiguration(
                algorithm=algorithm,
                parameters=parameters,
            )
        )
    return tuple(configurations)


def create_cso_grid_experiment() -> ExperimentSpecification:
    algorithm = cso_algorithm_specification()
    configurations = _grid_configurations()
    if len(configurations) != CSO_EXPECTED_CONFIGURATION_COUNT:
        raise RuntimeError(
            f"CSO grid produced {len(configurations)} configurations; "
            f"expected {CSO_EXPECTED_CONFIGURATION_COUNT}."
        )

    scenarios = default_benchmark_scenarios(dimensions=CSO_DIMENSIONS)
    experiment = ExperimentSpecification(
        name="cso-grid-3seed",
        algorithm=algorithm,
        scenarios=scenarios,
        configurations=configurations,
        seeds=SeedPlan(CSO_SEEDS),
        budget=EvaluationBudget(CSO_BUDGET),
        metadata={
            "purpose": "complete CSO hyperparameter validation and sensitivity analysis",
            "design": "full_factorial",
            "sensitivity_scope": "problem",
            "selection_scope": "problem",
            "normalized_gap": "scenario-local min-max gap over configuration means",
            "performance_tolerance": 1e-12,
            "evaluation_backend": CSO_EVALUATION_BACKEND,
            "parameter_order": ",".join(CSO_PARAMETER_ORDER),
            "seeds": ",".join(str(seed) for seed in CSO_SEEDS),
            "dimensions": ",".join(str(dimension) for dimension in CSO_DIMENSIONS),
            "function_evaluations_per_run": CSO_BUDGET,
        },
    )
    if experiment.run_count != CSO_EXPECTED_RUN_COUNT:
        raise RuntimeError(
            f"CSO grid produced {experiment.run_count} runs; expected {CSO_EXPECTED_RUN_COUNT}."
        )
    return experiment

from __future__ import annotations

from itertools import product
from typing import Any

from ..algorithms.cso import cso_algorithm_specification
from ..core.models import (
    AlgorithmConfiguration,
    EvaluationBudget,
    ExperimentSpecification,
    SeedPlan,
)
from .benchmark import default_benchmark_scenarios


# Full-factorial screening grid. Every numeric parameter has three levels and
# SPC is binary. This gives 3^7 * 2 = 4,374 configurations.
CSO_GRID = {
    "population_size": (20, 30, 60),
    "mixture_ratio": (0.05, 0.10, 0.20),
    "c1": (1.00, 2.05, 3.00),
    "smp": (2, 3, 5),
    "spc": (False, True),
    "cdc": (0.25, 0.50, 0.85),
    "srd": (0.05, 0.20, 0.50),
    "max_velocity": (0.5, 1.9, 5.0),
}

CSO_GRID_SEEDS = SeedPlan((27, 32, 59))
CSO_GRID_BUDGET = EvaluationBudget(10_000)
CSO_GRID_DIMENSIONS = (10, 100)


def iter_cso_grid_parameters():
    names = tuple(CSO_GRID)
    levels = tuple(CSO_GRID[name] for name in names)
    for values in product(*levels):
        yield dict(zip(names, values, strict=True))


def cso_grid_configuration_count() -> int:
    count = 1
    for levels in CSO_GRID.values():
        count *= len(levels)
    return count


def create_cso_grid_experiment() -> ExperimentSpecification:
    algorithm = cso_algorithm_specification()
    configurations = tuple(
        AlgorithmConfiguration(
            algorithm=algorithm,
            parameters=parameters,
        )
        for parameters in iter_cso_grid_parameters()
    )

    return ExperimentSpecification(
        name="cso-grid-3seed",
        algorithm=algorithm,
        scenarios=default_benchmark_scenarios(dimensions=CSO_GRID_DIMENSIONS),
        configurations=configurations,
        seeds=CSO_GRID_SEEDS,
        budget=CSO_GRID_BUDGET,
        metadata={
            "purpose": "full-factorial CSO hyperparameter analysis",
            "grid_design": "3-level full factorial plus binary SPC",
            "configuration_count": cso_grid_configuration_count(),
            "seed_count": len(CSO_GRID_SEEDS.seeds),
            "scenario_count": 6,
            "evaluation_budget": CSO_GRID_BUDGET.max_function_evaluations,
        },
    )


__all__ = [
    "CSO_GRID",
    "CSO_GRID_BUDGET",
    "CSO_GRID_DIMENSIONS",
    "CSO_GRID_SEEDS",
    "cso_grid_configuration_count",
    "create_cso_grid_experiment",
    "iter_cso_grid_parameters",
]

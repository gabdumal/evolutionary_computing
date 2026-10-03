from __future__ import annotations

from itertools import product

from ..algorithms.zoadamm_spec import (
    ZOADAMM_PARAMETER_SCHEMA,
    zoadamm_algorithm_specification,
)
from ..core.models import (
    AlgorithmConfiguration,
    EvaluationBudget,
    ExperimentSpecification,
    SeedPlan,
)
from .benchmark import default_benchmark_scenarios

# Full-factorial design: enough levels to study the main algorithmic controls
# while keeping the campaign substantially smaller than the CSO campaign.
ZOADAMM_GRID = {
    # Reference code uses 1e-3. The grid broadens this by ~1.5 orders of
    # magnitude on either side while retaining a central reference setting.
    "learning_rate": (1e-3, 3e-3, 1e-2, 3e-2),
    # beta1=0 is an explicit special case in the paper; larger values test
    # increasing momentum memory.
    "beta1": (0.0, 0.5, 0.9),
    # The paper notes a practical preference for small beta2; 0.99 is retained
    # as the high-memory reference endpoint.
    "beta2": (0.1, 0.5, 0.99),
    # mu=1e-3 is the reference experimental value; all levels remain small
    # relative to the 1/sqrt(d) bound for d <= 100 used in this campaign.
    "mu": (1e-4, 1e-3, 1e-2),
    # q controls variance reduction versus query consumption per update.
    "q": (1, 5, 10, 20),
    # The reference script enables decay; constant alpha is included as a
    # controlled alternative for this benchmark study.
    "decay_learning_rate": (False, True),
}

ZOADAMM_PARAMETER_ORDER = tuple(ZOADAMM_GRID)
ZOADAMM_SEEDS = (27, 32, 59)
ZOADAMM_DIMENSIONS = (10, 100)
ZOADAMM_BUDGET = 10_000
ZOADAMM_EXPECTED_CONFIGURATION_COUNT = 864
ZOADAMM_EXPECTED_RUN_COUNT = 15_552
ZOADAMM_EPSILON = 1e-12


def _grid_configurations() -> tuple[AlgorithmConfiguration, ...]:
    algorithm = zoadamm_algorithm_specification()
    configurations = []
    for values in product(*(ZOADAMM_GRID[name] for name in ZOADAMM_PARAMETER_ORDER)):
        parameters = dict(zip(ZOADAMM_PARAMETER_ORDER, values, strict=True))
        parameters["epsilon"] = ZOADAMM_EPSILON
        configurations.append(
            AlgorithmConfiguration(
                algorithm=algorithm,
                parameters=parameters,
            )
        )
    return tuple(configurations)


def create_zoadamm_grid_experiment() -> ExperimentSpecification:
    algorithm = zoadamm_algorithm_specification()
    configurations = _grid_configurations()
    if len(configurations) != ZOADAMM_EXPECTED_CONFIGURATION_COUNT:
        raise RuntimeError(
            f"ZO-AdaMM grid produced {len(configurations)} configurations; "
            f"expected {ZOADAMM_EXPECTED_CONFIGURATION_COUNT}."
        )

    experiment = ExperimentSpecification(
        name="zoadamm-grid-3seed",
        algorithm=algorithm,
        scenarios=default_benchmark_scenarios(dimensions=ZOADAMM_DIMENSIONS),
        configurations=configurations,
        seeds=SeedPlan(ZOADAMM_SEEDS),
        budget=EvaluationBudget(ZOADAMM_BUDGET),
        metadata={
            "purpose": "complete ZO-AdaMM hyperparameter validation and sensitivity analysis",
            "design": "full_factorial",
            "parameter_order": ",".join(ZOADAMM_PARAMETER_ORDER),
            "seeds": ",".join(str(seed) for seed in ZOADAMM_SEEDS),
            "dimensions": ",".join(str(dimension) for dimension in ZOADAMM_DIMENSIONS),
            "function_evaluations_per_run": ZOADAMM_BUDGET,
            "epsilon": ZOADAMM_EPSILON,
            "beta1_schedule": "constant beta1_t = beta1",
            "objective_setting": "deterministic benchmark functions",
            "reference_paper": "Chen et al., NeurIPS 2019",
            "reference_repository": "KaidiXu/ZO-AdaMM",
            "query_accounting": "one initial f(x) plus q probe evaluations and one post-update evaluation per full iteration; exact FE budget enforced",
            "probe_boundary_handling": "coordinate-wise clipping to benchmark box before probe evaluation",
            "central_grid_point": {
                "learning_rate": 1e-3,
                "beta1": 0.9,
                "beta2": 0.99,
                "mu": 1e-3,
                "q": 10,
                "decay_learning_rate": True,
                "epsilon": ZOADAMM_EPSILON,
            },
        },
    )

    if experiment.run_count != ZOADAMM_EXPECTED_RUN_COUNT:
        raise RuntimeError(
            f"ZO-AdaMM grid produced {experiment.run_count} runs; "
            f"expected {ZOADAMM_EXPECTED_RUN_COUNT}."
        )
    return experiment

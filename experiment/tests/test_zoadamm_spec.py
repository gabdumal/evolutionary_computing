from optimization_experiments.algorithms.zoadamm_spec import (
    ZOADAMM_DEFAULT_PARAMETERS,
    zoadamm_algorithm_specification,
)
from optimization_experiments.experiments.zoadamm import create_zoadamm_smoke_experiment


def test_zoadamm_schema_matches_defaults():
    algorithm = zoadamm_algorithm_specification()
    assert set(algorithm.parameter_schema.names) == set(ZOADAMM_DEFAULT_PARAMETERS)
    assert algorithm.fixed_parameters == ZOADAMM_DEFAULT_PARAMETERS


def test_zoadamm_smoke_shape():
    experiment = create_zoadamm_smoke_experiment()
    assert experiment.run_count == 18
    assert len(experiment.scenarios) == 6
    assert experiment.seeds.seeds == (27, 32, 59)
    assert experiment.budget.max_function_evaluations == 1_000

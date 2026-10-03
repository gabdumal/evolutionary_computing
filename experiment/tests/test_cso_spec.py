
from optimization_experiments.analysis import create_configuration_manifest
from optimization_experiments.algorithms.cso import (
    CSO_DEFAULT_PARAMETERS,
    cso_algorithm_specification,
)
from optimization_experiments.experiments.cso import create_cso_smoke_experiment


def test_cso_schema_matches_defaults():
    algorithm = cso_algorithm_specification()
    assert set(algorithm.parameter_schema.names) == set(CSO_DEFAULT_PARAMETERS)
    assert len(algorithm.fixed_parameters) == len(CSO_DEFAULT_PARAMETERS)


def test_cso_smoke_shape():
    experiment = create_cso_smoke_experiment()
    assert experiment.run_count == 18
    assert len(experiment.scenarios) == 6
    assert experiment.seeds.seeds == (27, 32, 59)
    assert experiment.budget.max_function_evaluations == 1_000


def test_configuration_manifest_has_full_grid():
    from optimization_experiments.experiments.cso_campaign import create_cso_grid_experiment

    experiment = create_cso_grid_experiment()
    frame = create_configuration_manifest(experiment)
    assert len(frame) == 4_374
    assert list(frame.columns) == [
        "configuration_id",
        "c1",
        "cdc",
        "max_velocity",
        "mixture_ratio",
        "population_size",
        "smp",
        "spc",
        "srd",
    ]

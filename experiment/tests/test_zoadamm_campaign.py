from optimization_experiments.analysis import create_configuration_manifest
from optimization_experiments.experiments.zoadamm_campaign import (
    ZOADAMM_BUDGET,
    ZOADAMM_EXPECTED_CONFIGURATION_COUNT,
    ZOADAMM_EXPECTED_RUN_COUNT,
    ZOADAMM_GRID,
    ZOADAMM_SEEDS,
    create_zoadamm_grid_experiment,
)


def test_zoadamm_grid_shape():
    experiment = create_zoadamm_grid_experiment()
    assert len(experiment.configurations) == ZOADAMM_EXPECTED_CONFIGURATION_COUNT
    assert experiment.run_count == ZOADAMM_EXPECTED_RUN_COUNT
    assert experiment.seeds.seeds == ZOADAMM_SEEDS
    assert experiment.budget.max_function_evaluations == ZOADAMM_BUDGET
    assert tuple(experiment.metadata["parameter_order"].split(",")) == tuple(ZOADAMM_GRID)


def test_zoadamm_grid_manifest():
    experiment = create_zoadamm_grid_experiment()
    frame = create_configuration_manifest(experiment)
    assert len(frame) == ZOADAMM_EXPECTED_CONFIGURATION_COUNT
    assert set(frame["epsilon"]) == {1e-12}
    for name, levels in ZOADAMM_GRID.items():
        assert set(frame[name]) == set(levels)

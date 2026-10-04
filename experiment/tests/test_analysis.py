import pandas as pd

from optimization_experiments.analysis import (
    create_best_configuration_results,
    create_configuration_results,
    create_parameter_effects,
    create_run_results,
)
from optimization_experiments.algorithms.cso import cso_algorithm_specification
from optimization_experiments.core import (
    AlgorithmConfiguration,
    BenchmarkScenario,
    EvaluationBudget,
    ExperimentSpecification,
    SeedPlan,
)
from optimization_experiments.core.serialization import to_primitive


def make_payload(seed: int, value: float, c1: float = 1.0):
    algorithm = cso_algorithm_specification()
    parameters = dict(algorithm.fixed_parameters)
    parameters["c1"] = c1
    configuration = AlgorithmConfiguration(algorithm, parameters)
    scenario = BenchmarkScenario("Sphere", 2, "sphere", -5, 5)
    specification = __import__(
        "optimization_experiments.core", fromlist=["RunSpecification"]
    ).RunSpecification(
        experiment_id="exp_analysis",
        experiment_name="analysis",
        algorithm=configuration,
        scenario=scenario,
        seed=seed,
        budget=EvaluationBudget(10),
    )
    return {
        "run": to_primitive(specification),
        "metrics": {
            "best_value": value,
            "function_evaluations": 10,
            "iterations": 3,
            "cpu_seconds": 1.0 + seed / 1000.0,
        },
    }


def test_requested_analysis_tables():
    runs = create_run_results((
        make_payload(27, 3.0),
        make_payload(32, 1.0),
        make_payload(59, 1.0),
    ))
    assert len(runs) == 3
    assert runs.iloc[0]["run_id"].startswith("run_")
    configs = create_configuration_results(runs)
    assert len(configs) == 1
    assert configs.iloc[0]["seed_count"] == 3
    assert configs.iloc[0]["calculated_value_mean"] == 5.0 / 3.0

    best = create_best_configuration_results(configs)
    assert set(best["configuration_id"]) == {configs.iloc[0]["configuration_id"]}

    effects = create_parameter_effects(runs)
    assert not effects.empty
    assert "mean_normalized_effect" in effects.columns

from pathlib import Path

import pandas as pd

from optimization_experiments.analysis.zoadamm import (
    analyze_zoadamm,
    create_problem_parameter_table,
    create_scenario_table,
)
from optimization_experiments.core.ids import configuration_id
from optimization_experiments.core.models import AlgorithmConfiguration, EvaluationBudget, ExperimentSpecification, SeedPlan, BenchmarkScenario
from optimization_experiments.algorithms.zoadamm_spec import zoadamm_algorithm_specification


def _small_experiment():
    algorithm = zoadamm_algorithm_specification()
    config_a = AlgorithmConfiguration(algorithm=algorithm, parameters={**algorithm.fixed_parameters, "learning_rate": 1e-3})
    config_b = AlgorithmConfiguration(algorithm=algorithm, parameters={**algorithm.fixed_parameters, "learning_rate": 1e-2})
    scenario = BenchmarkScenario("Sphere", 3, "sphere", -5.0, 5.0)
    return ExperimentSpecification(
        name="zoadamm-analysis-test",
        algorithm=algorithm,
        scenarios=(scenario,),
        configurations=(config_a, config_b),
        seeds=SeedPlan((27, 32, 59)),
        budget=EvaluationBudget(20),
    ), config_a, config_b


def test_scenario_table_has_three_seed_statistics():
    experiment, config_a, config_b = _small_experiment()
    rows = []
    for config, values in ((config_a, (1.0, 2.0, 3.0)), (config_b, (2.0, 3.0, 4.0))):
        cid = configuration_id(config)
        for seed, value in zip((27, 32, 59), values):
            rows.append({
                "problem": "Sphere",
                "dimension": 3,
                "configuration_id": cid,
                "calculated_value": value,
                "cpu_seconds": 0.1,
                "wall_seconds": 0.2,
                "function_evaluations": 20,
                "seed": seed,
            })
    table = create_scenario_table(pd.DataFrame(rows))
    assert set(table["seed_count"]) == {3}
    assert set(table.columns) >= {"min_best_value", "max_best_value", "mean_best_value", "std_best_value"}


def test_problem_parameter_table_is_balanced():
    experiment, config_a, config_b = _small_experiment()
    from optimization_experiments.analysis.zoadamm import create_problem_configuration_table

    scenario_rows = []
    for config, mean_gap in ((config_a, 0.0), (config_b, 1.0)):
        cid = configuration_id(config)
        scenario_rows.append({
            "problem": "Sphere",
            "dimension": 3,
            "configuration_id": cid,
            "normalized_gap": mean_gap,
            "std_normalized_gap_across_seeds": 0.0,
            "scenario_rank": 1.0 if mean_gap == 0.0 else 2.0,
            "mean_cpu_seconds": 0.1,
            "mean_wall_seconds": 0.2,
            "mean_function_evaluations": 20.0,
        })
    scenario_table = pd.DataFrame(scenario_rows)
    problem_configuration = create_problem_configuration_table(scenario_table, experiment)
    result = create_problem_parameter_table(problem_configuration, experiment)
    level = result[(result["problem"] == "Sphere") & (result["parameter"] == "learning_rate")]
    assert len(level) == 2
    assert set(level["parameter_value"]) == {1e-3, 1e-2}
    assert set(level["parameter_effect_range"]) == {1.0}


def test_full_analysis_shapes_from_records(tmp_path):
    from optimization_experiments.analysis.zoadamm import analyze_zoadamm
    from optimization_experiments.artifacts.store import ArtifactStore
    from optimization_experiments.core.serialization import to_primitive
    from optimization_experiments.core.ids import experiment_id
    from optimization_experiments.experiments.zoadamm_campaign import create_zoadamm_grid_experiment

    # Keep this test small while exercising every analysis stage.
    algorithm = zoadamm_algorithm_specification()
    configs = [
        AlgorithmConfiguration(
            algorithm=algorithm,
            parameters={
                **algorithm.fixed_parameters,
                "learning_rate": 1e-3,
                "beta1": 0.0,
                "beta2": 0.1,
                "mu": 1e-4,
                "q": 1,
                "decay_learning_rate": False,
            },
        ),
        AlgorithmConfiguration(
            algorithm=algorithm,
            parameters={
                **algorithm.fixed_parameters,
                "learning_rate": 1e-2,
                "beta1": 0.9,
                "beta2": 0.99,
                "mu": 1e-2,
                "q": 20,
                "decay_learning_rate": True,
            },
        ),
    ]
    scenarios = tuple(
        BenchmarkScenario(problem, dimension, objective, lower, upper)
        for dimension in (10, 100)
        for problem, objective, lower, upper in (
            ("HappyCat", "happycat", -100.0, 100.0),
            ("Rosenbrock", "rosenbrock", -30.0, 30.0),
            ("Schwefel", "schwefel", -500.0, 500.0),
        )
    )
    experiment = ExperimentSpecification(
        name="zoadamm-analysis-full-test",
        algorithm=algorithm,
        scenarios=scenarios,
        configurations=tuple(configs),
        seeds=SeedPlan((27, 32, 59)),
        budget=EvaluationBudget(20),
    )
    eid = experiment_id(experiment)

    records = []
    for config in configs:
        for scenario in scenarios:
            for seed in (27, 32, 59):
                spec = next(
                    run for run in experiment.iter_run_specifications()
                    if run.algorithm.parameters == config.parameters
                    and run.scenario == scenario
                    and run.seed == seed
                )
                payload_run = to_primitive(spec)
                records.append({
                    "status": "completed",
                    "run": payload_run,
                    "metrics": {
                        "best_value": float((1.0 if config is configs[0] else 2.0) + 0.01 * seed),
                        "function_evaluations": 20,
                        "iterations": 9,
                        "cpu_seconds": 0.1,
                        "wall_seconds": 0.1,
                    },
                })

    class FakeStore:
        def load_run_records(self):
            return tuple(records)

    result = analyze_zoadamm(experiment, FakeStore())
    assert len(result.run_table) == 36
    assert len(result.scenario_table) == 12
    assert len(result.problem_configuration_table) == 6
    assert len(result.selected_configuration_table) == 3
    assert len(result.selected_scenario_configuration_table) == 6
    assert set(result.parameter_names) == {"beta1", "beta2", "decay_learning_rate", "learning_rate", "mu", "q"}
    assert "epsilon" not in result.parameter_names
    assert not result.dimension_parameter_effects.empty

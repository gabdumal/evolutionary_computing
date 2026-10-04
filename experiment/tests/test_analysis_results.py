import json
from pathlib import Path

from optimization_experiments.analysis.results import (
    create_best_configuration_results,
    create_configuration_results,
    create_parameter_effects,
    create_parameter_effect_summary,
    create_run_results,
    write_analysis_artifacts,
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


def _payload(seed: int, value: float, c1: float) -> dict:
    algorithm = cso_algorithm_specification()
    parameters = dict(algorithm.fixed_parameters)
    parameters["c1"] = c1
    configuration = AlgorithmConfiguration(algorithm, parameters)
    scenario = BenchmarkScenario(
        problem="Sphere",
        dimension=2,
        objective="sphere",
        lower_bound=-5,
        upper_bound=5,
    )
    spec = __import__(
        "optimization_experiments.core",
        fromlist=["RunSpecification"],
    ).RunSpecification(
        experiment_id="exp_test",
        experiment_name="analysis",
        algorithm=configuration,
        scenario=scenario,
        seed=seed,
        budget=EvaluationBudget(10),
    )
    return {
        "run": to_primitive(spec),
        "metrics": {
            "best_value": value,
            "function_evaluations": 10,
            "iterations": 3,
            "cpu_seconds": 1.0 + seed / 1000.0,
        },
    }


def test_four_requested_tables():
    records = (
        _payload(27, 3.0, 1.0),
        _payload(32, 1.0, 1.0),
        _payload(59, 1.0, 1.0),
        _payload(27, 2.0, 2.0),
        _payload(32, 4.0, 2.0),
        _payload(59, 3.0, 2.0),
    )
    runs = create_run_results(records)
    assert len(runs) == 6
    expected_base = [
        "run_id", "seed", "algorithm", "objective_function",
        "dimension", "configuration_id",
    ]
    assert list(runs.columns[:6]) == expected_base
    assert "problem" not in runs.columns
    assert list(runs.columns[-4:]) == [
        "calculated_value", "function_evaluations", "iterations", "cpu_seconds",
    ]
    assert set(["c1", "cdc", "max_velocity", "mixture_ratio", "population_size", "smp", "spc", "srd"]).issubset(runs.columns)

    configs = create_configuration_results(runs)
    assert len(configs) == 2
    assert set(configs["seed_count"]) == {3}
    row = configs.loc[configs["c1"] == 1.0].iloc[0]
    assert row["calculated_value_mean"] == 5.0 / 3.0
    expected_std = ((1.0 - (5.0 / 3.0)) ** 2 + (1.0 - (5.0 / 3.0)) ** 2 + (3.0 - (5.0 / 3.0)) ** 2) ** 0.5 / (2 ** 0.5)
    assert abs(row["calculated_value_std"] - expected_std) < 1e-12
    assert "calculated_value_min" not in configs.columns
    assert "calculated_value_max" not in configs.columns
    assert "iterations_mean" in configs.columns
    assert "iterations_std" in configs.columns
    assert "cpu_seconds_mean" in configs.columns
    assert "cpu_seconds_std" in configs.columns

    best = create_best_configuration_results(configs)
    assert len(best) == 1
    assert best.iloc[0]["c1"] == 1.0
    assert best.iloc[0]["calculated_value_mean"] == 5.0 / 3.0

    effects = create_parameter_effects(runs)
    c1_effects = effects.loc[effects["parameter"] == "c1"]
    assert set(c1_effects["parameter_value"]) == {1.0, 2.0}
    summary = create_parameter_effect_summary(runs, effects)
    c1_summary = summary.loc[summary["parameter"] == "c1"].iloc[0]
    assert c1_summary["best_marginal_parameter_value"] == 1.0
    assert c1_summary["worst_marginal_parameter_value"] == 2.0
    assert c1_summary["parameter_effect_range"] == 4.0 / 3.0
    assert c1_summary["normalized_parameter_effect"] > 0.0
    assert c1_summary["normalized_parameter_effect_percent"] > 0.0
    assert "mean_calculated_value" in c1_effects.columns
    assert "std_calculated_value" in c1_effects.columns
    assert "problem" not in c1_effects.columns
    assert set(c1_effects["seed_count"]) == {3}


def test_write_analysis_artifacts_only_requested_outputs(tmp_path: Path):
    records = (_payload(27, 1.0, 1.0), _payload(32, 2.0, 1.0), _payload(59, 3.0, 1.0))
    from optimization_experiments.analysis.results import AnalysisTables
    from optimization_experiments.core import ExperimentSpecification

    algorithm = cso_algorithm_specification()
    configuration = AlgorithmConfiguration(algorithm, dict(algorithm.fixed_parameters))
    scenario = BenchmarkScenario("Sphere", 2, "sphere", -5, 5)
    experiment = ExperimentSpecification(
        name="analysis-test",
        algorithm=algorithm,
        scenarios=(scenario,),
        configurations=(configuration,),
        seeds=SeedPlan((27, 32, 59)),
        budget=EvaluationBudget(10),
    )
    runs = create_run_results(records)
    configs = create_configuration_results(runs)
    effects = create_parameter_effects(runs)
    tables = AnalysisTables(
        runs,
        configs,
        create_best_configuration_results(configs),
        effects,
        create_parameter_effect_summary(runs, effects),
    )
    write_analysis_artifacts(tables, experiment, tmp_path)

    assert sorted(path.name for path in tmp_path.glob("*.csv")) == [
        "best_configuration_results.csv",
        "configuration_results.csv",
        "parameter_effect_summary.csv",
        "parameter_effects.csv",
        "run_results.csv",
    ]
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["seeds"] == [27, 32, 59]

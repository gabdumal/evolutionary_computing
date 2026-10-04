import numpy as np

from optimization_experiments.algorithms.base import AlgorithmAdapter
from optimization_experiments.algorithms.cso_zoadamm import CSOZOAdaMMAdapter
from optimization_experiments.algorithms.cso_zoadamm_spec import (
    CSO_ZOADAMM_FIXED_PARAMETERS,
    CSO_ZOADAMM_PARAMETER_SCHEMA,
    CSO_ZOADAMM_VALIDATED_PROFILES,
    cso_zoadamm_algorithm_specification,
    cso_zoadamm_validated_parameters,
)
from optimization_experiments.core import (
    AlgorithmConfiguration,
    BenchmarkScenario,
    ConvergenceTrace,
    EvaluationBudget,
    ExperimentSpecification,
    ObjectiveResult,
    RunResult,
    SeedPlan,
    TimingResult,
)
from optimization_experiments.algorithms.zoadamm import ZOAdaMMAdapter


class FakeCSOAdapter(AlgorithmAdapter):
    name = "CSO"

    def run(self, specification):
        dimension = specification.scenario.dimension
        best = np.full(dimension, 0.25, dtype=float)
        return RunResult(
            specification=specification,
            objective=ObjectiveResult(
                best_value=float(np.sum(best**2)),
                best_solution=tuple(best),
            ),
            function_evaluations=specification.budget.max_function_evaluations,
            iterations=4,
            timing=TimingResult(cpu_seconds=0.01, wall_seconds=0.01),
            convergence=ConvergenceTrace(
                function_evaluations=(1, specification.budget.max_function_evaluations),
                best_values=(100.0, float(np.sum(best**2))),
            ),
        )


class FakeZOAdapter(ZOAdaMMAdapter):
    def run_from_initial_solution(self, specification, initial_solution):
        assert np.allclose(initial_solution, 0.25)
        best = np.asarray(initial_solution, dtype=float) * 0.5
        return RunResult(
            specification=specification,
            objective=ObjectiveResult(
                best_value=float(np.sum(best**2)),
                best_solution=tuple(best),
            ),
            function_evaluations=specification.budget.max_function_evaluations,
            iterations=2,
            timing=TimingResult(cpu_seconds=0.02, wall_seconds=0.02),
            convergence=ConvergenceTrace(
                function_evaluations=(1, specification.budget.max_function_evaluations),
                best_values=(1.0, float(np.sum(best**2))),
            ),
        )


def make_hybrid_specification(budget: int = 100):
    algorithm = cso_zoadamm_algorithm_specification()
    parameters = cso_zoadamm_validated_parameters("happycat", 10)
    configuration = AlgorithmConfiguration(algorithm, parameters)
    scenario = BenchmarkScenario("HappyCat", 10, "happycat", -100, 100)
    experiment = ExperimentSpecification(
        name="hybrid-test",
        algorithm=algorithm,
        scenarios=(scenario,),
        configurations=(configuration,),
        seeds=SeedPlan((27,)),
        budget=EvaluationBudget(budget),
    )
    return next(experiment.iter_run_specifications())


def test_hybrid_parameter_schema_is_complete():
    specification = cso_zoadamm_algorithm_specification()
    assert set(specification.parameter_schema.names) == set(CSO_ZOADAMM_PARAMETER_SCHEMA.names)
    assert dict(specification.fixed_parameters) == CSO_ZOADAMM_FIXED_PARAMETERS
    assert len(specification.fixed_parameters) == 1


def test_validated_profile_matches_source_values():
    assert len(CSO_ZOADAMM_VALIDATED_PROFILES) == 6
    happycat_10 = cso_zoadamm_validated_parameters("happycat", 10)
    assert happycat_10 == {
        "cso_population_size": 15,
        "cso_mixture_ratio": 0.1,
        "cso_c1": 1.05,
        "cso_smp": 2,
        "cso_spc": False,
        "cso_cdc": 1.0,
        "cso_srd": 0.4,
        "cso_max_velocity": 1.9,
        "zoadamm_learning_rate": 0.7,
        "zoadamm_beta1": 0.9,
        "zoadamm_beta2": 0.99999,
        "zoadamm_mu": 0.001,
        "zoadamm_q": 5,
        "zoadamm_epsilon": 1e-12,
        "zoadamm_decay_learning_rate": True,
        "cso_budget_fraction": 0.8,
    }


def test_hybrid_split_and_handoff():
    spec = make_hybrid_specification(100)
    result = CSOZOAdaMMAdapter(
        cso_adapter=FakeCSOAdapter(),
        zoadamm_adapter=FakeZOAdapter(),
    ).run(spec)

    assert result.function_evaluations == 100
    assert result.iterations == 6
    assert result.objective.best_value < 3 * 0.25**2 * (10 / 3)
    assert result.convergence.function_evaluations[-1] == 100
    assert all(
        right > left
        for left, right in zip(
            result.convergence.function_evaluations,
            result.convergence.function_evaluations[1:],
        )
    )


def test_hybrid_campaign_shape_and_scenario_specific_parameters():
    from optimization_experiments.experiments.cso_zoadamm import (
        CSO_ZOADAMM_BUDGET,
        create_cso_zoadamm_campaign_experiment,
    )

    experiment = create_cso_zoadamm_campaign_experiment()
    assert experiment.run_count == 18
    assert experiment.budget.max_function_evaluations == CSO_ZOADAMM_BUDGET
    assert experiment.seeds.seeds == (27, 32, 59)
    assert len(experiment.configurations) == 6
    assert len(experiment.scenario_configuration_ids) == 6

    expected_keys = {"happycat:10", "happycat:100", "rosenbrock:10", "rosenbrock:100", "schwefel:10", "schwefel:100"}
    observed = {
        f"{run.scenario.objective}:{run.scenario.dimension}": run.algorithm.parameters
        for run in experiment.iter_run_specifications()
    }
    assert set(observed) == expected_keys
    for key in expected_keys:
        objective, dimension = key.split(":")
        assert observed[key] == cso_zoadamm_validated_parameters(objective, int(dimension))

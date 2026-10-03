from optimization_experiments.algorithms.zoadamm import ZOAdaMMAdapter
from optimization_experiments.algorithms.zoadamm_spec import zoadamm_algorithm_specification
from optimization_experiments.core import (
    AlgorithmConfiguration,
    BenchmarkScenario,
    EvaluationBudget,
    ExperimentSpecification,
    SeedPlan,
)


def make_experiment(seed: int = 27, budget: int = 50):
    algorithm = zoadamm_algorithm_specification()
    configuration = AlgorithmConfiguration(algorithm, dict(algorithm.fixed_parameters))
    scenario = BenchmarkScenario("Sphere", 4, "sphere", -5, 5)
    return ExperimentSpecification(
        name="zoadamm-test",
        algorithm=algorithm,
        scenarios=(scenario,),
        configurations=(configuration,),
        seeds=SeedPlan((seed,)),
        budget=EvaluationBudget(budget),
    )


def test_zoadamm_budget_and_solution_contract():
    specification = next(make_experiment().iter_run_specifications())
    result = ZOAdaMMAdapter().run(specification)
    assert 0 < result.function_evaluations <= 50
    assert result.iterations >= 0
    assert len(result.objective.best_solution) == 4
    assert result.objective.best_value >= 0.0
    assert result.convergence.function_evaluations[-1] <= 50


def test_zoadamm_is_deterministic_for_same_seed():
    specification = next(make_experiment(seed=59, budget=40).iter_run_specifications())
    first = ZOAdaMMAdapter().run(specification)
    second = ZOAdaMMAdapter().run(specification)
    assert first.objective.best_value == second.objective.best_value
    assert first.objective.best_solution == second.objective.best_solution
    assert first.convergence == second.convergence

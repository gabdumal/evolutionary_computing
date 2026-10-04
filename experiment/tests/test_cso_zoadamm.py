import numpy as np

from optimization_experiments.algorithms.base import AlgorithmAdapter
from optimization_experiments.algorithms.cso_zoadamm import CSOZOAdaMMAdapter
from optimization_experiments.algorithms.cso_zoadamm_spec import (
    CSO_ZOADAMM_DEFAULT_PARAMETERS,
    cso_zoadamm_algorithm_specification,
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
    configuration = AlgorithmConfiguration(algorithm, dict(algorithm.fixed_parameters))
    scenario = BenchmarkScenario("Sphere", 3, "sphere", -5, 5)
    experiment = ExperimentSpecification(
        name="hybrid-test",
        algorithm=algorithm,
        scenarios=(scenario,),
        configurations=(configuration,),
        seeds=SeedPlan((27,)),
        budget=EvaluationBudget(budget),
    )
    return next(experiment.iter_run_specifications())


def test_hybrid_parameter_schema_matches_defaults():
    specification = cso_zoadamm_algorithm_specification()
    assert set(specification.parameter_schema.names) == set(CSO_ZOADAMM_DEFAULT_PARAMETERS)


def test_hybrid_split_and_handoff():
    spec = make_hybrid_specification(100)
    result = CSOZOAdaMMAdapter(
        cso_adapter=FakeCSOAdapter(),
        zoadamm_adapter=FakeZOAdapter(),
    ).run(spec)

    assert result.function_evaluations == 100
    assert result.iterations == 6
    assert result.objective.best_value < 3 * 0.25**2
    assert result.convergence.function_evaluations[-1] == 100
    assert all(
        right > left
        for left, right in zip(
            result.convergence.function_evaluations,
            result.convergence.function_evaluations[1:],
        )
    )


def test_hybrid_campaign_shape():
    from optimization_experiments.experiments.cso_zoadamm import (
        CSO_ZOADAMM_BUDGET,
        create_cso_zoadamm_campaign_experiment,
    )

    experiment = create_cso_zoadamm_campaign_experiment()
    assert experiment.run_count == 18
    assert experiment.budget.max_function_evaluations == CSO_ZOADAMM_BUDGET
    assert experiment.seeds.seeds == (27, 32, 59)
    assert experiment.configurations[0].parameters["cso_budget_fraction"] == 0.8

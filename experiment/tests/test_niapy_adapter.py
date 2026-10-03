
from __future__ import annotations

import numpy as np

from optimization_experiments.algorithms.niapy import NiaPyAlgorithmAdapter
from optimization_experiments.algorithms.cso import cso_algorithm_specification
from optimization_experiments.core import (
    AlgorithmConfiguration,
    BenchmarkScenario,
    EvaluationBudget,
    ExperimentSpecification,
    SeedPlan,
)
from optimization_experiments.core.models import ConvergenceTrace, RunSpecification


class FakeProblem:
    def __init__(self, *, dimension, lower, upper):
        self.dimension = dimension
        self.lower = lower
        self.upper = upper


class FakeOptimizationType:
    MINIMIZATION = "minimization"


class FakeTask:
    def __init__(self, *, problem, optimization_type, max_evals):
        self.problem = problem
        self.optimization_type = optimization_type
        self.max_evals = max_evals
        self.evals = 0
        self.iters = 0
        self.n_evals = []
        self.fitness_evals = []

    def evaluate(self, x):
        self.evals += 1
        value = float(np.sum(np.asarray(x, dtype=float) ** 2))
        self.n_evals.append(self.evals)
        self.fitness_evals.append(value)
        return value


class FakeCSO:
    def __init__(self, **parameters):
        self.parameters = parameters

    def run(self, task):
        x = np.zeros(task.problem.dimension, dtype=float)
        value = task.evaluate(x)
        task.iters = 1
        return x, value


def fake_load_niapy():
    return FakeCSO, FakeProblem, FakeTask, FakeOptimizationType


def test_niapy_adapter_contract(monkeypatch):
    import optimization_experiments.algorithms.niapy as module

    monkeypatch.setattr(module, "_load_niapy", fake_load_niapy)

    algorithm = cso_algorithm_specification()
    configuration = AlgorithmConfiguration(
        algorithm=algorithm,
        parameters=dict(algorithm.fixed_parameters),
    )
    scenario = BenchmarkScenario(
        problem="Sphere",
        dimension=4,
        objective="sphere",
        lower_bound=-5.0,
        upper_bound=5.0,
    )
    experiment = ExperimentSpecification(
        name="adapter-test",
        algorithm=algorithm,
        scenarios=(scenario,),
        configurations=(configuration,),
        seeds=SeedPlan((27,)),
        budget=EvaluationBudget(10),
    )
    specification = next(experiment.iter_run_specifications())

    result = NiaPyAlgorithmAdapter("CSO", FakeCSO).run(specification)

    assert result.function_evaluations == 1
    assert result.iterations == 1
    assert result.objective.best_value == 0.0
    assert result.objective.best_solution == (0.0, 0.0, 0.0, 0.0)
    assert result.convergence == ConvergenceTrace((1,), (0.0,))


def test_native_benchmark_class_detection(monkeypatch):
    import optimization_experiments.algorithms.niapy as module

    class FakeHappyCat(FakeProblem):
        pass

    class FakeRosenbrock(FakeProblem):
        pass

    class FakeSchwefel(FakeProblem):
        pass

    monkeypatch.setattr(
        module,
        "_load_native_problem_classes",
        lambda: {
            "happycat": FakeHappyCat,
            "rosenbrock": FakeRosenbrock,
            "schwefel": FakeSchwefel,
        },
    )

    scenarios = (
        BenchmarkScenario(
            problem="HappyCat",
            dimension=10,
            objective="HappyCat",
            lower_bound=-100.0,
            upper_bound=100.0,
        ),
        BenchmarkScenario(
            problem="Rosenbrock",
            dimension=10,
            objective="Rosenbrock",
            lower_bound=-30.0,
            upper_bound=30.0,
        ),
        BenchmarkScenario(
            problem="Schwefel",
            dimension=10,
            objective="Schwefel",
            lower_bound=-500.0,
            upper_bound=500.0,
        ),
    )

    classes = [module._native_problem_class(s) for s in scenarios]
    assert classes == [FakeHappyCat, FakeRosenbrock, FakeSchwefel]

    custom_bounds = BenchmarkScenario(
        problem="HappyCat",
        dimension=10,
        objective="happycat",
        lower_bound=-10.0,
        upper_bound=10.0,
    )
    assert module._native_problem_class(custom_bounds) is None


def test_create_task_passes_concrete_native_problem(monkeypatch):
    import optimization_experiments.algorithms.niapy as module

    class FakeHappyCat(FakeProblem):
        pass

    monkeypatch.setattr(
        module,
        "_load_native_problem_classes",
        lambda: {
            "happycat": FakeHappyCat,
            "rosenbrock": FakeProblem,
            "schwefel": FakeProblem,
        },
    )

    class CapturingTask:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    scenario = BenchmarkScenario(
        problem="HappyCat",
        dimension=10,
        objective="HappyCat",
        lower_bound=-100.0,
        upper_bound=100.0,
    )

    task = module._create_task(
        scenario,
        CapturingTask,
        FakeOptimizationType,
        FakeProblem,
        1000,
    )

    assert isinstance(task.kwargs["problem"], FakeHappyCat)
    assert task.kwargs["problem"].dimension == 10
    assert task.kwargs["problem"].lower == -100.0
    assert task.kwargs["problem"].upper == 100.0
    assert task.kwargs["max_evals"] == 1000

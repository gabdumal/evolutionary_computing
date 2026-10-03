
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

from __future__ import annotations

import time
from typing import Any

import numpy as np

from ..benchmarks import evaluate_objective
from ..core.models import (
    ConvergenceTrace,
    ObjectiveResult,
    RunResult,
    RunSpecification,
    TimingResult,
)
from .base import AlgorithmAdapter


def _load_niapy():
    try:
        from niapy.algorithms.basic import CatSwarmOptimization
        from niapy.problems import Problem
        from niapy.task import OptimizationType, Task
    except ImportError as exc:
        raise ImportError(
            "NiaPy >= 2.7.1 is required for the CSO adapter. "
            "Install the project dependencies first."
        ) from exc
    return CatSwarmOptimization, Problem, Task, OptimizationType


def _create_problem_class(Problem):
    class ScenarioProblem(Problem):
        def __init__(self, scenario):
            super().__init__(
                dimension=scenario.dimension,
                lower=scenario.lower_bound,
                upper=scenario.upper_bound,
            )
            self._scenario = scenario

        def _evaluate(self, x):
            return evaluate_objective(
                self._scenario.objective,
                np.asarray(x, dtype=np.float64),
                self._scenario.problem_parameters,
            )

    return ScenarioProblem


class NiaPyAlgorithmAdapter(AlgorithmAdapter):
    """Thin adapter around one NiaPy algorithm class."""

    def __init__(self, name: str, algorithm_factory):
        self.name = name
        self._algorithm_factory = algorithm_factory

    def run(self, specification: RunSpecification) -> RunResult:
        scenario = specification.scenario
        CatSwarmOptimization, Problem, Task, OptimizationType = _load_niapy()
        ProblemClass = _create_problem_class(Problem)

        parameters = dict(specification.algorithm.parameters)
        parameters["seed"] = specification.seed

        algorithm = self._algorithm_factory(**parameters)
        problem = ProblemClass(scenario)
        task = Task(
            problem=problem,
            optimization_type=OptimizationType.MINIMIZATION,
            max_evals=specification.budget.max_function_evaluations,
        )

        started = time.process_time()
        best_solution, best_fitness = algorithm.run(task)
        cpu_seconds = time.process_time() - started

        if best_solution is None or best_fitness is None:
            raise RuntimeError("NiaPy returned no best solution or best fitness.")

        function_evaluations = int(task.evals)
        iterations = int(task.iters)

        if function_evaluations <= 0:
            raise RuntimeError("NiaPy completed without objective evaluations.")

        convergence_evaluations, convergence_values = _extract_convergence(
            task,
            float(best_fitness),
        )

        best_value = float(getattr(task, "x_f", best_fitness))
        if not np.isfinite(best_value):
            best_value = float(best_fitness)

        solution = np.asarray(best_solution, dtype=np.float64).reshape(-1)
        if solution.size != scenario.dimension:
            raise RuntimeError(
                f"NiaPy returned solution dimension {solution.size}, "
                f"expected {scenario.dimension}."
            )

        return RunResult(
            specification=specification,
            objective=ObjectiveResult(
                best_value=best_value,
                best_solution=tuple(float(value) for value in solution),
            ),
            function_evaluations=function_evaluations,
            iterations=iterations,
            timing=TimingResult(cpu_seconds=cpu_seconds),
            convergence=ConvergenceTrace(
                function_evaluations=convergence_evaluations,
                best_values=convergence_values,
            ),
        )


def _extract_convergence(
    task: Any,
    fallback_best_value: float,
) -> tuple[tuple[int, ...], tuple[float, ...]]:
    convergence_data = getattr(task, "convergence_data", None)
    if callable(convergence_data):
        raw_evaluations, raw_values = convergence_data("evals")
    else:
        raw_evaluations = getattr(task, "n_evals", [])
        raw_values = getattr(task, "fitness_evals", [])

    evaluations = np.asarray(raw_evaluations, dtype=np.int64).reshape(-1)
    values = np.asarray(raw_values, dtype=np.float64).reshape(-1)

    if evaluations.size != values.size:
        raise RuntimeError("NiaPy returned inconsistent convergence data.")

    if evaluations.size == 0:
        completed = int(task.evals)
        return (completed,), (float(fallback_best_value),)

    best_values = np.minimum.accumulate(values)

    completed = int(task.evals)
    if evaluations[-1] < completed:
        evaluations = np.concatenate(
            (evaluations, np.asarray([completed], dtype=np.int64))
        )
        best_values = np.concatenate(
            (best_values, np.asarray([best_values[-1]], dtype=np.float64))
        )

    return (
        tuple(int(value) for value in evaluations),
        tuple(float(value) for value in best_values),
    )


def create_cso_adapter(parameters: dict[str, Any]) -> AlgorithmAdapter:
    CatSwarmOptimization, _, _, _ = _load_niapy()
    _ = parameters
    return NiaPyAlgorithmAdapter("CSO", CatSwarmOptimization)

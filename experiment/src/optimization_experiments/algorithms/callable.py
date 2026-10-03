from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import numpy as np

from ..core.models import (
    ConvergenceTrace,
    ObjectiveResult,
    RunResult,
    RunSpecification,
    TimingResult,
)
from .base import AlgorithmAdapter


Objective = Callable[[np.ndarray], float]
Optimizer = Callable[
    [Objective, int, int, dict[str, Any], float, float],
    tuple[np.ndarray, float, int, tuple[int, ...], tuple[float, ...]],
]


class CallableAlgorithmAdapter(AlgorithmAdapter):
    """Adapter for an optimizer function.

    The optimizer receives:
      objective, dimension, seed, parameters, lower_bound, upper_bound

    and returns:
      best_solution, best_value, iterations, convergence_evaluations, convergence_values
    """

    def __init__(self, name: str, optimizer: Optimizer):
        self.name = name
        self._optimizer = optimizer

    def run(self, specification: RunSpecification) -> RunResult:
        scenario = specification.scenario
        rng = np.random.default_rng(specification.seed)
        evaluation_count = 0

        def objective(x: np.ndarray) -> float:
            nonlocal evaluation_count
            if evaluation_count >= specification.budget.max_function_evaluations:
                raise RuntimeError("Function-evaluation budget exhausted.")
            evaluation_count += 1
            return float(scenario_objective(scenario, x))

        started = time.process_time()
        (
            best_solution,
            best_value,
            iterations,
            convergence_evaluations,
            convergence_values,
        ) = self._optimizer(
            objective,
            scenario.dimension,
            specification.seed,
            dict(specification.algorithm.parameters),
            scenario.lower_bound,
            scenario.upper_bound,
        )
        cpu_seconds = time.process_time() - started

        if evaluation_count == 0:
            raise RuntimeError("Optimizer performed no objective evaluations.")

        # Keep RNG construction explicit so adapters can standardize seed handling.
        _ = rng

        return RunResult(
            specification=specification,
            objective=ObjectiveResult(
                best_value=float(best_value),
                best_solution=tuple(float(v) for v in np.asarray(best_solution)),
            ),
            function_evaluations=evaluation_count,
            iterations=int(iterations),
            timing=TimingResult(cpu_seconds=cpu_seconds),
            convergence=ConvergenceTrace(
                function_evaluations=tuple(int(v) for v in convergence_evaluations),
                best_values=tuple(float(v) for v in convergence_values),
            ),
        )


def scenario_objective(scenario, x: np.ndarray) -> float:
    # The default API expects an importable objective registry to be installed.
    # Keeping this function small makes the benchmark layer replaceable.
    from ..benchmarks import evaluate_objective
    return evaluate_objective(scenario.objective, x, scenario.problem_parameters)

from __future__ import annotations

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


class FakeAlgorithmAdapter(AlgorithmAdapter):
    name = "fake"

    def run(self, specification: RunSpecification) -> RunResult:
        scenario = specification.scenario
        point = np.zeros(scenario.dimension, dtype=np.float64)
        value = evaluate_objective(scenario.objective, point, scenario.problem_parameters)
        evaluations = 1
        return RunResult(
            specification=specification,
            objective=ObjectiveResult(
                best_value=value,
                best_solution=tuple(float(v) for v in point),
            ),
            function_evaluations=evaluations,
            iterations=1,
            timing=TimingResult(cpu_seconds=0.0),
            convergence=ConvergenceTrace(
                function_evaluations=(1,),
                best_values=(float(value),),
            ),
        )


def create_fake_adapter(parameters: dict[str, Any]) -> AlgorithmAdapter:
    _ = parameters
    return FakeAlgorithmAdapter()

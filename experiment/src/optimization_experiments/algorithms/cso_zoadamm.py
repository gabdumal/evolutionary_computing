from __future__ import annotations

import time

import numpy as np

from ..core.models import (
    AlgorithmConfiguration,
    EvaluationBudget,
    ObjectiveResult,
    RunResult,
    RunSpecification,
    TimingResult,
    ConvergenceTrace,
)
from .base import AlgorithmAdapter
from .niapy import NiaPyAlgorithmAdapter, _load_niapy
from .zoadamm import ZOAdaMMAdapter
from .cso import cso_algorithm_specification
from .zoadamm_spec import zoadamm_algorithm_specification


class CSOZOAdaMMAdapter(AlgorithmAdapter):
    """Simple sequential hybrid: CSO exploration followed by ZO-AdaMM refinement."""

    name = "CSO-ZO-AdaMM"

    def __init__(
        self,
        *,
        cso_adapter: AlgorithmAdapter | None = None,
        zoadamm_adapter: ZOAdaMMAdapter | None = None,
    ) -> None:
        self._cso_adapter = cso_adapter or _make_cso_adapter()
        self._zoadamm_adapter = zoadamm_adapter or ZOAdaMMAdapter()

    def run(self, specification: RunSpecification) -> RunResult:
        parameters = dict(specification.algorithm.parameters)
        total_budget = specification.budget.max_function_evaluations
        if total_budget < 2:
            raise ValueError("CSO-ZO-AdaMM requires at least 2 function evaluations.")

        cso_fraction = float(parameters["cso_budget_fraction"])
        cso_budget = int(round(total_budget * cso_fraction))
        cso_budget = max(1, min(total_budget - 1, cso_budget))
        zoadamm_budget = total_budget - cso_budget

        cso_specification = _phase_specification(
            specification,
            algorithm=cso_algorithm_specification(),
            parameters=_cso_parameters(parameters),
            budget=cso_budget,
        )
        zoadamm_specification = _phase_specification(
            specification,
            algorithm=zoadamm_algorithm_specification(),
            parameters=_zoadamm_parameters(parameters),
            budget=zoadamm_budget,
        )

        started_wall = time.perf_counter()
        started_cpu = time.process_time()

        cso_result = self._cso_adapter.run(cso_specification)
        zoadamm_result = self._zoadamm_adapter.run_from_initial_solution(
            zoadamm_specification,
            np.asarray(cso_result.objective.best_solution, dtype=np.float64),
        )

        total_evaluations = (
            cso_result.function_evaluations + zoadamm_result.function_evaluations
        )
        if total_evaluations != total_budget:
            raise RuntimeError(
                "Hybrid did not consume the complete configured FE budget: "
                f"CSO={cso_result.function_evaluations}, "
                f"ZO-AdaMM={zoadamm_result.function_evaluations}, "
                f"total={total_evaluations}, expected={total_budget}."
            )

        best_value = min(
            cso_result.objective.best_value,
            zoadamm_result.objective.best_value,
        )
        best_solution = (
            cso_result.objective.best_solution
            if cso_result.objective.best_value <= zoadamm_result.objective.best_value
            else zoadamm_result.objective.best_solution
        )

        convergence = _merge_convergence(cso_result, zoadamm_result)
        cpu_seconds = time.process_time() - started_cpu
        wall_seconds = time.perf_counter() - started_wall

        return RunResult(
            specification=specification,
            objective=ObjectiveResult(
                best_value=float(best_value),
                best_solution=tuple(float(value) for value in best_solution),
            ),
            function_evaluations=total_evaluations,
            iterations=cso_result.iterations + zoadamm_result.iterations,
            timing=TimingResult(
                cpu_seconds=cpu_seconds,
                wall_seconds=wall_seconds,
            ),
            convergence=convergence,
        )


def _make_cso_adapter() -> AlgorithmAdapter:
    CatSwarmOptimization, _, _, _ = _load_niapy()
    return NiaPyAlgorithmAdapter("CSO", CatSwarmOptimization)


def _phase_specification(
    specification: RunSpecification,
    *,
    algorithm,
    parameters: dict[str, object],
    budget: int,
) -> RunSpecification:
    return RunSpecification(
        experiment_id=specification.experiment_id,
        experiment_name=specification.experiment_name,
        algorithm=AlgorithmConfiguration(algorithm=algorithm, parameters=parameters),
        scenario=specification.scenario,
        seed=specification.seed,
        budget=EvaluationBudget(budget),
    )


def _cso_parameters(parameters: dict[str, object]) -> dict[str, object]:
    return {
        "population_size": parameters["cso_population_size"],
        "mixture_ratio": parameters["cso_mixture_ratio"],
        "c1": parameters["cso_c1"],
        "smp": parameters["cso_smp"],
        "spc": parameters["cso_spc"],
        "cdc": parameters["cso_cdc"],
        "srd": parameters["cso_srd"],
        "max_velocity": parameters["cso_max_velocity"],
    }


def _zoadamm_parameters(parameters: dict[str, object]) -> dict[str, object]:
    return {
        "learning_rate": parameters["zoadamm_learning_rate"],
        "beta1": parameters["zoadamm_beta1"],
        "beta2": parameters["zoadamm_beta2"],
        "mu": parameters["zoadamm_mu"],
        "q": parameters["zoadamm_q"],
        "epsilon": parameters["zoadamm_epsilon"],
        "decay_learning_rate": parameters["zoadamm_decay_learning_rate"],
    }


def _merge_convergence(
    cso_result: RunResult,
    zoadamm_result: RunResult,
) -> ConvergenceTrace:
    offset = cso_result.function_evaluations
    first_evals = tuple(cso_result.convergence.function_evaluations)
    first_values = tuple(cso_result.convergence.best_values)
    second_evals = tuple(
        offset + value for value in zoadamm_result.convergence.function_evaluations
    )
    second_values = tuple(
        min(cso_result.objective.best_value, value)
        for value in zoadamm_result.convergence.best_values
    )
    return ConvergenceTrace(
        function_evaluations=first_evals + second_evals,
        best_values=first_values + second_values,
    )


def create_cso_zoadamm_adapter(parameters: dict[str, object]) -> AlgorithmAdapter:
    _ = parameters
    return CSOZOAdaMMAdapter()

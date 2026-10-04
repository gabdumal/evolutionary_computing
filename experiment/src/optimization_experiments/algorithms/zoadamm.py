from __future__ import annotations

import time

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


class ZOAdaMMAdapter(AlgorithmAdapter):
    """Reference-style NumPy implementation of ZO-AdaMM.

    The update follows Algorithm 1 of Chen et al. (NeurIPS 2019):
    - forward-difference zeroth-order gradient estimation;
    - exponential momentum m_t;
    - exponential second moment v_t;
    - AMSGrad-style v-hat = max(v-hat, v_t);
    - diagonal Mahalanobis adaptive step;
    - projection onto the benchmark box.

    For a diagonal positive metric and a box constraint, the Mahalanobis
    projection is coordinate-wise clipping, so no generic quadratic solver
    is needed.
    """

    name = "ZO-AdaMM"

    def run(self, specification: RunSpecification) -> RunResult:
        parameters = dict(specification.algorithm.parameters)
        scenario = specification.scenario
        budget = specification.budget.max_function_evaluations

        learning_rate = float(parameters["learning_rate"])
        beta1 = float(parameters["beta1"])
        beta2 = float(parameters["beta2"])
        mu = float(parameters["mu"])
        q = int(parameters["q"])
        epsilon = float(parameters["epsilon"])
        decay = bool(parameters["decay_learning_rate"])

        if learning_rate <= 0:
            raise ValueError("learning_rate must be positive.")
        if not 0.0 <= beta1 <= 1.0:
            raise ValueError("beta1 must be in [0, 1].")
        if not 0.0 <= beta2 <= 1.0:
            raise ValueError("beta2 must be in [0, 1].")
        if mu <= 0:
            raise ValueError("mu must be positive.")
        if q <= 0:
            raise ValueError("q must be positive.")
        if epsilon < 0:
            raise ValueError("epsilon cannot be negative.")

        rng = np.random.default_rng(specification.seed)
        dimension = scenario.dimension
        lower = float(scenario.lower_bound)
        upper = float(scenario.upper_bound)

        x = rng.uniform(lower, upper, size=dimension).astype(np.float64)
        m = np.zeros(dimension, dtype=np.float64)
        v = np.zeros(dimension, dtype=np.float64)
        v_hat = np.zeros(dimension, dtype=np.float64)

        evaluations = 0
        iterations = 0
        best_value = np.inf
        best_solution = x.copy()
        convergence_evaluations: list[int] = []
        convergence_values: list[float] = []

        wall_started = time.perf_counter()
        started = time.process_time()

        # The current-point value is reusable between iterations for deterministic
        # benchmark functions. This reduces each later q-direction iteration from
        # q+1 calls to q calls without changing the estimator.
        fx = evaluate_objective(
            scenario.objective,
            x,
            scenario.problem_parameters,
        )
        evaluations += 1
        best_value = float(fx)
        best_solution = x.copy()
        convergence_evaluations.append(evaluations)
        convergence_values.append(best_value)

        while evaluations < budget:
            remaining = budget - evaluations
            directions = min(q, remaining)

            # Uniform random directions on the unit sphere, as specified by the
            # paper. Rejection-free normalization avoids Gaussian directions
            # with an unbounded norm.
            u = rng.normal(size=(directions, dimension))
            norms = np.linalg.norm(u, axis=1)
            zero_norm = norms == 0.0
            while np.any(zero_norm):
                u[zero_norm] = rng.normal(size=(int(np.sum(zero_norm)), dimension))
                norms = np.linalg.norm(u, axis=1)
                zero_norm = norms == 0.0
            u /= norms[:, None]

            estimates: list[np.ndarray] = []
            for direction in u:
                if evaluations >= budget:
                    break

                probe = x + mu * direction
                probe = np.clip(probe, lower, upper)
                f_probe = evaluate_objective(
                    scenario.objective,
                    probe,
                    scenario.problem_parameters,
                )
                evaluations += 1

                # Equation (1) in the paper:
                # g_hat = (d / mu) [f(x + mu u) - f(x)] u.
                estimates.append(
                    (dimension / mu) * (f_probe - fx) * direction
                )

            if not estimates:
                break

            g_hat = np.mean(np.stack(estimates, axis=0), axis=0)

            iterations += 1
            m = beta1 * m + (1.0 - beta1) * g_hat
            v = beta2 * v + (1.0 - beta2) * (g_hat * g_hat)
            v_hat = np.maximum(v_hat, v)

            alpha_t = learning_rate / np.sqrt(iterations) if decay else learning_rate

            # Mahalanobis projection for diagonal V_hat reduces to clipping for
            # a Cartesian box. epsilon only stabilizes numerical division.
            denominator = np.sqrt(v_hat) + epsilon
            x = np.clip(
                x - alpha_t * m / denominator,
                lower,
                upper,
            )

            # Evaluate x for convergence tracking and for reuse in the next
            # iteration only if budget remains. If the budget was exhausted by
            # the probe evaluations, the final point is not queried.
            if evaluations < budget:
                fx = evaluate_objective(
                    scenario.objective,
                    x,
                    scenario.problem_parameters,
                )
                evaluations += 1

                if fx < best_value:
                    best_value = float(fx)
                    best_solution = x.copy()

                convergence_evaluations.append(evaluations)
                convergence_values.append(best_value)
            else:
                break

        cpu_seconds = time.process_time() - started
        wall_seconds = time.perf_counter() - wall_started

        if not np.isfinite(best_value):
            raise RuntimeError("ZO-AdaMM completed without a finite objective value.")

        return RunResult(
            specification=specification,
            objective=ObjectiveResult(
                best_value=float(best_value),
                best_solution=tuple(float(value) for value in best_solution),
            ),
            function_evaluations=evaluations,
            iterations=iterations,
            timing=TimingResult(
                cpu_seconds=cpu_seconds,
                wall_seconds=wall_seconds,
            ),
            convergence=ConvergenceTrace(
                function_evaluations=tuple(convergence_evaluations),
                best_values=tuple(convergence_values),
            ),
        )


def create_zoadamm_adapter(parameters: dict[str, object]) -> AlgorithmAdapter:
    # The algorithm configuration has already been validated by the API.
    _ = parameters
    return ZOAdaMMAdapter()

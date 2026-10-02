# pyright: reportMissingTypeStubs=false
from __future__ import annotations

"""Parallel, resumable execution of optimization experiments.

This module connects the experiment specifications to NiaPy and the
artifact store. It deliberately contains no statistical analysis.

Execution model
---------------
Each concrete ``ExperimentRunSpecification`` is an independent process
task. The parent process owns artifact persistence, while workers only
execute NiaPy and return ``ExperimentRunResult`` objects.

This design provides three useful properties:

- independent random seeds for every run;
- incremental persistence as soon as a worker finishes;
- safe resumption based on the artifact store's completed-run marker.
"""

import importlib
import multiprocessing
import os
import time
import traceback
from collections.abc import Iterator
from concurrent.futures import (
    FIRST_COMPLETED,
    Future,
    ProcessPoolExecutor,
    wait,
)
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TypeAlias

import numpy as np
import numpy.typing as npt

from experiment_artifacts import (
    ExperimentArtifactStore,
    ExperimentRunResult,
)
from experiment_specifications import (
    ExperimentRunSpecification,
    ExperimentSpecification,
)

DEFAULT_MAX_WORKERS: Final[int] = 6

FloatArray: TypeAlias = npt.NDArray[np.float64]
IntArray: TypeAlias = npt.NDArray[np.int64]

WorkerFuture: TypeAlias = Future[ExperimentRunResult]


@dataclass(frozen=True, slots=True)
class ExperimentExecutionReport:
    """Summary of one executor invocation."""

    experiment_id: str
    expected_run_count: int
    already_completed_count: int
    submitted_run_count: int
    completed_run_count: int
    failed_run_count: int
    elapsed_seconds: float
    failed_run_ids: tuple[str, ...]


class ExperimentRunExecutionError(RuntimeError):
    """Raised when NiaPy reports an exception from inside an algorithm."""


def _import_object(import_path: str) -> Any:
    """Resolve a top-level or nested Python object from an import path."""
    parts = import_path.split(".")

    for module_length in range(len(parts), 0, -1):
        module_name = ".".join(parts[:module_length])

        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exception:
            if exception.name != module_name:
                raise
            continue

        value: Any = module

        for attribute_name in parts[module_length:]:
            try:
                value = getattr(value, attribute_name)
            except AttributeError as exception:
                raise ImportError(
                    f"Cannot resolve {import_path!r}: {attribute_name!r} was not found."
                ) from exception

        return value

    raise ImportError(f"Cannot import any module prefix of {import_path!r}.")


def _load_niapy() -> tuple[Any, Any]:
    """Load the NiaPy Task and OptimizationType classes at the worker edge."""
    try:
        from niapy.task import OptimizationType, Task
    except ImportError as exception:
        raise ImportError(
            "NiaPy is required to execute experiments. "
            "Install it with `python -m pip install --upgrade niapy`."
        ) from exception

    return Task, OptimizationType


def _create_algorithm(run: ExperimentRunSpecification) -> Any:
    """Construct one fresh NiaPy algorithm for one concrete run."""
    algorithm_factory = _import_object(run.configuration.algorithm.import_path)

    parameters = dict(run.configuration.parameters)
    parameters["seed"] = run.seed

    try:
        return algorithm_factory(**parameters)
    except TypeError as exception:
        raise TypeError(
            "Could not construct the NiaPy algorithm "
            f"{run.configuration.algorithm.import_path!r} with "
            f"parameters {parameters!r}."
        ) from exception


def _create_problem(
    run: ExperimentRunSpecification,
) -> tuple[Any, int | None]:
    """Resolve a NiaPy problem name or construct a custom problem object."""
    specification = run.problem

    if specification.import_path is None:
        return specification.name, run.dimension

    problem_factory = _import_object(specification.import_path)
    parameters = dict(specification.parameters)
    parameters["dimension"] = run.dimension

    try:
        problem = problem_factory(**parameters)
    except TypeError as exception:
        raise TypeError(
            "Could not construct the problem "
            f"{specification.import_path!r} for dimension "
            f"{run.dimension} with parameters {parameters!r}."
        ) from exception

    return problem, None


def _create_task(
    run: ExperimentRunSpecification,
) -> Any:
    """Build the NiaPy Task for a concrete run."""
    Task, OptimizationType = _load_niapy()

    optimization_type = (
        OptimizationType.MINIMIZATION
        if run.problem.optimization == "minimize"
        else OptimizationType.MAXIMIZATION
    )

    problem, dimension = _create_problem(run)

    termination = run.termination

    max_evals: int | float = (
        termination.max_evaluations
        if termination.max_evaluations is not None
        else np.inf
    )
    max_iters: int | float = (
        termination.max_iterations if termination.max_iterations is not None else np.inf
    )

    return Task(
        problem=problem,
        dimension=dimension,
        optimization_type=optimization_type,
        max_evals=max_evals,
        max_iters=max_iters,
        cutoff_value=termination.cutoff_value,
        enable_logging=termination.enable_logging,
    )


def _solution_to_tuple(
    solution: object,
    dimension: int,
) -> tuple[float, ...]:
    """Normalize the solution returned by an untyped NiaPy boundary."""
    candidate: Any = solution

    if hasattr(solution, "x"):
        candidate = getattr(solution, "x", solution)

    array = np.asarray(candidate, dtype=np.float64).reshape(-1)

    if array.size != dimension:
        raise ValueError(
            f"NiaPy returned a solution with {array.size} coordinates; "
            f"expected {dimension}."
        )

    if not np.all(np.isfinite(array)):
        raise ValueError("NiaPy returned a solution containing non-finite values.")

    return tuple(float(value) for value in array)


def _convergence_arrays(
    task: Any,
    final_value: float,
) -> tuple[IntArray, FloatArray]:
    """Extract best-so-far improvement events from the NiaPy Task."""
    evaluations = np.asarray(
        getattr(task, "n_evals", []),
        dtype=np.int64,
    )
    internal_values = np.asarray(
        getattr(task, "fitness_evals", []),
        dtype=np.float64,
    )

    if evaluations.ndim != 1:
        evaluations = evaluations.reshape(-1)

    if internal_values.ndim != 1:
        internal_values = internal_values.reshape(-1)

    if evaluations.size != internal_values.size:
        raise RuntimeError(
            "NiaPy returned inconsistent convergence metadata: "
            f"{evaluations.size} evaluation points vs "
            f"{internal_values.size} values."
        )

    optimization_type = getattr(task, "optimization_type", None)
    direction_value = float(getattr(optimization_type, "value", 1.0))

    values = np.asarray(
        internal_values * direction_value,
        dtype=np.float64,
    )

    # NiaPy records best-value improvements. In a normal run this is
    # non-empty because population initialization evaluates candidates.
    # The fallback makes the executor robust to custom algorithms/tasks.
    if evaluations.size == 0:
        evaluations = np.asarray(
            [int(task.evals)],
            dtype=np.int64,
        )
        values = np.asarray(
            [final_value],
            dtype=np.float64,
        )
    elif not np.isclose(
        float(values[-1]),
        final_value,
        rtol=0.0,
        atol=0.0,
    ):
        evaluations = np.concatenate(
            (
                evaluations,
                np.asarray([int(task.evals)], dtype=np.int64),
            )
        )
        values = np.concatenate(
            (
                values,
                np.asarray([final_value], dtype=np.float64),
            )
        )

    return evaluations, values


def execute_single_run(
    run: ExperimentRunSpecification,
) -> ExperimentRunResult:
    """Execute one concrete run in a worker process."""
    started_at = time.perf_counter()

    algorithm = _create_algorithm(run)
    task = _create_task(run)

    final_solution, final_fitness = algorithm.run(task)

    if algorithm.bad_run():
        exception = getattr(algorithm, "exception", None)

        if exception is None:
            raise ExperimentRunExecutionError(
                "NiaPy reported a failed run without an exception object."
            )

        raise ExperimentRunExecutionError(
            f"NiaPy failed with {type(exception).__name__}: {exception}"
        ) from exception

    if final_solution is None or final_fitness is None:
        raise ExperimentRunExecutionError(
            "NiaPy returned no final solution or fitness."
        )

    if not isinstance(final_fitness, (int, float)):
        raise ExperimentRunExecutionError("NiaPy returned a non-numeric final fitness.")

    final_value = float(final_fitness)

    solution = _solution_to_tuple(
        final_solution,
        run.dimension,
    )

    evaluations = int(task.evals)
    iterations = int(task.iters)

    if evaluations <= 0:
        raise ExperimentRunExecutionError(
            "NiaPy completed without performing a function evaluation."
        )

    convergence_evaluations, convergence_values = _convergence_arrays(
        task,
        final_value,
    )

    return ExperimentRunResult(
        run_specification=run,
        best_value=final_value,
        best_solution=solution,
        function_evaluations=evaluations,
        iterations=iterations,
        elapsed_seconds=time.perf_counter() - started_at,
        convergence_evaluations=convergence_evaluations,
        convergence_values=convergence_values,
    )


def _submit_available_runs(
    executor: ProcessPoolExecutor,
    pending_runs: Iterator[ExperimentRunSpecification],
    futures: dict[WorkerFuture, ExperimentRunSpecification],
    max_pending: int,
) -> int:
    """Submit pending runs until the worker queue reaches its bound."""
    submitted = 0

    while len(futures) < max_pending:
        try:
            run = next(pending_runs)
        except StopIteration:
            break

        future = executor.submit(
            execute_single_run,
            run,
        )

        futures[future] = run
        submitted += 1

    return submitted


def execute_experiment(
    experiment: ExperimentSpecification,
    artifact_root: str | Path = "artifacts",
    *,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> ExperimentExecutionReport:
    """Execute all pending runs with incremental artifact persistence.

    Existing completed runs are skipped. At most ``max_workers`` runs are
    simultaneously in flight. Every successful run is persisted before
    another pending run is submitted, so a long campaign can be interrupted
    without losing already-completed results.

    The parent process performs all filesystem writes. Worker processes
    never share an open artifact store and never write into the same file.
    """
    if not isinstance(max_workers, int) or isinstance(max_workers, bool):
        raise TypeError("max_workers must be an integer.")

    if max_workers <= 0:
        raise ValueError("max_workers must be greater than zero.")

    available_cpus = os.cpu_count() or 1
    worker_count = min(max_workers, available_cpus)

    store = ExperimentArtifactStore(
        artifact_root,
        experiment,
    )
    store.initialize()

    already_completed_count = store.completed_run_count()
    pending_runs = iter(store.iter_pending_run_specifications())

    futures: dict[WorkerFuture, ExperimentRunSpecification] = {}
    submitted_run_count = 0
    completed_run_count = 0
    failed_run_ids: list[str] = []

    started_at = time.perf_counter()

    executor = ProcessPoolExecutor(
        max_workers=worker_count,
        mp_context=multiprocessing.get_context(),
    )

    try:
        submitted_run_count += _submit_available_runs(
            executor,
            pending_runs,
            futures,
            worker_count,
        )

        while futures:
            done, _ = wait(
                futures,
                return_when=FIRST_COMPLETED,
            )

            for future in done:
                run = futures.pop(future)

                try:
                    result = future.result()
                except Exception as exception:  # noqa: BLE001
                    failed_run_ids.append(run.run_id)

                    store.save_run_failure(
                        run,
                        exception_type=type(exception).__name__,
                        message=str(exception),
                        traceback="".join(
                            traceback.format_exception(
                                type(exception),
                                exception,
                                exception.__traceback__,
                            )
                        ),
                    )
                else:
                    store.save_run_result(result)
                    completed_run_count += 1

                submitted_run_count += _submit_available_runs(
                    executor,
                    pending_runs,
                    futures,
                    worker_count,
                )
    except KeyboardInterrupt:
        for future in futures:
            future.cancel()

        executor.shutdown(
            wait=False,
            cancel_futures=True,
        )
        raise
    except BaseException:
        for future in futures:
            future.cancel()

        executor.shutdown(
            wait=False,
            cancel_futures=True,
        )
        raise
    else:
        executor.shutdown(
            wait=True,
            cancel_futures=False,
        )

    elapsed_seconds = time.perf_counter() - started_at

    return ExperimentExecutionReport(
        experiment_id=experiment.experiment_id,
        expected_run_count=experiment.run_count,
        already_completed_count=already_completed_count,
        submitted_run_count=submitted_run_count,
        completed_run_count=completed_run_count,
        failed_run_count=len(failed_run_ids),
        elapsed_seconds=elapsed_seconds,
        failed_run_ids=tuple(failed_run_ids),
    )


__all__ = [
    "DEFAULT_MAX_WORKERS",
    "ExperimentExecutionReport",
    "ExperimentRunExecutionError",
    "execute_experiment",
    "execute_single_run",
]

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
from typing import Any, Final, Protocol, TypeAlias, cast

import numpy as np
import numpy.typing as npt

from experiment_artifacts import (
    ExperimentArtifactStore,
    ExperimentRunResult,
)
from experiment_specifications import (
    ExperimentRunSpecification,
    ExperimentSpecification,
    OptimizationDirection,
)

DEFAULT_MAX_WORKERS: Final[int] = 6
DEFAULT_PROGRESS_INTERVAL_SECONDS: Final[float] = 15.0

FloatArray: TypeAlias = npt.NDArray[np.float64]
IntArray: TypeAlias = npt.NDArray[np.int64]

WorkerFuture: TypeAlias = Future[ExperimentRunResult]


class _ConvergenceDataCallable(Protocol):
    def __call__(self, mode: str) -> tuple[object, object]: ...


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
    optimization: OptimizationDirection,
    fallback_best_value: float,
) -> tuple[IntArray, FloatArray]:
    """Extract a validated best-so-far trajectory from NiaPy."""
    convergence_data = getattr(task, "convergence_data", None)

    if callable(convergence_data):
        typed_convergence_data = cast(
            _ConvergenceDataCallable,
            convergence_data,
        )
        raw_evaluations, raw_internal_values = typed_convergence_data("evals")
    else:
        raw_evaluations = getattr(task, "n_evals", [])
        raw_internal_values = getattr(task, "fitness_evals", [])

    evaluations = np.asarray(
        raw_evaluations,
        dtype=np.int64,
    ).reshape(-1)
    internal_values = np.asarray(
        raw_internal_values,
        dtype=np.float64,
    ).reshape(-1)

    if evaluations.size != internal_values.size:
        raise RuntimeError(
            "NiaPy returned inconsistent convergence data: "
            f"{evaluations.size} evaluation points vs "
            f"{internal_values.size} values."
        )

    completed_evaluations = int(task.evals)

    if evaluations.size == 0:
        return (
            np.asarray([completed_evaluations], dtype=np.int64),
            np.asarray([fallback_best_value], dtype=np.float64),
        )

    if evaluations[0] < 1:
        raise RuntimeError("NiaPy returned a convergence evaluation below one.")

    if np.any(np.diff(evaluations) <= 0):
        raise RuntimeError("NiaPy returned non-increasing convergence evaluations.")

    if evaluations[-1] > completed_evaluations:
        raise RuntimeError(
            "NiaPy returned a convergence evaluation beyond the "
            "completed evaluation count."
        )

    if not np.all(np.isfinite(internal_values)):
        raise RuntimeError("NiaPy returned non-finite convergence fitness values.")

    # NiaPy's internal fitness representation is always minimized.
    best_internal_values = np.minimum.accumulate(internal_values)

    direction_value = 1.0 if optimization == "minimize" else -1.0
    objective_values = np.asarray(
        best_internal_values * direction_value,
        dtype=np.float64,
    )

    if evaluations[-1] < completed_evaluations:
        evaluations = np.concatenate(
            (
                evaluations,
                np.asarray([completed_evaluations], dtype=np.int64),
            )
        )
        objective_values = np.concatenate(
            (
                objective_values,
                np.asarray([float(objective_values[-1])], dtype=np.float64),
            )
        )

    return evaluations, objective_values


def execute_single_run(
    run: ExperimentRunSpecification,
) -> ExperimentRunResult:
    """Execute one concrete run in a worker process."""
    started_at = time.perf_counter()

    algorithm = _create_algorithm(run)
    task = _create_task(run)

    final_solution: object
    final_fitness: object

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

    if (
        not isinstance(final_fitness, (int, float))
        or isinstance(final_fitness, bool)
        or not np.isfinite(float(final_fitness))
    ):
        raise ExperimentRunExecutionError(
            "NiaPy returned a non-finite or non-numeric final fitness."
        )

    algorithm_returned_value = float(final_fitness)

    solution = _solution_to_tuple(
        final_solution,
        run.dimension,
    )

    function_evaluations = int(task.evals)
    iterations = int(task.iters)

    if function_evaluations <= 0:
        raise ExperimentRunExecutionError(
            "NiaPy completed without performing a function evaluation."
        )

    direction_value = 1.0 if run.problem.optimization == "minimize" else -1.0

    raw_task_best = getattr(task, "x_f", None)
    if (
        isinstance(raw_task_best, (int, float))
        and not isinstance(raw_task_best, bool)
        and np.isfinite(float(raw_task_best))
    ):
        best_value = float(raw_task_best) * direction_value
    else:
        best_value = algorithm_returned_value

    convergence_evaluations, convergence_values = _convergence_arrays(
        task,
        run.problem.optimization,
        best_value,
    )

    final_convergence_value = float(convergence_values[-1])

    if not np.isclose(
        final_convergence_value,
        best_value,
        rtol=1e-12,
        atol=1e-12,
    ):
        raise ExperimentRunExecutionError(
            "The persisted convergence trajectory is inconsistent with "
            "the final best objective value."
        )

    return ExperimentRunResult(
        run_specification=run,
        best_value=best_value,
        best_solution=solution,
        function_evaluations=function_evaluations,
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


def _print_execution_progress(
    *,
    total_run_count: int,
    already_completed_count: int,
    completed_run_count: int,
    failed_run_count: int,
    active_run_count: int,
    elapsed_seconds: float,
) -> None:
    """Print one concise progress update from the parent process."""
    processed_run_count = (
        already_completed_count + completed_run_count + failed_run_count
    )
    percentage = 100.0 * processed_run_count / total_run_count

    print(
        f"Progress: {processed_run_count:,}/{total_run_count:,} "
        f"({percentage:.1f}%) | completed={completed_run_count:,} "
        f"| failed={failed_run_count:,} | active={active_run_count:,} "
        f"| elapsed={elapsed_seconds:.1f}s",
        flush=True,
    )


def execute_experiment(
    experiment: ExperimentSpecification,
    artifact_root: str | Path = "artifacts",
    *,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_interval_seconds: float = DEFAULT_PROGRESS_INTERVAL_SECONDS,
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

    if (
        isinstance(progress_interval_seconds, bool)
        or not isinstance(progress_interval_seconds, (int, float))
        or not np.isfinite(float(progress_interval_seconds))
        or progress_interval_seconds <= 0.0
    ):
        raise ValueError("progress_interval_seconds must be a finite positive number.")

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
    last_progress_at = started_at

    print(
        f"Starting experiment {experiment.name!r}: "
        f"{experiment.run_count:,} expected runs, "
        f"{already_completed_count:,} already completed, "
        f"{worker_count} workers.",
        flush=True,
    )

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

        _print_execution_progress(
            total_run_count=experiment.run_count,
            already_completed_count=already_completed_count,
            completed_run_count=completed_run_count,
            failed_run_count=len(failed_run_ids),
            active_run_count=len(futures),
            elapsed_seconds=time.perf_counter() - started_at,
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

                now = time.perf_counter()
                if now - last_progress_at >= progress_interval_seconds:
                    _print_execution_progress(
                        total_run_count=experiment.run_count,
                        already_completed_count=already_completed_count,
                        completed_run_count=completed_run_count,
                        failed_run_count=len(failed_run_ids),
                        active_run_count=len(futures),
                        elapsed_seconds=now - started_at,
                    )
                    last_progress_at = now
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

    _print_execution_progress(
        total_run_count=experiment.run_count,
        already_completed_count=already_completed_count,
        completed_run_count=completed_run_count,
        failed_run_count=len(failed_run_ids),
        active_run_count=0,
        elapsed_seconds=elapsed_seconds,
    )

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
    "DEFAULT_PROGRESS_INTERVAL_SECONDS",
    "ExperimentExecutionReport",
    "ExperimentRunExecutionError",
    "execute_experiment",
    "execute_single_run",
]

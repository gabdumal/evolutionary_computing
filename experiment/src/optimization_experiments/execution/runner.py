from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass
import multiprocessing as mp
import os
from time import perf_counter

from ..algorithms import AlgorithmRegistry, default_registry
from ..artifacts import ArtifactStore
from ..core.ids import experiment_id, run_id
from ..core.models import ExperimentSpecification, RunSpecification


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    experiment_id: str
    expected_run_count: int
    completed_run_count: int
    skipped_completed_count: int
    failed_run_count: int
    cpu_seconds: float
    wall_seconds: float
    algorithm_wall_seconds: float = 0.0
    persistence_seconds: float = 0.0

    @property
    def processed_run_count(self) -> int:
        return self.completed_run_count + self.failed_run_count

    @property
    def runs_per_second(self) -> float:
        return (
            self.processed_run_count / self.wall_seconds
            if self.wall_seconds > 0
            else 0.0
        )

    @property
    def average_algorithm_wall_seconds(self) -> float:
        return (
            self.algorithm_wall_seconds / self.completed_run_count
            if self.completed_run_count
            else 0.0
        )

    @property
    def average_persistence_seconds(self) -> float:
        return (
            self.persistence_seconds / self.completed_run_count
            if self.completed_run_count
            else 0.0
        )


@dataclass(frozen=True, slots=True)
class WorkerExecution:
    run_identifier: str
    completed: bool
    cpu_seconds: float = 0.0
    algorithm_wall_seconds: float = 0.0
    persistence_seconds: float = 0.0
    function_evaluations: int = 0
    iterations: int = 0
    best_value: float | None = None
    error_type: str | None = None
    error_message: str | None = None


_WORKER_ARTIFACT_STORE: ArtifactStore | None = None


def _initialize_worker(
    artifact_root: str,
    experiment_identifier: str,
    durable: bool,
    compress_convergence: bool,
) -> None:
    global _WORKER_ARTIFACT_STORE
    _WORKER_ARTIFACT_STORE = ArtifactStore.for_worker(
        artifact_root,
        experiment_identifier,
        durable=durable,
        compress_convergence=compress_convergence,
    )


def _worker(
    run_specification: RunSpecification,
    registry: AlgorithmRegistry,
) -> WorkerExecution:
    store = _WORKER_ARTIFACT_STORE
    if store is None:
        raise RuntimeError("Worker artifact store was not initialized.")

    identifier = run_id(run_specification)
    try:
        adapter = registry.create(
            run_specification.algorithm.algorithm.implementation,
            dict(run_specification.algorithm.parameters),
        )
        result = adapter.run(run_specification)
    except Exception as error:
        try:
            persistence_started = perf_counter()
            store.save_failure(run_specification, error)
            persistence_seconds = perf_counter() - persistence_started
        except Exception:
            # Let the original execution failure propagate if the failure
            # marker itself cannot be persisted.
            raise
        return WorkerExecution(
            run_identifier=identifier,
            completed=False,
            persistence_seconds=persistence_seconds,
            error_type=type(error).__name__,
            error_message=str(error),
        )

    persistence_started = perf_counter()
    store.save_run(result)
    persistence_seconds = perf_counter() - persistence_started

    return WorkerExecution(
        run_identifier=identifier,
        completed=True,
        cpu_seconds=result.timing.cpu_seconds,
        algorithm_wall_seconds=result.timing.wall_seconds or 0.0,
        persistence_seconds=persistence_seconds,
        function_evaluations=result.function_evaluations,
        iterations=result.iterations,
        best_value=result.objective.best_value,
    )

def _format_duration(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 60.0:
        return f"{seconds:.2f}s"
    whole = int(seconds)
    days, remainder = divmod(whole, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_rate(rate: float) -> str:
    if rate <= 0:
        return "n/a"
    if rate >= 100:
        return f"{rate:,.0f}"
    if rate >= 10:
        return f"{rate:,.1f}"
    return f"{rate:,.2f}"


class ExperimentRunner:
    """Parallel, resumable runner with bounded scheduling and low-overhead logs."""

    def __init__(
        self,
        artifact_store: ArtifactStore,
        registry: AlgorithmRegistry | None = None,
        *,
        max_workers: int | None = None,
        start_method: str = "forkserver",
        progress_interval_seconds: float = 10.0,
        progress_interval_fraction: float = 0.01,
    ) -> None:
        if progress_interval_seconds <= 0:
            raise ValueError("progress_interval_seconds must be positive.")
        if not 0 < progress_interval_fraction <= 1:
            raise ValueError("progress_interval_fraction must be in (0, 1].")

        self.artifact_store = artifact_store
        self.registry = registry or default_registry()
        self.max_workers = max_workers or os.cpu_count() or 1
        self.start_method = start_method
        self.progress_interval_seconds = progress_interval_seconds
        self.progress_interval_fraction = progress_interval_fraction

    def run(self, experiment: ExperimentSpecification) -> ExecutionReport:
        if experiment_id(experiment) != self.artifact_store.experiment_identifier:
            raise ValueError("Runner experiment does not match the artifact store.")

        self.artifact_store.initialize()

        completed_ids = set(self.artifact_store.completed_run_ids())
        total_runs = experiment.run_count
        skipped = len(completed_ids)
        pending: Iterator[RunSpecification] = (
            specification
            for specification in experiment.iter_run_specifications()
            if run_id(specification) not in completed_ids
        )
        pending_count = total_runs - skipped

        worker_count = min(self.max_workers, os.cpu_count() or 1)
        print(
            f"Starting {experiment.name!r}: {total_runs:,} runs | "
            f"{skipped:,} already complete | {pending_count:,} pending | "
            f"{worker_count:,} workers",
            flush=True,
        )

        if pending_count == 0:
            return ExecutionReport(
                experiment_id=experiment_id(experiment),
                expected_run_count=total_runs,
                completed_run_count=0,
                skipped_completed_count=skipped,
                failed_run_count=0,
                cpu_seconds=0.0,
                wall_seconds=0.0,
            )

        completed = 0
        failed = 0
        cpu_seconds = 0.0
        algorithm_wall_seconds = 0.0
        persistence_seconds = 0.0
        wall_started = perf_counter()
        last_progress_time = wall_started
        progress_step = max(1, int(pending_count * self.progress_interval_fraction))
        next_progress_at = progress_step
        context = mp.get_context(self.start_method)
        in_flight: dict[Future[WorkerExecution], RunSpecification] = {}

        def submit_next(executor: ProcessPoolExecutor) -> bool:
            try:
                specification = next(pending)
            except StopIteration:
                return False
            future = executor.submit(_worker, specification, self.registry)
            in_flight[future] = specification
            return True

        with ProcessPoolExecutor(
            max_workers=worker_count,
            mp_context=context,
            initializer=_initialize_worker,
            initargs=(
                str(self.artifact_store.root),
                self.artifact_store.experiment_identifier,
                self.artifact_store.durable,
                self.artifact_store.compress_convergence,
            ),
        ) as executor:
            for _ in range(worker_count):
                if not submit_next(executor):
                    break

            last_result: WorkerExecution | None = None

            while in_flight:
                done, _ = wait(in_flight, return_when=FIRST_COMPLETED)

                for future in done:
                    specification = in_flight.pop(future)
                    try:
                        outcome = future.result()
                    except Exception as error:
                        # This means the worker itself failed before it could
                        # persist a normal run/failure artifact. Preserve the
                        # parent-side fallback marker.
                        failed += 1
                        self.artifact_store.save_failure(specification, error)
                        print(
                            f"[failed] {run_id(specification)}: "
                            f"{type(error).__name__}: {error}",
                            flush=True,
                        )
                    else:
                        persistence_seconds += outcome.persistence_seconds
                        if outcome.completed:
                            completed += 1
                            cpu_seconds += outcome.cpu_seconds
                            algorithm_wall_seconds += outcome.algorithm_wall_seconds
                            last_result = outcome
                        else:
                            failed += 1
                            print(
                                f"[failed] {outcome.run_identifier}: "
                                f"{outcome.error_type}: {outcome.error_message}",
                                flush=True,
                            )

                    processed = completed + failed
                    now = perf_counter()
                    should_report = (
                        processed >= next_progress_at
                        or now - last_progress_time >= self.progress_interval_seconds
                        or processed == pending_count
                    )

                    if should_report:
                        elapsed = now - wall_started
                        rate = processed / elapsed if elapsed > 0 else 0.0
                        remaining = max(0, pending_count - processed)
                        eta = remaining / rate if rate > 0 else 0.0
                        total_processed = skipped + processed
                        percentage = total_processed / total_runs * 100.0
                        active = len(in_flight)

                        last_run_text = "last_run=n/a"
                        if last_result is not None:
                            last_run_text = (
                                f"last_run={last_result.run_identifier} | "
                                f"run_wall={_format_duration(last_result.algorithm_wall_seconds)} | "
                                f"run_cpu={_format_duration(last_result.cpu_seconds)} | "
                                f"FE={last_result.function_evaluations:,}"
                            )

                        persist_avg = (
                            persistence_seconds / completed * 1000.0
                            if completed
                            else 0.0
                        )
                        print(
                            f"[progress] {total_processed:,}/{total_runs:,} "
                            f"({percentage:5.1f}%) | session={processed:,} | "
                            f"active={active} | elapsed={_format_duration(elapsed)} | "
                            f"rate={_format_rate(rate)} runs/s | "
                            f"ETA={_format_duration(eta) if rate > 0 else 'n/a'} | "
                            f"CPU={_format_duration(cpu_seconds)} | "
                            f"alg_wall={_format_duration(algorithm_wall_seconds)} | "
                            f"persist_avg={persist_avg:.1f}ms | failed={failed} | "
                            f"{last_run_text}",
                            flush=True,
                        )
                        last_progress_time = now
                        while next_progress_at <= processed:
                            next_progress_at += progress_step

                    # Back-pressure: keep exactly one new task per completed
                    # worker slot instead of allowing a massive Future queue.
                    submit_next(executor)

        wall_seconds = perf_counter() - wall_started
        processed = completed + failed
        rate = processed / wall_seconds if wall_seconds > 0 else 0.0
        print(
            "Campaign completed: "
            f"processed={processed:,}/{pending_count:,} | "
            f"completed={completed:,} | failed={failed:,} | "
            f"elapsed={_format_duration(wall_seconds)} | "
            f"rate={_format_rate(rate)} runs/s | "
            f"CPU={_format_duration(cpu_seconds)} | "
            f"alg_wall={_format_duration(algorithm_wall_seconds)} | "
            f"persist={_format_duration(persistence_seconds)}",
            flush=True,
        )

        return ExecutionReport(
            experiment_id=experiment_id(experiment),
            expected_run_count=total_runs,
            completed_run_count=completed,
            skipped_completed_count=skipped,
            failed_run_count=failed,
            cpu_seconds=cpu_seconds,
            wall_seconds=wall_seconds,
            algorithm_wall_seconds=algorithm_wall_seconds,
            persistence_seconds=persistence_seconds,
        )


__all__ = ["ExecutionReport", "ExperimentRunner", "WorkerExecution"]

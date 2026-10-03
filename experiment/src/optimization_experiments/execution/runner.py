from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
import multiprocessing as mp
import os
from time import perf_counter

from ..algorithms import AlgorithmRegistry, default_registry
from ..artifacts import ArtifactStore
from ..core.ids import experiment_id, run_id
from ..core.models import ExperimentSpecification, RunResult, RunSpecification


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    experiment_id: str
    expected_run_count: int
    completed_run_count: int
    skipped_completed_count: int
    failed_run_count: int
    cpu_seconds: float
    wall_seconds: float

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


def _worker(
    run_specification: RunSpecification,
    registry: AlgorithmRegistry,
) -> RunResult:
    adapter = registry.create(
        run_specification.algorithm.algorithm.implementation,
        dict(run_specification.algorithm.parameters),
    )
    return adapter.run(run_specification)


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
    """Parallel, resumable runner with low-overhead timing-aware progress."""

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
        if experiment_id(experiment) != experiment_id(self.artifact_store.experiment):
            raise ValueError("Runner experiment does not match the artifact store.")

        self.artifact_store.initialize()

        all_runs = tuple(experiment.iter_run_specifications())
        pending = (
            specification
            for specification in all_runs
            if not self.artifact_store.has_run(run_id(specification))
        )
        pending = iter(pending)

        total_runs = len(all_runs)
        skipped = sum(
            1
            for specification in all_runs
            if self.artifact_store.has_run(run_id(specification))
        )
        pending_count = total_runs - skipped
        completed = 0
        failed = 0
        cpu_seconds = 0.0
        wall_started = perf_counter()
        next_progress_at = max(1, int(pending_count * self.progress_interval_fraction))
        last_progress_time = wall_started

        worker_count = min(self.max_workers, os.cpu_count() or 1)
        print(
            f"Starting {experiment.name!r}: {total_runs:,} runs | "
            f"{skipped:,} already complete | {pending_count:,} pending | "
            f"{worker_count:,} workers",
            flush=True,
        )

        if not pending_count:
            return ExecutionReport(
                experiment_id=experiment_id(experiment),
                expected_run_count=total_runs,
                completed_run_count=0,
                skipped_completed_count=skipped,
                failed_run_count=0,
                cpu_seconds=0.0,
                wall_seconds=0.0,
            )

        context = mp.get_context(self.start_method)

        # Keep only one future per worker in flight. This bounds scheduler memory
        # and keeps submission overhead negligible for very large campaigns.
        with ProcessPoolExecutor(
            max_workers=worker_count,
            mp_context=context,
        ) as executor:
            futures: dict[object, RunSpecification] = {}

            def submit_next() -> bool:
                try:
                    specification = next(pending)
                except StopIteration:
                    return False
                future = executor.submit(_worker, specification, self.registry)
                futures[future] = specification
                return True

            for _ in range(worker_count):
                if not submit_next():
                    break

            last_result: RunResult | None = None

            while futures:
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    specification = futures.pop(future)
                    try:
                        result = future.result()
                    except Exception as error:
                        failed += 1
                        self.artifact_store.save_failure(specification, error)
                        print(
                            f"[failed] {run_id(specification)}: "
                            f"{type(error).__name__}: {error}",
                            flush=True,
                        )
                    else:
                        self.artifact_store.save_run(result)
                        completed += 1
                        cpu_seconds += result.timing.cpu_seconds
                        last_result = result

                    processed = completed + failed
                    total_processed = skipped + processed
                    now = perf_counter()
                    elapsed = now - wall_started
                    should_report = (
                        processed >= next_progress_at
                        or now - last_progress_time >= self.progress_interval_seconds
                        or processed == pending_count
                    )
                    if should_report:
                        rate = processed / elapsed if elapsed > 0 else 0.0
                        remaining = max(0, pending_count - processed)
                        eta = remaining / rate if rate > 0 else 0.0
                        percentage = total_processed / total_runs * 100.0
                        if last_result is None:
                            last_run_text = "last_run=n/a"
                        else:
                            last_run_text = (
                                f"last_run={run_id(last_result.specification)} | "
                                f"run_wall={_format_duration(last_result.timing.wall_seconds or 0.0)} | "
                                f"run_cpu={_format_duration(last_result.timing.cpu_seconds)} | "
                                f"FE={last_result.function_evaluations:,}"
                            )
                        print(
                            f"[progress] {total_processed:,}/{total_runs:,} "
                            f"({percentage:5.1f}%) | session={processed:,} | "
                            f"elapsed={_format_duration(elapsed)} | "
                            f"rate={_format_rate(rate)} runs/s | "
                            f"ETA={_format_duration(eta) if rate > 0 else 'n/a'} | "
                            f"CPU={_format_duration(cpu_seconds)} | "
                            f"failed={failed} | {last_run_text}",
                            flush=True,
                        )
                        last_progress_time = now
                        while next_progress_at <= processed:
                            next_progress_at += max(
                                1, int(pending_count * self.progress_interval_fraction)
                            )

                    submit_next()

        wall_seconds = perf_counter() - wall_started
        processed = completed + failed
        rate = processed / wall_seconds if wall_seconds > 0 else 0.0
        print(
            "Campaign completed: "
            f"processed={processed:,}/{pending_count:,} | "
            f"completed={completed:,} | failed={failed:,} | "
            f"elapsed={_format_duration(wall_seconds)} | "
            f"rate={_format_rate(rate)} runs/s | "
            f"CPU={_format_duration(cpu_seconds)}",
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
        )


__all__ = ["ExecutionReport", "ExperimentRunner"]

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass
import multiprocessing as mp
import os
from collections.abc import Iterator

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


def _worker(
    run_specification: RunSpecification,
    registry: AlgorithmRegistry,
) -> RunResult:
    adapter = registry.create(
        run_specification.algorithm.algorithm.implementation,
        dict(run_specification.algorithm.parameters),
    )
    return adapter.run(run_specification)


class ExperimentRunner:
    """Parallel, resumable runner with bounded in-flight work."""

    def __init__(
        self,
        artifact_store: ArtifactStore,
        registry: AlgorithmRegistry | None = None,
        *,
        max_workers: int | None = None,
        start_method: str = "forkserver",
    ) -> None:
        self.artifact_store = artifact_store
        self.registry = registry or default_registry()
        self.max_workers = max_workers or os.cpu_count() or 1
        self.start_method = start_method

    def run(self, experiment: ExperimentSpecification) -> ExecutionReport:
        if experiment_id(experiment) != experiment_id(self.artifact_store.experiment):
            raise ValueError("Runner experiment does not match the artifact store.")

        self.artifact_store.initialize()

        completed_ids = set(self.artifact_store.completed_run_ids())
        expected_run_count = experiment.run_count
        skipped = sum(
            1
            for specification in experiment.iter_run_specifications()
            if run_id(specification) in completed_ids
        )
        pending_count = expected_run_count - skipped

        completed = 0
        failed = 0
        cpu_seconds = 0.0

        worker_count = min(max(1, self.max_workers), os.cpu_count() or 1)
        print(
            f"Starting {experiment.name!r}: "
            f"{expected_run_count:,} runs | "
            f"{skipped:,} already complete | "
            f"{worker_count:,} workers",
            flush=True,
        )

        if pending_count == 0:
            return ExecutionReport(
                experiment_id=experiment_id(experiment),
                expected_run_count=expected_run_count,
                completed_run_count=0,
                skipped_completed_count=skipped,
                failed_run_count=0,
                cpu_seconds=0.0,
            )

        context = mp.get_context(self.start_method)
        specifications: Iterator[RunSpecification] = (
            specification
            for specification in experiment.iter_run_specifications()
            if run_id(specification) not in completed_ids
        )

        with ProcessPoolExecutor(
            max_workers=worker_count,
            mp_context=context,
        ) as executor:
            in_flight: dict[Future[RunResult], RunSpecification] = {}

            def submit_next() -> bool:
                try:
                    specification = next(specifications)
                except StopIteration:
                    return False
                future = executor.submit(_worker, specification, self.registry)
                in_flight[future] = specification
                return True

            for _ in range(min(worker_count, pending_count)):
                submit_next()

            while in_flight:
                done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
                for future in done:
                    specification = in_flight.pop(future)
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
                        self.artifact_store.report_progress(
                            completed=completed,
                            total=pending_count,
                        )

                    submit_next()

        return ExecutionReport(
            experiment_id=experiment_id(experiment),
            expected_run_count=expected_run_count,
            completed_run_count=completed,
            skipped_completed_count=skipped,
            failed_run_count=failed,
            cpu_seconds=cpu_seconds,
        )


__all__ = ["ExecutionReport", "ExperimentRunner"]

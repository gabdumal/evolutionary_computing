from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import multiprocessing as mp
import os

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
    """Parallel, resumable runner for independent experiment runs."""

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

        all_runs = tuple(experiment.iter_run_specifications())
        pending = [
            specification
            for specification in all_runs
            if not self.artifact_store.has_run(run_id(specification))
        ]

        skipped = len(all_runs) - len(pending)
        completed = 0
        failed = 0
        cpu_seconds = 0.0

        print(
            f"Starting {experiment.name!r}: "
            f"{len(all_runs):,} runs | "
            f"{skipped:,} already complete | "
            f"{min(self.max_workers, os.cpu_count() or 1):,} workers",
            flush=True,
        )

        if not pending:
            self.artifact_store.report_progress(completed=0, total=0)
            return ExecutionReport(
                experiment_id=experiment_id(experiment),
                expected_run_count=len(all_runs),
                completed_run_count=0,
                skipped_completed_count=skipped,
                failed_run_count=0,
                cpu_seconds=0.0,
            )

        worker_count = min(self.max_workers, os.cpu_count() or 1)
        context = mp.get_context(self.start_method)

        with ProcessPoolExecutor(
            max_workers=worker_count,
            mp_context=context,
        ) as executor:
            futures = {
                executor.submit(_worker, specification, self.registry): specification
                for specification in pending
            }

            for future in as_completed(futures):
                specification = futures[future]
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
                        total=len(pending),
                    )

        return ExecutionReport(
            experiment_id=experiment_id(experiment),
            expected_run_count=len(all_runs),
            completed_run_count=completed,
            skipped_completed_count=skipped,
            failed_run_count=failed,
            cpu_seconds=cpu_seconds,
        )


__all__ = ["ExecutionReport", "ExperimentRunner"]

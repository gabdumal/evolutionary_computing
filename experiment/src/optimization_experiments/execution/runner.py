from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import multiprocessing as mp
import os
from pathlib import Path
import time

from ..algorithms import AlgorithmRegistry
from ..artifacts import ArtifactStore
from ..core.ids import run_id
from ..core.models import ExperimentSpecification, RunResult, RunSpecification


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    experiment_id: str
    expected_run_count: int
    completed_run_count: int
    skipped_completed_count: int
    failed_run_count: int
    elapsed_cpu_seconds: float


def _worker(
    run_specification: RunSpecification,
    registry: AlgorithmRegistry,
) -> RunResult:
    parameters = dict(run_specification.algorithm.parameters)
    adapter = registry.create(run_specification.algorithm.algorithm.implementation, parameters)
    return adapter.run(run_specification)


class ExperimentRunner:
    def __init__(
        self,
        artifact_store: ArtifactStore,
        registry: AlgorithmRegistry,
        *,
        max_workers: int | None = None,
        start_method: str = "forkserver",
    ) -> None:
        self.artifact_store = artifact_store
        self.registry = registry
        self.max_workers = max_workers or os.cpu_count() or 1
        self.start_method = start_method

    def run(self, experiment: ExperimentSpecification) -> ExecutionReport:
        from ..core.ids import experiment_id

        exp_id = experiment_id(experiment)
        self.artifact_store.initialize_experiment(experiment)

        pending = []
        skipped = 0
        all_specs = tuple(experiment.iter_run_specifications())

        for spec in all_specs:
            if self.artifact_store.has_run(run_id(spec)):
                skipped += 1
            else:
                pending.append(spec)

        completed = 0
        failed = 0
        cpu_sum = 0.0
        started = time.perf_counter()

        context = mp.get_context(self.start_method)
        with ProcessPoolExecutor(
            max_workers=self.max_workers,
            mp_context=context,
        ) as executor:
            futures = {
                executor.submit(_worker, spec, self.registry): spec
                for spec in pending
            }
            for future in as_completed(futures):
                spec = futures[future]
                try:
                    result = future.result()
                    self.artifact_store.save_run(result)
                    completed += 1
                    cpu_sum += result.timing.cpu_seconds
                    self.artifact_store.report_progress(
                        completed=completed,
                        total=len(pending),
                        run_id=run_id(spec),
                    )
                except Exception as exc:
                    failed += 1
                    self.artifact_store.save_failure(spec, exc)

        _ = time.perf_counter() - started  # Intentionally not part of the scientific metric.

        return ExecutionReport(
            experiment_id=exp_id,
            expected_run_count=len(all_specs),
            completed_run_count=completed,
            skipped_completed_count=skipped,
            failed_run_count=failed,
            elapsed_cpu_seconds=cpu_sum,
        )

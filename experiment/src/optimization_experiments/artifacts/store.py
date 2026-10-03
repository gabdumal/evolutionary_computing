from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd

from ..core.ids import experiment_id, run_id
from ..core.models import ExperimentSpecification, RunResult, RunSpecification
from ..core.serialization import to_primitive


class ArtifactStore:
    """Filesystem-backed, resumable experiment store.

    Run JSON files are the authoritative run-level records.
    The Parquet index is a materialized analysis view.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def initialize_experiment(self, experiment: ExperimentSpecification) -> None:
        exp_root = self.root / experiment_id(experiment)
        for directory in ("runs", "failures", "logs", "analysis"):
            (exp_root / directory).mkdir(parents=True, exist_ok=True)
        self._atomic_json(exp_root / "experiment.json", to_primitive(experiment))

    def has_run(self, identifier: str) -> bool:
        return any(self.root.glob(f"*/runs/{identifier}.json"))

    def _experiment_root_for_run(self, identifier: str) -> Path:
        matches = list(self.root.glob(f"*/runs/{identifier}.json"))
        if not matches:
            raise FileNotFoundError(identifier)
        return matches[0].parent.parent

    def save_run(self, result: RunResult) -> None:
        from ..core.ids import experiment_id

        root = self.root / experiment_id(
            _experiment_from_run(result.specification)
        )
        root.joinpath("runs").mkdir(parents=True, exist_ok=True)
        self._atomic_json(
            root / "runs" / f"{run_id(result.specification)}.json",
            to_primitive(result),
        )

    def save_failure(self, specification: RunSpecification, error: Exception) -> None:
        from ..core.ids import experiment_id

        root = self.root / experiment_id(
            _experiment_from_run(specification)
        )
        root.joinpath("failures").mkdir(parents=True, exist_ok=True)
        self._atomic_json(
            root / "failures" / f"{run_id(specification)}.json",
            {
                "run_id": run_id(specification),
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )

    def report_progress(self, *, completed: int, total: int, run_id: str) -> None:
        print(f"[progress] {completed}/{total} completed — {run_id}", flush=True)

    def load_runs(self, experiment: ExperimentSpecification) -> pd.DataFrame:
        root = self.root / experiment_id(experiment)
        rows = []
        for path in sorted(root.glob("runs/*.json")):
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        if not rows:
            return pd.DataFrame()
        return pd.json_normalize(rows)

    def materialize_index(self, experiment: ExperimentSpecification) -> Path:
        root = self.root / experiment_id(experiment)
        dataframe = self.load_runs(experiment)
        path = root / "analysis" / "runs.parquet"
        dataframe.to_parquet(path, index=False)
        return path

    @staticmethod
    def _atomic_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, default=str)
            handle.flush()
            temporary = Path(handle.name)
        temporary.replace(path)


def _experiment_from_run(specification: RunSpecification) -> ExperimentSpecification:
    return ExperimentSpecification(
        name=specification.experiment_name,
        algorithm=specification.algorithm.algorithm,
        scenarios=(specification.scenario,),
        configurations=(specification.algorithm,),
        seeds=__import__(
            "optimization_experiments.core.models",
            fromlist=["SeedPlan"],
        ).SeedPlan((specification.seed,)),
        budget=specification.budget,
    )

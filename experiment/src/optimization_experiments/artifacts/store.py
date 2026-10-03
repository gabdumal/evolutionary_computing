from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from typing import Any, Iterator

import numpy as np
import pandas as pd

from ..core.ids import experiment_id, run_id
from ..core.models import (
    AlgorithmConfiguration,
    AlgorithmSpecification,
    BenchmarkScenario,
    ConvergenceTrace,
    EvaluationBudget,
    ExperimentSpecification,
    ObjectiveResult,
    ParameterDefinition,
    ParameterSchema,
    RunResult,
    RunSpecification,
    SeedPlan,
    TimingResult,
)
from ..core.serialization import to_primitive


ARTIFACT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ArtifactPaths:
    experiment: Path
    runs: Path
    convergence: Path
    failures: Path
    analysis: Path


class ArtifactStore:
    """Filesystem-backed, resumable storage bound to one experiment."""

    def __init__(
        self,
        root: str | Path,
        experiment: ExperimentSpecification,
        *,
        durable: bool = False,
        compress_convergence: bool = False,
    ):
        self.root = Path(root)
        self.experiment = experiment
        self._experiment_identifier = experiment_id(experiment)
        self.durable = durable
        self.compress_convergence = compress_convergence
        self.experiment_root = self.root / self._experiment_identifier
        self.paths = ArtifactPaths(
            experiment=self.experiment_root / "experiment.json",
            runs=self.experiment_root / "runs",
            convergence=self.experiment_root / "convergence",
            failures=self.experiment_root / "failures",
            analysis=self.experiment_root / "analysis",
        )

    @classmethod
    def for_existing(cls, root: str | Path, experiment_identifier: str) -> "ArtifactStore":
        """Create a read-only analysis context for an existing experiment."""
        root = Path(root)
        experiment_root = root / experiment_identifier
        experiment_path = experiment_root / "experiment.json"
        if not experiment_path.is_file():
            raise FileNotFoundError(f"Experiment artifact not found: {experiment_path}")
        payload = json.loads(experiment_path.read_text(encoding="utf-8"))
        if payload.get("experiment_id") != experiment_identifier:
            raise ValueError("Experiment artifact ID does not match the requested identifier.")
        store = cls.__new__(cls)
        store.root = root
        store.experiment = None
        store._experiment_identifier = experiment_identifier
        store.durable = False
        store.compress_convergence = False
        store.experiment_root = experiment_root
        store.paths = ArtifactPaths(
            experiment=experiment_path,
            runs=experiment_root / "runs",
            convergence=experiment_root / "convergence",
            failures=experiment_root / "failures",
            analysis=experiment_root / "analysis",
        )
        return store

    @classmethod
    def for_worker(
        cls,
        root: str | Path,
        experiment_identifier: str,
        *,
        durable: bool = False,
        compress_convergence: bool = False,
    ) -> "ArtifactStore":
        """Create a store context for worker-side persistence.

        Workers already receive a concrete RunSpecification containing the
        experiment ID, so sending the full experiment (thousands of
        configurations for the CSO grid) with every task would waste IPC.
        This context deliberately exposes only the paths and experiment ID
        required to write an authoritative run/failure artifact.
        """
        store = cls.__new__(cls)
        store.root = Path(root)
        store.experiment = None
        store._experiment_identifier = experiment_identifier
        store.durable = durable
        store.compress_convergence = compress_convergence
        store.experiment_root = store.root / experiment_identifier
        store.paths = ArtifactPaths(
            experiment=store.experiment_root / "experiment.json",
            runs=store.experiment_root / "runs",
            convergence=store.experiment_root / "convergence",
            failures=store.experiment_root / "failures",
            analysis=store.experiment_root / "analysis",
        )
        return store

    @property
    def experiment_identifier(self) -> str:
        return self._experiment_identifier

    def initialize(self) -> None:
        for directory in (
            self.paths.runs,
            self.paths.convergence,
            self.paths.failures,
            self.paths.analysis,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        payload = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "experiment": to_primitive(self.experiment),
            "experiment_id": experiment_id(self.experiment),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "environment": _environment_metadata(),
        }

        if self.paths.experiment.exists():
            existing = json.loads(self.paths.experiment.read_text(encoding="utf-8"))
            if existing.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
                raise ValueError("Incompatible artifact schema version.")
            if existing.get("experiment_id") != experiment_id(self.experiment):
                raise ValueError("Artifact directory belongs to a different experiment.")
            if existing.get("experiment") != to_primitive(self.experiment):
                raise ValueError("Existing experiment specification does not match.")
            return

        _atomic_json(self.paths.experiment, payload)

    def run_path(self, identifier: str) -> Path:
        return self.paths.runs / f"{identifier}.json"

    def convergence_path(self, identifier: str) -> Path:
        return self.paths.convergence / f"{identifier}.npz"

    def failure_path(self, identifier: str) -> Path:
        return self.paths.failures / f"{identifier}.json"

    def has_run(self, identifier: str) -> bool:
        return self.run_path(identifier).is_file()

    def completed_run_ids(self) -> tuple[str, ...]:
        return tuple(
            path.stem
            for path in sorted(self.paths.runs.glob("*.json"))
        )

    def save_run(self, result: RunResult) -> None:
        self._validate_result_experiment(result)
        identifier = run_id(result.specification)
        convergence_path = self.convergence_path(identifier)

        _atomic_npz(
            convergence_path,
            evaluations=np.asarray(
                result.convergence.function_evaluations,
                dtype=np.int64,
            ),
            values=np.asarray(
                result.convergence.best_values,
                dtype=np.float64,
            ),
            compress=self.compress_convergence,
            durable=self.durable,
        )

        payload = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "status": "completed",
            "run": to_primitive(result.specification),
            "metrics": {
                "best_value": result.objective.best_value,
                "best_solution": list(result.objective.best_solution),
                "function_evaluations": result.function_evaluations,
                "iterations": result.iterations,
                "cpu_seconds": result.timing.cpu_seconds,
                "wall_seconds": result.timing.wall_seconds,
            },
            "convergence": {
                "path": str(convergence_path.relative_to(self.experiment_root)),
                "sha256": _sha256(convergence_path),
                "points": len(result.convergence.best_values),
            },
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        _atomic_json(self.run_path(identifier), payload, durable=self.durable)

    def save_failure(
        self,
        specification: RunSpecification,
        error: Exception,
    ) -> None:
        self._validate_specification_experiment(specification)
        payload = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "status": "failed",
            "run": to_primitive(specification),
            "error": {
                "type": type(error).__name__,
                "message": str(error),
            },
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        _atomic_json(self.failure_path(run_id(specification)), payload, durable=self.durable)

    def load_run(self, identifier: str) -> RunResult:
        payload = json.loads(
            self.run_path(identifier).read_text(encoding="utf-8")
        )
        if payload["artifact_schema_version"] != ARTIFACT_SCHEMA_VERSION:
            raise ValueError("Incompatible run artifact schema.")
        if payload["status"] != "completed":
            raise ValueError("Run artifact is not completed.")

        specification = _deserialize_run_specification(payload["run"])
        self._validate_specification_experiment(specification)

        expected_identifier = run_id(specification)
        if expected_identifier != identifier:
            raise ValueError("Run ID does not match its artifact filename.")

        convergence = payload["convergence"]
        convergence_path = self.experiment_root / convergence["path"]
        if _sha256(convergence_path) != convergence["sha256"]:
            raise ValueError("Convergence checksum mismatch.")

        with np.load(convergence_path, allow_pickle=False) as arrays:
            evaluations = tuple(
                int(value) for value in np.asarray(
                    arrays["evaluations"],
                    dtype=np.int64,
                ).reshape(-1)
            )
            values = tuple(
                float(value) for value in np.asarray(
                    arrays["values"],
                    dtype=np.float64,
                ).reshape(-1)
            )

        metrics = payload["metrics"]
        return RunResult(
            specification=specification,
            objective=ObjectiveResult(
                best_value=float(metrics["best_value"]),
                best_solution=tuple(
                    float(value) for value in metrics["best_solution"]
                ),
            ),
            function_evaluations=int(metrics["function_evaluations"]),
            iterations=int(metrics["iterations"]),
            timing=TimingResult(
                cpu_seconds=float(metrics["cpu_seconds"]),
                wall_seconds=(
                    float(metrics["wall_seconds"])
                    if metrics.get("wall_seconds") is not None
                    else None
                ),
            ),
            convergence=ConvergenceTrace(
                function_evaluations=evaluations,
                best_values=values,
            ),
        )

    def iter_results(self) -> Iterator[RunResult]:
        for identifier in self.completed_run_ids():
            yield self.load_run(identifier)

    def load_run_records(self) -> tuple[dict[str, Any], ...]:
        records = []
        for identifier in self.completed_run_ids():
            records.append(
                json.loads(
                    self.run_path(identifier).read_text(encoding="utf-8")
                )
            )
        return tuple(records)

    def materialize_index(self) -> Path:
        from ..analysis.runs import create_run_table_from_records

        frame = create_run_table_from_records(self.load_run_records())
        path = self.paths.analysis / "runs.parquet"
        frame.to_parquet(path, index=False)
        return path

    def report_progress(
        self,
        *,
        completed: int,
        total: int,
    ) -> None:
        """Backward-compatible minimal progress output.

        Detailed timing-aware progress is owned by :class:`ExperimentRunner`;
        this method remains for callers that only have completion counts.
        """
        if total <= 0:
            return
        percentage = completed / total * 100.0
        print(
            f"[progress] {completed:,}/{total:,} ({percentage:5.1f}%)",
            flush=True,
        )

    def _validate_specification_experiment(
        self,
        specification: RunSpecification,
    ) -> None:
        if specification.experiment_id != self._experiment_identifier:
            raise ValueError("Run belongs to a different experiment.")

    def _validate_result_experiment(self, result: RunResult) -> None:
        self._validate_specification_experiment(result.specification)


def _deserialize_run_specification(
    payload: dict[str, Any],
) -> RunSpecification:
    algorithm_payload = payload["algorithm"]
    algorithm_specification_payload = algorithm_payload["algorithm"]
    parameter_definitions = tuple(
        ParameterDefinition(
            name=item["name"],
            value_type=_resolve_type(item["value_type"]),
            description=item["description"],
            minimum=item["minimum"],
            maximum=item["maximum"],
            choices=tuple(item["choices"]),
        )
        for item in algorithm_specification_payload["parameter_schema"]["definitions"]
    )
    algorithm_specification = AlgorithmSpecification(
        name=algorithm_specification_payload["name"],
        implementation=algorithm_specification_payload["implementation"],
        parameter_schema=ParameterSchema(parameter_definitions),
        fixed_parameters=algorithm_specification_payload["fixed_parameters"],
    )
    configuration = AlgorithmConfiguration(
        algorithm=algorithm_specification,
        parameters=algorithm_payload["parameters"],
    )
    scenario_payload = payload["scenario"]
    scenario = BenchmarkScenario(
        problem=scenario_payload["problem"],
        dimension=int(scenario_payload["dimension"]),
        objective=scenario_payload["objective"],
        lower_bound=float(scenario_payload["lower_bound"]),
        upper_bound=float(scenario_payload["upper_bound"]),
        problem_parameters=scenario_payload["problem_parameters"],
    )
    budget = EvaluationBudget(
        int(payload["budget"]["max_function_evaluations"])
    )
    return RunSpecification(
        experiment_id=payload["experiment_id"],
        experiment_name=payload["experiment_name"],
        algorithm=configuration,
        scenario=scenario,
        seed=int(payload["seed"]),
        budget=budget,
    )


def _resolve_type(path: str) -> type:
    if path == "builtins.int":
        return int
    if path == "builtins.float":
        return float
    if path == "builtins.bool":
        return bool
    if path == "builtins.str":
        return str
    raise ValueError(f"Unsupported parameter type in artifact: {path!r}.")


def _atomic_json(path: Path, payload: Any, *, durable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(
                payload,
                handle,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.flush()
            if durable:
                os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _atomic_npz(
    path: Path,
    *,
    evaluations: np.ndarray,
    values: np.ndarray,
    compress: bool = False,
    durable: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            if compress:
                np.savez_compressed(
                    handle,
                    evaluations=evaluations,
                    values=values,
                )
            else:
                np.savez(
                    handle,
                    evaluations=evaluations,
                    values=values,
                )
            handle.flush()
            if durable:
                os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _environment_metadata() -> dict[str, str]:
    metadata = {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": _package_version("numpy"),
        "pandas": _package_version("pandas"),
        "pyarrow": _package_version("pyarrow"),
        "niapy": _package_version("niapy"),
    }
    try:
        metadata["git_commit"] = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
    except Exception:
        metadata["git_commit"] = "unknown"
    return metadata


def _package_version(name: str) -> str:
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return "not-installed"


__all__ = ["ARTIFACT_SCHEMA_VERSION", "ArtifactStore"]

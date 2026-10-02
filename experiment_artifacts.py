from __future__ import annotations

"""Persistent artifacts for reproducible optimization experiments.

The store is intentionally independent from the execution and analysis
layers. Each completed run owns two files:

- ``runs/<run_id>.json``: scalar metrics and the complete run specification.
- ``convergence/<run_id>.npz``: the convergence trajectory.

A run is considered completed only when its JSON record exists. The
convergence artifact is written first, so an interrupted save cannot make
a partially written run look completed.

The experiment manifest is immutable after creation. It contains the
canonical experiment specification and expected run count, so no shared
counter or mutable index is required while multiple workers finish runs.
"""

import json
import math
import os
import re
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Final, Literal, TypeAlias, TypedDict, cast

import numpy as np
import numpy.typing as npt

from experiment_specifications import (
    AlgorithmConfiguration,
    AlgorithmSpecification,
    ExperimentRunSpecification,
    ExperimentSpecification,
    ParameterValue,
    ProblemSpecification,
    TerminationSpecification,
)

ARTIFACT_SCHEMA_VERSION: Final[int] = 1

RunStatus: TypeAlias = Literal["completed", "failed"]

FloatArray: TypeAlias = npt.NDArray[np.float64]
IntArray: TypeAlias = npt.NDArray[np.int64]


class _MetricsArtifact(TypedDict):
    best_value: float
    best_solution: list[float]
    function_evaluations: int
    iterations: int
    elapsed_seconds: float


class _ConvergenceArtifact(TypedDict):
    path: str
    sha256: str
    points: int


class _AlgorithmArtifact(TypedDict):
    import_path: str
    name: str
    parameters: dict[str, ParameterValue]


class _ConfigurationArtifact(TypedDict):
    algorithm: _AlgorithmArtifact
    parameters: dict[str, ParameterValue]


class _ProblemArtifact(TypedDict):
    name: str
    dimensions: list[int]
    import_path: str | None
    parameters: dict[str, ParameterValue]
    optimization: Literal["minimize", "maximize"]


class _TerminationArtifact(TypedDict):
    max_evaluations: int | None
    max_iterations: int | None
    cutoff_value: float | None
    enable_logging: bool


class _RunArtifact(TypedDict):
    experiment_id: str
    configuration_id: str
    configuration: _ConfigurationArtifact
    problem: _ProblemArtifact
    dimension: int
    seed: int
    termination: _TerminationArtifact


class _RunRecordArtifact(TypedDict):
    artifact_schema_version: int
    status: Literal["completed"]
    saved_at_utc: str
    run: _RunArtifact
    metrics: _MetricsArtifact
    convergence: _ConvergenceArtifact


class _ManifestArtifact(TypedDict):
    artifact_schema_version: int
    experiment_id: str
    experiment_name: str
    expected_run_count: int
    specification: dict[str, object]
    created_at_utc: str


_EXPERIMENT_DIRECTORY_SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class ExperimentRunResult:
    """Scientific result and convergence data for one completed run."""

    run_specification: ExperimentRunSpecification
    best_value: float
    best_solution: tuple[float, ...]
    function_evaluations: int
    iterations: int
    elapsed_seconds: float
    convergence_evaluations: IntArray
    convergence_values: FloatArray

    def __post_init__(self) -> None:
        if not math.isfinite(self.best_value):
            raise ValueError("best_value must be finite.")

        if not isinstance(self.function_evaluations, int) or isinstance(
            self.function_evaluations, bool
        ):
            raise TypeError("function_evaluations must be an integer.")

        if self.function_evaluations <= 0:
            raise ValueError("function_evaluations must be greater than zero.")

        if not isinstance(self.iterations, int) or isinstance(self.iterations, bool):
            raise TypeError("iterations must be an integer.")

        if self.iterations < 0:
            raise ValueError("iterations must not be negative.")

        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0.0:
            raise ValueError("elapsed_seconds must be a finite non-negative number.")

        expected_dimension = self.run_specification.dimension

        if len(self.best_solution) != expected_dimension:
            raise ValueError(
                "best_solution dimension does not match the run "
                f"dimension ({expected_dimension})."
            )

        if not all(math.isfinite(coordinate) for coordinate in self.best_solution):
            raise ValueError("best_solution must contain finite values.")

        evaluations = np.asarray(
            self.convergence_evaluations,
            dtype=np.int64,
        )
        values = np.asarray(
            self.convergence_values,
            dtype=np.float64,
        )

        if evaluations.ndim != 1:
            raise ValueError("convergence_evaluations must be one-dimensional.")

        if values.ndim != 1:
            raise ValueError("convergence_values must be one-dimensional.")

        if len(evaluations) != len(values):
            raise ValueError(
                "convergence_evaluations and convergence_values must have "
                "the same length."
            )

        if len(evaluations) == 0:
            raise ValueError("A completed run must contain convergence data.")

        if np.any(evaluations < 0):
            raise ValueError(
                "convergence_evaluations must not contain negative values."
            )

        if np.any(np.diff(evaluations) < 0):
            raise ValueError(
                "convergence_evaluations must be monotonically increasing."
            )

        if not np.all(np.isfinite(values)):
            raise ValueError("convergence_values must contain only finite values.")

        object.__setattr__(
            self,
            "convergence_evaluations",
            evaluations.copy(),
        )
        object.__setattr__(
            self,
            "convergence_values",
            values.copy(),
        )
        object.__setattr__(
            self,
            "best_solution",
            tuple(float(coordinate) for coordinate in self.best_solution),
        )


@dataclass(frozen=True, slots=True)
class ExperimentArtifactManifest:
    """Immutable metadata describing one artifact directory."""

    artifact_schema_version: int
    experiment_id: str
    experiment_name: str
    expected_run_count: int
    specification: Mapping[str, object]
    created_at_utc: str

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_schema_version, int) or isinstance(
            self.artifact_schema_version, bool
        ):
            raise TypeError("artifact_schema_version must be an integer.")

        if self.artifact_schema_version <= 0:
            raise ValueError("artifact_schema_version must be greater than zero.")

        if not self.experiment_id.strip():
            raise ValueError("experiment_id must not be empty.")

        if not self.experiment_name.strip():
            raise ValueError("experiment_name must not be empty.")

        if not isinstance(self.expected_run_count, int) or isinstance(
            self.expected_run_count, bool
        ):
            raise TypeError("expected_run_count must be an integer.")

        if self.expected_run_count <= 0:
            raise ValueError("expected_run_count must be greater than zero.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc must not be empty.")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify_experiment_name(name: str) -> str:
    slug = _EXPERIMENT_DIRECTORY_SAFE_NAME_PATTERN.sub(
        "_",
        name.strip(),
    )
    slug = slug.strip("._-")

    if not slug:
        return "experiment"

    return slug[:80]


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _jsonify(value: object) -> object:
    """Convert tuples and mappings into JSON-compatible structures."""
    if isinstance(value, Mapping):
        return {str(key): _jsonify(item) for key, item in value.items()}

    if isinstance(value, tuple):
        return [_jsonify(item) for item in value]

    if isinstance(value, list):
        return [_jsonify(item) for item in value]

    return value


def _atomic_write_text(
    path: Path,
    content: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def _atomic_write_npz(
    path: Path,
    *,
    evaluations: IntArray,
    values: FloatArray,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            np.savez_compressed(
                temporary_file,
                evaluations=evaluations,
                values=values,
            )
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def _fsync_directory(directory: Path) -> None:
    """Best-effort directory fsync for POSIX filesystems."""
    try:
        directory_descriptor = os.open(
            directory,
            os.O_RDONLY,
        )
    except OSError:
        return

    try:
        os.fsync(directory_descriptor)
    except OSError:
        pass
    finally:
        os.close(directory_descriptor)


def _file_sha256(path: Path) -> str:
    digest = sha256()

    with path.open("rb") as file:
        for block in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def _load_json_object(path: Path) -> dict[str, object]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise TypeError(f"Expected a JSON object in artifact: {path}")

    return payload


def _parse_json_string(
    value: object,
    *,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    return value


def _parse_json_int(
    value: object,
    *,
    field_name: str,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")

    return value


def _parse_run_specification(
    payload: _RunArtifact,
) -> ExperimentRunSpecification:
    configuration_payload = payload["configuration"]
    problem_payload = payload["problem"]
    termination_payload = payload["termination"]

    algorithm_payload = configuration_payload["algorithm"]

    algorithm = AlgorithmSpecification(
        import_path=algorithm_payload["import_path"],
        name=algorithm_payload["name"],
        parameters=algorithm_payload["parameters"],
    )

    configuration = AlgorithmConfiguration(
        algorithm=algorithm,
        parameters=configuration_payload["parameters"],
    )

    return ExperimentRunSpecification(
        experiment_id=payload["experiment_id"],
        configuration=configuration,
        problem=ProblemSpecification(
            name=problem_payload["name"],
            dimensions=tuple(problem_payload["dimensions"]),
            import_path=problem_payload["import_path"],
            parameters=problem_payload["parameters"],
            optimization=problem_payload["optimization"],
        ),
        dimension=payload["dimension"],
        seed=payload["seed"],
        termination=TerminationSpecification(
            max_evaluations=termination_payload["max_evaluations"],
            max_iterations=termination_payload["max_iterations"],
            cutoff_value=termination_payload["cutoff_value"],
            enable_logging=termination_payload["enable_logging"],
        ),
    )


def _serialize_run_specification(
    run: ExperimentRunSpecification,
) -> dict[str, object]:
    return {
        "experiment_id": run.experiment_id,
        "configuration_id": run.configuration_id,
        "configuration": {
            "algorithm": run.configuration.algorithm.identity(),
            "parameters": run.configuration.parameters,
        },
        "problem": run.problem.identity(),
        "dimension": run.dimension,
        "seed": run.seed,
        "termination": run.termination.identity(),
    }


def _serialize_manifest(
    manifest: ExperimentArtifactManifest,
) -> dict[str, object]:
    return {
        "artifact_schema_version": manifest.artifact_schema_version,
        "experiment_id": manifest.experiment_id,
        "experiment_name": manifest.experiment_name,
        "expected_run_count": manifest.expected_run_count,
        "specification": _jsonify(manifest.specification),
        "created_at_utc": manifest.created_at_utc,
    }


class ExperimentArtifactStore:
    """Filesystem-backed, resumable storage for one experiment."""

    def __init__(
        self,
        root_directory: str | Path,
        experiment: ExperimentSpecification,
    ) -> None:
        self.root_directory = Path(root_directory)
        self.experiment = experiment

        experiment_directory_name = (
            f"{experiment.experiment_id}__{_slugify_experiment_name(experiment.name)}"
        )

        self.experiment_directory = self.root_directory / experiment_directory_name

        self.manifest_path = self.experiment_directory / "manifest.json"
        self.runs_directory = self.experiment_directory / "runs"
        self.convergence_directory = self.experiment_directory / "convergence"
        self.failures_directory = self.experiment_directory / "failures"

    def initialize(self) -> ExperimentArtifactManifest:
        """Create or validate the immutable experiment manifest."""
        self.experiment_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.runs_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.convergence_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.failures_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        expected_manifest = ExperimentArtifactManifest(
            artifact_schema_version=ARTIFACT_SCHEMA_VERSION,
            experiment_id=self.experiment.experiment_id,
            experiment_name=self.experiment.name,
            expected_run_count=self.experiment.run_count,
            specification=self.experiment.identity(),
            created_at_utc=_utc_timestamp(),
        )

        if self.manifest_path.exists():
            existing_manifest = self.load_manifest()

            if (
                existing_manifest.artifact_schema_version
                != expected_manifest.artifact_schema_version
            ):
                raise ValueError(
                    "The existing artifact directory uses an "
                    "incompatible artifact schema version."
                )

            if existing_manifest.experiment_id != expected_manifest.experiment_id:
                raise ValueError(
                    "The existing artifact directory belongs to a different experiment."
                )

            if _canonical_json(existing_manifest.specification) != _canonical_json(
                expected_manifest.specification
            ):
                raise ValueError(
                    "The existing artifact manifest does not match "
                    "the supplied experiment specification."
                )

            return existing_manifest

        _atomic_write_text(
            self.manifest_path,
            json.dumps(
                _serialize_manifest(expected_manifest),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
        )

        return expected_manifest

    def load_manifest(self) -> ExperimentArtifactManifest:
        """Load the immutable experiment manifest."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(
                f"Experiment manifest does not exist: {self.manifest_path}"
            )

        raw_payload = _load_json_object(self.manifest_path)
        payload = cast(_ManifestArtifact, raw_payload)

        return ExperimentArtifactManifest(
            artifact_schema_version=_parse_json_int(
                payload["artifact_schema_version"],
                field_name="artifact_schema_version",
            ),
            experiment_id=_parse_json_string(
                payload["experiment_id"],
                field_name="experiment_id",
            ),
            experiment_name=_parse_json_string(
                payload["experiment_name"],
                field_name="experiment_name",
            ),
            expected_run_count=_parse_json_int(
                payload["expected_run_count"],
                field_name="expected_run_count",
            ),
            specification=cast(
                Mapping[str, object],
                payload["specification"],
            ),
            created_at_utc=_parse_json_string(
                payload["created_at_utc"],
                field_name="created_at_utc",
            ),
        )

    def run_result_path(
        self,
        run: str | ExperimentRunSpecification,
    ) -> Path:
        """Return the JSON artifact path for a run."""
        run_id = self._run_id(run)
        return self.runs_directory / f"{run_id}.json"

    def convergence_result_path(
        self,
        run: str | ExperimentRunSpecification,
    ) -> Path:
        """Return the convergence artifact path for a run."""
        run_id = self._run_id(run)
        return self.convergence_directory / f"{run_id}.npz"

    def failure_result_path(
        self,
        run: str | ExperimentRunSpecification,
    ) -> Path:
        """Return the latest failure record path for a run."""
        run_id = self._run_id(run)
        return self.failures_directory / f"{run_id}.json"

    def is_run_completed(
        self,
        run: str | ExperimentRunSpecification,
    ) -> bool:
        """Return whether a complete run marker exists."""
        return self.run_result_path(run).is_file()

    def completed_run_ids(self) -> tuple[str, ...]:
        """Return all completed run IDs in deterministic order."""
        return tuple(path.stem for path in sorted(self.runs_directory.glob("*.json")))

    def completed_run_count(self) -> int:
        """Return the number of completed runs currently persisted."""
        return len(self.completed_run_ids())

    def iter_pending_run_specifications(
        self,
    ) -> Iterator[ExperimentRunSpecification]:
        """Yield only runs that have not completed."""
        for run in self.experiment.iter_run_specifications():
            if not self.is_run_completed(run):
                yield run

    def iter_completed_run_results(
        self,
    ) -> Iterator[ExperimentRunResult]:
        """Load all completed runs in deterministic path order."""
        for run_id in self.completed_run_ids():
            yield self.load_run_result(run_id)

    def save_run_result(
        self,
        result: ExperimentRunResult,
    ) -> None:
        """Atomically persist a completed run and its convergence data."""
        self._validate_run_belongs_to_experiment(result.run_specification)

        run = result.run_specification
        convergence_path = self.convergence_result_path(run)
        result_path = self.run_result_path(run)

        _atomic_write_npz(
            convergence_path,
            evaluations=result.convergence_evaluations,
            values=result.convergence_values,
        )

        record = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "status": "completed",
            "saved_at_utc": _utc_timestamp(),
            "run": _serialize_run_specification(run),
            "metrics": {
                "best_value": result.best_value,
                "best_solution": list(result.best_solution),
                "function_evaluations": result.function_evaluations,
                "iterations": result.iterations,
                "elapsed_seconds": result.elapsed_seconds,
            },
            "convergence": {
                "path": str(convergence_path.relative_to(self.experiment_directory)),
                "sha256": _file_sha256(convergence_path),
                "points": len(result.convergence_values),
            },
        }

        _atomic_write_text(
            result_path,
            json.dumps(
                _jsonify(record),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
        )

    def save_run_failure(
        self,
        run: ExperimentRunSpecification,
        *,
        exception_type: str,
        message: str,
        traceback: str | None = None,
    ) -> None:
        """Persist the latest execution failure without marking the run complete."""
        self._validate_run_belongs_to_experiment(run)

        if not exception_type.strip():
            raise ValueError("exception_type must not be empty.")

        failure_record: dict[str, object] = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "status": "failed",
            "saved_at_utc": _utc_timestamp(),
            "run": _serialize_run_specification(run),
            "error": {
                "exception_type": exception_type,
                "message": message,
                "traceback": traceback,
            },
        }

        _atomic_write_text(
            self.failure_result_path(run),
            json.dumps(
                _jsonify(failure_record),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
        )

    def load_run_result(
        self,
        run: str | ExperimentRunSpecification,
    ) -> ExperimentRunResult:
        """Load and integrity-check a completed run."""
        result_path = self.run_result_path(run)

        if not result_path.is_file():
            raise FileNotFoundError(
                f"Completed run artifact does not exist: {result_path}"
            )

        raw_payload = _load_json_object(result_path)
        payload = cast(_RunRecordArtifact, raw_payload)

        if payload["artifact_schema_version"] != ARTIFACT_SCHEMA_VERSION:
            raise ValueError("The run artifact uses an incompatible artifact schema.")

        if payload["status"] != "completed":
            raise ValueError("The run artifact is not marked as completed.")

        loaded_run = _parse_run_specification(payload["run"])
        self._validate_run_belongs_to_experiment(loaded_run)

        requested_run_id = self._run_id(run)

        if loaded_run.run_id != requested_run_id:
            raise ValueError("The persisted run ID does not match its file name.")

        metrics = payload["metrics"]

        raw_best_solution = metrics["best_solution"]

        if not all(
            isinstance(coordinate, (int, float)) and not isinstance(coordinate, bool)
            for coordinate in raw_best_solution
        ):
            raise ValueError("metrics.best_solution must contain only numbers.")

        best_solution = tuple(float(coordinate) for coordinate in raw_best_solution)

        convergence_payload = payload["convergence"]

        relative_convergence_path = convergence_payload["path"]
        convergence_path = self.experiment_directory / relative_convergence_path

        if not convergence_path.is_file():
            raise FileNotFoundError(
                f"Convergence artifact does not exist: {convergence_path}"
            )

        expected_hash = str(convergence_payload["sha256"])
        actual_hash = _file_sha256(convergence_path)

        if actual_hash != expected_hash:
            raise ValueError(
                f"Convergence artifact checksum mismatch: {convergence_path}"
            )

        with np.load(
            convergence_path,
            allow_pickle=False,
        ) as convergence:
            evaluations = np.asarray(
                convergence["evaluations"],
                dtype=np.int64,
            )
            values = np.asarray(
                convergence["values"],
                dtype=np.float64,
            )

        return ExperimentRunResult(
            run_specification=loaded_run,
            best_value=metrics["best_value"],
            best_solution=best_solution,
            function_evaluations=metrics["function_evaluations"],
            iterations=metrics["iterations"],
            elapsed_seconds=metrics["elapsed_seconds"],
            convergence_evaluations=evaluations,
            convergence_values=values,
        )

    def _run_id(
        self,
        run: str | ExperimentRunSpecification,
    ) -> str:
        if isinstance(run, str):
            if not run.strip():
                raise ValueError("run ID must not be empty.")
            return run

        self._validate_run_belongs_to_experiment(run)
        return run.run_id

    def _validate_run_belongs_to_experiment(
        self,
        run: ExperimentRunSpecification,
    ) -> None:
        if run.experiment_id != self.experiment.experiment_id:
            raise ValueError("The supplied run belongs to a different experiment.")


__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "ExperimentArtifactManifest",
    "ExperimentArtifactStore",
    "ExperimentRunResult",
]

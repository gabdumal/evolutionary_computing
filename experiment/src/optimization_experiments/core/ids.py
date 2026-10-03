from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import (
    AlgorithmConfiguration,
    AlgorithmSpecification,
    BenchmarkScenario,
    ExperimentSpecification,
    RunSpecification,
)
from .serialization import to_primitive


def _digest_primitive(value: Any, prefix: str) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:16]}"


def _digest(value: Any, prefix: str) -> str:
    return _digest_primitive(to_primitive(value), prefix)


def algorithm_id(specification: AlgorithmSpecification) -> str:
    return _digest(specification, "alg")


def configuration_id(configuration: AlgorithmConfiguration) -> str:
    return _digest(configuration, "cfg")


def scenario_id(scenario: BenchmarkScenario) -> str:
    return _digest(scenario, "scn")


def experiment_id(specification: ExperimentSpecification) -> str:
    return _digest(specification, "exp")


def run_id(specification: RunSpecification) -> str:
    return _digest(specification, "run")


def algorithm_id_from_primitive(specification: dict[str, Any]) -> str:
    """Return the stable algorithm ID from its canonical serialized form."""
    return _digest_primitive(specification, "alg")


def configuration_id_from_primitive(configuration: dict[str, Any]) -> str:
    """Return the stable configuration ID from its canonical serialized form."""
    return _digest_primitive(configuration, "cfg")


def scenario_id_from_primitive(scenario: dict[str, Any]) -> str:
    """Return the stable scenario ID from its canonical serialized form."""
    return _digest_primitive(scenario, "scn")


def run_id_from_primitive(specification: dict[str, Any]) -> str:
    """Return the stable run ID from its canonical serialized form."""
    return _digest_primitive(specification, "run")


__all__ = [
    "algorithm_id",
    "algorithm_id_from_primitive",
    "configuration_id",
    "configuration_id_from_primitive",
    "experiment_id",
    "run_id",
    "run_id_from_primitive",
    "scenario_id",
    "scenario_id_from_primitive",
]

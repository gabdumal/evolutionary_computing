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


def _digest(value: Any, prefix: str) -> str:
    payload = json.dumps(
        to_primitive(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:16]}"


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

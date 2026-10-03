from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from ..core.models import RunResult, RunSpecification


class AlgorithmAdapter(ABC):
    """Thin adapter boundary between the experiment engine and an algorithm."""

    name: str

    @abstractmethod
    def run(self, specification: RunSpecification) -> RunResult:
        """Execute exactly one independent run."""
        raise NotImplementedError


class AlgorithmRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[dict[str, Any]], AlgorithmAdapter]] = {}

    def register(
        self,
        name: str,
        factory: Callable[[dict[str, Any]], AlgorithmAdapter],
    ) -> None:
        if name in self._factories:
            raise ValueError(f"Algorithm {name!r} is already registered.")
        self._factories[name] = factory

    def create(self, name: str, parameters: dict[str, Any]) -> AlgorithmAdapter:
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise KeyError(f"Unknown algorithm {name!r}.") from exc
        return factory(parameters)

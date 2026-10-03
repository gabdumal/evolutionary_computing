from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from ..core.models import RunResult, RunSpecification


class AlgorithmAdapter(ABC):
    """Execution boundary between the experiment engine and one optimizer."""

    name: str

    @abstractmethod
    def run(self, specification: RunSpecification) -> RunResult:
        """Execute exactly one independent optimization run."""
        raise NotImplementedError


class AlgorithmRegistry:
    """Registry of importable top-level adapter factories.

    The registry stores import paths rather than arbitrary callable objects,
    making the registry safely transferable to worker processes.
    """

    def __init__(self) -> None:
        self._factories: dict[str, str] = {}

    def register(self, name: str, factory_path: str) -> None:
        if name in self._factories:
            raise ValueError(f"Algorithm {name!r} is already registered.")
        self._factories[name] = factory_path

    def create(
        self,
        name: str,
        parameters: dict[str, Any],
    ) -> AlgorithmAdapter:
        try:
            factory_path = self._factories[name]
        except KeyError as exc:
            raise KeyError(f"Unknown algorithm implementation {name!r}.") from exc

        module_name, function_name = factory_path.rsplit(".", maxsplit=1)
        module = importlib.import_module(module_name)
        factory: Callable[[dict[str, Any]], AlgorithmAdapter] = getattr(
            module,
            function_name,
        )
        adapter = factory(parameters)
        if not isinstance(adapter, AlgorithmAdapter):
            raise TypeError(
                f"Factory {factory_path!r} returned {type(adapter).__name__}, "
                "not an AlgorithmAdapter."
            )
        return adapter


def default_registry() -> AlgorithmRegistry:
    registry = AlgorithmRegistry()
    registry.register(
        "cso",
        "optimization_experiments.algorithms.niapy.create_cso_adapter",
    )
    registry.register(
        "zoadamm",
        "optimization_experiments.algorithms.zoadamm.create_zoadamm_adapter",
    )
    return registry

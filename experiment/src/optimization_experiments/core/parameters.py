from __future__ import annotations

import itertools
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .models import AlgorithmConfiguration, AlgorithmSpecification


def resolve_configurations(
    algorithm: AlgorithmSpecification,
    grid: Mapping[str, Sequence[Any]],
) -> tuple[AlgorithmConfiguration, ...]:
    names = algorithm.parameter_schema.names
    unknown = set(grid) - set(names)
    missing = set(names) - set(grid)
    if unknown:
        raise ValueError(f"Unknown grid parameters: {sorted(unknown)}.")
    if missing:
        raise ValueError(f"Missing grid parameters: {sorted(missing)}.")
    if any(not values for values in grid.values()):
        raise ValueError("Grid parameter values cannot be empty.")

    ordered_values = [tuple(grid[name]) for name in names]
    configurations = []
    seen = set()

    for values in itertools.product(*ordered_values):
        parameters = dict(zip(names, values, strict=True))
        configuration = AlgorithmConfiguration(algorithm=algorithm, parameters=parameters)
        key = tuple((name, parameters[name]) for name in names)
        if key not in seen:
            seen.add(key)
            configurations.append(configuration)

    return tuple(configurations)

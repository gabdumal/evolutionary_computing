from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from typing import Any

from .models import AlgorithmConfiguration, AlgorithmSpecification


def resolve_configurations(
    algorithm: AlgorithmSpecification,
    grid: Mapping[str, Sequence[Any]],
) -> tuple[AlgorithmConfiguration, ...]:
    names = algorithm.parameter_schema.names
    unknown = set(grid) - set(names)
    if unknown:
        raise ValueError(f"Unknown grid parameters: {sorted(unknown)}.")
    missing = set(names) - set(grid)
    missing -= set(algorithm.fixed_parameters)
    if missing:
        raise ValueError(
            f"Parameters missing from both fixed values and grid: {sorted(missing)}."
        )

    ordered_names = tuple(
        name for name in names if name in grid
    )
    if any(not grid[name] for name in ordered_names):
        raise ValueError("Grid parameter values cannot be empty.")

    fixed = dict(algorithm.fixed_parameters)
    configurations: list[AlgorithmConfiguration] = []
    if not ordered_names:
        return (
            AlgorithmConfiguration(
                algorithm=algorithm,
                parameters=fixed,
            ),
        )

    for values in itertools.product(*(tuple(grid[name]) for name in ordered_names)):
        parameters = dict(fixed)
        parameters.update(zip(ordered_names, values, strict=True))
        configurations.append(
            AlgorithmConfiguration(
                algorithm=algorithm,
                parameters=parameters,
            )
        )

    return tuple(configurations)

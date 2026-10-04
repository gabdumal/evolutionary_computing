from __future__ import annotations

from collections.abc import Mapping

import numpy as np


def evaluate_objective(
    name: str,
    x: np.ndarray,
    parameters: Mapping[str, int | float | str | bool | None] | None = None,
) -> float:
    parameters = parameters or {}
    values = np.asarray(x, dtype=np.float64)
    dimension = values.size

    match name.lower():
        case "sphere":
            return float(np.sum(values**2))
        case "rosenbrock":
            return float(
                np.sum(
                    100.0 * (values[1:] - values[:-1] ** 2) ** 2
                    + (1.0 - values[:-1]) ** 2
                )
            )
        case "schwefel":
            return float(
                418.9829 * dimension
                - np.sum(values * np.sin(np.sqrt(np.abs(values))))
            )
        case "happycat":
            alpha = float(parameters.get("alpha", 0.25))
            squared_norm = float(np.sum(values**2))
            return float(
                np.abs(squared_norm - dimension) ** alpha
                + (0.5 * squared_norm + np.sum(values)) / dimension
                + 0.5
            )
        case _:
            raise KeyError(f"Unknown benchmark objective: {name!r}.")

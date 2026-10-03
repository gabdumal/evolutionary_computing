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

def evaluate_objective_batch(
    name: str,
    points: np.ndarray,
    parameters: Mapping[str, int | float | str | bool | None] | None = None,
) -> np.ndarray:
    """Evaluate a benchmark at many points without Python-level per-point dispatch.

    The first axis enumerates objective evaluations. Each row is one point and is
    counted as one function evaluation by the experiment runner.
    """
    parameters = parameters or {}
    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError("points must be a 2-D array with one point per row.")
    dimension = values.shape[1]

    match name.lower():
        case "sphere":
            return np.sum(values**2, axis=1)
        case "rosenbrock":
            if dimension < 2:
                raise ValueError("Rosenbrock requires dimension >= 2.")
            return np.sum(
                100.0 * (values[:, 1:] - values[:, :-1] ** 2) ** 2
                + (1.0 - values[:, :-1]) ** 2,
                axis=1,
            )
        case "schwefel":
            return 418.9829 * dimension - np.sum(
                values * np.sin(np.sqrt(np.abs(values))), axis=1
            )
        case "happycat":
            alpha = float(parameters.get("alpha", 0.25))
            squared_norm = np.sum(values**2, axis=1)
            return (
                np.abs(squared_norm - dimension) ** alpha
                + (0.5 * squared_norm + np.sum(values, axis=1)) / dimension
                + 0.5
            )
        case _:
            raise KeyError(f"Unknown benchmark objective: {name!r}.")


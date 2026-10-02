# pyright: reportMissingTypeStubs=false
from __future__ import annotations

"""Interactive visualization API for NiaPy optimization algorithms.

The module keeps NiaPy at a narrow integration boundary. NiaPy itself owns the
optimization algorithm and objective evaluation; this module records the
standard callback state and turns it into Plotly figures.

NiaPy does not provide PEP 561 typing metadata, so the public ``algorithm`` and
``problem`` parameters intentionally accept ``object`` at the integration
boundary. Runtime validation establishes the required NiaPy contract. The
visualizer's own data structures and plotting API remain explicitly typed.

The public API is intentionally small:

- :func:`run_niapy` records one optimization run.
- :func:`plot_optimization_history` visualizes a recorded run.
- :func:`plot_convergence` plots best-so-far convergence.
- :func:`visualize_niapy` runs and visualizes in one call.
- :func:`write_html` exports a Plotly figure.

NiaPy does not currently provide the type-stub metadata expected by Pylance.
The file-level ``reportMissingTypeStubs`` suppression is therefore limited to
this adapter module. No NiaPy types are reimplemented here; only the small
contracts actually required by the visualizer are defined.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, TypeAlias, cast

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go
from niapy.callbacks import Callback
from niapy.task import OptimizationType, Task

__all__ = [
    "OptimizationHistory",
    "VisualizationResult",
    "plot_1d_optimization",
    "plot_3d_optimization",
    "plot_convergence",
    "plot_optimization_history",
    "run_niapy",
    "visualize_niapy",
    "write_html",
]


FloatArray: TypeAlias = npt.NDArray[np.float64]
IntArray: TypeAlias = npt.NDArray[np.int64]
OptimizationName: TypeAlias = Literal["min", "max"]


class ObjectiveProblem(Protocol):
    """Minimal objective interface needed by the visualization layer."""

    dimension: int
    lower: FloatArray
    upper: FloatArray

    def evaluate(self, x: FloatArray) -> float:
        """Evaluate one candidate solution."""
        ...


class NiaPyTask(Protocol):
    """Minimal task view needed after NiaPy creates the optimization task."""

    dimension: int
    evals: int
    lower: FloatArray
    upper: FloatArray
    problem: ObjectiveProblem
    optimization_type: OptimizationType


ProblemInput: TypeAlias = object
AlgorithmInput: TypeAlias = object
Array2DInput: TypeAlias = Sequence[Sequence[float]] | FloatArray
VectorInput: TypeAlias = Sequence[float] | FloatArray


@dataclass(frozen=True, slots=True)
class OptimizationHistory:
    """Recorded trajectory of one NiaPy optimization run."""

    algorithm_name: str
    problem_name: str
    dimension: int
    optimization: OptimizationName

    positions: tuple[FloatArray, ...]
    objective_values: tuple[FloatArray, ...]
    best_positions: tuple[FloatArray, ...]
    best_values: FloatArray

    evaluations: IntArray
    iterations: IntArray

    final_solution: FloatArray
    final_value: float

    lower_bounds: FloatArray
    upper_bounds: FloatArray

    problem: ObjectiveProblem


@dataclass(frozen=True, slots=True)
class VisualizationResult:
    """Optimization history and the generated Plotly figures."""

    history: OptimizationHistory
    optimization_figure: go.Figure
    convergence_figure: go.Figure


class _TrajectoryRecorderMixin:
    """State recorder mixed into a real NiaPy Callback at runtime."""

    def __init__(
        self,
        task: NiaPyTask,
        optimization: OptimizationName,
    ) -> None:
        self._task = task
        self._optimization = optimization
        self._sign = 1.0 if optimization == "min" else -1.0

        self.positions: list[FloatArray] = []
        self.objective_values: list[FloatArray] = []
        self.best_positions: list[FloatArray] = []
        self.best_values: list[float] = []
        self.evaluations: list[int] = []
        self.iterations: list[int] = []

    def before_iteration(
        self,
        population: object,
        fitness: object,
        best_x: object,
        best_fitness: object,
        **params: object,
    ) -> None:
        """Record the initial population exactly once."""
        del params
        if not self.positions:
            self._record(population, fitness, best_x, best_fitness)

    def after_iteration(
        self,
        population: object,
        fitness: object,
        best_x: object,
        best_fitness: object,
        **params: object,
    ) -> None:
        """Record the population produced by the completed iteration."""
        del params
        self._record(population, fitness, best_x, best_fitness)

    def _record(
        self,
        population: object,
        fitness: object,
        best_x: object,
        best_fitness: object,
    ) -> None:
        positions = _population_to_matrix(
            population,
            self._task.dimension,
        )
        objective_values = _fitness_to_objective_values(
            fitness,
            self._sign,
            expected_size=len(positions),
        )
        best_position = _solution_to_vector(
            best_x,
            self._task.dimension,
        )
        best_value = float(np.float64(cast(float, best_fitness))) * self._sign

        self.positions.append(positions.copy())
        self.objective_values.append(objective_values.copy())
        self.best_positions.append(best_position.copy())
        self.best_values.append(best_value)
        self.evaluations.append(int(self._task.evals))
        self.iterations.append(len(self.iterations))


class _TrajectoryRecorder(_TrajectoryRecorderMixin, Callback):
    """Concrete NiaPy callback used by the recorder."""

    def __init__(
        self,
        task: NiaPyTask,
        optimization: OptimizationName,
    ) -> None:
        Callback.__init__(self)
        _TrajectoryRecorderMixin.__init__(self, task, optimization)


def _create_recorder(
    task: NiaPyTask,
    optimization: OptimizationName,
) -> _TrajectoryRecorder:
    """Create the visualization callback accepted by NiaPy."""
    return _TrajectoryRecorder(task, optimization)


def _coerce_optimization_name(
    optimization_type: OptimizationName | OptimizationType,
) -> OptimizationName:
    """Normalize a convenient string or NiaPy enum to ``min``/``max``."""
    if isinstance(optimization_type, str):
        if optimization_type == "min":
            return "min"
        if optimization_type == "max":
            return "max"
        raise ValueError(
            "optimization_type must be 'min', 'max', or a NiaPy OptimizationType value."
        )

    if optimization_type is OptimizationType.MINIMIZATION:
        return "min"
    if optimization_type is OptimizationType.MAXIMIZATION:
        return "max"

    raise ValueError(f"Unsupported optimization_type: {optimization_type!r}")


def _resolve_algorithm(algorithm: AlgorithmInput) -> Any:
    """Normalize a NiaPy algorithm instance or a zero-argument factory."""
    if hasattr(algorithm, "run") and hasattr(algorithm, "callbacks"):
        return algorithm

    if callable(algorithm):
        candidate = algorithm()
        if hasattr(candidate, "run") and hasattr(candidate, "callbacks"):
            return candidate

    raise TypeError(
        "algorithm must be a NiaPy algorithm instance or a zero-argument "
        "factory returning one."
    )


def _algorithm_name(algorithm: Any) -> str:
    """Get a readable algorithm name without depending on NiaPy internals."""
    raw_name = getattr(algorithm, "Name", None)

    if (
        isinstance(raw_name, Sequence)
        and not isinstance(raw_name, (str, bytes))
        and raw_name
    ):
        return str(raw_name[0])

    return type(algorithm).__name__


def _solution_to_vector(solution: object, dimension: int) -> FloatArray:
    """Normalize a NiaPy solution or Individual to one numeric vector."""
    raw_solution = getattr(solution, "x", solution)
    vector = np.asarray(raw_solution, dtype=np.float64).reshape(-1)

    if vector.size != dimension:
        raise ValueError(
            f"Expected a solution with {dimension} coordinates; received {vector.size}."
        )

    return vector


def _population_to_matrix(population: object, dimension: int) -> FloatArray:
    """Normalize common NiaPy population representations."""
    array = np.asarray(population)

    if array.ndim == 0:
        raise ValueError("NiaPy returned a scalar population.")

    if array.ndim == 2 and array.dtype != np.dtype(object):
        matrix = np.asarray(array, dtype=np.float64)
        if matrix.shape[1] != dimension:
            raise ValueError(
                f"Expected population dimension {dimension}; "
                f"received {matrix.shape[1]}."
            )
        return matrix

    if array.ndim == 1 and array.dtype != np.dtype(object):
        return _solution_to_vector(array, dimension).reshape(1, dimension)

    rows = [_solution_to_vector(item, dimension) for item in array.tolist()]

    if not rows:
        return np.empty((0, dimension), dtype=np.float64)

    return np.stack(rows, axis=0).astype(np.float64, copy=False)


def _fitness_to_objective_values(
    fitness: object,
    sign: float,
    *,
    expected_size: int,
) -> FloatArray:
    """Convert NiaPy internal fitness back to the original objective values."""
    values = np.asarray(fitness, dtype=np.float64).reshape(-1)

    if values.size == 1 and expected_size > 1:
        values = np.repeat(values, expected_size)

    if values.size != expected_size:
        raise ValueError(
            "Population and fitness sizes returned by NiaPy do not match: "
            f"{expected_size} positions vs {values.size} fitness values."
        )

    return np.asarray(values * sign, dtype=np.float64)


def _task_factory(
    problem: ProblemInput,
    *,
    dimension: int | None,
    max_evals: float,
    max_iters: float,
    optimization: OptimizationName,
    repair_function: object | None,
    cutoff_value: float | None,
    enable_logging: bool,
) -> NiaPyTask:
    """Construct the NiaPy Task while containing third-party types."""
    optimization_type = (
        OptimizationType.MINIMIZATION
        if optimization == "min"
        else OptimizationType.MAXIMIZATION
    )

    kwargs: dict[str, Any] = {
        "problem": problem,
        "dimension": dimension,
        "max_evals": max_evals,
        "max_iters": max_iters,
        "optimization_type": optimization_type,
        "enable_logging": enable_logging,
    }

    if repair_function is not None:
        kwargs["repair_function"] = repair_function
    if cutoff_value is not None:
        kwargs["cutoff_value"] = cutoff_value

    return cast(NiaPyTask, Task(**kwargs))


def run_niapy(
    algorithm: AlgorithmInput,
    problem: ProblemInput,
    *,
    dimension: int | None = None,
    max_evals: float = np.inf,
    max_iters: float = np.inf,
    optimization_type: OptimizationName | OptimizationType = "min",
    repair_function: object | None = None,
    cutoff_value: float | None = None,
    enable_logging: bool = False,
) -> OptimizationHistory:
    """Run any standard-interface NiaPy algorithm and record its trajectory.

    ``algorithm`` may be an already-configured NiaPy algorithm or a factory
    returning one. ``problem`` may be a NiaPy problem name or a concrete NiaPy
    problem instance.

    At least one of ``max_evals`` and ``max_iters`` must be finite.
    """
    if not np.isfinite(max_evals) and not np.isfinite(max_iters):
        raise ValueError(
            "At least one stopping limit must be finite: max_evals or max_iters."
        )

    resolved_algorithm = _resolve_algorithm(algorithm)
    resolved_optimization = _coerce_optimization_name(optimization_type)
    task = _task_factory(
        problem,
        dimension=dimension,
        max_evals=max_evals,
        max_iters=max_iters,
        optimization=resolved_optimization,
        repair_function=repair_function,
        cutoff_value=cutoff_value,
        enable_logging=enable_logging,
    )

    callback_container: Any = resolved_algorithm.callbacks
    original_callbacks = list(callback_container.callbacks)
    recorder = _create_recorder(task, resolved_optimization)

    callback_container.append(recorder)

    try:
        final_solution, final_value = resolved_algorithm.run(task)
    finally:
        # Restore the user's callback configuration even if NiaPy raises.
        callback_container.callbacks[:] = original_callbacks
        callback_container.set_algorithm(resolved_algorithm)

    if resolved_algorithm.bad_run():
        raise RuntimeError(
            f"NiaPy reported an error while running "
            f"{type(resolved_algorithm).__name__}."
        )

    if final_solution is None or final_value is None:
        raise RuntimeError("NiaPy did not return a valid optimization result.")

    if not recorder.positions:
        raise RuntimeError(
            "NiaPy terminated before its first iteration; "
            "no trajectory frame was available."
        )

    problem_object = cast(ObjectiveProblem, task.problem)
    raw_problem_name = getattr(problem_object, "name", None)
    problem_name = (
        str(raw_problem_name())
        if callable(raw_problem_name)
        else type(problem_object).__name__
    )
    final_vector = _solution_to_vector(final_solution, task.dimension)
    final_objective_value = float(final_value)

    lower_bounds = np.asarray(task.lower, dtype=np.float64).reshape(-1)
    upper_bounds = np.asarray(task.upper, dtype=np.float64).reshape(-1)

    return OptimizationHistory(
        algorithm_name=_algorithm_name(resolved_algorithm),
        problem_name=problem_name,
        dimension=int(task.dimension),
        optimization=resolved_optimization,
        positions=tuple(recorder.positions),
        objective_values=tuple(recorder.objective_values),
        best_positions=tuple(recorder.best_positions),
        best_values=np.asarray(recorder.best_values, dtype=np.float64),
        evaluations=np.asarray(recorder.evaluations, dtype=np.int64),
        iterations=np.asarray(recorder.iterations, dtype=np.int64),
        final_solution=final_vector.copy(),
        final_value=final_objective_value,
        lower_bounds=lower_bounds.copy(),
        upper_bounds=upper_bounds.copy(),
        problem=problem_object,
    )


def _frame_indices(
    frame_count: int,
    frame_stride: int | Literal["auto"],
    max_frames: int,
) -> IntArray:
    """Choose frame indices without dropping the initial or final state."""
    if frame_count <= 0:
        raise ValueError("The optimization history contains no frames.")
    if max_frames < 2:
        raise ValueError("max_frames must be at least 2.")

    if frame_stride == "auto":
        stride = max(
            1,
            int(np.ceil((frame_count - 1) / (max_frames - 1))),
        )
    elif frame_stride >= 1:
        stride = frame_stride
    else:
        raise ValueError("frame_stride must be a positive integer or 'auto'.")

    indices = list(range(0, frame_count, stride))
    if indices[-1] != frame_count - 1:
        indices.append(frame_count - 1)

    return np.asarray(indices, dtype=np.int64)


def _objective_grid(
    history: OptimizationHistory,
    *,
    x_dimension: int,
    y_dimension: int,
    resolution: int,
    anchor: VectorInput | None,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Build the 2D objective slice used by the 3D visualization."""
    if history.dimension < 2:
        raise ValueError("A 3D visualization requires at least two variables.")
    if x_dimension == y_dimension:
        raise ValueError("x_dimension and y_dimension must be different.")
    if not 0 <= x_dimension < history.dimension:
        raise IndexError("x_dimension is outside the problem dimension.")
    if not 0 <= y_dimension < history.dimension:
        raise IndexError("y_dimension is outside the problem dimension.")
    if resolution < 10:
        raise ValueError("surface_resolution must be at least 10.")
    if not np.all(np.isfinite(history.lower_bounds)) or not np.all(
        np.isfinite(history.upper_bounds)
    ):
        raise ValueError("Finite bounds are required for a 3D surface.")

    if anchor is None:
        base = history.best_positions[-1].copy()
    else:
        base = _solution_to_vector(anchor, history.dimension)

    x_values = np.linspace(
        history.lower_bounds[x_dimension],
        history.upper_bounds[x_dimension],
        resolution,
        dtype=np.float64,
    )
    y_values = np.linspace(
        history.lower_bounds[y_dimension],
        history.upper_bounds[y_dimension],
        resolution,
        dtype=np.float64,
    )

    X, Y = np.meshgrid(x_values, y_values)
    points = np.repeat(
        base[None, :],
        resolution * resolution,
        axis=0,
    )
    points[:, x_dimension] = X.reshape(-1)
    points[:, y_dimension] = Y.reshape(-1)

    values = [float(history.problem.evaluate(point)) for point in points]
    Z = np.asarray(values, dtype=np.float64).reshape(
        resolution,
        resolution,
    )

    return X, Y, Z


def _animation_title(
    history: OptimizationHistory,
    history_index: int,
) -> str:
    """Build a compact title for an animation frame."""
    return (
        f"{history.algorithm_name} — {history.problem_name}"
        f" | iteration {int(history.iterations[history_index])}"
        f" | best = {history.best_values[history_index]:.4e}"
    )


def plot_3d_optimization(
    history: OptimizationHistory,
    *,
    x_dimension: int = 0,
    y_dimension: int = 1,
    surface_resolution: int = 80,
    slice_anchor: VectorInput | None = None,
    frame_stride: int | Literal["auto"] = "auto",
    max_frames: int = 100,
    frame_duration_ms: int = 150,
    width: int = 1000,
    height: int = 760,
    reference_points: Array2DInput | None = None,
    reference_label: str = "Reference solutions",
) -> go.Figure:
    """Create an interactive 3D animation for a problem with D >= 2.

    For D=2 the surface is the exact objective landscape. For D>2 it is a
    two-dimensional slice, with undisplayed dimensions fixed at ``slice_anchor``
    or at the final best solution.
    """
    X, Y, Z = _objective_grid(
        history,
        x_dimension=x_dimension,
        y_dimension=y_dimension,
        resolution=surface_resolution,
        anchor=slice_anchor,
    )
    frame_ids = _frame_indices(
        len(history.positions),
        frame_stride,
        max_frames,
    )

    first_index = int(frame_ids[0])
    initial_points = history.positions[first_index]
    initial_values = history.objective_values[first_index]
    initial_best = history.best_positions[first_index]
    initial_best_value = history.best_values[first_index]

    data: list[Any] = [
        go.Surface(
            x=X,
            y=Y,
            z=Z,
            colorscale="Viridis",
            opacity=0.78,
            colorbar={
                "title": {"text": "Objective"},
                "len": 0.8,
            },
            name="Objective surface",
            hovertemplate=(
                "x=%{x:.3f}<br>y=%{y:.3f}<br>objective=%{z:.3e}<extra></extra>"
            ),
        ),
        go.Scatter3d(
            x=initial_points[:, x_dimension],
            y=initial_points[:, y_dimension],
            z=initial_values,
            mode="markers",
            name="Individuals",
            marker={"size": 7},
            hovertemplate=(
                "x=%{x:.4f}<br>y=%{y:.4f}<br>objective=%{z:.6e}<extra></extra>"
            ),
        ),
        go.Scatter3d(
            x=[initial_best[x_dimension]],
            y=[initial_best[y_dimension]],
            z=[initial_best_value],
            mode="markers",
            name="Best-so-far",
            marker={"size": 14, "symbol": "diamond"},
            hovertemplate=(
                "best x=%{x:.6f}<br>"
                "best y=%{y:.6f}<br>"
                "objective=%{z:.6e}<extra></extra>"
            ),
        ),
    ]

    if reference_points is not None:
        references = np.asarray(reference_points, dtype=np.float64)
        if references.ndim == 1:
            references = references.reshape(1, -1)
        if references.ndim != 2 or references.shape[1] != history.dimension:
            raise ValueError(
                f"reference_points must have shape (n_points, {history.dimension})."
            )

        reference_values = np.asarray(
            [float(history.problem.evaluate(point)) for point in references],
            dtype=np.float64,
        )

        data.append(
            go.Scatter3d(
                x=references[:, x_dimension],
                y=references[:, y_dimension],
                z=reference_values,
                mode="markers",
                name=reference_label,
                marker={"size": 10, "symbol": "x"},
                hovertemplate=(
                    "reference x=%{x:.6f}<br>"
                    "reference y=%{y:.6f}<br>"
                    "objective=%{z:.6e}<extra></extra>"
                ),
            )
        )

    frames: list[go.Frame] = []
    for frame_number, history_index_raw in enumerate(frame_ids):
        history_index = int(history_index_raw)
        points = history.positions[history_index]
        values = history.objective_values[history_index]
        best = history.best_positions[history_index]
        best_value = history.best_values[history_index]

        frames.append(
            go.Frame(
                name=str(frame_number),
                traces=[1, 2],
                data=[
                    go.Scatter3d(
                        x=points[:, x_dimension],
                        y=points[:, y_dimension],
                        z=values,
                        mode="markers",
                        name="Individuals",
                        marker={"size": 7},
                    ),
                    go.Scatter3d(
                        x=[best[x_dimension]],
                        y=[best[y_dimension]],
                        z=[best_value],
                        mode="markers",
                        name="Best-so-far",
                        marker={"size": 14, "symbol": "diamond"},
                    ),
                ],
                layout=go.Layout(title=_animation_title(history, history_index)),
            )
        )

    slider_steps: list[dict[str, object]] = [
        {
            "args": [
                [frame.name],
                {
                    "frame": {
                        "duration": frame_duration_ms,
                        "redraw": True,
                    },
                    "mode": "immediate",
                    "transition": {"duration": 0},
                },
            ],
            "label": str(history.iterations[int(history_index)]),
            "method": "animate",
        }
        for frame, history_index in zip(frames, frame_ids, strict=True)
    ]

    figure = go.Figure(data=data, frames=frames)
    figure.update_layout(
        title=_animation_title(history, first_index),
        width=width,
        height=height,
        margin={"l": 0, "r": 0, "t": 70, "b": 0},
        uirevision="keep-camera",
        scene={
            "xaxis_title": f"x[{x_dimension}]",
            "yaxis_title": f"x[{y_dimension}]",
            "zaxis_title": "Objective",
            "camera": {"eye": {"x": 1.55, "y": 1.55, "z": 1.10}},
        },
        updatemenus=[
            {
                "type": "buttons",
                "direction": "left",
                "x": 0.08,
                "y": 1.05,
                "showactive": False,
                "buttons": [
                    {
                        "label": "▶ Play",
                        "method": "animate",
                        "args": [
                            None,
                            {
                                "frame": {
                                    "duration": frame_duration_ms,
                                    "redraw": True,
                                },
                                "transition": {"duration": 0},
                                "fromcurrent": True,
                                "mode": "immediate",
                            },
                        ],
                    },
                    {
                        "label": "⏸ Pause",
                        "method": "animate",
                        "args": [
                            [None],
                            {
                                "frame": {
                                    "duration": 0,
                                    "redraw": False,
                                },
                                "mode": "immediate",
                            },
                        ],
                    },
                ],
            }
        ],
        sliders=[
            {
                "active": 0,
                "x": 0.08,
                "y": 0.02,
                "len": 0.84,
                "currentvalue": {
                    "prefix": "Iteration: ",
                    "font": {"size": 14},
                },
                "steps": slider_steps,
            }
        ],
    )

    return figure


def plot_1d_optimization(
    history: OptimizationHistory,
    *,
    width: int = 1000,
    height: int = 700,
    frame_stride: int | Literal["auto"] = "auto",
    max_frames: int = 100,
    frame_duration_ms: int = 150,
) -> go.Figure:
    """Create an animated objective plot for a one-dimensional problem."""
    if history.dimension != 1:
        raise ValueError("plot_1d_optimization requires dimension=1.")
    if not np.all(np.isfinite(history.lower_bounds)) or not np.all(
        np.isfinite(history.upper_bounds)
    ):
        raise ValueError("Finite bounds are required for a 1D plot.")

    x_values = np.linspace(
        history.lower_bounds[0],
        history.upper_bounds[0],
        800,
        dtype=np.float64,
    )
    objective_values = np.asarray(
        [
            float(history.problem.evaluate(np.asarray([x], dtype=np.float64)))
            for x in x_values
        ],
        dtype=np.float64,
    )

    frame_ids = _frame_indices(
        len(history.positions),
        frame_stride,
        max_frames,
    )
    first_index = int(frame_ids[0])

    figure = go.Figure(
        data=[
            go.Scatter(
                x=x_values,
                y=objective_values,
                mode="lines",
                name="Objective",
            ),
            go.Scatter(
                x=history.positions[first_index][:, 0],
                y=history.objective_values[first_index],
                mode="markers",
                name="Individuals",
                marker={"size": 9},
            ),
            go.Scatter(
                x=[history.best_positions[first_index][0]],
                y=[history.best_values[first_index]],
                mode="markers",
                name="Best-so-far",
                marker={"size": 14, "symbol": "diamond"},
            ),
        ]
    )

    frames: list[go.Frame] = []
    for frame_number, history_index_raw in enumerate(frame_ids):
        history_index = int(history_index_raw)
        frames.append(
            go.Frame(
                name=str(frame_number),
                traces=[1, 2],
                data=[
                    go.Scatter(
                        x=history.positions[history_index][:, 0],
                        y=history.objective_values[history_index],
                        mode="markers",
                        name="Individuals",
                        marker={"size": 9},
                    ),
                    go.Scatter(
                        x=[history.best_positions[history_index][0]],
                        y=[history.best_values[history_index]],
                        mode="markers",
                        name="Best-so-far",
                        marker={"size": 14, "symbol": "diamond"},
                    ),
                ],
                layout=go.Layout(title=_animation_title(history, history_index)),
            )
        )

    figure.frames = frames
    figure.update_layout(
        title=_animation_title(history, first_index),
        width=width,
        height=height,
        margin={"l": 60, "r": 30, "t": 70, "b": 60},
        xaxis_title="x[0]",
        yaxis_title="Objective",
        updatemenus=[
            {
                "type": "buttons",
                "direction": "left",
                "x": 0.08,
                "y": 1.05,
                "showactive": False,
                "buttons": [
                    {
                        "label": "▶ Play",
                        "method": "animate",
                        "args": [
                            None,
                            {
                                "frame": {
                                    "duration": frame_duration_ms,
                                    "redraw": True,
                                },
                                "transition": {"duration": 0},
                                "fromcurrent": True,
                                "mode": "immediate",
                            },
                        ],
                    },
                    {
                        "label": "⏸ Pause",
                        "method": "animate",
                        "args": [
                            [None],
                            {
                                "frame": {"duration": 0, "redraw": False},
                                "mode": "immediate",
                            },
                        ],
                    },
                ],
            }
        ],
        sliders=[
            {
                "active": 0,
                "x": 0.08,
                "y": 0.02,
                "len": 0.84,
                "currentvalue": {
                    "prefix": "Iteration: ",
                    "font": {"size": 14},
                },
                "steps": [
                    {
                        "args": [
                            [frame.name],
                            {
                                "frame": {
                                    "duration": frame_duration_ms,
                                    "redraw": True,
                                },
                                "mode": "immediate",
                                "transition": {"duration": 0},
                            },
                        ],
                        "label": str(history.iterations[int(history_index)]),
                        "method": "animate",
                    }
                    for frame, history_index in zip(
                        frames,
                        frame_ids,
                        strict=True,
                    )
                ],
            }
        ],
    )

    return figure


def plot_convergence(
    history: OptimizationHistory,
    *,
    width: int = 1000,
    height: int = 500,
    log_y: bool | Literal["auto"] = "auto",
) -> go.Figure:
    """Plot best-so-far objective value against iteration."""
    values = history.best_values

    use_log = (
        bool(np.all(np.isfinite(values)) and np.all(values > 0))
        if log_y == "auto"
        else log_y
    )

    figure = go.Figure(
        data=[
            go.Scatter(
                x=history.iterations,
                y=values,
                mode="lines+markers",
                name="Best-so-far",
                hovertemplate=("iteration=%{x}<br>best=%{y:.6e}<extra></extra>"),
            )
        ]
    )
    figure.update_layout(
        title=(f"Convergence — {history.algorithm_name} on {history.problem_name}"),
        width=width,
        height=height,
        xaxis_title="Iteration",
        yaxis_title="Best objective value",
        margin={"l": 70, "r": 30, "t": 60, "b": 60},
    )

    if use_log:
        figure.update_yaxes(type="log")

    return figure


def plot_optimization_history(
    history: OptimizationHistory,
    *,
    mode: Literal["auto", "1d", "3d"] = "auto",
    **kwargs: Any,
) -> go.Figure:
    """Visualize an existing optimization history."""
    resolved_mode = mode
    if resolved_mode == "auto":
        resolved_mode = "1d" if history.dimension == 1 else "3d"

    if resolved_mode == "1d":
        return plot_1d_optimization(history, **kwargs)
    if resolved_mode == "3d":
        return plot_3d_optimization(history, **kwargs)

    raise ValueError("mode must be 'auto', '1d', or '3d'.")


def visualize_niapy(
    algorithm: AlgorithmInput,
    problem: ProblemInput,
    *,
    dimension: int | None = None,
    max_evals: float = np.inf,
    max_iters: float = np.inf,
    optimization_type: OptimizationName | OptimizationType = "min",
    repair_function: object | None = None,
    cutoff_value: float | None = None,
    enable_logging: bool = False,
    mode: Literal["auto", "1d", "3d"] = "auto",
    x_dimension: int = 0,
    y_dimension: int = 1,
    surface_resolution: int = 80,
    slice_anchor: VectorInput | None = None,
    frame_stride: int | Literal["auto"] = "auto",
    max_frames: int = 100,
    frame_duration_ms: int = 150,
    reference_points: Array2DInput | None = None,
    reference_label: str = "Reference solutions",
    figure_width: int = 1000,
    figure_height: int = 760,
) -> VisualizationResult:
    """Run a NiaPy optimization and build its figures."""
    history = run_niapy(
        algorithm,
        problem,
        dimension=dimension,
        max_evals=max_evals,
        max_iters=max_iters,
        optimization_type=optimization_type,
        repair_function=repair_function,
        cutoff_value=cutoff_value,
        enable_logging=enable_logging,
    )

    if mode == "1d" or (mode == "auto" and history.dimension == 1):
        optimization_figure = plot_1d_optimization(
            history,
            width=figure_width,
            height=figure_height,
            frame_stride=frame_stride,
            max_frames=max_frames,
            frame_duration_ms=frame_duration_ms,
        )
    else:
        optimization_figure = plot_3d_optimization(
            history,
            x_dimension=x_dimension,
            y_dimension=y_dimension,
            surface_resolution=surface_resolution,
            slice_anchor=slice_anchor,
            frame_stride=frame_stride,
            max_frames=max_frames,
            frame_duration_ms=frame_duration_ms,
            width=figure_width,
            height=figure_height,
            reference_points=reference_points,
            reference_label=reference_label,
        )

    convergence_figure = plot_convergence(history)

    return VisualizationResult(
        history=history,
        optimization_figure=optimization_figure,
        convergence_figure=convergence_figure,
    )


def write_html(
    figure: go.Figure,
    path: str | Path,
    *,
    include_plotlyjs: bool | Literal["cdn", "directory"] = "cdn",
) -> None:
    """Write a Plotly figure to an HTML file."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(
        output_path,
        include_plotlyjs=include_plotlyjs,
        auto_open=False,
    )

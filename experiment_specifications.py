from __future__ import annotations

"""Immutable, deterministic specifications for optimization experiments.

This module defines the experiment contract only. It does not execute
NiaPy, perform parallelism, persist results, or run statistical analyses.

NiaPy is represented by import paths rather than imported classes. This
keeps this layer independent of NiaPy's missing type metadata and makes
specifications straightforward to record in experiment artifacts.
"""

import json
import math
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Final, Literal, TypeAlias

SEEDS: Final[tuple[int, ...]] = (
    27,
    32,
    59,
    74,
    93,
)

SEED: Final[int] = SEEDS[0]

SCHEMA_VERSION: Final[int] = 1

OptimizationDirection: TypeAlias = Literal["minimize", "maximize"]

ParameterValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | list["ParameterValue"]
    | dict[str, "ParameterValue"]
)

ParameterSet: TypeAlias = Mapping[str, ParameterValue]

_IMPORT_PATH_PATTERN = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")


def _validate_non_empty_name(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")


def _validate_import_path(import_path: str) -> None:
    if not _IMPORT_PATH_PATTERN.fullmatch(import_path):
        raise ValueError(
            "import_path must be a dotted Python import path such as "
            "'niapy.algorithms.basic.ParticleSwarmOptimization'."
        )

    if "<locals>" in import_path:
        raise ValueError("import_path must refer to an importable top-level object.")


def _validate_parameter_name(name: str) -> None:
    if not name.isidentifier():
        raise ValueError(
            f"Invalid parameter name {name!r}; expected a Python identifier."
        )


def _validate_serializable_value(value: ParameterValue) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Parameter values must be JSON-serializable and must not "
            "contain non-finite floating-point values."
        ) from exc


def _normalize_parameters(
    parameters: ParameterSet,
) -> dict[str, ParameterValue]:
    normalized = deepcopy(dict(parameters))

    for name, value in normalized.items():
        _validate_parameter_name(name)
        _validate_serializable_value(value)

    return normalized


def _stable_identifier(payload: object, prefix: str) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = sha256(serialized.encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


@dataclass(frozen=True, slots=True)
class AlgorithmSpecification:
    """Reference and fixed constructor parameters for an algorithm."""

    import_path: str
    parameters: ParameterSet = field(default_factory=dict)
    name: str | None = None

    def __post_init__(self) -> None:
        _validate_import_path(self.import_path)

        normalized_parameters = _normalize_parameters(self.parameters)
        object.__setattr__(self, "parameters", normalized_parameters)

        if self.name is not None:
            _validate_non_empty_name(self.name, "name")

    @classmethod
    def from_callable(
        cls,
        factory: Callable[..., object],
        *,
        parameters: ParameterSet | None = None,
        name: str | None = None,
    ) -> AlgorithmSpecification:
        """Build a specification from an importable class or factory."""
        module = getattr(factory, "__module__", None)
        qualified_name = getattr(factory, "__qualname__", None)

        if not isinstance(module, str) or not isinstance(
            qualified_name,
            str,
        ):
            raise TypeError("factory must expose __module__ and __qualname__.")

        import_path = f"{module}.{qualified_name}"
        _validate_import_path(import_path)

        return cls(
            import_path=import_path,
            parameters={} if parameters is None else parameters,
            name=name,
        )

    @property
    def display_name(self) -> str:
        """Return the configured or inferred display name."""
        if self.name is not None:
            return self.name

        return self.import_path.rsplit(".", maxsplit=1)[-1]

    def identity(self) -> dict[str, object]:
        """Return the canonical algorithm definition."""
        return {
            "import_path": self.import_path,
            "name": self.display_name,
            "parameters": self.parameters,
        }


@dataclass(frozen=True, slots=True)
class ProblemSpecification:
    """Definition of an objective-function family and its dimensions."""

    name: str
    dimensions: tuple[int, ...]
    import_path: str | None = None
    parameters: ParameterSet = field(default_factory=dict)
    optimization: OptimizationDirection = "minimize"

    def __post_init__(self) -> None:
        _validate_non_empty_name(self.name, "name")

        normalized_dimensions = tuple(self.dimensions)

        if not normalized_dimensions:
            raise ValueError("dimensions must contain at least one value.")

        if any(
            not isinstance(dimension, int) or isinstance(dimension, bool)
            for dimension in normalized_dimensions
        ):
            raise TypeError("Every dimension must be an integer.")

        if any(dimension <= 0 for dimension in normalized_dimensions):
            raise ValueError("Every dimension must be greater than zero.")

        if len(set(normalized_dimensions)) != len(normalized_dimensions):
            raise ValueError("dimensions must not contain duplicates.")

        object.__setattr__(
            self,
            "dimensions",
            normalized_dimensions,
        )

        normalized_parameters = _normalize_parameters(self.parameters)
        object.__setattr__(
            self,
            "parameters",
            normalized_parameters,
        )

        if self.import_path is None and normalized_parameters:
            raise ValueError(
                "parameters require import_path to identify a custom "
                "problem constructor."
            )

        if self.import_path is not None:
            _validate_import_path(self.import_path)

        if self.optimization not in {"minimize", "maximize"}:
            raise ValueError("optimization must be 'minimize' or 'maximize'.")

    def identity(self) -> dict[str, object]:
        """Return the canonical problem definition."""
        return {
            "name": self.name,
            "dimensions": self.dimensions,
            "import_path": self.import_path,
            "parameters": self.parameters,
            "optimization": self.optimization,
        }


@dataclass(frozen=True, slots=True)
class TerminationSpecification:
    """Stopping criteria shared by every run in an experiment."""

    max_evaluations: int | None = None
    max_iterations: int | None = None
    cutoff_value: float | None = None
    enable_logging: bool = False

    def __post_init__(self) -> None:
        if self.max_evaluations is None and self.max_iterations is None:
            raise ValueError(
                "At least one stopping limit must be specified: "
                "max_evaluations or max_iterations."
            )

        if self.max_evaluations is not None:
            if not isinstance(self.max_evaluations, int) or isinstance(
                self.max_evaluations, bool
            ):
                raise TypeError("max_evaluations must be an integer or None.")

            if self.max_evaluations <= 0:
                raise ValueError("max_evaluations must be greater than zero.")

        if self.max_iterations is not None:
            if not isinstance(self.max_iterations, int) or isinstance(
                self.max_iterations, bool
            ):
                raise TypeError("max_iterations must be an integer or None.")

            if self.max_iterations <= 0:
                raise ValueError("max_iterations must be greater than zero.")

        if self.cutoff_value is not None:
            if isinstance(self.cutoff_value, bool):
                raise TypeError("cutoff_value must be a real number or None.")

            try:
                cutoff_value = float(self.cutoff_value)
            except (TypeError, ValueError) as exc:
                raise TypeError("cutoff_value must be a real number or None.") from exc

            if not math.isfinite(cutoff_value):
                raise ValueError("cutoff_value must be finite when provided.")

            object.__setattr__(
                self,
                "cutoff_value",
                cutoff_value,
            )

    def identity(self) -> dict[str, object]:
        """Return the canonical termination definition."""
        return {
            "max_evaluations": self.max_evaluations,
            "max_iterations": self.max_iterations,
            "cutoff_value": self.cutoff_value,
            "enable_logging": self.enable_logging,
        }


@dataclass(frozen=True, slots=True)
class SeedSpecification:
    """Deterministic seed selection for repeated stochastic runs."""

    seeds: tuple[int, ...] = SEEDS
    replications: int = 1

    def __post_init__(self) -> None:
        normalized_seeds = tuple(self.seeds)

        if not normalized_seeds:
            raise ValueError("seeds must contain at least one seed.")

        if any(
            not isinstance(seed, int) or isinstance(seed, bool)
            for seed in normalized_seeds
        ):
            raise TypeError("Every seed must be an integer.")

        if len(set(normalized_seeds)) != len(normalized_seeds):
            raise ValueError("seeds must not contain duplicates.")

        if not isinstance(self.replications, int) or isinstance(
            self.replications, bool
        ):
            raise TypeError("replications must be an integer.")

        if not 1 <= self.replications <= len(normalized_seeds):
            raise ValueError("replications must be between 1 and the number of seeds.")

        object.__setattr__(self, "seeds", normalized_seeds)

    @property
    def selected_seeds(self) -> tuple[int, ...]:
        """Return the first N configured seeds according to replications."""
        return self.seeds[: self.replications]

    def identity(self) -> dict[str, object]:
        """Return the canonical seed policy."""
        return {
            "seeds": self.seeds,
            "replications": self.replications,
        }


@dataclass(frozen=True, slots=True)
class AlgorithmConfiguration:
    """One fully resolved algorithm configuration."""

    algorithm: AlgorithmSpecification
    parameters: ParameterSet

    def __post_init__(self) -> None:
        normalized_parameters = _normalize_parameters(self.parameters)
        object.__setattr__(
            self,
            "parameters",
            normalized_parameters,
        )

    @property
    def name(self) -> str:
        """Return the algorithm's display name."""
        return self.algorithm.display_name

    @property
    def configuration_id(self) -> str:
        """Return a stable identifier for this configuration."""
        return _stable_identifier(
            {
                "schema_version": SCHEMA_VERSION,
                "algorithm": self.algorithm.identity(),
                "parameters": self.parameters,
            },
            "configuration",
        )

    def identity(self) -> dict[str, object]:
        """Return the canonical configuration definition."""
        return {
            "algorithm": self.algorithm.identity(),
            "parameters": self.parameters,
        }


@dataclass(frozen=True, slots=True)
class ExperimentRunSpecification:
    """One concrete execution: configuration × problem × dimension × seed."""

    experiment_id: str
    configuration: AlgorithmConfiguration
    problem: ProblemSpecification
    dimension: int
    seed: int
    termination: TerminationSpecification

    def __post_init__(self) -> None:
        _validate_non_empty_name(self.experiment_id, "experiment_id")

        if not isinstance(self.dimension, int) or isinstance(
            self.dimension,
            bool,
        ):
            raise TypeError("dimension must be an integer.")

        if self.dimension not in self.problem.dimensions:
            raise ValueError(
                "dimension must be one of the dimensions declared by the problem."
            )

        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise TypeError("seed must be an integer.")

    @property
    def configuration_id(self) -> str:
        """Return the configuration identifier."""
        return self.configuration.configuration_id

    @property
    def run_id(self) -> str:
        """Return a stable identifier for this concrete run."""
        return _stable_identifier(
            {
                "schema_version": SCHEMA_VERSION,
                "experiment_id": self.experiment_id,
                "configuration_id": self.configuration_id,
                "problem": self.problem.identity(),
                "dimension": self.dimension,
                "seed": self.seed,
                "termination": self.termination.identity(),
            },
            "run",
        )


@dataclass(frozen=True, slots=True)
class ExperimentSpecification:
    """Complete deterministic definition of an experiment campaign."""

    name: str
    algorithm: AlgorithmSpecification
    problems: tuple[ProblemSpecification, ...]
    parameter_grid: Mapping[str, Sequence[ParameterValue]] = field(default_factory=dict)
    seeds: SeedSpecification = field(default_factory=SeedSpecification)
    termination: TerminationSpecification = field(
        default_factory=lambda: TerminationSpecification(
            max_evaluations=10_000,
        )
    )
    description: str | None = None

    def __post_init__(self) -> None:
        _validate_non_empty_name(self.name, "name")

        normalized_problems = tuple(self.problems)

        if not normalized_problems:
            raise ValueError(
                "problems must contain at least one problem specification."
            )

        problem_keys = [
            (
                problem.name,
                problem.import_path,
                problem.parameters,
                problem.dimensions,
                problem.optimization,
            )
            for problem in normalized_problems
        ]

        problem_identity_strings = [
            json.dumps(
                key,
                sort_keys=True,
                allow_nan=False,
                separators=(",", ":"),
            )
            for key in problem_keys
        ]

        if len(set(problem_identity_strings)) != len(problem_identity_strings):
            raise ValueError("problems must not contain duplicate specifications.")

        object.__setattr__(
            self,
            "problems",
            normalized_problems,
        )

        normalized_grid: dict[str, tuple[ParameterValue, ...]] = {}

        for parameter_name, values in self.parameter_grid.items():
            _validate_parameter_name(parameter_name)

            if isinstance(values, (str, bytes, bytearray)):
                raise TypeError(
                    f"Parameter grid for {parameter_name!r} must be a "
                    "sequence of candidate values, not a string."
                )

            normalized_values = tuple(deepcopy(list(values)))

            if not normalized_values:
                raise ValueError(
                    f"Parameter grid for {parameter_name!r} must contain "
                    "at least one value."
                )

            serialized_values = [
                json.dumps(
                    value,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                for value in normalized_values
            ]

            if len(set(serialized_values)) != len(serialized_values):
                raise ValueError(
                    f"Parameter grid for {parameter_name!r} contains duplicate values."
                )

            for value in normalized_values:
                _validate_serializable_value(value)

            normalized_grid[parameter_name] = normalized_values

        fixed_parameter_names = set(self.algorithm.parameters)
        grid_parameter_names = set(normalized_grid)
        collision_names = fixed_parameter_names & grid_parameter_names

        if collision_names:
            collisions = ", ".join(sorted(collision_names))
            raise ValueError(
                "A parameter cannot be both fixed and part of the "
                f"parameter grid: {collisions}."
            )

        object.__setattr__(
            self,
            "parameter_grid",
            dict(sorted(normalized_grid.items())),
        )

        if self.description is not None and not self.description.strip():
            raise ValueError("description must contain text when provided.")

    @property
    def experiment_id(self) -> str:
        """Return a stable identifier for the complete experiment."""
        return _stable_identifier(
            self.identity(),
            "experiment",
        )

    @property
    def configuration_count(self) -> int:
        """Return the number of Cartesian-product configurations."""
        count = 1

        for values in self.parameter_grid.values():
            count *= len(values)

        return count

    @property
    def run_count(self) -> int:
        """Return the number of concrete runs in the campaign."""
        problem_dimension_count = sum(
            len(problem.dimensions) for problem in self.problems
        )

        return (
            self.configuration_count
            * problem_dimension_count
            * len(self.seeds.selected_seeds)
        )

    def iter_algorithm_configurations(
        self,
    ) -> Iterator[AlgorithmConfiguration]:
        """Yield configurations without materializing the Cartesian grid."""
        parameter_names = tuple(self.parameter_grid)

        if not parameter_names:
            yield AlgorithmConfiguration(
                algorithm=self.algorithm,
                parameters=self.algorithm.parameters,
            )
            return

        def iterate(
            index: int,
            resolved_parameters: dict[str, ParameterValue],
        ) -> Iterator[AlgorithmConfiguration]:
            if index == len(parameter_names):
                yield AlgorithmConfiguration(
                    algorithm=self.algorithm,
                    parameters=resolved_parameters,
                )
                return

            parameter_name = parameter_names[index]

            for value in self.parameter_grid[parameter_name]:
                next_parameters = dict(resolved_parameters)
                next_parameters[parameter_name] = deepcopy(value)

                yield from iterate(
                    index + 1,
                    next_parameters,
                )

        yield from iterate(0, dict(self.algorithm.parameters))

    def iter_run_specifications(
        self,
    ) -> Iterator[ExperimentRunSpecification]:
        """Yield concrete runs in a deterministic order."""
        experiment_id = self.experiment_id

        for configuration in self.iter_algorithm_configurations():
            for problem in self.problems:
                for dimension in problem.dimensions:
                    for seed in self.seeds.selected_seeds:
                        yield ExperimentRunSpecification(
                            experiment_id=experiment_id,
                            configuration=configuration,
                            problem=problem,
                            dimension=dimension,
                            seed=seed,
                            termination=self.termination,
                        )

    def identity(self) -> dict[str, object]:
        """Return the canonical experiment definition."""
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "description": self.description,
            "algorithm": self.algorithm.identity(),
            "problems": tuple(problem.identity() for problem in self.problems),
            "parameter_grid": self.parameter_grid,
            "seeds": self.seeds.identity(),
            "termination": self.termination.identity(),
        }


__all__ = [
    "SCHEMA_VERSION",
    "SEED",
    "SEEDS",
    "AlgorithmConfiguration",
    "AlgorithmSpecification",
    "ExperimentRunSpecification",
    "ExperimentSpecification",
    "OptimizationDirection",
    "ParameterSet",
    "ParameterValue",
    "ProblemSpecification",
    "SeedSpecification",
    "TerminationSpecification",
]

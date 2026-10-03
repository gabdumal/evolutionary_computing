from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


Scalar = int | float | str | bool | None


def _copy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return dict(value)


def _matches_type(value: Any, expected: type) -> bool:
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, expected)


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    name: str
    value_type: type
    description: str = ""
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[Scalar, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.isidentifier():
            raise ValueError(f"Invalid parameter name: {self.name!r}.")
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum:
                raise ValueError(
                    f"Parameter {self.name!r} has minimum greater than maximum."
                )

    def validate(self, value: Any) -> None:
        if not _matches_type(value, self.value_type):
            raise TypeError(
                f"Parameter {self.name!r} must be compatible with "
                f"{self.value_type.__name__}, got {type(value).__name__}."
            )
        if self.minimum is not None and value < self.minimum:
            raise ValueError(f"Parameter {self.name!r} must be >= {self.minimum}.")
        if self.maximum is not None and value > self.maximum:
            raise ValueError(f"Parameter {self.name!r} must be <= {self.maximum}.")
        if self.choices and value not in self.choices:
            raise ValueError(
                f"Parameter {self.name!r} must be one of {self.choices}; got {value!r}."
            )


@dataclass(frozen=True, slots=True)
class ParameterSchema:
    definitions: tuple[ParameterDefinition, ...]

    def __post_init__(self) -> None:
        names = [definition.name for definition in self.definitions]
        if len(names) != len(set(names)):
            raise ValueError("Parameter names must be unique.")

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(definition.name for definition in self.definitions)

    def validate(
        self,
        parameters: Mapping[str, Any],
        *,
        complete: bool = True,
    ) -> None:
        expected = set(self.names)
        actual = set(parameters)
        unknown = actual - expected
        if unknown:
            raise ValueError(f"Unknown parameters: {sorted(unknown)}.")
        if complete:
            missing = expected - actual
            if missing:
                raise ValueError(f"Missing parameters: {sorted(missing)}.")
        definitions = {definition.name: definition for definition in self.definitions}
        for name, value in parameters.items():
            definitions[name].validate(value)


@dataclass(frozen=True, slots=True)
class AlgorithmSpecification:
    name: str
    implementation: str
    parameter_schema: ParameterSchema
    fixed_parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Algorithm name cannot be empty.")
        if not self.implementation.strip():
            raise ValueError("Algorithm implementation cannot be empty.")
        object.__setattr__(self, "fixed_parameters", _copy_mapping(self.fixed_parameters))
        self.parameter_schema.validate(self.fixed_parameters, complete=False)


@dataclass(frozen=True, slots=True)
class AlgorithmConfiguration:
    algorithm: AlgorithmSpecification
    parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        parameters = dict(self.parameters)
        self.algorithm.parameter_schema.validate(parameters)
        object.__setattr__(self, "parameters", _copy_mapping(parameters))


@dataclass(frozen=True, slots=True)
class BenchmarkScenario:
    problem: str
    dimension: int
    objective: str
    lower_bound: float
    upper_bound: float
    problem_parameters: Mapping[str, Scalar] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.problem.strip():
            raise ValueError("Scenario problem cannot be empty.")
        if not self.objective.strip():
            raise ValueError("Scenario objective cannot be empty.")
        if self.dimension <= 0:
            raise ValueError("Scenario dimension must be positive.")
        lower_bound = float(self.lower_bound)
        upper_bound = float(self.upper_bound)
        if lower_bound >= upper_bound:
            raise ValueError("lower_bound must be smaller than upper_bound.")
        object.__setattr__(self, "lower_bound", lower_bound)
        object.__setattr__(self, "upper_bound", upper_bound)
        object.__setattr__(
            self,
            "problem_parameters",
            _copy_mapping(self.problem_parameters),
        )


@dataclass(frozen=True, slots=True)
class EvaluationBudget:
    max_function_evaluations: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.max_function_evaluations, int)
            or isinstance(self.max_function_evaluations, bool)
            or self.max_function_evaluations <= 0
        ):
            raise ValueError("max_function_evaluations must be a positive integer.")


@dataclass(frozen=True, slots=True)
class SeedPlan:
    seeds: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.seeds:
            raise ValueError("At least one seed is required.")
        if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in self.seeds):
            raise TypeError("Every seed must be an integer.")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("Seeds must be unique.")


@dataclass(frozen=True, slots=True)
class RunSpecification:
    experiment_id: str
    experiment_name: str
    algorithm: AlgorithmConfiguration
    scenario: BenchmarkScenario
    seed: int
    budget: EvaluationBudget

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id cannot be empty.")
        if not self.experiment_name.strip():
            raise ValueError("experiment_name cannot be empty.")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer.")


@dataclass(frozen=True, slots=True)
class ObjectiveResult:
    best_value: float
    best_solution: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class TimingResult:
    cpu_seconds: float

    def __post_init__(self) -> None:
        if self.cpu_seconds < 0:
            raise ValueError("cpu_seconds cannot be negative.")


@dataclass(frozen=True, slots=True)
class ConvergenceTrace:
    function_evaluations: tuple[int, ...]
    best_values: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.function_evaluations) != len(self.best_values):
            raise ValueError("Convergence axes must have equal length.")
        if not self.function_evaluations:
            raise ValueError("Convergence trace cannot be empty.")
        if any(value <= 0 for value in self.function_evaluations):
            raise ValueError("Function-evaluation counts must be positive.")
        if any(
            right <= left
            for left, right in zip(
                self.function_evaluations,
                self.function_evaluations[1:],
            )
        ):
            raise ValueError("Function-evaluation counts must be strictly increasing.")


@dataclass(frozen=True, slots=True)
class RunResult:
    specification: RunSpecification
    objective: ObjectiveResult
    function_evaluations: int
    iterations: int
    timing: TimingResult
    convergence: ConvergenceTrace

    def __post_init__(self) -> None:
        if self.function_evaluations <= 0:
            raise ValueError("function_evaluations must be positive.")
        if self.function_evaluations > self.specification.budget.max_function_evaluations:
            raise ValueError("function_evaluations exceeds the configured budget.")
        if self.iterations < 0:
            raise ValueError("iterations cannot be negative.")
        if len(self.objective.best_solution) != self.specification.scenario.dimension:
            raise ValueError("best_solution dimension does not match the scenario.")
        try:
            coordinates = tuple(float(value) for value in self.objective.best_solution)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "best_solution contains a non-convertible coordinate."
            ) from exc
        if not all(map(__import__("math").isfinite, coordinates)):
            raise ValueError("best_solution must contain only finite coordinates.")


@dataclass(frozen=True, slots=True)
class ExperimentSpecification:
    name: str
    algorithm: AlgorithmSpecification
    scenarios: tuple[BenchmarkScenario, ...]
    configurations: tuple[AlgorithmConfiguration, ...]
    seeds: SeedPlan
    budget: EvaluationBudget
    metadata: Mapping[str, Scalar] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Experiment name cannot be empty.")
        if not self.scenarios:
            raise ValueError("At least one scenario is required.")
        if not self.configurations:
            raise ValueError("At least one algorithm configuration is required.")
        if any(
            configuration.algorithm.implementation != self.algorithm.implementation
            for configuration in self.configurations
        ):
            raise ValueError("All configurations must belong to the experiment algorithm.")
        object.__setattr__(self, "metadata", _copy_mapping(self.metadata))

    def iter_run_specifications(self):
        from .ids import experiment_id

        identifier = experiment_id(self)
        for configuration in self.configurations:
            for scenario in self.scenarios:
                for seed in self.seeds.seeds:
                    yield RunSpecification(
                        experiment_id=identifier,
                        experiment_name=self.name,
                        algorithm=configuration,
                        scenario=scenario,
                        seed=seed,
                        budget=self.budget,
                    )

    @property
    def run_count(self) -> int:
        return len(self.configurations) * len(self.scenarios) * len(self.seeds.seeds)

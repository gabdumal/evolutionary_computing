"""Reusable infrastructure for reproducible optimization experiments."""

from .core import (
    AlgorithmConfiguration,
    AlgorithmSpecification,
    BenchmarkScenario,
    ConvergenceTrace,
    EvaluationBudget,
    ExperimentSpecification,
    ObjectiveResult,
    ParameterDefinition,
    ParameterSchema,
    RunResult,
    RunSpecification,
    SeedPlan,
    TimingResult,
)
from .algorithms import AlgorithmAdapter, AlgorithmRegistry
from .execution import ExecutionReport, ExperimentRunner
from .artifacts import ArtifactStore
from .validation import ValidationReport, validate_experiment
from .analysis import RunDataset, aggregate_runs

__all__ = [
    "AlgorithmAdapter",
    "AlgorithmConfiguration",
    "AlgorithmRegistry",
    "AlgorithmSpecification",
    "ArtifactStore",
    "BenchmarkScenario",
    "ConvergenceTrace",
    "EvaluationBudget",
    "ExecutionReport",
    "ExperimentRunner",
    "ExperimentSpecification",
    "ObjectiveResult",
    "ParameterDefinition",
    "ParameterSchema",
    "RunDataset",
    "RunResult",
    "RunSpecification",
    "SeedPlan",
    "TimingResult",
    "ValidationReport",
    "aggregate_runs",
    "validate_experiment",
]

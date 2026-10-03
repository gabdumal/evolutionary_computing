from __future__ import annotations

from ..core.models import BenchmarkScenario


def default_benchmark_scenarios(
    *,
    dimensions: tuple[int, ...] = (10, 100),
) -> tuple[BenchmarkScenario, ...]:
    scenarios = []
    for dimension in dimensions:
        scenarios.extend(
            (
                BenchmarkScenario(
                    problem="HappyCat",
                    dimension=dimension,
                    objective="happycat",
                    lower_bound=-20.0,
                    upper_bound=20.0,
                ),
                BenchmarkScenario(
                    problem="Rosenbrock",
                    dimension=dimension,
                    objective="rosenbrock",
                    lower_bound=-30.0,
                    upper_bound=30.0,
                ),
                BenchmarkScenario(
                    problem="Schwefel",
                    dimension=dimension,
                    objective="schwefel",
                    lower_bound=-500.0,
                    upper_bound=500.0,
                ),
            )
        )
    return tuple(scenarios)

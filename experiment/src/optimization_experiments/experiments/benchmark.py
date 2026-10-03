from __future__ import annotations

from ..core.models import BenchmarkScenario


def default_benchmark_scenarios(
    *,
    dimensions: tuple[int, ...] = (10, 100),
) -> tuple[BenchmarkScenario, ...]:
    scenarios = []
    bounds = {
        "HappyCat": (-100.0, 100.0),
        "Rosenbrock": (-30.0, 30.0),
        "Schwefel": (-500.0, 500.0),
    }

    for dimension in dimensions:
        for problem, objective in (
            ("HappyCat", "happycat"),
            ("Rosenbrock", "rosenbrock"),
            ("Schwefel", "schwefel"),
        ):
            lower, upper = bounds[problem]
            scenarios.append(
                BenchmarkScenario(
                    problem=problem,
                    dimension=dimension,
                    objective=objective,
                    lower_bound=lower,
                    upper_bound=upper,
                )
            )

    return tuple(scenarios)

import pandas as pd

from optimization_experiments.analysis import (
    create_run_statistics_table,
    create_run_table,
)
from optimization_experiments.algorithms.cso import cso_algorithm_specification
from optimization_experiments.core import (
    AlgorithmConfiguration,
    BenchmarkScenario,
    ConvergenceTrace,
    EvaluationBudget,
    ExperimentSpecification,
    ObjectiveResult,
    RunResult,
    RunSpecification,
    SeedPlan,
    TimingResult,
)


def make_result(seed: int, value: float):
    algorithm = cso_algorithm_specification()
    configuration = AlgorithmConfiguration(
        algorithm,
        dict(algorithm.fixed_parameters),
    )
    scenario = BenchmarkScenario(
        problem="Sphere",
        dimension=2,
        objective="sphere",
        lower_bound=-5,
        upper_bound=5,
    )
    specification = RunSpecification(
        experiment_id="exp_analysis",
        experiment_name="analysis",
        algorithm=configuration,
        scenario=scenario,
        seed=seed,
        budget=EvaluationBudget(10),
    )
    return RunResult(
        specification=specification,
        objective=ObjectiveResult(
            best_value=value,
            best_solution=(0.0, 0.0),
        ),
        function_evaluations=10,
        iterations=3,
        timing=TimingResult(cpu_seconds=1.0 + seed / 1000.0),
        convergence=ConvergenceTrace(
            function_evaluations=(5, 10),
            best_values=(value + 1.0, value),
        ),
    )


def test_run_and_statistics_tables():
    table = create_run_table(
        (make_result(27, 3.0), make_result(32, 1.0), make_result(59, 2.0))
    )
    assert len(table) == 3
    assert "population_size" in table.columns

    statistics = create_run_statistics_table(
        table,
        group_by=("problem", "dimension"),
    )
    assert len(statistics) == 1
    assert statistics.iloc[0]["calculated_value__min"] == 1.0
    assert statistics.iloc[0]["calculated_value__max"] == 3.0
    assert statistics.iloc[0]["calculated_value__mean"] == 2.0


def test_run_table_from_records_matches_run_table():
    from optimization_experiments.core.serialization import to_primitive

    results = (make_result(27, 3.0), make_result(32, 1.0))
    records = tuple(
        {
            "run": to_primitive(result.specification),
            "metrics": {
                "best_value": result.objective.best_value,
                "best_solution": list(result.objective.best_solution),
                "function_evaluations": result.function_evaluations,
                "iterations": result.iterations,
                "cpu_seconds": result.timing.cpu_seconds,
            },
        }
        for result in results
    )

    from optimization_experiments.analysis import create_run_table_from_records

    from_records = create_run_table_from_records(records)
    from_results = create_run_table(results)

    pd.testing.assert_frame_equal(
        from_records.sort_values("run_id").reset_index(drop=True),
        from_results.sort_values("run_id").reset_index(drop=True),
        check_dtype=False,
    )

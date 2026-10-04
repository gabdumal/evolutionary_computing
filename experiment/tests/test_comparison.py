import pandas as pd

from optimization_experiments.analysis.comparison import (
    analyze_algorithm_comparison,
    create_formatted_comparison_table,
)


def _frame(algorithm: str, offset: float) -> pd.DataFrame:
    rows = []
    for objective, dimension in (
        ("Rosenbrock", 10),
        ("Rosenbrock", 100),
        ("Schwefel", 10),
        ("Schwefel", 100),
        ("HappyCat", 10),
        ("HappyCat", 100),
    ):
        for config_id, extra in (("cfg_bad", 10.0), ("cfg_good", 0.0)):
            for seed in (27, 32, 59):
                rows.append(
                    {
                        "objective_function": objective,
                        "dimension": dimension,
                        "configuration_id": config_id,
                        "seed": seed,
                        "calculated_value": offset + extra + seed / 1000,
                        "iterations": 100 + seed,
                        "cpu_seconds": 0.4 + seed / 10000,
                        "function_evaluations": 10_000,
                    }
                )
    frame = pd.DataFrame(rows)
    frame["algorithm"] = algorithm
    return frame


def test_comparison_selects_one_configuration_per_algorithm_scenario():
    comparison = analyze_algorithm_comparison(
        {"CSO": _frame("CSO", 0), "ZO-AdaMM": _frame("ZO-AdaMM", 1)}
    )
    assert len(comparison.table) == 12
    assert set(comparison.table["seed_count"]) == {3}
    assert set(comparison.table["configuration_id"]) == {"cfg_good"}


def test_formatted_comparison_matches_current_table_columns():
    comparison = analyze_algorithm_comparison(
        {"CSO": _frame("CSO", 0), "ZO-AdaMM": _frame("ZO-AdaMM", 1)}
    )
    table = create_formatted_comparison_table(comparison.table)
    assert list(table.columns) == [
        "algorithm",
        "objective_function",
        "dimension",
        "configuration_id",
        "value",
        "iterations",
        "time_seconds",
        "seed_count",
    ]
    assert table.iloc[0]["value"].count("±") == 1
    assert table.iloc[0]["time_seconds"].count("±") == 1

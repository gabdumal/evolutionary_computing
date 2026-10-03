from __future__ import annotations

"""Run and persist deterministic, problem-specific sensitivity analysis."""

import argparse
import importlib
import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from experiment_artifacts import DEFAULT_ARTIFACT_ROOT, ExperimentArtifactStore
from experiment_specifications import ExperimentSpecification
from sensitivity_analysis import (
    analyze_sensitivity,
    create_configuration_comparison_table,
    create_parameter_effect_table,
    create_selected_configuration_table,
)

ARTIFACT_ROOT = DEFAULT_ARTIFACT_ROOT


def main() -> None:
    arguments = _parse_arguments()
    experiment_factory = _load_experiment_factory(
        arguments.experiment_module,
        arguments.experiment_factory,
    )
    experiment = experiment_factory()
    if not isinstance(experiment, ExperimentSpecification):
        raise SystemExit(
            f"{arguments.experiment_module}.{arguments.experiment_factory} "
            "did not return an ExperimentSpecification."
        )

    artifact_store = ExperimentArtifactStore(
        arguments.artifact_root,
        experiment,
    )

    analysis = analyze_sensitivity(
        artifact_store,
        experiment,
        require_complete=not arguments.allow_incomplete,
    )

    output_directory = artifact_store.experiment_directory / "analysis"
    output_directory.mkdir(parents=True, exist_ok=True)

    analysis.run_table.to_csv(
        output_directory / "run_results.csv",
        index=False,
    )
    analysis.scenario_table.to_csv(
        output_directory / "scenario_results.csv",
        index=False,
    )
    create_configuration_comparison_table(analysis).to_csv(
        output_directory / "problem_configuration_results.csv",
        index=False,
    )
    analysis.problem_parameter_table.to_csv(
        output_directory / "problem_parameter_results.csv",
        index=False,
    )
    create_parameter_effect_table(analysis).to_csv(
        output_directory / "problem_parameter_effect_summary.csv",
        index=False,
    )
    create_selected_configuration_table(analysis).to_csv(
        output_directory / "selected_configurations.csv",
        index=False,
    )

    metadata = {
        "experiment_id": analysis.experiment_id,
        "algorithm": analysis.algorithm_name,
        "design": analysis.design,
        "sensitivity_scope": "problem",
        "parameter_names": list(analysis.parameter_names),
        "problems": list(analysis.problems),
        "completed_run_count": analysis.completed_run_count,
        "analyzed_run_count": analysis.analyzed_run_count,
        "expected_run_count": analysis.validation_report.expected_run_count,
        "validation_is_valid": analysis.validation_report.is_valid,
        "validation_error_count": analysis.validation_report.error_count,
        "validation_warning_count": analysis.validation_report.warning_count,
        "configuration_count": analysis.configuration_count,
        "problem_configuration_count": analysis.problem_configuration_count,
        "scenario_count": analysis.scenario_count,
        "selection_rule": (
            "minimum mean normalized gap per problem; ties within tolerance are "
            "resolved by minimum worst normalized gap, then minimum mean CPU time, "
            "then configuration ID"
        ),
    }
    with (output_directory / "metadata.json").open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            indent=2,
            ensure_ascii=True,
            sort_keys=True,
        )
        file.write("\n")

    print(f"Experiment: {experiment.name}")
    print(f"Experiment ID: {experiment.experiment_id}")
    print("Sensitivity scope: problem")
    print(f"Design: {analysis.design}")
    print(f"Configurations: {analysis.configuration_count}")
    print(f"Problem/configuration rows: {analysis.problem_configuration_count}")
    print(f"Problems: {', '.join(analysis.problems)}")
    print(f"Scenarios: {analysis.scenario_count}")
    print(
        "Runs: "
        f"{analysis.analyzed_run_count}/{analysis.validation_report.expected_run_count}"
    )
    print(f"Validation valid: {analysis.validation_report.is_valid}")
    print(f"Analysis output: {output_directory}")

    _print_parameter_effects(analysis.problem_parameter_table)
    _print_configuration_results(analysis.problem_configuration_table)
    _print_selected_configurations(analysis.selected_configuration_table)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze a completed optimization sensitivity experiment without "
            "executing additional optimization runs. Configuration performance "
            "and parameter effects are computed independently for each problem."
        )
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path(ARTIFACT_ROOT),
        help="Root directory containing experiment artifacts.",
    )
    parser.add_argument(
        "--experiment-module",
        default="run_validation",
        help="Python module containing the experiment factory.",
    )
    parser.add_argument(
        "--experiment-factory",
        default="create_validation_experiment",
        help="Factory function that returns the ExperimentSpecification.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Analyze the valid completed subset instead of requiring all runs.",
    )
    return parser.parse_args()


def _load_experiment_factory(
    module_name: str,
    factory_name: str,
) -> Callable[[], ExperimentSpecification]:
    """Load an experiment factory without hard-coding one campaign."""
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise SystemExit(
            f"Could not import experiment module {module_name!r}: {exc}"
        ) from exc

    factory = getattr(module, factory_name, None)
    if not callable(factory):
        raise SystemExit(
            f"Experiment factory {module_name}.{factory_name} is not callable."
        )

    def typed_factory() -> ExperimentSpecification:
        result = factory()
        if not isinstance(result, ExperimentSpecification):
            raise TypeError(
                f"{module_name}.{factory_name} did not return an "
                "ExperimentSpecification."
            )
        return result

    return typed_factory


def _print_parameter_effects(parameter_table: pd.DataFrame) -> None:
    if parameter_table.empty:
        print("\nNo parameter sensitivity results.")
        return

    print("\nProblem-specific parameter effects:")
    display_columns = [
        "problem",
        "parameter",
        "parameter_value",
        "mean_normalized_gap",
        "mean_rank",
        "parameter_effect_range",
    ]
    print(
        parameter_table.loc[:, display_columns].to_string(
            index=False,
            float_format=lambda value: f"{value:.6f}",
        )
    )


def _print_configuration_results(configuration_table: pd.DataFrame) -> None:
    if configuration_table.empty:
        print("\nNo configuration sensitivity results.")
        return

    print("\nProblem-specific configuration results:")
    parameter_columns = [
        column
        for column in configuration_table.columns
        if column
        not in {
            "problem",
            "configuration_id",
            "algorithm",
            "dimension_count",
            "mean_normalized_gap",
            "std_normalized_gap",
            "mean_seed_std_normalized_gap",
            "max_seed_std_normalized_gap",
            "mean_rank",
            "worst_normalized_gap",
            "mean_cpu_seconds",
            "mean_function_evaluations",
        }
        and not column.endswith("__key")
    ]
    display_columns = [
        "problem",
        "configuration_id",
        *parameter_columns,
        "mean_normalized_gap",
        "std_normalized_gap",
        "mean_rank",
        "worst_normalized_gap",
        "mean_cpu_seconds",
    ]
    print(
        configuration_table.loc[:, display_columns].to_string(
            index=False,
            float_format=lambda value: f"{value:.6f}",
        )
    )


def _print_selected_configurations(selected_table: pd.DataFrame) -> None:
    if selected_table.empty:
        print("\nNo selected configurations.")
        return

    print("\nSelected configuration per problem:")
    display_columns = [
        "problem",
        "configuration_id",
        "selection_status",
        "mean_normalized_gap",
        "worst_normalized_gap",
        "mean_cpu_seconds",
    ]
    print(
        selected_table.loc[:, display_columns].to_string(
            index=False,
            float_format=lambda value: f"{value:.6f}",
        )
    )


if __name__ == "__main__":
    main()

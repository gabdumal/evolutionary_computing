"""Generate only the two requested sensitivity-analysis artifacts."""

import argparse
import importlib
from collections.abc import Callable
from pathlib import Path

from experiment_artifacts import DEFAULT_ARTIFACT_ROOT, ExperimentArtifactStore
from experiment_specifications import ExperimentSpecification
from sensitivity_analysis import (
    DEFAULT_MAX_WORKERS,
    analyze_sensitivity,
    create_dimension_parameter_summary_table,
    create_selected_parameters_by_dimension_table,
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

    artifact_store = ExperimentArtifactStore(arguments.artifact_root, experiment)
    analysis = analyze_sensitivity(
        artifact_store,
        experiment,
        require_complete=not arguments.allow_incomplete,
        max_workers=arguments.workers,
    )

    output_directory = artifact_store.experiment_directory / "analysis"
    output_directory.mkdir(parents=True, exist_ok=True)

    create_dimension_parameter_summary_table(analysis).to_csv(
        output_directory / "problem_parameter_dimension_summary.csv",
        index=False,
    )
    create_selected_parameters_by_dimension_table(analysis).to_csv(
        output_directory / "selected_parameters_by_dimension.csv",
        index=False,
    )

    print(f"Experiment: {experiment.name}")
    print(f"Output: {output_directory}")


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze a completed sensitivity experiment and generate only the "
            "two requested slide tables."
        )
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path(ARTIFACT_ROOT),
    )
    parser.add_argument(
        "--experiment-module",
        default="run_validation",
    )
    parser.add_argument(
        "--experiment-factory",
        default="create_validation_experiment",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Number of worker processes used for sensitivity calculations.",
    )
    return parser.parse_args()


def _load_experiment_factory(
    module_name: str,
    factory_name: str,
) -> Callable[[], ExperimentSpecification]:
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


if __name__ == "__main__":
    main()

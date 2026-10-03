from __future__ import annotations

"""Generate raw and statistical artifacts for a completed experiment."""

import argparse
import importlib
from collections.abc import Callable
from pathlib import Path

from experiment_artifacts import DEFAULT_ARTIFACT_ROOT, ExperimentArtifactStore
from experiment_specifications import ExperimentSpecification
from results_analysis import (
    DEFAULT_PROGRESS_INTERVAL_SECONDS,
    generate_result_artifacts,
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
    generate_result_artifacts(
        artifact_store,
        experiment,
        output_directory=arguments.output_directory,
        require_complete=not arguments.allow_incomplete,
        progress_interval_seconds=arguments.progress_interval,
    )


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate one row per completed run and statistics grouped by "
            "configuration, objective function, and dimension."
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
        help="Factory function returning an ExperimentSpecification.",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=None,
        help="Directory for the two generated CSV files.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Generate tables from the completed subset.",
    )
    parser.add_argument(
        "--progress-interval",
        type=float,
        default=DEFAULT_PROGRESS_INTERVAL_SECONDS,
        help="Console progress interval in seconds.",
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

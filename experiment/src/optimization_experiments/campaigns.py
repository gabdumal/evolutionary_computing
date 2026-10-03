from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .algorithms import AlgorithmRegistry, default_registry
from .analysis import analyze_cso, write_cso_analysis_artifacts
from .artifacts import ArtifactStore
from .core.models import ExperimentSpecification
from .execution import ExecutionReport, ExperimentRunner
from .validation import ValidationReport, validate_experiment


@dataclass(frozen=True, slots=True)
class CampaignReport:
    execution: ExecutionReport
    validation: ValidationReport


def run_campaign(
    experiment: ExperimentSpecification,
    *,
    artifact_root: str | Path = "_artifacts",
    registry: AlgorithmRegistry | None = None,
    max_workers: int | None = None,
    start_method: str = "forkserver",
    validate: bool = True,
    generate_analysis: bool = True,
    durable_artifacts: bool = False,
    compress_convergence: bool = False,
) -> CampaignReport:
    store = ArtifactStore(
        artifact_root,
        experiment,
        durable=durable_artifacts,
        compress_convergence=compress_convergence,
    )
    runner = ExperimentRunner(
        store,
        registry or default_registry(),
        max_workers=max_workers,
        start_method=start_method,
    )
    execution = runner.run(experiment)
    validation = validate_experiment(experiment, store)

    if validation.valid and generate_analysis:
        if experiment.name.startswith("cso-grid"):
            analysis = analyze_cso(experiment, store)
            write_cso_analysis_artifacts(analysis, store.paths.analysis)
        else:
            from .analysis import generate_result_artifacts
            generate_result_artifacts(experiment, store)

    if validate and not validation.valid:
        raise RuntimeError(
            "Experiment validation failed:\n"
            + "\n".join(validation.errors)
        )

    return CampaignReport(
        execution=execution,
        validation=validation,
    )

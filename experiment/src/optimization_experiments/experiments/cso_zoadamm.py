from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ..algorithms.cso_zoadamm_spec import (
    CSO_ZOADAMM_VALIDATED_PROFILES,
    cso_zoadamm_algorithm_specification,
    cso_zoadamm_validated_configuration,
)
from ..core.ids import configuration_id, experiment_id
from ..core.models import (
    AlgorithmConfiguration,
    EvaluationBudget,
    ExperimentSpecification,
    RunSpecification,
    SeedPlan,
)
from .benchmark import default_benchmark_scenarios


CSO_ZOADAMM_SMOKE_BUDGET = 1_000
CSO_ZOADAMM_BUDGET = 10_000
CSO_ZOADAMM_SEEDS = (27, 32, 59)
CSO_ZOADAMM_DIMENSIONS = (10, 100)
CSO_ZOADAMM_CSO_FRACTION = 0.8


@dataclass(frozen=True, slots=True)
class ScenarioConfiguredExperimentSpecification(ExperimentSpecification):
    """Experiment with exactly one resolved algorithm configuration per scenario."""

    scenario_configuration_ids: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ExperimentSpecification.__post_init__(self)
        valid_configuration_ids = {
            configuration_id(configuration) for configuration in self.configurations
        }
        missing = [
            _scenario_key(scenario)
            for scenario in self.scenarios
            if _scenario_key(scenario) not in self.scenario_configuration_ids
        ]
        unknown = set(self.scenario_configuration_ids.values()) - valid_configuration_ids
        if missing:
            raise ValueError(f"Missing hybrid configuration mapping for scenarios: {missing}.")
        if unknown:
            raise ValueError(
                f"Hybrid mapping references unknown configurations: {sorted(unknown)}."
            )

    def iter_run_specifications(self):
        identifier = experiment_id(self)
        by_id = {
            configuration_id(configuration): configuration for configuration in self.configurations
        }
        for scenario in self.scenarios:
            key = _scenario_key(scenario)
            configuration = by_id[self.scenario_configuration_ids[key]]
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
        return len(self.scenarios) * len(self.seeds.seeds)


def _scenario_key(scenario) -> str:
    return f"{scenario.objective.lower()}:{scenario.dimension}"


def _create_hybrid_experiment(
    *, name: str, budget: int, purpose: str
) -> ScenarioConfiguredExperimentSpecification:
    algorithm = cso_zoadamm_algorithm_specification()
    scenarios = default_benchmark_scenarios(dimensions=CSO_ZOADAMM_DIMENSIONS)

    configurations: list[AlgorithmConfiguration] = []
    scenario_configuration_ids: dict[str, str] = {}
    profile_sources: dict[str, dict[str, str]] = {}

    for objective_function, dimension in sorted(CSO_ZOADAMM_VALIDATED_PROFILES):
        configuration = cso_zoadamm_validated_configuration(
            algorithm,
            objective_function,
            dimension,
        )
        configurations.append(configuration)
        key = f"{objective_function}:{dimension}"
        scenario_configuration_ids[key] = configuration_id(configuration)
        profile = CSO_ZOADAMM_VALIDATED_PROFILES[(objective_function, dimension)]
        profile_sources[key] = {
            "cso_configuration_id": profile["source_cso_configuration_id"],
            "zoadamm_configuration_id": profile["source_zoadamm_configuration_id"],
            "hybrid_configuration_id": configuration_id(configuration),
        }

    return ScenarioConfiguredExperimentSpecification(
        name=name,
        algorithm=algorithm,
        scenarios=scenarios,
        configurations=tuple(configurations),
        seeds=SeedPlan(CSO_ZOADAMM_SEEDS),
        budget=EvaluationBudget(budget),
        scenario_configuration_ids=scenario_configuration_ids,
        metadata={
            "purpose": purpose,
            "design": "sequential_hybrid",
            "hybrid": "CSO exploration -> ZO-AdaMM refinement",
            "cso_budget_fraction": CSO_ZOADAMM_CSO_FRACTION,
            "cso_budget_fraction_description": "80% of total function evaluations",
            "zoadamm_budget_fraction_description": "20% of total function evaluations",
            "seeds": ",".join(str(seed) for seed in CSO_ZOADAMM_SEEDS),
            "dimensions": ",".join(str(dimension) for dimension in CSO_ZOADAMM_DIMENSIONS),
            "function_evaluations_per_run": budget,
            "parameter_source": "best standalone CSO and ZO-AdaMM configurations selected from 3-seed validation",
            "validated_profile_sources": str(profile_sources),
        },
    )


def create_cso_zoadamm_smoke_experiment() -> ExperimentSpecification:
    return _create_hybrid_experiment(
        name="cso-zoadamm-smoke-validated",
        budget=CSO_ZOADAMM_SMOKE_BUDGET,
        purpose="post-implementation smoke validation using validated component parameters",
    )


def create_cso_zoadamm_campaign_experiment() -> ExperimentSpecification:
    return _create_hybrid_experiment(
        name="cso-zoadamm-validated-80-20-3seed",
        budget=CSO_ZOADAMM_BUDGET,
        purpose="final CSO-ZO-AdaMM hybrid benchmark campaign using validated component parameters",
    )

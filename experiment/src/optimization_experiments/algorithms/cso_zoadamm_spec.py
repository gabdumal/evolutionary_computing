from __future__ import annotations

from typing import Any

from ..core.models import AlgorithmConfiguration, AlgorithmSpecification, ParameterDefinition, ParameterSchema


CSO_ZOADAMM_PARAMETER_SCHEMA = ParameterSchema(
    definitions=(
        ParameterDefinition("cso_population_size", int, "CSO population size.", minimum=1),
        ParameterDefinition(
            "cso_mixture_ratio",
            float,
            "CSO mixture ratio.",
            minimum=0.0,
            maximum=1.0,
        ),
        ParameterDefinition("cso_c1", float, "CSO tracing acceleration coefficient.", minimum=0.0),
        ParameterDefinition("cso_smp", int, "CSO seeking memory pool size.", minimum=1),
        ParameterDefinition("cso_spc", bool, "Whether CSO seeking mode considers self-position."),
        ParameterDefinition(
            "cso_cdc",
            float,
            "CSO fraction of dimensions changed in seeking mode.",
            minimum=0.0,
            maximum=1.0,
        ),
        ParameterDefinition(
            "cso_srd",
            float,
            "CSO seeking range.",
            minimum=0.0,
            maximum=1.0,
        ),
        ParameterDefinition("cso_max_velocity", float, "CSO maximum tracing velocity.", minimum=0.0),
        ParameterDefinition(
            "zoadamm_learning_rate",
            float,
            "ZO-AdaMM base learning rate.",
            minimum=0.0,
        ),
        ParameterDefinition(
            "zoadamm_beta1",
            float,
            "ZO-AdaMM first-moment coefficient.",
            minimum=0.0,
            maximum=1.0,
        ),
        ParameterDefinition(
            "zoadamm_beta2",
            float,
            "ZO-AdaMM second-moment coefficient.",
            minimum=0.0,
            maximum=1.0,
        ),
        ParameterDefinition(
            "zoadamm_mu",
            float,
            "ZO-AdaMM smoothing parameter.",
            minimum=0.0,
        ),
        ParameterDefinition(
            "zoadamm_q",
            int,
            "ZO-AdaMM number of directions per estimate.",
            minimum=1,
        ),
        ParameterDefinition(
            "zoadamm_epsilon",
            float,
            "ZO-AdaMM numerical stabilizer.",
            minimum=0.0,
        ),
        ParameterDefinition(
            "zoadamm_decay_learning_rate",
            bool,
            "Whether ZO-AdaMM decays the learning rate.",
        ),
        ParameterDefinition(
            "cso_budget_fraction",
            float,
            "Fraction of the total FE budget allocated to CSO.",
            minimum=0.0,
            maximum=1.0,
        ),
    )
)

# The hybrid does not use generic CSO/ZO-AdaMM defaults.  Its six profiles below
# are the configurations selected from the user's standalone 3-seed validation.
# Keys are objective function + dimension.
CSO_ZOADAMM_VALIDATED_PROFILES: dict[tuple[str, int], dict[str, Any]] = {
    ("happycat", 10): {
        "cso_population_size": 15,
        "cso_mixture_ratio": 0.1,
        "cso_c1": 1.05,
        "cso_smp": 2,
        "cso_spc": False,
        "cso_cdc": 1.0,
        "cso_srd": 0.4,
        "cso_max_velocity": 1.9,
        "zoadamm_learning_rate": 0.7,
        "zoadamm_beta1": 0.9,
        "zoadamm_beta2": 0.99999,
        "zoadamm_mu": 0.001,
        "zoadamm_q": 5,
        "zoadamm_epsilon": 1e-12,
        "zoadamm_decay_learning_rate": True,
        "cso_budget_fraction": 0.8,
        "source_cso_configuration_id": "cfg_5d06b752965a6774",
        "source_zoadamm_configuration_id": "cfg_7af707503efcf31a",
    },
    ("happycat", 100): {
        "cso_population_size": 15,
        "cso_mixture_ratio": 0.3,
        "cso_c1": 2.05,
        "cso_smp": 2,
        "cso_spc": False,
        "cso_cdc": 1.0,
        "cso_srd": 0.4,
        "cso_max_velocity": 1.0,
        "zoadamm_learning_rate": 1.5,
        "zoadamm_beta1": 0.99,
        "zoadamm_beta2": 0.9999,
        "zoadamm_mu": 0.001,
        "zoadamm_q": 5,
        "zoadamm_epsilon": 1e-12,
        "zoadamm_decay_learning_rate": True,
        "cso_budget_fraction": 0.8,
        "source_cso_configuration_id": "cfg_a3f9958e436d3bd0",
        "source_zoadamm_configuration_id": "cfg_aa149cad5b2ac5a3",
    },
    ("rosenbrock", 10): {
        "cso_population_size": 60,
        "cso_mixture_ratio": 0.1,
        "cso_c1": 1.05,
        "cso_smp": 3,
        "cso_spc": True,
        "cso_cdc": 0.6,
        "cso_srd": 0.1,
        "cso_max_velocity": 1.0,
        "zoadamm_learning_rate": 2.0,
        "zoadamm_beta1": 0.9,
        "zoadamm_beta2": 0.9999999,
        "zoadamm_mu": 0.001,
        "zoadamm_q": 30,
        "zoadamm_epsilon": 1e-12,
        "zoadamm_decay_learning_rate": True,
        "cso_budget_fraction": 0.8,
        "source_cso_configuration_id": "cfg_a85d8af5699deaa5",
        "source_zoadamm_configuration_id": "cfg_31acc57f36821808",
    },
    ("rosenbrock", 100): {
        "cso_population_size": 15,
        "cso_mixture_ratio": 0.1,
        "cso_c1": 1.05,
        "cso_smp": 5,
        "cso_spc": True,
        "cso_cdc": 0.6,
        "cso_srd": 0.1,
        "cso_max_velocity": 1.9,
        "zoadamm_learning_rate": 1.5,
        "zoadamm_beta1": 0.0,
        "zoadamm_beta2": 0.99999999,
        "zoadamm_mu": 0.001,
        "zoadamm_q": 5,
        "zoadamm_epsilon": 1e-12,
        "zoadamm_decay_learning_rate": True,
        "cso_budget_fraction": 0.8,
        "source_cso_configuration_id": "cfg_ac488c3496499f2d",
        "source_zoadamm_configuration_id": "cfg_99aecedf6c529670",
    },
    ("schwefel", 10): {
        "cso_population_size": 15,
        "cso_mixture_ratio": 0.3,
        "cso_c1": 2.05,
        "cso_smp": 2,
        "cso_spc": True,
        "cso_cdc": 0.6,
        "cso_srd": 0.1,
        "cso_max_velocity": 3.0,
        "zoadamm_learning_rate": 2.0,
        "zoadamm_beta1": 0.95,
        "zoadamm_beta2": 0.9999999,
        "zoadamm_mu": 0.001,
        "zoadamm_q": 40,
        "zoadamm_epsilon": 1e-12,
        "zoadamm_decay_learning_rate": True,
        "cso_budget_fraction": 0.8,
        "source_cso_configuration_id": "cfg_04e67997b94c21ed",
        "source_zoadamm_configuration_id": "cfg_f052cb79ca98e299",
    },
    ("schwefel", 100): {
        "cso_population_size": 15,
        "cso_mixture_ratio": 0.5,
        "cso_c1": 3.05,
        "cso_smp": 2,
        "cso_spc": True,
        "cso_cdc": 0.6,
        "cso_srd": 0.1,
        "cso_max_velocity": 3.0,
        "zoadamm_learning_rate": 0.7,
        "zoadamm_beta1": 0.0,
        "zoadamm_beta2": 0.999999,
        "zoadamm_mu": 0.001,
        "zoadamm_q": 10,
        "zoadamm_epsilon": 1e-12,
        "zoadamm_decay_learning_rate": True,
        "cso_budget_fraction": 0.8,
        "source_cso_configuration_id": "cfg_abd1821797cf8018",
        "source_zoadamm_configuration_id": "cfg_f2503eee26481d7d",
    },
}

# Only the budget split is generic at algorithm-specification level. The
# component optimizer parameters are intentionally supplied by the scenario-
# specific validated profiles in the hybrid experiment.
CSO_ZOADAMM_FIXED_PARAMETERS = {
    "cso_budget_fraction": 0.8,
}

def cso_zoadamm_algorithm_specification() -> AlgorithmSpecification:
    return AlgorithmSpecification(
        name="CSO-ZO-AdaMM",
        implementation="cso_zoadamm",
        parameter_schema=CSO_ZOADAMM_PARAMETER_SCHEMA,
        fixed_parameters=CSO_ZOADAMM_FIXED_PARAMETERS,
    )


def cso_zoadamm_validated_parameters(
    objective_function: str,
    dimension: int,
) -> dict[str, Any]:
    key = (objective_function.lower(), int(dimension))
    try:
        profile = dict(CSO_ZOADAMM_VALIDATED_PROFILES[key])
    except KeyError as exc:
        supported = ", ".join(
            f"{objective}/{dimension}" for objective, dimension in sorted(CSO_ZOADAMM_VALIDATED_PROFILES)
        )
        raise KeyError(
            f"No validated CSO-ZO-AdaMM profile for {objective_function!r}, dimension={dimension}. "
            f"Supported profiles: {supported}."
        ) from exc

    # Source configuration IDs are metadata for traceability, not optimizer
    # parameters passed to CSO or ZO-AdaMM.
    profile.pop("source_cso_configuration_id")
    profile.pop("source_zoadamm_configuration_id")
    return profile


def cso_zoadamm_validated_configuration(
    algorithm: AlgorithmSpecification,
    objective_function: str,
    dimension: int,
) -> AlgorithmConfiguration:
    parameters = cso_zoadamm_validated_parameters(objective_function, dimension)
    return AlgorithmConfiguration(algorithm=algorithm, parameters=parameters)

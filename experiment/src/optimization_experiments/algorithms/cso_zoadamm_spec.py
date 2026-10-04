from __future__ import annotations

from ..core.models import AlgorithmSpecification, ParameterDefinition, ParameterSchema
from .cso import CSO_DEFAULT_PARAMETERS
from .zoadamm_spec import ZOADAMM_DEFAULT_PARAMETERS


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


CSO_ZOADAMM_DEFAULT_PARAMETERS = {
    "cso_population_size": CSO_DEFAULT_PARAMETERS["population_size"],
    "cso_mixture_ratio": CSO_DEFAULT_PARAMETERS["mixture_ratio"],
    "cso_c1": CSO_DEFAULT_PARAMETERS["c1"],
    "cso_smp": CSO_DEFAULT_PARAMETERS["smp"],
    "cso_spc": CSO_DEFAULT_PARAMETERS["spc"],
    "cso_cdc": CSO_DEFAULT_PARAMETERS["cdc"],
    "cso_srd": CSO_DEFAULT_PARAMETERS["srd"],
    "cso_max_velocity": CSO_DEFAULT_PARAMETERS["max_velocity"],
    "zoadamm_learning_rate": ZOADAMM_DEFAULT_PARAMETERS["learning_rate"],
    "zoadamm_beta1": ZOADAMM_DEFAULT_PARAMETERS["beta1"],
    "zoadamm_beta2": ZOADAMM_DEFAULT_PARAMETERS["beta2"],
    "zoadamm_mu": ZOADAMM_DEFAULT_PARAMETERS["mu"],
    "zoadamm_q": ZOADAMM_DEFAULT_PARAMETERS["q"],
    "zoadamm_epsilon": ZOADAMM_DEFAULT_PARAMETERS["epsilon"],
    "zoadamm_decay_learning_rate": ZOADAMM_DEFAULT_PARAMETERS["decay_learning_rate"],
    "cso_budget_fraction": 0.8,
}


def cso_zoadamm_algorithm_specification() -> AlgorithmSpecification:
    return AlgorithmSpecification(
        name="CSO-ZO-AdaMM",
        implementation="cso_zoadamm",
        parameter_schema=CSO_ZOADAMM_PARAMETER_SCHEMA,
        fixed_parameters=CSO_ZOADAMM_DEFAULT_PARAMETERS,
    )

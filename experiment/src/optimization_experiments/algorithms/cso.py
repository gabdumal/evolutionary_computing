from __future__ import annotations

from ..core.models import (
    AlgorithmSpecification,
    ParameterDefinition,
    ParameterSchema,
)


CSO_PARAMETER_SCHEMA = ParameterSchema(
    definitions=(
        ParameterDefinition(
            "population_size",
            int,
            "Number of cats in the population.",
            minimum=1,
        ),
        ParameterDefinition(
            "mixture_ratio",
            float,
            "Fraction of cats in tracing mode.",
            minimum=0.0,
            maximum=1.0,
        ),
        ParameterDefinition(
            "c1",
            float,
            "Tracing-mode acceleration coefficient.",
            minimum=0.0,
        ),
        ParameterDefinition(
            "smp",
            int,
            "Seeking memory pool size.",
            minimum=1,
        ),
        ParameterDefinition(
            "spc",
            bool,
            "Whether self-position is considered in seeking mode.",
        ),
        ParameterDefinition(
            "cdc",
            float,
            "Fraction of dimensions changed in seeking mode.",
            minimum=0.0,
            maximum=1.0,
        ),
        ParameterDefinition(
            "srd",
            float,
            "Seeking range of the selected dimensions.",
            minimum=0.0,
            maximum=1.0,
        ),
        ParameterDefinition(
            "max_velocity",
            float,
            "Maximum tracing velocity.",
            minimum=0.0,
        ),
    )
)

CSO_DEFAULT_PARAMETERS = {
    "population_size": 30,
    "mixture_ratio": 0.1,
    "c1": 2.05,
    "smp": 3,
    "spc": True,
    "cdc": 0.85,
    "srd": 0.2,
    "max_velocity": 1.9,
}


def cso_algorithm_specification() -> AlgorithmSpecification:
    return AlgorithmSpecification(
        name="CSO",
        implementation="cso",
        parameter_schema=CSO_PARAMETER_SCHEMA,
        fixed_parameters=CSO_DEFAULT_PARAMETERS,
    )

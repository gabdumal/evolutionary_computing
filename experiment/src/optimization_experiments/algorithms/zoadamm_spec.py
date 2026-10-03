from __future__ import annotations

from ..core.models import AlgorithmSpecification, ParameterDefinition, ParameterSchema


ZOADAMM_PARAMETER_SCHEMA = ParameterSchema(
    definitions=(
        ParameterDefinition("learning_rate", float, "Base step size alpha_t.", minimum=0.0),
        ParameterDefinition("beta1", float, "Momentum coefficient.", minimum=0.0, maximum=1.0),
        ParameterDefinition("beta2", float, "Second-moment coefficient.", minimum=0.0, maximum=1.0),
        ParameterDefinition("mu", float, "ZO smoothing parameter.", minimum=0.0),
        ParameterDefinition("q", int, "Number of random directions averaged per estimate.", minimum=1),
        ParameterDefinition("epsilon", float, "Inverse-square-root numerical stabilizer.", minimum=0.0),
        ParameterDefinition("decay_learning_rate", bool, "Use alpha_t = learning_rate / sqrt(t)."),
    )
)

# The reference experimental repository explicitly uses lr=0.001, q=10,
# mu=0.001 and learning-rate decay. beta1/beta2 are explicit Algorithm 1
# parameters; these defaults are the conventional adaptive-momentum values.
ZOADAMM_DEFAULT_PARAMETERS = {
    "learning_rate": 0.001,
    "beta1": 0.9,
    "beta2": 0.99,
    "mu": 0.001,
    "q": 10,
    "epsilon": 1e-12,
    "decay_learning_rate": True,
}


def zoadamm_algorithm_specification() -> AlgorithmSpecification:
    return AlgorithmSpecification(
        name="ZO-AdaMM",
        implementation="zoadamm",
        parameter_schema=ZOADAMM_PARAMETER_SCHEMA,
        fixed_parameters=ZOADAMM_DEFAULT_PARAMETERS,
    )

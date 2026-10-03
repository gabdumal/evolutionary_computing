from optimization_experiments.core import (
    AlgorithmSpecification,
    ParameterDefinition,
    ParameterSchema,
    resolve_configurations,
)


def test_grid_resolution():
    schema = ParameterSchema(
        (
            ParameterDefinition("a", int),
            ParameterDefinition("b", float),
        )
    )
    algorithm = AlgorithmSpecification("test", "test", schema)
    configurations = resolve_configurations(
        algorithm,
        {"a": (1, 2), "b": (0.1, 0.2, 0.3)},
    )
    assert len(configurations) == 6

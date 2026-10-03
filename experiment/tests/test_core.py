from optimization_experiments.core import (
    AlgorithmConfiguration,
    AlgorithmSpecification,
    BenchmarkScenario,
    EvaluationBudget,
    ParameterDefinition,
    ParameterSchema,
    SeedPlan,
    configuration_id,
    run_id,
)


def make_algorithm():
    schema = ParameterSchema(
        (
            ParameterDefinition("population_size", int, minimum=2),
            ParameterDefinition("mixture_ratio", float, minimum=0.0, maximum=1.0),
        )
    )
    algorithm = AlgorithmSpecification(
        name="test",
        implementation="test",
        parameter_schema=schema,
        fixed_parameters={"population_size": 10, "mixture_ratio": 0.1},
    )
    return algorithm


def test_configuration_id_is_deterministic():
    algorithm = make_algorithm()
    a = AlgorithmConfiguration(algorithm, {"population_size": 10, "mixture_ratio": 0.1})
    b = AlgorithmConfiguration(algorithm, {"population_size": 10, "mixture_ratio": 0.1})
    assert configuration_id(a) == configuration_id(b)


def test_run_id_changes_with_seed():
    algorithm = make_algorithm()
    configuration = AlgorithmConfiguration(
        algorithm,
        {"population_size": 10, "mixture_ratio": 0.1},
    )
    scenario = BenchmarkScenario(
        problem="Sphere",
        dimension=10,
        objective="sphere",
        lower_bound=-5.0,
        upper_bound=5.0,
    )
    budget = EvaluationBudget(10_000)

    from optimization_experiments.core.models import RunSpecification

    first = RunSpecification("x", configuration, scenario, 27, budget)
    second = RunSpecification("x", configuration, scenario, 32, budget)
    assert run_id(first) != run_id(second)


def test_seed_plan_rejects_duplicates():
    try:
        SeedPlan((27, 27))
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate seeds should be rejected.")


def test_algorithm_specification_allows_partial_fixed_parameters():
    schema = ParameterSchema(
        (
            ParameterDefinition("a", int),
            ParameterDefinition("b", float),
        )
    )
    algorithm = AlgorithmSpecification(
        "test",
        "test",
        schema,
        fixed_parameters={"a": 1},
    )
    assert algorithm.fixed_parameters["a"] == 1

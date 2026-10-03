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
from optimization_experiments.core.models import RunSpecification


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
        fixed_parameters={
            "population_size": 10,
            "mixture_ratio": 0.1,
        },
    )
    return algorithm


def make_run(seed: int):
    algorithm = make_algorithm()
    configuration = AlgorithmConfiguration(
        algorithm=algorithm,
        parameters=dict(algorithm.fixed_parameters),
    )
    scenario = BenchmarkScenario(
        problem="Sphere",
        dimension=10,
        objective="sphere",
        lower_bound=-5.0,
        upper_bound=5.0,
    )
    return RunSpecification(
        experiment_id="exp_test",
        experiment_name="test",
        algorithm=configuration,
        scenario=scenario,
        seed=seed,
        budget=EvaluationBudget(1_000),
    )


def test_configuration_id_is_deterministic():
    algorithm = make_algorithm()
    first = AlgorithmConfiguration(
        algorithm,
        dict(algorithm.fixed_parameters),
    )
    second = AlgorithmConfiguration(
        algorithm,
        dict(algorithm.fixed_parameters),
    )
    assert configuration_id(first) == configuration_id(second)


def test_run_id_changes_with_seed():
    assert run_id(make_run(27)) != run_id(make_run(32))


def test_seed_plan_rejects_duplicates():
    try:
        SeedPlan((27, 27))
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate seeds should be rejected.")


def test_integer_parameter_rejects_bool():
    schema = ParameterSchema((ParameterDefinition("x", int),))
    try:
        schema.validate({"x": True})
    except TypeError:
        pass
    else:
        raise AssertionError("bool must not be accepted as an integer parameter.")

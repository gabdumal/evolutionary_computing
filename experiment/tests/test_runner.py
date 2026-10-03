from pathlib import Path

from optimization_experiments.algorithms import default_registry
from optimization_experiments.algorithms.cso import cso_algorithm_specification
from optimization_experiments.artifacts import ArtifactStore
from optimization_experiments.core import (
    AlgorithmConfiguration,
    BenchmarkScenario,
    EvaluationBudget,
    ExperimentSpecification,
    SeedPlan,
)
from optimization_experiments.execution import ExperimentRunner
from optimization_experiments.validation import validate_experiment


def test_fake_runner_round_trip(tmp_path: Path):
    algorithm = cso_algorithm_specification()
    fake_algorithm = type(algorithm)(
        name=algorithm.name,
        implementation="fake",
        parameter_schema=algorithm.parameter_schema,
        fixed_parameters=dict(algorithm.fixed_parameters),
    )
    configuration = AlgorithmConfiguration(
        algorithm=fake_algorithm,
        parameters=dict(fake_algorithm.fixed_parameters),
    )

    experiment = ExperimentSpecification(
        name="fake-smoke",
        algorithm=fake_algorithm,
        scenarios=(
            BenchmarkScenario(
                problem="Sphere",
                dimension=3,
                objective="sphere",
                lower_bound=-5,
                upper_bound=5,
            ),
        ),
        configurations=(configuration,),
        seeds=SeedPlan((27, 32)),
        budget=EvaluationBudget(10),
    )

    registry = default_registry()
    registry.register(
        "fake",
        "optimization_experiments.algorithms.testing.create_fake_adapter",
    )

    store = ArtifactStore(tmp_path, experiment)
    report = ExperimentRunner(
        store,
        registry,
        max_workers=1,
    ).run(experiment)

    validation = validate_experiment(experiment, store)
    assert report.completed_run_count == 2
    assert validation.valid
    assert len(store.completed_run_ids()) == 2

    try:
        import pyarrow  # noqa: F401
    except ImportError:
        return

    assert store.materialize_index().is_file()


def test_runner_does_not_submit_more_than_worker_limit(tmp_path: Path, monkeypatch):
    from optimization_experiments.execution import runner as runner_module

    algorithm = cso_algorithm_specification()
    fake_algorithm = type(algorithm)(
        name=algorithm.name,
        implementation="fake",
        parameter_schema=algorithm.parameter_schema,
        fixed_parameters=dict(algorithm.fixed_parameters),
    )
    configuration = AlgorithmConfiguration(
        algorithm=fake_algorithm,
        parameters=dict(fake_algorithm.fixed_parameters),
    )
    scenario = BenchmarkScenario(
        problem="Sphere",
        dimension=3,
        objective="sphere",
        lower_bound=-5,
        upper_bound=5,
    )
    experiment = ExperimentSpecification(
        name="bounded-runner",
        algorithm=fake_algorithm,
        scenarios=(scenario,),
        configurations=(configuration,),
        seeds=SeedPlan(tuple(range(10))),
        budget=EvaluationBudget(10),
    )

    registry = default_registry()
    registry.register(
        "fake",
        "optimization_experiments.algorithms.testing.create_fake_adapter",
    )

    class TrackingExecutor:
        max_in_flight = 0
        current = 0

        def __init__(self, *, max_workers, mp_context):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args):
            TrackingExecutor.current += 1
            TrackingExecutor.max_in_flight = max(
                TrackingExecutor.max_in_flight,
                TrackingExecutor.current,
            )
            from concurrent.futures import Future
            future = Future()
            try:
                future.set_result(fn(*args))
            finally:
                TrackingExecutor.current -= 1
            return future

    monkeypatch.setattr(runner_module, "ProcessPoolExecutor", TrackingExecutor)

    store = ArtifactStore(tmp_path, experiment)
    report = ExperimentRunner(
        store,
        registry,
        max_workers=2,
        start_method="forkserver",
    ).run(experiment)

    assert report.completed_run_count == 10
    assert TrackingExecutor.max_in_flight <= 2

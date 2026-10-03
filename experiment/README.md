# optimization-experiments

Initial API for reproducible optimization experiments.

## Design goals

- Python 3.14+
- deterministic experiment/configuration/scenario/run identities
- explicit function-evaluation budgets
- CPU time as the scientific timing metric
- independent `configuration × scenario × seed` runs
- resumable filesystem artifacts
- Parquet materialization for analysis throughput
- algorithm adapters so CSO, ZO-AdaMM, and future hybrids share the same runner
- problem-specific analysis without cross-problem hyperparameter averaging
- thin experiment wrappers

## Parameter model

`ParameterSchema` defines the complete parameter contract of an algorithm.
`AlgorithmConfiguration` contains one fully resolved configuration. The grid
resolver creates configurations before execution, so every persisted run has
the exact parameters that were actually used.

`AlgorithmSpecification.fixed_parameters` is optional metadata/default
information; it is not a substitute for a resolved configuration.

## Current package layout

```text
src/optimization_experiments/
├── core/
│   ├── models.py
│   ├── ids.py
│   └── parameters.py
├── algorithms/
│   ├── base.py
│   └── callable.py
├── execution/
│   └── runner.py
├── artifacts/
│   └── store.py
├── validation/
│   └── validate.py
├── analysis/
│   └── runs.py
├── experiments/
│   └── benchmark.py
└── benchmarks.py
```

## Scientific protocol currently encoded

The default benchmark scenario factory contains:

- HappyCat
- Rosenbrock
- Schwefel
- dimensions 10 and 100

The API intentionally does not encode a particular ZO-AdaMM hyperparameter grid yet. That belongs in the algorithm-specific experiment definition after the algorithm adapter is implemented.

## Important boundary

`AlgorithmAdapter` is the only execution boundary that needs to know how an optimizer works. The experiment runner only knows how to schedule independent runs and persist `RunResult`.

The intended future shape is:

```text
ExperimentSpecification
        │
        ▼
   ExperimentRunner
        │
        ▼
 AlgorithmAdapter
   ├── CSO / NiaPy
   ├── ZO-AdaMM
   └── Hybrid
        │
        ▼
     RunResult
        │
        ├── objective
        ├── function evaluations
        ├── iterations
        ├── CPU seconds
        └── convergence trace
```

## CPU-time policy

`wall-clock time` is deliberately not part of `RunResult`. CPU time is measured inside the worker process with `time.process_time()` and is the scientific timing metric for this project.

## Next implementation step

Implement the concrete CSO/NiaPy adapter and verify a small deterministic smoke campaign against the old CSO results before running the complete experiment again. Then implement ZO-AdaMM behind the same adapter contract.

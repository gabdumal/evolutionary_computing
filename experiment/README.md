# optimization-experiments

Reusable infrastructure for reproducible stochastic and zero-order optimization
experiments.

## Architecture

```text
ExperimentSpecification
        │
        ▼
   ExperimentRunner
        │
        ▼
 AlgorithmRegistry
        │
        ├── CSO → NiaPyAlgorithmAdapter
        ├── ZO-AdaMM → future adapter
        └── Hybrid → future adapter
        │
        ▼
     RunResult
        │
        ├── best objective / solution
        ├── function evaluations
        ├── iterations
        ├── CPU seconds
        └── convergence vs function evaluations
        │
        ▼
 ArtifactStore
        │
        ├── experiment.json
        ├── runs/*.json
        ├── convergence/*.npz
        ├── failures/*.json
        └── analysis/*.parquet / *.csv
```

## API contracts

The runner does not know how an optimization algorithm works. An
`AlgorithmAdapter` receives one immutable `RunSpecification` and returns one
`RunResult`.

The registry stores **import paths**, not arbitrary closures or lambda
functions. This makes adapter construction safe across Python worker
processes.

The runner keeps only a bounded number of futures in flight (at most the
configured worker count), so large campaigns do not create one pending Future
object per run.

Function-evaluation budget is explicit and is the primary cross-algorithm
resource metric.

## CSO

The CSO adapter is a thin wrapper over NiaPy's
`CatSwarmOptimization(population_size, mixture_ratio, c1, smp, spc, cdc, srd,
max_velocity, ...)`.

The project targets NiaPy 2.7.1+ and Python 3.14+.

## Benchmarks

The default scenarios are:

- HappyCat, D=10 and D=100, [-100, 100]
- Rosenbrock, D=10 and D=100, [-30, 30]
- Schwefel, D=10 and D=100, [-500, 500]

These domains match the NiaPy benchmark definitions used as the baseline.

## Smoke campaign

Run:

```bash
python -m optimization_experiments.cli cso-smoke --workers 1
```

or after installation:

```bash
opt-experiments cso-smoke --workers 1
```

The smoke campaign contains one CSO configuration, 6 benchmark scenarios,
3 seeds and a 1,000-function-evaluation budget, for 18 independent runs.

## Analysis

The canonical run table contains one row per run with:

```text
run_id
experiment_id
algorithm_id
algorithm
configuration_id
scenario_id
objective_function
problem
dimension
seed
<resolved algorithm parameters>
calculated_value
function_evaluations
iterations
cpu_seconds
```

Statistics aggregate by configuration/scenario and provide:

```text
min
max
mean
std
```

for objective value, function evaluations, iterations and CPU time.

The analysis index is built from the lightweight run JSON metadata. Convergence
arrays stored in `.npz` files are not loaded just to build `run_results.csv` or
`runs.parquet`; they remain available for dedicated convergence analysis.

## Scientific timing policy

The scientific timing metric is CPU time measured inside the worker with
`time.process_time()`. The framework deliberately keeps wall-clock timing out
of the algorithm result so queueing and scheduling overhead do not become an
algorithm metric.

## Environment provenance

`experiment.json` records Python, platform, machine, NumPy, pandas, pyarrow,
NiaPy and the current Git commit when available. Environment metadata does not
enter the scientific experiment identity.

## Next step

After the CSO smoke campaign is verified locally with NiaPy 2.7.1+, the next
adapter can implement ZO-AdaMM without modifying the execution, artifact,
validation or statistical APIs.

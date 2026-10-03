# Optimization Experiments API

Reusable experiment infrastructure for benchmark-based optimization studies.

## Current CSO campaign

The complete CSO campaign uses:

- 4,374 full-factorial configurations;
- 6 benchmark scenarios (HappyCat, Rosenbrock, Schwefel at dimensions 10 and 100);
- 3 seeds (27, 32, 59);
- 10,000 function evaluations per run;
- 78,732 independent runs.

The CSO adapter uses NiaPy's native implementations for the three standard
benchmarks whenever the scenario exactly matches their documented default
semantics. This keeps the hot objective-evaluation path out of the project's
Python dispatcher.

## Execution performance

Artifact persistence is optimized for long-running campaigns by default:

- atomic file replacement is retained;
- per-run `fsync` is disabled by default;
- convergence arrays are stored as uncompressed `.npz` by default;
- convergence checksums are retained;
- only a bounded number of worker futures is kept in flight.

For maximum filesystem durability, use `--durable-artifacts`.
For smaller convergence artifacts at the cost of additional CPU, use
`--compress-convergence`.

The console reports elapsed time, run throughput, ETA, accumulated CPU time,
accumulated algorithm wall time, average persistence time, active workers,
and the most recently completed run.

## Commands

Generate the deterministic CSO configuration manifest:

```bash
python -m optimization_experiments.cli cso-grid-manifest \
  --output cso_configuration_grid.csv
```

Run the complete three-seed CSO campaign:

```bash
python -m optimization_experiments.cli cso-grid --workers 8
```

For Linux, the process start method can be selected explicitly:

```bash
python -m optimization_experiments.cli cso-grid \
  --workers 8 \
  --start-method fork
```

The default remains `forkserver` for conservative behavior. Existing completed
runs from an experiment are resumed only when the experiment identity matches.
The optimized CSO campaign includes a backend marker in its identity so runs
from the previous generic-objective implementation are not mixed into the new
campaign.


## Execution performance

The process pool uses bounded scheduling and persists authoritative run/convergence artifacts inside the worker that executed the run. This avoids serializing the full convergence trace back to the parent process and avoids making the parent a single-file-system writer bottleneck. `--durable-artifacts` enables fsync, while convergence compression remains opt-in with `--compress-convergence`.

For the three native NiaPy benchmarks used by the CSO campaign, the adapter uses NiaPy's native benchmark implementations in the objective-evaluation hot path and falls back to the project's generic objective dispatcher only for scenarios whose semantics do not exactly match a native benchmark.


## Recommended full CSO execution

For the complete three-seed campaign, use:

```bash
python -m optimization_experiments.cli cso-grid --workers 8
```

The default execution is non-durable for throughput. Use `--durable-artifacts` only when fsync-on-each-artifact is required. Use `--compress-convergence` only when reduced storage size is worth the additional CPU cost.

## Current ZO-AdaMM campaign

The complete three-seed ZO-AdaMM campaign uses 864 full-factorial configurations,
6 benchmark scenarios (HappyCat, Rosenbrock, Schwefel at dimensions 10 and 100),
3 seeds (27, 32, 59), and 10,000 function evaluations per run, for 15,552 runs.

The tuned parameters are:

- `learning_rate`: 0.001, 0.003, 0.01, 0.03
- `beta1`: 0.0, 0.5, 0.9
- `beta2`: 0.1, 0.5, 0.99
- `mu`: 0.0001, 0.001, 0.01
- `q`: 1, 5, 10, 20
- `decay_learning_rate`: false, true

`epsilon=1e-12` is fixed as a numerical stabilizer and is not treated as a
scientific hyperparameter. The reference implementation repository uses
`lr=0.001`, `q=10`, `mu=0.001`, and learning-rate decay in its main experiment
script. The paper also explicitly discusses a practical preference for smaller
`beta2` and identifies `beta1,t=0` as an important constrained nonconvex special
case.

Generate the deterministic ZO-AdaMM configuration manifest:

```bash
python -m optimization_experiments.cli zoadamm-grid-manifest \
  --output zoadamm_configuration_grid.csv
```

Run the complete three-seed campaign:

```bash
python -m optimization_experiments.cli zoadamm-grid --workers 12
```

The campaign analysis writes per-run results, three-seed scenario statistics,
problem-level configuration summaries, parameter-level effects, dimension-specific
parameter effects, and both problem-level and problem×dimension selected
configurations.

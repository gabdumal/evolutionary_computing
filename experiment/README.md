# Optimization Experiments API

Reusable, reproducible infrastructure for benchmark-based optimization experiments.
The same execution, artifact, validation and analysis layers are used by CSO and
ZO-AdaMM.

## Requirements

- Python 3.14+
- NiaPy 2.7.1+
- NumPy, pandas and PyArrow

Install in the project virtual environment with:

```bash
python -m pip install -e ".[dev]"
```

## Experimental design

### CSO

The complete CSO campaign uses 4,374 full-factorial configurations, 6 benchmark
scenarios, 3 seeds `(27, 32, 59)` and 10,000 function evaluations per run:

```text
4,374 configurations × 6 scenarios × 3 seeds = 78,732 runs
```

The six scenarios are HappyCat, Rosenbrock and Schwefel at dimensions 10 and 100.

### ZO-AdaMM

The complete ZO-AdaMM campaign uses 864 configurations, the same 6 benchmark
scenarios, the same 3 seeds and the same 10,000-FE budget:

```text
864 configurations × 6 scenarios × 3 seeds = 15,552 runs
```

Its factorial grid varies `learning_rate`, `beta1`, `beta2`, `mu`, `q` and
`decay_learning_rate`; numerical `epsilon` is fixed at `1e-12`.

Function evaluations are the primary cross-algorithm effort budget. Iteration
counts and CPU time are secondary measurements.

## Execution and persistence

The runner uses bounded multiprocessing and worker-side persistence so large
campaigns do not serialize every convergence trace through the parent process.
The default filesystem mode favors throughput: per-run `fsync` is off and
convergence arrays are uncompressed `.npz`. Use `--durable-artifacts` when
filesystem durability is more important than throughput; use
`--compress-convergence` when disk space is more important than CPU time.

The console reports elapsed wall time, throughput, ETA, accumulated CPU time,
algorithm wall time and persistence time.

Completed runs are resumable. A run is skipped only when its deterministic
experiment/run identity already exists in the corresponding experiment
artifact directory.

## All CLI commands

All commands can be invoked either as:

```bash
python -m optimization_experiments.cli <command> ...
```

or, after installation, as:

```bash
opt-experiments <command> ...
```

### `cso-smoke`

Runs 18 small CSO runs: one configuration × 6 scenarios × 3 seeds, with a
1,000-FE budget. Use it after installation to verify the full execution,
persistence and validation pipeline.

```bash
python -m optimization_experiments.cli cso-smoke --workers 1
```

Useful execution options are shared with the full campaigns:

```text
--artifact-root PATH
--workers N
--start-method {fork,forkserver,spawn}
--no-analysis
--durable-artifacts
--compress-convergence
```

### `cso-grid-manifest`

Generates the deterministic list of all 4,374 CSO configurations without
executing optimization runs.

```bash
python -m optimization_experiments.cli cso-grid-manifest \
  --output cso_configuration_grid.csv
```

### `cso-grid`

Runs the complete 78,732-run CSO campaign using the 10,000-FE budget.

```bash
python -m optimization_experiments.cli cso-grid --workers 8
```

For Linux, the process start method can be selected explicitly:

```bash
python -m optimization_experiments.cli cso-grid \
  --workers 8 \
  --start-method forkserver
```

Use `--no-analysis` when you want to execute only the campaign and postpone
analysis. Existing completed runs are still reused.

### `zoadamm-smoke`

Runs 18 small ZO-AdaMM runs: one configuration × 6 scenarios × 3 seeds, with a
1,000-FE budget.

```bash
python -m optimization_experiments.cli zoadamm-smoke --workers 1
```

### `zoadamm-grid-manifest`

Generates the deterministic list of all 864 ZO-AdaMM configurations without
executing optimization runs.

```bash
python -m optimization_experiments.cli zoadamm-grid-manifest \
  --output zoadamm_configuration_grid.csv
```

### `zoadamm-grid`

Runs the complete 15,552-run ZO-AdaMM campaign using the same 10,000-FE budget
as CSO.

```bash
python -m optimization_experiments.cli zoadamm-grid --workers 8
```

The same `--workers`, `--start-method`, `--no-analysis`, `--durable-artifacts`
and `--compress-convergence` options are supported.

### `cso-analyze`

Analyzes an already completed CSO experiment without executing any new
optimization runs. Supply the exact experiment ID printed by the campaign.

```bash
python -m optimization_experiments.cli cso-analyze \
  --artifact-root _artifacts \
  --experiment-id <CSO_EXPERIMENT_ID>
```

The command validates the completed experiment first and then generates the
four user-facing analysis CSVs.

### `zoadamm-analyze`

The ZO-AdaMM equivalent of `cso-analyze`.

```bash
python -m optimization_experiments.cli zoadamm-analyze \
  --artifact-root _artifacts \
  --experiment-id <ZOADAMM_EXPERIMENT_ID>
```

### `compare`

Compares the completed CSO and ZO-AdaMM analyses without rerunning either
algorithm. Both experiments must already have `analysis/runs.parquet`.

```bash
python -m optimization_experiments.cli compare \
  --artifact-root _artifacts \
  --cso-experiment-id <CSO_EXPERIMENT_ID> \
  --zoadamm-experiment-id <ZOADAMM_EXPERIMENT_ID>
```

The comparison selects the best configuration independently for each
`algorithm × objective_function × dimension`, using the lowest mean objective
value over the three seeds. Ties are resolved by objective standard deviation,
mean CPU time and configuration ID.

The primary comparison outputs are:

- `algorithm_comparison_results.csv`: numerical aggregate table;
- `algorithm_comparison_table.csv`: formatted `mean ± std` table;
- `algorithm_comparison_wide.csv`: one row per objective function × dimension;
- `metadata.json`: comparison and selection rules.

The comparison uses CPU time as its reported execution-time metric.

## Analysis outputs

For each analyzed experiment, the default analysis writes exactly four
user-facing CSVs under `analysis/`.

### `run_results.csv`

One row per run:

```text
run_id
seed
algorithm
objective_function
dimension
configuration_id
<resolved parameters>
calculated_value
function_evaluations
iterations
cpu_seconds
```

This is the run-level source for all aggregate analyses.

### `configuration_results.csv`

One row per:

```text
algorithm × objective_function × dimension × configuration
```

The three seeds are aggregated. Every metric measured across seeds has both
`mean` and sample `std` (`ddof=1`):

```text
calculated_value_mean / calculated_value_std
function_evaluations_mean / function_evaluations_std
iterations_mean / iterations_std
cpu_seconds_mean / cpu_seconds_std
```

`seed_count` records how many seeds contributed to the row.

### `best_configuration_results.csv`

One row per best configuration for each `algorithm × objective_function ×
dimension` combination. Selection is performed **after aggregating the seeds**:
the configuration with the lowest `calculated_value_mean` is selected. The
row retains the complete configuration parameters and the `mean`/`std`
statistics already present in `configuration_results.csv`. If configurations
tie on the aggregated mean, all tied configurations are retained. No
individual seed is selected here.

### `parameter_effects.csv`

Measures marginal parameter effects independently for each
`algorithm × objective_function × dimension × parameter × parameter_value`.
The other hyperparameters are averaged over.

For each parameter level, the analysis first averages the configurations
carrying that level **within each seed**. It then computes the `mean` and
sample `std` across the executed seeds. Consequently, the reported `std` is
seed-to-seed variability, not variability among individual configurations.

The table includes:

```text
mean_calculated_value
std_calculated_value
seed_count
configuration_count
mean_normalized_effect
parameter_effect_range
best_parameter_level
```

`best_parameter_level` means the best **marginal level of that individual
parameter**. It is not the globally best configuration.

The normalized effect is 0 for the best parameter level and 1 for the worst
level within the corresponding parameter group.

## Intermediate and primary raw artifacts

`analysis/runs.parquet` is an intermediate analysis index created from the
lightweight run JSON metadata. It is not a second scientific source of truth;
`runs/*.json` remain the authoritative per-run records.

`convergence/*.npz` contains the best-so-far convergence trace versus function
evaluations. Convergence files are intentionally kept outside the default
CSV analysis pipeline and are not loaded just to make the four analysis CSVs.

`experiment.json` stores the experiment specification and environment
provenance. `failures/*.json` records failed runs without treating them as
completed runs.

## Scientific interpretation

`function_evaluations` is the primary search-effort metric shared by CSO and
ZO-AdaMM. A fair cross-algorithm comparison therefore uses the same FE budget,
not the same iteration count. CPU time is a secondary computational-cost
metric, while iterations describe the internal dynamics of each algorithm.

## CLI


### Analysis commands

```bash
python -m optimization_experiments.cli cso-analyze --experiment-id <CSO_EXPERIMENT_ID>
python -m optimization_experiments.cli zoadamm-analyze --experiment-id <ZOADAMM_EXPERIMENT_ID>
```

These commands do not execute new optimization runs. They reopen the completed experiment using the normal `ArtifactStore` constructor, validate the stored runs, and regenerate the four analysis CSVs. The supplied experiment ID must match the corresponding campaign specification.

```bash
python -m optimization_experiments.cli compare \
  --cso-experiment-id <CSO_EXPERIMENT_ID> \
  --zoadamm-experiment-id <ZOADAMM_EXPERIMENT_ID>
```

The comparison command reads the two `analysis/runs.parquet` indexes directly; it does not reconstruct an `ArtifactStore`.

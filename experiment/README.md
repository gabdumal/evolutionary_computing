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

### CSO → ZO-AdaMM hybrid

The hybrid is deliberately sequential and simple. CSO receives 80% of the
function-evaluation budget and explores the search space. Its best solution is
then passed as the initial point to ZO-AdaMM, which uses the remaining 20% for
refinement. The hybrid keeps the same total number of function evaluations as
the standalone methods.

The final campaign uses 6 validated configurations, one for each objective-function × dimension pair,
6 benchmark scenarios, 3 seeds `(27, 32, 59)` and 10,000 FEs per run:

```text
6 configurations × 6 benchmark scenarios × 3 seeds would overcount the design, so the
experiment binds exactly one validated configuration to each scenario:
6 scenario-specific configurations × 3 seeds = 18 runs
80,000 FEs CSO + 20,000 FEs ZO-AdaMM = 10,000 FEs/run
```

Each hybrid scenario uses the best CSO configuration and the best ZO-AdaMM
configuration selected independently in the standalone 3-seed validation.
The six objective-function × dimension pairs therefore have six resolved
hybrid parameter configurations; no generic CSO or ZO-AdaMM defaults are used.

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

### `hybrid-smoke`

Runs 18 small CSO → ZO-AdaMM smoke runs using an 80/20 FE split and the
validated component parameters for each objective-function × dimension pair.

```bash
python -m optimization_experiments.cli hybrid-smoke --workers 1
```

### `hybrid-campaign`

Runs the final 18-run CSO → ZO-AdaMM campaign with 10,000 FEs per run and
the validated component parameters for each objective-function × dimension pair.

```bash
python -m optimization_experiments.cli hybrid-campaign --workers 8
```

The hybrid uses 8,000 FEs for CSO followed by 2,000 FEs for ZO-AdaMM.

### `hybrid-analyze`

Regenerates the analysis artifacts for a completed hybrid campaign without
executing new runs.

```bash
python -m optimization_experiments.cli hybrid-analyze \
  --artifact-root _artifacts \
  --experiment-id <HYBRID_EXPERIMENT_ID>
```

### `cso-analyze`

Analyzes an already completed CSO experiment without executing any new
optimization runs. Supply the exact experiment ID printed by the campaign.

```bash
python -m optimization_experiments.cli cso-analyze \
  --artifact-root _artifacts \
  --experiment-id <CSO_EXPERIMENT_ID>
```

The command validates the completed experiment first and then generates the
user-facing analysis CSVs.

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

For each analyzed experiment, the default analysis writes exactly five
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

Contains only the observed marginal statistics for each
`algorithm × objective_function × dimension × parameter × parameter_value`.
The other hyperparameters are averaged over.

For each parameter level, the analysis first averages the configurations
carrying that level **within each seed**. It then computes the `mean` and
sample `std` across the executed seeds. Consequently, the reported `std` is
seed-to-seed variability, not variability among individual configurations.

The table contains only:

```text
algorithm
objective_function
dimension
parameter
parameter_value
mean_calculated_value
std_calculated_value
seed_count
configuration_count
```

It deliberately does **not** contain best/worst levels, effect ranges,
normalization, rankings, or other cross-level interpretation.

### `parameter_effect_summary.csv`

Consolidates the level-wise parameter analysis to one row for each
`algorithm × objective_function × dimension × parameter` combination. It
contains:

```text
level_count
best_marginal_parameter_value
best_marginal_mean
best_marginal_std
worst_marginal_parameter_value
worst_marginal_mean
worst_marginal_std
parameter_effect_range
normalized_parameter_effect
normalized_parameter_effect_percent
```

`best_marginal_parameter_value` is the best level of that individual
parameter after marginalizing over the other hyperparameters. It is **not**
the globally best configuration.

For minimization, the absolute effect is:

```text
parameter_effect_range = worst_marginal_mean - best_marginal_mean
```

The normalized effect is the same range divided by the absolute mean
objective value of the complete `algorithm × objective_function × dimension`
scenario. This normalization allows effect magnitudes to be compared across
benchmark functions with different objective-value scales. The percentage
column is the same quantity multiplied by 100.

If a parameter has only one evaluated level, its sensitivity is **not
measurable** from that experiment, so the effect and normalized effect are
`NaN` rather than zero.

## Intermediate and primary raw artifacts

`analysis/runs.parquet` is an intermediate analysis index created from the
lightweight run JSON metadata. It is not a second scientific source of truth;
`runs/*.json` remain the authoritative per-run records.

`convergence/*.npz` contains the best-so-far convergence trace versus function
evaluations. Convergence files are intentionally kept outside the default
CSV analysis pipeline and are not loaded just to make the analysis CSVs.

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

These commands do not execute new optimization runs. They reopen the completed experiment using the normal `ArtifactStore` constructor, validate the stored runs, and regenerate the analysis CSVs. The supplied experiment ID must match the corresponding campaign specification.

```bash
python -m optimization_experiments.cli compare \
  --cso-experiment-id <CSO_EXPERIMENT_ID> \
  --zoadamm-experiment-id <ZOADAMM_EXPERIMENT_ID>
```

The comparison command reads the two `analysis/runs.parquet` indexes directly; it does not reconstruct an `ArtifactStore`.

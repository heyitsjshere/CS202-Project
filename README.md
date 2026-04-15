# CS202-Project

RCPSP solver project with multiple heuristic solvers and one exact optimal solver.

## Quick Start

Run any benchmark in parallel with workers:

```bash
python3 all_solver_benchmarks/benchmark_solver_1.py --dataset sm_j10 --workers 4
python3 all_solver_benchmarks/benchmark_solver_optimal.py --dataset sm_j10 --time-limit 10 --workers 8
```

## Run Benchmarks with Workers

All benchmark scripts support parallel execution with `--workers` (or `-w`).

Examples:

```bash
python3 all_solver_benchmarks/benchmark_solver_1.py --dataset sm_j10 --workers 4
python3 all_solver_benchmarks/benchmark_solver_2.py --dataset sm_j20 --time-limit 2 --workers 4
python3 all_solver_benchmarks/benchmark_solver_3.py --dataset sm_j20 --time-limit 2 --workers 8
python3 all_solver_benchmarks/benchmark_solver_4.py --dataset sm_j20 --time-limit 2 --workers 8
python3 all_solver_benchmarks/benchmark_solver_optimal.py --dataset sm_j10 --time-limit 10 --workers 8
```

Useful optional flags:

- `--first-n` to limit how many instances are run.
- `--time-limit` for per-instance solve time.
- `--seed` and `--starts` where supported by heuristic solvers.

## Standardized CSV Results

All benchmark scripts now log every instance (not only feasible ones) into CSV files under `results/`.

Default files:

- `benchmark_solver_1.py` -> `results/solver_1_results.csv`
- `benchmark_solver_2.py` -> `results/solver_2_results.csv`
- `benchmark_solver_3.py` -> `results/solver_3_results.csv`
- `benchmark_solver_4.py` -> `results/solver_4_results.csv`
- `benchmark_solver_optimal.py` -> `results/solver_optimal_results.csv`

Each CSV row includes status values.

Typical heuristic statuses:

- `feasible`
- `true_infeasible`
- `heuristic_failed`
- `error`

Typical exact/optimal statuses:

- `feasible_optimal`
- `feasible_not_proven`
- `true_infeasible`
- `heuristic_failed`

CSV columns:

`dataset, instance, solver, status, makespan, time_ms, time_limit_s, workers, seed, starts`

Optional override:

```bash
python3 all_solver_benchmarks/benchmark_solver_1.py --dataset sm_j10 --workers 4 --csv-file results/custom.csv
python3 all_solver_benchmarks/benchmark_solver_optimal.py --dataset sm_j20 --workers 8 --csv-file results/optimal_custom.csv
```

Backward compatibility:

- `--log-file` is still accepted as a legacy alias.

## More Details

For detailed solver and benchmark usage, see `all_solvers/README.txt`.
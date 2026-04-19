# CS202-Project

## CS202 Report Team

- Sim Kay Wee — kaywee.sim.2024@computing.smu.edu.sg
- Noah Sau Cheng Kuan — noah.sau.2024@computing.smu.edu.sg
- Seah Min-Yi — minyi.seah.2024@computing.smu.edu.sg
- Srividya Ravi Sivashankar — srividya.rs.2024@computing.smu.edu.sg
- Lim Junsheng — js.lim.2024@computing.smu.edu.sg

RCPSP solver project focused on `solver_3` and `solver_optimal`.

## Project Summary

This project solves Resource-Constrained Project Scheduling Problem (RCPSP) instances from two datasets (`sm_j10` and `sm_j20`) using `solver_3` (heuristic) and `solver_optimal` (exact). The workflow is: parse instance -> run selected solver -> validate schedule -> record per-instance output to CSV for analysis.

Core folders:

- `all_solvers/`: solver implementations (`solver_3`, `solver_optimal`).
- `all_solver_benchmarks/`: batch benchmark runners with multiprocessing workers and uniform CSV output.
- `utils/`: shared parser and helper modules used by benchmarks and solver components.
- `sm_j10/`, `sm_j20/`: benchmark instance datasets.
- `results/`: generated CSV outputs for each solver run.

## Quick Start

Run any benchmark in parallel with workers:

```bash
python3 all_solver_benchmarks/benchmark_solver_3.py --dataset sm_j10 --workers 4
python3 all_solver_benchmarks/benchmark_solver_optimal.py --dataset sm_j10 --time-limit 10 --workers 8
```

## Run Benchmarks with Workers

All benchmark scripts support parallel execution with `--workers` (or `-w`).

Examples:

```bash
python3 all_solver_benchmarks/benchmark_solver_3.py --dataset sm_j20 --time-limit 30 --workers 8
python3 all_solver_benchmarks/benchmark_solver_optimal.py --dataset sm_j10 --time-limit 30 --workers 8
```

Useful optional flags:

- `--first-n` to limit how many instances are run.
- `--time-limit` for per-instance solve time.
- `--seed` and `--starts` where supported by heuristic solvers.

## Standardized CSV Results

All benchmark scripts now log every instance (not only feasible ones) into CSV files under `results/`.

Default files:

- `benchmark_solver_3.py` -> `results/solver_3_results.csv`
- `benchmark_solver_optimal.py` -> `results/solver_optimal_sm_j10_results.csv` or `results/solver_optimal_sm_j20_results.csv`

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
python3 all_solver_benchmarks/benchmark_solver_3.py --dataset sm_j10 --workers 4 --csv-file results/custom.csv
python3 all_solver_benchmarks/benchmark_solver_optimal.py --dataset sm_j20 --workers 8 --csv-file results/optimal_custom.csv
```

Backward compatibility:

- `--log-file` is still accepted as a legacy alias.

## More Details

For detailed solver and benchmark usage, see `all_solvers/README.txt`.
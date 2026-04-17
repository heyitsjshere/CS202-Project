all_solvers folder
==================

This folder contains copies of the four solver variants (numbered):
- solver_1.py  (from solver.py)
- solver_2.py  (from solver2_fixed.py)
- solver_3.py
- solver_4.py

And one exact-mode solver wrapper:
- solver_optimal.py

Usage examples (from project root):

python all_solvers/solver_1.py sm_j10/PSP1.SCH
python all_solvers/solver_2.py sm_j10/PSP1.SCH --time-limit 2
python all_solvers/solver_3.py sm_j10/PSP1.SCH
python all_solvers/solver_4.py sm_j10/PSP1.SCH
python all_solvers/solver_optimal.py sm_j10/PSP1.SCH --time-limit 10
python all_solvers/solver_optimal.py sm_j10/PSP1.SCH --time-limit 10 --require-proof


Benchmark folder
================

New folder: all_solver_benchmarks/

- benchmark_solver_1.py
- benchmark_solver_2.py
- benchmark_solver_3.py
- benchmark_solver_4.py
- benchmark_solver_optimal.py

Examples:

python all_solver_benchmarks/benchmark_solver_1.py --dataset sm_j10
python all_solver_benchmarks/benchmark_solver_2.py --dataset sm_j20 --time-limit 2
python all_solver_benchmarks/benchmark_solver_3.py --dataset sm_j20 --time-limit 2
python all_solver_benchmarks/benchmark_solver_4.py --dataset sm_j20 --time-limit 2
python all_solver_benchmarks/benchmark_solver_optimal.py --dataset sm_j10 --time-limit 10


Strict fairness protocol (recommended for reporting)
====================================================

Use exactly the same setup across heuristic solvers 1/2/3/4:

1) same --dataset
2) same --first-n
3) same --time-limit (e.g., 2 seconds)
4) fixed --seed where supported

Example fair run on J20 first 100 instances:

python all_solver_benchmarks/benchmark_solver_1.py --dataset sm_j20 --first-n 100 --time-limit 2 --seed 42
python all_solver_benchmarks/benchmark_solver_2.py --dataset sm_j20 --first-n 100 --time-limit 2
python all_solver_benchmarks/benchmark_solver_3.py --dataset sm_j20 --first-n 100 --time-limit 2 --seed 42
python all_solver_benchmarks/benchmark_solver_4.py --dataset sm_j20 --first-n 100 --time-limit 2 --seed 42

Optimal solver is reported separately (different objective class: proof-capable exact search):

python all_solver_benchmarks/benchmark_solver_optimal.py --dataset sm_j20 --first-n 100 --time-limit 10


Which solver is best?
=====================

It depends on your goal:

- Best speed-quality balance (recommended default): solver_3.py
- Best heuristic quality (closest to optimal, usually slower): solver_4.py
- Most robust standalone style / parser-flexibility style: solver_2.py
- Fast baseline: solver_1.py
- True optimal proof attempts: solver_optimal.py

Practical recommendation for coursework runs:

1) Use solver_3.py for full J10/J20 throughput runs
2) Use solver_4.py on smaller subsets when you want stronger quality
3) Use solver_optimal.py only for spot checks / proven-optimal reference


Differences between solvers
===========================

solver_1.py
- Baseline multistart SGS heuristic
- Fastest/simple baseline behavior
- Good for quick sanity runs

solver_2.py
- Standalone-style solver copied from solver2_fixed.py
- Strong validation/parser behavior, process-driven style
- Usually slower due to heavier workflow

solver_3.py
- Portfolio + multistart + local search + double-justification
- Approximation-oriented and early-stop aware
- Usually best practical tradeoff

solver_4.py
- Hybrid metaheuristic (ALNS + GA-style crossover/mutation + path relinking + tabu)
- Strongest search intensity among heuristics
- Better quality potential, but more runtime overhead

solver_optimal.py
- Uses exact branch-and-bound from solver.py
- Can prove optimal on easier/smaller instances
- Not scalable for large sets under tight limits




Multithreading + Results CSV
============================

Parallel mode is available in all benchmark scripts using --workers (or -w).

Examples:

python3 all_solver_benchmarks/benchmark_solver_1.py --dataset sm_j10 --workers 4
python3 all_solver_benchmarks/benchmark_solver_2.py --dataset sm_j20 --time-limit 2 --workers 4
python3 all_solver_benchmarks/benchmark_solver_3.py --dataset sm_j20 --time-limit 2 --workers 8
python3 all_solver_benchmarks/benchmark_solver_4.py --dataset sm_j20 --time-limit 2 --workers 8
python3 all_solver_benchmarks/benchmark_solver_optimal.py --dataset sm_j10 --time-limit 10 --workers 8

Default CSV behavior:

- CSVs are automatically written under results/
- benchmark_solver_1.py -> results/solver_1_results.csv
- benchmark_solver_2.py -> results/solver_2_results.csv
- benchmark_solver_3.py -> results/solver_3_results.csv
- benchmark_solver_4.py -> results/solver_4_results.csv
- benchmark_solver_optimal.py -> results/solver_optimal_sm_j10_results.csv or results/solver_optimal_sm_j20_results.csv

All instances are recorded to CSV, including statuses such as:

- feasible
- true_infeasible
- heuristic_failed
- error
- feasible_optimal
- feasible_not_proven

Optional override:

python3 all_solver_benchmarks/benchmark_solver_1.py --dataset sm_j10 --workers 4 --csv-file results/custom.csv

Legacy flag compatibility:

- --log-file is still accepted as an alias.

CSV columns:

dataset, instance, solver, status, makespan, time_ms, time_limit_s, workers, seed, starts

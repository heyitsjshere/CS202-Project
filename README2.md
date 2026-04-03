# RCPSP Solver Usage Guide

This guide explains exactly what to run for each goal.

---

## 1) Where to run commands

Run in the folder with the j10 and j20 folders
---

## 2) Quick command cheat-sheet

## Exact commands to test what

Run all j10 (heuristic benchmark):

```bash
python benchmark_j10.py
```

Run all j20 (heuristic benchmark):

```bash
python benchmark_j20.py
```

Run all j10 (optimal/proof benchmark):

```bash
python benchmark_optimal_j10.py
```

Run all j20 (optimal/proof benchmark):

```bash
python benchmark_optimal_j20.py
```

Test one instance in assignment output format (jobs 1..N start times):

```bash
python main.py sm_j10/PSP1.SCH
```

or

```bash
python main.py sm_j20/PSP1.SCH
```

Test all instances using `main.py` output format:

```bash
for f in sm_j10/PSP*.SCH; do python main.py "$f"; done
for f in sm_j20/PSP*.SCH; do python main.py "$f"; done
```

### Dedicated scripts (no path edits needed)

Heuristic j10:

```bash
python benchmark_j10.py
```

Optimal j10:

```bash
python benchmark_optimal_j10.py
```

Heuristic j20:

```bash
python benchmark_j20.py
```

Optimal j20:

```bash
python benchmark_optimal_j20.py
```

## A. Fast scalable run (recommended for larger instances like `sm_j20`)

```bash
python benchmark.py --dataset sm_j20 --repeat 1 --warmup 0 --starts 30 --seed 42
```

Use this when you want good schedules quickly.

## B. Exact/proof run (tries to prove optimality)

```bash
python benchmark_optimal.py --dataset sm_j20 --repeat 1 --warmup 0 --optimal-time-limit 10
```

Use this when you need optimality proof attempts.

## C. Single instance output in assignment format (job 1..N start times)

Heuristic:

```bash
python main.py sm_j20/PSP1.SCH
```

If infeasible, `main.py` prints `-1`.

---

## 3) Which script to use

- `benchmark.py`  
  General benchmark runner (heuristic by default, optional exact mode).

- `benchmark_optimal.py`  
  Dedicated exact/proof runner.

- `benchmark_j20.py`  
  Convenience runner preconfigured for `sm_j20` heuristic mode.

- `benchmark_j10.py`  
  Convenience runner preconfigured for `sm_j10` heuristic mode.

- `benchmark_optimal_j10.py`  
  Convenience runner preconfigured for `sm_j10` optimal mode.

- `benchmark_optimal_j20.py`  
  Convenience runner preconfigured for `sm_j20` optimal mode.

- `main.py`  
  Single-instance runner with assignment-format output.

---

## 3.1) Heuristic benchmark vs Optimal/Proof benchmark

### Heuristic benchmark (`benchmark_j10.py`, `benchmark_j20.py`, or `benchmark.py` without `--optimal`)

- Uses multi-start SGS heuristic.
- Goal: get a valid schedule quickly.
- Output is typically `FEASIBLE` with a makespan.
- Fast and scalable for larger sets (especially `sm_j20`).
- Does **not** guarantee the reported makespan is globally optimal.

### Optimal/Proof benchmark (`benchmark_optimal_j10.py`, `benchmark_optimal_j20.py`, or `benchmark.py --optimal`)

- Uses exact branch-and-bound search.
- Goal: prove optimality if possible within the time limit.
- Output can be:
  - `FEASIBLE (OPTIMAL)` = optimality proven.
  - `FEASIBLE (NOT PROVEN)` = valid solution found, but proof not finished before time limit.
- Much slower as instance size increases.

### Practical recommendation

- Use heuristic benchmark for full runs and speed.
- Use optimal/proof benchmark for spot-checking quality or when proof is required.

---

## 4) Meaning of key options

- `--dataset sm_j10|sm_j20`  
  Select instance folder.

- `--repeat N`  
  Number of measured runs per instance (for timing stats).

- `--warmup N`  
  Number of unmeasured warmup runs before timing.

- `--starts N`  
  Number of randomized SGS starts (heuristic mode only). Higher can improve quality but costs more time.

- `--seed N`  
  Random seed for reproducible heuristic runs.

- `--optimal` (in `benchmark.py`)  
  Enables exact branch-and-bound mode.

- `--optimal-time-limit S`  
  Per-instance time budget for exact proof search.

---

## 5) Output status meanings

- `FEASIBLE`  
  Valid schedule found.

- `FEASIBLE (OPTIMAL)`  
  Valid schedule found and proven optimal.

- `FEASIBLE (NOT PROVEN)`  
  Valid schedule found, but proof search hit time limit before proving optimality.

- `TRUE INFEASIBLE`  
  Instance is genuinely infeasible (e.g., capacity/graph infeasibility).

- `HEURISTIC FAILED`  
  Heuristic did not produce a schedule (possible false infeasible).

- `TIMEOUT`  
  External timeout hit (if timeout mode used).

---

## 6) Recommended workflows

## If you want speed (course demo / large sets)

```bash
python benchmark.py --dataset sm_j20 --repeat 1 --warmup 0 --starts 30 --seed 42
```

## If you want proof attempts

```bash
python benchmark_optimal.py --dataset sm_j20 --repeat 1 --warmup 0 --optimal-time-limit 10
```

If too slow, lower limit:

```bash
python benchmark_optimal.py --dataset sm_j20 --repeat 1 --warmup 0 --optimal-time-limit 2
```

If you want stronger chance to prove optimality, raise limit:

```bash
python benchmark_optimal.py --dataset sm_j20 --repeat 1 --warmup 0 --optimal-time-limit 30
```

---

## 7) Common issues and fixes

## "zsh: unknown file attribute: h"
Cause: You pasted markdown-style command like `python [benchmark.py](...)`.

Fix: run plain filename only:

```bash
python benchmark.py --dataset sm_j20 --repeat 1 --warmup 0 --starts 30 --seed 42
```

## Exit code `130`
Cause: Command interrupted (usually Ctrl+C).

Fix: rerun command, or lower workload (`--repeat 1 --warmup 0`, lower time limit).

## Exact mode stays `NOT PROVEN`
Cause: Combinatorial explosion at larger instance sizes.

Fix options:
1. Increase `--optimal-time-limit`
2. Use heuristic mode for production runs
3. Run exact mode only on selected important instances

---

## 8) Practical defaults

- For `sm_j10`: exact mode may often prove optimal quickly.
- For `sm_j20`: use heuristic mode for throughput; exact mode for spot checks.

Good default commands:

```bash
python benchmark.py --dataset sm_j20 --repeat 1 --warmup 0 --starts 30 --seed 42
python benchmark_optimal.py --dataset sm_j20 --repeat 1 --warmup 0 --optimal-time-limit 10
```

---

## 9) One-liner summary

- Need fast and scalable? -> `benchmark.py` heuristic command.
- Need proof attempts? -> `benchmark_optimal.py` command.
- Need assignment output for one file? -> `main.py <instance_path>`.

---

## 10) Record comparison report (same results + heuristic quality)

Generate a CSV report that records:

- heuristic run 1 result
- heuristic run 2 result (same or different seed)
- whether both heuristic runs match
- optimal/proof result
- heuristic gap vs optimal (when optimal is proven)

Command example:

```bash
python compare_quality.py --dataset sm_j20 --starts 30 --seed 42 --second-seed 42 --optimal-time-limit 10 --out comparison_j20.csv
```

If you want sensitivity check (different heuristic seeds):

```bash
python compare_quality.py --dataset sm_j20 --starts 30 --seed 42 --second-seed 99 --optimal-time-limit 10 --out comparison_j20_seed_sensitivity.csv
```

Output CSV is created in `updated_instances/`.

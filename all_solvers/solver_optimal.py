import argparse
import multiprocessing as mp
import os
import statistics
import sys
import time
from pathlib import Path

# Ensure parent project folder is importable when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser import parse_sch
from solver import classify_and_solve_optimal


def _solve_one(args_tuple):
    """Worker function for multiprocessing. Must be top-level for pickling."""
    filepath, time_limit, _ = args_tuple
    t0 = time.perf_counter_ns()
    instance = parse_sch(filepath)
    status, _, makespan, _ = classify_and_solve_optimal(
        instance,
        time_limit_s=max(0.2, time_limit),
    )
    t1 = time.perf_counter_ns()
    elapsed_ms = (t1 - t0) / 1_000_000

    return Path(filepath).name, status, makespan, elapsed_ms


def parse_args():
    parser = argparse.ArgumentParser(
        description="Exact RCPSP solver (branch-and-bound optimal mode)"
    )
    parser.add_argument(
        "instance", nargs="?", default=None,
        help="Path to .SCH instance file (single-instance mode)",
    )
    parser.add_argument("--time-limit", type=float, default=10.0,
                        help="Per-instance exact solve time limit in seconds")
    parser.add_argument("--require-proof", action="store_true",
                        help="If set, print -1 unless optimality is proven")
    parser.add_argument("--dataset", type=str, default=None,
                        help="Dataset directory (e.g. sm_j10, sm_j20) for batch mode")
    parser.add_argument("--workers", "-w", type=int, default=None,
                        help="Number of parallel worker processes (default: CPU count)")
    parser.add_argument("--first-n", type=int, default=0,
                        help="Only process the first N instances (0 = all)")
    return parser.parse_args()


def main():
    args = parse_args()

    # --- Single-instance mode (original behavior) ---
    if args.instance and not args.dataset:
        instance = parse_sch(args.instance)
        status, schedule, _, _ = classify_and_solve_optimal(
            instance,
            time_limit_s=max(0.2, args.time_limit),
        )

        if args.require_proof and status != "feasible_optimal":
            print("-1")
            return
        if status not in ("feasible_optimal", "feasible_not_proven") or schedule is None:
            print("-1")
            return
        if instance.n <= 2:
            print("")
            return
        print(", ".join(str(schedule[j]) for j in range(1, instance.n - 1)))
        return

    # --- Batch mode ---
    if not args.dataset:
        print("Error: provide either an instance file or --dataset for batch mode.",
              file=sys.stderr)
        sys.exit(1)

    dataset_dir = PROJECT_ROOT / args.dataset
    files = sorted(dataset_dir.glob("PSP*.SCH"), key=lambda x: int(x.stem[3:]))
    if args.first_n > 0:
        files = files[: args.first_n]
    if not files:
        print(f"Error: no PSP*.SCH files found in {dataset_dir}", file=sys.stderr)
        sys.exit(1)

    workers = args.workers or os.cpu_count() or 1
    time_limit = max(0.2, args.time_limit)

    print("=" * 96)
    print(
        f"solver_optimal (batch) | dataset={args.dataset} | instances={len(files)} | "
        f"workers={workers} | time_limit={time_limit:.2f}s"
    )
    print("=" * 96)
    print(f"{'Instance':<16} {'Status':<22} {'Makespan':>10} {'Time(ms)':>12}")
    print("-" * 96)

    tasks = [(str(f), time_limit, args.require_proof) for f in files]

    counts = {
        "feasible_optimal": 0,
        "feasible_not_proven": 0,
        "true_infeasible": 0,
        "heuristic_failed": 0,
    }
    times = []
    wall_start = time.perf_counter()

    with mp.Pool(processes=workers) as pool:
        for name, status, makespan, elapsed_ms in pool.imap_unordered(_solve_one, tasks):
            times.append(elapsed_ms)
            if status in counts:
                counts[status] += 1

            mk_disp = "-" if makespan is None else str(makespan)
            print(f"{name:<16} {status.upper():<22} {mk_disp:>10} {elapsed_ms:>12.1f}")

    wall_elapsed = time.perf_counter() - wall_start

    print()
    print("Summary")
    print("-" * 96)
    print(f"Total instances:      {len(files)}")
    print(f"Feasible optimal:     {counts['feasible_optimal']}")
    print(f"Feasible not proven:  {counts['feasible_not_proven']}")
    print(f"True infeasible:      {counts['true_infeasible']}")
    print(f"Heuristic failed:     {counts['heuristic_failed']}")
    if times:
        print(f"Avg solve time:       {sum(times)/len(times):.1f} ms")
        print(f"Median solve time:    {statistics.median(times):.1f} ms")
        print(f"Min/Max solve time:   {min(times):.1f} / {max(times):.1f} ms")
    print(f"Wall-clock time:      {wall_elapsed:.2f} s")
    print(f"Workers:              {workers}")


if __name__ == "__main__":
    main()

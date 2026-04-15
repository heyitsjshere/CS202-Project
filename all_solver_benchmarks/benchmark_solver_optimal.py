import argparse
import csv
import multiprocessing as mp
import os
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.parser import parse_sch
from all_solvers.solver_optimal import classify_and_solve_optimal


def _solve_one(args_tuple):
    """Worker function for multiprocessing. Must be top-level for pickling."""
    filepath, time_limit, dataset = args_tuple
    t0 = time.perf_counter_ns()
    instance = parse_sch(filepath)
    status, _, makespan, _ = classify_and_solve_optimal(
        instance,
        time_limit_s=max(0.2, time_limit),
    )
    t1 = time.perf_counter_ns()
    elapsed_ms = (t1 - t0) / 1_000_000

    return Path(filepath).name, status, makespan, elapsed_ms, dataset


def parse_args():
    p = argparse.ArgumentParser(description="Benchmark exact optimal solver")
    p.add_argument("--dataset", choices=["sm_j10", "sm_j20"], default="sm_j10")
    p.add_argument("--time-limit", type=float, default=10.0)
    p.add_argument("--first-n", type=int, default=0)
    p.add_argument("--workers", "-w", type=int, default=None,
                   help="Number of parallel worker processes (default: CPU count)")
    p.add_argument("--csv-file", type=str, default=None,
                   help="Optional CSV path override (default: results/solver_optimal_<dataset>_results.csv)")
    p.add_argument("--log-file", type=str, default=None,
                   help=argparse.SUPPRESS)
    return p.parse_args()


def main():
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    files = sorted((root / args.dataset).glob("PSP*.SCH"), key=lambda x: int(x.stem[3:]))
    if args.first_n > 0:
        files = files[: args.first_n]

    if not files:
        raise FileNotFoundError(f"No PSP*.SCH files found in {args.dataset}")

    workers = args.workers or os.cpu_count() or 1
    time_limit = max(0.2, args.time_limit)

    print("=" * 96)
    print(
        f"benchmark_solver_optimal | dataset={args.dataset} | instances={len(files)} | "
        f"workers={workers} | time_limit={time_limit:.2f}s"
    )
    print("=" * 96)
    print(f"{'Instance':<16} {'Status':<22} {'Makespan':>10} {'Time(ms)':>12}")
    print("-" * 96)

    tasks = [(str(f), time_limit, args.dataset) for f in files]

    counts = {
        "feasible_optimal": 0,
        "feasible_not_proven": 0,
        "true_infeasible": 0,
        "heuristic_failed": 0,
    }
    times = []
    wall_start = time.perf_counter()

    results_dir = root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    default_csv = results_dir / f"solver_optimal_{args.dataset}_results.csv"
    csv_path = Path(args.csv_file) if args.csv_file else (
        Path(args.log_file) if args.log_file else default_csv
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_file = open(csv_path, "a", newline="")
    csv_writer = csv.writer(csv_file)
    if csv_file.tell() == 0:
        csv_writer.writerow([
            "dataset", "instance", "solver", "status", "makespan", "time_ms",
            "time_limit_s", "workers", "seed", "starts",
        ])

    print(f"CSV file:             {csv_path}")

    try:
        with mp.Pool(processes=workers) as pool:
            for name, status, makespan, elapsed_ms, dataset in pool.imap_unordered(_solve_one, tasks):
                times.append(elapsed_ms)
                if status in counts:
                    counts[status] += 1
                csv_writer.writerow([
                    dataset,
                    name,
                    "solver_optimal",
                    status,
                    "" if makespan is None else makespan,
                    f"{elapsed_ms:.1f}",
                    f"{time_limit:.2f}",
                    workers,
                    "",
                    "",
                ])
                csv_file.flush()

                mk_disp = "-" if makespan is None else str(makespan)
                print(f"{name:<16} {status.upper():<22} {mk_disp:>10} {elapsed_ms:>12.1f}")
    finally:
        csv_file.close()

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

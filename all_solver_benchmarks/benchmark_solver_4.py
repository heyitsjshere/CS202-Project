import argparse
import csv
import multiprocessing as mp
import os
import statistics
import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.parser import parse_sch
from all_solvers.solver_4 import classify_and_solve_best


def _output_line_from_schedule(instance, status, schedule):
    if status == "feasible" and schedule is not None:
        if instance.n <= 2:
            return ""
        return ", ".join(str(schedule[j]) for j in range(1, instance.n - 1))
    return "-1"


def _solve_one(args_tuple):
    """Worker: run solver_4 directly on a single instance."""
    filepath, time_limit, seed, dataset = args_tuple
    inst = parse_sch(filepath)
    t0 = time.perf_counter_ns()
    status, schedule, mk, _ = classify_and_solve_best(
        inst,
        time_limit_s=max(0.2, time_limit),
        seed=seed,
    )
    t1 = time.perf_counter_ns()
    ms = (t1 - t0) / 1_000_000
    if status == "feasible":
        format_ok = schedule is not None and len(schedule) == inst.n
    elif status in ("true_infeasible", "heuristic_failed"):
        # Non-feasible statuses correspond to printing -1 in solver CLI.
        format_ok = True
    else:
        format_ok = False
    output_line = _output_line_from_schedule(inst, status, schedule)
    return Path(filepath).name, status, mk, ms, dataset, format_ok, output_line


def parse_args():
    p = argparse.ArgumentParser(description="Benchmark solver_4")
    p.add_argument("--dataset", choices=["sm_j10", "sm_j20"], default="sm_j10")
    p.add_argument("--time-limit", type=float, default=2.0)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--first-n", type=int, default=0)
    p.add_argument("--workers", "-w", type=int, default=None,
                   help="Number of parallel worker processes (default: CPU count)")
    p.add_argument("--csv-file", type=str, default=None,
                   help="Optional CSV path override (default: results/solver_4_results.csv)")
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

    print("=" * 96)
    print(
        f"benchmark_solver_4 | dataset={args.dataset} | instances={len(files)} | "
        f"workers={workers} | time_limit={max(0.2, args.time_limit):.2f}s | seed={args.seed}"
    )
    print("=" * 96)
    print(f"{'Instance':<16} {'Status':<22} {'Makespan':>10} {'Time(ms)':>12}")
    print("-" * 96)

    tasks = [(str(f), args.time_limit, args.seed, args.dataset) for f in files]

    counts = {"feasible": 0, "true_infeasible": 0, "heuristic_failed": 0, "error": 0}
    output_format_ok_count = 0
    times = []
    wall_start = time.perf_counter()

    results_dir = root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = Path(args.csv_file) if args.csv_file else (
        Path(args.log_file) if args.log_file else (results_dir / "solver_4_results.csv")
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_file = open(csv_path, "a", newline="")
    csv_writer = csv.writer(csv_file)
    if csv_file.tell() == 0:
        csv_writer.writerow([
            "dataset", "instance", "solver", "status", "makespan", "time_ms",
            "time_limit_s", "workers", "seed", "starts", "output_format_ok", "output_line",
        ])

    print(f"CSV file:             {csv_path}")

    try:
        with mp.Pool(processes=workers) as pool:
            for name, status, makespan, elapsed_ms, dataset, format_ok, output_line in pool.imap_unordered(_solve_one, tasks):
                times.append(elapsed_ms)
                if status in counts:
                    counts[status] += 1
                else:
                    counts["error"] += 1
                if format_ok:
                    output_format_ok_count += 1
                csv_writer.writerow([
                    dataset,
                    name,
                    "solver_4",
                    status,
                    "" if makespan is None else makespan,
                    f"{elapsed_ms:.1f}",
                    f"{max(0.2, args.time_limit):.2f}",
                    workers,
                    args.seed,
                    "",
                    str(format_ok).lower(),
                    output_line,
                ])
                csv_file.flush()

                mk_disp = "-" if makespan is None else str(makespan)
                print(f"{name:<16} {status.upper():<22} {mk_disp:>10} {elapsed_ms:>12.1f}")
    finally:
        csv_file.close()

    wall_elapsed = time.perf_counter() - wall_start

    print("\nSummary")
    print("-" * 96)
    print(f"Total: {len(files)}")
    print(f"Feasible: {counts['feasible']}")
    print(f"True infeasible: {counts['true_infeasible']}")
    print(f"Heuristic failed: {counts['heuristic_failed']}")
    print(f"Error: {counts['error']}")
    print(f"Output-format valid: {output_format_ok_count}/{len(files)}")
    if times:
        print(f"Avg time: {sum(times)/len(times):.1f} ms")
        print(f"Median time: {statistics.median(times):.1f} ms")
        print(f"Min/Max time: {min(times):.1f} / {max(times):.1f} ms")
    print(f"Wall-clock time:      {wall_elapsed:.2f} s")
    print(f"Workers:              {workers}")


if __name__ == "__main__":
    main()

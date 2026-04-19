import argparse
import csv
import multiprocessing as mp
import os
import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.parser import parse_sch
from all_solvers.solver_3 import classify_and_solve_best


def _output_line_from_schedule(instance, status, schedule):
    if status == "feasible" and schedule is not None:
        if instance.n <= 2:
            return ""
        return ", ".join(str(schedule[j]) for j in range(1, instance.n - 1))
    return "-1"


def _solve_one(args_tuple):
    """Worker: run solver_3 directly on a single instance."""
    filepath, time_limit, starts, seed, dataset = args_tuple
    inst = parse_sch(filepath)
    t0 = time.perf_counter_ns()
    status, schedule, mk, _ = classify_and_solve_best(
        inst,
        time_limit_s=max(0.2, time_limit),
        starts=max(1, starts),
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
    p = argparse.ArgumentParser(description="Benchmark solver_3")
    p.add_argument("--dataset", choices=["sm_j10", "sm_j20"], default="sm_j10")
    p.add_argument("--time-limit", type=float, default=2.0)
    p.add_argument("--starts", type=int, default=120)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--first-n", type=int, default=0)
    p.add_argument("--workers", "-w", type=int, default=None,
                   help="Number of parallel worker processes (default: CPU count)")
    p.add_argument("--csv-file", type=str, default=None,
                   help="Optional CSV path override (default: results/solver_3_<dataset>_results.csv)")
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

    tasks = [
        (str(f), args.time_limit, args.starts, args.seed, args.dataset)
        for f in files
    ]

    results_dir = root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    default_csv = results_dir / f"solver_3_{args.dataset}_results.csv"
    csv_path = Path(args.csv_file) if args.csv_file else (
        Path(args.log_file) if args.log_file else default_csv
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_file = open(csv_path, "a", newline="")
    csv_writer = csv.writer(csv_file)
    if csv_file.tell() == 0:
        csv_writer.writerow([
            "dataset", "instance", "solver", "status", "makespan", "time_ms",
            "time_limit_s", "workers", "seed", "starts", "output_format_ok", "output_line",
        ])

    try:
        with mp.Pool(processes=workers) as pool:
            for name, status, makespan, elapsed_ms, dataset, format_ok, output_line in pool.imap_unordered(_solve_one, tasks):
                csv_writer.writerow([
                    dataset,
                    name,
                    "solver_3",
                    status,
                    "" if makespan is None else makespan,
                    f"{elapsed_ms:.1f}",
                    f"{max(0.2, args.time_limit):.2f}",
                    workers,
                    args.seed,
                    max(1, args.starts),
                    str(format_ok).lower(),
                    output_line,
                ])
                csv_file.flush()
                print(output_line)
    finally:
        csv_file.close()


if __name__ == "__main__":
    main()

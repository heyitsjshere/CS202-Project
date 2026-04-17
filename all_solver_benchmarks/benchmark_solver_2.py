import argparse
import csv
import multiprocessing as mp
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.parser import parse_sch
from all_solvers.solver_optimal import validate_schedule


def _schedule_from_output(instance, output_line):
    if output_line.strip() == "-1":
        return None
    parts = [x.strip() for x in output_line.split(",") if x.strip()]
    if len(parts) != instance.n - 2:
        raise ValueError("unexpected output length")
    starts = [0] * instance.n
    vals = [int(x) for x in parts]
    for j in range(1, instance.n - 1):
        starts[j] = vals[j - 1]
    sink = instance.n - 1
    preds = [i for i, j in instance.precedence if j == sink]
    starts[sink] = max((starts[p] + instance.durations[p] for p in preds), default=0)
    return starts


def _output_format_ok(instance, output_line):
    text = output_line.strip()
    if text == "-1":
        return True
    parts = [x.strip() for x in text.split(",") if x.strip()]
    if len(parts) != (instance.n - 2):
        return False
    try:
        [int(x) for x in parts]
    except ValueError:
        return False
    return True


def _solve_one(args_tuple):
    """Worker: run solver_2 via subprocess on a single instance."""
    filepath, script_path, time_limit, dataset = args_tuple
    inst = parse_sch(filepath)
    cmd = [sys.executable, str(script_path), filepath, "--time-limit", str(max(0.2, time_limit))]

    t0 = time.perf_counter_ns()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    t1 = time.perf_counter_ns()
    ms = (t1 - t0) / 1_000_000

    if proc.returncode != 0:
        return Path(filepath).name, "error", None, ms, dataset, False, ""

    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        return Path(filepath).name, "error", None, ms, dataset, False, ""

    output_line = lines[-1]
    format_ok = _output_format_ok(inst, output_line)

    try:
        sched = _schedule_from_output(inst, output_line)
    except Exception:
        return Path(filepath).name, "error", None, ms, dataset, format_ok, output_line

    if sched is None:
        return Path(filepath).name, "heuristic_failed", None, ms, dataset, format_ok, output_line

    ok, _, mk = validate_schedule(inst, sched)
    if ok:
        return Path(filepath).name, "feasible", mk, ms, dataset, format_ok, output_line
    return Path(filepath).name, "error", None, ms, dataset, format_ok, output_line


def parse_args():
    p = argparse.ArgumentParser(description="Benchmark solver_2 (solver2_fixed.py)")
    p.add_argument("--dataset", choices=["sm_j10", "sm_j20"], default="sm_j10")
    p.add_argument("--time-limit", type=float, default=2.0)
    p.add_argument("--first-n", type=int, default=0)
    p.add_argument("--workers", "-w", type=int, default=None,
                   help="Number of parallel worker processes (default: CPU count)")
    p.add_argument("--csv-file", type=str, default=None,
                   help="Optional CSV path override (default: results/solver_2_results.csv)")
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
    script_path = str(root / "all_solvers" / "solver_2.py")

    print("=" * 96)
    print(
        f"benchmark_solver_2 | dataset={args.dataset} | instances={len(files)} | "
        f"workers={workers} | time_limit={max(0.2, args.time_limit):.2f}s"
    )
    print("=" * 96)
    print(f"{'Instance':<16} {'Status':<22} {'Makespan':>10} {'Time(ms)':>12}")
    print("-" * 96)

    tasks = [(str(f), script_path, args.time_limit, args.dataset) for f in files]

    counts = {"feasible": 0, "true_infeasible": 0, "heuristic_failed": 0, "error": 0}
    output_format_ok_count = 0
    times = []
    wall_start = time.perf_counter()

    results_dir = root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = Path(args.csv_file) if args.csv_file else (
        Path(args.log_file) if args.log_file else (results_dir / "solver_2_results.csv")
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
                if format_ok:
                    output_format_ok_count += 1
                csv_writer.writerow([
                    dataset,
                    name,
                    "solver_2",
                    status,
                    "" if makespan is None else makespan,
                    f"{elapsed_ms:.1f}",
                    f"{max(0.2, args.time_limit):.2f}",
                    workers,
                    "",
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

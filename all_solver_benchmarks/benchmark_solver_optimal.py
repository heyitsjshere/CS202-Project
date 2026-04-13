import argparse
import statistics
import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser import parse_sch
from solver import classify_and_solve_optimal


def parse_args():
    p = argparse.ArgumentParser(description="Benchmark exact optimal solver")
    p.add_argument("--dataset", choices=["sm_j10", "sm_j20"], default="sm_j10")
    p.add_argument("--time-limit", type=float, default=10.0)
    p.add_argument("--first-n", type=int, default=0)
    return p.parse_args()


def main():
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    files = sorted((root / args.dataset).glob("PSP*.SCH"), key=lambda x: int(x.stem[3:]))
    if args.first_n > 0:
        files = files[: args.first_n]

    if not files:
        raise FileNotFoundError(f"No PSP*.SCH files found in {args.dataset}")

    print("=" * 96)
    print(
        f"benchmark_solver_optimal | dataset={args.dataset} | instances={len(files)} | "
        f"time_limit={max(0.2, args.time_limit):.2f}s"
    )
    print("=" * 96)
    print(f"{'Instance':<12} {'Status':<18} {'Makespan':>10} {'Time(ms)':>12}")
    print("-" * 96)

    times = []
    counts = {
        "feasible_optimal": 0,
        "feasible_not_proven": 0,
        "true_infeasible": 0,
        "heuristic_failed": 0,
        "error": 0,
    }

    for f in files:
        inst = parse_sch(str(f))
        t0 = time.perf_counter_ns()
        status, _, mk, msg = classify_and_solve_optimal(inst, time_limit_s=max(0.2, args.time_limit))
        t1 = time.perf_counter_ns()
        ms = (t1 - t0) / 1_000_000
        times.append(ms)

        if status in counts:
            counts[status] += 1
        else:
            counts["error"] += 1

        status_disp = status.upper()
        mk_disp = "-" if mk is None else str(mk)
        print(f"{f.name:<12} {status_disp:<18} {mk_disp:>10} {ms:>12.1f}")

    print("\nSummary")
    print("-" * 96)
    print(f"Total: {len(files)}")
    print(f"Feasible optimal: {counts['feasible_optimal']}")
    print(f"Feasible not proven: {counts['feasible_not_proven']}")
    print(f"True infeasible: {counts['true_infeasible']}")
    print(f"Heuristic failed: {counts['heuristic_failed']}")
    print(f"Error: {counts['error']}")
    if times:
        print(f"Avg time: {sum(times)/len(times):.1f} ms")
        print(f"Median time: {statistics.median(times):.1f} ms")
        print(f"Min/Max time: {min(times):.1f} / {max(times):.1f} ms")


if __name__ == "__main__":
    main()

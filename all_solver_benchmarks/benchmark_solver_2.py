import argparse
import statistics
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser import parse_sch
from solver import validate_schedule


def parse_args():
    p = argparse.ArgumentParser(description="Benchmark solver_2 (solver2_fixed.py)")
    p.add_argument("--dataset", choices=["sm_j10", "sm_j20"], default="sm_j10")
    p.add_argument("--time-limit", type=float, default=2.0)
    p.add_argument("--first-n", type=int, default=0)
    return p.parse_args()


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


def main():
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    files = sorted((root / args.dataset).glob("PSP*.SCH"), key=lambda x: int(x.stem[3:]))
    if args.first_n > 0:
        files = files[: args.first_n]

    if not files:
        raise FileNotFoundError(f"No PSP*.SCH files found in {args.dataset}")

    script_path = root / "solver2_fixed.py"

    print("=" * 96)
    print(
        f"benchmark_solver_2 | dataset={args.dataset} | instances={len(files)} | "
        f"time_limit={max(0.2, args.time_limit):.2f}s"
    )
    print("=" * 96)
    print(f"{'Instance':<12} {'Status':<18} {'Makespan':>10} {'Time(ms)':>12}")
    print("-" * 96)

    times = []
    counts = {
        "feasible": 0,
        "true_infeasible": 0,
        "heuristic_failed": 0,
        "error": 0,
    }

    for f in files:
        inst = parse_sch(str(f))
        cmd = [sys.executable, str(script_path), str(f), "--time-limit", str(max(0.2, args.time_limit))]

        t0 = time.perf_counter_ns()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        t1 = time.perf_counter_ns()
        ms = (t1 - t0) / 1_000_000
        times.append(ms)

        if proc.returncode != 0:
            counts["error"] += 1
            print(f"{f.name:<12} {'ERROR':<18} {'-':>10} {ms:>12.1f}")
            continue

        lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        if not lines:
            counts["error"] += 1
            print(f"{f.name:<12} {'ERROR':<18} {'-':>10} {ms:>12.1f}")
            continue

        try:
            sched = _schedule_from_output(inst, lines[-1])
        except Exception as exc:
            counts["error"] += 1
            print(f"{f.name:<12} {'ERROR':<18} {'-':>10} {ms:>12.1f}")
            continue

        if sched is None:
            counts["heuristic_failed"] += 1
            print(f"{f.name:<12} {'HEURISTIC_FAILED':<18} {'-':>10} {ms:>12.1f}")
            continue

        ok, msg, mk = validate_schedule(inst, sched)
        if ok:
            counts["feasible"] += 1
            print(f"{f.name:<12} {'FEASIBLE':<18} {mk:>10} {ms:>12.1f}")
        else:
            counts["error"] += 1
            print(f"{f.name:<12} {'ERROR':<18} {'-':>10} {ms:>12.1f}")

    print("\nSummary")
    print("-" * 96)
    print(f"Total: {len(files)}")
    print(f"Feasible: {counts['feasible']}")
    print(f"True infeasible: {counts['true_infeasible']}")
    print(f"Heuristic failed: {counts['heuristic_failed']}")
    print(f"Error: {counts['error']}")
    if times:
        print(f"Avg time: {sum(times)/len(times):.1f} ms")
        print(f"Median time: {statistics.median(times):.1f} ms")
        print(f"Min/Max time: {min(times):.1f} / {max(times):.1f} ms")


if __name__ == "__main__":
    main()

import argparse
import sys
from pathlib import Path

# Ensure parent project folder is importable when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser import parse_sch
from solver import classify_and_solve_optimal


def parse_args():
    parser = argparse.ArgumentParser(description="Exact RCPSP solver (branch-and-bound optimal mode)")
    parser.add_argument("instance", help="Path to .SCH instance file")
    parser.add_argument("--time-limit", type=float, default=10.0, help="Per-instance exact solve time limit in seconds")
    parser.add_argument(
        "--require-proof",
        action="store_true",
        help="If set, print -1 unless optimality is proven",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    instance = parse_sch(args.instance)

    status, schedule, _, _ = classify_and_solve_optimal(
        instance,
        time_limit_s=max(0.2, args.time_limit),
    )

    # Strict mode: only accept proven optimal.
    if args.require_proof and status != "feasible_optimal":
        print("-1")
        return

    # Non-strict mode: allow best exact incumbent even if not proven optimal.
    if status not in ("feasible_optimal", "feasible_not_proven") or schedule is None:
        print("-1")
        return

    if instance.n <= 2:
        print("")
        return

    print(", ".join(str(schedule[j]) for j in range(1, instance.n - 1)))


if __name__ == "__main__":
    main()

import argparse
from pathlib import Path

from benchmark import run


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        choices=["sm_j10", "sm_j20"],
        default="sm_j20",
        help="Which dataset folder to run.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=0,
        help="Per-instance timeout in seconds outside solver (0 disables external timeout).",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of measured runs per instance.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=0,
        help="Number of warmup runs per instance.",
    )
    parser.add_argument(
        "--optimal-time-limit",
        type=float,
        default=10.0,
        help="Per-instance internal time limit for exact solver.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    base_dir = Path(__file__).resolve().parent
    files = sorted(
        (base_dir / args.dataset).glob("PSP*.SCH"),
        key=lambda p: int(p.stem[3:]),
    )

    if not files:
        raise FileNotFoundError(f"No PSP*.SCH files found in {args.dataset}")

    timeout_s = args.timeout if args.timeout > 0 else None
    print(
        f"Optimal benchmark mode | dataset={args.dataset} | "
        f"repeat={max(1, args.repeat)} | warmup={max(0, args.warmup)} | "
        f"optimal_time_limit={max(0.0, args.optimal_time_limit):.2f}s"
    )

    counts = {
        "feasible": 0,
        "feasible_optimal": 0,
        "feasible_not_proven": 0,
        "true_infeasible": 0,
        "heuristic_failed": 0,
        "timeout": 0,
        "error": 0,
    }

    for f in files:
        status = run(
            str(f),
            timeout_s=timeout_s,
            repeat=max(1, args.repeat),
            warmup=max(0, args.warmup),
            use_optimal=True,
            optimal_time_limit=max(0.0, args.optimal_time_limit),
            starts=1,
            seed=42,
        )
        if status in counts:
            counts[status] += 1

    total = len(files)
    print("\nSummary")
    print(f"Total: {total}")
    print(f"Feasible: {counts['feasible']}")
    print(f"Feasible optimal: {counts['feasible_optimal']}")
    print(f"Feasible not proven: {counts['feasible_not_proven']}")
    print(f"True infeasible: {counts['true_infeasible']}")
    print(f"Heuristic failed: {counts['heuristic_failed']}")
    print(f"Timeout: {counts['timeout']}")
    print(f"Error: {counts['error']}")


if __name__ == "__main__":
    main()

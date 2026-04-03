from benchmark import run
from pathlib import Path


def main():
    base_dir = Path(__file__).resolve().parent
    files = sorted(
        (base_dir / "sm_j20").glob("PSP*.SCH"),
        key=lambda p: int(p.stem[3:]),
    )

    if not files:
        raise FileNotFoundError("No PSP*.SCH files found in sm_j20")

    print("Dataset: sm_j20")
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
            timeout_s=None,
            repeat=1,
            warmup=0,
            use_optimal=False,
            starts=30,
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

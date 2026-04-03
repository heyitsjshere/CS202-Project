from pathlib import Path
import sys

try:
    from .parser import parse_sch
    from .solver import classify_and_solve
except ImportError:
    from parser import parse_sch
    from solver import classify_and_solve


def main():
    base_dir = Path(__file__).resolve().parent
    if len(sys.argv) > 1:
        raw_path = Path(sys.argv[1])
        if raw_path.is_absolute() and raw_path.exists():
            instance_path = raw_path
        elif raw_path.exists():
            instance_path = raw_path.resolve()
        else:
            candidate_j10 = base_dir / "sm_j10" / raw_path.name
            candidate_j20 = base_dir / "sm_j20" / raw_path.name
            if candidate_j10.exists():
                instance_path = candidate_j10
            elif candidate_j20.exists():
                instance_path = candidate_j20
            else:
                raise FileNotFoundError(
                    f"Instance file not found: {raw_path}. "
                    "Try sm_j10/<file>.SCH or sm_j20/<file>.SCH"
                )
    else:
        instance_path = base_dir / "sm_j10" / "PSP1.SCH"

    instance = parse_sch(str(instance_path))

    status, schedule, _, _ = classify_and_solve(instance)

    if status != "feasible":
        print("-1")
        return

    # Jobs are indexed 0..N+1 with dummy source/sink, output jobs 1..N.
    if instance.n <= 2:
        print("")
        return

    output = ", ".join(str(schedule[j]) for j in range(1, instance.n - 1))
    print(output)


if __name__ == "__main__":
    main()
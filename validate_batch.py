from pathlib import Path
import subprocess
import sys

from parser import parse_sch


def build_successors_and_predecessors(instance):
    succ_of = [[] for _ in range(instance.n)]
    pred_of = [[] for _ in range(instance.n)]
    for i, j in instance.precedence:
        succ_of[i].append(j)
        pred_of[j].append(i)
    return succ_of, pred_of


def validate_output(instance, stdout_text):
    text = stdout_text.strip()

    # Case 1: solver says infeasible
    if text == "-1":
        return True, "returned -1"

    parts = [p.strip() for p in text.split(",") if p.strip() != ""]

    # Noah's parser stores total activities including dummies in instance.n
    expected_real_jobs = instance.n - 2
    if len(parts) != expected_real_jobs:
        return False, f"expected {expected_real_jobs} start times, got {len(parts)}"

    try:
        starts_real = [int(x) for x in parts]
    except ValueError:
        return False, "non-integer output detected"

    # Rebuild full start vector
    starts = [0] * instance.n
    # jobs 1 .. instance.n-2 are real jobs
    for j in range(1, instance.n - 1):
        starts[j] = starts_real[j - 1]

    succ_of, pred_of = build_successors_and_predecessors(instance)

    # Set sink start time consistently from predecessors
    sink = instance.n - 1
    if pred_of[sink]:
        starts[sink] = max(starts[p] + instance.durations[p] for p in pred_of[sink])
    else:
        starts[sink] = 0

    # Precedence validation
    for i, j in instance.precedence:
        finish_i = starts[i] + instance.durations[i]
        if starts[j] < finish_i:
            return False, f"precedence violation: {i}->{j} with start[{j}]={starts[j]} < {finish_i}"

    # Resource validation
    horizon = max(starts[i] + instance.durations[i] for i in range(instance.n))
    usage = [[0] * instance.num_resources for _ in range(horizon)]

    for i in range(instance.n):
        s = starts[i]
        e = s + instance.durations[i]
        for t in range(s, e):
            for k in range(instance.num_resources):
                usage[t][k] += instance.demands[i][k]
                if usage[t][k] > instance.resources[k]:
                    return False, (
                        f"resource violation at time {t}, resource {k}: "
                        f"{usage[t][k]} > {instance.resources[k]}"
                    )

    return True, "valid schedule"


def main():
    base = Path("updated_instances/sm_j20")
    files = sorted(base.glob("PSP*.SCH"), key=lambda p: int(p.stem[3:]))

    ok = 0
    bad = 0

    for f in files:
        result = subprocess.run(
            [sys.executable, "main.py", str(f)],
            capture_output=True,
            text=True,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:
            print(f"[ERROR] {f.name}: process crashed")
            if stderr:
                print(stderr)
            bad += 1
            continue

        instance = parse_sch(str(f))
        valid, msg = validate_output(instance, stdout)

        if valid:
            print(f"[OK]  {f.name}: {msg} | output={stdout}")
            ok += 1
        else:
            print(f"[BAD] {f.name}: {msg} | output={stdout}")
            bad += 1

    print(f"\nSummary: OK={ok}, BAD={bad}")


if __name__ == "__main__":
    main()
import csv
from pathlib import Path


TOPO_CSV = Path("results/solver_topological_sm_j20_results.csv")
OTHER_CSV = Path("results/solver_optimal_sm_j20_results.csv")
OTHER_SOLVER = "solver_optimal"
OTHER_LABEL = "Optimal"


def read_latest_feasible_rows(path, solver_name, feasible_statuses):
    rows = {}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row.get("solver") != solver_name:
                continue

            status = row.get("status")
            makespan = row.get("makespan")
            time_ms = row.get("time_ms")

            if status not in feasible_statuses or makespan in ("", None) or time_ms in ("", None):
                continue

            key = (row["dataset"], row["instance"])

            # If the CSV has repeated runs, this keeps the latest row.
            rows[key] = {
                "makespan": int(float(makespan)),
                "time_ms": float(time_ms),
            }

    return rows


def main():
    topo = read_latest_feasible_rows(TOPO_CSV, "solver_topological", {"feasible"})
    other = read_latest_feasible_rows(
        OTHER_CSV,
        OTHER_SOLVER,
        {"feasible", "feasible_optimal", "feasible_not_proven"},
    )

    common = sorted(set(topo) & set(other))

    if not common:
        print("No matching feasible instances found.")
        return

    improvements = []
    absolute_improvements = []
    topo_makespans = []
    other_makespans = []
    other_better = 0
    other_equal = 0
    other_worse = 0

    print(f"{'Dataset':<8} {'Instance':<14} {'Topo':>8} {OTHER_LABEL:>8} {'Diff':>8} {'Improve %':>10}")
    print("-" * 64)

    for key in common:
        topo_mk = topo[key]["makespan"]
        other_mk = other[key]["makespan"]

        diff = topo_mk - other_mk
        pct = (diff / topo_mk) * 100 if topo_mk > 0 else 0.0

        improvements.append(pct)
        absolute_improvements.append(diff)
        topo_makespans.append(topo_mk)
        other_makespans.append(other_mk)

        if diff > 0:
            other_better += 1
        elif diff == 0:
            other_equal += 1
        else:
            other_worse += 1

        dataset, instance = key
        print(f"{dataset:<8} {instance:<14} {topo_mk:>8} {other_mk:>8} {diff:>8} {pct:>9.2f}%")

    avg_pct = sum(improvements) / len(improvements)
    avg_abs = sum(absolute_improvements) / len(absolute_improvements)
    avg_topo_makespan = sum(topo_makespans) / len(topo_makespans)
    avg_other_makespan = sum(other_makespans) / len(other_makespans)

    print()
    print("Summary")
    print("-" * 64)
    print(f"Compared instances:       {len(common)}")
    print(f"{OTHER_LABEL} better:          {other_better}")
    print(f"{OTHER_LABEL} equal:           {other_equal}")
    print(f"{OTHER_LABEL} worse:           {other_worse}")
    print(f"Average topo makespan:    {avg_topo_makespan:.2f}")
    print(f"Average {OTHER_LABEL} span:    {avg_other_makespan:.2f}")
    print(f"Average improvement:      {avg_pct:.2f}%")
    print(f"Average makespan saved:   {avg_abs:.2f}")


if __name__ == "__main__":
    main()

import csv
from pathlib import Path


TOPO_CSV = Path("results/solver_topological_sm_j20_results.csv")
SOLVER3_CSV = Path("results/solver_3_sm_j20_results.csv")


def read_latest_feasible_rows(path, solver_name):
    rows = {}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row.get("solver") != solver_name:
                continue

            status = row.get("status")
            makespan = row.get("makespan")
            time_ms = row.get("time_ms")

            if status != "feasible" or makespan in ("", None) or time_ms in ("", None):
                continue

            key = (row["dataset"], row["instance"])

            # If the CSV has repeated runs, this keeps the latest row.
            rows[key] = {
                "makespan": int(float(makespan)),
                "time_ms": float(time_ms),
            }

    return rows


def main():
    topo = read_latest_feasible_rows(TOPO_CSV, "solver_topological")
    solver3 = read_latest_feasible_rows(SOLVER3_CSV, "solver_3")

    common = sorted(set(topo) & set(solver3))

    if not common:
        print("No matching feasible instances found.")
        return

    improvements = []
    absolute_improvements = []
    topo_makespans = []
    solver3_makespans = []
    solver3_better = 0
    solver3_equal = 0
    solver3_worse = 0

    print(f"{'Dataset':<8} {'Instance':<14} {'Topo':>8} {'Solver3':>8} {'Diff':>8} {'Improve %':>10}")
    print("-" * 64)

    for key in common:
        topo_mk = topo[key]["makespan"]
        solver3_mk = solver3[key]["makespan"]

        diff = topo_mk - solver3_mk
        pct = (diff / topo_mk) * 100 if topo_mk > 0 else 0.0

        improvements.append(pct)
        absolute_improvements.append(diff)
        topo_makespans.append(topo_mk)
        solver3_makespans.append(solver3_mk)

        if diff > 0:
            solver3_better += 1
        elif diff == 0:
            solver3_equal += 1
        else:
            solver3_worse += 1

        dataset, instance = key
        print(f"{dataset:<8} {instance:<14} {topo_mk:>8} {solver3_mk:>8} {diff:>8} {pct:>9.2f}%")

    avg_pct = sum(improvements) / len(improvements)
    avg_abs = sum(absolute_improvements) / len(absolute_improvements)
    avg_topo_makespan = sum(topo_makespans) / len(topo_makespans)
    avg_solver3_makespan = sum(solver3_makespans) / len(solver3_makespans)

    print()
    print("Summary")
    print("-" * 64)
    print(f"Compared instances:       {len(common)}")
    print(f"Solver 3 better:          {solver3_better}")
    print(f"Solver 3 equal:           {solver3_equal}")
    print(f"Solver 3 worse:           {solver3_worse}")
    print(f"Average topo makespan:    {avg_topo_makespan:.2f}")
    print(f"Average solver 3 span:    {avg_solver3_makespan:.2f}")
    print(f"Average improvement:      {avg_pct:.2f}%")
    print(f"Average makespan saved:   {avg_abs:.2f}")


if __name__ == "__main__":
    main()

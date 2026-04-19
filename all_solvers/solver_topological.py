import argparse
import sys
from pathlib import Path

# Ensure parent project folder is importable when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.graph_utils import build_graph, topological_order
from utils.parser import parse_sch


def resource_feasible(instance):
    for i in range(instance.n):
        for r in range(instance.num_resources):
            if instance.demands[i][r] > instance.resources[r]:
                return False
    return True


def validate_schedule(instance, schedule):
    n = instance.n
    if schedule is None or len(schedule) != n:
        return False, "invalid schedule length", None

    durations = instance.durations
    demands = instance.demands
    capacities = instance.resources
    num_resources = instance.num_resources

    for i in range(n):
        if schedule[i] < 0:
            return False, f"negative start time at activity {i}", None

    for i, j in instance.precedence:
        if schedule[j] < schedule[i] + durations[i]:
            return False, f"precedence violation: {i}->{j}", None

    makespan = max(schedule[i] + durations[i] for i in range(n)) if n else 0
    usage = [[0] * num_resources for _ in range(max(1, makespan))]

    for i in range(n):
        s = schedule[i]
        d = durations[i]
        if d <= 0:
            continue
        for t in range(s, s + d):
            row = usage[t]
            for r in range(num_resources):
                row[r] += demands[i][r]
                if row[r] > capacities[r]:
                    return False, f"resource violation at t={t}, resource={r}", None

    return True, "", makespan


def _earliest_resource_feasible_start(instance, usage, reqs, duration, earliest, horizon):
    if duration <= 0:
        return earliest

    t = earliest
    latest_start = horizon - duration
    while t <= latest_start:
        feasible = True
        for dt in range(duration):
            row = usage[t + dt]
            for r, demand in reqs:
                if row[r] + demand > instance.resources[r]:
                    feasible = False
                    break
            if not feasible:
                break
        if feasible:
            return t
        t += 1

    return None


def solve_topological(instance):
    if instance.n <= 0:
        return [], 0

    order = topological_order(instance)
    _, pred = build_graph(instance)

    durations = instance.durations
    demands = instance.demands
    num_resources = instance.num_resources
    horizon = sum(durations)

    if horizon <= 0:
        return [0] * instance.n, 0

    usage = [[0] * num_resources for _ in range(horizon)]
    start = [0] * instance.n
    active_resource_demands = [
        [(r, demands[i][r]) for r in range(num_resources) if demands[i][r] > 0]
        for i in range(instance.n)
    ]

    for i in order:
        reqs = active_resource_demands[i]
        for r, demand in reqs:
            if demand > instance.resources[r]:
                raise ValueError(
                    f"Infeasible instance: activity {i} demand on resource {r} "
                    f"({demand}) exceeds capacity ({instance.resources[r]})"
                )

        earliest = max((start[p] + durations[p] for p in pred[i]), default=0)
        t = _earliest_resource_feasible_start(
            instance,
            usage,
            reqs,
            durations[i],
            earliest,
            horizon,
        )
        if t is None:
            raise ValueError(
                f"Infeasible instance: unable to schedule activity {i} within horizon {horizon}"
            )

        start[i] = t
        for dt in range(durations[i]):
            row = usage[t + dt]
            for r, demand in reqs:
                row[r] += demand

    makespan = max(start[i] + durations[i] for i in range(instance.n))
    return start, makespan


def classify_and_solve_topological(instance):
    if instance.n <= 0:
        return "feasible", [], 0, ""

    if not resource_feasible(instance):
        return "true_infeasible", None, None, "capacity violation"

    try:
        schedule, makespan = solve_topological(instance)
    except ValueError as exc:
        return "true_infeasible", None, None, str(exc)

    ok, msg, checked_makespan = validate_schedule(instance, schedule)
    if not ok:
        return "heuristic_failed", None, None, f"internal invalid schedule: {msg}"

    return "feasible", schedule, checked_makespan, "topological_order + earliest_resource_feasible_sgs"


def solve_rcpsp(instance):
    status, schedule, makespan, message = classify_and_solve_topological(instance)
    if status == "feasible":
        return schedule, makespan
    raise ValueError(message or status)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Baseline RCPSP solver using topological order and earliest resource-feasible scheduling"
    )
    parser.add_argument("instance", help="Path to .SCH instance file")
    return parser.parse_args()


def main():
    args = parse_args()
    instance = parse_sch(args.instance)
    status, schedule, _, _ = classify_and_solve_topological(instance)

    if status != "feasible" or schedule is None:
        print("-1")
        return

    if instance.n <= 2:
        print("")
        return

    print(", ".join(str(schedule[j]) for j in range(1, instance.n - 1)))


if __name__ == "__main__":
    main()

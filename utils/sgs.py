import heapq

from utils.graph_utils import build_graph, compute_critical_path


def sgs(instance, priority_bias=None):
    n = instance.n
    durations = instance.durations
    demands = instance.demands
    capacities = instance.resources
    num_resources = instance.num_resources

    horizon = sum(durations)

    if horizon <= 0:
        return [0] * n, 0

    if priority_bias is None:
        priority_bias = [0.0] * n
    elif len(priority_bias) != n:
        raise ValueError("priority_bias length mismatch")

    succ, pred = build_graph(instance)
    cp = compute_critical_path(instance)

    in_degree = [len(pred[i]) for i in range(n)]

    start = [0] * n
    usage = [[0] * num_resources for _ in range(horizon)]

    # For speed: check/update only resources with non-zero demand per activity.
    active_resource_demands = [
        [(r, demands[i][r]) for r in range(num_resources) if demands[i][r] > 0]
        for i in range(n)
    ]

    ready = []
    scheduled_count = 0

    # priority: critical path first
    for i in range(n):
        if in_degree[i] == 0:
            heapq.heappush(ready, (-(cp[i] + priority_bias[i]), i))

    while ready:
        _, i = heapq.heappop(ready)

        # Quick infeasibility check: activity cannot fit resource capacities at any time.
        reqs = active_resource_demands[i]
        for r, d in reqs:
            if d > capacities[r]:
                raise ValueError(
                    f"Infeasible instance: activity {i} demand on resource {r} "
                    f"({d}) exceeds capacity ({capacities[r]})"
                )

        duration_i = durations[i]
        t = max((start[p] + durations[p] for p in pred[i]), default=0)
        latest_start = horizon - duration_i

        while t <= latest_start:
            feasible = True

            for dt in range(duration_i):
                if t + dt >= horizon:
                    feasible = False
                    break

                row = usage[t + dt]
                for r, d in reqs:
                    if row[r] + d > capacities[r]:
                        feasible = False
                        break

                if not feasible:
                    break

            if feasible:
                break

            t += 1

        if t > latest_start:
            raise ValueError(
                f"Infeasible instance: unable to schedule activity {i} within horizon {horizon}"
            )

        start[i] = t
        scheduled_count += 1

        for dt in range(duration_i):
            row = usage[t + dt]
            for r, d in reqs:
                row[r] += d

        for j in succ[i]:
            in_degree[j] -= 1
            if in_degree[j] == 0:
                heapq.heappush(ready, (-(cp[j] + priority_bias[j]), j))

    if scheduled_count != n:
        raise ValueError("No feasible topological scheduling order (possible cycle)")

    makespan = max(start[i] + durations[i] for i in range(n))
    return start, makespan
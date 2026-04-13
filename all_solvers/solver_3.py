import math
import random
import time
import heapq
from collections import deque


class RCPSPInstance:
    def __init__(self):
        self.n = 0
        self.num_resources = 0
        self.durations = []
        self.demands = []
        self.resources = []
        self.precedence = []


def parse_sch(filepath):
    inst = RCPSPInstance()

    with open(filepath, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    def parse_ints(raw_line):
        cleaned = raw_line.replace("[", " ").replace("]", " ")
        return [int(x) for x in cleaned.split()]

    idx = 0
    header = parse_ints(lines[idx])
    if len(header) < 2:
        raise ValueError(f"Invalid SCH header in {filepath}")

    n_activities_without_dummies = header[0]
    r = header[1]
    expected_n = n_activities_without_dummies + 2
    idx += 1

    precedence = []
    seen_ids = set()

    for _ in range(expected_n):
        parts = parse_ints(lines[idx])
        idx += 1
        if len(parts) < 2:
            raise ValueError(f"Invalid precedence row in {filepath}: {lines[idx - 1]}")

        i = parts[0]
        if len(parts) == 2:
            k = parts[1]
            successors = []
        elif len(parts) >= 3 and len(parts) == parts[1] + 2:
            k = parts[1]
            successors = parts[2:2 + k] if k > 0 else []
        else:
            if len(parts) < 3:
                raise ValueError(f"Invalid precedence row in {filepath}: {lines[idx - 1]}")
            k = parts[2]
            successors = parts[3:3 + k] if k > 0 else []

        seen_ids.add(i)
        for j in successors:
            precedence.append((i, j))
            seen_ids.add(j)

    if not seen_ids:
        raise ValueError(f"No activities found in {filepath}")

    n = max(max(seen_ids) + 1, expected_n)

    durations = [0] * n
    demands = [[0] * r for _ in range(n)]

    for _ in range(expected_n):
        parts = parse_ints(lines[idx])
        idx += 1
        if len(parts) < 2:
            raise ValueError(f"Invalid duration row in {filepath}: {lines[idx - 1]}")

        i = parts[0]
        if len(parts) >= 2 + r and len(parts) == 2 + r:
            duration = parts[1]
            demand_values = parts[2:2 + r]
        else:
            if len(parts) < 3:
                raise ValueError(f"Invalid duration row in {filepath}: {lines[idx - 1]}")
            duration = parts[2]
            demand_values = parts[3:3 + r]

        if len(demand_values) < r:
            demand_values += [0] * (r - len(demand_values))

        durations[i] = duration
        demands[i] = demand_values

    capacities = parse_ints(lines[idx])
    if len(capacities) < r:
        raise ValueError(f"Invalid resource capacity row in {filepath}: {lines[idx]}")

    inst.n = n
    inst.num_resources = r
    inst.precedence = precedence
    inst.durations = durations
    inst.demands = demands
    inst.resources = capacities[:r]

    return inst


def build_graph(instance):
    succ = [[] for _ in range(instance.n)]
    pred = [[] for _ in range(instance.n)]

    for i, j in instance.precedence:
        if 0 <= i < instance.n and 0 <= j < instance.n:
            succ[i].append(j)
            pred[j].append(i)

    return succ, pred


def topological_order(instance):
    succ, pred = build_graph(instance)
    in_degree = [len(pred[i]) for i in range(instance.n)]
    q = deque(i for i in range(instance.n) if in_degree[i] == 0)
    order = []

    while q:
        u = q.popleft()
        order.append(u)
        for v in succ[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                q.append(v)

    if len(order) != instance.n:
        raise ValueError("Precedence graph contains a cycle")

    return order


def compute_critical_path(instance):
    succ, _ = build_graph(instance)
    order = topological_order(instance)
    cp = [0] * instance.n

    for u in reversed(order):
        if succ[u]:
            cp[u] = instance.durations[u] + max(cp[v] for v in succ[u])
        else:
            cp[u] = instance.durations[u]

    return cp


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

    active_resource_demands = [
        [(r, demands[i][r]) for r in range(num_resources) if demands[i][r] > 0]
        for i in range(n)
    ]

    ready = []
    scheduled_count = 0

    for i in range(n):
        if in_degree[i] == 0:
            heapq.heappush(ready, (-(cp[i] + priority_bias[i]), i))

    while ready:
        _, i = heapq.heappop(ready)

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

    makespan = max(schedule[i] + durations[i] for i in range(n))
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


def _zscore(values):
    n = len(values)
    if n == 0:
        return []
    mean = sum(values) / n
    var = sum((x - mean) * (x - mean) for x in values) / n
    std = math.sqrt(var) if var > 1e-12 else 1.0
    return [(x - mean) / std for x in values]


def _compute_metrics(instance):
    succ, pred = build_graph(instance)
    topo = topological_order(instance)
    cp = compute_critical_path(instance)

    est = [0] * instance.n
    for i in topo:
        fi = est[i] + instance.durations[i]
        for j in succ[i]:
            if fi > est[j]:
                est[j] = fi

    descendants = [set() for _ in range(instance.n)]
    for i in reversed(topo):
        seen = set()
        for j in succ[i]:
            seen.add(j)
            seen.update(descendants[j])
        descendants[i] = seen

    desc = [len(s) for s in descendants]
    dur = list(instance.durations)
    res_weight = [sum(instance.demands[i]) for i in range(instance.n)]

    return {
        "succ": succ,
        "pred": pred,
        "topo": topo,
        "cp": cp,
        "est": est,
        "desc": desc,
        "dur": dur,
        "res": res_weight,
        "features": [
            _zscore(desc),
            _zscore(res_weight),
            _zscore(dur),
            _zscore([-x for x in est]),
            _zscore(cp),
        ],
    }


def _bias_from_weights(features, weights):
    n = len(features[0]) if features else 0
    bias = [0.0] * n
    for w, f in zip(weights, features):
        if abs(w) < 1e-12:
            continue
        for i in range(n):
            bias[i] += w * f[i]
    return bias


def _find_latest_feasible(instance, usage, reqs, duration, latest):
    if duration <= 0:
        return max(0, latest)

    t = latest
    while t >= 0:
        feasible = True
        for dt in range(duration):
            row = usage[t + dt]
            for r, dem in reqs:
                if row[r] + dem > instance.resources[r]:
                    feasible = False
                    break
            if not feasible:
                break
        if feasible:
            return t
        t -= 1
    return None


def _right_justify(instance, schedule, metrics, makespan):
    n = instance.n
    succ = metrics["succ"]
    topo = metrics["topo"]
    durations = instance.durations
    reqs = [
        [(r, instance.demands[i][r]) for r in range(instance.num_resources) if instance.demands[i][r] > 0]
        for i in range(n)
    ]

    horizon = max(1, makespan)
    usage = [[0] * instance.num_resources for _ in range(horizon)]
    new_start = [-1] * n

    for i in reversed(topo):
        d = durations[i]
        latest = makespan - d
        if succ[i]:
            latest_from_succ = min(new_start[j] - d for j in succ[i] if new_start[j] >= 0)
            latest = min(latest, latest_from_succ)

        latest = max(0, latest)
        if latest + d > horizon:
            usage.extend([[0] * instance.num_resources for _ in range(latest + d - horizon)])
            horizon = latest + d

        t = _find_latest_feasible(instance, usage, reqs[i], d, latest)
        if t is None:
            t = max(0, min(schedule[i], latest))

        new_start[i] = t
        for dt in range(d):
            row = usage[t + dt]
            for r, dem in reqs[i]:
                row[r] += dem

    return new_start


def _sgs_from_rank(instance, rank, metrics):
    n = instance.n
    succ = metrics["succ"]
    pred = metrics["pred"]
    durations = instance.durations
    reqs = [
        [(r, instance.demands[i][r]) for r in range(instance.num_resources) if instance.demands[i][r] > 0]
        for i in range(n)
    ]

    in_degree = [len(pred[i]) for i in range(n)]
    ready = [i for i in range(n) if in_degree[i] == 0]
    ready.sort(key=lambda x: (rank[x], -metrics["cp"][x], x))

    horizon = max(1, sum(durations))
    usage = [[0] * instance.num_resources for _ in range(horizon)]
    start = [0] * n
    scheduled_count = 0

    while ready:
        i = ready.pop(0)
        d = durations[i]
        t = max((start[p] + durations[p] for p in pred[i]), default=0)

        while True:
            if t + d > horizon:
                usage.extend([[0] * instance.num_resources for _ in range(t + d - horizon)])
                horizon = t + d

            feasible = True
            for dt in range(d):
                row = usage[t + dt]
                for r, dem in reqs[i]:
                    if row[r] + dem > instance.resources[r]:
                        feasible = False
                        break
                if not feasible:
                    break
            if feasible:
                break
            t += 1

        start[i] = t
        scheduled_count += 1

        for dt in range(d):
            row = usage[t + dt]
            for r, dem in reqs[i]:
                row[r] += dem

        for j in succ[i]:
            in_degree[j] -= 1
            if in_degree[j] == 0:
                ready.append(j)

        ready.sort(key=lambda x: (rank[x], -metrics["cp"][x], x))

    if scheduled_count != n:
        raise ValueError("No feasible topological scheduling order")

    mk = max(start[i] + durations[i] for i in range(n))
    return start, mk


def _double_justify(instance, schedule, metrics, passes=2):
    best = list(schedule)
    ok, _, best_mk = validate_schedule(instance, best)
    if not ok:
        return schedule, None

    for _ in range(max(1, passes)):
        right = _right_justify(instance, best, metrics, best_mk)
        order = sorted(range(instance.n), key=lambda i: (right[i], i))
        rank = [0] * instance.n
        for pos, act in enumerate(order):
            rank[act] = pos

        left, left_mk = _sgs_from_rank(instance, rank, metrics)
        ok, _, checked = validate_schedule(instance, left)
        if not ok:
            break
        if checked < best_mk:
            best = left
            best_mk = checked
        else:
            break

    return best, best_mk


def _evaluate_bias_solution(instance, metrics, bias):
    schedule, _ = sgs(instance, priority_bias=bias)
    ok, msg, checked_makespan = validate_schedule(instance, schedule)
    if not ok:
        raise ValueError(msg)

    schedule, improved_mk = _double_justify(instance, schedule, metrics, passes=2)
    ok, msg, checked_makespan = validate_schedule(instance, schedule)
    if not ok:
        raise ValueError(msg)
    if improved_mk is None:
        improved_mk = checked_makespan
    return schedule, improved_mk


def classify_and_solve_best(instance, time_limit_s=28.0, seed=42, starts=120):
    if instance.n <= 0:
        return "feasible", [], 0, ""

    if not resource_feasible(instance):
        return "true_infeasible", None, None, "capacity violation"

    try:
        topological_order(instance)
    except ValueError as exc:
        return "true_infeasible", None, None, str(exc)

    rng = random.Random(seed)
    n = instance.n
    start_clock = time.perf_counter()
    budget_s = max(0.2, float(time_limit_s))
    deadline = start_clock + budget_s
    # Approximation-oriented early-stop guard: return early if search stagnates.
    min_runtime_s = min(budget_s, max(0.15, 0.20 * budget_s))
    stagnation_window_s = min(2.0, max(0.30, 0.35 * budget_s))

    metrics = _compute_metrics(instance)
    features = metrics["features"]

    best_schedule = None
    best_makespan = float("inf")
    best_weights = None
    last_error = ""
    improvements = 0
    last_improve_t = start_clock

    # Deterministic portfolio starts.
    seed_weights = [
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0, 0.0],
        [0.4, 0.3, 0.1, 0.2, 0.6],
        [0.7, 0.2, 0.0, 0.2, 0.8],
    ]

    def try_candidate(weights, activity_noise=0.0):
        nonlocal best_schedule, best_makespan, best_weights, last_error, improvements, last_improve_t
        bias = _bias_from_weights(features, weights)
        if activity_noise > 0:
            m = max(1, n // 10)
            for i in rng.sample(range(n), m):
                bias[i] += rng.uniform(-activity_noise, activity_noise)
        try:
            schedule, mk = _evaluate_bias_solution(instance, metrics, bias)
            if mk < best_makespan:
                best_makespan = mk
                best_schedule = schedule
                best_weights = list(weights)
                improvements += 1
                last_improve_t = time.perf_counter()
                return True
        except ValueError as exc:
            last_error = str(exc)
        return False

    for w in seed_weights:
        if time.perf_counter() >= deadline:
            break
        try_candidate(w)

    # Randomized multistart around portfolio.
    for _ in range(max(1, int(starts))):
        if time.perf_counter() >= deadline:
            break
        base = rng.choice(seed_weights)
        w = [base[i] + rng.uniform(-0.8, 0.8) for i in range(len(base))]
        try_candidate(w, activity_noise=0.25)

    if best_schedule is None:
        return "heuristic_failed", None, None, (last_error or "no feasible schedule found")

    # Simulated-annealing style weight search near incumbent.
    current_w = list(best_weights if best_weights is not None else seed_weights[0])
    current_mk = best_makespan
    temp = max(1.0, 0.05 * current_mk)
    step = 0.35

    while time.perf_counter() < deadline:
        now = time.perf_counter()
        if (now - start_clock) >= min_runtime_s and (now - last_improve_t) >= stagnation_window_s:
            break

        cand_w = [x + rng.gauss(0.0, step) for x in current_w]
        bias = _bias_from_weights(features, cand_w)

        m = max(1, n // 12)
        for i in rng.sample(range(n), m):
            bias[i] += rng.uniform(-0.2, 0.2)

        try:
            cand_schedule, cand_mk = _evaluate_bias_solution(instance, metrics, bias)
        except ValueError as exc:
            last_error = str(exc)
            temp = max(0.5, temp * 0.995)
            step = max(0.08, step * 0.999)
            continue

        delta = cand_mk - current_mk
        if delta <= 0 or rng.random() < math.exp(-delta / max(0.5, temp)):
            current_w = cand_w
            current_mk = cand_mk

        if cand_mk < best_makespan:
            best_makespan = cand_mk
            best_schedule = cand_schedule
            best_weights = list(cand_w)
            improvements += 1
            last_improve_t = time.perf_counter()

        temp = max(0.5, temp * 0.996)
        step = max(0.08, step * 0.999)

    elapsed = time.perf_counter() - start_clock
    return "feasible", best_schedule, best_makespan, (
        f"solver_3 starts={starts}, improvements={improvements}, elapsed={elapsed:.3f}s"
    )


def classify_and_solve(instance):
    return classify_and_solve_best(instance, time_limit_s=28.0, seed=42, starts=120)


def solve_rcpsp(instance):
    status, schedule, makespan, message = classify_and_solve(instance)
    if status == "feasible":
        return schedule, makespan
    raise ValueError(message or status)


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python solver_3.py <instance_file.SCH>")
        return

    instance = parse_sch(sys.argv[1])
    status, schedule, _, _ = classify_and_solve(instance)

    if status != "feasible":
        print("-1")
        return

    if instance.n <= 2:
        print("")
        return

    print(", ".join(str(schedule[j]) for j in range(1, instance.n - 1)))


if __name__ == "__main__":
    main()

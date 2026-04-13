import math
import random
import time
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


# ---------------------------
# Core validity / feasibility
# ---------------------------

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


# ---------------------------
# Metrics and decoding
# ---------------------------

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
    res = [sum(instance.demands[i]) for i in range(instance.n)]

    return {
        "succ": succ,
        "pred": pred,
        "topo": topo,
        "cp": cp,
        "est": est,
        "desc": desc,
        "dur": dur,
        "res": res,
        "features": [
            _zscore(desc),
            _zscore(res),
            _zscore(dur),
            _zscore([-x for x in est]),
            _zscore(cp),
        ],
    }


def _keys_from_weights(features, weights):
    n = len(features[0]) if features else 0
    keys = [0.0] * n
    for w, f in zip(weights, features):
        if abs(w) < 1e-12:
            continue
        for i in range(n):
            keys[i] += w * f[i]
    return keys


def _decode_schedule(instance, metrics, keys):
    n = instance.n
    succ = metrics["succ"]
    pred = metrics["pred"]
    durations = instance.durations
    num_resources = instance.num_resources

    reqs = [
        [(r, instance.demands[i][r]) for r in range(num_resources) if instance.demands[i][r] > 0]
        for i in range(n)
    ]

    in_degree = [len(pred[i]) for i in range(n)]
    ready = [i for i in range(n) if in_degree[i] == 0]

    horizon = max(1, sum(durations))
    usage = [[0] * num_resources for _ in range(horizon)]
    start = [0] * n
    scheduled_count = 0

    while ready:
        ready.sort(key=lambda x: (keys[x], -metrics["cp"][x], x))
        i = ready.pop(0)

        d = durations[i]
        t = max((start[p] + durations[p] for p in pred[i]), default=0)

        while True:
            if t + d > horizon:
                usage.extend([[0] * num_resources for _ in range(t + d - horizon)])
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

    if scheduled_count != n:
        raise ValueError("No feasible topological scheduling order")

    mk = max(start[i] + durations[i] for i in range(n))
    return start, mk


# ---------------------------
# Justification (post-improve)
# ---------------------------

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


def _double_justify(instance, metrics, schedule, passes=1):
    best = list(schedule)
    ok, _, best_mk = validate_schedule(instance, best)
    if not ok:
        return schedule, None

    for _ in range(max(1, passes)):
        right = _right_justify(instance, best, metrics, best_mk)
        order = sorted(range(instance.n), key=lambda i: (right[i], i))
        rank = [0.0] * instance.n
        for pos, act in enumerate(order):
            rank[act] = float(pos)

        left, _ = _decode_schedule(instance, metrics, rank)
        ok, _, mk = validate_schedule(instance, left)
        if ok and mk < best_mk:
            best = left
            best_mk = mk
        else:
            break

    return best, best_mk


# ---------------------------
# Hybrid metaheuristic (ALNS + GA + path relinking + tabu)
# ---------------------------

def _signature(keys, precision=2):
    return tuple(round(k, precision) for k in keys)


def _destroy_random(keys, rng, fraction=0.20, magnitude=0.8):
    out = list(keys)
    n = len(out)
    m = max(1, int(n * fraction))
    for i in rng.sample(range(n), m):
        out[i] += rng.uniform(-magnitude, magnitude)
    return out


def _destroy_critical(keys, metrics, rng, fraction=0.20, magnitude=0.8):
    out = list(keys)
    n = len(out)
    order = sorted(range(n), key=lambda i: metrics["cp"][i], reverse=True)
    m = max(1, int(n * fraction))
    core = order[:m]
    for i in core:
        out[i] += rng.uniform(-magnitude, magnitude)
    return out


def _destroy_resource(keys, metrics, rng, fraction=0.20, magnitude=0.8):
    out = list(keys)
    n = len(out)
    order = sorted(range(n), key=lambda i: metrics["res"][i], reverse=True)
    m = max(1, int(n * fraction))
    core = order[:m]
    for i in core:
        out[i] += rng.uniform(-magnitude, magnitude)
    return out


def _path_relink(keys_a, keys_b, alpha=0.5):
    return [(1.0 - alpha) * a + alpha * b for a, b in zip(keys_a, keys_b)]


def _crossover(keys_a, keys_b, rng):
    child = []
    for a, b in zip(keys_a, keys_b):
        if rng.random() < 0.5:
            child.append(a)
        else:
            child.append(b)
    return child


def _mutate(keys, rng, sigma=0.15, prob=0.15):
    out = list(keys)
    for i in range(len(out)):
        if rng.random() < prob:
            out[i] += rng.gauss(0.0, sigma)
    return out


def _evaluate_keys(instance, metrics, keys, justify_passes=1):
    schedule, _ = _decode_schedule(instance, metrics, keys)
    schedule, mk = _double_justify(instance, metrics, schedule, passes=justify_passes)
    ok, msg, checked_mk = validate_schedule(instance, schedule)
    if not ok:
        raise ValueError(msg)
    return schedule, checked_mk


def classify_and_solve_best(instance, time_limit_s=2.0, seed=42):
    if instance.n <= 0:
        return "feasible", [], 0, ""

    if not resource_feasible(instance):
        return "true_infeasible", None, None, "capacity violation"

    try:
        topological_order(instance)
    except ValueError as exc:
        return "true_infeasible", None, None, str(exc)

    rng = random.Random(seed)
    metrics = _compute_metrics(instance)
    features = metrics["features"]

    start_clock = time.perf_counter()
    budget = max(0.2, float(time_limit_s))
    deadline = start_clock + budget

    best_schedule = None
    best_mk = float("inf")
    best_keys = None

    current_schedule = None
    current_mk = float("inf")
    current_keys = None

    last_error = ""

    # Portfolio seeds
    seed_weights = [
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [0.8, 0.0, 0.1, 0.1, 0.8],
        [0.0, 0.8, 0.2, 0.0, 0.4],
        [0.4, 0.3, 0.1, 0.2, 0.6],
        [0.1, 0.1, 0.7, 0.2, 0.3],
    ]

    population = []
    for w in seed_weights:
        if time.perf_counter() >= deadline:
            break
        keys = _keys_from_weights(features, w)
        keys = _mutate(keys, rng, sigma=0.20, prob=0.20)
        try:
            sch, mk = _evaluate_keys(instance, metrics, keys, justify_passes=1)
            population.append((mk, keys, sch))
        except ValueError as exc:
            last_error = str(exc)

    # Random population add-ons
    while len(population) < 10 and time.perf_counter() < deadline:
        keys = [rng.uniform(-1.0, 1.0) for _ in range(instance.n)]
        try:
            sch, mk = _evaluate_keys(instance, metrics, keys, justify_passes=1)
            population.append((mk, keys, sch))
        except ValueError as exc:
            last_error = str(exc)

    if not population:
        return "heuristic_failed", None, None, (last_error or "no feasible schedule found")

    population.sort(key=lambda x: x[0])
    best_mk, best_keys, best_schedule = population[0][0], list(population[0][1]), list(population[0][2])
    current_mk, current_keys, current_schedule = best_mk, list(best_keys), list(best_schedule)

    # Adaptive ALNS operator weights
    op_names = ["random", "critical", "resource"]
    op_weights = {k: 1.0 for k in op_names}
    op_success = {k: 0 for k in op_names}

    tabu = deque(maxlen=256)
    tabu_set = set()

    def tabu_add(sig):
        if len(tabu) == tabu.maxlen:
            old = tabu.popleft()
            tabu_set.discard(old)
        tabu.append(sig)
        tabu_set.add(sig)

    def pick_operator():
        total = sum(op_weights.values())
        x = rng.uniform(0.0, total)
        acc = 0.0
        for k in op_names:
            acc += op_weights[k]
            if x <= acc:
                return k
        return op_names[-1]

    no_improve_iters = 0
    temp = max(0.5, 0.03 * best_mk)

    while time.perf_counter() < deadline:
        op = pick_operator()

        # ALNS destroy step
        if op == "random":
            cand_keys = _destroy_random(current_keys, rng, fraction=0.22, magnitude=0.9)
        elif op == "critical":
            cand_keys = _destroy_critical(current_keys, metrics, rng, fraction=0.20, magnitude=0.8)
        else:
            cand_keys = _destroy_resource(current_keys, metrics, rng, fraction=0.20, magnitude=0.8)

        # Path relinking toward incumbent best
        if best_keys is not None:
            alpha = rng.uniform(0.25, 0.65)
            cand_keys = _path_relink(cand_keys, best_keys, alpha=alpha)

        # Occasional GA crossover with another elite candidate
        if len(population) >= 2 and rng.random() < 0.25:
            elite = population[rng.randrange(min(5, len(population)))]
            cand_keys = _crossover(cand_keys, elite[1], rng)
            cand_keys = _mutate(cand_keys, rng, sigma=0.12, prob=0.12)

        sig = _signature(cand_keys, precision=2)
        if sig in tabu_set:
            no_improve_iters += 1
            temp = max(0.25, temp * 0.995)
            if no_improve_iters > 40 and time.perf_counter() - start_clock > 0.35 * budget:
                break
            continue

        try:
            cand_schedule, cand_mk = _evaluate_keys(instance, metrics, cand_keys, justify_passes=1)
        except ValueError as exc:
            last_error = str(exc)
            tabu_add(sig)
            no_improve_iters += 1
            temp = max(0.25, temp * 0.995)
            continue

        delta = cand_mk - current_mk
        accept = delta <= 0 or rng.random() < math.exp(-delta / max(0.25, temp))

        if accept:
            current_keys = list(cand_keys)
            current_schedule = list(cand_schedule)
            current_mk = cand_mk

        if cand_mk < best_mk:
            best_mk = cand_mk
            best_keys = list(cand_keys)
            best_schedule = list(cand_schedule)
            op_success[op] += 1
            op_weights[op] = min(8.0, op_weights[op] + 0.25)
            no_improve_iters = 0
        else:
            no_improve_iters += 1
            op_weights[op] = max(0.4, op_weights[op] * 0.997)

        # Maintain tiny elite pool
        population.append((cand_mk, list(cand_keys), list(cand_schedule)))
        population.sort(key=lambda x: x[0])
        if len(population) > 16:
            population = population[:16]

        tabu_add(sig)
        temp = max(0.25, temp * 0.998)

        # Early stop after enough stagnation
        if no_improve_iters > 55 and time.perf_counter() - start_clock > 0.45 * budget:
            break

    if best_schedule is None:
        return "heuristic_failed", None, None, (last_error or "no feasible schedule found")

    elapsed = time.perf_counter() - start_clock
    msg = (
        f"solver_4 hybrid(ALNS+GA+PR+tabu), elapsed={elapsed:.3f}s, "
        f"ops={op_success}"
    )
    return "feasible", best_schedule, best_mk, msg


def classify_and_solve(instance):
    # Fast default for benchmark-style runs.
    return classify_and_solve_best(instance, time_limit_s=2.0, seed=42)


def solve_rcpsp(instance):
    status, schedule, makespan, message = classify_and_solve(instance)
    if status == "feasible":
        return schedule, makespan
    raise ValueError(message or status)


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python solver_4.py <instance_file.SCH>")
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

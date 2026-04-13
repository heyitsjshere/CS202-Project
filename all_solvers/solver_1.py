import time
import random
import heapq
import argparse
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
	usage = [[0] * num_resources for _ in range(makespan)]

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


def classify_and_solve(instance):
	if instance.n <= 0:
		return "feasible", [], 0, ""

	if not resource_feasible(instance):
		return "true_infeasible", None, None, "capacity violation"

	try:
		topological_order(instance)
	except ValueError as exc:
		return "true_infeasible", None, None, str(exc)

	try:
		schedule, makespan = sgs(instance)
	except ValueError as exc:
		return "heuristic_failed", None, None, str(exc)

	ok, msg, validated_makespan = validate_schedule(instance, schedule)
	if not ok:
		return "heuristic_failed", None, None, f"invalid heuristic schedule: {msg}"

	return "feasible", schedule, validated_makespan, ""


def _evaluate_bias_solution(instance, bias):
	"""Run SGS with a priority bias and validate the resulting schedule."""
	schedule, _ = sgs(instance, priority_bias=bias)
	ok, msg, checked_makespan = validate_schedule(instance, schedule)
	if not ok:
		raise ValueError(msg)
	return schedule, checked_makespan


def classify_and_solve_multistart(
	instance,
	starts=30,
	seed=42,
	ls_iters=20,
	ls_neighbors=6,
	ls_step=0.20,
):
	"""Scalable heuristic mode: randomized multistart SGS + local bias refinement."""
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
	trials = max(1, int(starts))
	ls_iters = max(0, int(ls_iters))
	ls_neighbors = max(1, int(ls_neighbors))
	ls_step = max(0.01, float(ls_step))

	best_schedule = None
	best_makespan = float("inf")
	best_bias = None
	last_error = ""

	for _ in range(trials):
		bias = [rng.uniform(-0.5, 0.5) for _ in range(n)]
		try:
			schedule, checked_makespan = _evaluate_bias_solution(instance, bias)
			if checked_makespan < best_makespan:
				best_makespan = checked_makespan
				best_schedule = schedule
				best_bias = list(bias)
		except ValueError as exc:
			last_error = str(exc)

	# Fallback seed point for local search if all randomized starts failed.
	if best_bias is None:
		try:
			zero_bias = [0.0] * n
			schedule, checked_makespan = _evaluate_bias_solution(instance, zero_bias)
			best_schedule = schedule
			best_makespan = checked_makespan
			best_bias = zero_bias
		except ValueError as exc:
			last_error = str(exc)

	# Local search in bias space: mutate a few priorities and keep improving moves.
	local_improvements = 0
	if best_bias is not None and ls_iters > 0:
		current_bias = list(best_bias)
		current_makespan = best_makespan
		step = ls_step

		for it in range(ls_iters):
			iter_best_makespan = current_makespan
			iter_best_schedule = None
			iter_best_bias = None

			for _ in range(ls_neighbors):
				candidate_bias = list(current_bias)
				mut_count = max(1, min(n, n // 8))
				for j in rng.sample(range(n), mut_count):
					candidate_bias[j] += rng.uniform(-step, step)

				try:
					schedule, mk = _evaluate_bias_solution(instance, candidate_bias)
				except ValueError as exc:
					last_error = str(exc)
					continue

				if mk < iter_best_makespan:
					iter_best_makespan = mk
					iter_best_schedule = schedule
					iter_best_bias = candidate_bias

			if iter_best_bias is not None:
				current_bias = iter_best_bias
				current_makespan = iter_best_makespan
				best_bias = iter_best_bias
				best_schedule = iter_best_schedule
				best_makespan = iter_best_makespan
				local_improvements += 1
			else:
				# Gentle cooling and occasional kick to escape plateaus.
				step = max(0.02, step * 0.90)
				if it % 5 == 4:
					for j in rng.sample(range(n), max(1, n // 12)):
						current_bias[j] += rng.uniform(-0.15, 0.15)

	if best_schedule is not None:
		msg = f"multistart={trials}"
		if ls_iters > 0:
			msg += f", local_search={ls_iters}, improved_iters={local_improvements}"
		return "feasible", best_schedule, best_makespan, msg

	return "heuristic_failed", None, None, (last_error or "no feasible schedule found in multistart")


def classify_and_solve_optimal(instance, time_limit_s=10.0):
	"""
	Exact branch-and-bound search over active schedules.

	Returns statuses:
	  - feasible_optimal
	  - feasible_not_proven (time limit reached with incumbent)
	  - true_infeasible
	  - heuristic_failed
	"""
	n = instance.n
	if n <= 0:
		return "feasible_optimal", [], 0, ""

	if not resource_feasible(instance):
		return "true_infeasible", None, None, "capacity violation"

	try:
		topo = topological_order(instance)
	except ValueError as exc:
		return "true_infeasible", None, None, str(exc)

	succ, pred = build_graph(instance)
	cp = compute_critical_path(instance)

	durations = instance.durations
	demands = instance.demands
	capacities = instance.resources
	num_resources = instance.num_resources
	horizon = sum(durations)

	if horizon <= 0:
		return "feasible_optimal", [0] * n, 0, ""

	reqs = [[(r, demands[i][r]) for r in range(num_resources) if demands[i][r] > 0] for i in range(n)]

	base_status, base_schedule, base_makespan, _ = classify_and_solve_multistart(
		instance,
		starts=min(64, max(8, n * 2)),
		seed=42,
	)
	best_schedule = None
	best_makespan = float("inf")
	if base_status == "feasible":
		best_schedule = list(base_schedule)
		best_makespan = base_makespan

	usage = [[0] * num_resources for _ in range(horizon)]
	start = [-1] * n
	scheduled = [False] * n
	timed_out = [False]
	deadline = (time.perf_counter() + float(time_limit_s)) if time_limit_s and time_limit_s > 0 else None

	def earliest_feasible_start(job, est, latest_start):
		d = durations[job]
		if d == 0:
			return est

		t = est
		while t <= latest_start:
			feasible = True
			for dt in range(d):
				row = usage[t + dt]
				for r, dem in reqs[job]:
					if row[r] + dem > capacities[r]:
						feasible = False
						break
				if not feasible:
					break
			if feasible:
				return t
			t += 1
		return None

	def precedence_lower_bound(current_finish):
		ef = [0] * n
		for u in topo:
			est = 0
			for p in pred[u]:
				pf = (start[p] + durations[p]) if scheduled[p] else ef[p]
				if pf > est:
					est = pf

			if scheduled[u]:
				# Start is fixed at scheduled[u]; keep consistency with precedence.
				ef[u] = max(est, start[u]) + durations[u]
			else:
				ef[u] = est + durations[u]

		return max(current_finish, max(ef))

	def resource_lower_bound():
		lb = 0
		for r in range(num_resources):
			cap = capacities[r]
			if cap <= 0:
				continue
			remaining_work = 0
			for i in range(n):
				if not scheduled[i]:
					remaining_work += durations[i] * demands[i][r]
			lb_r = (remaining_work + cap - 1) // cap
			if lb_r > lb:
				lb = lb_r
		return lb

	def dfs(scheduled_count, current_finish):
		nonlocal best_schedule, best_makespan

		if deadline is not None and time.perf_counter() > deadline:
			timed_out[0] = True
			return

		lb = max(precedence_lower_bound(current_finish), resource_lower_bound())
		if lb >= best_makespan:
			return

		if scheduled_count == n:
			if current_finish < best_makespan:
				best_makespan = current_finish
				best_schedule = list(start)
			return

		ready = []
		for i in range(n):
			if scheduled[i]:
				continue
			if all(scheduled[p] for p in pred[i]):
				ready.append(i)

		if not ready:
			return

		# Most-constrained-first branching with feasible-start lookahead.
		candidates = []
		for i in ready:
			est = max((start[p] + durations[p] for p in pred[i]), default=0)
			latest_start = horizon - durations[i]
			if best_makespan < float("inf"):
				latest_start = min(latest_start, best_makespan - durations[i])
			if latest_start < est:
				continue

			t = earliest_feasible_start(i, est, latest_start)
			if t is None:
				continue

			slack = latest_start - t
			pressure = sum((dem / capacities[r]) if capacities[r] > 0 else dem for r, dem in reqs[i])
			candidates.append((slack, t, -pressure, -cp[i], -len(succ[i]), i, t))

		if not candidates:
			return

		candidates.sort()

		for _, _, _, _, _, i, t in candidates:

			d = durations[i]
			scheduled[i] = True
			start[i] = t
			for dt in range(d):
				row = usage[t + dt]
				for r, dem in reqs[i]:
					row[r] += dem

			dfs(scheduled_count + 1, max(current_finish, t + d))

			for dt in range(d):
				row = usage[t + dt]
				for r, dem in reqs[i]:
					row[r] -= dem
			start[i] = -1
			scheduled[i] = False

			if timed_out[0]:
				return

	dfs(0, 0)

	if best_schedule is None:
		if timed_out[0]:
			return "heuristic_failed", None, None, "time limit reached without incumbent"
		return "true_infeasible", None, None, "no feasible schedule exists"

	ok, msg, checked_makespan = validate_schedule(instance, best_schedule)
	if not ok:
		return "heuristic_failed", None, None, f"internal invalid schedule: {msg}"

	if timed_out[0]:
		return "feasible_not_proven", best_schedule, checked_makespan, "time limit reached"
	return "feasible_optimal", best_schedule, checked_makespan, ""


def solve_rcpsp(instance):
	"""Default heuristic solve for speed."""
	status, schedule, makespan, message = classify_and_solve(instance)
	if status == "feasible":
		return schedule, makespan
	raise ValueError(message or status)


def main():
	parser = argparse.ArgumentParser(description="Standalone solver_1")
	parser.add_argument("instance", help="Path to .SCH instance")
	parser.add_argument("--time-limit", type=float, default=2.0, help="Accepted for benchmark parity")
	parser.add_argument("--starts", type=int, default=30)
	parser.add_argument("--seed", type=int, default=42)
	args = parser.parse_args()

	instance = parse_sch(args.instance)
	status, schedule, _, _ = classify_and_solve_multistart(
		instance,
		starts=max(1, args.starts),
		seed=args.seed,
	)

	if status != "feasible":
		print("-1")
		return

	if instance.n <= 2:
		print("")
		return

	print(", ".join(str(schedule[j]) for j in range(1, instance.n - 1)))


if __name__ == "__main__":
	main()

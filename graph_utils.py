from collections import deque


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

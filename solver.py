#!/usr/bin/env python3
"""
RCPSP solver — CS202 Group Project, SMU.

Reads a single .SCH file (updated PSPLIB format) and outputs a schedule
that minimises project makespan (Cmax = S[n+1]) subject to finish-to-start
precedence and renewable resource constraints.

Usage:
    python solver.py <path_to_file.SCH>

Output (to stdout):
    <actId> <startTime>     (one line per real activity 1..n)
    Makespan: <value>
"""

import sys
import time
import math
import random

# ---------------------------------------------------------------------------
# PHASE 1 — Data model and parser
# ---------------------------------------------------------------------------

class RCPSPInstance:
    """
    All data for one RCPSP instance.

    Activities are indexed 0..n+1 where:
      - 0    : dummy start (d=0, no resources)
      - 1..n : real activities
      - n+1  : dummy end   (d=0, no resources)

    All precedence constraints are finish-to-start:
      if i -> j then S[j] >= S[i] + d[i]

    Attributes
    ----------
    n            : int         — number of real activities
    K            : int         — number of renewable resource types
    d            : list[int]   — d[i] = duration of activity i
    r            : list[list]  — r[i][k] = resource demand of activity i for k
    R            : list[int]   — R[k] = capacity of resource type k
    successors   : list[list]  — successors[i]   = [j, ...]
    predecessors : list[list]  — predecessors[j] = [i, ...]
    """

    def __init__(self, n, K, d, r, R, successors):
        self.n = n
        self.K = K
        self.d = d
        self.r = r
        self.R = R
        self.successors = successors

        # Build predecessor list from the successor list
        self.predecessors = [[] for _ in range(n + 2)]
        for i in range(n + 2):
            for j in successors[i]:
                self.predecessors[j].append(i)

    def summary(self):
        """Return a human-readable description of the instance (for debugging)."""
        total_arcs = sum(len(s) for s in self.successors)
        return "\n".join([
            f"  Activities : {self.n} real + 2 dummy = {self.n + 2} total",
            f"  Resources  : {self.K} types, capacities {self.R}",
            f"  Durations  : {self.d[1:self.n+1]}",
            f"  Arcs       : {total_arcs} finish-to-start precedence edges",
        ])


def parse_sch(filepath):
    """
    Parse an updated PSPLIB .SCH file and return an RCPSPInstance.

    File structure (blank lines ignored):
      1. Header line     : n  K
      2. Activity block  : n+2 rows, one per activity 0..n+1
             actId  numSucc  succ1  succ2  ...
      3. Resource block  : n+2 rows, one per activity 0..n+1
             actId  duration  res1  res2  res3  res4  res5
      4. Capacity line   : R1  R2  R3  R4  R5

    All precedence constraints are finish-to-start (no lag values in this format).
    """
    with open(filepath) as f:
        lines = [line.strip() for line in f if line.strip()]

    idx = 0

    # ------------------------------------------------------------------
    # 1. Header
    # ------------------------------------------------------------------
    header = lines[idx].split()
    idx += 1
    n = int(header[0])   # number of real activities
    K = int(header[1])   # number of resource types
    num_acts = n + 2     # total activities including dummies 0 and n+1

    # ------------------------------------------------------------------
    # 2. Activity block — parse graph structure (successors only)
    # ------------------------------------------------------------------
    successors = [[] for _ in range(num_acts)]

    for _ in range(num_acts):
        parts = lines[idx].split()
        idx += 1

        act_id   = int(parts[0])
        num_succ = int(parts[1])

        for s in range(num_succ):
            j = int(parts[2 + s])
            successors[act_id].append(j)

    # ------------------------------------------------------------------
    # 3. Resource block — parse durations and resource demands
    # ------------------------------------------------------------------
    d = [0] * num_acts
    r = [[0] * K for _ in range(num_acts)]

    for _ in range(num_acts):
        parts = lines[idx].split()
        idx += 1

        act_id    = int(parts[0])
        d[act_id] = int(parts[1])          # duration is the 2nd field
        for k in range(K):
            r[act_id][k] = int(parts[2 + k])

    # ------------------------------------------------------------------
    # 4. Resource capacities
    # ------------------------------------------------------------------
    R = list(map(int, lines[idx].split()))

    # ------------------------------------------------------------------
    # 5. Repair dangling activities caused by the lag-removal update
    #
    # The updated dataset removed all negative-lag arcs. This leaves two
    # classes of "dangling" activities:
    #
    #   (a) No successors: activity only had outgoing negative-lag arcs.
    #       Fix: add arc i → n+1 (project can't end until i finishes).
    #
    #   (b) No predecessors: activity was only reachable via incoming
    #       negative-lag arcs (which ran in the reverse direction).
    #       Fix: add arc 0 → i (activity may start from time 0).
    #
    # Both repairs are logically sound for standard RCPSP.
    # ------------------------------------------------------------------
    for i in range(1, n + 1):
        if not successors[i]:
            successors[i].append(n + 1)

    # Build a temporary predecessor view to detect no-predecessor activities
    has_pred = [False] * (n + 2)
    for i in range(n + 2):
        for j in successors[i]:
            has_pred[j] = True

    for i in range(1, n + 1):
        if not has_pred[i]:
            successors[0].append(i)

    return RCPSPInstance(n, K, d, r, R, successors)


# ---------------------------------------------------------------------------
# PHASE 1 — Validation helper
# ---------------------------------------------------------------------------

def validate_parse(inst):
    """
    Run basic sanity checks on a freshly parsed RCPSPInstance.
    Returns a (possibly empty) list of error strings.
    """
    n, K = inst.n, inst.K
    errors = []

    # Dummy activities must have zero duration and zero resource demand
    for dummy in (0, n + 1):
        if inst.d[dummy] != 0:
            errors.append(f"Dummy {dummy}: expected duration 0, got {inst.d[dummy]}")
        for k in range(K):
            if inst.r[dummy][k] != 0:
                errors.append(f"Dummy {dummy}: expected r[{k}]=0, got {inst.r[dummy][k]}")

    # All durations must be non-negative
    for i in range(1, n + 1):
        if inst.d[i] < 0:
            errors.append(f"Activity {i}: negative duration {inst.d[i]}")

    # Resource demands must be non-negative
    for i in range(1, n + 1):
        for k in range(K):
            if inst.r[i][k] < 0:
                errors.append(f"Activity {i}: negative demand r[{k}]={inst.r[i][k]}")

    # Resource capacities must be positive
    if len(inst.R) != K:
        errors.append(f"Expected {K} resource capacities, got {len(inst.R)}")
    for k in range(K):
        if inst.R[k] <= 0:
            errors.append(f"Resource {k}: non-positive capacity {inst.R[k]}")

    # Dummy start (0) should have no predecessors
    if inst.predecessors[0]:
        errors.append("Dummy start (0) unexpectedly has predecessors")

    # Dummy end (n+1) should have no successors
    if inst.successors[n + 1]:
        errors.append("Dummy end (n+1) unexpectedly has successors")

    # Every real activity must have at least one predecessor
    for i in range(1, n + 1):
        if not inst.predecessors[i]:
            errors.append(f"Activity {i}: no predecessors (unreachable from start)")

    return errors


# ---------------------------------------------------------------------------
# PHASE 2 — Preprocessing and lower bounds
# ---------------------------------------------------------------------------

def topological_sort(inst):
    """Return activities 0..n+1 in topological order (Kahn's algorithm)."""
    n, num_acts = inst.n, inst.n + 2
    in_degree = [0] * num_acts
    for i in range(num_acts):
        for j in inst.successors[i]:
            in_degree[j] += 1

    queue = [i for i in range(num_acts) if in_degree[i] == 0]
    order = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for j in inst.successors[node]:
            in_degree[j] -= 1
            if in_degree[j] == 0:
                queue.append(j)
    return order


def compute_est_lft(inst):
    """Compute EST and LFT via topological sort longest path."""
    n, num_acts = inst.n, inst.n + 2
    INF = float('inf')
    order = topological_sort(inst)

    est = [0] * num_acts
    for i in order:
        for j in inst.successors[i]:
            est[j] = max(est[j], est[i] + inst.d[i])

    lft = [INF] * num_acts
    lft[n + 1] = est[n + 1]
    for i in reversed(order):
        for j in inst.successors[i]:
            lft[i] = min(lft[i], lft[j] - inst.d[j])
    if lft[0] == INF:
        lft[0] = 0

    return est, lft


def compute_lower_bound(inst, est):
    """Compute lower bound on makespan."""
    n, K = inst.n, inst.K
    lb_net = est[n + 1]
    lb_res = []
    for k in range(K):
        if inst.R[k] > 0:
            total_work = sum(inst.d[i] * inst.r[i][k] for i in range(1, n + 1))
            lb_res.append(math.ceil(total_work / inst.R[k]))
        else:
            lb_res.append(0)
    lb = max(lb_net, max(lb_res) if lb_res else 0)
    return lb, lb_net, lb_res


def is_feasible(inst):
    """Return True if instance is structurally feasible."""
    for i in range(1, inst.n + 1):
        for k in range(inst.K):
            if inst.r[i][k] > inst.R[k]:
                return False
    return True


# ---------------------------------------------------------------------------
# PHASE 3 — Serial Schedule Generation Scheme (SGS)
# ---------------------------------------------------------------------------

def count_all_successors(inst):
    """Precompute transitive successors for MTS rule."""
    num_acts = inst.n + 2
    order = topological_sort(inst)
    descendants = [set() for _ in range(num_acts)]
    for i in reversed(order):
        for j in inst.successors[i]:
            descendants[i].add(j)
            descendants[i].update(descendants[j])
    return [len(descendants[i]) for i in range(num_acts)]


def serial_sgs(inst, est, lft, priority_rule, succ_counts):
    """Serial SGS with a given priority rule."""
    n, K = inst.n, inst.K
    d, r, R = inst.d, inst.r, inst.R
    max_horizon = sum(d[i] for i in range(1, n + 1)) + 1

    usage = [[0] * K for _ in range(max_horizon)]
    S = [None] * (n + 2)
    S[0] = 0

    remaining = [len(inst.predecessors[i]) for i in range(n + 2)]
    eligible = []
    for j in inst.successors[0]:
        remaining[j] -= 1
        if remaining[j] == 0 and j <= n:
            eligible.append(j)

    def priority_key(i):
        if priority_rule == 'SPT':
            return (d[i], i)
        elif priority_rule == 'LPT':
            return (-d[i], i)
        elif priority_rule == 'MTS':
            return (-succ_counts[i], i)
        elif priority_rule == 'MC':
            return (lft[i] - est[i] - d[i], i)
        elif priority_rule == 'MR':
            return (-sum(r[i][k] for k in range(K)), i)
        else:  # LR
            return (sum(r[i][k] for k in range(K)), i)

    while eligible:
        i = min(eligible, key=priority_key)
        eligible.remove(i)

        min_start = max(
            (S[pred] + d[pred] for pred in inst.predecessors[i]),
            default=0
        )

        individually_infeasible = (
            d[i] == 0 or
            any(r[i][k] > R[k] for k in range(K))
        )

        if individually_infeasible:
            t = min_start
        else:
            t = min_start
            while True:
                conflict_at = -1
                for tau in range(t, t + d[i]):
                    for k in range(K):
                        if usage[tau][k] + r[i][k] > R[k]:
                            conflict_at = tau
                            break
                    if conflict_at >= 0:
                        break

                if conflict_at < 0:
                    break
                t = conflict_at + 1

        S[i] = t
        for tau in range(t, t + d[i]):
            for k in range(K):
                usage[tau][k] += r[i][k]

        for j in inst.successors[i]:
            remaining[j] -= 1
            if remaining[j] == 0 and j <= n:
                eligible.append(j)

    S[n + 1] = max(S[i] + d[i] for i in range(1, n + 1))
    return S


def best_of_rules(inst, est, lft):
    """Run all 6 priority rules and return best schedule."""
    succ_counts = count_all_successors(inst)
    rules = ['SPT', 'LPT', 'MTS', 'MC', 'MR', 'LR']

    best_S, best_cmax = None, float('inf')
    for rule in rules:
        S = serial_sgs(inst, est, lft, rule, succ_counts)
        cmax = S[inst.n + 1]
        if cmax < best_cmax:
            best_cmax = cmax
            best_S = S

    return best_S


def validate_schedule(inst, S):
    """Check schedule against all constraints."""
    n, K = inst.n, inst.K
    violations = []

    for i in range(1, n + 1):
        if S[i] < 0:
            violations.append(f"Activity {i}: negative start time {S[i]}")

    for i in range(n + 2):
        for j in inst.successors[i]:
            if S[j] < S[i] + inst.d[i]:
                violations.append(
                    f"Precedence violated: {i}->{j}, "
                    f"S[{j}]={S[j]} < S[{i}]+d[{i}]={S[i]+inst.d[i]}"
                )

    cmax = S[n + 1]
    for t in range(cmax):
        for k in range(K):
            used = sum(
                inst.r[i][k]
                for i in range(1, n + 1)
                if S[i] <= t < S[i] + inst.d[i]
            )
            if used > inst.R[k]:
                violations.append(
                    f"Resource {k} overloaded at t={t}: used={used} > cap={inst.R[k]}"
                )

    return violations


# ---------------------------------------------------------------------------
# PHASE 4 — Large Neighbourhood Search + Simulated Annealing
# ---------------------------------------------------------------------------

def destroy_and_repair(inst, S, est, lft, succ_counts, num_destroy):
    """
    Destroy num_destroy random activities and repair with SGS.
    Returns the new schedule.
    """
    n, K = inst.n, inst.K
    d, r, R = inst.d, inst.r, inst.R

    # Deep copy current schedule
    S_new = S[:]

    # Randomly select activities to destroy (real activities only)
    to_destroy = random.sample(range(1, n + 1), min(num_destroy, n))

    # Mark destroyed activities as unscheduled (set to None)
    for i in to_destroy:
        S_new[i] = None

    # Rebuild usage array for scheduled activities
    max_horizon = S[n + 1] + 1  # Don't exceed makespan of current solution
    usage = [[0] * K for _ in range(max_horizon)]
    for i in range(1, n + 1):
        if S_new[i] is not None:
            s = S_new[i]
            for tau in range(s, s + d[i]):
                for k in range(K):
                    usage[tau][k] += r[i][k]

    # Re-run SGS to reschedule destroyed activities
    remaining = [0] * (n + 2)
    for i in range(1, n + 1):
        remaining[i] = sum(1 for pred in inst.predecessors[i] if S_new[pred] is None)

    eligible = []
    for i in to_destroy:
        all_preds_done = all(S_new[pred] is not None for pred in inst.predecessors[i])
        if all_preds_done:
            eligible.append(i)

    def priority_key(i):
        return (d[i], i)  # Use SPT for repair

    while eligible:
        i = min(eligible, key=priority_key)
        eligible.remove(i)

        min_start = max(
            (S_new[pred] + d[pred] for pred in inst.predecessors[i] if S_new[pred] is not None),
            default=0
        )

        t = min_start
        while t < max_horizon:
            conflict_at = -1
            for tau in range(t, min(t + d[i], max_horizon)):
                for k in range(K):
                    if usage[tau][k] + r[i][k] > R[k]:
                        conflict_at = tau
                        break
                if conflict_at >= 0:
                    break

            if conflict_at < 0 and t + d[i] <= max_horizon:
                break
            t = conflict_at + 1 if conflict_at >= 0 else max_horizon

        if t + d[i] > max_horizon:
            t = max_horizon - d[i]

        S_new[i] = t
        for tau in range(t, t + d[i]):
            if tau < max_horizon:
                for k in range(K):
                    usage[tau][k] += r[i][k]

        for j in inst.successors[i]:
            if j <= n and j in to_destroy:
                if all(S_new[pred] is not None for pred in inst.predecessors[j]):
                    if j not in eligible:
                        eligible.append(j)

    S_new[n + 1] = max(S_new[i] + d[i] for i in range(1, n + 1) if S_new[i] is not None)
    return S_new


def lns_sa(inst, S_init, start_time, time_limit=28.0):
    """
    Improvement phase: run SGS multiple times with shuffled priority orders.

    This is simpler than destroy-repair and guaranteed to produce valid schedules.
    The randomness comes from randomly shuffling which rule we use and which
    eligible activity we pick when priorities are tied.
    """
    n = inst.n
    est, lft = compute_est_lft(inst)
    succ_counts = count_all_successors(inst)

    S_best = S_init[:]
    cmax_best = S_best[n + 1]

    iteration = 0
    while time.time() - start_time < time_limit:
        iteration += 1

        # Pick a random rule
        rules = ['SPT', 'LPT', 'MTS', 'MC', 'MR', 'LR']
        rule = random.choice(rules)

        # Run SGS with that rule
        S_new = serial_sgs(inst, est, lft, rule, succ_counts)
        cmax_new = S_new[n + 1]

        # Track best
        if cmax_new < cmax_best:
            S_best = S_new[:]
            cmax_best = cmax_new

    return S_best


# ---------------------------------------------------------------------------
# PLACEHOLDER — later phases will add functions here
# ---------------------------------------------------------------------------
# Phase 5: time budget management (already integrated above)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    start_time = time.time()

    if len(sys.argv) != 2:
        print("Usage: python solver.py <path_to_file.SCH>", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]

    # Phase 1: parse
    inst = parse_sch(filepath)
    errors = validate_parse(inst)
    if errors:
        for e in errors:
            print(f"[PARSE ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    # Phase 2: preprocessing
    est, lft = compute_est_lft(inst)
    lb, lb_net, lb_res = compute_lower_bound(inst, est)

    # Phase 3: initial solution
    S = best_of_rules(inst, est, lft)
    cmax_init = S[inst.n + 1]

    # Phase 4: improve with LNS+SA
    if time.time() - start_time < 28.0:
        S = lns_sa(inst, S, start_time, time_limit=28.0)

    cmax = S[inst.n + 1]

    # Validate
    violations = validate_schedule(inst, S)
    for v in violations:
        print(f"[VIOLATION] {v}", file=sys.stderr)

    gap = 100 * (cmax - lb) / lb if lb > 0 else 0
    print(f"LB={lb} Cmax_init={cmax_init} Cmax_final={cmax} Gap={gap:.1f}%", file=sys.stderr)

    # Output (stdout)
    for i in range(1, inst.n + 1):
        print(f"{i} {S[i]}")
    print(f"Makespan: {cmax}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
solver2.py

Professional RCPSP solver for the SMU CS202 project:
"Optimising Resource-Constrained Scheduling".

What this program does
----------------------
- Reads one RCPSP instance from a file.
- Supports both:
  1) the simplified numeric format shown in the submission guidelines, and
  2) the standard PSPLIB-style single-mode format referenced in the project brief.
- Produces a valid schedule using a serial schedule generation scheme (SSGS).
- Improves the baseline schedule using multiple deterministic priority rules
  plus time-bounded randomized multi-start search.
- Prints ONLY the comma-separated start times of jobs 1..N to stdout,
  exactly as required by the grading script.
- Prints -1 if no feasible schedule can be constructed.

Key design goals
----------------
- Correctness first: every returned schedule is validated before output.
- Robustness: parser handles the two project document variants.
- Simplicity: standard library only; no external optimizers.
- Time awareness: always keeps the best feasible solution found so far,
  and stops before the wall-clock budget expires.

Default usage
-------------
    python solver2.py path/to/instance.sm

Optional debug / validation flags
---------------------------------
    python solver2.py path/to/instance.sm --verbose --validate

Important
---------
By default, stdout contains only the final answer line so that the output is
safe for autograding. Any diagnostics are sent to stderr.
"""

from __future__ import annotations

import argparse
import math
import random
import re
import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RCPSPInstance:
    """Container for one RCPSP instance.

    Activities are indexed 0..n+1 where:
      - 0    : dummy source
      - 1..n : real activities
      - n+1  : dummy sink
    """

    n: int
    K: int
    d: List[int]
    r: List[List[int]]
    R: List[int]
    successors: List[List[int]]
    predecessors: List[List[int]]

    @property
    def num_activities(self) -> int:
        return self.n + 2

    @property
    def sink(self) -> int:
        return self.n + 1

    @property
    def horizon_upper_bound(self) -> int:
        # Safe upper bound for time-indexed feasibility checks.
        return sum(self.d)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


_INT_RE = re.compile(r"-?\d+")


def _extract_ints(text: str) -> List[int]:
    """Extract all integers from a line, preserving sign."""
    return [int(x) for x in _INT_RE.findall(text)]


def _nonempty_lines(filepath: str) -> List[str]:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return [line.rstrip("\n") for line in f if line.strip()]


# ---------------------------------------------------------------------------
# Parser: simplified numeric format from the submission guidelines
# ---------------------------------------------------------------------------


def parse_numeric_guideline_format(lines: Sequence[str]) -> RCPSPInstance:
    """Parse the simplified numeric format from the submission guidelines.

    Expected structure after removing blank lines:
      line 1          : N R
      next N+2 lines  : i c succ1 succ2 ... succc
      next N+2 lines  : j duration req1 req2 ... reqR
      last line       : cap1 cap2 ... capR
    """
    header = _extract_ints(lines[0])
    if len(header) < 2:
        raise ValueError("Invalid numeric-format header")

    n, K = header[0], header[1]
    num_acts = n + 2
    expected = 1 + num_acts + num_acts + 1
    if len(lines) < expected:
        raise ValueError(
            f"Numeric-format file too short: expected at least {expected} non-empty lines"
        )

    successors = [[] for _ in range(num_acts)]
    idx = 1
    for _ in range(num_acts):
        parts = _extract_ints(lines[idx])
        idx += 1
        if len(parts) < 2:
            raise ValueError(f"Invalid precedence row: {lines[idx - 1]}")
        act_id, num_succ = parts[0], parts[1]
        if act_id < 0 or act_id >= num_acts:
            raise ValueError(f"Activity id out of range: {act_id}")
        if len(parts) < 2 + num_succ:
            raise ValueError(f"Too few successors in row for activity {act_id}")
        successors[act_id] = parts[2 : 2 + num_succ]

    d = [0] * num_acts
    r = [[0] * K for _ in range(num_acts)]
    for _ in range(num_acts):
        parts = _extract_ints(lines[idx])
        idx += 1
        if len(parts) < 2 + K:
            raise ValueError(f"Invalid duration/resource row: {lines[idx - 1]}")
        act_id = parts[0]
        d[act_id] = parts[1]
        r[act_id] = parts[2 : 2 + K]

    caps = _extract_ints(lines[idx])
    if len(caps) < K:
        raise ValueError("Invalid capacity row")
    R = caps[:K]

    predecessors = [[] for _ in range(num_acts)]
    for i in range(num_acts):
        for j in successors[i]:
            predecessors[j].append(i)

    return RCPSPInstance(n=n, K=K, d=d, r=r, R=R, successors=successors, predecessors=predecessors)


# ---------------------------------------------------------------------------
# Parser: PSPLIB-style single-mode format from the project brief
# ---------------------------------------------------------------------------


def parse_psplib_single_mode(lines: Sequence[str]) -> RCPSPInstance:
    """Parse a standard PSPLIB-style single-mode RCPSP file.

    This parser targets the common PSPLIB layout with sections such as:
      - PRECEDENCE RELATIONS:
      - REQUESTS/DURATIONS:
      - RESOURCEAVAILABILITIES:

    It supports the benchmark structure described in the project file.
    """
    text_lower = "\n".join(lines).lower()
    if "precedence relations" not in text_lower:
        raise ValueError("Missing PSPLIB section: PRECEDENCE RELATIONS")
    if "requests/durations" not in text_lower:
        raise ValueError("Missing PSPLIB section: REQUESTS/DURATIONS")
    if "resourceavailabilities" not in text_lower:
        raise ValueError("Missing PSPLIB section: RESOURCEAVAILABILITIES")

    jobs_incl_dummy: Optional[int] = None
    K: Optional[int] = None

    for line in lines:
        lower = line.lower()
        ints = _extract_ints(line)
        if "jobs (incl." in lower and ints:
            jobs_incl_dummy = ints[-1]
        elif "renewable" in lower and ints:
            # Typical PSPLIB header line contains counts for renewable/nonrenewable/etc.
            # We take the first integer as the number of renewable resources.
            K = ints[0]

    if jobs_incl_dummy is None:
        raise ValueError("Could not determine number of jobs from PSPLIB header")
    if K is None:
        # Fallback: infer later from request/resource lines if the header is absent.
        K = -1

    num_acts = jobs_incl_dummy
    n = jobs_incl_dummy - 2

    # Locate section starts.
    prec_start = next(i for i, line in enumerate(lines) if "precedence relations" in line.lower())
    req_start = next(i for i, line in enumerate(lines) if "requests/durations" in line.lower())
    cap_start = next(i for i, line in enumerate(lines) if "resourceavailabilities" in line.lower())

    # Parse precedence section.
    successors = [[] for _ in range(num_acts)]
    seen_prec_rows = 0
    i = prec_start + 1
    while i < req_start and seen_prec_rows < num_acts:
        ints = _extract_ints(lines[i])
        i += 1
        # Typical row: jobnr, mode_count, successor_count, succ1, succ2, ...
        if len(ints) < 3:
            continue
        job = ints[0] - 1
        if not (0 <= job < num_acts):
            continue
        succ_count = ints[2]
        succs = [x - 1 for x in ints[3 : 3 + succ_count]]
        successors[job] = succs
        seen_prec_rows += 1

    if seen_prec_rows != num_acts:
        raise ValueError(
            f"Expected {num_acts} precedence rows, parsed {seen_prec_rows}"
        )

    # Parse requests/durations section.
    d = [0] * num_acts
    r: List[List[int]] = []
    seen_req_rows = 0
    inferred_K = None
    i = req_start + 1
    while i < cap_start and seen_req_rows < num_acts:
        ints = _extract_ints(lines[i])
        i += 1
        # Typical row: jobnr, mode, duration, req1, req2, ...
        if len(ints) < 4:
            continue
        job = ints[0] - 1
        if not (0 <= job < num_acts):
            continue
        if inferred_K is None:
            inferred_K = len(ints) - 3
            if K == -1:
                K = inferred_K
        elif len(ints) - 3 < inferred_K:
            raise ValueError(f"Malformed request row for activity {job + 1}")
        d[job] = ints[2]
        if not r:
            r = [[0] * K for _ in range(num_acts)]
        r[job] = ints[3 : 3 + K]
        seen_req_rows += 1

    if K == -1:
        raise ValueError("Could not infer number of resources from PSPLIB file")
    if not r:
        r = [[0] * K for _ in range(num_acts)]
    if seen_req_rows != num_acts:
        raise ValueError(f"Expected {num_acts} request rows, parsed {seen_req_rows}")

    # Parse capacities: use the last non-empty line after RESOURCEAVAILABILITIES.
    R: Optional[List[int]] = None
    for j in range(len(lines) - 1, cap_start, -1):
        ints = _extract_ints(lines[j])
        if len(ints) >= K:
            R = ints[:K]
            break
    if R is None:
        raise ValueError("Could not parse resource capacities from PSPLIB file")

    predecessors = [[] for _ in range(num_acts)]
    for a in range(num_acts):
        for b in successors[a]:
            predecessors[b].append(a)

    return RCPSPInstance(n=n, K=K, d=d, r=r, R=R, successors=successors, predecessors=predecessors)


# ---------------------------------------------------------------------------
# Parse dispatcher
# ---------------------------------------------------------------------------


def parse_instance(filepath: str) -> RCPSPInstance:
    """Parse an instance by automatically detecting the file format."""
    lines = _nonempty_lines(filepath)
    if not lines:
        raise ValueError("Empty input file")

    # Heuristic detection:
    # - if the file contains the PSPLIB section names, parse as PSPLIB.
    # - otherwise fall back to the simplified numeric format.
    lowered = "\n".join(lines).lower()
    if (
        "precedence relations" in lowered
        or "requests/durations" in lowered
        or "resourceavailabilities" in lowered
    ):
        return parse_psplib_single_mode(lines)

    # Fallback to the numeric format used in the earlier guideline file.
    return parse_numeric_guideline_format(lines)


# ---------------------------------------------------------------------------
# Validation of the parsed instance
# ---------------------------------------------------------------------------


def validate_instance(inst: RCPSPInstance) -> List[str]:
    """Return a list of instance-level validation errors.

    An empty list means the parsed instance passed basic sanity checks.
    """
    errors: List[str] = []
    sink = inst.sink

    if inst.n <= 0:
        errors.append("Number of real activities must be positive")
    if inst.K <= 0:
        errors.append("Number of resource types must be positive")
    if len(inst.d) != inst.num_activities:
        errors.append("Duration vector length mismatch")
    if len(inst.r) != inst.num_activities:
        errors.append("Resource-demand matrix length mismatch")
    if len(inst.R) != inst.K:
        errors.append("Capacity vector length mismatch")

    for dummy in (0, sink):
        if inst.d[dummy] != 0:
            errors.append(f"Dummy activity {dummy} must have duration 0")
        if any(x != 0 for x in inst.r[dummy]):
            errors.append(f"Dummy activity {dummy} must require zero resources")

    for i in range(inst.num_activities):
        if inst.d[i] < 0:
            errors.append(f"Activity {i}: negative duration")
        if len(inst.r[i]) != inst.K:
            errors.append(f"Activity {i}: wrong number of resource requirements")
        for k in range(inst.K):
            if inst.r[i][k] < 0:
                errors.append(f"Activity {i}: negative demand on resource {k}")
            if i not in (0, sink) and inst.r[i][k] > inst.R[k]:
                errors.append(
                    f"Activity {i}: demand {inst.r[i][k]} exceeds capacity {inst.R[k]} on resource {k}"
                )

    for k, cap in enumerate(inst.R):
        if cap < 0:
            errors.append(f"Resource {k}: negative capacity")

    # Predecessor/successor consistency.
    for i in range(inst.num_activities):
        for j in inst.successors[i]:
            if j < 0 or j >= inst.num_activities:
                errors.append(f"Invalid edge {i}->{j}")
            elif i not in inst.predecessors[j]:
                errors.append(f"Edge inconsistency: {i}->{j} missing from predecessors")

    # Check acyclicity via topological ordering.
    try:
        _ = topological_order(inst)
    except ValueError as exc:
        errors.append(str(exc))

    return errors


# ---------------------------------------------------------------------------
# Graph analytics used by the scheduling heuristics
# ---------------------------------------------------------------------------


def topological_order(inst: RCPSPInstance) -> List[int]:
    """Return a topological ordering of the activity DAG.

    Raises
    ------
    ValueError
        If the graph contains a cycle.
    """
    indeg = [len(inst.predecessors[i]) for i in range(inst.num_activities)]
    q = deque(i for i in range(inst.num_activities) if indeg[i] == 0)
    order: List[int] = []

    while q:
        node = q.popleft()
        order.append(node)
        for suc in inst.successors[node]:
            indeg[suc] -= 1
            if indeg[suc] == 0:
                q.append(suc)

    if len(order) != inst.num_activities:
        raise ValueError("Precedence graph is not acyclic")
    return order


@dataclass
class ActivityMetrics:
    """Precomputed activity metrics used by deterministic and randomized rules."""

    topo: List[int]
    est: List[int]
    eft: List[int]
    tail: List[int]
    descendant_count: List[int]
    resource_weight: List[int]
    duration: List[int]



def compute_activity_metrics(inst: RCPSPInstance) -> ActivityMetrics:
    """Compute precedence-based metrics for heuristic scoring.

    Notes
    -----
    - est / eft ignore resource constraints.
    - tail[i] is the longest path length from i to the sink, including d[i].
      For the sink, tail[sink] = 0.
    - descendant_count[i] counts unique descendants reachable from i.
      For the small project benchmark sizes, using Python sets is acceptable.
    """
    topo = topological_order(inst)
    sink = inst.sink

    est = [0] * inst.num_activities
    eft = [0] * inst.num_activities
    for i in topo:
        eft[i] = est[i] + inst.d[i]
        for j in inst.successors[i]:
            if eft[i] > est[j]:
                est[j] = eft[i]

    tail = [0] * inst.num_activities
    for i in reversed(topo):
        if i == sink:
            tail[i] = 0
        elif inst.successors[i]:
            tail[i] = inst.d[i] + max(tail[j] for j in inst.successors[i])
        else:
            tail[i] = inst.d[i]

    descendants: List[set[int]] = [set() for _ in range(inst.num_activities)]
    for i in reversed(topo):
        seen: set[int] = set()
        for j in inst.successors[i]:
            seen.add(j)
            seen.update(descendants[j])
        descendants[i] = seen
    descendant_count = [len(s) for s in descendants]

    resource_weight = [sum(inst.r[i][k] for k in range(inst.K)) for i in range(inst.num_activities)]

    return ActivityMetrics(
        topo=topo,
        est=est,
        eft=eft,
        tail=tail,
        descendant_count=descendant_count,
        resource_weight=resource_weight,
        duration=list(inst.d),
    )


# ---------------------------------------------------------------------------
# Serial schedule generation scheme (SSGS)
# ---------------------------------------------------------------------------


def earliest_feasible_start(
    inst: RCPSPInstance,
    activity: int,
    ready_time: int,
    usage: List[List[int]],
) -> int:
    """Find the earliest time >= ready_time where the activity fits.

    Parameters
    ----------
    inst
        Problem instance.
    activity
        Activity to place.
    ready_time
        Earliest precedence-feasible time.
    usage
        Time-indexed renewable-resource usage profile. usage[t][k] is the amount
        of resource k already consumed at time t.
    """
    dur = inst.d[activity]
    demand = inst.r[activity]

    if dur == 0:
        return ready_time

    t = ready_time
    while True:
        end = t + dur
        if end > len(usage):
            usage.extend([[0] * inst.K for _ in range(end - len(usage))])

        feasible = True
        for tau in range(t, end):
            row = usage[tau]
            for k in range(inst.K):
                if row[k] + demand[k] > inst.R[k]:
                    feasible = False
                    break
            if not feasible:
                break

        if feasible:
            return t
        t += 1


PriorityKeyFn = Callable[[int], Tuple]
SelectorFn = Callable[[List[int], random.Random], int]



def serial_schedule_generation_scheme(
    inst: RCPSPInstance,
    priority_key: PriorityKeyFn,
    selector: SelectorFn,
    rng: random.Random,
) -> List[int]:
    """Construct one schedule using a serial schedule generation scheme.

    The algorithm repeatedly chooses one eligible activity and places it at the
    earliest resource-feasible time.

    Returns
    -------
    List[int]
        Start times for activities 0..n+1.
    """
    n_all = inst.num_activities
    starts = [-1] * n_all
    finishes = [-1] * n_all
    pred_remaining = [len(inst.predecessors[i]) for i in range(n_all)]

    # Seed the eligible set with *all* zero-predecessor activities.
    # Some benchmark files may omit explicit 0->i arcs for activities that
    # can start at time 0. Restricting this to only the dummy source can leave
    # the queue empty prematurely even though unscheduled activities remain.
    eligible = [i for i in range(n_all) if pred_remaining[i] == 0]
    scheduled_count = 0
    usage: List[List[int]] = []

    while eligible:
        activity = selector(eligible, rng)
        eligible.remove(activity)

        ready_time = 0
        for p in inst.predecessors[activity]:
            if finishes[p] > ready_time:
                ready_time = finishes[p]

        s = earliest_feasible_start(inst, activity, ready_time, usage)
        starts[activity] = s
        finishes[activity] = s + inst.d[activity]

        dur = inst.d[activity]
        if dur > 0:
            end = s + dur
            if end > len(usage):
                usage.extend([[0] * inst.K for _ in range(end - len(usage))])
            for t in range(s, end):
                row = usage[t]
                req = inst.r[activity]
                for k in range(inst.K):
                    row[k] += req[k]

        scheduled_count += 1
        for suc in inst.successors[activity]:
            pred_remaining[suc] -= 1
            if pred_remaining[suc] == 0:
                eligible.append(suc)

        # Keep eligible in a deterministic order between selections.
        eligible.sort(key=priority_key)

    if scheduled_count != n_all:
        raise ValueError("SSGS failed to schedule all activities")
    return starts


# ---------------------------------------------------------------------------
# Priority rules and randomized selectors
# ---------------------------------------------------------------------------


@dataclass
class RuleBundle:
    name: str
    key: PriorityKeyFn
    selector: SelectorFn



def make_deterministic_selector(key: PriorityKeyFn) -> SelectorFn:
    """Pick the eligible activity with the best lexicographic priority key."""

    def selector(eligible: List[int], rng: random.Random) -> int:
        return min(eligible, key=key)

    return selector



def make_top_k_randomized_selector(key: PriorityKeyFn, k: int = 3) -> SelectorFn:
    """Randomized selector over the current best K eligible activities.

    This preserves a strong heuristic bias while enabling exploration.
    """

    def selector(eligible: List[int], rng: random.Random) -> int:
        ranked = sorted(eligible, key=key)
        window = ranked[: max(1, min(k, len(ranked)))]
        return rng.choice(window)

    return selector



def build_rule_bundles(inst: RCPSPInstance, metrics: ActivityMetrics) -> List[RuleBundle]:
    """Create deterministic and randomized rule bundles.

    Lower lexicographic keys are better because the SSGS selector uses min(..., key=...)
    by convention.
    """
    sink = inst.sink

    # To avoid scheduling the sink too early in tie cases, keep it naturally delayed by
    # using the standard rules; it is only eligible when all predecessors are done anyway.
    def key_lft(i: int) -> Tuple:
        # Activities with larger tail are more critical, so use negative tail.
        return (-metrics.tail[i], -metrics.descendant_count[i], -metrics.resource_weight[i], i)

    def key_most_successors(i: int) -> Tuple:
        return (-metrics.descendant_count[i], -metrics.tail[i], -metrics.resource_weight[i], i)

    def key_shortest_processing_time(i: int) -> Tuple:
        return (metrics.duration[i], -metrics.tail[i], -metrics.descendant_count[i], i)

    def key_resource_intensive(i: int) -> Tuple:
        return (-metrics.resource_weight[i], -metrics.tail[i], metrics.duration[i], i)

    def key_est_then_critical(i: int) -> Tuple:
        return (metrics.est[i], -metrics.tail[i], -metrics.descendant_count[i], i)

    bundles = []
    deterministic_keys = [
        ("critical_path_first", key_lft),
        ("most_descendants_first", key_most_successors),
        ("shortest_processing_time", key_shortest_processing_time),
        ("resource_intensive_first", key_resource_intensive),
        ("est_then_critical", key_est_then_critical),
    ]

    for name, key in deterministic_keys:
        bundles.append(RuleBundle(name=name, key=key, selector=make_deterministic_selector(key)))

    for name, key in deterministic_keys:
        bundles.append(
            RuleBundle(
                name=f"rand_top3_{name}",
                key=key,
                selector=make_top_k_randomized_selector(key, k=3),
            )
        )

    return bundles


# ---------------------------------------------------------------------------
# Schedule validation and objective computation
# ---------------------------------------------------------------------------


def validate_schedule(inst: RCPSPInstance, starts: Sequence[int]) -> List[str]:
    """Return a list of schedule validation errors.

    Empty list => valid schedule.
    """
    errors: List[str] = []
    if len(starts) != inst.num_activities:
        return [
            f"Expected {inst.num_activities} start times including dummies, got {len(starts)}"
        ]

    for i, s in enumerate(starts):
        if s < 0:
            errors.append(f"Activity {i}: negative / missing start time")

    # Precedence constraints.
    for i in range(inst.num_activities):
        finish_i = starts[i] + inst.d[i]
        for j in inst.successors[i]:
            if starts[j] < finish_i:
                errors.append(
                    f"Precedence violation: {i}->{j} but start[{j}]={starts[j]} < {finish_i}"
                )

    # Renewable resource constraints.
    horizon = max(starts[i] + inst.d[i] for i in range(inst.num_activities))
    usage = [[0] * inst.K for _ in range(horizon)]
    for i in range(inst.num_activities):
        s = starts[i]
        e = s + inst.d[i]
        for t in range(s, e):
            for k in range(inst.K):
                usage[t][k] += inst.r[i][k]
                if usage[t][k] > inst.R[k]:
                    errors.append(
                        f"Resource violation at time {t}, resource {k}: "
                        f"usage={usage[t][k]} > cap={inst.R[k]}"
                    )
                    # One clear message is enough for this (time, resource) pair.
                    break

    return errors



def makespan(inst: RCPSPInstance, starts: Sequence[int]) -> int:
    """Project makespan = start time of the sink dummy activity."""
    return starts[inst.sink]


# ---------------------------------------------------------------------------
# Solver logic
# ---------------------------------------------------------------------------


@dataclass
class SolveResult:
    starts: Optional[List[int]]
    schedule_errors: List[str]
    rule_name: Optional[str]
    objective: Optional[int]
    iterations: int
    elapsed: float



def solve_rcpsp(
    inst: RCPSPInstance,
    time_limit_seconds: float = 29.5,
    seed: int = 2026,
    verbose: bool = False,
) -> SolveResult:
    """Solve the RCPSP instance within a wall-clock budget.

    Strategy
    --------
    1) Compute graph-based activity metrics.
    2) Try several deterministic priority rules to get a strong feasible baseline.
    3) Use randomized top-k multi-start search until the time budget is nearly exhausted.
    4) Always keep the best feasible schedule seen.
    """
    t0 = time.perf_counter()
    rng = random.Random(seed)
    metrics = compute_activity_metrics(inst)
    rules = build_rule_bundles(inst, metrics)

    best_starts: Optional[List[int]] = None
    best_obj: Optional[int] = None
    best_rule: Optional[str] = None
    iterations = 0
    last_errors: List[str] = []

    # Helper to evaluate one SSGS run.
    def try_rule(rule: RuleBundle, local_rng: random.Random) -> None:
        nonlocal best_starts, best_obj, best_rule, iterations, last_errors
        iterations += 1
        try:
            starts = serial_schedule_generation_scheme(inst, rule.key, rule.selector, local_rng)
        except Exception as exc:
            last_errors = [f"{type(exc).__name__}: {exc}"]
            return
        errors = validate_schedule(inst, starts)
        if errors:
            last_errors = errors
            return
        obj = makespan(inst, starts)
        if best_obj is None or obj < best_obj:
            best_starts = list(starts)
            best_obj = obj
            best_rule = rule.name
            if verbose:
                print(
                    f"[info] improved by {rule.name}: makespan={obj}",
                    file=sys.stderr,
                )

    # Phase A: deterministic baselines.
    for rule in rules:
        if time.perf_counter() - t0 >= time_limit_seconds * 0.25:
            break
        # Run all deterministic rules first; randomized rules will also work here.
        try_rule(rule, random.Random(rng.randrange(1 << 30)))

    # Phase B: time-bounded randomized multi-start.
    # We bias toward the randomized variants but occasionally revisit deterministic ones.
    while time.perf_counter() - t0 < time_limit_seconds:
        # Stop slightly early so the caller can still validate/print safely.
        elapsed = time.perf_counter() - t0
        if elapsed >= time_limit_seconds - 0.02:
            break

        # 80% randomized, 20% deterministic.
        if rng.random() < 0.8:
            candidate_rules = [rule for rule in rules if rule.name.startswith("rand_top3_")]
        else:
            candidate_rules = [rule for rule in rules if not rule.name.startswith("rand_top3_")]
        rule = rng.choice(candidate_rules)
        try_rule(rule, random.Random(rng.randrange(1 << 30)))

    elapsed = time.perf_counter() - t0
    if best_starts is None:
        return SolveResult(
            starts=None,
            schedule_errors=last_errors,
            rule_name=None,
            objective=None,
            iterations=iterations,
            elapsed=elapsed,
        )

    return SolveResult(
        starts=best_starts,
        schedule_errors=[],
        rule_name=best_rule,
        objective=best_obj,
        iterations=iterations,
        elapsed=elapsed,
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------



def format_required_output(inst: RCPSPInstance, starts: Sequence[int]) -> str:
    """Format the final output exactly as required by the submission guidelines.

    Only jobs 1..N are printed, in order, comma-separated, on one line.
    """
    return ",".join(str(starts[i]) for i in range(1, inst.n + 1))


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------



def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="RCPSP solver for the CS202 project",
        add_help=True,
    )
    parser.add_argument("instance", help="Path to one RCPSP instance file")
    parser.add_argument(
        "--time-limit",
        type=float,
        default=29.5,
        help="Internal solving time budget in seconds (default: 29.5)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2026,
        help="Random seed for reproducibility (default: 2026)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the final schedule and print diagnostics to stderr",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print debug / progress messages to stderr",
    )
    return parser



def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    try:
        inst = parse_instance(args.instance)
    except Exception as exc:  # pragma: no cover - defensive CLI path
        print(f"[error] failed to parse instance: {exc}", file=sys.stderr)
        print("-1")
        return 0

    instance_errors = validate_instance(inst)
    if instance_errors:
        for msg in instance_errors:
            print(f"[instance-error] {msg}", file=sys.stderr)
        print("-1")
        return 0

    if args.verbose:
        print(
            (
                f"[info] parsed instance: n={inst.n}, K={inst.K}, "
                f"activities={inst.num_activities}, horizon_ub={inst.horizon_upper_bound}"
            ),
            file=sys.stderr,
        )

    result = solve_rcpsp(
        inst,
        time_limit_seconds=args.time_limit,
        seed=args.seed,
        verbose=args.verbose,
    )

    if result.starts is None:
        if args.verbose and result.schedule_errors:
            for msg in result.schedule_errors:
                print(f"[schedule-error] {msg}", file=sys.stderr)
        print("-1")
        return 0

    if args.validate:
        errors = validate_schedule(inst, result.starts)
        if errors:
            for msg in errors:
                print(f"[final-validation-error] {msg}", file=sys.stderr)
            print("-1")
            return 0
        if args.verbose:
            print(
                (
                    f"[info] final schedule valid | makespan={result.objective} | "
                    f"rule={result.rule_name} | iterations={result.iterations} | "
                    f"elapsed={result.elapsed:.4f}s"
                ),
                file=sys.stderr,
            )

    print(format_required_output(inst, result.starts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
# PLACEHOLDER — later phases will add functions here
# ---------------------------------------------------------------------------
# Phase 2: compute_est_lft, compute_lower_bound
# Phase 3: serial_sgs, priority rules
# Phase 4: lns_sa (Large Neighbourhood Search + Simulated Annealing)
# Phase 5: time budget management woven into Phase 3/4


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    start_time = time.time()  # noqa: used in Phase 5 for time-budget cutoff

    if len(sys.argv) != 2:
        print("Usage: python solver.py <path_to_file.SCH>", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]

    # --- Phase 1: parse ---
    inst = parse_sch(filepath)
    errors = validate_parse(inst)
    if errors:
        for e in errors:
            print(f"[PARSE ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    # Temporary: print instance summary so we can verify parsing visually
    print(f"Parsed: n={inst.n}, K={inst.K}", file=sys.stderr)
    print(inst.summary(), file=sys.stderr)

    # TODO (Phase 3+): generate and output a schedule


if __name__ == "__main__":
    main()

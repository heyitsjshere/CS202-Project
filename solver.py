#!/usr/bin/env python3
"""
RCPSP/max solver — CS202 Group Project, SMU.

Reads a single .SCH file (PSPLIB/ProGenMax format) and outputs a schedule
that minimises project makespan (Cmax = S[n+1]) subject to precedence,
max-lag, and resource constraints.

Usage:
    python solver.py <path_to_file.SCH>

Output (to stdout):
    <actId> <startTime>     (one line per real activity 1..n)
    Makespan: <value>
"""

import sys
import time
import math

# ---------------------------------------------------------------------------
# PHASE 1 — Data model and parser
# ---------------------------------------------------------------------------

class RCPSPInstance:
    """
    All data for one RCPSP/max instance.

    Activities are indexed 0..n+1 where:
      - 0     : dummy start (d=0, no resources)
      - 1..n  : real activities
      - n+1   : dummy end   (d=0, no resources)

    Temporal constraints on the constraint graph are expressed as signed lags
    on directed arcs i → j:
      - lag > 0 : S[j] >= S[i] + lag   (minimum time lag, "forward" arc)
      - lag = 0 : S[j] >= S[i]         (start-to-start with no gap)
      - lag < 0 : S[j] <= S[i] + |lag| (maximum time lag, "backward" arc)

    Attributes
    ----------
    n           : int          — number of real activities
    K           : int          — number of renewable resource types
    d           : list[int]    — d[i] = duration of activity i
    r           : list[list]   — r[i][k] = resource demand of activity i for k
    R           : list[int]    — R[k] = capacity of resource type k
    successors  : list[list]   — successors[i]  = [(j, lag), ...]
    predecessors: list[list]   — predecessors[j] = [(i, lag), ...]
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
            for j, lag in successors[i]:
                self.predecessors[j].append((i, lag))

    def summary(self):
        """Return a human-readable description of the instance (for debugging)."""
        lines = [
            f"  Activities : {self.n} real + 2 dummy = {self.n + 2} total",
            f"  Resources  : {self.K} types, capacities {self.R}",
            f"  Durations  : {self.d[1:self.n+1]}",
        ]
        arcs_fwd = sum(
            1 for i in range(self.n + 2)
            for _, lag in self.successors[i] if lag >= 0
        )
        arcs_bwd = sum(
            1 for i in range(self.n + 2)
            for _, lag in self.successors[i] if lag < 0
        )
        lines.append(f"  Arcs       : {arcs_fwd} forward (lag>=0), {arcs_bwd} backward (lag<0)")
        return "\n".join(lines)


def parse_sch(filepath):
    """
    Parse a PSPLIB/ProGenMax .SCH file and return an RCPSPInstance.

    File structure (blank lines ignored):
      1. Header line          : n  K  0  0
      2. Activity block       : n+2 rows, one per activity 0..n+1
           actId  modes  numSucc  succ1 succ2 ...  [lag1] [lag2] ...
      3. Resource block       : n+2 rows, one per activity 0..n+1
           actId  modes  duration  res1 res2 res3 res4 res5
      4. Capacity line        : R1  R2  R3  R4  R5

    Lag values are signed integers wrapped in brackets, e.g. [9] or [-22].
    A positive lag encodes a minimum time lag (forward constraint).
    A negative lag encodes a maximum time lag (backward constraint).
    """
    with open(filepath) as f:
        # Drop blank/whitespace-only lines; keep non-empty stripped lines
        lines = [line.strip() for line in f if line.strip()]

    idx = 0  # current line pointer

    # ------------------------------------------------------------------
    # 1. Header
    # ------------------------------------------------------------------
    header = lines[idx].split()
    idx += 1
    n = int(header[0])   # number of real activities
    K = int(header[1])   # number of resource types
    num_acts = n + 2     # total activities including dummies 0 and n+1

    # ------------------------------------------------------------------
    # 2. Activity block  — parse graph structure (successors + lags)
    # ------------------------------------------------------------------
    successors = [[] for _ in range(num_acts)]

    for _ in range(num_acts):
        parts = lines[idx].split()
        idx += 1

        act_id   = int(parts[0])
        # parts[1] is always "1" (single-mode), ignored
        num_succ = int(parts[2])

        if num_succ == 0:
            # Dummy end node: line is just "actId  1  0"
            continue

        # Successor activity IDs come right after numSucc
        succ_ids = [int(parts[3 + s]) for s in range(num_succ)]

        # Lag values follow the successor IDs, in [x] bracket notation
        # Each token looks like "[9]" or "[-22]" — strip brackets, parse int
        for s in range(num_succ):
            lag_token = parts[3 + num_succ + s]
            lag = int(lag_token.strip('[]'))
            successors[act_id].append((succ_ids[s], lag))

    # ------------------------------------------------------------------
    # 3. Resource block  — parse durations and resource demands
    # ------------------------------------------------------------------
    d = [0] * num_acts              # durations (int)
    r = [[0] * K for _ in range(num_acts)]  # resource demands

    for _ in range(num_acts):
        parts = lines[idx].split()
        idx += 1

        act_id      = int(parts[0])
        # parts[1] is always "1" (single-mode), ignored
        d[act_id]   = int(parts[2])      # duration is the 3rd field
        for k in range(K):
            r[act_id][k] = int(parts[3 + k])

    # ------------------------------------------------------------------
    # 4. Resource capacities
    # ------------------------------------------------------------------
    R = list(map(int, lines[idx].split()))

    return RCPSPInstance(n, K, d, r, R, successors)


# ---------------------------------------------------------------------------
# PHASE 1 — Validation helper
# ---------------------------------------------------------------------------

def validate_parse(inst):
    """
    Run basic sanity checks on a freshly parsed RCPSPInstance.

    Returns a (possibly empty) list of error strings.
    An empty list means all checks passed.
    """
    n, K = inst.n, inst.K
    errors = []

    # Dummy activities must have zero duration and zero resource demand
    for dummy in (0, n + 1):
        if inst.d[dummy] != 0:
            errors.append(
                f"Dummy {dummy}: expected duration 0, got {inst.d[dummy]}"
            )
        for k in range(K):
            if inst.r[dummy][k] != 0:
                errors.append(
                    f"Dummy {dummy}: expected r[{k}]=0, got {inst.r[dummy][k]}"
                )

    # All durations must be non-negative
    for i in range(1, n + 1):
        if inst.d[i] < 0:
            errors.append(f"Activity {i}: negative duration {inst.d[i]}")

    # Resource demands must be non-negative and at most capacity
    for i in range(1, n + 1):
        for k in range(K):
            if inst.r[i][k] < 0:
                errors.append(
                    f"Activity {i}: negative demand r[{k}]={inst.r[i][k]}"
                )
            if inst.r[i][k] > inst.R[k]:
                errors.append(
                    f"Activity {i}: r[{k}]={inst.r[i][k]} exceeds capacity {inst.R[k]}"
                )

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

    # Every real activity must be reachable from 0 (has at least one predecessor)
    # and must eventually reach n+1 (has at least one successor)
    for i in range(1, n + 1):
        if not inst.predecessors[i]:
            errors.append(f"Activity {i}: no predecessors (unreachable from start)")
        if not inst.successors[i]:
            errors.append(f"Activity {i}: no successors (never reaches end)")

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
    start_time = time.time()   # Phase 5: record wall-clock start immediately

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
    # (This block will be replaced once scheduling is implemented)
    print(f"Parsed: n={inst.n}, K={inst.K}", file=sys.stderr)
    print(inst.summary(), file=sys.stderr)

    # TODO (Phase 3+): generate and output a schedule
    # For now, print a placeholder to confirm the output format
    # print("<actId> <startTime>")
    # print("Makespan: <value>")


if __name__ == "__main__":
    main()

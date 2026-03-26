# CS202 Group Project — RCPSP/max Solver Roadmap

**Course:** CS202, Singapore Management University
**Problem:** Resource-Constrained Project Scheduling Problem with max-lag constraints (RCPSP/max)
**Goal:** Minimise project makespan (Cmax) within a 30-second wall-clock time limit per instance
**Language:** Python (standard library only — no OR-Tools, PuLP, Gurobi, CPLEX)

---

## Quick Reference

| Dataset | Real Activities | Instances | Gap Target |
|---------|----------------|-----------|------------|
| J10     | 10             | 270       | < 5% vs LB |
| J20     | 20             | 270       | < 10% vs LB |

**Gap(%) = 100 × (Cmax_found − LB) / LB**

**Invocation:** `python solver.py <path_to_file.SCH>`
**Output:** One `actId startTime` line per real activity, then `Makespan: <value>`

---

## Constraint Cheat Sheet

| Constraint | Formula |
|---|---|
| Positive lag (forward) | S[j] >= S[i] + lag |
| Zero lag | S[j] >= S[i] |
| Negative lag (backward/max-lag) | S[j] <= S[i] + \|lag\| |
| Resource at time t | Σ r[i][k] for all active i ≤ R[k] |
| Active interval | S[i] ≤ t < S[i] + d[i] &nbsp;&nbsp;(**exclusive** upper bound) |
| Non-negativity | S[i] >= 0 |

---

## Phase 1 — Parse and Model ✅

**Status:** Complete

- [x] Read `.SCH` file line by line; strip blank lines
- [x] Parse header: extract `n` (real activities) and `K` (resource types)
- [x] Parse **activity block** (`n+2` rows): for each activity store list of `(successor, lag)` pairs
      Format: `actId  modes  numSucc  succ1 succ2 ...  [lag1] [lag2] ...`
- [x] Parse **resource block** (`n+2` rows): extract duration `d[i]` (3rd field) and `r[i][k]`
      Format: `actId  modes  duration  res1 res2 res3 res4 res5`
- [x] Parse last line: store `R[k]` for `k in 0..K-1`
- [x] Build `successors[i]` and `predecessors[j]` adjacency lists
- [x] `validate_parse` sanity checker: dummy durations=0, all-zero resources, no orphan activities
- [x] Tested on J10/PSP1.SCH and J20/PSP1.SCH — all checks pass

**Key insight:** Negative lags (e.g. `[-22]`) create backward arcs that form cycles in the
constraint graph. Topological sort breaks here — Bellman-Ford is required (Phase 2).

---

## Phase 2 — Preprocessing and Lower Bounds

**Status:** Not started

- [ ] Run **Bellman-Ford** from node 0 to compute `EST[i]` (Earliest Start Time)
  - Forward arc `(i, j, L≥0)`: `EST[j] = max(EST[j], EST[i] + L)`
  - Backward arc `(i, j, L<0)`: treat as forward arc `(j, i, -L)`, i.e. `EST[i] = max(EST[i], EST[j] - L)`
  - Run `n+1` relaxation rounds (standard Bellman-Ford on `n+2` nodes)
- [ ] Run backwards Bellman-Ford from node `n+1` to compute `LFT[i]` (Latest Finish Time)
- [ ] Compute **network lower bound**: `LB_net` = longest path from 0 to `n+1`
- [ ] Compute **resource lower bound** for each resource type k:
      `LB_res[k] = ceil( Σ d[i] * r[i][k] for i in 1..n ) / R[k]`
- [ ] `LB = max(LB_net, max over k of LB_res[k])`
- [ ] Assert `EST[i] + d[i] <= LFT[i]` for all real activities

**Pitfall:** Bellman-Ford must handle negative-lag arcs carefully. Do NOT just flip sign — convert
`(i→j, lag<0)` to a reverse arc `(j→i, -lag)` for EST propagation.

---

## Phase 3 — Baseline Greedy Scheduler (Serial SGS)

**Status:** Not started

- [ ] Implement **Serial Schedule Generation Scheme (SGS)**:
  1. Maintain a set of *eligible* activities (all predecessors already scheduled)
  2. Pick one eligible activity using a priority rule
  3. Compute its earliest feasible start time:
     - **(a) Precedence:** `start >= max(S[pred] + lag)` over all predecessors with `lag > 0`
     - **(b) Max-lag:** `start <= min upper bound` from all backward arcs
     - **(c) Resources:** shift `start` forward until `[start, start+d[i])` fits within capacity
  4. Schedule it, update eligible set
  5. Repeat until all `n` real activities are scheduled
- [ ] Implement **6 priority rules** (pick the eligible activity with the best score):
  - **SPT** — Shortest Processing Time: smallest `d[i]`
  - **LPT** — Longest Processing Time: largest `d[i]`
  - **MTS** — Most Total Successors: most downstream activities (transitive)
  - **MC**  — Most Critical: smallest slack `LFT[i] - EST[i] - d[i]` (ascending)
  - **MR**  — Most Resources: highest total resource demand `Σ r[i][k]`
  - **LR**  — Least Resources: lowest total resource demand
- [ ] Run all 6 rules; keep the best (lowest Cmax) as the initial solution
- [ ] Run full **validation checklist** on the output before printing
- [ ] Test on J10 first — compute `Gap(%)` vs `LB`

**Pitfall:** Resource interval upper bound is **exclusive**: active during `[S[i], S[i]+d[i])`.
Check `S[i] <= t < S[i]+d[i]`, not `S[i] <= t <= S[i]+d[i]`.

---

## Phase 4 — Improve Solution Quality (LNS + Simulated Annealing)

**Status:** Not started

- [ ] **Destroy operator:** randomly unschedule 20–40% of activities
  - For J10: destroy 3–4 activities; for J20: destroy 5–8
  - If removing activity `i` violates a max-lag upper bound on another activity `j`, unschedule `j` too (cascade)
- [ ] **Repair operator:** re-run SGS on the partial schedule to reschedule destroyed activities
- [ ] **Acceptance criterion (Simulated Annealing):**
  - Accept if `new_Cmax < best_Cmax`
  - Accept worse solution with probability `exp(-delta / T)` where `delta = new_Cmax - current_Cmax`
  - Cool temperature: `T *= 0.995` to `0.9999` each iteration
- [ ] Track **best solution** seen across all iterations
- [ ] Stop when `time.time() - start >= 28.0`; return best immediately

**Why LNS over Genetic Algorithm:** LNS+SA converges faster per iteration and handles
max-lag cascade constraints more cleanly than permutation-based crossover in a GA.

---

## Phase 5 — Time Budget Management

**Status:** Not started (woven into Phases 3 and 4)

- [ ] `start_time = time.time()` at the very top of `main()`
- [ ] Before every SGS run and every LNS iteration: `if time.time() - start_time >= 28.0: break`
- [ ] Reserve ≥ 2 seconds buffer before the 30s hard deadline
- [ ] Measure empirically: how many LNS iterations fit in 25 seconds for J10 vs J20?
- [ ] Tune destroy fraction and temperature schedule based on measurements

---

## Phase 6 — Testing and Validation

**Status:** Not started

- [ ] Run on all 270 J10 instances; record `Cmax` and `Gap(%)` for each
- [ ] Run on all 270 J20 instances
- [ ] Compute: average Gap(%), worst-case Gap(%), count of instances below target threshold
- [ ] Confirm **zero invalid schedules** across all instances (run validator on all)
- [ ] Do not over-fit to J10/J20 — grading uses harder unseen instances

**Validation checklist (run before every output):**
- [ ] Precedence: `S[j] >= S[i] + lag` for all arcs with `lag > 0`
- [ ] Max-lag: `S[j] <= S[i] + |lag|` for all arcs with `lag < 0`
- [ ] Resource: at every time `t`, `Σ r[i][k]` for active `i` ≤ `R[k]`
- [ ] Non-negativity: `S[i] >= 0` for all `i`
- [ ] All `n` real activities have an assigned start time

---

## Phase 7 — Write-up

**Status:** Not started

- [ ] Describe algorithm design and rationale for choices (why Serial SGS + LNS+SA)
- [ ] Report Gap(%) statistics on J10 and J20 (average, worst, % within target)
- [ ] Analyse time budget usage (how many LNS iterations per instance on average)
- [ ] Discuss tradeoffs (e.g. why LNS over B&B for J20, why SA acceptance over greedy)
- [ ] Prepare slides if required

---

## Known Pitfalls (Keep This Handy)

| # | Pitfall | Where It Bites |
|---|---------|----------------|
| 1 | Negative lags create **cycles** — use Bellman-Ford, not topological sort | Phase 2, 3 |
| 2 | Resource interval is `[S[i], S[i]+d[i])` — **exclusive** upper bound | Phase 3, 6 |
| 3 | Always propagate **max-lag upper bounds** after scheduling each activity | Phase 3, 4 |
| 4 | Check wall-clock time **before** every iteration, not after | Phase 5 |
| 5 | Lag values can be **large and negative** — use signed integers everywhere | Phase 1, 2 |
| 6 | Do not assume a fixed Cmax upper bound — **allocate resource tracking dynamically** | Phase 3 |
| 7 | LNS destroy must **cascade**: removing `i` may force removal of activities with tight max-lag to `i` | Phase 4 |

---

## Current Status

| Phase | Status | Owner |
|-------|--------|-------|
| 1 — Parse and model | ✅ Complete | |
| 2 — Lower bounds | ⬜ Not started | |
| 3 — Serial SGS | ⬜ Not started | |
| 4 — LNS + SA | ⬜ Not started | |
| 5 — Time budget | ⬜ Not started | |
| 6 — Testing | ⬜ Not started | |
| 7 — Write-up | ⬜ Not started | |

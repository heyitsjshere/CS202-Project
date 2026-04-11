# CS202 Group Project — RCPSP Solver Roadmap

**Course:** CS202, Singapore Management University
**Problem:** Resource-Constrained Project Scheduling Problem (RCPSP)
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
| Precedence (finish-to-start) | S[j] >= S[i] + d[i] for every arc i → j |
| Resource at time t | Σ r[i][k] for all active i ≤ R[k] |
| Active interval | S[i] ≤ t < S[i] + d[i] &nbsp;&nbsp;(**exclusive** upper bound) |
| Non-negativity | S[i] >= 0 |

---

## File Format (Updated PSPLIB)

```
n  K                                    ← header: 2 fields
actId  numSucc  succ1  succ2  ...       ← activity block (n+2 rows, no lags)
actId  duration  res1  res2  ...  res5  ← resource block (n+2 rows)
R1  R2  R3  R4  R5                      ← resource capacities
```

---

## Phase 1 — Parse and Model ✅

**Status:** Complete

- [x] Read `.SCH` file line by line; strip blank lines
- [x] Parse header: extract `n` (real activities) and `K` (resource types)
- [x] Parse **activity block** (`n+2` rows): for each activity store list of successor IDs
      Format: `actId  numSucc  succ1  succ2  ...`
- [x] Parse **resource block** (`n+2` rows): extract duration `d[i]` (2nd field) and `r[i][k]`
      Format: `actId  duration  res1  res2  res3  res4  res5`
- [x] Parse last line: store `R[k]` for `k in 0..K-1`
- [x] Build `successors[i]` and `predecessors[j]` adjacency lists
- [x] `validate_parse` sanity checker: dummy durations=0, all-zero resources, no orphan activities
- [x] Tested on all 270 J10 and 270 J20 instances — format confirmed consistent across all files ✅

---

## Phase 2 — Preprocessing and Lower Bounds

**Status:** Not started

- [ ] Compute `EST[i]` (Earliest Start Time) via **topological sort + longest path** on the DAG:
  - Initialise `EST[0] = 0`
  - For each activity in topological order: `EST[j] = max(EST[j], EST[i] + d[i])` for every arc `i → j`
- [ ] Compute `LFT[i]` (Latest Finish Time) by running the same process **backwards** from `n+1`:
  - Initialise `LFT[n+1] = EST[n+1]`
  - For each activity in reverse topological order: `LFT[i] = min(LFT[i], LFT[j] - d[i])` for every arc `i → j`
- [ ] Compute **network lower bound**: `LB_net = EST[n+1]` (longest path through the DAG)
- [ ] Compute **resource lower bound** for each resource type k:
      `LB_res[k] = ceil( Σ d[i] * r[i][k] for i in 1..n ) / R[k]`
- [ ] `LB = max(LB_net, max over k of LB_res[k])`
- [ ] Assert `EST[i] + d[i] <= LFT[i]` for all real activities (sanity check)

---

## Phase 3 — Baseline Greedy Scheduler (Serial SGS)

**Status:** Not started

- [ ] Implement **Serial Schedule Generation Scheme (SGS)**:
  1. Maintain a set of *eligible* activities (all predecessors already scheduled)
  2. Pick one eligible activity using a priority rule
  3. Compute its earliest feasible start time:
     - **(a) Precedence:** `start = max(S[pred] + d[pred])` over all predecessors
     - **(b) Resources:** shift `start` forward until `[start, start+d[i])` fits within capacity
  4. Schedule it, update eligible set
  5. Repeat until all `n` real activities are scheduled
- [ ] Implement **6 priority rules** (pick the eligible activity with the best score):
  - **SPT** — Shortest Processing Time: smallest `d[i]`
  - **LPT** — Longest Processing Time: largest `d[i]`
  - **MTS** — Most Total Successors: most downstream activities (transitive count)
  - **MC**  — Most Critical: smallest slack `LFT[i] - EST[i] - d[i]` (ascending)
  - **MR**  — Most Resources: highest total resource demand `Σ r[i][k]`
  - **LR**  — Least Resources: lowest total resource demand
- [ ] Run all 6 rules; keep the best (lowest Cmax) as the initial solution
- [ ] Run full **validation checklist** on the output before printing
- [ ] Test on J10 first — compute `Gap(%)` vs `LB`

**Pitfall:** Resource interval upper bound is **exclusive**: active during `[S[i], S[i]+d[i])`.
Check `S[i] <= t < S[i]+d[i]`, not `S[i] <= t <= S[i]+d[i]`.

---

## Phase 4 — Improve Solution Quality (Multi-Start SGS)

**Status:** Implemented but limited effectiveness

- [x] Implement multi-start SGS with random rule selection
- [x] Run multiple SGS iterations within time budget (28s)
- [x] Track and return best schedule found
- [ ] Tie-breaking randomization (future improvement)
- [ ] True metaheuristics like LNS+SA with proper neighborhoods (future)

**Current results:** No significant improvement over Phase 3 baseline (~35% avg gap).
This is expected — all 6 priority rules are deterministic, so re-running them produces
identical solutions. To improve further, need either:
  1. Randomised tie-breaking in SGS priority order
  2. Proper metaheuristics (LNS destroy-repair with variable neighbourhood)
  3. Local search with sophisticated feasibility maintenance

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
- [ ] Precedence: `S[j] >= S[i] + d[i]` for all arcs `i → j`
- [ ] Resource: at every time `t`, `Σ r[i][k]` for active `i` ≤ `R[k]`
- [ ] Non-negativity: `S[i] >= 0` for all `i`
- [ ] All `n` real activities have an assigned start time

---

## Phase 7 — Write-up

**Status:** Not started

- [ ] Describe algorithm design and rationale for choices (why Serial SGS + LNS+SA)
- [ ] Report Gap(%) statistics on J10 and J20 (average, worst, % within target)
- [ ] Analyse time budget usage (how many LNS iterations per instance on average)
- [ ] Discuss tradeoffs (e.g. why LNS+SA over Branch and Bound)
- [ ] Prepare slides if required

---

## Known Pitfalls (Keep This Handy)

| # | Pitfall | Where It Bites |
|---|---------|----------------|
| 1 | Resource interval is `[S[i], S[i]+d[i])` — **exclusive** upper bound | Phase 3, 6 |
| 2 | Check wall-clock time **before** every iteration, not after | Phase 5 |
| 3 | Do not assume a fixed Cmax upper bound — allocate resource tracking dynamically | Phase 3 |
| 4 | Dummy activities (0 and n+1) have `d=0` — never consume resources or block time | Phase 3 |

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

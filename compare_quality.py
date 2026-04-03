import argparse
import csv
import time
from pathlib import Path

from parser import parse_sch
from solver import classify_and_solve_multistart, classify_and_solve_optimal


def run_heuristic(instance, starts, seed, ls_iters, ls_neighbors, ls_step):
    t0 = time.perf_counter_ns()
    status, _, makespan, message = classify_and_solve_multistart(
        instance,
        starts=starts,
        seed=seed,
        ls_iters=ls_iters,
        ls_neighbors=ls_neighbors,
        ls_step=ls_step,
    )
    t1 = time.perf_counter_ns()
    elapsed_ms = (t1 - t0) / 1_000_000
    return status, makespan, message, elapsed_ms


def run_optimal(instance, time_limit_s):
    t0 = time.perf_counter_ns()
    status, _, makespan, message = classify_and_solve_optimal(
        instance,
        time_limit_s=time_limit_s,
    )
    t1 = time.perf_counter_ns()
    elapsed_ms = (t1 - t0) / 1_000_000
    return status, makespan, message, elapsed_ms


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare heuristic vs optimal/proof and write a CSV report."
    )
    parser.add_argument("--dataset", choices=["sm_j10", "sm_j20"], default="sm_j20")
    parser.add_argument("--starts", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ls-iters", type=int, default=20)
    parser.add_argument("--ls-neighbors", type=int, default=6)
    parser.add_argument("--ls-step", type=float, default=0.20)
    parser.add_argument(
        "--second-seed",
        type=int,
        default=42,
        help="Second heuristic seed for reproducibility check (set different value to test sensitivity).",
    )
    parser.add_argument("--optimal-time-limit", type=float, default=10.0)
    parser.add_argument(
        "--out",
        default="comparison_report.csv",
        help="Output CSV file path (relative to updated_instances).",
    )
    parser.add_argument(
        "--first-n",
        type=int,
        default=0,
        help="If > 0, run comparison only on first N instances after sorting.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    base_dir = Path(__file__).resolve().parent
    files = sorted(
        (base_dir / args.dataset).glob("PSP*.SCH"),
        key=lambda p: int(p.stem[3:]),
    )

    if args.first_n and args.first_n > 0:
        files = files[: args.first_n]

    if not files:
        raise FileNotFoundError(f"No PSP*.SCH files found in {args.dataset}")

    out_path = (base_dir / args.out).resolve()

    rows = []
    same_count = 0
    proven_count = 0
    matched_optimal_count = 0

    for f in files:
        inst = parse_sch(str(f))

        h1_status, h1_mk, h1_msg, h1_ms = run_heuristic(
            inst,
            max(1, args.starts),
            args.seed,
            max(0, args.ls_iters),
            max(1, args.ls_neighbors),
            max(0.01, args.ls_step),
        )
        h2_status, h2_mk, h2_msg, h2_ms = run_heuristic(
            inst,
            max(1, args.starts),
            args.second_seed,
            max(0, args.ls_iters),
            max(1, args.ls_neighbors),
            max(0.01, args.ls_step),
        )
        o_status, o_mk, o_msg, o_ms = run_optimal(inst, max(0.0, args.optimal_time_limit))

        same_heuristic = (
            h1_status == h2_status
            and h1_mk == h2_mk
        )
        if same_heuristic:
            same_count += 1

        gap = ""
        gap_pct = ""
        if o_status == "feasible_optimal" and h1_status in ("feasible", "feasible_optimal", "feasible_not_proven") and h1_mk is not None:
            proven_count += 1
            gap_val = h1_mk - o_mk
            gap = str(gap_val)
            if o_mk and o_mk > 0:
                gap_pct = f"{(100.0 * gap_val / o_mk):.2f}"
            else:
                gap_pct = "0.00"
            if gap_val == 0:
                matched_optimal_count += 1

        rows.append(
            {
                "instance": f.name,
                "heur1_status": h1_status,
                "heur1_makespan": "" if h1_mk is None else h1_mk,
                "heur1_time_ms": f"{h1_ms:.3f}",
                "heur1_message": h1_msg,
                "heur2_status": h2_status,
                "heur2_makespan": "" if h2_mk is None else h2_mk,
                "heur2_time_ms": f"{h2_ms:.3f}",
                "heur2_message": h2_msg,
                "same_heuristic_result": same_heuristic,
                "optimal_status": o_status,
                "optimal_makespan": "" if o_mk is None else o_mk,
                "optimal_time_ms": f"{o_ms:.3f}",
                "optimal_message": o_msg,
                "heur1_gap_to_optimal": gap,
                "heur1_gap_to_optimal_pct": gap_pct,
            }
        )

    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    print(f"Wrote report: {out_path}")
    print(f"Total instances: {total}")
    print(f"Heuristic reproducibility matches: {same_count}/{total}")
    print(f"Optimal-proven instances: {proven_count}")
    if proven_count > 0:
        print(f"Heuristic matched optimal on proven set: {matched_optimal_count}/{proven_count}")


if __name__ == "__main__":
    main()

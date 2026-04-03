import argparse
import multiprocessing as mp
import statistics
import time
from pathlib import Path

from parser import parse_sch
from solver import classify_and_solve_multistart, classify_and_solve_optimal


TIME_LIMIT_SECONDS = 30


def _solve_worker(instance, out_q, use_optimal, optimal_time_limit, starts, seed, ls_iters, ls_neighbors, ls_step):
    try:
        if use_optimal:
            status, _, makespan, message = classify_and_solve_optimal(
                instance,
                time_limit_s=optimal_time_limit,
            )
        else:
            status, _, makespan, message = classify_and_solve_multistart(
                instance,
                starts=starts,
                seed=seed,
                ls_iters=ls_iters,
                ls_neighbors=ls_neighbors,
                ls_step=ls_step,
            )
        out_q.put(("ok", status, makespan, message))
    except Exception as exc:
        out_q.put(("err", str(exc)))


def _run_with_timeout(
    inst,
    timeout_s,
    use_optimal=False,
    optimal_time_limit=10.0,
    starts=30,
    seed=42,
    ls_iters=20,
    ls_neighbors=6,
    ls_step=0.20,
):
    out_q = mp.Queue()
    proc = mp.Process(
        target=_solve_worker,
        args=(inst, out_q, use_optimal, optimal_time_limit, starts, seed, ls_iters, ls_neighbors, ls_step),
    )

    start = time.perf_counter_ns()
    proc.start()
    proc.join(timeout_s)
    end = time.perf_counter_ns()

    if proc.is_alive():
        proc.terminate()
        proc.join()
        elapsed_s = (end - start) / 1_000_000_000
        return ("timeout", elapsed_s)

    if out_q.empty():
        return ("err", "no result returned")

    worker_status, *payload = out_q.get()
    if worker_status == "err":
        return ("err", payload[0])

    elapsed_ms = (end - start) / 1_000_000
    status, makespan, message = payload
    return ("ok", status, makespan, message, elapsed_ms)


def _run_direct(
    inst,
    use_optimal=False,
    optimal_time_limit=10.0,
    starts=30,
    seed=42,
    ls_iters=20,
    ls_neighbors=6,
    ls_step=0.20,
):
    start = time.perf_counter_ns()
    if use_optimal:
        status, _, makespan, message = classify_and_solve_optimal(
            inst,
            time_limit_s=optimal_time_limit,
        )
    else:
        status, _, makespan, message = classify_and_solve_multistart(
            inst,
            starts=starts,
            seed=seed,
            ls_iters=ls_iters,
            ls_neighbors=ls_neighbors,
            ls_step=ls_step,
        )
    end = time.perf_counter_ns()
    elapsed_ms = (end - start) / 1_000_000
    return status, makespan, message, elapsed_ms


def _print_status_line(filepath, status, makespan=None, elapsed_ms=None, message=""):
    if status in ("feasible", "feasible_optimal", "feasible_not_proven"):
        suffix = ""
        if status == "feasible_optimal":
            suffix = " (OPTIMAL)"
        elif status == "feasible_not_proven":
            suffix = " (NOT PROVEN)"
        if elapsed_ms is not None:
            print(f"{filepath} | FEASIBLE{suffix} | Makespan: {makespan} | Time: {elapsed_ms:.3f} ms")
        else:
            print(f"{filepath} | FEASIBLE{suffix} | Makespan: {makespan}")
        return status

    if status == "true_infeasible":
        print(f"{filepath} | TRUE INFEASIBLE (capacity/graph infeasible)")
        return status

    if status == "heuristic_failed":
        print(f"{filepath} | HEURISTIC FAILED (possible false infeasible) | {message}")
        return status

    print(f"{filepath} | ERROR: {message or ('unknown status ' + str(status))}")
    return "error"


def run(
    filepath,
    timeout_s=None,
    repeat=1,
    warmup=1,
    use_optimal=False,
    optimal_time_limit=10.0,
    starts=30,
    seed=42,
    ls_iters=20,
    ls_neighbors=6,
    ls_step=0.20,
):
    inst = parse_sch(filepath)
    if timeout_s is not None and timeout_s > 0:
        result = _run_with_timeout(
            inst,
            timeout_s,
            use_optimal=use_optimal,
            optimal_time_limit=optimal_time_limit,
            starts=starts,
            seed=seed,
            ls_iters=ls_iters,
            ls_neighbors=ls_neighbors,
            ls_step=ls_step,
        )
        if result[0] == "timeout":
            elapsed_s = result[1]
            print(f"{filepath} | TIMEOUT (> {timeout_s}s) | Time: {elapsed_s:.3f} s")
            return "timeout"
        if result[0] == "err":
            print(f"{filepath} | ERROR: {result[1]}")
            return "error"

        _, status, makespan, message, elapsed_ms = result
        return _print_status_line(filepath, status, makespan=makespan, elapsed_ms=elapsed_ms, message=message)

    # Fair timing mode (no process overhead): warmup + repeated measurements.
    try:
        for _ in range(max(0, warmup)):
            _run_direct(
                inst,
                use_optimal=use_optimal,
                optimal_time_limit=optimal_time_limit,
                starts=starts,
                seed=seed,
                ls_iters=ls_iters,
                ls_neighbors=ls_neighbors,
                ls_step=ls_step,
            )

        run_count = max(1, repeat)
        times = []
        makespan = None
        final_status = None
        final_message = ""
        for _ in range(run_count):
            status_i, makespan_i, message_i, elapsed_ms = _run_direct(
                inst,
                use_optimal=use_optimal,
                optimal_time_limit=optimal_time_limit,
                starts=starts,
                seed=seed,
                ls_iters=ls_iters,
                ls_neighbors=ls_neighbors,
                ls_step=ls_step,
            )
            final_status = status_i
            final_message = message_i
            if status_i not in ("feasible", "feasible_optimal", "feasible_not_proven"):
                break
            if makespan is None:
                makespan = makespan_i
            times.append(elapsed_ms)

        if final_status not in ("feasible", "feasible_optimal", "feasible_not_proven"):
            return _print_status_line(filepath, final_status, message=final_message)

        avg_ms = sum(times) / len(times)
        median_ms = statistics.median(times)
        min_ms = min(times)
        max_ms = max(times)

        suffix = ""
        if final_status == "feasible_optimal":
            suffix = " (OPTIMAL)"
        elif final_status == "feasible_not_proven":
            suffix = " (NOT PROVEN)"

        print(
            f"{filepath} | FEASIBLE{suffix} | Makespan: {makespan} | "
            f"Avg: {avg_ms:.3f} ms | Median: {median_ms:.3f} ms | "
            f"Min: {min_ms:.3f} ms | Max: {max_ms:.3f} ms | Runs: {run_count}"
        )
        return final_status
    except Exception as exc:
        print(f"{filepath} | ERROR: {exc}")
        return "error"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--timeout",
        type=int,
        default=0,
        help=(
            "Per-instance timeout in seconds. "
            "Use 0 for fastest mode (no timeout process isolation)."
        ),
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=10,
        help="Number of measured runs per instance in fast mode (timeout=0).",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=10,
        help="Number of warmup runs per instance before measured runs in fast mode.",
    )
    parser.add_argument(
        "--optimal",
        action="store_true",
        help="Use exact branch-and-bound mode to prove optimality when possible.",
    )
    parser.add_argument(
        "--optimal-time-limit",
        type=float,
        default=10.0,
        help="Per-instance time limit (seconds) for exact optimal mode.",
    )
    parser.add_argument(
        "--starts",
        type=int,
        default=30,
        help="Number of randomized SGS starts in scalable heuristic mode.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for multi-start heuristic mode.",
    )
    parser.add_argument(
        "--ls-iters",
        type=int,
        default=20,
        help="Local-search refinement iterations after multistart (heuristic mode).",
    )
    parser.add_argument(
        "--ls-neighbors",
        type=int,
        default=6,
        help="Neighbor candidates evaluated per local-search iteration.",
    )
    parser.add_argument(
        "--ls-step",
        type=float,
        default=0.20,
        help="Bias mutation magnitude for local-search moves.",
    )
    parser.add_argument(
        "--dataset",
        choices=["sm_j10", "sm_j20"],
        default="sm_j10",
        help="Dataset folder to run.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    base_dir = Path(__file__).resolve().parent
    files = sorted(
        (base_dir / args.dataset).glob("PSP*.SCH"),
        key=lambda p: int(p.stem[3:]),
    )

    if not files:
        raise FileNotFoundError(f"No PSP*.SCH files found in {args.dataset}")

    timeout_s = args.timeout if args.timeout > 0 else None
    if timeout_s is None:
        print(
            f"Running in fair timing mode (no timeout): "
            f"warmup={max(0, args.warmup)}, repeat={max(1, args.repeat)}"
        )
    else:
        print(f"Running with timeout: {timeout_s}s per instance.")

    if args.optimal:
        print(f"Exact mode enabled with per-instance limit: {args.optimal_time_limit:.2f}s")
    else:
        print(
            "Scalable heuristic mode: "
            f"starts={max(1, args.starts)}, seed={args.seed}, "
            f"ls_iters={max(0, args.ls_iters)}, "
            f"ls_neighbors={max(1, args.ls_neighbors)}, "
            f"ls_step={max(0.01, args.ls_step):.2f}"
        )
    print(f"Dataset: {args.dataset}")

    counts = {
        "feasible": 0,
        "feasible_optimal": 0,
        "feasible_not_proven": 0,
        "true_infeasible": 0,
        "heuristic_failed": 0,
        "timeout": 0,
        "error": 0,
    }

    for f in files:
        status = run(
            str(f),
            timeout_s=timeout_s,
            repeat=max(1, args.repeat),
            warmup=max(0, args.warmup),
            use_optimal=args.optimal,
            optimal_time_limit=max(0.0, args.optimal_time_limit),
            starts=max(1, args.starts),
            seed=args.seed,
            ls_iters=max(0, args.ls_iters),
            ls_neighbors=max(1, args.ls_neighbors),
            ls_step=max(0.01, args.ls_step),
        )
        if status in counts:
            counts[status] += 1

    total = len(files)
    print("\nSummary")
    print(f"Total: {total}")
    print(f"Feasible: {counts['feasible']}")
    print(f"Feasible optimal: {counts['feasible_optimal']}")
    print(f"Feasible not proven: {counts['feasible_not_proven']}")
    print(f"True infeasible: {counts['true_infeasible']}")
    print(f"Heuristic failed: {counts['heuristic_failed']}")
    print(f"Timeout: {counts['timeout']}")
    print(f"Error: {counts['error']}")
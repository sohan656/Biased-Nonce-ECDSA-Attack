#!/usr/bin/env python3
"""
run_experiments.py -- empirical evaluation of the biased-nonce ECDSA attack.

Produces the data for rubric criterion 3 (Testing & Preliminary Results) and
synopsis objective 4 (minimum #signatures / minimum bias for reliable recovery).

Four experiments, all written INCREMENTALLY to results/experiments.csv so the
run is resumable: re-running skips (experiment, params, trial) rows already done.

Columns: experiment, model, l, t, dim, trial, success, verified, seconds
"""
import sys, os, csv, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import ecdsa_hnp as e

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "results", "experiments.csv")
FIELDS = ["experiment", "model", "l", "t", "dim", "trial", "success", "verified", "seconds"]


def load_done():
    done = set()
    if os.path.exists(RESULTS):
        with open(RESULTS) as f:
            for row in csv.DictReader(f):
                done.add((row["experiment"], row["model"], int(row["l"]),
                          int(row["t"]), int(row["trial"])))
    return done


def append_row(row):
    new = not os.path.exists(RESULTS)
    with open(RESULTS, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def run_one(experiment, model, l, t, trial):
    seed = hash((experiment, model, l, t, trial)) & 0xffffffff
    t0 = time.time()
    res = e.run_attack(model=model, l=l, t=t, seed=seed)
    dt = time.time() - t0
    return {
        "experiment": experiment, "model": model, "l": l, "t": t, "dim": t + 2,
        "trial": trial, "success": int(res["success"]),
        "verified": int(res["verified"]), "seconds": round(dt, 3),
    }


# ---------------------------------------------------------------------------
# Experiment grids  (kept modest so the whole sweep finishes in minutes)
# ---------------------------------------------------------------------------
def plan():
    jobs = []

    # Exp 1: success rate vs BIAS (l), signatures fixed high enough to show a
    # clean fail->success transition as l grows.
    T_FIXED = 36
    for l in [10, 12, 13, 14, 15, 16, 18, 20]:
        for trial in range(6):
            jobs.append(("vs_bias", "zero_msb", l, T_FIXED, trial))

    # Exp 2: success rate vs #SIGNATURES (t), bias fixed
    L_FIXED = 14
    for t in [26, 30, 32, 34, 36, 40, 44]:
        for trial in range(6):
            jobs.append(("vs_sigs", "zero_msb", L_FIXED, t, trial))

    # Exp 3: RUNTIME vs lattice dimension (always-succeed regime l=20)
    for t in [20, 25, 30, 35, 40, 45]:
        for trial in range(3):
            jobs.append(("runtime", "zero_msb", 20, t, trial))

    # Exp 4: MODEL comparison at a setting where all three should recover
    for model in ["zero_msb", "zero_lsb", "known_msb"]:
        for trial in range(6):
            jobs.append(("models", model, 18, 32, trial))

    return jobs


def main(budget_seconds=3600):
    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    done = load_done()
    jobs = plan()
    todo = [j for j in jobs if j not in done]
    print(f"total jobs: {len(jobs)}  |  already done: {len(done)}  |  remaining: {len(todo)}")
    start = time.time()
    for i, (exp, model, l, t, trial) in enumerate(todo):
        if time.time() - start > budget_seconds:
            print(f"\n[budget reached] stopping; {len(todo)-i} jobs left -- re-run to continue.")
            return False
        row = run_one(exp, model, l, t, trial)
        append_row(row)
        print(f"  [{i+1}/{len(todo)}] {exp:8s} {model:9s} l={l:2d} t={t:2d} "
              f"trial={trial} -> success={row['success']} {row['seconds']:.1f}s")
    print("\nALL EXPERIMENTS COMPLETE.")
    return True


if __name__ == "__main__":
    main()

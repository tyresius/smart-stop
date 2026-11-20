#!/usr/bin/env python3
"""
Block 7b (balanced) — jumper margins on the MATURE stack
=========================================================
The completion check (2026-07-19). Re-runs the Block 7b hot-split grid on
`SmartStopBalancedResponse` (balance-routed pre-flash + jumper response +
the bug-#8 leader-capped predictor) — the candidate "finished controller".

Two questions:
  1. Did the bug-#8 fix (more conservative follower prediction) lift the
     hot-split cross-path floor above the 3.3 m margin?
  2. Did fairness routing REDUCE the jumper hazard? Patrick's mechanism:
     unfair service manufactures frustrated jumpers (patience model), so a
     controller that serves the side street on schedule should see fewer
     jumps and larger margins than the throughput-greedy `SmartStopResponse`.

Grid identical to block7_hotsplit.py (q in {0,5,10%}, patience U(8,20)s,
lambda in {1600,2000,2400}, 3 seeds) so before/after is paired. Prints a
side-by-side vs the committed block7_hotsplit.csv.

Usage:  python block7_balanced.py [--smoke]
"""

import csv
import sys
import time

import numpy as np

import balance_preflash  # noqa: F401  registers SmartStopBalancedResponse
from capacity_curves import run_stream
from starvation_probe import make_probe_schedule, road_stats, VICTIM, DOMINANT

ALG = 'SmartStopBalancedResponse'
Q_LEVELS = [0.0, 0.05, 0.10]
PATIENCE = (8.0, 20.0)
LAMBDAS  = [1600, 2000, 2400]
REPS     = 3
MARGIN_M = 3.3
REF_CSV  = "block7_hotsplit.csv"   # committed SmartStopResponse baseline


def main():
    smoke = "--smoke" in sys.argv
    lams = [2000] if smoke else LAMBDAS
    qs = [0.10] if smoke else Q_LEVELS
    reps = 1 if smoke else REPS

    rows = []
    t0 = time.time()
    for lam in lams:
        for rep in range(reps):
            schedule = make_probe_schedule(lam, rep, 'poisson')
            for q in qs:
                jk = None if q == 0.0 else (q, *PATIENCE)
                res = run_stream(ALG, schedule, fair=True, jumpers=jk)
                vs = res['vehicles']
                served = [v for v in vs if v['served']]
                delays = [v['control_delay'] for v in served]
                vic = road_stats(vs, VICTIM)
                dom = road_stats(vs, DOMINANT)
                rows.append(dict(
                    lam_vph=lam, rep=rep, q=q, n_jumps=res['n_jumps'],
                    mean_delay=round(float(np.mean(delays)), 2) if delays else None,
                    served_frac=round(len(served) / len(vs), 4) if vs else None,
                    victim_mean=vic['mean'], dom_mean=dom['mean'],
                    min_dist_m=(round(res['min_dist'], 2)
                                if res['min_dist'] != float('inf') else ''),
                ))
                r = rows[-1]
                print(f"  λ={lam:>5} rep {rep} q={q:>4.0%}: jumps={r['n_jumps']}, "
                      f"min_dist={r['min_dist_m']} m, delay={r['mean_delay']} s, "
                      f"served={r['served_frac']} ({time.time()-t0:.0f}s)",
                      flush=True)

    out = "block7_balanced_smoke.csv" if smoke else "block7_balanced.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {out}")

    # ── Paired verdict vs committed SmartStopResponse ───────────────────────
    ref = {}
    try:
        for r in csv.DictReader(open(REF_CSV)):
            ref[(int(r['lam_vph']), r['rep'], float(r['q']))] = r
    except FileNotFoundError:
        ref = {}

    def cell(sel, field, agg):
        vals = [r[field] for r in sel if r[field] not in (None, '')]
        vals = [float(v) for v in vals]
        return agg(vals) if vals else None

    print("\n" + "=" * 84)
    print(f"MATURE STACK ({ALG}) vs committed SmartStopResponse — hot split")
    print("=" * 84)
    print(f"{'λ':>6} | {'q':>5} | {'min dist':>18} | {'jumps':>12} | "
          f"{'victim mean':>16} | verdict")
    print("-" * 84)
    all_floor = float('inf')
    for lam in lams:
        for q in qs:
            sel = [r for r in rows if r['lam_vph'] == lam and r['q'] == q]
            m = cell(sel, 'min_dist_m', min)
            nj = int(np.sum([r['n_jumps'] for r in sel]))
            vm = cell(sel, 'victim_mean', np.mean)
            rsel = [ref[k] for k in ref
                    if k[0] == lam and abs(k[2] - q) < 1e-6]
            rm = cell(rsel, 'min_dist_m', min) if rsel else None
            rnj = int(np.sum([int(r['n_jumps']) for r in rsel])) if rsel else None
            rvm = cell(rsel, 'victim_mean', np.mean) if rsel else None
            if m is not None:
                all_floor = min(all_floor, m)
            verdict = "SAFE" if (m is not None and m >= MARGIN_M) else "< margin"
            md = f"{m:.2f}" + (f" (was {rm:.2f})" if rm is not None else "")
            jd = f"{nj}" + (f" (was {rnj})" if rnj is not None else "")
            vd = (f"{vm:.1f}s" if vm is not None else "—") + \
                 (f" (was {rvm:.1f})" if rvm is not None else "")
            print(f"{lam:>6} | {q:>5.0%} | {md:>18} | {jd:>12} | {vd:>16} | {verdict}")
    print("-" * 84)
    print(f"MATURE-STACK HOT-SPLIT FLOOR: {all_floor:.2f} m  "
          f"({'CLEARS 3.3 m — final safety asterisk closes' if all_floor >= MARGIN_M else 'still < 3.3 m — documented limitation stands'})")
    print("=" * 84)


if __name__ == "__main__":
    main()

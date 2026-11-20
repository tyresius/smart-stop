#!/usr/bin/env python3
"""
Block 7b — Jumper response re-validated on the starvation hot split
====================================================================
Audit 2026-07-08: `SmartStopResponse` posted a 3.19 m min cross-path distance
on the hot-split schedule (poisson, 2,000 veh/h, rep 0) — below the 3.3 m
Block 7 margin — with jumpers DISABLED. Block 7 only swept balanced
schedules, so hot-split × Response was an untested combination (flagged in
CLAIMS §5 and README backlog #4).

This sweep closes (or confirms) that flag: the full Block 7 grid
(q ∈ {0, 5%, 10%}, patience U(8,20) s) on the hot-split arrival pattern
(dominant Main E 45% / 80%-through aimed at Green S's merge; victim 25%),
λ ∈ {1,600, 2,000, 2,400}, 3 seeds each. q=0 cells isolate the evasive-stack
dynamics from jump events themselves.

Usage:  python block7_hotsplit.py [--smoke]
"""

import csv
import sys
import time

import numpy as np

import block7_response  # noqa: F401  registers ALG_MAP['SmartStopResponse']
from capacity_curves import run_stream
from starvation_probe import make_probe_schedule, road_stats, VICTIM, DOMINANT

Q_LEVELS = [0.0, 0.05, 0.10]
PATIENCE = (8.0, 20.0)
LAMBDAS  = [1600, 2000, 2400]
REPS     = 3
MARGIN_M = 3.3


def main():
    smoke = "--smoke" in sys.argv
    lams = [2000] if smoke else LAMBDAS
    qs = [0.0] if smoke else Q_LEVELS
    reps = 1 if smoke else REPS

    rows = []
    t0 = time.time()
    for lam in lams:
        for rep in range(reps):
            schedule = make_probe_schedule(lam, rep, 'poisson')
            for q in qs:
                jk = None if q == 0.0 else (q, *PATIENCE)
                res = run_stream('SmartStopResponse', schedule, fair=True,
                                 jumpers=jk)
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
                    min_samepath_m=(round(res['min_samepath'], 2)
                                    if res['min_samepath'] != float('inf') else ''),
                ))
                r = rows[-1]
                print(f"  λ={lam:>5} rep {rep} q={q:>4.0%}: "
                      f"jumps={r['n_jumps']}, min_dist={r['min_dist_m']} m, "
                      f"delay={r['mean_delay']} s, served={r['served_frac']} "
                      f"({time.time()-t0:.0f}s)", flush=True)

    out = "block7_hotsplit_smoke.csv" if smoke else "block7_hotsplit.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {out}")

    print("\n" + "=" * 78)
    print("JUMPER RESPONSE x HOT SPLIT — cross-path margin verdicts")
    print("=" * 78)
    print(f"{'λ':>6} | {'q':>5} | {'jumps':>5} | {'min dist':>8} | "
          f"{'mean delay':>10} | {'served':>6} | {'verdict':>8}")
    for lam in lams:
        for q in qs:
            sel = [r for r in rows if r['lam_vph'] == lam and r['q'] == q]
            if not sel:
                continue
            m = min(float(r['min_dist_m']) for r in sel if r['min_dist_m'] != '')
            d = float(np.mean([r['mean_delay'] for r in sel
                               if r['mean_delay'] is not None]))
            s = float(np.mean([r['served_frac'] for r in sel]))
            nj = int(np.sum([r['n_jumps'] for r in sel]))
            verdict = "SAFE" if m >= MARGIN_M else "VIOLATED"
            print(f"{lam:>6} | {q:>5.0%} | {nj:>5} | {m:>7.2f}m | "
                  f"{d:>9.1f}s | {s*100:>5.0f}% | {verdict:>8}")
    print("=" * 78)


if __name__ == "__main__":
    main()

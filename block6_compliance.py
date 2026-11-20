#!/usr/bin/env python3
"""
Block 6 — Compliance Sweep: flash-jumpers (the last untested kill-risk)
========================================================================
A jumper is a driver who, after waiting past their patience at the head of
the queue, goes WITHOUT the green flash. The controller never predicted or
approved the launch; it only "sees" the jumper once moving (the camera
picks them up as active traffic, so all SUBSEQUENT flash decisions account
for them — that part of the product works by construction). The exposure
is the jump moment itself: an unauthorized vehicle entering conflicts the
gating already cleared for others.

Sweep: q ∈ {0%, 5%, 10%} of drivers are jumpers, patience ~ U(8, 20) s,
on the mature controller (SmartStopPreflash) at moderate and heavy demand.
Metrics: cross-path minimum distance + violation count (safety), mean
delay (jumping's system cost/benefit).

Usage:  python block6_compliance.py [--smoke]
"""

import csv
import sys
import time

import numpy as np

import block5_adaptive  # registers SmartStopPreflash in ALG_MAP  # noqa: F401
from capacity_curves import run_stream, make_schedule

Q_LEVELS  = [0.0, 0.05, 0.10]
PATIENCE  = (8.0, 20.0)
LAMBDAS   = [1200, 2000]
ALG       = 'SmartStopPreflash'
REPS      = 2
MARGIN_M  = 3.4          # violation threshold (3.5 m margin minus the usual
                         # 0.04-0.06 m discretization shave)


def main():
    smoke = "--smoke" in sys.argv
    lams = [1200] if smoke else LAMBDAS
    qs = [0.10] if smoke else Q_LEVELS
    reps = 1 if smoke else REPS

    rows = []
    t0 = time.time()
    for lam in lams:
        for rep in range(reps):
            schedule = make_schedule(lam, rep)
            for q in qs:
                jk = None if q == 0.0 else (q, *PATIENCE)
                res = run_stream(ALG, schedule, fair=True, jumpers=jk)
                vs = res['vehicles']
                served = [v for v in vs if v['served']]
                delays = [v['control_delay'] for v in served]
                rows.append(dict(
                    lam_vph=lam, rep=rep, q=q, n_jumps=res['n_jumps'],
                    mean_delay=round(float(np.mean(delays)), 2) if delays else None,
                    served_frac=round(len(served) / len(vs), 4) if vs else None,
                    min_dist_m=(round(res['min_dist'], 2)
                                if res['min_dist'] != float('inf') else ''),
                ))
                print(f"  λ={lam:>5} rep {rep} q={q:>4.0%}: "
                      f"jumps={res['n_jumps']}, "
                      f"min_dist={rows[-1]['min_dist_m']} m, "
                      f"delay={rows[-1]['mean_delay']} s "
                      f"({time.time()-t0:.0f}s)", flush=True)

    out = "block6_compliance_smoke.csv" if smoke else "block6_compliance.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {out}")

    print("\n" + "=" * 66)
    print("COMPLIANCE SWEEP — flash-jumpers on SmartStopPreflash")
    print("=" * 66)
    print(f"{'λ':>6} | {'q':>5} | {'jumps':>5} | {'mean delay':>10} | "
          f"{'min dist':>8} | {'violation?':>10}")
    for lam in lams:
        for q in qs:
            sel = [r for r in rows if r['lam_vph'] == lam and r['q'] == q]
            if not sel:
                continue
            d = float(np.mean([r['mean_delay'] for r in sel
                               if r['mean_delay'] is not None]))
            m = min(float(r['min_dist_m']) for r in sel
                    if r['min_dist_m'] != '')
            nj = int(np.sum([r['n_jumps'] for r in sel]))
            viol = "YES <-- " if m < MARGIN_M else "no"
            print(f"{lam:>6} | {q:>5.0%} | {nj:>5} | {d:>9.1f}s | "
                  f"{m:>7.2f}m | {viol:>10}")
    print("=" * 66)


if __name__ == "__main__":
    main()

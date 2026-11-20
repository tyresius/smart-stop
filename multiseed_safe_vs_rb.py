#!/usr/bin/env python3
"""
Multi-seed confirmation of Smart Safe vs Roundabout (survival gate)
===================================================================
(2026-07-21.) The single-seed survival gate showed streaming Smart Safe holds
the roundabout regime map (wins arterial + dominant). This re-runs it across
5 seeds to firm up the numbers before they go in the deck — including the
counterintuitive Safe ~ full-Smart-Stop result, which needs seed support.

Writes each run to multiseed_safe_vs_rb.csv as it completes (partial results
survive an interrupted run), then aggregates mean +/- std per cell.

Usage:  python multiseed_safe_vs_rb.py [--smoke]
"""
import csv
import os
import sys
import time

import numpy as np

# importing registers ALG_MAP['SmartSafeStream'] (streaming Smart Safe)
from safe_vs_roundabout import CELLS, ALGS
from capacity_curves import run_stream, make_schedule

REPS = 5
OUT = "multiseed_safe_vs_rb.csv"


def measure(name, sched):
    res = run_stream(name, sched, fair=True)
    served = [v for v in res['vehicles'] if v['served']]
    d = [v['control_delay'] for v in served]
    return (round(float(np.mean(d)), 2) if d else None,
            round(len(served) / len(res['vehicles']) * 100, 2) if res['vehicles'] else None)


def main():
    smoke = "--smoke" in sys.argv
    cells = CELLS[1:2] if smoke else CELLS
    reps = 1 if smoke else REPS

    fields = ['cell', 'lam', 'rep', 'alg', 'mean_delay', 'served_pct']
    # fresh file
    with open(OUT, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=fields).writeheader()

    t0 = time.time()
    for rep in range(reps):
        for label, lam, split in cells:
            sched = make_schedule(lam, rep, split=split)
            for aname, akey in ALGS:
                mean, sf = measure(akey, sched)
                row = dict(cell=label, lam=lam, rep=rep, alg=aname,
                           mean_delay=mean, served_pct=sf)
                with open(OUT, "a", newline="") as f:
                    csv.DictWriter(f, fieldnames=fields).writerow(row)
                print(f"  rep {rep} {label:>9} {lam} {aname:<16}: {mean}s "
                      f"(served {sf}%)  ({time.time()-t0:.0f}s)", flush=True)

    # ── Aggregate ───────────────────────────────────────────────────────────
    rows = list(csv.DictReader(open(OUT)))
    def agg(cell, alg):
        vals = [float(r['mean_delay']) for r in rows
                if r['cell'] == cell and r['alg'] == alg and r['mean_delay'] not in ('', 'None')]
        return (np.mean(vals), np.std(vals), len(vals)) if vals else (None, None, 0)

    cell_labels = []
    for label, lam, _ in cells:
        tag = f'{label} {lam}'
        if tag not in cell_labels:
            cell_labels.append(tag)

    print("\n" + "=" * 82)
    print(f"MULTI-SEED ({reps}) — Smart Safe vs Roundabout, mean delay +/- std (s)")
    print("=" * 82)
    print(f"{'cell':>15} | {'Smart Safe':>16} | {'full SmartStop':>16} | "
          f"{'Roundabout':>16} | verdict")
    print("-" * 82)
    for label, lam, _ in cells:
        tag = f'{label} {lam}'
        safe_m, safe_s, _ = agg(label, 'Smart Safe')
        full_m, full_s, _ = agg(label, 'full Smart Stop')
        rb_m, rb_s, _ = agg(label, 'Roundabout')
        verdict = ('Safe WINS' if safe_m < rb_m else
                   'parity' if abs(safe_m - rb_m) / rb_m < 0.10 else 'Safe loses')
        print(f"{tag:>15} | {safe_m:>6.1f} ±{safe_s:>4.1f}s | "
              f"{full_m:>6.1f} ±{full_s:>4.1f}s | {rb_m:>6.1f} ±{rb_s:>4.1f}s | {verdict}")
    print("=" * 82)


if __name__ == "__main__":
    main()

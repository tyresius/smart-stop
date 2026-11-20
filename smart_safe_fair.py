#!/usr/bin/env python3
"""
Smart Safe under curvature-fair physics — the "bridge" numbers
===============================================================
The deck restructure (July 17) presents Smart Safe as a conservative bridge
from today's stop sign to full Smart Stop. Its only existing numbers are from
the retired legacy benchmark, and we don't cut corners: this runs
`SmartStopSafeAlgorithm` over the exact stratified 348-scenario sample used
by `reality_sweeps.py --fair` (same SEED, same fair=True knob), then pairs it
per-scenario against the committed `reality_fair_results.csv`.

Expected shape if the bridge story is honest: Traditional < SmartSafe <
SmartStop on clearance, with SmartSafe's win-rate and margins in between.

Usage:  python smart_safe_fair.py [--smoke]
"""

import csv
import sys
import time

import numpy as np

from path_based_smart_stop import SmartStopSafeAlgorithm
from reality_sweeps import stratified_sample, run_scenario

REF_CSV = "reality_fair_results.csv"
OUT_CSV = "smart_safe_fair.csv"


def main():
    smoke = "--smoke" in sys.argv
    sample = stratified_sample()
    if smoke:
        sample = sample[:6] + sample[-6:]
    print(f"Smart Safe fair-physics run: {len(sample)} scenarios")

    rows = []
    t0 = time.time()
    n = len(sample)
    for i, (sid, configs) in enumerate(sample):
        tt, ok, md = run_scenario(SmartStopSafeAlgorithm, configs, sid,
                                  fair=True)
        rows.append(dict(
            sweep='fair', value='curvature', algorithm='SmartSafe',
            scenario_id=sid, n_vehicles=len(configs),
            total_time=round(tt, 2), completed=int(ok),
            min_dist_m=(round(md, 2) if md != float('inf') else ''),
        ))
        if (i + 1) % 40 == 0 or i == n - 1:
            print(f"  [{i+1}/{n}] {time.time()-t0:.0f}s elapsed", flush=True)

    out = "smart_safe_fair_smoke.csv" if smoke else OUT_CSV
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {out} ({len(rows)} rows)")

    # ── Paired comparison vs the committed fair results ─────────────────────
    ref = {}
    for r in csv.DictReader(open(REF_CSV)):
        ref[(r['algorithm'], r['scenario_id'])] = r
    safe = {str(r['scenario_id']): r for r in rows if r['completed']}

    print("\n" + "=" * 74)
    print("SMART SAFE — curvature-fair physics, paired vs reality_fair_results")
    print("=" * 74)
    md_all = [float(r['min_dist_m']) for r in rows
              if r['completed'] and r['min_dist_m'] != '']
    print(f"  completed: {sum(1 for r in rows if r['completed'])}/{len(rows)}"
          f"   min-dist floor: {min(md_all):.2f} m" if md_all else "  n/a")
    for opp in ('Traditional', 'Roundabout', 'SmartStop'):
        savings, wins, losses, ties = [], 0, 0, 0
        for sid, r in safe.items():
            b = ref.get((opp, sid))
            if not b or not int(b['completed']):
                continue
            bt, st = float(b['total_time']), float(r['total_time'])
            savings.append((bt - st) / bt * 100 if bt else 0.0)
            d = bt - st
            if d > 0.15: wins += 1
            elif d < -0.15: losses += 1
            else: ties += 1
        tot = wins + losses + ties
        if tot == 0:
            print(f"  vs {opp:<12}: no paired scenarios")
            continue
        print(f"  vs {opp:<12}: mean saving {np.mean(savings):+6.1f}%   "
              f"wins {wins}/{tot} ({wins/tot*100:.0f}%), "
              f"loses {losses}/{tot}, ties {ties}/{tot}")
    print("=" * 74)


if __name__ == "__main__":
    main()

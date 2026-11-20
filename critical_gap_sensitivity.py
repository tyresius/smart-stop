#!/usr/bin/env python3
"""
Critical-gap sensitivity — reviewer-proofing the roundabout comparison
=======================================================================
REALITY_REPORT pins the roundabout entry critical gap at 4.5 s, between the
field-measured 3.86 s (single-lane US) and HCM-default ~5.0 s, and notes a
±0.6 s sensitivity run is "cheap if a reviewer asks." This runs it before
anyone asks.

Question: do the two headline regime-map cells survive across the plausible
critical-gap band?
  - Arterial 40/40/10/10 @ 2,000 (Smart Stop pre-flash claims 37.7 vs 73.3 s)
    -> does a 3.9 s (aggressive-driver) roundabout close the gap?
  - Balanced 25/25/25/25 @ 2,400 (roundabout leads 37.5 vs 53.6 s)
    -> conceded cell; does 5.1 s hand it to Smart Stop? (If so, we STILL
       concede it — the pinned 4.5 s verdict stands; this just bounds it.)

Only the roundabout is re-run (Smart Stop doesn't read the gap constant);
Smart Stop reference numbers come from CLAIMS.md verbatim.

Usage:  python critical_gap_sensitivity.py [--smoke]
"""

import csv
import sys
import time

import numpy as np

from block3_reality import RealisticRoundabout
from capacity_curves import run_stream, make_schedule, ALG_MAP

GAPS = [3.9, 4.5, 5.1]          # s — field-measured .. pinned .. HCM-default
CELLS = [
    # (label, split, lam, SmartStop reference from CLAIMS §3, its source note)
    ("arterial",  [0.4, 0.4, 0.1, 0.1], 2000, 37.7, "pre-flash, CLAIMS §3"),
    ("balanced",  None,                 2400, 53.6, "pre-flash, CLAIMS §3"),
]
REPS = 2


def _register_gap_variants():
    names = {}
    for g in GAPS:
        name = f"Roundabout_gap{g:.1f}"
        cls = type(f"RealisticRoundabout_gap{str(g).replace('.', '_')}",
                   (RealisticRoundabout,), {"critical_gap": g})
        ALG_MAP[name] = cls
        names[g] = name
    return names


def main():
    smoke = "--smoke" in sys.argv
    gaps = [3.9] if smoke else GAPS
    cells = CELLS[:1] if smoke else CELLS
    reps = 1 if smoke else REPS

    names = _register_gap_variants()
    rows = []
    t0 = time.time()
    for label, split, lam, ss_ref, ss_note in cells:
        for rep in range(reps):
            schedule = make_schedule(lam, rep, split=split)
            for g in gaps:
                res = run_stream(names[g], schedule, fair=True)
                vs = res['vehicles']
                served = [v for v in vs if v['served']]
                d = [v['control_delay'] for v in served]
                rows.append(dict(
                    cell=label, lam_vph=lam, rep=rep, critical_gap_s=g,
                    rb_mean_delay=round(float(np.mean(d)), 2) if d else None,
                    served_frac=round(len(served) / len(vs), 4) if vs else None,
                    min_dist_m=(round(res['min_dist'], 2)
                                if res['min_dist'] != float('inf') else ''),
                ))
                r = rows[-1]
                print(f"  {label:>8} λ={lam} rep {rep} gap={g}: "
                      f"delay={r['rb_mean_delay']} s served={r['served_frac']} "
                      f"({time.time()-t0:.0f}s)", flush=True)

    out = "critical_gap_sensitivity_smoke.csv" if smoke \
        else "critical_gap_sensitivity.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {out}")

    print("\n" + "=" * 76)
    print("CRITICAL-GAP SENSITIVITY — roundabout mean delay by gap")
    print("=" * 76)
    for label, split, lam, ss_ref, ss_note in cells:
        print(f"\n{label.upper()} @ {lam} veh/h   "
              f"[Smart Stop reference: {ss_ref} s ({ss_note})]")
        for g in gaps:
            sel = [r['rb_mean_delay'] for r in rows
                   if r['cell'] == label and r['critical_gap_s'] == g
                   and r['rb_mean_delay'] is not None]
            if not sel:
                continue
            m = float(np.mean(sel))
            verdict = ("Smart Stop still wins" if ss_ref < m else
                       "roundabout wins/ties")
            print(f"  gap {g:>3} s -> {m:7.1f} s   ({verdict})")
    print("=" * 76)


if __name__ == "__main__":
    main()

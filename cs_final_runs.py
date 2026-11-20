#!/usr/bin/env python3
"""
Final benchmark cleanups (2026-07-05):
  1. Pre-flash WITHOUT adaptive windows on balanced patterns — Block 5
     benchmarked pre-flash stacked on adaptive windows, which actively hurt
     balanced traffic; this isolates the clean pre-flash number.
  2. Arterial rerun with pre-flash — the Block 4 arterial win (Smart Stop's
     signature regime) predates the best controller; the margin should widen.
"""

import csv
import sys
import time

import numpy as np

from block3_reality import GatedPlatoonSmartStop
from block5_adaptive import PreflashAdaptiveSmartStop
from capacity_curves import run_stream, make_schedule, ALG_MAP


class PreflashOnlySmartStop(GatedPlatoonSmartStop):
    """Pre-flash lever without the adaptive-window lever (fixed PLATOON_MAX=4)."""
    MIN_CANDIDATE_DWELL = 0.5

    def __init__(self, geometry):
        super().__init__(geometry)
        self.collision_detector.min_candidate_dwell = self.MIN_CANDIDATE_DWELL


ALG_MAP['SmartStopPreflashOnly'] = PreflashOnlySmartStop

RUNS = [
    # (pattern label, split, lambda list, algs)
    ("balanced", None, [2000, 2400],
     ['Roundabout', 'SmartStopPreflash', 'SmartStopPreflashOnly']),
    ("arterial", [0.4, 0.4, 0.1, 0.1], [1600, 2000, 2400],
     ['Roundabout', 'SmartStopReal', 'SmartStopPreflashOnly']),
]


def main():
    rows = []
    t0 = time.time()
    for pat, split, lams, algs in RUNS:
        for lam in lams:
            schedule = make_schedule(lam, 0, split=split)
            for alg in algs:
                res = run_stream(alg, schedule, fair=True)
                vs = res['vehicles']
                served = [v for v in vs if v['served']]
                delays = [v['control_delay'] for v in served]
                rows.append(dict(
                    pattern=pat, lam_vph=lam, algorithm=alg,
                    mean_delay=round(float(np.mean(delays)), 2) if delays else None,
                    served_frac=round(len(served) / len(vs), 4) if vs else None,
                    min_dist_m=(round(res['min_dist'], 2)
                                if res['min_dist'] != float('inf') else ''),
                ))
                print(f"  {pat:>8} λ={lam:>5} {alg:<22}"
                      f"delay={rows[-1]['mean_delay']}s "
                      f"min={rows[-1]['min_dist_m']}m ({time.time()-t0:.0f}s)",
                      flush=True)

    with open("cs_final_runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("Wrote cs_final_runs.csv")


if __name__ == "__main__":
    main()

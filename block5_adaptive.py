#!/usr/bin/env python3
"""
Block 5 (lever 1) — Adaptive Platoon Length
============================================
Block 4 diagnosed Smart Stop's two losing regimes (balanced-heavy,
single-dominant) as service-rate limits, not physics: PLATOON_MAX=4 plus a
full flash-reaction dwell per window head caps any one approach's
throughput. Signals solve the same problem with green-split allocation —
longer greens for heavier movements. This module does the equivalent:

  AdaptivePlatoonSmartStop: the platoon claim limit scales with the
  claiming approach's queue depth, throttled by cross-traffic waiting time
  so a dominant approach cannot starve the minors:

      cross_wait < 12 s  -> serve up to 8   (nobody's hurting; drain the queue)
      cross_wait < 25 s  -> serve up to 4   (Block 3 behavior)
      otherwise          -> serve up to 2   (yield the window soon)

  The claim is a commitment (like a green): once claimed, followers release
  on the normal leader-progress condition regardless of later arrivals.

Benchmarks (this script): the three cells Smart Stop lost or nearly lost —
balanced-heavy, one_heavy (Block 4), and the starvation-probe hot split —
Adaptive vs Block 3 GatedPlatoonSmartStop vs RealisticRoundabout, full
realism on all sides, paired arrival schedules.

Usage:
    python block5_adaptive.py            # full benchmark -> CSV + tables
    python block5_adaptive.py --smoke    # one cell
"""

import csv
import sys
import time

import numpy as np

from block3_reality import GatedPlatoonSmartStop
from capacity_curves import run_stream, make_schedule, ROADS, ALG_MAP
from starvation_probe import make_probe_schedule, VICTIM, DOMINANT

LAM_POINTS = [2000, 2400]   # the volumes where Block 4's losses live
REPS = 1                    # saturated runs are ~3-5 min each; 18 runs total


class AdaptivePlatoonSmartStop(GatedPlatoonSmartStop):
    """Green-split analog: platoon length follows the claiming approach's
    queue depth, with a fairness brake only at extreme cross-traffic wait.

    v1 lesson (smoke test, one_heavy 2,000: 112.2 s ≈ no change): throttling
    window length whenever cross traffic waited >12 s was backwards — at
    saturation SOMEONE is always waiting, so the throttle pinned windows at
    or below the fixed baseline exactly when longer windows were needed.
    Signal theory does the opposite: cycle lengths GROW with saturation
    (fewer switchovers per vehicle served). v2 serves up to the approach's
    actual queue depth (capped), braking only when a cross head has waited
    past CROSS_BRAKE_S — protecting the p95 tail without giving up the
    switchover economics."""

    MIN_WINDOW    = 4      # never below the Block 3 fixed value
    MAX_WINDOW    = 12     # drain cap (a ~35 s green at ~2.9 s discharge)
    CROSS_BRAKE_S = 40.0   # hard fairness brake

    def _platoon_limit(self, leader):
        cross_wait = 0.0
        own_queue = 1
        for v in self.waiting_vehicles:
            if v.road_name == leader.road_name:
                own_queue += 1
            elif v.arrival_time is not None:
                cross_wait = max(cross_wait,
                                 self.current_time - v.arrival_time)
        if cross_wait > self.CROSS_BRAKE_S:
            return self.MIN_WINDOW
        return max(self.MIN_WINDOW, min(self.MAX_WINDOW, own_queue))

    def _claim_followers(self, leader):
        limit = self._platoon_limit(leader)
        old_max, self.PLATOON_MAX = self.PLATOON_MAX, limit
        try:
            super()._claim_followers(leader)   # keeps follower-dwell capping
        finally:
            self.PLATOON_MAX = old_max


class PreflashAdaptiveSmartStop(AdaptivePlatoonSmartStop):
    """Block 5 lever 2 on top of lever 1: pre-flash via minimum-dwell
    hypothesis (a stopped driver can't launch in under ~0.5 s, so the flash
    may be issued while a conflict is still clearing — the reaction time
    absorbs the wait). See DwellRobustDetector.min_candidate_dwell."""

    MIN_CANDIDATE_DWELL = 0.5

    def __init__(self, geometry):
        super().__init__(geometry)
        self.collision_detector.min_candidate_dwell = self.MIN_CANDIDATE_DWELL


ALG_MAP['SmartStopAdaptive'] = AdaptivePlatoonSmartStop
ALG_MAP['SmartStopPreflash'] = PreflashAdaptiveSmartStop

PATTERNS = {
    # (schedule builder, kwargs) — paired schedules across algorithms
    'balanced':  ('capacity', dict(split=None)),
    'one_heavy': ('capacity', dict(split=[0.55, 0.15, 0.15, 0.15])),
    'hot_split': ('probe',    dict(mode='poisson')),   # starvation-probe split
}
ALGS = ['Roundabout', 'SmartStopReal', 'SmartStopAdaptive', 'SmartStopPreflash']


def main():
    smoke = "--smoke" in sys.argv
    lam_points = [2000] if smoke else LAM_POINTS
    patterns = ['one_heavy'] if smoke else list(PATTERNS)
    reps = 1 if smoke else REPS

    rows = []
    t0 = time.time()
    for pat in patterns:
        kind, kw = PATTERNS[pat]
        for lam in lam_points:
            for rep in range(reps):
                if kind == 'probe':
                    schedule = make_probe_schedule(lam, rep, kw['mode'])
                else:
                    schedule = make_schedule(lam, rep, split=kw['split'])
                for alg in ALGS:
                    res = run_stream(alg, schedule, fair=True)
                    vs = res['vehicles']
                    served = [v for v in vs if v['served']]
                    delays = [v['control_delay'] for v in served]
                    # Worst-approach p95 (fairness signature)
                    worst_p95 = 0.0
                    for road in ROADS:
                        rd = [v['control_delay'] for v in served
                              if v['road'] == road]
                        if rd:
                            worst_p95 = max(worst_p95,
                                            float(np.percentile(rd, 95)))
                    rows.append(dict(
                        pattern=pat, lam_vph=lam, rep=rep, algorithm=alg,
                        overall=round(float(np.mean(delays)), 2) if delays else None,
                        worst_p95=round(worst_p95, 2),
                        served_frac=round(len(served) / len(vs), 4) if vs else None,
                        min_dist_m=(round(res['min_dist'], 2)
                                    if res['min_dist'] != float('inf') else ''),
                        min_samepath_m=(round(res['min_samepath'], 2)
                                        if res['min_samepath'] != float('inf')
                                        else ''),
                    ))
                    print(f"  {pat:>9} λ={lam:>5} rep {rep} {alg:<18}"
                          f"({time.time()-t0:.0f}s)", flush=True)

    out = "block5_adaptive_smoke.csv" if smoke else "block5_adaptive.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {out}")

    def cell(pat, lam, alg, field):
        vals = [r[field] for r in rows
                if r['pattern'] == pat and r['lam_vph'] == lam
                and r['algorithm'] == alg and r[field] not in (None, '')]
        return float(np.mean(vals)) if vals else None

    print("\n" + "=" * 92)
    print("BLOCK 5 — ADAPTIVE PLATOON LENGTH (mean delay s | worst-approach p95 | served)")
    print("=" * 92)
    for pat in patterns:
        print(f"\nPATTERN: {pat}")
        hdr = f"{'λ':>6} |" + "".join(f" {a:>28} |" for a in ALGS)
        print(hdr); print("-" * len(hdr))
        for lam in lam_points:
            cells = []
            for alg in ALGS:
                o = cell(pat, lam, alg, 'overall')
                p = cell(pat, lam, alg, 'worst_p95')
                s = cell(pat, lam, alg, 'served_frac')
                cells.append(f"{o:7.1f}s p95 {p:6.1f} {s*100:4.0f}%"
                             if o is not None else " " * 27)
            print(f"{lam:>6} |" + " |".join(f" {c:>28}" for c in cells) + " |")
    mins = [r['min_dist_m'] for r in rows
            if r['algorithm'] == 'SmartStopAdaptive' and r['min_dist_m'] != '']
    sp = [r['min_samepath_m'] for r in rows
          if r['algorithm'] == 'SmartStopAdaptive' and r['min_samepath_m'] != '']
    if mins:
        print(f"\nSmartStopAdaptive min cross-path {min(mins):.2f} m; "
              f"min same-path arc gap {min(sp):.2f} m" if sp else "")
    print("=" * 92)


if __name__ == "__main__":
    main()

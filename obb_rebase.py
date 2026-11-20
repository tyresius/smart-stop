#!/usr/bin/env python3
"""
OBB re-base, first cut — physically-grounded safety margin
===========================================================
(Audit finding 1, step 3, 2026-09-29.) The 3.5 m center margin lets perpendicular
crossings physically overlap (43% real broadside conflicts for full Smart Stop).
Bump the margin to 4.596 m = 3.25*sqrt(2), the center-distance that GUARANTEES no
4.5x2.0 box overlap in any orientation, and measure:
  (A) does the real (paths-cross) overlap rate collapse to ~0?
  (B) what does it cost in clearance time (the throughput proxy)?

This is a conservative first cut — a true oriented-bounding-box decision check
would block strictly less (only actual overlaps, not all diagonal-possible
approaches), so this OVER-states the throughput cost. It bounds the damage.

Usage:  python obb_rebase.py [--smoke]
"""
import sys

import numpy as np

from path_based_smart_stop import PathBasedSmartStopAlgorithm, SmartStopSafeAlgorithm
from reality_sweeps import generate_scenarios, run_scenario
from obb_classify import run_classify

OBB_MARGIN = 4.596


class SmartStopOBB(PathBasedSmartStopAlgorithm):
    SAFETY_MARGIN = OBB_MARGIN


class SmartSafeOBB(SmartStopSafeAlgorithm):
    SAFETY_MARGIN = OBB_MARGIN


def main():
    smoke = "--smoke" in sys.argv
    scen = [s for s in generate_scenarios() if len(s) in (2, 3, 4)]
    scen = scen[::7] if not smoke else scen[::40]
    print(f"OBB re-base (margin {OBB_MARGIN} m) over {len(scen)} scenarios\n")

    variants = [
        ('Smart Stop (3.5 m)', PathBasedSmartStopAlgorithm),
        ('Smart Stop OBB (4.6 m)', SmartStopOBB),
        ('Smart Safe (4.0 m)', SmartStopSafeAlgorithm),
        ('Smart Safe OBB (4.6 m)', SmartSafeOBB),
    ]
    print(f"{'controller':<24} | {'real overlap':>12} | {'mean clearance':>14} | {'vs base':>8}")
    print("-" * 68)
    base_clear = {}
    for label, Ctl in variants:
        n = real = 0
        clears = []
        for s in scen:
            cfg = [(r, sig, o) for r, sig, o in s]
            _, r, _ = run_classify(cfg, Ctl)
            n += 1; real += r
            tt, ok, _ = run_scenario(Ctl, cfg, 1, fair=True)
            if ok:
                clears.append(tt)
        mc = float(np.mean(clears)) if clears else float('nan')
        base_key = 'stop' if 'Stop' in label else 'safe'
        if 'OBB' not in label:
            base_clear[base_key] = mc
            delta = '—'
        else:
            b = base_clear.get(base_key)
            delta = f"{(mc-b)/b*100:+.0f}%" if b else '?'
        print(f"{label:<24} | {real:>4}/{n} ({real/n*100:>3.0f}%) | "
              f"{mc:>12.1f}s | {delta:>8}")
    print(f"\nRead: does OBB margin drive the real (paths-cross) overlap rate to ~0,")
    print(f"and at what clearance-time cost? (Conservative upper bound on the cost.)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Streaming cost of the motion-confirmed-intent defense
======================================================
(2026-07-21.) The discrete suite showed `ConfirmedSmartStop` closes the
false-signal vulnerability at +45.7% clearance — but discrete clearance is the
harshest metric. This measures the cost on the STREAMING regime cells that
produce the deck's headline numbers, so the adopt/pivot decision has real
regime deltas.

`SmartStopConfirmed` = the mature streaming controller (GatedPlatoonSmartStop)
with the motion-confirmed-intent mixin. Compared head-to-head against
`SmartStopReal` on paired arrival schedules (honest traffic — the cost of the
defense on normal drivers, independent of any attack).

Usage:  python confirmed_streaming.py [--smoke]
"""

import sys
import time

import numpy as np

from motion_confirmed_intent import MotionConfirmedMixin
from block3_reality import GatedPlatoonSmartStop
from capacity_curves import run_stream, make_schedule, ALG_MAP, ROADS


class ConfirmedGatedSmartStop(MotionConfirmedMixin, GatedPlatoonSmartStop):
    """Mature streaming Smart Stop + motion-confirmed intent."""
    pass


ALG_MAP['SmartStopConfirmed'] = ConfirmedGatedSmartStop

# (label, lambda, split) — the deck's regime operating points.
CELLS = [
    ('light',    1000, None),
    ('arterial', 2000, [0.40, 0.40, 0.10, 0.10]),
    ('arterial', 2400, [0.40, 0.40, 0.10, 0.10]),
    ('balanced', 2400, None),
    ('dominant', 2400, [0.55, 0.15, 0.15, 0.15]),
]
BASE, DEF = 'SmartStopReal', 'SmartStopConfirmed'


def measure(alg, schedule):
    res = run_stream(alg, schedule, fair=True)
    vs = res['vehicles']
    served = [v for v in vs if v['served']]
    d = [v['control_delay'] for v in served]
    return dict(mean=round(float(np.mean(d)), 2) if d else None,
                served=round(len(served) / len(vs), 4) if vs else None,
                min_dist=(round(res['min_dist'], 2)
                          if res['min_dist'] != float('inf') else None))


def main():
    smoke = "--smoke" in sys.argv
    cells = CELLS[1:2] if smoke else CELLS

    rows = []
    t0 = time.time()
    for label, lam, split in cells:
        schedule = make_schedule(lam, 0, split=split)
        b = measure(BASE, schedule)
        d = measure(DEF, schedule)
        delta = ((d['mean'] - b['mean']) / b['mean'] * 100
                 if b['mean'] and d['mean'] else None)
        rows.append(dict(label=label, lam=lam, base=b, deff=d, delta=delta))
        print(f"  {label:>9} λ={lam}: base {b['mean']}s  confirmed {d['mean']}s  "
              f"({delta:+.0f}%)  floors {b['min_dist']}/{d['min_dist']} m  "
              f"({time.time()-t0:.0f}s)", flush=True)

    print("\n" + "=" * 80)
    print("STREAMING COST OF MOTION-CONFIRMED INTENT — SmartStopConfirmed vs SmartStopReal")
    print("=" * 80)
    print(f"{'cell':>18} | {'baseline':>10} | {'confirmed':>10} | {'delay Δ':>8} | "
          f"{'min-dist (b/c)':>16}")
    print("-" * 80)
    for r in rows:
        b, d = r['base'], r['deff']
        print(f"{r['label']+' '+str(r['lam']):>18} | {b['mean']:>9.1f}s | "
              f"{d['mean']:>9.1f}s | {r['delta']:>+7.0f}% | "
              f"{b['min_dist']}/{d['min_dist']} m")
    print("=" * 80)
    worst = max((r['delta'] for r in rows if r['delta'] is not None), default=0)
    print(f"Worst-case regime delay increase: {worst:+.0f}%   "
          f"(discrete-clearance cost was +45.7% — regime cost is the real number)")


if __name__ == "__main__":
    main()

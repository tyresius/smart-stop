#!/usr/bin/env python3
"""
Smart Safe (streaming) vs the roundabout — the survival gate
=============================================================
(2026-07-21.) Smart Safe is deception-resistant (step 1: 0/516 breaches). The
project's floor is that it must at least reach parity with a fairly-modeled
roundabout. This runs a STREAMING adaptation of Smart Safe's principle —
a declared STRAIGHT is treated as a worst-case LEFT (never trusted to be
non-crossing); R and L unchanged — head-to-head with the roundabout across
the regime cells, honest traffic. SmartStopReal (full, trusting) is shown as
the fast end of the spectrum you slide toward as the real cheat rate drops.

Not cheating in either direction: Smart Safe's physical paths are unchanged
(cars drive their true movement); only the controller's SAFETY assumption is
conservative. Faithful to the discrete Smart Safe semantic, adapted to the
platoon controller.

Usage:  python safe_vs_roundabout.py [--smoke]
"""
import sys
import time

import numpy as np

from block3_reality import GatedPlatoonSmartStop
from capacity_curves import run_stream, make_schedule, ALG_MAP


class SafeGatedSmartStop(GatedPlatoonSmartStop):
    """Streaming Smart Safe: a declared straight (NS/S) is treated by the
    controller as a worst-case left. Physical path unchanged (built before
    this relabel); only the controller's view is conservative."""
    def add_vehicle(self, vehicle):
        if getattr(vehicle, 'signal', None) == "NS/S":
            vehicle.signal = "L"
        super().add_vehicle(vehicle)


ALG_MAP['SmartSafeStream'] = SafeGatedSmartStop

CELLS = [
    ('light',    1000, None),
    ('arterial', 2000, [0.40, 0.40, 0.10, 0.10]),
    ('balanced', 2400, None),
    ('dominant', 2400, [0.55, 0.15, 0.15, 0.15]),
]
ALGS = [('Smart Safe', 'SmartSafeStream'),
        ('full Smart Stop', 'SmartStopReal'),
        ('Roundabout', 'Roundabout')]


def measure(name, sched):
    res = run_stream(name, sched, fair=True)
    served = [v for v in res['vehicles'] if v['served']]
    d = [v['control_delay'] for v in served]
    return (round(float(np.mean(d)), 1) if d else None,
            round(len(served) / len(res['vehicles']) * 100, 1) if res['vehicles'] else None)


def main():
    smoke = "--smoke" in sys.argv
    cells = CELLS[1:2] if smoke else CELLS
    t0 = time.time()

    rows = []
    for label, lam, split in cells:
        sched = make_schedule(lam, 0, split=split)
        cell = {'cell': f'{label} {lam}'}
        for aname, akey in ALGS:
            mean, sf = measure(akey, sched)
            cell[aname] = mean
            cell[aname + '_sf'] = sf
            print(f"  {label:>9} {lam} {aname:<16}: {mean}s (served {sf}%)  "
                  f"({time.time()-t0:.0f}s)", flush=True)
        rows.append(cell)

    print("\n" + "=" * 78)
    print("SMART SAFE vs ROUNDABOUT (streaming, honest traffic) — the survival gate")
    print("=" * 78)
    print(f"{'cell':>15} | {'Smart Safe':>11} | {'full SmartStop':>14} | "
          f"{'Roundabout':>11} | {'Safe vs RB':>11}")
    print("-" * 78)
    for r in rows:
        safe, full, rb = r['Smart Safe'], r['full Smart Stop'], r['Roundabout']
        verdict = ('Safe WINS' if safe < rb else
                   'parity' if abs(safe - rb) / rb < 0.10 else 'Safe loses')
        print(f"{r['cell']:>15} | {safe:>10.1f}s | {full:>13.1f}s | "
              f"{rb:>10.1f}s | {verdict:>11}")
    print("=" * 78)
    wins = sum(1 for r in rows if r['Smart Safe'] <= r['Roundabout'] * 1.10)
    print(f"Smart Safe at parity-or-better with the roundabout in "
          f"{wins}/{len(rows)} regime cells.")


if __name__ == "__main__":
    main()

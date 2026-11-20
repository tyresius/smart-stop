#!/usr/bin/env python3
"""
Block 7 — Jumper Response: closing the compliance hazard
=========================================================
Block 6 found flash-jumpers ≥5% produce collisions (0.02 m) — with two
deliberate omissions this module now supplies:

  1. EvasiveVehicle (block3_reality): reactive human braking — the
     less-committed vehicle in any predicted cross-path conflict brakes to
     a stop. Applies to everyone: jumpers, victims, normal traffic.
  2. ResponseSmartStop: the controller-side hold — any active vehicle the
     controller did not itself flash (detected at step start as an unknown
     active, exactly what the camera would report) freezes ALL new flashes
     and pending platoon releases for HOLD_S. Authorized traffic already
     in motion continues (protected by evasive braking).

Sweep: identical to Block 6 (q ∈ {0, 5%, 10%}, patience U(8,20) s,
λ ∈ {1,200, 2,000}) so the before/after is paired.

Usage:  python block7_response.py [--smoke]
"""

import csv
import sys
import time

import numpy as np

from block5_adaptive import PreflashAdaptiveSmartStop
from capacity_curves import run_stream, make_schedule, ALG_MAP

Q_LEVELS = [0.0, 0.05, 0.10]
PATIENCE = (8.0, 20.0)
LAMBDAS  = [1200, 2000]
REPS     = 2
MARGIN_M = 3.3


class ResponseSmartStop(PreflashAdaptiveSmartStop):
    """Mature controller + unauthorized-motion response: unknown actives
    (jumpers) trigger a flash hold; evasive vehicles handle the physics."""

    USE_EVASIVE = True
    HOLD_S = 2.0

    def __init__(self, geometry):
        super().__init__(geometry)
        self._known_ids = set()
        self._hold_until = -1.0

    def step(self, dt: float = 0.1):
        # Camera check: any active vehicle we didn't flash is a jumper.
        for v in self.active_vehicles:
            if id(v) not in self._known_ids:
                self._hold_until = max(self._hold_until,
                                       self.current_time + self.HOLD_S)
                self._known_ids.add(id(v))
        result = super().step(dt)
        for v in self.active_vehicles:
            self._known_ids.add(id(v))
        return result

    def _release_followers(self):
        if self.current_time < self._hold_until:
            return
        super()._release_followers()

    def _coordinate_smart_movements(self):
        if self.current_time < self._hold_until:
            return
        super()._coordinate_smart_movements()


ALG_MAP['SmartStopResponse'] = ResponseSmartStop


def main():
    smoke = "--smoke" in sys.argv
    lams = [2000] if smoke else LAMBDAS
    qs = [0.10] if smoke else Q_LEVELS
    reps = 1 if smoke else REPS

    rows = []
    t0 = time.time()
    for lam in lams:
        for rep in range(reps):
            schedule = make_schedule(lam, rep)
            for q in qs:
                jk = None if q == 0.0 else (q, *PATIENCE)
                res = run_stream('SmartStopResponse', schedule, fair=True,
                                 jumpers=jk)
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
                      f"delay={rows[-1]['mean_delay']} s, "
                      f"served={rows[-1]['served_frac']} "
                      f"({time.time()-t0:.0f}s)", flush=True)

    out = "block7_response_smoke.csv" if smoke else "block7_response.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {out}")

    print("\n" + "=" * 72)
    print("JUMPER RESPONSE — evasive braking + flash hold (vs Block 6 raw)")
    print("=" * 72)
    print(f"{'λ':>6} | {'q':>5} | {'jumps':>5} | {'mean delay':>10} | "
          f"{'min dist':>8} | {'served':>6} | {'verdict':>8}")
    for lam in lams:
        for q in qs:
            sel = [r for r in rows if r['lam_vph'] == lam and r['q'] == q]
            if not sel:
                continue
            d = float(np.mean([r['mean_delay'] for r in sel
                               if r['mean_delay'] is not None]))
            m = min(float(r['min_dist_m']) for r in sel if r['min_dist_m'] != '')
            s = float(np.mean([r['served_frac'] for r in sel]))
            nj = int(np.sum([r['n_jumps'] for r in sel]))
            verdict = "SAFE" if m >= MARGIN_M else "VIOLATED"
            print(f"{lam:>6} | {q:>5.0%} | {nj:>5} | {d:>9.1f}s | "
                  f"{m:>7.2f}m | {s*100:>5.0f}% | {verdict:>8}")
    print("=" * 72)


if __name__ == "__main__":
    main()

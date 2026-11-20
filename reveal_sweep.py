#!/usr/bin/env python3
"""
Reveal-distance sweep — the deciding experiment for false-signal defense
=========================================================================
(2026-07-21.) The universal motion-confirmed controller closes the
false-signal hole but costs +242% on the arterial because it confirms intent
only after REVEAL_M = 4.0 m of travel (deep toward the center). Safety holds
at ANY reveal distance (before reveal all intent hypotheses are checked); the
open question is THROUGHPUT: how short can the reveal be — how early does a
left-turner's heading betray it — and does the arterial cost collapse there?

Part A (safety, discrete, fast): false R/L across a scenario subset at each
reveal distance — floor must stay >= ~3.46 m (honest baseline).
Part B (throughput, streaming, slow): arterial 40/40/10/10 @ 2,000 at each
reveal distance vs the trusting baseline (56.9 s) and the reveal=4.0 result
(194.6 s = +242%).

A short reveal that keeps the floor AND recovers most of the throughput =
the project survives (pending: can a camera actually confirm heading that
early — a vision-phase question). If throughput stays wrecked even at the
shortest physically-plausible reveal, the single-lane case doesn't survive.

Usage:  python reveal_sweep.py [--smoke]
"""

import sys
import time

import numpy as np

from reality_sweeps import PerceptionDetector, make_phantoms, generate_scenarios
from path_based_smart_stop import PathBasedSmartStopAlgorithm
from block3_reality import GatedPlatoonSmartStop
from capacity_curves import run_stream, make_schedule, ALG_MAP
from adversarial_intent import run_adv, MARGIN_M

REVEALS = [1.0, 2.0]        # 4.0 already measured (+242%); 0 = trust baseline
ARTERIAL = dict(lam=2000, split=[0.40, 0.40, 0.10, 0.10])


class RevealDetector(PerceptionDetector):
    """PerceptionDetector with a configurable reveal distance (how far a
    vehicle must travel before its true path is treated as confirmed)."""
    def __init__(self, inner, variant_map, reveal_m):
        super().__init__(inner, variant_map)
        self.reveal_m = reveal_m

    def _variants(self, v):
        phantoms = self.variant_map.get(id(v))
        if not phantoms:
            return [v]
        if v.active and v.current_position_meters > self.reveal_m:
            true_ph = [p for p in phantoms if p.signal == v.true_signal]
            phantoms = true_ph or phantoms
        for p in phantoms:
            p.active = v.active
            p.completed = v.completed
            p.current_position_meters = v.current_position_meters
            p.state.velocity = v.state.velocity
        return phantoms


def make_reveal_controller(base, reveal_m):
    class _Confirmed(base):
        def __init__(self, geometry):
            super().__init__(geometry)
            self._mci = {}
            self.collision_detector = RevealDetector(
                self.collision_detector, self._mci, reveal_m)

        def add_vehicle(self, vehicle):
            super().add_vehicle(vehicle)
            if getattr(vehicle, 'true_signal', None) is not None:
                self._mci[id(vehicle)] = make_phantoms(
                    vehicle.road_name, vehicle.order, self.geometry)
    return _Confirmed


def main():
    smoke = "--smoke" in sys.argv
    reveals = [1.0] if smoke else REVEALS
    t0 = time.time()

    # ── Part A: safety at each reveal (discrete, fast) ──────────────────────
    scen = [s for s in generate_scenarios() if len(s) in (2, 3)
            and any(sig == 'R' for _, sig, _ in s)]
    scen = scen[:60] if smoke else scen[::4]   # subset for speed
    print(f"Part A — safety, {len(scen)} adversarial scenarios per reveal")
    safety = {}
    for R in reveals:
        Ctl = make_reveal_controller(PathBasedSmartStopAlgorithm, R)
        floor = float('inf')
        for s in scen:
            adv, flipped = [], False
            for road, sig, order in s:
                if sig == 'R' and not flipped:
                    adv.append((road, 'L', order, 'R')); flipped = True
                else:
                    adv.append((road, sig, order, sig))
            _, _, md = run_adv(adv, 'trusting', Ctl)
            floor = min(floor, md)
        safety[R] = floor
        print(f"  reveal {R} m: floor {floor:.2f} m  "
              f"({'SAFE' if floor >= 3.4 else 'BREACH'})  ({time.time()-t0:.0f}s)",
              flush=True)

    # ── Part B: arterial throughput at each reveal (streaming, slow) ────────
    print("\nPart B — arterial 40/40/10/10 @ 2,000 throughput per reveal")
    sched = make_schedule(ARTERIAL['lam'], 0, split=ARTERIAL['split'])
    base = run_stream('SmartStopReal', sched, fair=True)
    b_served = [v for v in base['vehicles'] if v['served']]
    b_mean = round(float(np.mean([v['control_delay'] for v in b_served])), 2)
    print(f"  baseline SmartStopReal (trust): {b_mean}s  "
          f"floor {round(base['min_dist'],2)}m  ({time.time()-t0:.0f}s)",
          flush=True)
    tput = {}
    for R in reveals:
        name = f'ConfR{R}'
        ALG_MAP[name] = make_reveal_controller(GatedPlatoonSmartStop, R)
        res = run_stream(name, sched, fair=True)
        served = [v for v in res['vehicles'] if v['served']]
        mean = round(float(np.mean([v['control_delay'] for v in served])), 2)
        delta = (mean - b_mean) / b_mean * 100
        tput[R] = (mean, round(res['min_dist'], 2), delta)
        print(f"  reveal {R} m: {mean}s ({delta:+.0f}%)  "
              f"floor {round(res['min_dist'],2)}m  ({time.time()-t0:.0f}s)",
              flush=True)

    print("\n" + "=" * 72)
    print("DECIDING EXPERIMENT — reveal distance vs safety & arterial throughput")
    print("=" * 72)
    print(f"{'reveal':>8} | {'disc. floor':>11} | {'arterial delay':>14} | {'vs trust':>9}")
    print("-" * 72)
    print(f"{'0 (trust)':>8} | {'2.56 (vuln)':>11} | {b_mean:>13.1f}s | {'—':>9}")
    for R in reveals:
        mean, floor, delta = tput[R]
        print(f"{R:>7}m | {safety[R]:>9.2f} m | {mean:>13.1f}s | {delta:>+8.0f}%")
    print(f"{'4.0 m':>8} | {'3.48 (safe)':>11} | {'194.6s':>14} | {'+242%':>9}")
    print("=" * 72)


if __name__ == "__main__":
    main()

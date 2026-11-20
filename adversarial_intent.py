#!/usr/bin/env python3
"""
Adversarial / mistaken intent — does a false turn signal break safety?
=======================================================================
(2026-07-21, prompted by Patrick.) The sim models UNREADABLE intent
(worst-case phantoms) but not DECEPTIVE intent: a driver who signals one
movement and performs another. Worst case: signal "R" (the trusted,
low-conflict co-activation) then turn "L" (maximum conflict). The
co-activation controller currently trusts the declared signal — so this is
an unmodeled attack surface. This experiment measures the exposure and tests
a motion-confirmed-intent defense.

Model of a false-signaler (faithful to the code): built as
RealityVehicle(road, TRUE_signal="L", order, observed_signal="R") — it
physically drives the LEFT path, but every controller lookup (rule
selection, EXIT_ARM co-activation, priority) sees "R".

Three conditions per scenario (all curvature-fair physics):
  1. honest      — signals are truthful (baseline; margins should hold).
  2. trusting     — the R-declarer actually turns L; controller as-is (no
                    phantom net for signaled cars = today's deployed
                    behavior). Does the EXIT_ARM co-activation shortcut on
                    the declared "R" bypass the true "L" conflict?
  3. confirmed    — same deception, but EVERY vehicle gets the
                    phantom/REVEAL_M net (PerceptionDetector): intent is a
                    hypothesis confirmed by motion, never trusted on
                    declaration. Expect safe; measure the throughput cost.

Metric: realized min cross-path distance (safety) + clearance time
(throughput). A cell is a VIOLATION if min-dist < 3.5 m (the design margin).

Usage:  python adversarial_intent.py [--smoke]
"""

import math
import sys
import time

import numpy as np

from config import METERS_PER_UNIT
from path_based_smart_stop import FourWayGeometry, PathBasedSmartStopAlgorithm
from reality_sweeps import (
    RealityVehicle, PerceptionDetector, make_phantoms,
    FAIR_CAP_4WAY, generate_scenarios, MAX_STEPS, DT,
)

MARGIN_M = 3.5


def run_adv(configs, mode, AlgClass=PathBasedSmartStopAlgorithm):
    """configs: list of (road, true_signal, order, declared_signal).
    declared_signal == true_signal for honest cars; differs for a false-
    signaler. mode in {honest, trusting, confirmed}. AlgClass lets a
    self-defending controller (motion_confirmed_intent.ConfirmedSmartStop) be
    tested WITHOUT the harness-side phantom net (mode='trusting'), proving the
    defense is in the controller, not bolted on by the test."""
    geometry = FourWayGeometry()
    alg = AlgClass(geometry)
    variant_map = {}
    for road, true_sig, order, declared in configs:
        obs = None if declared == true_sig else declared
        v = RealityVehicle(road, true_sig, order, geometry,
                           observed_signal=obs)
        v.INTERSECTION_SPEED = FAIR_CAP_4WAY[true_sig]   # physics on TRUE path
        alg.add_vehicle(v)
        if mode == 'confirmed':
            variant_map[id(v)] = make_phantoms(road, order, geometry)
    if variant_map:
        alg.collision_detector = PerceptionDetector(alg.collision_detector,
                                                    variant_map)

    n = len(configs)
    min_dist = float('inf')
    for _ in range(MAX_STEPS):
        status = alg.step(DT)
        moving = [v for v in getattr(alg, 'active_vehicles', []) if v.active]
        for i in range(len(moving)):
            for j in range(i + 1, len(moving)):
                a, b = moving[i], moving[j]
                d = math.hypot(a.state.x - b.state.x,
                               a.state.y - b.state.y) * METERS_PER_UNIT
                if d < min_dist:
                    min_dist = d
        if status['waiting'] == 0 and status['active'] == 0:
            break
    m = alg.get_metrics()
    completed = m.get('completed_vehicles', 0) == n
    return round(m.get('total_time', 0.0), 2), completed, min_dist


def main():
    smoke = "--smoke" in sys.argv
    # All 2- and 3-car scenarios that contain at least one R-declarer (the
    # cars that can become the worst-case false-signaler). 2-car pairs are the
    # cleanest pairwise safety probe.
    scen = [s for s in generate_scenarios() if len(s) in (2, 3)]
    scen = [s for s in scen if any(sig == 'R' for _, sig, _ in s)]
    if smoke:
        scen = scen[:40]
    print(f"Adversarial-intent sweep: {len(scen)} scenarios with an R-declarer")

    rows = []
    t0 = time.time()
    for sid, s in enumerate(scen):
        # honest: declared == true
        honest_cfg = [(road, sig, order, sig) for road, sig, order in s]
        # deception: FIRST R-declarer actually turns L, still declares R
        adv_cfg, flipped = [], False
        for road, sig, order in s:
            if sig == 'R' and not flipped:
                adv_cfg.append((road, 'L', order, 'R'))   # true L, declared R
                flipped = True
            else:
                adv_cfg.append((road, sig, order, sig))

        h_t, h_ok, h_md = run_adv(honest_cfg, 'honest')
        t_t, t_ok, t_md = run_adv(adv_cfg, 'trusting')
        c_t, c_ok, c_md = run_adv(adv_cfg, 'confirmed')
        rows.append(dict(sid=sid, ncar=len(s),
                         honest_md=h_md, honest_t=h_t,
                         trust_md=t_md, trust_t=t_t, trust_ok=t_ok,
                         conf_md=c_md, conf_t=c_t, conf_ok=c_ok))
        if (sid + 1) % 50 == 0:
            print(f"  [{sid+1}/{len(scen)}] {time.time()-t0:.0f}s", flush=True)

    import csv
    with open("adversarial_intent.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    def floor(key):
        vals = [r[key] for r in rows if r[key] != float('inf')]
        return min(vals) if vals else float('inf')

    def viol(key):
        return sum(1 for r in rows if r[key] < MARGIN_M)

    n = len(rows)
    print("\n" + "=" * 78)
    print("ADVERSARIAL INTENT — false 'right' that turns 'left'")
    print("=" * 78)
    print(f"scenarios: {n}   (design margin {MARGIN_M} m)")
    print(f"{'condition':<28} | {'min-dist floor':>14} | {'< margin':>16}")
    print("-" * 78)
    print(f"{'1. honest (baseline)':<28} | {floor('honest_md'):>12.2f} m | "
          f"{viol('honest_md'):>4}/{n} ({viol('honest_md')/n*100:.0f}%)")
    print(f"{'2. trusting (current code)':<28} | {floor('trust_md'):>12.2f} m | "
          f"{viol('trust_md'):>4}/{n} ({viol('trust_md')/n*100:.0f}%)")
    print(f"{'3. motion-confirmed defense':<28} | {floor('conf_md'):>12.2f} m | "
          f"{viol('conf_md'):>4}/{n} ({viol('conf_md')/n*100:.0f}%)")
    print("-" * 78)
    # throughput cost of the defense on scenarios where it stayed safe
    safe = [r for r in rows if r['conf_md'] >= MARGIN_M and r['honest_t'] > 0]
    if safe:
        cost = np.mean([(r['conf_t'] - r['honest_t']) / r['honest_t'] * 100
                        for r in safe])
        print(f"defense throughput cost vs honest (clearance): {cost:+.1f}% mean")
    exploited = sum(1 for r in rows
                    if r['trust_md'] < MARGIN_M <= r['conf_md'])
    print(f"scenarios the defense RESCUES (trusting<margin -> confirmed safe): "
          f"{exploited}/{n}")
    hard = sum(1 for r in rows if r['conf_md'] < MARGIN_M)
    print(f"scenarios still < margin even WITH the defense: {hard}/{n}")
    print("=" * 78)


if __name__ == "__main__":
    main()

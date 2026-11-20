#!/usr/bin/env python3
"""
OBB diagnostic — is the 3.5 m center-distance safety metric physically sound?
=============================================================================
(Audit finding 1, 2026-09-29.) The safety observable records center-to-center
distance vs a 3.5 m margin, but vehicles are 4.5 m x 2.0 m. For a perpendicular
crossing, two boxes can OVERLAP at center-distances up to 3.25*sqrt(2)=4.596 m.
So a reported "safe" floor of 3.4-3.99 m may be a physical broadside overlap.

This re-measures the REALIZED minimum oriented-bounding-box (OBB) separation
between cross-path vehicles, using their actual per-step (x, y, heading) —
no prediction, no shapely, no change to any co-activation decision. It answers:
of the events the center-distance metric calls safe, how many are OBB overlaps?

Method: Separating Axis Theorem on the two 4.5x2.0 rectangles. Positive gap =
bumper-to-bumper clearance (m); <= 0 = physical overlap.

Usage:  python obb_diag.py [--smoke]
"""
import math
import sys

import numpy as np

from config import METERS_PER_UNIT
from path_based_smart_stop import (
    FourWayGeometry, PathBasedSmartStopAlgorithm, SmartStopSafeAlgorithm,
    RoundaboutAlgorithm)
from reality_sweeps import RealityVehicle, FAIR_CAP_4WAY, generate_scenarios, MAX_STEPS, DT

L_M, W_M = 4.5, 2.0


def _corners_m(x, y, h):
    """Four corners (metres) of a vehicle centred at grid (x,y), heading h."""
    xm, ym = x * METERS_PER_UNIT, y * METERS_PER_UNIT
    c, s = math.cos(h), math.sin(h)
    hl, hw = L_M / 2, W_M / 2
    return [(xm + dx * c - dy * s, ym + dx * s + dy * c)
            for dx, dy in ((hl, hw), (hl, -hw), (-hl, -hw), (-hl, hw))]


def obb_gap(p1, p2):
    """SAT separation between two convex quads. >0 = clearance (m), <=0 overlap.
    Returns the max positive per-axis gap (a conservative clearance estimate);
    0.0 if the boxes overlap on every axis."""
    best_gap = -float('inf')
    for poly in (p1, p2):
        for i in range(4):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % 4]
            nx, ny = -(y2 - y1), (x2 - x1)
            mag = math.hypot(nx, ny) or 1.0
            nx, ny = nx / mag, ny / mag
            a = [px * nx + py * ny for px, py in p1]
            b = [px * nx + py * ny for px, py in p2]
            gap = max(min(b) - max(a), min(a) - max(b))
            if gap > best_gap:
                best_gap = gap
    return best_gap if best_gap > 0 else 0.0


def run_obb(configs, AlgClass):
    geometry = FourWayGeometry()
    use_rb = AlgClass is RoundaboutAlgorithm
    alg = AlgClass(geometry)
    for road, sig, order in configs:
        v = RealityVehicle(road, sig, order, geometry, use_roundabout_paths=use_rb)
        v.INTERSECTION_SPEED = FAIR_CAP_4WAY[sig] if not use_rb else v.INTERSECTION_SPEED
        alg.add_vehicle(v)

    min_center = float('inf')
    min_obb = float('inf')
    obb_at_center_floor = None
    for _ in range(MAX_STEPS):
        alg.step(DT)
        moving = [v for v in getattr(alg, 'active_vehicles', []) if v.active]
        for i in range(len(moving)):
            for j in range(i + 1, len(moving)):
                a, b = moving[i], moving[j]
                if a.road_name == b.road_name and a.signal == b.signal:
                    continue                               # same track (car-following)
                cd = math.hypot(a.state.x - b.state.x,
                                a.state.y - b.state.y) * METERS_PER_UNIT
                gap = obb_gap(_corners_m(a.state.x, a.state.y, a.state.heading),
                              _corners_m(b.state.x, b.state.y, b.state.heading))
                if cd < min_center:
                    min_center = cd
                    obb_at_center_floor = gap
                if gap < min_obb:
                    min_obb = gap
        if not moving and getattr(alg, 'waiting_vehicles', []) == []:
            break
    return min_center, min_obb, obb_at_center_floor


def main():
    smoke = "--smoke" in sys.argv
    scen = [s for s in generate_scenarios() if len(s) in (2, 3, 4)]
    # stratified-ish subset for speed
    scen = scen[::7] if not smoke else scen[:40]
    print(f"OBB diagnostic over {len(scen)} scenarios "
          f"(overlap = OBB gap <= 0; bumper-safe = gap >= 0.5 m)\n")

    controllers = [('Smart Stop', PathBasedSmartStopAlgorithm),
                   ('Smart Safe', SmartStopSafeAlgorithm),
                   ('Roundabout', RoundaboutAlgorithm)]
    print(f"{'controller':<12} | {'center floor':>12} | {'OBB floor':>10} | "
          f"{'overlaps':>10} | {'< 0.5 m bumper':>14}")
    print("-" * 70)
    for label, Ctl in controllers:
        centers, obbs, overlaps, tight = [], [], 0, 0
        for s in scen:
            cfg = [(r, sig, o) for r, sig, o in s]
            mc, mo, _ = run_obb(cfg, Ctl)
            if mc != float('inf'):
                centers.append(mc)
            if mo != float('inf'):
                obbs.append(mo)
                if mo <= 0.0:
                    overlaps += 1
                if mo < 0.5:
                    tight += 1
        n = len(obbs)
        print(f"{label:<12} | {min(centers):>10.2f} m | {min(obbs):>8.2f} m | "
              f"{overlaps:>4}/{n} ({overlaps/n*100:>3.0f}%) | "
              f"{tight:>4}/{n} ({tight/n*100:>3.0f}%)")
    print("\nRead: 'OBB floor' is the realized bumper-to-bumper clearance (m).")
    print("If Smart Stop/Safe show overlaps where the roundabout does not, the")
    print("center-distance safety metric was masking physical broadside conflicts.")


if __name__ == "__main__":
    main()

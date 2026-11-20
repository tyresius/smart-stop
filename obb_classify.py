#!/usr/bin/env python3
"""
OBB overlap decomposition — real crossing conflicts vs lane-width artifacts
===========================================================================
(Audit finding 1, step 2, 2026-09-29.) `obb_diag.py` showed full Smart Stop's
footprints overlap in ~63% of scenarios. Definitive real-vs-artifact test:
do the two vehicles' CENTERLINE PATHS actually intersect?

  - PATHS CROSS: the two vehicles are aimed through the same point — no lane
    width separates them. A footprint overlap here is a REAL conflict the
    co-activation logic wrongly permitted (or a merge into a shared exit).
  - PATHS DON'T CROSS: the footprints overlap only because the single-lane
    centerline model draws two non-crossing paths close together. Real lane
    width would (likely) separate them — a MODELING ARTIFACT.

For every pair that OBB-overlaps at any step, we test path intersection once.
The "paths-cross overlap" rate is the honest indictment of the controller.

Usage:  python obb_classify.py [--smoke]
"""
import math
import sys

from path_based_smart_stop import (
    FourWayGeometry, PathBasedSmartStopAlgorithm, SmartStopSafeAlgorithm,
    RoundaboutAlgorithm)
from reality_sweeps import RealityVehicle, FAIR_CAP_4WAY, generate_scenarios, MAX_STEPS, DT
from obb_diag import _corners_m, obb_gap


def _ccw(ax, ay, bx, by, cx, cy):
    return (cy - ay) * (bx - ax) - (by - ay) * (cx - ax)


def _seg_cross(p1, p2, p3, p4):
    d1 = _ccw(p3[0], p3[1], p4[0], p4[1], p1[0], p1[1])
    d2 = _ccw(p3[0], p3[1], p4[0], p4[1], p2[0], p2[1])
    d3 = _ccw(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
    d4 = _ccw(p1[0], p1[1], p2[0], p2[1], p4[0], p4[1])
    return (d1 * d2 < 0) and (d3 * d4 < 0)   # proper interior crossing


def paths_cross(a, b, step=2):
    ax, ay = list(a.path_x), list(a.path_y)
    bx, by = list(b.path_x), list(b.path_y)
    for i in range(0, len(ax) - 1, step):
        p1 = (ax[i], ay[i]); p2 = (ax[min(i + step, len(ax) - 1)], ay[min(i + step, len(ay) - 1)])
        for j in range(0, len(bx) - 1, step):
            p3 = (bx[j], by[j]); p4 = (bx[min(j + step, len(bx) - 1)], by[min(j + step, len(by) - 1)])
            if _seg_cross(p1, p2, p3, p4):
                return True
    return False


def run_classify(configs, AlgClass):
    geometry = FourWayGeometry()
    use_rb = AlgClass is RoundaboutAlgorithm
    alg = AlgClass(geometry)
    for road, sig, order in configs:
        v = RealityVehicle(road, sig, order, geometry, use_roundabout_paths=use_rb)
        if not use_rb:
            v.INTERSECTION_SPEED = FAIR_CAP_4WAY[sig]
        alg.add_vehicle(v)

    overlap_pairs = {}      # (id_a,id_b) -> (a,b)  pairs that overlapped
    for _ in range(MAX_STEPS):
        alg.step(DT)
        moving = [v for v in getattr(alg, 'active_vehicles', []) if v.active]
        for i in range(len(moving)):
            for j in range(i + 1, len(moving)):
                a, b = moving[i], moving[j]
                if a.road_name == b.road_name and a.signal == b.signal:
                    continue
                gap = obb_gap(_corners_m(a.state.x, a.state.y, a.state.heading),
                              _corners_m(b.state.x, b.state.y, b.state.heading))
                if gap <= 0.0:
                    key = tuple(sorted((id(a), id(b))))
                    overlap_pairs[key] = (a, b)
        if not moving and getattr(alg, 'waiting_vehicles', []) == []:
            break

    if not overlap_pairs:
        return False, False, False
    real = any(paths_cross(a, b) for a, b in overlap_pairs.values())
    artifact = any(not paths_cross(a, b) for a, b in overlap_pairs.values())
    return True, real, artifact


def main():
    smoke = "--smoke" in sys.argv
    scen = [s for s in generate_scenarios() if len(s) in (2, 3, 4)]
    scen = scen[::7] if not smoke else scen[::40]
    print(f"OBB overlap decomposition (path-intersection test) over {len(scen)} scenarios\n")

    controllers = [('Smart Stop', PathBasedSmartStopAlgorithm),
                   ('Smart Safe', SmartStopSafeAlgorithm),
                   ('Roundabout', RoundaboutAlgorithm)]
    print(f"{'controller':<12} | {'any overlap':>12} | {'PATHS CROSS (real)':>18} | "
          f"{'paths dont (artifact)':>21}")
    print("-" * 74)
    for label, Ctl in controllers:
        n = ov = re = ar = 0
        for s in scen:
            cfg = [(r, sig, o) for r, sig, o in s]
            o, r, a = run_classify(cfg, Ctl)
            n += 1
            ov += o; re += r; ar += a
        print(f"{label:<12} | {ov:>4}/{n} ({ov/n*100:>3.0f}%) | "
              f"{re:>4}/{n} ({re/n*100:>3.0f}%) | {ar:>4}/{n} ({ar/n*100:>3.0f}%)")
    print("\nPATHS CROSS = real conflict (aimed through the same point, no lane")
    print("width saves them). paths-dont = single-lane centerline artifact.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Tests for independent_checker.py (audit 3, 2026-11-11).

Hand-built cases it must catch or pass (crossing, rear-end, mixed-movement
same lane, a 0.05 m near miss, pass-by, between-step contact), then contacts
staged with real simulator vehicles. Run: .venv/bin/python test_independent_checker.py
"""
import math

from independent_checker import (poly_distance, footprint, min_distance_over_step,
                                 ContactMonitor, CAR_L, CAR_W)
from path_based_smart_stop import FourWayGeometry
from reality_sweeps import RealityVehicle, FAIR_CAP_4WAY
from config import METERS_PER_UNIT as MPU


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol


def test_rear_end_overlap():
    # same lane, centres 4.4 m apart on 4.5 m cars -> 0.1 m overlap
    d = poly_distance(footprint(0, 0, 0), footprint(4.4, 0, 0))
    assert close(d, -0.1), d


def test_near_miss_005():
    # side by side, 0.05 m apart
    d = poly_distance(footprint(0, 0, 0), footprint(0, CAR_W + 0.05, 0))
    assert close(d, 0.05), d


def test_pass_by_opposing_lanes():
    # opposing lanes 4.5 m apart, 2.0 m wide cars -> 2.5 m gap
    d = poly_distance(footprint(0, -2.25, 0), footprint(0, 2.25, math.pi))
    assert close(d, 2.5), d


def test_corner_to_corner():
    # B offset so nearest corners are (0.3, 0.4) apart -> 0.5 m
    d = poly_distance(footprint(0, 0, 0), footprint(CAR_L + 0.3, CAR_W + 0.4, 0))
    assert close(d, 0.5), d


def test_crossing_overlap():
    # perpendicular cars crossing at the same point
    assert poly_distance(footprint(0, 0, 0), footprint(0.5, 0.5, math.pi / 2)) < 0


def test_mixed_movement_same_lane():
    # follower going straight, leader 3 m ahead already turned 30 degrees
    assert poly_distance(footprint(0, 0, 0), footprint(3.0, 0.4, math.radians(30))) < 0


def test_between_step_contact():
    # A crosses B entirely within one step; both step instants are clear
    a0, a1 = (-6.0, 0.0, 0.0), (6.0, 0.0, 0.0)
    b = (0.0, 0.0, math.pi / 2)
    assert poly_distance(footprint(*a0), footprint(*b)) > 2.0
    assert poly_distance(footprint(*a1), footprint(*b)) > 2.0
    best, lower = min_distance_over_step(a0, a1, b, b)
    assert best <= 0.0 and lower <= 0.0, (best, lower)


def test_between_step_near_miss_measured():
    # A passes B with 0.3 m lateral gap mid-step; endpoints are far apart
    best, lower = min_distance_over_step((-10, 0, 0), (10, 0, 0),
                                         (0, CAR_W + 0.3, 0), (0, CAR_W + 0.3, 0))
    # best finds the true 0.3 m; `lower` is a guaranteed floor (looser here
    # because A jumps 20 m in one step) and only has to prove no contact
    assert close(best, 0.3, 1e-3) and lower > 0.0, (best, lower)


def test_far_pair_is_clear():
    best, lower = min_distance_over_step((0, 0, 0), (0.6, 0, 0),
                                         (0, 10, 0), (0.6, 10, 0))
    assert best > 7.9 and lower > 0


def _drive(pairs, steps=120, dt=0.1):
    """Step real vehicles (no controller) and feed the monitor."""
    mon = ContactMonitor()
    t = 0.0
    for _ in range(steps):
        t += dt
        for v in pairs:
            v.update(dt)
        mon.observe(t, [(v, (v.state.x * MPU, v.state.y * MPU, v.state.heading),
                         v.active) for v in pairs if not v.completed])
    return mon


def _car(road, sig, order, geo):
    v = RealityVehicle(road, sig, order, geo)
    v.INTERSECTION_SPEED = FAIR_CAP_4WAY[sig]
    v.activate(0.0)
    return v


def test_staged_crossing_collision_caught():
    geo = FourWayGeometry()
    mon = _drive([_car("Main E", "NS/S", 1, geo), _car("Green S", "NS/S", 2, geo)])
    s = mon.summary()['moving-moving']
    assert s['contacts'] >= 1, s


def test_staged_opposing_straights_clear():
    geo = FourWayGeometry()
    mon = _drive([_car("Main E", "NS/S", 1, geo), _car("Main W", "NS/S", 2, geo)])
    s = mon.summary()['moving-moving']
    assert s['contacts'] == 0 and s['min_gap_m'] is not None and s['min_gap_m'] > 2.0, s


def test_staged_same_lane_rear_end_caught():
    # the old observer skipped same-lane same-movement pairs entirely
    geo = FourWayGeometry()
    lead = _car("Main E", "NS/S", 1, geo)
    follow = _car("Main E", "NS/S", 2, geo)
    follow.current_position_meters = 0.0
    lead.current_position_meters = 3.0        # 3 m ahead on a 4.5 m car
    lead._update_position_from_meters()
    mon = _drive([lead, follow], steps=5)
    assert mon.summary()['moving-moving']['contacts'] >= 1


if __name__ == '__main__':
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith('test_') and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)

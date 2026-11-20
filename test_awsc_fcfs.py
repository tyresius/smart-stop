#!/usr/bin/env python3
"""Tests for HumanFourWayFCFS, the rebuilt all-way-stop baseline (audit 3,
2026-11-11). Each test also records how the legacy HumanFourWay behaved, so
the audit findings F1 (priority scoring) and F2 (full-path hold) stay
documented. Run: .venv/bin/python test_awsc_fcfs.py
"""
from path_based_smart_stop import FourWayGeometry
from reality_sweeps import RealityVehicle, FAIR_CAP_4WAY
from cs4_human_baseline import HumanFourWay, HumanFourWayFCFS, conflict_table


def _car(geo, road, sig, order, arrival):
    v = RealityVehicle(road, sig, order, geo)
    v.INTERSECTION_SPEED = FAIR_CAP_4WAY[sig]
    v.arrival_time = arrival
    return v


def _setup(cls, specs, now):
    geo = FourWayGeometry()
    alg = cls(geo)
    alg.current_time = now
    cars = [_car(geo, *s) for s in specs]
    for c in cars:
        alg.add_vehicle(c)
    return alg, cars


def _step_until(alg, cond, max_steps=400):
    for _ in range(max_steps):
        alg.step(0.1)
        if cond():
            return True
    return False


def test_f1_first_come_first_served():
    # The auditor's case: earlier left turn vs later right turn. Legacy
    # released the later right turn and held the left (F1). FCFS releases the
    # left turn; the right turn may join only because the two movements never
    # touch (conflict table = 0).
    specs = [("Main E", "L", 1, 0.0), ("Green N", "R", 2, 1.5)]
    alg, (left, right) = _setup(HumanFourWayFCFS, specs, 1.5)
    alg.step(0.1)
    assert left.active
    if right.active:
        assert conflict_table(alg.MARGIN_M)[(("Main E", "L"), ("Green N", "R"))] == 0.0
    legacy, (l2, r2) = _setup(HumanFourWay, specs, 1.5)
    legacy.step(0.1)
    assert r2.active and not l2.active, "legacy behaviour changed (F1)"


def test_fcfs_with_a_conflicting_later_car():
    # earlier left turn vs later conflicting straight: only the left goes
    specs = [("Main E", "L", 1, 0.0), ("Green N", "NS/S", 2, 1.5)]
    alg, (left, straight) = _setup(HumanFourWayFCFS, specs, 1.5)
    alg.step(0.1)
    assert left.active and not straight.active
    legacy, (l2, s2) = _setup(HumanFourWay, specs, 1.5)
    legacy.step(0.1)
    assert s2.active and not l2.active, "legacy ranks the straight first (F1)"


def test_tie_yields_to_the_right():
    # simultaneous arrivals: eastbound (Main E) yields to northbound (Green S),
    # which is on its right, even though Main E arrived 0.5 s earlier
    specs = [("Main E", "L", 1, 0.0), ("Green S", "L", 2, 0.5)]
    alg, (east, north) = _setup(HumanFourWayFCFS, specs, 0.5)
    alg.step(0.1)
    assert north.active and not east.active


def _follower_case(cls, road2, sig2):
    geo = FourWayGeometry()
    alg = cls(geo)
    lead = _car(geo, "Main E", "NS/S", 1, 0.0)
    alg.add_vehicle(lead)
    alg.step(0.1)
    assert lead.active
    other = _car(geo, road2, sig2, 2, alg.current_time)
    alg.add_vehicle(other)
    assert _step_until(alg, lambda: other.active)
    return lead


def test_f2_same_lane_follower_not_held_for_whole_path():
    lead = _follower_case(HumanFourWayFCFS, "Main E", "NS/S")
    assert 5.5 <= lead.current_position_meters < 6.5, lead.current_position_meters
    assert not lead.completed
    legacy_lead = _follower_case(HumanFourWay, "Main E", "NS/S")
    assert legacy_lead.completed, "legacy behaviour changed (F2)"


def test_cross_traffic_waits_for_conflict_area_not_path_end():
    # the crossing car goes once the eastbound straight has passed its
    # corridor (conflict table), long before the straight finishes its path
    lead = _follower_case(HumanFourWayFCFS, "Green S", "NS/S")
    need = conflict_table(HumanFourWayFCFS.MARGIN_M)[(("Main E", "NS/S"),
                                                      ("Green S", "NS/S"))]
    assert need <= lead.current_position_meters < need + 0.7, \
        (need, lead.current_position_meters)
    assert not lead.completed
    legacy_lead = _follower_case(HumanFourWay, "Green S", "NS/S")
    assert legacy_lead.completed, "legacy held cross traffic for the whole path"


def test_folk_pairing_out_of_turn():
    geo = FourWayGeometry()
    alg = HumanFourWayFCFS(geo)
    east = _car(geo, "Main E", "NS/S", 1, 0.0)
    alg.add_vehicle(east)
    alg.step(0.1)
    holder = _car(geo, "Green N", "L", 2, alg.current_time)        # blocked
    opp = _car(geo, "Main W", "NS/S", 3, alg.current_time + 0.5)   # pairs with east
    alg.add_vehicle(holder)
    alg.add_vehicle(opp)
    alg.current_time += 0.5
    alg.step(0.1)
    assert opp.active and not holder.active


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

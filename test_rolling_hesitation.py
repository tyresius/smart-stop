#!/usr/bin/env python3
"""Tests for the rolling-hesitation switches (2026-11-11).
Run: .venv/bin/python test_rolling_hesitation.py"""
import statistics as st

import capacity_curves as cc
import hesitation_sweep as hs
import block3_reality
from block3_reality import RollingVehicle, DwellRobustDetector, DWELL_HYPOTHESES
from blind_safe_v2 import BlindSafeV2Hes
from path_based_smart_stop import FourWayGeometry
from stopsign_vs_signal import SignalActuated


def _roller(hesitation=None):
    v = RollingVehicle("Main E", "NS/S", 1, FourWayGeometry())
    v.INTERSECTION_SPEED = 6.0
    v.roll_deadline, v.roll_v0 = 0.3, 6.0
    if hesitation is not None:
        v.roll_hesitation = hesitation
    v.activate(0.0)
    return v


def _advance(v, secs):
    for _ in range(int(round(secs / 0.1))):
        v.update(0.1)


def test_legacy_roller_goes_at_once():
    v = _roller()
    _advance(v, 0.5)
    assert v.rolled and 2.4 <= v.current_position_meters <= 3.6, v.current_position_meters


def test_hesitant_roller_crosses_late_at_speed():
    v = _roller(1.0)
    _advance(v, 0.9)
    assert v.rolled and v.current_position_meters == 0.0     # still easing off
    _advance(v, 0.6)
    assert 2.4 <= v.current_position_meters <= 4.2, v.current_position_meters


def _dwell(alg):
    d = alg.collision_detector
    while d is not None and not isinstance(d, DwellRobustDetector):
        d = getattr(d, 'inner', None)
    return d


def test_widening_switch_sets_this_controller_only():
    geo = FourWayGeometry()
    wide = type('W', (BlindSafeV2Hes,), {'H_S': 1.0, 'WIDEN': True})(geo)
    narrow = type('N', (BlindSafeV2Hes,), {'H_S': 1.0, 'WIDEN': False})(geo)
    sig = SignalActuated(geo)
    b = DWELL_HYPOTHESES
    assert _dwell(wide).stop_hyps == (b[0], b[1] + 0.5, b[2] + 1.0)
    assert _dwell(wide).roll_hyps == (0.0, 0.25, 0.5, 0.75, 1.0)
    assert _dwell(narrow).stop_hyps == b and _dwell(narrow).roll_hyps is None
    assert getattr(_dwell(sig), 'roll_hyps', None) is None
    assert getattr(_dwell(sig), 'stop_hyps', None) is None


def _stream(cls_attrs, lam=400):
    cls = type('T', (BlindSafeV2Hes,), cls_attrs)
    cc.ALG_MAP['T_hes'] = cls
    hs.OBBTurnAware.clearance_m = hs.BUFFER
    block3_reality.DWELL_HYPOTHESES = hs.BASE_HYPS
    sched = cc.make_schedule(lam, 0, split=dict(hs.SPLITS)['arterial'])
    return [v for v in cc.run_stream('T_hes', sched, fair=True)['vehicles'] if v['served']]


def test_no_roll_switch_stops_everyone():
    vs = _stream({'H_S': 0.0, 'ALLOW_ROLL': False})
    assert all(v['stopped'] for v in vs)


def test_hesitant_rollers_still_roll_and_cost_more():
    base = _stream({'H_S': 0.0, 'ALLOW_ROLL': True})
    hes = _stream({'H_S': 1.0, 'ALLOW_ROLL': True, 'WIDEN': True})
    assert any(not v['stopped'] for v in hes)
    assert st.mean(v['control_delay_sp'] for v in hes) > st.mean(v['control_delay_sp'] for v in base)


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

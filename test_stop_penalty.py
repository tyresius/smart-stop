#!/usr/bin/env python3
"""Tests for the stop penalty in capacity_curves.run_stream (2026-11-11).
Run: .venv/bin/python test_stop_penalty.py"""
import csv
import statistics as st

import capacity_curves as cc
import hesitation_sweep as hs           # registers HS_Blind / HS_Signal
import cs4_human_baseline                # registers HumanFourWayFCFS  # noqa: F401
import block3_reality


def _legacy_settings():
    hs.OBBTurnAware.clearance_m = hs.BUFFER
    hs.BlindSafe.NO_ROLL = False
    hs.BlindSafe.HESITATION_S = 0.0
    block3_reality.DWELL_HYPOTHESES = hs.BASE_HYPS


def _run(key, lam=400, rep=0, split='arterial'):
    _legacy_settings()
    sched = cc.make_schedule(lam, rep, split=dict(hs.SPLITS)[split])
    return [v for v in cc.run_stream(key, sched, fair=True)['vehicles'] if v['served']]


def test_acceleration_loss_matches_formula():
    for sig in ("NS/S", "L", "R"):
        ff = cc.freeflow_time("Main E", sig, False, True)
        ffr = cc.freeflow_roll_time("Main E", sig, False, True)
        vc = cc.roll_speed(sig, False, True)
        assert ffr < ff
        assert abs((ff - ffr) - vc / (2 * cc.LAUNCH_ACCEL)) < 0.15, (sig, ff, ffr)


def test_legacy_delay_unchanged():
    com = {(r['split'], r['lam'], r['rep'], r['alg']): float(r['mean_delay'])
           for r in csv.DictReader(open('hesitation_sweep.csv'))
           if r['alg'] == 'Signal' or r['hesitation'] == '0.0'}
    for key, alg in (('HS_Signal', 'Signal'), ('HS_Blind', 'Smart Safe (blind)')):
        vs = _run(key)
        got = round(st.mean(v['control_delay'] for v in vs), 2)
        assert abs(got - com[('arterial', '400', '0', alg)]) < 0.01, (alg, got)


def test_all_way_stop_cars_all_stop_and_pay():
    vs = _run('HumanFourWayFCFS')
    assert all(v['stopped'] for v in vs)
    extra = st.mean(v['control_delay_sp'] - v['control_delay'] for v in vs)
    # each stopped car pays roughly its braking + acceleration loss (1.6-3.0 s)
    assert 1.5 < extra < 3.1, extra
    assert all(v['control_delay_hcm'] >= v['control_delay_sp'] for v in vs)


def test_rolling_cars_pay_no_stop_penalty():
    vs = _run('HS_Blind')                  # H = 0: rolling launches allowed
    rolled = [v for v in vs if not v['stopped']]
    stopped = [v for v in vs if v['stopped']]
    assert rolled and stopped
    assert st.mean(v['control_delay_sp'] for v in rolled) < 0.5
    assert st.mean(v['control_delay_sp'] for v in stopped) > 1.5


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

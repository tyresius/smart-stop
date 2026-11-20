#!/usr/bin/env python3
"""Guard: a signal-blind controller must never read a real car's true
movement (audit 3, 2026-11-11).

Traces every read of `.signal` on real vehicles during a short run, ignoring
the controller's hypothesis stand-ins ("phantoms"), and classifies each call
site. Allowed readers: the car generating its own path (physics) and the
measurement code (harness safety observable, OBBWatch, independent checker).
Anything else is a controller using knowledge a camera lacks.

Legacy BlindSafe is expected to show the known leak sites (priority and
grouping, now routed through `_intent_of` / `_same_group`); BlindSafeV2 must
show none. Note: after REVEAL_M every controller reads `true_signal` by
design (a perfect classifier, audit 3 F6) - that is a separate, documented
assumption, not checked here.

Run: .venv/bin/python test_blind_no_truth.py
"""
import collections
import sys

import reality_sweeps
from reality_sweeps import RealityVehicle

ALLOWED = {
    ('path_based_smart_stop.py', '_generate_4way_path'),
    ('path_based_smart_stop.py', '_generate_path'),
    ('path_based_smart_stop.py', '_generate_roundabout_path'),
    ('capacity_curves.py', 'run_stream'),          # harness safety observable
    ('obb_survival_gate.py', 'step'),              # OBBWatch observer
    ('independent_checker.py', '_tag'),
}
LEGACY_LEAKS = {('path_based_smart_stop.py', '_intent_of'),
                ('block2_platoon.py', '_same_group')}

_reads = collections.Counter()


def _get(self):
    if not self.__dict__.get('_phantom', False):
        f = sys._getframe(1)
        _reads[(f.f_code.co_filename.split('/')[-1], f.f_code.co_name)] += 1
    return self.__dict__['_sig']


def _set(self, val):
    self.__dict__['_sig'] = val


def _install():
    RealityVehicle.signal = property(_get, _set)
    import motion_confirmed_intent as mci
    import blind_safe_v2 as v2

    def mark(fn):
        def wrapped(*a, **k):
            ph = fn(*a, **k)
            for p in ph:
                p.__dict__['_phantom'] = True
            return ph
        return wrapped
    mci.make_phantoms = mark(mci.make_phantoms)
    v2.make_phantoms_v2 = mark(v2.make_phantoms_v2)


def _leaks(alg_key):
    import capacity_curves as cc
    import hesitation_sweep as hs
    hs.OBBTurnAware.clearance_m = 1.0
    _reads.clear()
    cc.run_stream(alg_key, cc.make_schedule(600, 0, split=[0.4, 0.4, 0.1, 0.1]),
                  fair=True)
    return {site: n for site, n in _reads.items() if site not in ALLOWED}


def test_legacy_blind_shows_known_leaks():
    leaks = _leaks('HS_Blind')
    assert set(leaks) == LEGACY_LEAKS, leaks


def test_v2_reads_no_true_movement():
    leaks = _leaks('BlindSafeV2')
    assert not leaks, leaks


if __name__ == '__main__':
    _install()
    import blind_safe_v2  # noqa: F401  (registers BlindSafeV2)
    failed = 0
    for name, fn in [('test_legacy_blind_shows_known_leaks', test_legacy_blind_shows_known_leaks),
                     ('test_v2_reads_no_true_movement', test_v2_reads_no_true_movement)]:
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
    print(f"\n{2 - failed}/2 passed")
    raise SystemExit(1 if failed else 0)

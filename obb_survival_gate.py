#!/usr/bin/env python3
"""
OBB survival gate — streaming Smart Safe at the 4.596 m margin vs Roundabout
============================================================================
(Audit finding 1, step 4, 2026-10-01.) obb_rebase.py showed the 4.596 m margin
(= 3.25*sqrt(2), no 4.5x2.0 box overlap in any orientation) drives real
overlaps to 0% in the DISCRETE scenarios at +18% (Safe) clearance cost. Discrete
is not regime. This re-runs the multi-seed survival gate
(multiseed_safe_vs_rb.py: same cells, same seeds/schedules) with:

  Smart Safe 3.5    streaming Smart Safe as previously gated. NOTE: the
                    streaming SafeGatedSmartStop inherits PathBased's 3.5 m
                    margin, NOT the discrete Smart Safe's 4.0 m — so the jump
                    to 4.596 here is larger than the discrete +18% assumed.
  Smart Safe OBB    same controller, radial distance test REPLACED by an
                    oriented-box (SAT) test on predicted poses, footprints
                    inflated by a clearance buffer CLEARANCE_M. (A radial
                    4.596 m margin was tried first and is invalid as a
                    decision rule: opposing lanes are 4.5 m apart, so it
                    forbids parallel opposing straights — which Smart Safe
                    sends to the geometric check because it relabels every
                    declared straight as L. Smoke, arterial seed 0: 158 s,
                    81.7% served vs 52.7 s at 3.5 m.)
  Roundabout        unchanged (as previously gated)
  Roundabout OBB    held to the SAME footprint standard: (1) yield line set
                    back 1.5 m — as-is the entry spur starts at r = 9.3 m vs
                    ring centerline 6.75 m, so a car waiting/launching there
                    overlaps circulating traffic (~1 m; 59 real overlaps,
                    arterial seed 0); (2) entry conflict check = the same
                    OBB test — its 3.5 m radial margin is < a car length, and
                    with (1) alone 26 ring rear-end overlaps remained.

Every controller is wrapped with an OBB watcher that SAT-tests every
non-platoon active pair each step and records distinct overlapping pairs,
split into real (paths cross) vs lane-artifact — so we verify the fix holds in
streaming, and that the roundabout bar itself is physically clean.

Usage:  python obb_survival_gate.py [--smoke] [--workers N]
"""
import csv
import math
import sys
import time
from multiprocessing import Pool

import numpy as np

from config import METERS_PER_UNIT
import capacity_curves as cc
from capacity_curves import run_stream, make_schedule, ALG_MAP
from safe_vs_roundabout import SafeGatedSmartStop, CELLS
from obb_diag import _corners_m, obb_gap
from obb_classify import paths_cross

REPS = 5
OUT = "obb_survival_gate.csv"
PREFILTER_M = 5.0   # half-diagonal sum of two 4.5x2.0 boxes is 4.92 m


class OBBWatch:
    """Mixin: after each step, SAT-test active non-platoon pairs."""

    def _obb_init(self):
        self.obb_pairs = {}          # key -> real(bool)
        self.obb_min_gap = float('inf')

    def step(self, dt=0.1):
        status = super().step(dt)
        if not hasattr(self, 'obb_pairs'):
            self._obb_init()
        mv = [v for v in getattr(self, 'active_vehicles', []) if v.active]
        for i in range(len(mv)):
            a = mv[i]
            for j in range(i + 1, len(mv)):
                b = mv[j]
                if a.road_name == b.road_name and a.signal == b.signal:
                    continue                      # platoon same-track: arc-gap rule
                d = math.hypot(a.state.x - b.state.x,
                               a.state.y - b.state.y) * METERS_PER_UNIT
                if d > PREFILTER_M:
                    continue
                g = obb_gap(_corners_m(a.state.x, a.state.y, a.state.heading),
                            _corners_m(b.state.x, b.state.y, b.state.heading))
                if g < self.obb_min_gap:
                    self.obb_min_gap = g
                if g <= 0.0:
                    key = tuple(sorted((id(a), id(b))))
                    if key not in self.obb_pairs:
                        self.obb_pairs[key] = paths_cross(a, b)
        return status


from turn_aware_collision import TurnAwareCollisionDetector
from path_based_smart_stop import PathBasedVehicle, CollisionDetector
from obb_diag import L_M, W_M

CLEARANCE_M = 1.0           # footprint-to-footprint buffer (m); sweepable
_DIAG_M = math.hypot(L_M, W_M)


# Predicted-pose heading (audit 3, 2026-11-11). 'secant' is the original rule:
# the chord toward the free-kinematics position 0.3 s (or 1.5 s) later, which
# can sit 14-20 degrees off the path on turns and ignores the detector's own
# delay hypotheses. 'tangent' uses the path direction at the predicted point.
# Legacy default keeps committed results reproducible; new runs set 'tangent'.
HEADING_MODE = 'secant'
_PATH_TABLES = {}       # path signature -> (x, y, segment headings)


def _path_tables(v):
    px, py = v.path_x, v.path_y
    key = (len(px), round(float(px[0]), 4), round(float(py[0]), 4),
           round(float(px[-1]), 4), round(float(py[-1]), 4))
    tab = _PATH_TABLES.get(key)
    if tab is None:
        x, y = np.asarray(px, float), np.asarray(py, float)
        # Paths contain duplicate joint points (zero-length segments whose
        # direction is floating-point noise); drop them before taking headings.
        keep = np.concatenate([[True], np.hypot(np.diff(x), np.diff(y)) > 1e-9])
        x, y = x[keep], y[keep]
        tab = (x, y, np.arctan2(np.diff(y), np.diff(x)))
        _PATH_TABLES[key] = tab
    return tab


def _tangent_heading(v, p):
    """Path direction at the path vertex nearest the predicted point p."""
    x, y, hd = _path_tables(v)
    i = int(np.argmin((x - p[0]) ** 2 + (y - p[1]) ** 2))
    return float(hd[min(i, len(hd) - 1)])


def _pred_heading(v, t, p):
    """Heading of the predicted pose: finite difference along the path;
    falls back to the current heading for a vehicle that won't move."""
    if HEADING_MODE == 'tangent' and getattr(v, 'path_x', None) is not None \
            and len(v.path_x) > 1:
        return _tangent_heading(v, p)
    for dt in (0.3, 1.5):
        q = v.get_future_position(t + dt) if hasattr(v, 'get_future_position') else None
        if q and math.hypot(q[0] - p[0], q[1] - p[1]) > 1e-3:
            return math.atan2(q[1] - p[1], q[0] - p[0])
    return v.state.heading


def _box(x, y, h, inflate):
    xm, ym = x * METERS_PER_UNIT, y * METERS_PER_UNIT
    c, s = math.cos(h), math.sin(h)
    hl, hw = (L_M + inflate) / 2, (W_M + inflate) / 2
    return [(xm + dx * c - dy * s, ym + dx * s + dy * c)
            for dx, dy in ((hl, hw), (hl, -hw), (-hl, -hw), (-hl, hw))]


def _obb_conflict(det, v1, v2, time_horizon):
    """Would the predicted footprints, each inflated by clearance_m/2,
    overlap at any sampled time in the horizon?"""
    n = max(det.MIN_SAMPLES, int(time_horizon / det.SAMPLE_INTERVAL_SECONDS) + 1)
    reach = _DIAG_M + det.clearance_m * 1.5
    for t in np.linspace(0, time_horizon, n):
        p1 = det._predict_position(v1, t)
        p2 = det._predict_position(v2, t)
        if not (p1 and p2):
            continue
        if math.hypot(p1[0] - p2[0], p1[1] - p2[1]) * METERS_PER_UNIT >= reach:
            continue
        b1 = _box(p1[0], p1[1], _pred_heading(v1, t, p1), det.clearance_m)
        b2 = _box(p2[0], p2[1], _pred_heading(v2, t, p2), det.clearance_m)
        if obb_gap(b1, b2) <= 0.0:
            return True
    return False


class OBBTurnAware(TurnAwareCollisionDetector):
    """Turn-aware rules unchanged; the geometric fallback (Rule 4) is the
    footprint test instead of 'centers within a radius?'."""
    clearance_m = CLEARANCE_M

    def _check_distance_collision(self, v1, v2, time_horizon, safety_margin=None):
        return _obb_conflict(self, v1, v2, time_horizon)


class OBBPlain(CollisionDetector):
    """Roundabout entry check held to the SAME footprint standard (its
    3.5 m radial margin is < one car length: ring rear-end overlaps)."""
    clearance_m = CLEARANCE_M

    def check_collision(self, v1, v2, time_horizon=3.0):
        if not (v1.active or v2.active):
            return False
        return _obb_conflict(self, v1, v2, time_horizon)


def _innermost(det):
    while hasattr(det, 'inner'):
        det = det.inner
    return det


class SafeOBBCheck(SafeGatedSmartStop):
    def __init__(self, geometry):
        super().__init__(geometry)
        _innermost(self.collision_detector).__class__ = OBBTurnAware


class RoundaboutOBB(ALG_MAP['Roundabout']):
    """Yield line set back (via _YieldPatch at run time) + OBB entry check."""
    def __init__(self, geometry):
        super().__init__(geometry)
        self.collision_detector.__class__ = OBBPlain


YIELD_SETBACK_U = 1.5 / METERS_PER_UNIT
_orig_rb_path = PathBasedVehicle._generate_roundabout_path


def _setback_rb_path(self):
    """Prepend a straight lead-in so the yield point clears the ring lane."""
    xs, ys = _orig_rb_path(self)
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    ux, uy = xs[0] - xs[1], ys[0] - ys[1]
    m = math.hypot(ux, uy)
    ux, uy = ux / m, uy / m
    k = np.linspace(YIELD_SETBACK_U, 0, 12, endpoint=False)
    return (np.concatenate([xs[0] + ux * k, xs]),
            np.concatenate([ys[0] + uy * k, ys]))


class _YieldPatch:
    """Context: roundabout paths with the set-back yield line (process-local;
    free-flow cache cleared so control delay uses the matching path)."""
    def __enter__(self):
        PathBasedVehicle._generate_roundabout_path = _setback_rb_path
        cc._FREEFLOW_CACHE.clear()
        cc._FREEFLOW_ROLL_CACHE.clear()      # stop-penalty reference (2026-11-15)

    def __exit__(self, *a):
        PathBasedVehicle._generate_roundabout_path = _orig_rb_path
        cc._FREEFLOW_CACHE.clear()
        cc._FREEFLOW_ROLL_CACHE.clear()



def _watched(base):
    return type(base.__name__ + 'Watch', (OBBWatch, base), {})


ALG_MAP['W_Safe35'] = _watched(SafeGatedSmartStop)
ALG_MAP['W_SafeOBB'] = _watched(SafeOBBCheck)
ALG_MAP['W_Roundabout'] = _watched(ALG_MAP['Roundabout'])
ALG_MAP['W_RoundaboutOBB'] = _watched(RoundaboutOBB)     # + _YieldPatch
cc.NO_JITTER_ALGS.update({'W_Roundabout', 'W_RoundaboutOBB'})

ALGS = [('Smart Safe 3.5', 'W_Safe35'),
        ('Smart Safe OBB', 'W_SafeOBB'),
        ('Roundabout', 'W_Roundabout'),
        ('Roundabout OBB', 'W_RoundaboutOBB')]

FIELDS = ['cell', 'lam', 'rep', 'alg', 'mean_delay', 'served_pct',
          'obb_real', 'obb_artifact', 'obb_min_gap_m', 'secs']

_last_alg = {}


def _capture_init(self, *a, **k):
    _orig_init[type(self)](self, *a, **k)
    _last_alg['alg'] = self


_orig_init = {}
for _k in ('W_Safe35', 'W_SafeOBB', 'W_Roundabout', 'W_RoundaboutOBB'):
    C = ALG_MAP[_k]
    _orig_init[C] = C.__init__
    C.__init__ = _capture_init


def job(args):
    label, lam, split, rep, aname, akey, clearance = args
    OBBTurnAware.clearance_m = OBBPlain.clearance_m = clearance
    t0 = time.time()
    sched = make_schedule(lam, rep, split=split)
    if akey == 'W_RoundaboutOBB':
        with _YieldPatch():
            res = run_stream(akey, sched, fair=True)
    else:
        res = run_stream(akey, sched, fair=True)
    alg = _last_alg['alg']
    served = [v for v in res['vehicles'] if v['served']]
    d = [v['control_delay'] for v in served]
    pairs = getattr(alg, 'obb_pairs', {})
    real = sum(1 for r in pairs.values() if r)
    mg = getattr(alg, 'obb_min_gap', float('inf'))
    return dict(cell=label, lam=lam, rep=rep, alg=aname,
                mean_delay=round(float(np.mean(d)), 2) if d else None,
                served_pct=round(len(served) / len(res['vehicles']) * 100, 2)
                if res['vehicles'] else None,
                obb_real=real, obb_artifact=len(pairs) - real,
                obb_min_gap_m=round(mg, 2) if mg != float('inf') else '',
                secs=round(time.time() - t0))


def main():
    smoke = "--smoke" in sys.argv
    workers = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 6
    cells = CELLS[1:2] if smoke else CELLS
    reps = 1 if smoke else REPS
    clearance = (float(sys.argv[sys.argv.index('--clearance') + 1])
                 if '--clearance' in sys.argv else CLEARANCE_M)
    jobs = [(lab, lam, sp, rep, an, ak, clearance)
            for rep in range(reps) for lab, lam, sp in cells for an, ak in ALGS]
    # longest-first: heavy cells + Smart Safe dominate wall time
    jobs.sort(key=lambda j: (j[1], 'Roundabout' not in j[5]), reverse=True)


    out = OUT if not smoke else OUT.replace('.csv', '_smoke.csv')
    if clearance != CLEARANCE_M:
        out = out.replace('.csv', f'_c{clearance:g}.csv')
    print(f"OBB clearance buffer {clearance} m -> {out}")
    if '--summarize' in sys.argv:
        jobs = []                       # re-aggregate an existing CSV only
    else:
        with open(out, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
    t0 = time.time()
    with Pool(workers) as pool:
        for row in pool.imap_unordered(job, jobs):
            with open(out, "a", newline="") as f:
                csv.DictWriter(f, fieldnames=FIELDS).writerow(row)
            print(f"  rep {row['rep']} {row['cell']:>9} {row['alg']:<15}: "
                  f"{row['mean_delay']}s served {row['served_pct']}%  "
                  f"OBB real {row['obb_real']} art {row['obb_artifact']} "
                  f"min {row['obb_min_gap_m']}  ({time.time()-t0:.0f}s)", flush=True)

    rows = list(csv.DictReader(open(out)))

    def agg(cell, alg, key):
        v = [float(r[key]) for r in rows if r['cell'] == cell and r['alg'] == alg
             and r[key] not in ('', 'None')]
        return (np.mean(v), np.std(v), sum(v)) if v else (float('nan'),) * 3

    W = 124
    print("\n" + "=" * W)
    print(f"OBB SURVIVAL GATE ({reps} seeds) — mean delay ± std (s); served %; "
          f"real OBB overlaps (sum)")
    print("=" * W)
    print(f"{'cell':>14} | " + " | ".join(f"{an:>22}" for an, _ in ALGS)
          + " | verdict (Safe OBB vs RB OBB)")
    print("-" * W)
    for label, lam, _ in cells:
        cols = []
        for an, _ in ALGS:
            m, s, _ = agg(label, an, 'mean_delay')
            sp, _, _ = agg(label, an, 'served_pct')
            _, _, ro = agg(label, an, 'obb_real')
            cols.append((m, s, sp, ro))
        so, rb = cols[1][0], cols[3][0]          # honest bar: same footprint standard
        # served-aware: lower delay over fewer served cars is not a win
        if cols[1][2] < cols[3][2] - 2.0:
            verdict = f'OBB loses (capacity: {cols[1][2]:.0f}% vs {cols[3][2]:.0f}% served)'
        else:
            verdict = ('OBB WINS' if so < rb * 0.90 else
                       'parity' if abs(so - rb) / rb < 0.10 else 'OBB loses')
        cost = (cols[1][0] - cols[0][0]) / cols[0][0] * 100
        print(f"{label + ' ' + str(lam):>14} | " + " | ".join(
            f"{m:>5.1f}±{s:>4.1f} {sp:>5.1f}% r{int(ro):<2}" for m, s, sp, ro in cols)
            + f" | {verdict} (OBB cost {cost:+.0f}%)")
    print("=" * W)


if __name__ == "__main__":
    main()

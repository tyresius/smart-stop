#!/usr/bin/env python3
"""
Hesitation sweep — signal-blind Smart Safe vs the actuated signal
=================================================================
(2026-10-03.) Two honesty fixes over stopsign_vs_signal.py, then the
novel-device (MUTCD expectancy) stress test:

1. SIGNAL-BLIND. The streaming Smart Safe gated so far (SafeGatedSmartStop)
   still trusted declared L/R, and its geometric check walked each car's TRUE
   path — oracle knowledge a camera lacks before the car moves. The product
   premise is that Smart Safe ignores turn signals entirely. `BlindSafe` =
   motion-confirmed intent (PerceptionDetector: every not-yet-revealed car is
   checked against ALL THREE possible paths until it has travelled REVEAL_M)
   on the streaming platoon controller, with the OBB footprint check innermost.
   Turn signals are never read.

2. HESITATION. Drivers facing a flashing green over a stop sign have never
   seen it. Modeled as, for every flash-responding (head) vehicle:
     + H seconds added to its launch reaction delay (U(0.5, 2.0) + H);
     no rolling launches when H > 0 (hesitant drivers come to a full stop).
   Platoon followers keep the 0.6 s follow cap (they react to the car ahead —
   familiar car-following, not the device). The controller is CALIBRATED to
   the slower population (launch-delay hypotheses widened by H), and realized
   OBB overlaps are still checked every step. The signal gets NO hesitation
   (drivers know signals).

Usage:  python hesitation_sweep.py [--smoke] [--workers N] [--summarize]
"""
import csv
import sys
import time
from multiprocessing import Pool

import numpy as np

import block3_reality
import capacity_curves as cc
from capacity_curves import run_stream, make_schedule, ALG_MAP
from block3_reality import GatedPlatoonSmartStop
from motion_confirmed_intent import MotionConfirmedMixin
from obb_survival_gate import OBBWatch, OBBTurnAware, _innermost
from stopsign_vs_signal import SignalActuated

REPS = 5
OUT = "hesitation_sweep.csv"
LAMBDAS = [400, 600, 800, 1000, 1200]
SPLITS = [('balanced', None), ('arterial', [0.40, 0.40, 0.10, 0.10])]
HESITATION = [0.0, 0.5, 1.0, 2.0, 3.0]
BUFFER = 1.0
BASE_HYPS = block3_reality.DWELL_HYPOTHESES          # (0.0, 1.2, 2.5)


class BlindSafe(MotionConfirmedMixin, GatedPlatoonSmartStop):
    """Signal-blind Smart Safe: intent = motion only; OBB footprint check."""
    HESITATION_S = 0.0
    NO_ROLL = False           # full stop without extra hesitation (H=0 variant)

    def __init__(self, geometry):
        super().__init__(geometry)
        _innermost(self.collision_detector).__class__ = OBBTurnAware

    def add_vehicle(self, vehicle):
        h = self.HESITATION_S
        if h > 0.0 or self.NO_ROLL:
            vehicle.reaction_delay = getattr(vehicle, 'reaction_delay', 0.0) + h
            vehicle.roll_v0 = 0.0             # no rolling launch
            vehicle.roll_deadline = -1.0
            vehicle.state.velocity = 0.0
        super().add_vehicle(vehicle)


_last = {}


def _watched(base):
    def __init__(self, geometry):
        base.__init__(self, geometry)
        _last['alg'] = self
    return type(base.__name__ + 'W', (OBBWatch, base), {'__init__': __init__})


ALG_MAP['HS_Blind'] = _watched(BlindSafe)
ALG_MAP['HS_Signal'] = _watched(SignalActuated)

FIELDS = ['split', 'lam', 'rep', 'alg', 'hesitation', 'mean_delay', 'p95_delay',
          'served_pct', 'obb_real', 'obb_artifact', 'obb_min_gap_m', 'secs']


def job(args):
    split_label, split, lam, rep, akey, h = args
    OBBTurnAware.clearance_m = BUFFER
    BlindSafe.NO_ROLL = (h == 'stop')
    h = 0.0 if h == 'stop' else h
    BlindSafe.HESITATION_S = h
    # controller calibrated to the hesitant launch-delay population
    block3_reality.DWELL_HYPOTHESES = (BASE_HYPS[0], BASE_HYPS[1] + h / 2,
                                       BASE_HYPS[2] + h)
    t0 = time.time()
    res = run_stream(akey, make_schedule(lam, rep, split=split), fair=True)
    alg = _last['alg']
    vs = res['vehicles']
    served = [v for v in vs if v['served']]
    d = [v['control_delay'] for v in served]
    pairs = getattr(alg, 'obb_pairs', {})
    real = sum(1 for r in pairs.values() if r)
    mg = getattr(alg, 'obb_min_gap', float('inf'))
    return dict(split=split_label, lam=lam, rep=rep,
                alg='Smart Safe (blind)' if akey == 'HS_Blind' else 'Signal',
                hesitation=(('stop' if BlindSafe.NO_ROLL else h)
                            if akey == 'HS_Blind' else ''),
                mean_delay=round(float(np.mean(d)), 2) if d else '',
                p95_delay=round(float(np.percentile(d, 95)), 2) if d else '',
                served_pct=round(len(served) / len(vs) * 100, 2) if vs else '',
                obb_real=real, obb_artifact=len(pairs) - real,
                obb_min_gap_m=round(mg, 2) if mg != float('inf') else '',
                secs=round(time.time() - t0))


def summarize(rows):
    def agg(sl, lam, alg, h, key):
        v = [float(r[key]) for r in rows
             if r['split'] == sl and int(r['lam']) == lam and r['alg'] == alg
             and str(r['hesitation']) == str(h) and r[key] not in ('', None)]
        return (np.mean(v), np.std(v), np.sum(v)) if v else (np.nan,) * 3

    hs = sorted({float(r['hesitation']) for r in rows
                 if r['hesitation'] not in ('', 'stop')})
    cols = [('Signal', '')] + [('Smart Safe (blind)', h) for h in hs]
    if any(r['hesitation'] == 'stop' for r in rows):
        cols.insert(2, ('Smart Safe (blind)', 'stop'))
    W = 30 + 19 * len(cols)
    print("\n" + "=" * W)
    print(f"HESITATION SWEEP — mean control delay (s) [served %] {{real OBB overlaps}}; "
          f"OBB buffer {BUFFER} m; Smart Safe signal-blind")
    print("=" * W)
    for sl, _ in SPLITS:
        lams = sorted({int(r['lam']) for r in rows if r['split'] == sl})
        if not lams:
            continue
        print(f"\n{sl.upper()}")
        print(f"{'veh/h':>6} | " + " | ".join(
            f"{'Signal' if a == 'Signal' else ('Safe stop H=0' if h == 'stop' else f'Safe H={h:g}s'):>16}"
            for a, h in cols)
            + " | Safe beats signal up to H =")
        print("-" * W)
        for lam in lams:
            cells, sig_m = [], agg(sl, lam, 'Signal', '', 'mean_delay')[0]
            sig_sp = agg(sl, lam, 'Signal', '', 'served_pct')[0]
            best_h = None
            for a, h in cols:
                m, _, _ = agg(sl, lam, a, h, 'mean_delay')
                sp, _, _ = agg(sl, lam, a, h, 'served_pct')
                _, _, ro = agg(sl, lam, a, h, 'obb_real')
                cells.append(f"{m:6.1f} [{sp:3.0f}%] {{{int(ro) if ro == ro else 0}}}")
                if a != 'Signal' and h != 'stop' and m < sig_m and sp >= sig_sp - 1.0:
                    best_h = h if best_h is None or h > best_h else best_h
            tag = '—' if best_h is None else (best_h if isinstance(best_h, str) else f"{best_h:g} s")
            print(f"{lam:>6} | " + " | ".join(f"{c:>16}" for c in cells) + f" | {tag}")
    print("=" * W)


def main():
    smoke = "--smoke" in sys.argv
    workers = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 9
    out = OUT if not smoke else OUT.replace('.csv', '_smoke.csv')
    if '--summarize' in sys.argv:
        summarize(list(csv.DictReader(open(out))))
        return
    if '--targeted' in sys.argv:
        jobs = []
        for rep in range(REPS):
            for sl, sp in SPLITS:
                for lam in (400, 600, 800):
                    jobs.append((sl, sp, lam, rep, 'HS_Blind', 'stop'))
                for lam in (1000, 1200):
                    jobs.append((sl, sp, lam, rep, 'HS_Signal', 0.0))
                    jobs.append((sl, sp, lam, rep, 'HS_Blind', 0.0))
        return _run(jobs, out, workers, append=True)
    lams = [600, 1200] if smoke else LAMBDAS
    splits = SPLITS[1:] if smoke else SPLITS
    reps = 1 if smoke else REPS
    hes = [0.0, 3.0] if smoke else HESITATION
    jobs = []
    for rep in range(reps):
        for sl, sp in splits:
            for lam in lams:
                jobs.append((sl, sp, lam, rep, 'HS_Signal', 0.0))
                for h in hes:
                    jobs.append((sl, sp, lam, rep, 'HS_Blind', h))
    jobs.sort(key=lambda j: (j[2], j[5], j[3]))           # light first: results stream
    _run(jobs, out, workers)


def _run(jobs, out, workers, append=False):
    if not append:
        with open(out, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
    t0 = time.time()
    with Pool(workers) as pool:
        for row in pool.imap_unordered(job, jobs):
            with open(out, "a", newline="") as f:
                csv.DictWriter(f, fieldnames=FIELDS).writerow(row)
            print(f"  {row['split']:>8} {row['lam']:>5} rep {row['rep']} "
                  f"{row['alg']:<18} H={row['hesitation']!s:<4}: {row['mean_delay']}s "
                  f"[{row['served_pct']}%] OBB real {row['obb_real']} "
                  f"min {row['obb_min_gap_m']}  ({time.time()-t0:.0f}s)", flush=True)
    summarize(list(csv.DictReader(open(out))))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Stop-sign replacement gate — Smart Safe vs all-way stop vs traffic signal
=========================================================================
(2026-10-03.) The product pivot is STOP-SIGN REPLACEMENT with no civil works.
A city with a failing all-way stop has two real options: keep the all-way stop
(status quo) or install a traffic signal (the upgrade it would otherwise buy).
This runs all three under ONE physical standard (OBB footprints, realized
overlaps SAT-checked every step, see obb_survival_gate.py):

  All-way stop   HumanFourWay (cs4_human_baseline.py): FCFS + the two folk
                 pairings real drivers use (opposing straights, perpendicular
                 rights). The honest status quo, not strict-serial.
  Smart Safe     SafeOBBCheck: streaming Smart Safe with the OBB decision
                 check at clearance buffer B (0.5 / 1.0 m).
  Signal         SignalActuated (below): two-phase actuated, permitted lefts.

Signal model — same vehicles, same car-following discharge, same reaction
jitter and rolling arrivals as Smart Safe (it subclasses the same streaming
platoon controller); only right-of-way differs:
  * phases EW (Main E/W) and NS (Green N/S); a vehicle may launch only on
    its phase's green;
  * permitted lefts/rights yield via the SAME OBB conflict check at buffer B
    (they launch only into a footprint-clear gap; through traffic likewise
    cannot launch into a turning car still in the box);
  * green queues discharge as car-following platoons (no 4-car window);
  * actuated: min green 8 s, max green 40 s, gap-out after 3 s with no
    queued green-phase vehicle (only if the other phase has demand), rest
    in green otherwise;
  * change interval: yellow 3.5 s + all-red 1.5 s. Effective use of yellow:
    rolling vehicles / queued followers may still launch during the first
    2.0 s of yellow (dilemma-zone drivers proceed); nothing launches after.
Signal-favourable simplifications (stated, not hidden): no pedestrian
phases/minimums, no detector failures, lefts accept any OBB-clear gap (no
human critical-gap hesitation), timings tuned for these volumes. Signal-
unfavourable: no protected-left phase, no coordination with neighbours.

Usage:  python stopsign_vs_signal.py [--smoke] [--workers N]
"""
import csv
import sys
import time
from multiprocessing import Pool

import numpy as np

import capacity_curves as cc
from capacity_curves import run_stream, make_schedule, ALG_MAP
from block3_reality import GatedPlatoonSmartStop, CONFIRM_V
import cs4_human_baseline  # registers HumanFourWay  # noqa: F401
from cs4_human_baseline import HumanFourWay
from obb_survival_gate import (OBBWatch, OBBTurnAware, SafeOBBCheck,
                               _innermost)

REPS = 5
OUT = "stopsign_vs_signal.csv"
LAMBDAS = [400, 600, 800, 1000, 1200, 1600]
SPLITS = [('balanced', None), ('arterial', [0.40, 0.40, 0.10, 0.10])]
BUFFERS = [0.5, 1.0]

PHASE_ROADS = {'EW': ('Main E', 'Main W'), 'NS': ('Green N', 'Green S')}


class SignalActuated(GatedPlatoonSmartStop):
    """Two-phase actuated signal with permitted turns (see module doc)."""

    PLATOON_MAX = 50          # a green discharges the whole queue
    MIN_GREEN = 8.0
    MAX_GREEN = 40.0
    PASSAGE = 3.0
    YELLOW = 3.5
    ALL_RED = 1.5
    YELLOW_USED = 2.0

    def __init__(self, geometry):
        super().__init__(geometry)
        _innermost(self.collision_detector).__class__ = OBBTurnAware
        self.phase = 'EW'
        self.mode = 'green'           # green | yellow | allred
        self.mode_t0 = 0.0
        self.last_call = 0.0          # last time the green phase had a queue

    # ── helpers ────────────────────────────────────────────────────────────
    def _green_roads(self):
        return PHASE_ROADS[self.phase]

    def _other(self):
        return 'NS' if self.phase == 'EW' else 'EW'

    def _demand(self, phase):
        roads = PHASE_ROADS[phase]
        return any(v.road_name in roads for v in self.waiting_vehicles) or \
            any(v.road_name in roads for v in self._pending)

    def _launch_ok(self):
        el = self.current_time - self.mode_t0
        return self.mode == 'green' or (self.mode == 'yellow'
                                        and el < self.YELLOW_USED)

    def _clear(self, v):
        for a in self.active_vehicles:
            if self.collision_detector.check_collision(
                    v, a, time_horizon=self.COLLISION_TIME_HORIZON):
                return False
        return True

    # ── phase machine ──────────────────────────────────────────────────────
    def _advance_phase(self):
        t, el = self.current_time, self.current_time - self.mode_t0
        if self.mode == 'green':
            if self._demand(self.phase):
                self.last_call = t
            if not self._demand(self._other()) or el < self.MIN_GREEN:
                return
            if el >= self.MAX_GREEN or t - self.last_call >= self.PASSAGE:
                self.mode, self.mode_t0 = 'yellow', t
        elif self.mode == 'yellow' and el >= self.YELLOW:
            self.mode, self.mode_t0 = 'allred', t
            self._unclaim_pending()
        elif self.mode == 'allred' and el >= self.ALL_RED:
            self.phase = self._other()
            self.mode, self.mode_t0 = 'green', t
            self.last_call = t

    def _unclaim_pending(self):
        """Claimed-but-unreleased followers stop at the line for red: back
        to the queue with their own (full) reaction delay restored."""
        for v in self._pending:
            v.leader = None
            if hasattr(v, '_orig_rd'):
                v.reaction_delay = v._orig_rd
            self.waiting_vehicles.append(v)
        self._pending = []
        self.waiting_vehicles.sort(key=lambda v: v.order)

    # ── overrides ──────────────────────────────────────────────────────────
    def _claim_followers(self, leader):
        n0 = len(self._pending)
        road_q = [v for v in self.waiting_vehicles
                  if v.road_name == leader.road_name]
        for v in road_q[:self.PLATOON_MAX - 1]:
            v._orig_rd = getattr(v, 'reaction_delay', 0.0)
        super()._claim_followers(leader)
        return n0

    def _release_followers(self):
        if self._launch_ok():
            super()._release_followers()

    def _coordinate_smart_movements(self):
        self._advance_phase()
        if not self._launch_ok() or not self.waiting_vehicles:
            return
        in_yellow = self.mode == 'yellow'
        for v in self._heads_of_queue():
            if v.road_name not in self._green_roads():
                continue
            if in_yellow and v.state.velocity < CONFIRM_V:
                continue                  # stopped cars don't launch on yellow
            if self._clear(v):
                self.waiting_vehicles.remove(v)
                v.activate(self.current_time)
                self.active_vehicles.append(v)


# ── registration (watched variants; capture the instance for OBB stats) ────
_last = {}


def _watched(base):
    def __init__(self, geometry):
        base.__init__(self, geometry)
        _last['alg'] = self
    return type(base.__name__ + 'W', (OBBWatch, base), {'__init__': __init__})


ALG_MAP['SS_Human'] = _watched(HumanFourWay)
ALG_MAP['SS_Safe'] = _watched(SafeOBBCheck)
ALG_MAP['SS_Signal'] = _watched(SignalActuated)

ALGS = [('All-way stop', 'SS_Human', False),
        ('Smart Safe', 'SS_Safe', True),
        ('Signal', 'SS_Signal', True)]

FIELDS = ['split', 'lam', 'rep', 'alg', 'buffer', 'mean_delay', 'p95_delay',
          'served_pct', 'obb_real', 'obb_artifact', 'obb_min_gap_m', 'secs']


def job(args):
    split_label, split, lam, rep, aname, akey, buf = args
    OBBTurnAware.clearance_m = buf if buf is not None else 1.0
    t0 = time.time()
    res = run_stream(akey, make_schedule(lam, rep, split=split), fair=True)
    alg = _last['alg']
    vs = res['vehicles']
    served = [v for v in vs if v['served']]
    d = [v['control_delay'] for v in served]
    pairs = getattr(alg, 'obb_pairs', {})
    real = sum(1 for r in pairs.values() if r)
    mg = getattr(alg, 'obb_min_gap', float('inf'))
    return dict(split=split_label, lam=lam, rep=rep, alg=aname,
                buffer='' if buf is None else buf,
                mean_delay=round(float(np.mean(d)), 2) if d else '',
                p95_delay=round(float(np.percentile(d, 95)), 2) if d else '',
                served_pct=round(len(served) / len(vs) * 100, 2) if vs else '',
                obb_real=real, obb_artifact=len(pairs) - real,
                obb_min_gap_m=round(mg, 2) if mg != float('inf') else '',
                secs=round(time.time() - t0))


def summarize(rows):
    def agg(sl, lam, alg, buf, key):
        v = [float(r[key]) for r in rows
             if r['split'] == sl and int(r['lam']) == lam and r['alg'] == alg
             and str(r['buffer']) == str(buf) and r[key] not in ('', None)]
        return (np.mean(v), np.std(v), np.sum(v)) if v else (np.nan,) * 3

    cols = [('All-way stop', ''), ('Smart Safe', 0.5), ('Signal', 0.5),
            ('Smart Safe', 1.0), ('Signal', 1.0)]
    W = 132
    print("\n" + "=" * W)
    print("STOP-SIGN REPLACEMENT GATE — mean control delay ± std (s) [served %] "
          "{real OBB overlaps}; Safe/Signal at buffer B")
    print("=" * W)
    for sl, _ in SPLITS:
        print(f"\n{sl.upper()}")
        print(f"{'veh/h':>6} | " + " | ".join(
            f"{a + (f' B{b:g}' if b != '' else ''):>21}" for a, b in cols))
        print("-" * W)
        lams = sorted({int(r['lam']) for r in rows if r['split'] == sl})
        for lam in lams:
            cells = []
            for a, b in cols:
                m, s, _ = agg(sl, lam, a, b, 'mean_delay')
                sp, _, _ = agg(sl, lam, a, b, 'served_pct')
                _, _, ro = agg(sl, lam, a, b, 'obb_real')
                cells.append(f"{m:6.1f}±{s:5.1f} [{sp:3.0f}%] {{{int(ro) if ro == ro else 0}}}")
            print(f"{lam:>6} | " + " | ".join(f"{c:>21}" for c in cells))
    print("=" * W)


def main():
    smoke = "--smoke" in sys.argv
    workers = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 8
    out = OUT if not smoke else OUT.replace('.csv', '_smoke.csv')
    if '--summarize' in sys.argv:
        summarize(list(csv.DictReader(open(out))))
        return
    lams = [600, 1200] if smoke else LAMBDAS
    splits = SPLITS[1:] if smoke else SPLITS
    reps = 1 if smoke else REPS
    jobs = []
    for rep in range(reps):
        for sl, sp in splits:
            for lam in lams:
                for an, ak, uses_b in ALGS:
                    for b in (BUFFERS if uses_b else [None]):
                        jobs.append((sl, sp, lam, rep, an, ak, b))
    jobs.sort(key=lambda j: (j[2], j[5] == 'SS_Safe'), reverse=True)  # heavy first

    with open(out, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writeheader()
    t0 = time.time()
    with Pool(workers) as pool:
        for row in pool.imap_unordered(job, jobs):
            with open(out, "a", newline="") as f:
                csv.DictWriter(f, fieldnames=FIELDS).writerow(row)
            print(f"  {row['split']:>8} {row['lam']:>5} rep {row['rep']} "
                  f"{row['alg']:<13} B={row['buffer']!s:<4}: {row['mean_delay']}s "
                  f"[{row['served_pct']}%] OBB real {row['obb_real']} "
                  f"min {row['obb_min_gap_m']}  ({time.time()-t0:.0f}s)", flush=True)
    summarize(list(csv.DictReader(open(out))))


if __name__ == "__main__":
    main()

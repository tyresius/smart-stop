#!/usr/bin/env python3
"""
Dominance check: why doesn't Smart Safe clearly beat a stop sign? (2026-11-12)
=============================================================================
Patrick's objection: a controller that can do everything a stop sign does,
plus roll cars through and release several at once, should not merely tie
it, and its edge should GROW with traffic, not shrink. Three suspects, each
isolated on the same arrival seeds:

  1. CAP. Smart Safe inherits `len(active_vehicles) < 4` from early code: no
     new flash while 4 cars are "active", and cars stay active until the end
     of their exit lane. The signal and the stop sign have no such cap.
  2. INFORMATION. The blind controller never reads turn signals; the rebuilt
     stop sign's drivers read them perfectly (honest signals in these runs).
     "Informed" gives Smart Safe the same knowledge as the human drivers
     (diagnostic only: Patrick's design rule is that Smart Safe ignores
     signals, because they can lie).
  3. GENEROUS HUMANS. The rebuilt stop sign lets a driver go out of turn
     whenever its movement never conflicts with any moving car. "Folk-only"
     restricts that to the two classic pairings (opposing straights,
     perpendicular rights), as the legacy baseline did.

All Smart Safe variants are BlindSafeV2Hes, H = 0, tangent headings; delay is
control_delay_sp (stops charged); independent checker on every run.
600 / 800 / 1,000 veh/h, both splits, seeds 0-4.

Usage: .venv/bin/python dominance_check.py [--summarize] -> dominance_check.csv / .txt
"""
import csv
import statistics as st
import sys
import time
from math import sqrt
from multiprocessing import Pool

import numpy as np

import block3_reality
import hesitation_sweep as hs
import obb_survival_gate as g
import reality_sweeps
from capacity_curves import ALG_MAP, run_stream, make_schedule
from independent_checker import IndependentWatch
from blind_safe_v2 import BlindSafeV2Hes, PerceptionDetectorV2
from cs4_human_baseline import HumanFourWayFCFS, _folk_pair

SPLITS = dict(hs.SPLITS)
LAMBDAS = (600, 800, 1000)
SEEDS = range(5)
T_CRIT = {4: 2.776, 3: 3.182, 2: 4.303, 1: 12.706}
_last = {}


class PerceptionInformed(PerceptionDetectorV2):
    """Knows every car's movement from the start (honest turn signals)."""

    def _variants(self, v):
        phantoms = self.variant_map.get(id(v))
        if not phantoms:
            return [v]
        phantoms = [p for p in phantoms if p.signal == v.true_signal] or phantoms
        leader, rolled = getattr(v, 'leader', None), getattr(v, 'rolled', False)
        for p in phantoms:
            p.active, p.completed = v.active, v.completed
            p.current_position_meters = v.current_position_meters
            p.state.velocity = v.state.velocity
            p.leader, p.rolled = leader, rolled
        return phantoms


class InformedMixin:
    def __init__(self, geometry):
        super().__init__(geometry)
        self.collision_detector.__class__ = PerceptionInformed

    def _intent_of(self, vehicle):
        return vehicle.signal

    def _same_group(self, v, leader):
        return v.signal == leader.signal


class FolkOnlyStopSign(HumanFourWayFCFS):
    def _may_go_out_of_turn(self, cand, a):
        return _folk_pair(cand, a)


def _register(name, bases, attrs=None):
    def __init__(self, geometry):
        super(cls, self).__init__(geometry)
        _last['alg'] = self
    cls = type(name, (IndependentWatch,) + bases, dict(attrs or {}, __init__=__init__))
    ALG_MAP[name] = cls
    return name


NOCAP = {'MAX_ACTIVE': 999}
CONDS = {
    'Safe rolling': _register('DC_roll', (BlindSafeV2Hes,), {'ALLOW_ROLL': True}),
    'Safe rolling, no cap': _register('DC_roll_nocap', (BlindSafeV2Hes,), dict(NOCAP, ALLOW_ROLL=True)),
    'Safe rolling, informed': _register('DC_roll_inf', (InformedMixin, BlindSafeV2Hes), {'ALLOW_ROLL': True}),
    'Safe rolling, no cap, informed': _register('DC_roll_nocap_inf', (InformedMixin, BlindSafeV2Hes),
                                                dict(NOCAP, ALLOW_ROLL=True)),
    'Safe full stop, no cap': _register('DC_stop_nocap', (BlindSafeV2Hes,), dict(NOCAP, ALLOW_ROLL=False)),
    'Safe full stop, no cap, informed': _register('DC_stop_nocap_inf', (InformedMixin, BlindSafeV2Hes),
                                                  dict(NOCAP, ALLOW_ROLL=False)),
    'Stop sign': _register('DC_stopsign', (HumanFourWayFCFS,)),
    'Stop sign, folk-only': _register('DC_stopsign_folk', (FolkOnlyStopSign,)),
}


def job(args):
    label, split, lam, rep = args
    g.HEADING_MODE = 'tangent'
    hs.OBBTurnAware.clearance_m = hs.BUFFER
    block3_reality.DWELL_HYPOTHESES = hs.BASE_HYPS
    t0 = time.time()
    res = run_stream(CONDS[label], make_schedule(lam, rep, split=SPLITS[split]), fair=True)
    alg = _last['alg']
    sv = [v for v in res['vehicles'] if v['served']]
    s = alg.ic.summary()
    return dict(cond=label, split=split, lam=lam, rep=rep,
                mean_sp=round(float(np.mean([v['control_delay_sp'] for v in sv])), 3),
                stop_frac=round(sum(v['stopped'] for v in sv) / len(sv), 3),
                served_pct=round(len(sv) / len(res['vehicles']) * 100, 2),
                contacts=s['moving-moving']['contacts'] + s['moving-stopped-cross']['contacts'],
                min_gap_moving=s['moving-moving']['min_gap_m'] or '',
                cap_blocks=getattr(alg, '_cap_blocks', 0),
                secs=round(time.time() - t0))


def summarize(rows):
    cell = {}
    for r in rows:
        cell.setdefault((r['cond'], r['split'], int(r['lam'])), {})[int(r['rep'])] = r

    def mean(c, sp, lam, k='mean_sp'):
        return st.mean(float(r[k]) for r in cell[(c, sp, lam)].values())

    def paired(a, b, sp, lam):
        A = {k: float(r['mean_sp']) for k, r in cell[(a, sp, lam)].items()}
        B = {k: float(r['mean_sp']) for k, r in cell[(b, sp, lam)].items()}
        d = [A[k] - B[k] for k in A if k in B]
        m = st.mean(d)
        hw = T_CRIT[len(d) - 1] * st.stdev(d) / sqrt(len(d))
        v = 'lower' if m + hw < 0 else 'higher' if m - hw > 0 else 'n.r.'
        return f"{m:+6.1f} [{m - hw:+5.1f},{m + hw:+5.1f}] {v}"

    L = ["DOMINANCE CHECK (BlindSafeV2Hes H=0, tangent headings; 5 seeds; delay with stops charged)", ""]
    contacts = sum(int(r['contacts']) for r in rows)
    L.append(f"Contacts found by the independent checker, all runs: {contacts}")
    L.append("")
    L.append("Mean delay (s) [share of cars stopped] {times the 4-car cap blocked a clear release, per run}")
    for sp in SPLITS:
        L.append(f"  {sp}:")
        for c in CONDS:
            parts = []
            for lam in LAMBDAS:
                if (c, sp, lam) not in cell:
                    continue
                cb = mean(c, sp, lam, 'cap_blocks')
                parts.append(f"{lam}: {mean(c, sp, lam):6.1f} [{mean(c, sp, lam, 'stop_frac'):4.0%}]"
                             + (f" {{{cb:5.0f}}}" if c.startswith('Safe') else "        "))
            L.append(f"    {c:34} " + "   ".join(parts))
        L.append("")
    L.append("Paired differences, mean [95% CI] (negative = first is lower):")
    pairs = [('Safe rolling, no cap', 'Safe rolling', 'effect of removing the cap (rolling)'),
             ('Safe rolling, informed', 'Safe rolling', 'effect of turn-signal knowledge'),
             ('Stop sign, folk-only', 'Stop sign', 'effect of restricting humans to folk pairings'),
             ('Safe rolling', 'Stop sign', 'Smart Safe as tested vs stop sign'),
             ('Safe rolling, no cap', 'Stop sign', 'no cap vs stop sign'),
             ('Safe rolling, no cap, informed', 'Stop sign', 'no cap + informed vs stop sign'),
             ('Safe full stop, no cap', 'Stop sign', 'FULL STOP, no cap vs stop sign'),
             ('Safe full stop, no cap, informed', 'Stop sign', 'FULL STOP, no cap + informed vs stop sign'),
             ('Safe rolling, no cap', 'Stop sign, folk-only', 'no cap vs folk-only stop sign')]
    for a, b, what in pairs:
        L.append(f"  {what}:")
        for sp in SPLITS:
            L.append(f"    {sp:9} " + "   ".join(
                f"{lam}: {paired(a, b, sp, lam)}" for lam in LAMBDAS
                if (a, sp, lam) in cell and (b, sp, lam) in cell))
    txt = "\n".join(L)
    print(txt)
    open('dominance_check.txt', 'w').write(txt + "\n")


def main():
    jobs = [(c, sp, lam, rep) for c in CONDS for lam in LAMBDAS for sp in SPLITS for rep in SEEDS]
    jobs.sort(key=lambda j: (-j[2], not j[0].startswith('Safe')))
    rows = []
    with Pool(9) as pool:
        for r in pool.imap_unordered(job, jobs):
            rows.append(r)
            with open('dominance_check.csv', 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(r))
                w.writeheader()
                w.writerows(sorted(rows, key=lambda x: (x['cond'], x['split'], x['lam'], x['rep'])))
            print(f"[{len(rows)}/{len(jobs)}] {r['cond']:34} {r['split']:9} {r['lam']} rep {r['rep']}: "
                  f"{r['mean_sp']} s, cap blocks {r['cap_blocks']}, contacts {r['contacts']} ({r['secs']}s)",
                  flush=True)
    summarize([{k: str(v) for k, v in r.items()} for r in rows])


if __name__ == '__main__':
    if '--summarize' in sys.argv:
        summarize(list(csv.DictReader(open('dominance_check.csv'))))
    else:
        main()

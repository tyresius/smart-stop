#!/usr/bin/env python3
"""
Fair signalling test (2026-11-12)
=================================
dominance_check.txt showed Smart Safe beats the stop sign 3-4x when it knows
where cars are going, as the stop sign's human drivers do. But both sides had
PERFECT signals. Here both face the same imperfect drivers:

  perfect    every driver signals, honestly
  realistic  25% don't signal (the SAE field share already in CLAIMS.md);
             the rest signal honestly
  liars      realistic + 2% signal falsely: they signal a right turn (or
             straight, if they really are turning right) and go another way.
             2% is a stress assumption, not field data.

Each driver's behaviour is fixed by its arrival number and seed, so every
controller faces the identical drivers.

Who knows what (symmetric):
  Stop sign drivers   know their own movement; read others' signals
                      (believing them); a non-signaller is "could be any
                      movement" until its motion reveals it (REVEAL_M = 4 m).
  Smart Safe, reads   the same: believes signals, treats non-signallers as
  signals             any movement until REVEAL_M. Rolling launches, H = 0,
                      BlindSafeV2 otherwise, tangent headings.
  Smart Safe, blind   ignores signals entirely (the current design); the same
                      in every regime, so it runs once.
Delay with stops charged; independent checker on every run.
600 / 800 / 1,000 veh/h, both splits, seeds 0-9.

HOW THE RESULTS WILL BE READ (fixed before running):
  1. The advantage SURVIVES realistic signalling where signal-reading Smart
     Safe beats the stop sign under `realistic`, paired 95% CI below zero.
  2. Signal-reading Smart Safe is NO LESS SAFE than the stop sign under
     `liars` if its contacts are no more frequent than the stop sign's (same
     drivers, so the counts are directly comparable). Any contact under
     `perfect` or `realistic` would be a defect, not a deception effect.
  3. Neither side has evasive braking in the model, so absolute contact counts
     overstate real crashes; only the comparison carries weight.

Usage: .venv/bin/python fair_signalling_test.py [--summarize]
Outputs: fair_signalling_test.csv / .txt / _events.jsonl
"""
import csv
import json
import random
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
from reality_sweeps import SIGNALS
from capacity_curves import ALG_MAP, run_stream, make_schedule, SEED
from independent_checker import IndependentWatch
from blind_safe_v2 import BlindSafeV2Hes, PerceptionDetectorV2
from cs4_human_baseline import HumanFourWayFCFS, conflict_table
from obb_diag import L_M

SPLITS = dict(hs.SPLITS)
LAMBDAS = (600, 800, 1000)
SEEDS = range(10)
REGIMES = {'perfect': (0.0, 0.0), 'realistic': (0.25, 0.0), 'liars': (0.25, 0.02)}
T_CRIT = {9: 2.262, 4: 2.776}
_last = {}


def _declared(true_sig, u, none_q, false_q):
    if u < none_q:
        return None
    if u < none_q + false_q:
        return 'R' if true_sig != 'R' else 'NS/S'
    return true_sig


class DriverSignals:
    """Assigns each arriving driver's signalling behaviour (deterministic per
    arrival number, so every controller sees the same drivers)."""
    NONE_Q = 0.0
    FALSE_Q = 0.0

    def add_vehicle(self, v):
        u = random.Random(f"{SEED}-signal-{v.order}").random()
        v.declared = _declared(v.signal, u, self.NONE_Q, self.FALSE_Q)
        if v.declared is not None and v.declared != v.signal:
            self.liars = getattr(self, 'liars', set()) | {v.order}
        super().add_vehicle(v)


def _revealed(v):
    return v.active and v.current_position_meters > reality_sweeps.REVEAL_M


# ── the stop sign with signal-reading drivers ─────────────────────────────
class StopSignSignals(DriverSignals, HumanFourWayFCFS):
    def _perceived(self, a):
        return a.signal if _revealed(a) else a.declared

    def _clear_s(self, a, cand):
        tab = conflict_table(self.MARGIN_M)
        m = self._perceived(a)
        moves = [m] if m is not None else SIGNALS
        return max(tab[((a.road_name, x), (cand.road_name, cand.signal))] for x in moves)

    def _holder_may_go(self, cand, a):
        if a.road_name == cand.road_name and self._perceived(a) == cand.signal:
            return a.current_position_meters >= L_M + self.SAME_LANE_GAP_M
        return a.current_position_meters >= self._clear_s(a, cand)

    def _may_go_out_of_turn(self, cand, a):
        return a.road_name != cand.road_name and self._clear_s(a, cand) == 0.0


# ── Smart Safe that reads signals the same way ─────────────────────────────
class PerceptionSignals(PerceptionDetectorV2):
    def _variants(self, v):
        phantoms = self.variant_map.get(id(v))
        if not phantoms:
            return [v]
        if _revealed(v):
            sel = [p for p in phantoms if p.signal == v.true_signal]
        elif getattr(v, 'declared', None) is not None:
            sel = [p for p in phantoms if p.signal == v.declared]
        else:
            sel = phantoms
        phantoms = sel or phantoms
        leader, rolled = getattr(v, 'leader', None), getattr(v, 'rolled', False)
        for p in phantoms:
            p.active, p.completed = v.active, v.completed
            p.current_position_meters = v.current_position_meters
            p.state.velocity = v.state.velocity
            p.leader, p.rolled = leader, rolled
        return phantoms


class SafeReadsSignals(DriverSignals, BlindSafeV2Hes):
    ALLOW_ROLL = True

    def __init__(self, geometry):
        super().__init__(geometry)
        self.collision_detector.__class__ = PerceptionSignals

    def _intent_of(self, vehicle):
        return getattr(vehicle, 'declared', None)

    def _same_group(self, v, leader):
        d = getattr(v, 'declared', None)
        return d is not None and d == getattr(leader, 'declared', None)


class SafeBlind(DriverSignals, BlindSafeV2Hes):
    ALLOW_ROLL = True


def _register(name, base, attrs):
    def __init__(self, geometry):
        super(cls, self).__init__(geometry)
        _last['alg'] = self
    cls = type(name, (IndependentWatch, base), dict(attrs, __init__=__init__))
    ALG_MAP[name] = cls
    return name


CONDS = {}
for reg, (nq, fq) in REGIMES.items():
    CONDS[('Stop sign', reg)] = _register(f'FS_stop_{reg}', StopSignSignals,
                                          {'NONE_Q': nq, 'FALSE_Q': fq})
    CONDS[('Smart Safe, reads signals', reg)] = _register(f'FS_read_{reg}', SafeReadsSignals,
                                                          {'NONE_Q': nq, 'FALSE_Q': fq})
CONDS[('Smart Safe, blind', 'any')] = _register('FS_blind', SafeBlind, {})


def job(args):
    ctrl, reg, split, lam, rep = args
    g.HEADING_MODE = 'tangent'
    hs.OBBTurnAware.clearance_m = hs.BUFFER
    block3_reality.DWELL_HYPOTHESES = hs.BASE_HYPS
    t0 = time.time()
    res = run_stream(CONDS[(ctrl, reg)], make_schedule(lam, rep, split=SPLITS[split]), fair=True)
    alg = _last['alg']
    sv = [v for v in res['vehicles'] if v['served']]
    s = alg.ic.summary()
    liars = getattr(alg, 'liars', set())
    ev = [e for e in alg.ic.events if e['category'] in ('moving-moving', 'moving-stopped-cross')
          and e['contact']]

    def order(tag):
        return int(tag.split('#')[1])
    liar_contacts = sum(1 for e in ev if order(e['a']) in liars or order(e['b']) in liars)
    row = dict(ctrl=ctrl, regime=reg, split=split, lam=lam, rep=rep,
               mean_sp=round(float(np.mean([v['control_delay_sp'] for v in sv])), 3),
               stop_frac=round(sum(v['stopped'] for v in sv) / len(sv), 3),
               served_pct=round(len(sv) / len(res['vehicles']) * 100, 2),
               contacts=len(ev), contacts_with_liar=liar_contacts, liars=len(liars),
               min_gap_moving=s['moving-moving']['min_gap_m'] if s['moving-moving']['min_gap_m'] is not None else '',
               secs=round(time.time() - t0))
    events = [dict(e, ctrl=ctrl, regime=reg, split=split, lam=lam, rep=rep) for e in ev[:20]]
    return row, events


def summarize(rows):
    cell = {}
    for r in rows:
        cell.setdefault((r['ctrl'], r['regime'], r['split'], int(r['lam'])), {})[int(r['rep'])] = r

    def get(ctrl, reg, sp, lam):
        return cell.get((ctrl, reg, sp, lam)) or cell.get((ctrl, 'any', sp, lam))

    def mean(ctrl, reg, sp, lam, k='mean_sp'):
        return st.mean(float(r[k]) for r in get(ctrl, reg, sp, lam).values())

    def paired(a, b):
        d = [float(a[k]['mean_sp']) - float(b[k]['mean_sp']) for k in a if k in b]
        m = st.mean(d)
        hw = T_CRIT[len(d) - 1] * st.stdev(d) / sqrt(len(d))
        v = 'LOWER' if m + hw < 0 else 'higher' if m - hw > 0 else 'n.r.'
        return f"{m:+6.1f} [{m - hw:+5.1f},{m + hw:+5.1f}] {v}"

    L = ["FAIR SIGNALLING TEST (10 seeds; delay with stops charged; Smart Safe rolling, H=0)", ""]
    L.append("1. SAFETY: contacts (moving-moving + moving vs waiting car), all volumes and splits")
    L.append(f"   {'controller':28} {'regime':10} {'contacts':>8} {'involving a liar':>17} {'liars':>6}")
    for (ctrl, reg) in CONDS:
        rs = [r for (c, g_, _, _), d in cell.items() if c == ctrl and g_ == reg for r in d.values()]
        if rs:
            L.append(f"   {ctrl:28} {reg:10} {sum(int(r['contacts']) for r in rs):8} "
                     f"{sum(int(r['contacts_with_liar']) for r in rs):17} "
                     f"{sum(int(r['liars']) for r in rs):6}")
    L.append("")
    L.append("2. MEAN DELAY (s) [share of cars stopped]")
    for sp in SPLITS:
        L.append(f"   {sp}:")
        for (ctrl, reg) in CONDS:
            parts = [f"{lam}: {mean(ctrl, reg, sp, lam):5.1f} [{mean(ctrl, reg, sp, lam, 'stop_frac'):4.0%}]"
                     for lam in LAMBDAS if get(ctrl, reg, sp, lam)]
            L.append(f"     {ctrl:28} {reg:10} " + "   ".join(parts))
        L.append("")
    L.append("3. PAIRED DIFFERENCES (negative = first is lower)")
    comps = [(('Smart Safe, reads signals', r), ('Stop sign', r), f"reads signals vs stop sign, {r}")
             for r in REGIMES]
    comps += [(('Smart Safe, blind', 'any'), ('Stop sign', r), f"blind vs stop sign, {r}") for r in REGIMES]
    comps += [(('Smart Safe, reads signals', 'realistic'), ('Smart Safe, reads signals', 'perfect'),
               "reads signals: realistic minus perfect"),
              (('Stop sign', 'realistic'), ('Stop sign', 'perfect'), "stop sign: realistic minus perfect")]
    for a, b, what in comps:
        L.append(f"   {what}:")
        for sp in SPLITS:
            L.append(f"     {sp:9} " + "   ".join(
                f"{lam}: {paired(get(*a, sp, lam), get(*b, sp, lam))}" for lam in LAMBDAS))
    txt = "\n".join(L)
    print(txt)
    open('fair_signalling_test.txt', 'w').write(txt + "\n")


def main():
    jobs = [(c, r, sp, lam, rep) for (c, r) in CONDS for lam in LAMBDAS for sp in SPLITS for rep in SEEDS]
    jobs.sort(key=lambda j: (-j[3], j[0] != 'Smart Safe, blind'))
    rows = []
    with open('fair_signalling_test_events.jsonl', 'w') as evf, Pool(9) as pool:
        for row, events in pool.imap_unordered(job, jobs):
            rows.append(row)
            for e in events:
                evf.write(json.dumps(e) + '\n')
            evf.flush()
            with open('fair_signalling_test.csv', 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(row))
                w.writeheader()
                w.writerows(sorted(rows, key=lambda x: (x['ctrl'], x['regime'], x['split'],
                                                        x['lam'], x['rep'])))
            print(f"[{len(rows)}/{len(jobs)}] {row['ctrl']:28} {row['regime']:10} {row['split']:9} "
                  f"{row['lam']} rep {row['rep']}: {row['mean_sp']} s, contacts {row['contacts']} "
                  f"(liar {row['contacts_with_liar']}/{row['liars']}) ({row['secs']}s)", flush=True)
    summarize([{k: str(v) for k, v in r.items()} for r in rows])


if __name__ == '__main__':
    if '--summarize' in sys.argv:
        summarize(list(csv.DictReader(open('fair_signalling_test.csv'))))
    else:
        main()

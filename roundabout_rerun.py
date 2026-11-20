#!/usr/bin/env python3
"""
Roundabout re-run under the current standards (2026-11-15)
=========================================================
The roundabout comparison (obb_survival_gate.py, 1 Oct) predates every fix
since: legacy metric (stops free), legacy headings, no independent checker,
and only oversaturated volumes (1,000-2,400 veh/h). This puts the corrected
roundabout on the same footing as everything in fair_signalling_test.py.

Roundabout = RoundaboutOBB from 1 Oct, with one fix (2026-11-15): its gap
check now also sees a car still on its entry arc that is about to reach the
merge point (GAP_INCLUDES_ENTERING; the Oct rules ignored such cars, which
produced entry contacts). The unchanged Oct version is run alongside.
  - gap acceptance: 4.5 s critical gap, 2.8 s follow-up between entries from
    one approach (roundabout_entry.py, block3_reality.RealisticRoundabout);
  - rolling entry when the ring is clear; no extra reaction dwell (the gap
    acceptance already includes the driver's decision time);
  - 1.5 m yield-line setback and footprint entry check, B = 1.0 m.
It needs nobody's turn signal (entry is judged on ring positions), so like
blind Smart Safe it is the same in every signalling regime.

Runs here:
  - roundabout: balanced, arterial, dominant (55/15/15/15)
  - stop sign, Smart Safe blind and signal-reading: dominant only (balanced
    and arterial are reused from fair_signalling_test.csv, same seeds)
Realistic signalling (25% don't signal). 600 / 800 / 1,000 veh/h, seeds 0-9.
Delay with stops charged; independent checker on every run.

Usage: .venv/bin/python roundabout_rerun.py [--summarize]
Outputs: roundabout_rerun.csv / .txt
"""
import csv
import statistics as st
import sys
import time
from math import sqrt
from multiprocessing import Pool

import numpy as np

import capacity_curves as cc
import fair_signalling_test as fst
import obb_survival_gate as g
import hesitation_sweep as hs
import block3_reality
from capacity_curves import ALG_MAP, run_stream, make_schedule
from independent_checker import IndependentWatch
from obb_survival_gate import RoundaboutOBB, OBBPlain, _YieldPatch

fst.SPLITS['dominant'] = [0.55, 0.15, 0.15, 0.15]
SPLITS = ('balanced', 'arterial', 'dominant')
LAMBDAS = fst.LAMBDAS
SEEDS = fst.SEEDS
T9 = 2.262
_last = {}


def _rb_init(self, geometry):
    RoundaboutOBB.__init__(self, geometry)
    _last['alg'] = self


# 'Roundabout' = fixed gap check (also sees cars about to reach the merge from
# an entry arc); 'Roundabout (Oct rules)' = unchanged 1 Oct model, for reference.
RB_KEYS = {'Roundabout': 'RR_Roundabout', 'Roundabout (Oct rules)': 'RR_Roundabout_oct'}
ALG_MAP['RR_Roundabout'] = type('RoundaboutOBBIC', (IndependentWatch, RoundaboutOBB),
                                {'__init__': _rb_init, 'GAP_INCLUDES_ENTERING': True})
ALG_MAP['RR_Roundabout_oct'] = type('RoundaboutOBBOctIC', (IndependentWatch, RoundaboutOBB),
                                    {'__init__': _rb_init})
cc.NO_JITTER_ALGS.update(RB_KEYS.values())


def rb_job(split, lam, rep, label='Roundabout'):
    g.HEADING_MODE = 'tangent'
    OBBPlain.clearance_m = 1.0
    hs.OBBTurnAware.clearance_m = hs.BUFFER
    block3_reality.DWELL_HYPOTHESES = hs.BASE_HYPS
    t0 = time.time()
    with _YieldPatch():
        res = run_stream(RB_KEYS[label], make_schedule(lam, rep, split=fst.SPLITS[split]),
                         fair=True)
    alg = _last['alg']
    sv = [v for v in res['vehicles'] if v['served']]
    s = alg.ic.summary()
    return dict(ctrl=label, regime='any', split=split, lam=lam, rep=rep,
                mean_sp=round(float(np.mean([v['control_delay_sp'] for v in sv])), 3),
                stop_frac=round(sum(v['stopped'] for v in sv) / len(sv), 3),
                served_pct=round(len(sv) / len(res['vehicles']) * 100, 2),
                contacts=s['moving-moving']['contacts'] + s['moving-stopped-cross']['contacts'],
                min_gap_moving=s['moving-moving']['min_gap_m'] if s['moving-moving']['min_gap_m'] is not None else '',
                secs=round(time.time() - t0))


def job(args):
    ctrl, split, lam, rep = args
    if ctrl in RB_KEYS:
        return rb_job(split, lam, rep, ctrl)
    reg = 'any' if ctrl == 'Smart Safe, blind' else 'realistic'
    row, _ = fst.job((ctrl, reg, split, lam, rep))
    keep = ('ctrl', 'regime', 'split', 'lam', 'rep', 'mean_sp', 'stop_frac', 'served_pct',
            'contacts', 'min_gap_moving', 'secs')
    return {k: row[k] for k in keep}


CTRLS = ('Stop sign', 'Smart Safe, blind', 'Smart Safe, reads signals', 'Roundabout',
         'Roundabout (Oct rules)')


def summarize(rows):
    cell = {}
    for r in rows:
        cell.setdefault((r['ctrl'], r['split'], int(r['lam'])), {})[int(r['rep'])] = r
    # balanced / arterial for the three non-roundabout controllers: fair test
    for r in csv.DictReader(open('fair_signalling_test.csv')):
        if r['regime'] in ('realistic', 'any') and (r['ctrl'], r['split'], int(r['lam'])) not in cell \
                or (r['regime'] in ('realistic', 'any')
                    and int(r['rep']) not in cell.get((r['ctrl'], r['split'], int(r['lam'])), {})):
            cell.setdefault((r['ctrl'], r['split'], int(r['lam'])), {})[int(r['rep'])] = r

    def m(c, sp, lam, k='mean_sp'):
        return st.mean(float(r[k]) for r in cell[(c, sp, lam)].values())

    def paired(a, b, sp, lam):
        A, B = cell[(a, sp, lam)], cell[(b, sp, lam)]
        d = [float(A[k]['mean_sp']) - float(B[k]['mean_sp']) for k in A if k in B]
        mm = st.mean(d)
        hw = T9 * st.stdev(d) / sqrt(len(d))
        v = 'LOWER' if mm + hw < 0 else 'higher' if mm - hw > 0 else 'n.r.'
        return f"{mm:+6.1f} [{mm - hw:+5.1f},{mm + hw:+5.1f}] {v}"

    L = ["ROUNDABOUT RE-RUN (realistic signalling; 10 seeds; delay with stops charged)", ""]
    for lab in RB_KEYS:
        rb = [r for (c, _, _), d in cell.items() if c == lab for r in d.values()]
        L.append(f"{lab}: contacts (independent checker) in {len(rb)} runs: "
                 f"{sum(int(r['contacts']) for r in rb)} (runs with any: "
                 f"{sum(1 for r in rb if int(r['contacts']) > 0)}); closest moving pair "
                 f"{min(float(r['min_gap_moving']) for r in rb if r['min_gap_moving'] not in ('', None)):.2f} m")
    L += [f"Dominant-split contacts, other controllers: "
          f"{sum(int(r['contacts']) for (c, sp, _), d in cell.items() if sp == 'dominant' and c not in RB_KEYS for r in d.values())}",
          "", "MEAN DELAY (s) [share stopped] {lowest served %}"]
    for sp in SPLITS:
        L.append(f"  {sp}:")
        for c in CTRLS:
            parts = []
            for lam in LAMBDAS:
                if (c, sp, lam) in cell:
                    sv = min(float(r['served_pct']) for r in cell[(c, sp, lam)].values())
                    parts.append(f"{lam}: {m(c, sp, lam):5.1f} [{m(c, sp, lam, 'stop_frac'):4.0%}]"
                                 + (f" {{{sv:.0f}%}}" if sv < 99.5 else ""))
            L.append(f"    {c:27} " + "   ".join(parts))
        L.append("")
    L.append("PAIRED DIFFERENCES (negative = first is lower)")
    for a, b in (('Roundabout', 'Stop sign'), ('Smart Safe, blind', 'Roundabout'),
                 ('Smart Safe, reads signals', 'Roundabout'),
                 ('Roundabout', 'Roundabout (Oct rules)')):
        L.append(f"  {a} vs {b}:")
        for sp in SPLITS:
            L.append(f"    {sp:9} " + "   ".join(f"{lam}: {paired(a, b, sp, lam)}" for lam in LAMBDAS))
    txt = "\n".join(L)
    print(txt)
    open('roundabout_rerun.txt', 'w').write(txt + "\n")


def main():
    jobs = [(rb, sp, lam, rep) for rb in RB_KEYS for sp in SPLITS for lam in LAMBDAS for rep in SEEDS]
    jobs += [(c, 'dominant', lam, rep) for c in CTRLS[:3] for lam in LAMBDAS for rep in SEEDS]
    jobs.sort(key=lambda j: (-j[2], j[0] != 'Smart Safe, blind'))
    rows = []
    with Pool(9) as pool:
        for r in pool.imap_unordered(job, jobs):
            rows.append(r)
            with open('roundabout_rerun.csv', 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(r))
                w.writeheader()
                w.writerows(sorted(rows, key=lambda x: (x['ctrl'], x['split'], x['lam'], x['rep'])))
            print(f"[{len(rows)}/{len(jobs)}] {r['ctrl']:27} {r['split']:9} {r['lam']} rep {r['rep']}: "
                  f"{r['mean_sp']} s, served {r['served_pct']}%, contacts {r['contacts']} ({r['secs']}s)",
                  flush=True)
    summarize([{k: str(v) for k, v in r.items()} for r in rows])


if __name__ == '__main__':
    if '--summarize' in sys.argv:
        summarize(list(csv.DictReader(open('roundabout_rerun.csv'))))
    else:
        main()

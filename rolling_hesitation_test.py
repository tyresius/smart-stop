#!/usr/bin/env python3
"""
Rolling + hesitation factorial (2026-11-11)
==========================================
Question: Smart Safe's only edge over the existing stop sign is letting cars
roll through on the flash (stop_penalty_check.txt). Every earlier hesitation
run also forced a full stop, so we don't know whether a driver who ROLLS but
hesitates keeps that edge. This separates the three factors (audit 1
finding B, FALSIFICATION_PLAN.md Stage 4).

Controllers (all current, corrected versions):
  Smart Safe   BlindSafeV2Hes (blind V2 + tangent headings), conditions:
               H = 0: rolling / full stop
               H = 0.5, 1.0: {rolling, full stop} x {widening on, off}
  Signal       SignalActuated, tangent headings
  Stop sign    HumanFourWayFCFS (rebuilt)
Volumes 400 / 600 / 800 veh/h, both splits, seeds 0-9 (the same arrival
traces for every controller). Primary metric: control_delay_sp (stops
charged); control_delay_hcm reported as a sensitivity. Independent checker
on every run.

HOW THE RESULTS WILL BE READ (fixed before running):
  1. A condition is ADMISSIBLE at a volume and split only if the independent
     checker finds zero contacts between moving cars, and zero between a
     moving car and a car waiting at another approach's line, over all 10
     seeds. Same-lane queue contacts are the known queue-model artifact
     (checker_validation.txt) and don't count.
  2. Widening is a SAFETY REQUIREMENT at H if the widening-off arm is not
     admissible; otherwise it is only a throughput cost.
  3. Rolling KEEPS ITS EDGE at hesitation H (in a cell) if the best
     admissible rolling arm at that H has lower control_delay_sp than the
     rebuilt stop sign, with the paired 95% interval excluding zero.
  4. Nothing here is a pass/kill for the project; it answers the one
     question above. The pass condition in FALSIFICATION_PLAN.md is still
     awaiting revision and approval.

Usage: .venv/bin/python rolling_hesitation_test.py [--workers 9] [--summarize]
Outputs: rolling_hesitation_test.csv / .txt / _events.jsonl
"""
import csv
import json
import statistics as st
import sys
import time
from math import sqrt
from multiprocessing import Pool

import numpy as np

import block3_reality
import hesitation_sweep as hs
import obb_survival_gate as g
from capacity_curves import ALG_MAP, run_stream, make_schedule
from independent_checker import IndependentWatch
from blind_safe_v2 import BlindSafeV2Hes
from stopsign_vs_signal import SignalActuated
from cs4_human_baseline import HumanFourWayFCFS

SPLITS = dict(hs.SPLITS)
LAMBDAS = (400, 600, 800)
SEEDS = range(10)
T_CRIT = {9: 2.262, 8: 2.306, 7: 2.365, 6: 2.447, 5: 2.571, 4: 2.776, 3: 3.182, 2: 4.303, 1: 12.706}
_last = {}


def _wrap(base, name, attrs=None):
    def __init__(self, geometry):
        base.__init__(self, geometry)
        _last['alg'] = self
    cls = type(name, (IndependentWatch, base), dict(attrs or {}, __init__=__init__))
    ALG_MAP[name] = cls
    return name


CONDS = {}      # label -> (ALG_MAP key, H, roll, widen)
for h, roll, widen in [(0.0, True, True), (0.0, False, True),
                       (0.5, True, True), (0.5, True, False), (0.5, False, True), (0.5, False, False),
                       (1.0, True, True), (1.0, True, False), (1.0, False, True), (1.0, False, False)]:
    label = (f"Safe H={h:g} {'rolling' if roll else 'full stop'}"
             + ('' if h == 0 else (' +widen' if widen else ' no-widen')))
    key = _wrap(BlindSafeV2Hes, 'RH_' + label.replace(' ', '_').replace('=', ''),
                {'H_S': h, 'ALLOW_ROLL': roll, 'WIDEN': widen})
    CONDS[label] = (key, h, roll, widen)
CONDS['Signal'] = (_wrap(SignalActuated, 'RH_Signal'), None, None, None)
CONDS['Stop sign'] = (_wrap(HumanFourWayFCFS, 'RH_StopSign'), None, None, None)


def job(args):
    label, split, lam, rep = args
    key = CONDS[label][0]
    g.HEADING_MODE = 'tangent'
    hs.OBBTurnAware.clearance_m = hs.BUFFER
    block3_reality.DWELL_HYPOTHESES = hs.BASE_HYPS
    t0 = time.time()
    res = run_stream(key, make_schedule(lam, rep, split=SPLITS[split]), fair=True)
    vs = res['vehicles']
    sv = [v for v in vs if v['served']]
    s = _last['alg'].ic.summary()

    def m(k):
        return round(float(np.mean([v[k] for v in sv])), 3) if sv else ''
    row = dict(cond=label, split=split, lam=lam, rep=rep,
               mean_sp=m('control_delay_sp'), mean_hcm=m('control_delay_hcm'),
               mean_legacy=m('control_delay'),
               p95_sp=round(float(np.percentile([v['control_delay_sp'] for v in sv], 95)), 2)
               if sv else '',
               stop_frac=round(sum(v['stopped'] for v in sv) / len(sv), 3) if sv else '',
               served_pct=round(len(sv) / len(vs) * 100, 2) if vs else '',
               unreached=res['n_unreached'],
               contacts_moving=s['moving-moving']['contacts'],
               contacts_vs_waiting=s['moving-stopped-cross']['contacts'],
               min_gap_moving=s['moving-moving']['min_gap_m'] if s['moving-moving']['min_gap_m'] is not None else '',
               queue_artifacts=s['moving-stopped-lane']['contacts'],
               secs=round(time.time() - t0))
    events = [dict(e, cond=label, split=split, lam=lam, rep=rep)
              for e in _last['alg'].ic.events
              if e['category'] in ('moving-moving', 'moving-stopped-cross')][:20]
    return row, events


def _paired(a, b):
    keys = sorted(set(a) & set(b))
    d = [a[k] - b[k] for k in keys]
    if len(d) < 2:
        return None
    mm = st.mean(d)
    hw = T_CRIT[len(d) - 1] * st.stdev(d) / sqrt(len(d))
    return mm, mm - hw, mm + hw


def summarize(rows):
    for r in rows:
        for k in ('lam', 'rep', 'contacts_moving', 'contacts_vs_waiting', 'queue_artifacts'):
            r[k] = int(r[k])
        for k in ('mean_sp', 'mean_hcm', 'mean_legacy', 'stop_frac', 'served_pct'):
            r[k] = float(r[k])
    cell = {}
    for r in rows:
        cell.setdefault((r['cond'], r['split'], r['lam']), {})[r['rep']] = r
    safe_labels = [c for c in CONDS if c.startswith('Safe')]

    def admissible(c, sp, lam):
        rs = cell.get((c, sp, lam), {}).values()
        return all(r['contacts_moving'] == 0 and r['contacts_vs_waiting'] == 0 for r in rs)

    L = ["ROLLING + HESITATION FACTORIAL (BlindSafeV2, tangent headings; 10 seeds per cell)",
         "Delay = control_delay_sp (stops charged), mean seconds per car.", ""]
    L.append("1. SAFETY (independent checker): contacts between moving cars / moving vs waiting car")
    for c in list(CONDS):
        tot_m = sum(r['contacts_moving'] for (cc_, _, _), d in cell.items() if cc_ == c for r in d.values())
        tot_w = sum(r['contacts_vs_waiting'] for (cc_, _, _), d in cell.items() if cc_ == c for r in d.values())
        gaps = [float(r['min_gap_moving']) for (cc_, _, _), d in cell.items() if cc_ == c
                for r in d.values() if r['min_gap_moving'] not in ('', None)]
        L.append(f"  {c:32} {tot_m:4} / {tot_w:4}   closest moving pair "
                 f"{min(gaps) if gaps else float('nan'):.2f} m")
    L.append("")
    L.append("2. MEAN DELAY (s) and share of cars that stopped")
    for sp in SPLITS:
        L.append(f"  {sp}:")
        hdr = f"    {'condition':32}" + "".join(f"{lam:>16}" for lam in LAMBDAS)
        L.append(hdr)
        for c in CONDS:
            cells = []
            for lam in LAMBDAS:
                rs = list(cell.get((c, sp, lam), {}).values())
                if not rs:
                    cells.append(f"{'—':>16}")
                    continue
                md = st.mean(r['mean_sp'] for r in rs)
                sf = st.mean(r['stop_frac'] for r in rs)
                flag = '' if admissible(c, sp, lam) else '!'
                cells.append(f"{md:7.1f}{flag:1} ({sf:4.0%})")
            L.append(f"    {c:32}" + "".join(f"{x:>16}" for x in cells))
        L.append("")
    L.append("  ! = not admissible (a contact between moving cars or with a waiting car)")
    L.append("")
    L.append("3. VERSUS THE STOP SIGN AND THE SIGNAL (paired, mean [95% CI]; negative = Smart Safe lower)")
    for sp in SPLITS:
        for lam in LAMBDAS:
            L.append(f"  {sp} {lam} veh/h:")
            for c in safe_labels:
                a = cell.get((c, sp, lam))
                if not a:
                    continue
                parts = []
                for comp in ('Stop sign', 'Signal'):
                    b = cell.get((comp, sp, lam))
                    p = _paired({k: r['mean_sp'] for k, r in a.items()},
                                {k: r['mean_sp'] for k, r in b.items()}) if b else None
                    if p:
                        v = 'LOWER' if p[2] < 0 else 'higher' if p[1] > 0 else 'n.r.'
                        parts.append(f"vs {comp.lower():9} {p[0]:+5.1f} [{p[1]:+5.1f},{p[2]:+5.1f}] {v:6}")
                flag = '' if admissible(c, sp, lam) else '  (not admissible)'
                L.append(f"    {c:32} " + "  ".join(parts) + flag)
        L.append("")
    L.append("4. ANSWERS (reading rules 2 and 3 in the docstring)")
    for h in (0.5, 1.0):
        for roll in (True, False):
            mode = 'rolling' if roll else 'full stop'
            on, off = (f"Safe H={h:g} {mode} +widen", f"Safe H={h:g} {mode} no-widen")
            bad = [(sp, lam) for sp in SPLITS for lam in LAMBDAS if not admissible(off, sp, lam)]
            L.append(f"  H={h:g} {mode}: widening "
                     + (f"IS a safety requirement (no-widen has contacts in {bad})" if bad
                        else "is NOT needed for safety in these runs (no-widen arm admissible)"))
    for h in (0.0, 0.5, 1.0):
        arms = ([f"Safe H=0 rolling"] if h == 0 else
                [f"Safe H={h:g} rolling +widen", f"Safe H={h:g} rolling no-widen"])
        for sp in SPLITS:
            for lam in LAMBDAS:
                best = None
                for arm in arms:
                    if (arm, sp, lam) not in cell or not admissible(arm, sp, lam):
                        continue
                    p = _paired({k: r['mean_sp'] for k, r in cell[(arm, sp, lam)].items()},
                                {k: r['mean_sp'] for k, r in cell[('Stop sign', sp, lam)].items()})
                    if p and (best is None or p[0] < best[1][0]):
                        best = (arm, p)
                if best is None:
                    L.append(f"  H={h:g} {sp:9} {lam}: no admissible rolling arm")
                    continue
                arm, p = best
                verdict = 'KEEPS its edge' if p[2] < 0 else ('LOSES to the stop sign' if p[1] > 0
                                                             else 'no resolved edge')
                L.append(f"  H={h:g} {sp:9} {lam}: rolling {verdict} vs the stop sign "
                         f"({p[0]:+.1f} s [{p[1]:+.1f},{p[2]:+.1f}], best admissible arm: {arm})")
    txt = "\n".join(L)
    print(txt)
    open('rolling_hesitation_test.txt', 'w').write(txt + "\n")


def main():
    workers = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 9
    jobs = [(c, sp, lam, rep) for c in CONDS for lam in LAMBDAS for sp in SPLITS for rep in SEEDS]
    heavy = {c: (CONDS[c][1] or 0) * (0 if CONDS[c][2] else 1) for c in CONDS}
    jobs.sort(key=lambda j: (-j[2], -heavy[j[0]]))          # heaviest first
    rows = []
    with open('rolling_hesitation_test_events.jsonl', 'w') as ev, Pool(workers) as pool:
        for row, events in pool.imap_unordered(job, jobs):
            rows.append(row)
            for e in events:
                ev.write(json.dumps(e) + '\n')
            ev.flush()
            with open('rolling_hesitation_test.csv', 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(row))
                w.writeheader()
                w.writerows(sorted(rows, key=lambda r: (r['cond'], r['split'], r['lam'], r['rep'])))
            print(f"[{len(rows)}/{len(jobs)}] {row['cond']:32} {row['split']:9} {row['lam']} "
                  f"rep {row['rep']}: {row['mean_sp']} s  stopped {row['stop_frac']}  "
                  f"contacts {row['contacts_moving']}/{row['contacts_vs_waiting']} ({row['secs']}s)",
                  flush=True)
    summarize([{k: str(v) for k, v in r.items()} for r in rows])


if __name__ == '__main__':
    if '--summarize' in sys.argv:
        summarize(list(csv.DictReader(open('rolling_hesitation_test.csv'))))
    else:
        main()

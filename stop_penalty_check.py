#!/usr/bin/env python3
"""
What does charging for stops change? (2026-11-11)
================================================
One change at a time: the controllers here are the committed legacy ones
(signal, legacy BlindSafe, secant headings) plus the rebuilt stop sign, on
the committed arrival seeds. Only the delay accounting differs:

  legacy   `control_delay`      stopping costs nothing (cars appear at the line)
  sp       `control_delay_sp`   braking + acceleration loss charged per stop
                                (this model's speeds: 1.6-3.0 s per stop)
  hcm      `control_delay_hcm`  each stop scaled to HCM's 5 s allowance
                                (faster real-world approaches)

The legacy column must reproduce hesitation_sweep.csv exactly (checked).
Smart Safe V2 / tangent headings are the separate re-baseline (step 5).

Usage: .venv/bin/python stop_penalty_check.py [--summarize]
Outputs: stop_penalty_check.csv, stop_penalty_check.txt
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
import cs4_human_baseline  # noqa: F401  (registers HumanFourWayFCFS)
from capacity_curves import run_stream, make_schedule

SPLITS = dict(hs.SPLITS)
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571}
CONDS = [  # (label, ALG_MAP key, hesitation, volumes)
    ('Signal', 'HS_Signal', 0.0, (400, 600, 800, 1000)),
    ('Safe rolling (H=0)', 'HS_Blind', 0.0, (400, 600, 800, 1000)),
    ('Safe full stop', 'HS_Blind', 'stop', (400, 600, 800)),
    ('Safe H=0.5', 'HS_Blind', 0.5, (400, 600, 800)),
    ('Stop sign (rebuilt)', 'HumanFourWayFCFS', 0.0, (400, 600, 800, 1000)),
]
COMMITTED_KEY = {'Signal': ('Signal', ''), 'Safe rolling (H=0)': ('Smart Safe (blind)', '0.0'),
                 'Safe full stop': ('Smart Safe (blind)', 'stop'),
                 'Safe H=0.5': ('Smart Safe (blind)', '0.5')}


def job(args):
    label, key, h, split, lam, rep = args
    g.HEADING_MODE = 'secant'
    hs.OBBTurnAware.clearance_m = hs.BUFFER
    hs.BlindSafe.NO_ROLL = (h == 'stop')
    hh = 0.0 if h == 'stop' else h
    hs.BlindSafe.HESITATION_S = hh
    b = hs.BASE_HYPS
    block3_reality.DWELL_HYPOTHESES = (b[0], b[1] + hh / 2, b[2] + hh)
    t0 = time.time()
    res = run_stream(key, make_schedule(lam, rep, split=SPLITS[split]), fair=True)
    vs = res['vehicles']
    sv = [v for v in vs if v['served']]

    def m(k):
        return round(float(np.mean([v[k] for v in sv])), 3) if sv else ''
    return dict(cond=label, split=split, lam=lam, rep=rep,
                mean_legacy=m('control_delay'), mean_sp=m('control_delay_sp'),
                mean_hcm=m('control_delay_hcm'),
                p95_sp=round(float(np.percentile([v['control_delay_sp'] for v in sv], 95)), 2)
                if sv else '',
                stop_frac=round(sum(v['stopped'] for v in sv) / len(sv), 3) if sv else '',
                served_pct=round(len(sv) / len(vs) * 100, 2) if vs else '',
                secs=round(time.time() - t0))


def paired(a, b):
    keys = sorted(set(a) & set(b))
    d = [a[k] - b[k] for k in keys]
    if len(d) < 2:
        return None
    mm = st.mean(d)
    hw = T975[len(d) - 1] * st.stdev(d) / sqrt(len(d))
    v = 'lower' if mm + hw < 0 else 'higher' if mm - hw > 0 else 'n.r.'
    return f"{mm:+6.1f} [{mm - hw:+5.1f},{mm + hw:+5.1f}] {v:6}"


def summarize(rows):
    com = {}
    for r in csv.DictReader(open('hesitation_sweep.csv')):
        com[(r['alg'], r['hesitation'], r['split'], int(r['lam']), int(r['rep']))] = float(r['mean_delay'])
    cell = {}
    for r in rows:
        cell.setdefault((r['cond'], r['split'], int(r['lam'])), {})[int(r['rep'])] = r
    bad = [r for r in rows if r['cond'] in COMMITTED_KEY
           and (COMMITTED_KEY[r['cond']] + (r['split'], int(r['lam']), int(r['rep']))) in com
           and abs(float(r['mean_legacy']) - com[COMMITTED_KEY[r['cond']]
                                                 + (r['split'], int(r['lam']), int(r['rep']))]) > 0.01]
    L = ["STOP PENALTY CHECK (legacy controllers, committed seeds; 5 seeds per cell)", "",
         f"Legacy delays reproduce hesitation_sweep.csv: {'yes' if not bad else f'NO ({len(bad)} runs differ)'}",
         "", "Mean control delay (s): legacy -> with stop penalty (sp) -> HCM-scaled (hcm); "
         "share of cars that stopped", ""]
    for sp in SPLITS:
        L.append(f"{sp}:")
        for lam in (400, 600, 800, 1000):
            for label, *_ in CONDS:
                rs = list(cell.get((label, sp, lam), {}).values())
                if not rs:
                    continue
                f = lambda k: st.mean(float(r[k]) for r in rs)
                L.append(f"  {lam:5} {label:20} {f('mean_legacy'):6.1f} -> {f('mean_sp'):6.1f}"
                         f" -> {f('mean_hcm'):6.1f}   stopped {f('stop_frac'):4.0%}"
                         f"   served {min(float(r['served_pct']) for r in rs):.0f}%")
        L.append("")
    L += ["Paired differences, mean [95% CI], first minus second; 'lower' = first has less delay", ""]
    pairs = [('Safe rolling (H=0)', 'Signal'), ('Safe full stop', 'Signal'),
             ('Safe H=0.5', 'Signal'), ('Stop sign (rebuilt)', 'Signal'),
             ('Safe rolling (H=0)', 'Stop sign (rebuilt)'),
             ('Safe full stop', 'Stop sign (rebuilt)'), ('Safe H=0.5', 'Stop sign (rebuilt)')]
    for metric, name in (('mean_legacy', 'legacy (no stop cost)'),
                         ('mean_sp', 'with stop penalty'), ('mean_hcm', 'HCM-scaled stops')):
        L.append(f"-- {name} --")
        for sp in SPLITS:
            for lam in (400, 600, 800, 1000):
                for a, b in pairs:
                    ca, cb = cell.get((a, sp, lam)), cell.get((b, sp, lam))
                    if not (ca and cb):
                        continue
                    p = paired({k: float(r[metric]) for k, r in ca.items()},
                               {k: float(r[metric]) for k, r in cb.items()})
                    if p:
                        L.append(f"  {sp:9} {lam:5}  {a:20} vs {b:20} {p}")
            L.append("")
    txt = "\n".join(L)
    print(txt)
    open('stop_penalty_check.txt', 'w').write(txt + "\n")


def main():
    jobs = [(label, key, h, sp, lam, rep) for label, key, h, lams in CONDS
            for lam in lams for sp in SPLITS for rep in range(5)]
    jobs.sort(key=lambda j: (-j[4], j[0] == 'Stop sign (rebuilt)'))   # heavy first
    rows = []
    with Pool(8) as pool:
        for r in pool.imap_unordered(job, jobs):
            rows.append(r)
            with open('stop_penalty_check.csv', 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(r))
                w.writeheader()
                w.writerows(sorted(rows, key=lambda x: (x['cond'], x['split'], x['lam'], x['rep'])))
            print(f"{r['cond']:20} {r['split']:9} {r['lam']:5} rep {r['rep']}: "
                  f"{r['mean_legacy']} -> {r['mean_sp']} -> {r['mean_hcm']} "
                  f"stopped {r['stop_frac']} ({r['secs']}s)", flush=True)
    summarize(rows)


if __name__ == '__main__':
    if '--summarize' in sys.argv:
        summarize(list(csv.DictReader(open('stop_penalty_check.csv'))))
    else:
        main()

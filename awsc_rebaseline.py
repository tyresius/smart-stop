#!/usr/bin/env python3
"""
All-way stop re-baseline: does the rebuilt stop sign change the picture?
=======================================================================
(audit 3 step 1 follow-up, 2026-11-11)

Runs the legacy `HumanFourWay` and the rebuilt `HumanFourWayFCFS` on the
SAME arrival seeds as the committed hesitation sweep (400-1,200 veh/h, both
splits, 5 seeds), with the independent checker attached, then pairs the
rebuilt stop sign against the committed signal and Smart Safe cells.

Caveats that travel with these numbers:
  - Smart Safe and the signal figures are the committed legacy runs (secant
    headings, legacy BlindSafe). Their re-baseline is a separate step.
  - The stop sign uses a different queue model from the platoon controllers
    (2 s move-up per car vs a virtual queue; audit 3 F7). That matters more as
    queues grow.
  - At saturation the rebuilt stop sign is still 12-65% SLOWER than HCM
    headways (awsc_calibration.txt), so at high volume it is, if anything,
    pessimistic.

Usage: .venv/bin/python awsc_rebaseline.py -> awsc_rebaseline.csv / .txt
"""
import csv
import statistics as st
import time
from math import sqrt
from multiprocessing import Pool

import numpy as np

import hesitation_sweep as hs
from capacity_curves import ALG_MAP, run_stream, make_schedule
from independent_checker import IndependentWatch
from cs4_human_baseline import HumanFourWay, HumanFourWayFCFS

SPLITS = dict(hs.SPLITS)
LAMBDAS = [400, 600, 800, 1000, 1200]
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571}
_last = {}


def _wrap(base):
    def __init__(self, geometry):
        base.__init__(self, geometry)
        _last['alg'] = self
    return type(base.__name__ + 'RB', (IndependentWatch, base), {'__init__': __init__})


ALG_MAP['RB_legacy'] = _wrap(HumanFourWay)
ALG_MAP['RB_FCFS'] = _wrap(HumanFourWayFCFS)
LABEL = {'RB_legacy': 'AWSC legacy', 'RB_FCFS': 'AWSC FCFS'}


def job(args):
    key, split, lam, rep = args
    t0 = time.time()
    res = run_stream(key, make_schedule(lam, rep, split=SPLITS[split]), fair=True)
    vs = res['vehicles']
    served = [v for v in vs if v['served']]
    d = [v['control_delay'] for v in served]
    s = _last['alg'].ic.summary()
    return dict(alg=LABEL[key], split=split, lam=lam, rep=rep,
                mean_delay=round(float(np.mean(d)), 2) if d else '',
                p95_delay=round(float(np.percentile(d, 95)), 2) if d else '',
                served_pct=round(len(served) / len(vs) * 100, 2) if vs else '',
                unreached=res['n_unreached'],
                contacts_moving=s['moving-moving']['contacts'],
                contacts_vs_waiting=s['moving-stopped-cross']['contacts'],
                secs=round(time.time() - t0))


def paired(a, b):
    """Mean of a - b over common seeds, 95% t-interval, verdict."""
    keys = sorted(set(a) & set(b))
    d = [a[k] - b[k] for k in keys]
    if len(d) < 2:
        return None
    m = st.mean(d)
    hw = T975[len(d) - 1] * st.stdev(d) / sqrt(len(d))
    verdict = ('lower' if m + hw < 0 else 'higher' if m - hw > 0 else 'not resolved')
    return len(d), m, m - hw, m + hw, verdict


def main():
    jobs = [(k, sp, lam, rep) for lam in reversed(LAMBDAS) for sp in SPLITS
            for k in ('RB_FCFS', 'RB_legacy') for rep in range(5)]
    with Pool(8) as pool:
        rows = pool.map(job, jobs)
    rows.sort(key=lambda r: (r['alg'], r['split'], r['lam'], r['rep']))
    with open('awsc_rebaseline.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    com = {}
    for r in csv.DictReader(open('hesitation_sweep.csv')):
        label = 'Signal' if r['alg'] == 'Signal' else f"Safe {r['hesitation']}"
        com.setdefault((r['split'], int(r['lam']), label), {})[int(r['rep'])] = float(r['mean_delay'])
    aw = {}
    for r in rows:
        aw.setdefault((r['split'], r['lam'], r['alg']), {})[r['rep']] = r['mean_delay']

    L = ["ALL-WAY STOP RE-BASELINE (same arrival seeds as hesitation_sweep.csv)", "",
         "Mean control delay (s), 5 seeds; served %; contacts found by the independent checker", ""]
    for sp in SPLITS:
        L.append(f"{sp}:")
        for lam in LAMBDAS:
            parts = []
            for alg in ('AWSC legacy', 'AWSC FCFS'):
                rs = [r for r in rows if r['split'] == sp and r['lam'] == lam and r['alg'] == alg]
                md = st.mean(r['mean_delay'] for r in rs)
                sv = min(r['served_pct'] for r in rs)
                ct = sum(r['contacts_moving'] + r['contacts_vs_waiting'] for r in rs)
                parts.append(f"{alg} {md:6.1f} ({sv:.0f}% served, {ct} contacts)")
            L.append(f"  {lam:5}: " + " | ".join(parts))
        L.append("")
    L += ["Rebuilt stop sign (FCFS) minus each committed alternative, paired by seed:",
          "(negative = the plain stop sign has LOWER delay)", ""]
    for sp in SPLITS:
        for lam in LAMBDAS:
            fc = aw[(sp, lam, 'AWSC FCFS')]
            for label, name in (('Signal', 'signal'), ('Safe 0.0', 'Safe H=0 rolling'),
                                ('Safe stop', 'Safe full stop'), ('Safe 0.5', 'Safe H=0.5'),
                                ('Safe 1.0', 'Safe H=1')):
                other = com.get((sp, lam, label))
                if not other:
                    continue
                p = paired(fc, other)
                if p:
                    n, m, lo, hi, v = p
                    L.append(f"  {sp:9} {lam:5}  vs {name:17} n={n}  {m:+7.1f} s  "
                             f"[{lo:+6.1f}, {hi:+6.1f}]  stop sign {v}")
        L.append("")
    txt = "\n".join(L)
    print(txt)
    open('awsc_rebaseline.txt', 'w').write(txt + "\n")


if __name__ == '__main__':
    main()

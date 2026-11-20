#!/usr/bin/env python3
"""
Independent-checker validation run (audit 3 steps 1-3, 2026-11-11)
===================================================================
A. LEGACY RE-CHECK. Re-runs the committed hesitation-sweep cells nearest the
   crossover (800 and 1,000 veh/h, both splits, 5 seeds, H = 0) for the
   actuated signal and legacy BlindSafe, unchanged, with the independent
   checker attached. Delays must reproduce the committed CSV exactly (the
   checker only observes); the checker then says whether "no overlaps
   observed" survives every pair, waiting cars and between-step contact.
B. V2 SMOKE (not a result). BlindSafeV2 and the signal with tangent headings,
   2 seeds at the same cells: does the fixed controller run cleanly and stay
   contact-free? The re-baseline itself is step 5.
C. ALL-WAY STOP. Legacy HumanFourWay vs rebuilt HumanFourWayFCFS at 600
   veh/h, both splits, 5 seeds, with the checker (human rules must not crash
   cars either).

Usage: .venv/bin/python checker_validation.py [--workers 8]
Outputs: checker_validation.csv, checker_validation_events.jsonl,
         checker_validation.txt (summary)
"""
import csv
import json
import sys
import time
from multiprocessing import Pool

import numpy as np

import block3_reality
import hesitation_sweep as hs
import obb_survival_gate as g
from capacity_curves import ALG_MAP, run_stream, make_schedule
from obb_survival_gate import OBBWatch
from independent_checker import IndependentWatch, ContactMonitor
from stopsign_vs_signal import SignalActuated
from blind_safe_v2 import BlindSafeV2
from cs4_human_baseline import HumanFourWay, HumanFourWayFCFS

SPLITS = dict(hs.SPLITS)
BASE_HYPS = hs.BASE_HYPS
_last = {}


def _wrap(base):
    def __init__(self, geometry):
        base.__init__(self, geometry)
        _last['alg'] = self
    return type(base.__name__ + 'CV', (IndependentWatch, OBBWatch, base),
                {'__init__': __init__})


ALG_MAP['CV_Signal'] = _wrap(SignalActuated)
ALG_MAP['CV_Blind'] = _wrap(hs.BlindSafe)
ALG_MAP['CV_BlindV2'] = _wrap(BlindSafeV2)
ALG_MAP['CV_AWSC_legacy'] = _wrap(HumanFourWay)
ALG_MAP['CV_AWSC_FCFS'] = _wrap(HumanFourWayFCFS)
LABEL = {'CV_Signal': 'Signal', 'CV_Blind': 'Smart Safe (blind)',
         'CV_BlindV2': 'Smart Safe V2', 'CV_AWSC_legacy': 'AWSC legacy',
         'CV_AWSC_FCFS': 'AWSC FCFS'}
SHORT = {'moving-moving': 'mm', 'moving-stopped-cross': 'msx',
         'moving-stopped-lane': 'msl', 'stopped-stopped': 'ss'}


def committed():
    out = {}
    for r in csv.DictReader(open('hesitation_sweep.csv')):
        if r['alg'] == 'Signal' or r['hesitation'] == '0.0':
            out[(r['split'], int(r['lam']), int(r['rep']), r['alg'])] = float(r['mean_delay'])
    return out


def job(args):
    part, akey, split, lam, rep, heading = args
    g.HEADING_MODE = heading
    hs.OBBTurnAware.clearance_m = hs.BUFFER
    hs.BlindSafe.NO_ROLL = False
    hs.BlindSafe.HESITATION_S = 0.0
    block3_reality.DWELL_HYPOTHESES = BASE_HYPS
    t0 = time.time()
    res = run_stream(akey, make_schedule(lam, rep, split=SPLITS[split]), fair=True)
    alg = _last['alg']
    vs = res['vehicles']
    served = [v for v in vs if v['served']]
    d = [v['control_delay'] for v in served]
    pairs = getattr(alg, 'obb_pairs', {})
    ic = getattr(alg, 'ic', ContactMonitor())
    summ = ic.summary()
    row = dict(part=part, alg=LABEL[akey], split=split, lam=lam, rep=rep,
               heading=heading,
               mean_delay=round(float(np.mean(d)), 2) if d else '',
               p95_delay=round(float(np.percentile(d, 95)), 2) if d else '',
               served_pct=round(len(served) / len(vs) * 100, 2) if vs else '',
               old_observer_overlaps=sum(1 for r in pairs.values() if r),
               ic_pairs_checked=ic.pairs_checked, secs=round(time.time() - t0))
    for cat, s in summ.items():
        k = SHORT[cat]
        row[f'ic_{k}_contacts'] = s['contacts']
        row[f'ic_{k}_near'] = s['near']
        row[f'ic_{k}_min_gap_m'] = s['min_gap_m'] if s['min_gap_m'] is not None else ''
    events = [dict(e, part=part, alg=LABEL[akey], split=split, lam=lam, rep=rep)
              for e in ic.events if e['category'] != 'moving-stopped-lane'][:50]
    lane = [e for e in ic.events if e['category'] == 'moving-stopped-lane'][:5]
    events += [dict(e, part=part, alg=LABEL[akey], split=split, lam=lam, rep=rep)
               for e in lane]
    return row, events


def main():
    workers = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 8
    jobs = []
    for lam in (1000, 800):                                   # heavy first
        for sp in ('balanced', 'arterial'):
            for rep in range(5):
                jobs += [('A', 'CV_Signal', sp, lam, rep, 'secant'),
                         ('A', 'CV_Blind', sp, lam, rep, 'secant')]
            for rep in range(2):
                jobs += [('B', 'CV_BlindV2', sp, lam, rep, 'tangent'),
                         ('B', 'CV_Signal', sp, lam, rep, 'tangent')]
    for sp in ('balanced', 'arterial'):
        for rep in range(5):
            jobs += [('C', 'CV_AWSC_legacy', sp, 600, rep, 'secant'),
                     ('C', 'CV_AWSC_FCFS', sp, 600, rep, 'secant')]
    rows = []
    fields = None
    with open('checker_validation_events.jsonl', 'w') as ev_out, Pool(workers) as pool:
        for row, events in pool.imap_unordered(job, jobs):
            rows.append(row)
            for e in events:
                ev_out.write(json.dumps(e) + '\n')
            ev_out.flush()
            fields = fields or list(row.keys())
            with open('checker_validation.csv', 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerows(sorted(rows, key=lambda r: (r['part'], r['alg'], r['split'],
                                                        r['lam'], r['rep'])))
            print(f"{row['part']} {row['alg']:18} {row['split']:9} {row['lam']:5} "
                  f"rep {row['rep']} {row['heading']:7}: {row['mean_delay']}s "
                  f"mm={row['ic_mm_contacts']} msx={row['ic_msx_contacts']} "
                  f"msl={row['ic_msl_contacts']} ({row['secs']}s)", flush=True)
    summarize(rows)


def summarize(rows):
    com = committed()
    lines = ["CHECKER VALIDATION SUMMARY", ""]
    for part, title in (('A', 'A. Legacy re-check (committed cells, H=0, secant headings)'),
                        ('B', 'B. V2 smoke (2 seeds, tangent headings) - not a result'),
                        ('C', 'C. All-way stop, 600 veh/h')):
        lines.append(title)
        grp = {}
        for r in rows:
            if r['part'] == part:
                grp.setdefault((r['alg'], r['split'], r['lam']), []).append(r)
        for (alg, sp, lam), rs in sorted(grp.items()):
            md = np.mean([r['mean_delay'] for r in rs])
            tot = {k: sum(r[f'ic_{k}_contacts'] for r in rs) for k in SHORT.values()}
            mins = {k: min((r[f'ic_{k}_min_gap_m'] for r in rs
                            if r[f'ic_{k}_min_gap_m'] != ''), default='-')
                    for k in SHORT.values()}
            extra = ''
            if part == 'A':
                key_alg = 'Signal' if alg == 'Signal' else 'Smart Safe (blind)'
                have = [r for r in rs if (sp, lam, r['rep'], key_alg) in com]
                match = all(abs(r['mean_delay'] - com[(sp, lam, r['rep'], key_alg)]) < 0.01
                            for r in have)
                extra = (f" | reproduces committed delays: {'yes' if match else 'NO'}"
                         f" ({len(have)} of {len(rs)} seeds have a committed run)")
            lines.append(
                f"  {alg:18} {sp:9} {lam:5} n={len(rs)} delay {md:6.1f}s | contacts "
                f"moving-moving {tot['mm']} (min gap {mins['mm']}), "
                f"moving-vs-waiting cross {tot['msx']} (min {mins['msx']}), "
                f"same-lane queue {tot['msl']}, old observer "
                f"{sum(r['old_observer_overlaps'] for r in rs)}{extra}")
        lines.append("")
    txt = "\n".join(lines)
    print(txt)
    open('checker_validation.txt', 'w').write(txt + "\n")


if __name__ == '__main__':
    if '--summarize' in sys.argv:
        rows = list(csv.DictReader(open('checker_validation.csv')))
        for r in rows:
            for k, v in r.items():
                if k.startswith('ic_') or k in ('lam', 'rep', 'old_observer_overlaps'):
                    r[k] = int(v) if v not in ('',) and '.' not in v else (float(v) if v else '')
                elif k in ('mean_delay',):
                    r[k] = float(v)
        summarize(rows)
    else:
        main()

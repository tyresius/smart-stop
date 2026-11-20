#!/usr/bin/env python3
"""Paired confidence intervals for the verdict-bearing hesitation sweep.

Signal and Smart Safe runs with the same (split, veh/h, rep) share one arrival
schedule (`make_schedule(lam, rep)`), so each seed gives a paired difference
Safe - Signal in mean control delay. This prints the mean difference and a
95% t-interval per cell, and says whether the cell is resolved.

Caveats: 3-5 seeds per cell, t-interval assumes roughly normal differences,
no correction for testing many cells at once. Added 2026-11-09 in response to
external audit 1 ("paired-seed confidence intervals, not just means").

Usage: .venv/bin/python paired_ci_check.py   (reads hesitation_sweep.csv)
"""
import csv
import statistics as st
from math import sqrt

T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571}   # t(0.975, df)
CONDS = [('0.0', 'H=0'), ('stop', 'full stop'), ('0.5', 'H=0.5'),
         ('1.0', 'H=1'), ('2.0', 'H=2')]


def main(path='hesitation_sweep.csv'):
    rows = list(csv.DictReader(open(path)))
    sig = {(r['split'], int(r['lam']), r['rep']): float(r['mean_delay'])
           for r in rows if r['alg'] == 'Signal' and r['mean_delay']}
    print('Smart Safe (blind) minus Signal, mean control delay (s), paired by seed')
    print(f"{'split':9}{'veh/h':>6}  {'condition':10}{'n':>2}  "
          f"{'mean diff':>9}  {'95% CI':>17}  result")
    for sl in ('balanced', 'arterial'):
        for lam in (400, 600, 800, 1000, 1200):
            for h, label in CONDS:
                d = [float(r['mean_delay']) - sig[(sl, lam, r['rep'])]
                     for r in rows
                     if r['alg'] != 'Signal' and r['split'] == sl
                     and int(r['lam']) == lam and r['hesitation'] == h
                     and r['mean_delay'] and (sl, lam, r['rep']) in sig]
                if len(d) < 2:
                    continue
                m = st.mean(d)
                hw = T975[len(d) - 1] * st.stdev(d) / sqrt(len(d))
                res = ('Safe wins' if m + hw < 0 else
                       'Safe loses' if m - hw > 0 else 'not resolved')
                print(f"{sl:9}{lam:6}  {label:10}{len(d):2}  {m:+9.1f}  "
                      f"[{m - hw:+6.1f}, {m + hw:+6.1f}]  {res}")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Queue-model sensitivity (audit 3 F7, 2026-11-15)
================================================
The stop sign uses the harness's physical-ish queue: the next car reaches the
line MOVE_UP_TIME (2 s) after the car ahead starts. Smart Safe and the signal
use a virtual queue: every queued car is available at the line at once. That
asymmetry could flatter Smart Safe.

Bound it: re-run the stop sign (realistic signalling, from
fair_signalling_test.py) with MOVE_UP_TIME = 0, i.e. the same instant queue
Smart Safe gets, and pair it with the committed Smart Safe runs (same seeds).
If Smart Safe still wins, the queue model doesn't drive the result.

Usage: .venv/bin/python moveup_sensitivity.py -> moveup_sensitivity.txt
"""
import csv
import statistics as st
from math import sqrt
from multiprocessing import Pool

import numpy as np

import capacity_curves as cc
import fair_signalling_test as fst

T9 = 2.262


def job(args):
    split, lam, rep, moveup = args
    cc.MOVE_UP_TIME = moveup
    row, _ = fst.job(('Stop sign', 'realistic', split, lam, rep))
    return split, lam, rep, moveup, row['mean_sp'], row['contacts']


def main():
    jobs = [(sp, lam, rep, mu) for sp in fst.SPLITS for lam in fst.LAMBDAS
            for rep in fst.SEEDS for mu in (2.0, 0.0)]
    with Pool(9) as pool:
        res = pool.map(job, jobs)
    stop = {(sp, lam, rep, mu): d for sp, lam, rep, mu, d, _ in res}
    contacts = sum(c for *_, c in res)
    safe = {}
    for r in csv.DictReader(open('fair_signalling_test.csv')):
        if r['regime'] in ('realistic', 'any'):
            safe[(r['ctrl'], r['split'], int(r['lam']), int(r['rep']))] = float(r['mean_sp'])
    L = ["QUEUE-MODEL SENSITIVITY: stop sign with the 2 s move-up vs an instant queue",
         "(realistic signalling; 10 seeds; delay with stops charged)", "",
         f"Stop-sign contacts, all runs: {contacts}", ""]
    for sp in fst.SPLITS:
        L.append(f"{sp}:")
        for lam in fst.LAMBDAS:
            m2 = st.mean(stop[(sp, lam, r, 2.0)] for r in fst.SEEDS)
            m0 = st.mean(stop[(sp, lam, r, 0.0)] for r in fst.SEEDS)
            parts = [f"stop sign {m2:5.1f} -> {m0:5.1f} with instant queue"]
            for ctrl in ('Smart Safe, reads signals', 'Smart Safe, blind'):
                d = [safe[(ctrl, sp, lam, r)] - stop[(sp, lam, r, 0.0)] for r in fst.SEEDS]
                m = st.mean(d)
                hw = T9 * st.stdev(d) / sqrt(len(d))
                v = 'LOWER' if m + hw < 0 else 'higher' if m - hw > 0 else 'n.r.'
                parts.append(f"{ctrl.split(', ')[1]} minus it {m:+5.1f} [{m - hw:+5.1f},{m + hw:+5.1f}] {v}")
            L.append(f"  {lam:5}: " + " | ".join(parts))
        L.append("")
    txt = "\n".join(L)
    print(txt)
    open('moveup_sensitivity.txt', 'w').write(txt + "\n")


if __name__ == '__main__':
    main()

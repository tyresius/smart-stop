#!/usr/bin/env python3
"""
Controller compute timing (2026-11-15)
======================================
CPU time (time.thread_time, so machine load and preemption don't distort it)
of one 0.1 s controller step (decision logic plus the model's
vehicle physics, which the step also advances) for the two Smart Safe designs,
at 800 veh/h balanced, 25% non-signalling, no deception, seeds 0-2.
No independent checker attached (it is an observer, not part of the controller).

Plain, unoptimised, single-threaded Python. Indicative only: the numbers include
simulation bookkeeping a deployed controller would not do, and exclude
perception (camera processing), which a deployed controller would.

Usage: .venv/bin/python compute_timing.py -> compute_timing.txt
"""
import platform
import statistics as st
import time
from multiprocessing import Pool

import numpy as np

import block3_reality
import obb_survival_gate as g
import hesitation_sweep as hs
import fair_signalling_test as fs
from capacity_curves import run_stream, make_schedule, ALG_MAP

LAM, SPLIT, SEEDS = 800.0, 'balanced', (0, 1, 2)
_times = {}


def _timed(name, base, attrs):
    def step(self, dt=0.1):
        t0 = time.thread_time()
        out = base.step(self, dt)
        _times.setdefault(name, []).append(time.thread_time() - t0)
        return out
    ALG_MAP[name] = type(name, (base,), dict(attrs, step=step))
    return name


DESIGNS = {
    'Smart Safe, blind': _timed('CT_blind', fs.SafeBlind, {}),
    'Smart Safe, reads signals': _timed('CT_read', fs.SafeReadsSignals,
                                        {'NONE_Q': 0.25, 'FALSE_Q': 0.0}),
}


def job(args):
    name, rep = args
    g.HEADING_MODE = 'tangent'
    hs.OBBTurnAware.clearance_m = hs.BUFFER
    block3_reality.DWELL_HYPOTHESES = hs.BASE_HYPS
    _times.clear()
    run_stream(name, make_schedule(LAM, rep, split=fs.SPLITS[SPLIT]), fair=True)
    return name, _times[name]


def main():
    with Pool(len(SEEDS) * len(DESIGNS)) as pool:
        for name, t in pool.map(job, [(n, r) for n in DESIGNS.values() for r in SEEDS]):
            _times.setdefault('all_' + name, []).extend(t)
    L = [f"CONTROLLER STEP TIME (ms per 0.1 s step; {LAM:.0f} veh/h {SPLIT}, seeds "
         f"{SEEDS[0]}-{SEEDS[-1]}, 25% non-signalling)",
         f"Python {platform.python_version()} on {platform.machine()} "
         f"({platform.system()}); CPU time per step (thread_time), unoptimised", "",
         f"{'design':28} {'steps':>7} {'median':>8} {'p99':>8} {'max':>8} {'budget':>8}"]
    for label, name in DESIGNS.items():
        x = np.array(_times['all_' + name]) * 1000
        L.append(f"{label:28} {len(x):7d} {st.median(x):8.2f} {np.percentile(x, 99):8.1f} "
                 f"{x.max():8.1f} {100:8d}")
    L += ["", "Includes vehicle physics and simulation bookkeeping; excludes camera",
          "processing. Indicative of order of magnitude only."]
    txt = "\n".join(L)
    print(txt)
    open('compute_timing.txt', 'w').write(txt + "\n")


if __name__ == '__main__':
    main()

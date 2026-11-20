#!/usr/bin/env python3
"""
All-way-stop calibration against HCM saturation headways (audit 3, 2026-11-11)
==============================================================================
Saturates one, two or four approaches and measures the mean departure
headway (time between successive cars from the same approach starting to
move) for the legacy `HumanFourWay` and the rebuilt `HumanFourWayFCFS`, both
with its first rule ('box': wait until the other car has left the whole
box) and its adopted rule ('conflict': wait until it has passed your
conflict area).

HCM reference (6th ed., ch. 21, geometry group 1 = single-lane approaches),
base saturation headways by degree-of-conflict case: 1: 3.9 s, 2: 4.7 s,
3: 5.8 s, 4: 7.0 s, 5: 9.6 s. Turn adjustment +0.2 x P(left) - 0.6 x P(right)
= -0.06 s for this model's 15% / 70% / 15% mix. The configurations map
roughly onto cases 1, 2, 3 and 5; HCM's own method averages over case
probabilities, so treat this as a sanity check, not a fit.

Usage: .venv/bin/python awsc_calibration.py   (~5 min) -> awsc_calibration.txt
"""
import statistics as st
import sys
from multiprocessing import Pool

import capacity_curves as cc
from capacity_curves import ALG_MAP, run_stream, make_schedule
from cs4_human_baseline import HumanFourWay, HumanFourWayFCFS

ADJ = 0.2 * 0.15 - 0.6 * 0.15
CONFIGS = [  # (label, split over ROADS = Main E, Main W, Green N, Green S, HCM case, base)
    ('one approach', [1.0, 0.0, 0.0, 0.0], 1, 3.9),
    ('two opposing', [0.5, 0.5, 0.0, 0.0], 2, 4.7),
    ('two perpendicular', [0.5, 0.0, 0.5, 0.0], 3, 5.8),
    ('all four', [0.25, 0.25, 0.25, 0.25], 5, 9.6),
]
DEMAND = 2400          # veh/h total: every loaded approach is oversaturated
REPS = 2
_last = {}


def _logged(base):
    def __init__(self, geometry):
        base.__init__(self, geometry)
        self.departures = []
        self._dep_seen = set()
        _last['alg'] = self

    def step(self, dt=0.1):
        status = base.step(self, dt)
        for v in self.active_vehicles:
            if id(v) not in self._dep_seen and v.current_position_meters > 0.0:
                self._dep_seen.add(id(v))
                self.departures.append((v.road_name, self.current_time))
        return status
    return type(base.__name__ + 'Log', (base,), {'__init__': __init__, 'step': step})


ALG_MAP['CAL_Legacy'] = _logged(HumanFourWay)
ALG_MAP['CAL_FCFS'] = _logged(HumanFourWayFCFS)
ALG_MAP['CAL_FCFS_box'] = _logged(type('HumanFourWayFCFSBox', (HumanFourWayFCFS,),
                                       {'CLEAR_RULE': 'box'}))


def job(args):
    key, label, split, rep = args
    run_stream(key, make_schedule(DEMAND, rep, split=split), fair=True)
    deps = _last['alg'].departures
    lo, hi = cc.T_WARMUP, cc.T_WARMUP + cc.T_MEASURE
    hw = []
    for road in cc.ROADS:
        ts = [t for r, t in deps if r == road and lo <= t <= hi]
        hw += [b - a for a, b in zip(ts, ts[1:])]
    return key, label, rep, hw


def main():
    jobs = [(k, lab, sp, rep) for k in ('CAL_Legacy', 'CAL_FCFS_box', 'CAL_FCFS')
            for lab, sp, _, _ in CONFIGS for rep in range(REPS)]
    with Pool(8) as pool:
        res = pool.map(job, jobs)
    agg = {}
    for key, lab, rep, hw in res:
        agg.setdefault((key, lab), []).extend(hw)
    lines = ["Mean departure headway per approach under saturation (s)",
             f"{DEMAND} veh/h offered, {REPS} seeds, measured {cc.T_WARMUP:.0f}-"
             f"{cc.T_WARMUP + cc.T_MEASURE:.0f} s",
             "",
             f"{'configuration':20} {'HCM case':>8} {'HCM':>6} {'legacy':>8} "
             f"{'box rule':>9} {'conflict':>9}   (n per column)"]
    for lab, _, case, base in CONFIGS:
        a, b, c = (agg[(k, lab)] for k in ('CAL_Legacy', 'CAL_FCFS_box', 'CAL_FCFS'))
        lines.append(f"{lab:20} {case:>8} {base + ADJ:6.2f} {st.mean(a):8.2f} "
                     f"{st.mean(b):9.2f} {st.mean(c):9.2f}   "
                     f"({len(a)} / {len(b)} / {len(c)})")
    lines += ["", "HCM: 6th ed. ch. 21 base saturation headways, geometry group 1,",
              "plus turn adjustment -0.06 s for 15% left / 15% right."]
    txt = "\n".join(lines)
    print(txt)
    open('awsc_calibration.txt', 'w').write(txt + "\n")


if __name__ == '__main__':
    main()

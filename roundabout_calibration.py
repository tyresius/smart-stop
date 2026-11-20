#!/usr/bin/env python3
"""
Roundabout calibration against HCM entry capacity (2026-11-15)
==============================================================
Saturates the Main E entry (1,800 veh/h offered) while Green N supplies the
circulating flow past it (its straight and left movements pass the Main E
merge: 85% of its demand). Measures Main E's entry throughput over the
120-600 s window for the fixed roundabout model, and compares with:

  model gap parameters  c = (3600/tf) * exp(-vc (tc - tf/2)/3600), tc 4.5, tf 2.8
  HCM 2010 single-lane  c = 1130 * exp(-0.0010 vc)
  HCM 6 single-lane     c = 1380 * exp(-0.00102 vc)
(veh/h; verify both coefficient pairs against the HCM roundabout chapter
before quoting. A Louisiana study found HCM 6 overestimates local capacity
and HCM 2010 fits closer.)

Usage: .venv/bin/python roundabout_calibration.py -> roundabout_calibration.txt
"""
import math
import statistics as st
from multiprocessing import Pool

import capacity_curves as cc
from capacity_curves import run_stream, make_schedule, ALG_MAP
import roundabout_rerun as rr                  # registers the fixed roundabout
from obb_survival_gate import _YieldPatch, OBBPlain
import obb_survival_gate as g

ENTRY = 1800.0
CIRC_DEMANDS = (0, 300, 600, 900)              # Green N veh/h
SEEDS = (0, 1)
_last = {}


def _logged(base):
    def __init__(self, geometry):
        base.__init__(self, geometry)
        self.departures, self._seen = [], set()
        _last['alg'] = self

    def step(self, dt=0.1):
        s = base.step(self, dt)
        for v in self.active_vehicles:
            if id(v) not in self._seen and v.current_position_meters > 0.0:
                self._seen.add(id(v))
                self.departures.append((v.road_name, self.current_time))
        return s
    return type(base.__name__ + 'Cal', (base,), {'__init__': __init__, 'step': step})


ALG_MAP['RC_Roundabout'] = _logged(ALG_MAP['RR_Roundabout'])
cc.NO_JITTER_ALGS.add('RC_Roundabout')


def job(args):
    q, rep = args
    g.HEADING_MODE = 'tangent'
    OBBPlain.clearance_m = 1.0
    lam = ENTRY + q
    split = [ENTRY / lam, 0.0, q / lam, 0.0]          # Main E, Main W, Green N, Green S
    with _YieldPatch():
        run_stream('RC_Roundabout', make_schedule(lam, rep, split=split), fair=True)
    lo, hi = cc.T_WARMUP, cc.T_WARMUP + cc.T_MEASURE
    deps = _last['alg'].departures
    entry = sum(1 for r, t in deps if r == 'Main E' and lo <= t <= hi)
    circ = sum(1 for r, t in deps if r == 'Green N' and lo <= t <= hi)
    return q, rep, entry * 3600 / (hi - lo), 0.85 * circ * 3600 / (hi - lo)


def main():
    with Pool(2) as pool:
        res = pool.map(job, [(q, r) for q in CIRC_DEMANDS for r in SEEDS])
    L = ["ROUNDABOUT ENTRY CAPACITY vs circulating flow (veh/h; fixed model; 2 seeds)", "",
         f"{'circulating vc':>15} {'model (sim)':>12} {'model params':>13} {'HCM 2010':>9} {'HCM 6':>7}"]
    for q in CIRC_DEMANDS:
        rs = [x for x in res if x[0] == q]
        cap = st.mean(x[2] for x in rs)
        vc = st.mean(x[3] for x in rs)
        params = 3600 / 2.8 * math.exp(-vc * (4.5 - 1.4) / 3600)
        h10 = 1130 * math.exp(-0.0010 * vc)
        h6 = 1380 * math.exp(-0.00102 * vc)
        L.append(f"{vc:15.0f} {cap:12.0f} {params:13.0f} {h10:9.0f} {h6:7.0f}")
    L += ["", "Model gap rules: critical gap 4.5 s (HCM 6 implies ~5.0 s), follow-up 2.8 s",
          "(HCM 6 implies ~2.6 s). Circulating flow = 85% of Green N departures (its",
          "straight and left movements pass the Main E merge)."]
    txt = "\n".join(L)
    print(txt)
    open('roundabout_calibration.txt', 'w').write(txt + "\n")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Predicted-heading error check (audit 3 F4, 2026-11-11)
=====================================================
The safety check orients each predicted footprint with `_pred_heading`. The
legacy rule ('secant') takes the chord to the free-kinematics position 0.3 s
later, or 1.5 s later when the car isn't moving yet (e.g. inside a
launch-delay hypothesis). This compares it with the path direction at the
predicted point ('tangent') over a grid of states the controller actually
evaluates: speeds 0 to the movement's cap, positions 0-13 m, launch-delay
hypotheses 0 / 1.2 / 2.5 s, and the 0-3 s look-ahead.

Usage: .venv/bin/python heading_error_check.py -> heading_error_check.txt
"""
import math

import numpy as np

import obb_survival_gate as g
from block3_reality import RollingVehicle, _DelayShift
from path_based_smart_stop import FourWayGeometry
from reality_sweeps import FAIR_CAP_4WAY


def _angdiff(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def main():
    geo = FourWayGeometry()
    half_diag = math.hypot(4.5 / 2, 2.0 / 2)
    lines = ["Secant vs tangent predicted heading (degrees)", "",
             f"{'movement':9} {'median':>7} {'p95':>7} {'max':>7}  "
             f"{'corner shift at p95 / max (m)':>30}"]
    for sig, label in (("R", "right"), ("L", "left"), ("NS/S", "straight")):
        errs = []
        for v0 in (0.0, 1.0, 2.0, FAIR_CAP_4WAY[sig]):
            for pos in np.arange(0.0, 14.0, 1.0):
                v = RollingVehicle("Main E", sig, 1, geo)
                v.INTERSECTION_SPEED = FAIR_CAP_4WAY[sig]
                v.activate(0.0)
                v._go_time = 0.0
                v.current_position_meters = float(pos)
                v.state.velocity = v0
                v._update_position_from_meters()
                for d in (0.0, 1.2, 2.5):
                    pv = _DelayShift(v, d) if d else v
                    for t in np.linspace(0.0, 3.0, 16):
                        p = pv.get_future_position(t)
                        g.HEADING_MODE = 'secant'
                        a = g._pred_heading(pv, t, p)
                        g.HEADING_MODE = 'tangent'
                        b = g._pred_heading(pv, t, p)
                        errs.append(math.degrees(_angdiff(a, b)))
        g.HEADING_MODE = 'secant'
        e = np.array(errs)
        p95, mx = np.percentile(e, 95), e.max()
        shift = [2 * half_diag * math.sin(math.radians(x) / 2) for x in (p95, mx)]
        lines.append(f"{label:9} {np.median(e):7.1f} {p95:7.1f} {mx:7.1f}  "
                     f"{shift[0]:14.2f} / {shift[1]:.2f}")
    lines += ["", "Corner shift = how far the far corner of a 4.5 x 2.0 m box moves",
              "when it is rotated by that error about its centre. The clearance",
              "buffer B = 1.0 m adds 0.5 m per side."]
    txt = "\n".join(lines)
    print(txt)
    open('heading_error_check.txt', 'w').write(txt + "\n")


if __name__ == '__main__':
    main()

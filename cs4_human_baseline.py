#!/usr/bin/env python3
"""
CS4 — Informal Human Co-activation Baseline
============================================
Real drivers at 4-way stops don't serialize strictly: everyone knows
opposing straights go together, and perpendicular rights don't conflict.
The strictly-serial TraditionalStopAlgorithm therefore UNDERSTATES the
human baseline, flattering Smart Stop's vs-Traditional headline. This
module models the informal human intersection: co-activation permitted for
exactly the two pairings drivers actually do by convention — nothing else
(no exit-arm topology, no trajectory prediction, no platoons) — with the
usual human reaction jitter.

The honest headline is then Smart Stop vs HumanFourWay, not vs Traditional.
"""

import csv
import math
import sys
import time

import numpy as np

import block5_adaptive  # registers SmartStopPreflash  # noqa: F401
from config import METERS_PER_UNIT
from obb_diag import L_M, W_M
from path_based_smart_stop import PathBasedSmartStopAlgorithm
from capacity_curves import run_stream, make_schedule, ALG_MAP

LAMBDAS = [600, 900, 1200]
REPS = 2
ALGS = ['Traditional', 'HumanFourWay', 'SmartStopPreflash']

_PARALLEL = {("Main E", "Main W"), ("Main W", "Main E"),
             ("Green N", "Green S"), ("Green S", "Green N")}


class HumanInformalDetector:
    """Convention-only conflict logic: opposing straights and perpendicular
    double-rights are 'obviously fine'; every other combination is treated
    as conflicting (humans don't run trajectory predictions)."""

    safety_margin = 3.5

    def check_collision(self, v1, v2, time_horizon=3.0,
                        signal1=None, signal2=None):
        s1 = signal1 if signal1 is not None else v1.signal
        s2 = signal2 if signal2 is not None else v2.signal
        pair = (v1.road_name, v2.road_name)
        if pair in _PARALLEL and s1 == "NS/S" and s2 == "NS/S":
            return False
        if (v1.road_name != v2.road_name and pair not in _PARALLEL
                and s1 == "R" and s2 == "R"):
            return False
        return True


class HumanFourWay(PathBasedSmartStopAlgorithm):
    """Informal human 4-way: FCFS-plus-convention. Inherits the coordination
    loop but with the convention-only detector, so only the two folk
    pairings ever co-activate."""

    def __init__(self, geometry):
        super().__init__(geometry)
        self.collision_detector = HumanInformalDetector()


ALG_MAP['HumanFourWay'] = HumanFourWay


def _folk_pair(a, b):
    """The two pairings drivers make by convention (as HumanInformalDetector):
    opposing straights, and perpendicular right turns."""
    pair = (a.road_name, b.road_name)
    if pair in _PARALLEL and a.signal == "NS/S" and b.signal == "NS/S":
        return True
    return (a.road_name != b.road_name and pair not in _PARALLEL
            and a.signal == "R" and b.signal == "R")


_CA_TABLES = {}


def _movement_samples(road, sig, geo, step_m=0.1):
    """Poses (m, m, rad) every step_m along a movement's path, and the arc
    position where its rear has left the intersection box."""
    from reality_sweeps import RealityVehicle
    v = RealityVehicle(road, sig, 1, geo)
    x = np.asarray(v.path_x, float) * METERS_PER_UNIT
    y = np.asarray(v.path_y, float) * METERS_PER_UNIT
    keep = np.concatenate([[True], np.hypot(np.diff(x), np.diff(y)) > 1e-9])
    x, y = x[keep], y[keep]
    seg = np.hypot(np.diff(x), np.diff(y))
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    hd = np.arctan2(np.diff(y), np.diff(x))
    s = np.arange(0.0, cum[-1], step_m)
    i = np.clip(np.searchsorted(cum, s, side='right') - 1, 0, len(seg) - 1)
    u = (s - cum[i]) / seg[i]
    px, py, ph = x[i] + u * (x[i + 1] - x[i]), y[i] + u * (y[i + 1] - y[i]), hd[i]
    box = 1.35 * METERS_PER_UNIT
    out = np.where((np.abs(px) > box) | (np.abs(py) > box))[0]
    out = out[s[out] > 1.0]
    s_exit = (s[out[0]] if len(out) else cum[-1]) + L_M / 2
    return s, px, py, ph, s_exit


def _footprint_points(x, y, h, length, width, res=0.1):
    """Points covering a rotated rectangle (m), for rasterised overlap tests."""
    gx = np.arange(-length / 2, length / 2 + 1e-9, res)
    gy = np.arange(-width / 2, width / 2 + 1e-9, res)
    lx, ly = np.meshgrid(gx, gy)
    lx, ly = lx.ravel(), ly.ravel()
    c, s = math.cos(h), math.sin(h)
    return x + lx * c - ly * s, y + lx * s + ly * c


def conflict_table(margin_m, res=0.1):
    """For every (occupant movement, candidate movement): the arc position
    along the occupant's path after which its footprint never again touches
    the candidate's corridor (the candidate's footprints, inflated by
    margin_m, from the stop line until its rear leaves the box). 0.0 means the
    two movements never conflict. Rasterised at `res` metres."""
    key = (margin_m, res)
    if key in _CA_TABLES:
        return _CA_TABLES[key]
    from path_based_smart_stop import FourWayGeometry
    from reality_sweeps import ROADS, SIGNALS
    geo = FourWayGeometry()
    mv = {(r, g): _movement_samples(r, g, geo) for r in ROADS for g in SIGNALS}
    half = 20.0
    n = int(2 * half / res) + 1

    def cells(xs, ys):
        return (np.clip(((xs + half) / res).astype(int), 0, n - 1),
                np.clip(((ys + half) / res).astype(int), 0, n - 1))

    corridors, occ = {}, {}
    for m, (s, px, py, ph, s_exit) in mv.items():
        grid = np.zeros((n, n), bool)
        for k in np.where(s <= s_exit)[0]:
            xs, ys = _footprint_points(px[k], py[k], ph[k], L_M + 2 * margin_m,
                                       W_M + 2 * margin_m, res)
            grid[cells(xs, ys)] = True
        corridors[m] = grid
        occ[m] = [cells(*_footprint_points(px[k], py[k], ph[k], L_M, W_M, res))
                  for k in range(len(s))]
    table = {}
    for o, (s, _, _, _, _) in mv.items():
        for c in mv:
            grid, last = corridors[c], None
            for k, ij in enumerate(occ[o]):
                if grid[ij].any():
                    last = k
            table[(o, c)] = 0.0 if last is None else float(s[last]) + res
    _CA_TABLES[key] = table
    return table


class HumanFourWayFCFS(PathBasedSmartStopAlgorithm):
    """All-way stop, first-come-first-served (rebuilt 2026-11-11, audit 3).

    Replaces `HumanFourWay` (kept unchanged so committed results reproduce),
    which (F1) chose who goes first with Smart Stop's own priority scoring,
    and (F2) held every non-paired car until the previous car had driven its
    whole path, exit lane included.

    Rules, all based on what a driver at the line can see:
      1. Turn order is the order cars reached the stop line. Cars arriving
         within TIE_WINDOW_S of each other count as simultaneous, and the car
         on the right goes first (all four tied: earliest arrival).
      2. The car whose turn it is goes once every car still in the
         intersection has either
           (a) passed its conflict area: the moving car's footprint will not
               touch this car's corridor (its footprints from the stop line
               until its rear leaves the box, widened by MARGIN_M) again.
               Movements that never touch need no wait. This is the
               "conflict area" model traffic microsimulators use for
               unsignalised intersections; or
           (b) is ahead of it in the same lane, making the same movement, at
               least one car length plus SAME_LANE_GAP_M down the path.
      3. Any other waiting car may go out of turn only if its movement never
         conflicts with any car already moving (this includes the folk
         pairings: opposing straights, perpendicular rights).
    No priority by movement type and no wait bonus. Departure headways are
    checked against HCM all-way-stop saturation headways by
    awsc_calibration.py.

    CLEAR_RULE = 'box' gives the simpler first rebuild (wait until the car
    has left the whole box; out-of-turn only for folk pairs). It fixed F1
    and F2 but ran ~1.2-1.9x slower than HCM headways, so it is kept only
    for the calibration comparison.
    """

    CLEAR_RULE = 'conflict'
    MARGIN_M = 0.5
    TIE_WINDOW_S = 1.0
    SAME_LANE_GAP_M = 1.0
    BOX = 1.35                                  # intersection box half-width (grid)
    # The approach on each approach's right (traffic from the right has priority)
    RIGHT_OF = {"Main W": "Green N", "Green N": "Main E",
                "Main E": "Green S", "Green S": "Main W"}

    def __init__(self, geometry):
        super().__init__(geometry)
        self.collision_detector = HumanInformalDetector()   # not used to decide

    # -- what a driver can see --------------------------------------------
    def _cleared_box(self, v):
        """True once the car's whole footprint has left the intersection box
        after passing through it (sticky)."""
        if getattr(v, '_awsc_cleared', False):
            return True
        if not v.active or v.intersection_exit_time is None:
            return False
        hl = 0.5 * L_M / METERS_PER_UNIT
        hw = 0.5 * W_M / METERS_PER_UNIT
        c, s = math.cos(v.state.heading), math.sin(v.state.heading)
        x, y, B = v.state.x, v.state.y, self.BOX
        car = [(x + dx * c - dy * s, y + dx * s + dy * c)
               for dx, dy in ((hl, hw), (hl, -hw), (-hl, -hw), (-hl, hw))]
        box = [(B, B), (B, -B), (-B, -B), (-B, B)]
        for ax in ((1.0, 0.0), (0.0, 1.0), (c, s), (-s, c)):
            pc = [px * ax[0] + py * ax[1] for px, py in car]
            pb = [px * ax[0] + py * ax[1] for px, py in box]
            if max(pc) < min(pb) or max(pb) < min(pc):
                v._awsc_cleared = True
                return True
        return False

    def _turn_order(self, heads):
        heads = sorted(heads, key=lambda v: (v.arrival_time, v.order))
        first = heads[0].arrival_time
        tied = [v for v in heads if v.arrival_time - first <= self.TIE_WINDOW_S]
        roads = {v.road_name for v in tied}
        free = [v for v in tied if self.RIGHT_OF[v.road_name] not in roads]
        holder = free[0] if free else tied[0]
        return [holder] + [v for v in heads if v is not holder]

    def _clear_s(self, a, cand):
        """Arc position the occupant must pass before `cand` may go (0 = the
        movements never conflict)."""
        table = conflict_table(self.MARGIN_M)
        return table[((a.road_name, a.signal), (cand.road_name, cand.signal))]

    def _holder_may_go(self, cand, a):
        if (a.road_name == cand.road_name and a.signal == cand.signal):
            return a.current_position_meters >= L_M + self.SAME_LANE_GAP_M
        if self.CLEAR_RULE == 'box':
            return _folk_pair(cand, a) or self._cleared_box(a)
        return a.current_position_meters >= self._clear_s(a, cand)

    def _may_go_out_of_turn(self, cand, a):
        if self.CLEAR_RULE == 'box':
            return _folk_pair(cand, a)
        same_lane = a.road_name == cand.road_name
        return not same_lane and self._clear_s(a, cand) == 0.0

    def _coordinate_smart_movements(self):
        heads = self._heads_of_queue()
        if not heads:
            return
        order = self._turn_order(heads)
        for i, cand in enumerate(order):
            occupants = [a for a in self.active_vehicles
                         if not self._cleared_box(a)]
            if i == 0:
                ok = all(self._holder_may_go(cand, a) for a in occupants)
            else:
                ok = bool(occupants) and all(self._may_go_out_of_turn(cand, a)
                                             for a in occupants)
            if ok:
                self.waiting_vehicles.remove(cand)
                cand.activate(self.current_time)
                self.active_vehicles.append(cand)


ALG_MAP['HumanFourWayFCFS'] = HumanFourWayFCFS


def main():
    rows = []
    t0 = time.time()
    for lam in LAMBDAS:
        for rep in range(REPS):
            schedule = make_schedule(lam, rep)
            for alg in ALGS:
                res = run_stream(alg, schedule, fair=True)
                vs = res['vehicles']
                served = [v for v in vs if v['served']]
                delays = [v['control_delay'] for v in served]
                rows.append(dict(
                    lam_vph=lam, rep=rep, algorithm=alg,
                    mean_delay=round(float(np.mean(delays)), 2) if delays else None,
                    served_frac=round(len(served) / len(vs), 4) if vs else None,
                ))
                print(f"  λ={lam:>5} rep {rep} {alg:<18}"
                      f"({time.time()-t0:.0f}s)", flush=True)

    with open("cs4_human_baseline.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print("\n" + "=" * 70)
    print("HONEST HUMAN BASELINE — mean control delay s/veh (served %)")
    print("=" * 70)
    print(f"{'λ':>6} |" + "".join(f" {a:>20} |" for a in ALGS))
    for lam in LAMBDAS:
        cells = []
        for alg in ALGS:
            sel = [r for r in rows if r['lam_vph'] == lam
                   and r['algorithm'] == alg and r['mean_delay'] is not None]
            if sel:
                d = float(np.mean([r['mean_delay'] for r in sel]))
                s = float(np.mean([r['served_frac'] for r in sel]))
                cells.append(f"{d:8.1f}s ({s*100:3.0f}%)")
            else:
                cells.append(" " * 15)
        print(f"{lam:>6} |" + " |".join(f" {c:>20}" for c in cells) + " |")
    print("=" * 70)


if __name__ == "__main__":
    main()

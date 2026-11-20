#!/usr/bin/env python3
"""
Block 1 — Arrival Streams, Delay Metrics, and Capacity Curves
=============================================================
Upgrades the comparison from "clear N pre-queued cars" (toy scenarios,
max 1 car per approach) to the standard traffic-engineering framing:
Poisson arrivals at demand λ, measured control delay per vehicle, and
volume-delay curves whose knee is the intersection's capacity.

Why this matters:
  - Published capacity bands exist for the two baselines, so the model can
    be VALIDATED before any Smart Stop claim is trusted:
        all-way stop (AWSC), balanced 4-leg . ~700-1,200 veh/h total
        single-lane roundabout .............. ~1,200-1,800 veh/h total
    (HCM/FHWA ballpark figures — pin exact HCM 6th-ed values before
    publication use.)
  - Queue-service dynamics — where schedulers historically beat yield
    merging — are invisible to the clearance-time benchmark. This is the
    regime the "decisive experiment" (Blocks 2-4) will be judged in.

Model notes (Block 1 scope — no car-following yet):
  - Physical queueing is abstracted: only the head of each approach queue
    exists inside the algorithm. When a head is activated, the next
    vehicle reaches the stop line after MOVE_UP_TIME (queue creep). This
    is the standard queue-server abstraction; Block 2 replaces it with
    real car-following + platoon release.
  - Physics defaults to the curvature-fair model from reality_sweeps.py
    (straights uncapped, turns limited by 0.25 g lateral comfort).
    --legacy runs the original 2.0 m/s slow-zone model instead.
  - Delay convention (HCM-style): control delay = (exit - arrival) minus
    the same movement's solo free-flow line-to-exit time. The roundabout's
    longer ring path is therefore NOT counted as delay (geometric delay is
    separate, per HCM). Total travel time is also reported so nothing is
    hidden by the convention.
  - Arrival schedules are generated once per (λ, rep) and reused across
    all algorithms — comparisons are paired.

Usage:
    python capacity_curves.py            # full λ sweep -> CSV + PNG + table
    python capacity_curves.py --legacy   # original 2.0 m/s physics
    python capacity_curves.py --quick    # fewer λ points / reps (smoke)
"""

import csv
import math
import os
import random
import sys
import time
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import METERS_PER_UNIT
from path_based_smart_stop import (
    FourWayGeometry,
    TraditionalStopAlgorithm, RoundaboutAlgorithm,
    PathBasedSmartStopAlgorithm,
)
from reality_sweeps import RealityVehicle, FAIR_CAP_4WAY, FAIR_CAP_RING
from block2_platoon import FollowingVehicle, PlatoonSmartStop

ROADS = ['Main E', 'Main W', 'Green N', 'Green S']
DT = 0.1
SEED = 42

# Turn-movement mix (L / straight / R). Typical urban approach shares.
TURN_MIX = [("L", 0.15), ("NS/S", 0.70), ("R", 0.15)]

# Queue move-up: time for the next queued car to creep to the stop line
# after the head departs (standard AWSC modeling value ~2 s).
MOVE_UP_TIME = 2.0

# Simulation windows (seconds)
T_WARMUP  = 120.0     # vehicles arriving here are simulated but not measured
T_MEASURE = 480.0     # measurement window
T_DRAIN   = 300.0     # extra time to let measured vehicles finish
T_MAX     = T_WARMUP + T_MEASURE + T_DRAIN

# Capacity call: largest λ with mean control delay under this threshold AND
# ≥98% of measured demand served by T_MAX. (50 s = HCM LOS E/F boundary for
# unsignalized intersections is 50 s/veh.)
DELAY_CAP_S  = 50.0
SERVED_FRAC  = 0.98

from roundabout_entry import (
    GapAcceptanceRoundabout, QuadrantRoundabout,
    RING_R_GRID, RING_TOL, CRITICAL_GAP, ENTRY_ANGLE_DEG,
)
from block3_reality import (
    GatedPlatoonSmartStop, RealisticRoundabout, RollingVehicle, EvasiveVehicle,
    ROLL_WINDOW,
)

# Per-driver reaction jitter U(lo, hi) seconds, applied to stopped launches.
# Exemptions:
#   SmartStopPlatoon — kept jitter-free as the Block 2 ideal ceiling, so the
#     realism cost is measurable as (SmartStopReal - SmartStopPlatoon).
#   Roundabout — the HCM critical gap ALREADY includes driver decision time;
#     adding a post-acceptance dwell double-counts it and produces fictional
#     collisions (a car accepting a gap, then sitting 2 s while the ring
#     state changes — real drivers re-judge; the model's accept moment IS
#     the launch moment). Caught as 0.00 m cross-path distances.
JITTER = (0.5, 2.0)
NO_JITTER_ALGS = {'SmartStopPlatoon', 'Roundabout'}

ALG_MAP = {
    'Traditional':      TraditionalStopAlgorithm,
    'Roundabout':       RealisticRoundabout,     # Block 3 default; --entry flag
    'SmartStopPlatoon': PlatoonSmartStop,        # Block 2 ideal ceiling
    'SmartStopReal':    GatedPlatoonSmartStop,   # Block 3: jitter+gating+rolling
}


# ─────────────────────────────────────────────────────────────────────────────
# Arrival schedule (shared across algorithms for paired comparison)
# ─────────────────────────────────────────────────────────────────────────────

def make_schedule(lam_total_vph, rep, split=None):
    """Poisson arrivals per approach. Returns sorted list of
    (t_arrival, road, signal, order). `split` = per-approach demand fractions
    (default balanced); the knob Block 4's asymmetric-demand sweep will use."""
    if split is None:
        split = [0.25] * 4
    rng = random.Random((SEED, int(lam_total_vph), rep).__repr__())
    events = []
    horizon = T_WARMUP + T_MEASURE
    for road, frac in zip(ROADS, split):
        lam = lam_total_vph * frac / 3600.0          # veh/s on this approach
        if lam <= 0:
            continue
        t = rng.expovariate(lam)
        while t < horizon:
            u = rng.random()
            acc = 0.0
            sig = TURN_MIX[-1][0]
            for s, p in TURN_MIX:
                acc += p
                if u < acc:
                    sig = s
                    break
            events.append((t, road, sig))
            t += rng.expovariate(lam)
    events.sort()
    return [(t, road, sig, i + 1) for i, (t, road, sig) in enumerate(events)]


# ─────────────────────────────────────────────────────────────────────────────
# Free-flow reference times (solo vehicle, line to intersection-exit)
# ─────────────────────────────────────────────────────────────────────────────

_FREEFLOW_CACHE = {}

# ── Stop penalty (2026-11-11) ────────────────────────────────────────────────
# Cars appear at the stop line, and the legacy `control_delay` measures from a
# launch FROM REST at the line. So stopping cost nothing: neither the braking
# before the line nor the time lost accelerating back up was charged, and a
# car that rolled through only got credit for the acceleration it skipped.
# HCM control delay charges both. `control_delay_sp` does too:
#   - free flow = passing the line at the movement's speed cap without
#     stopping (`freeflow_roll_time`), so a stopped car pays its acceleration
#     loss through the simulation itself; and
#   - every car that came to rest at the line also pays the braking loss
#     v_cap / (2 * STOP_DECEL) it would have spent slowing to a stop.
# `control_delay_hcm` is a sensitivity: it scales each stop's total cost
# (braking + acceleration loss) up to the HCM all-way-stop allowance of
# 5 s, which assumes faster approaches than this model's 6 m/s cruise.
# Legacy `control_delay` is unchanged, so committed results reproduce.
STOP_DECEL = 3.0           # m/s^2: comfortable stop (ITE ~10 ft/s^2); = model max decel
LAUNCH_ACCEL = 1.5         # m/s^2: PathBasedVehicle.max_acceleration
HCM_STOP_PENALTY_S = 5.0   # HCM AWSC delay allowance for decelerating and accelerating
_FREEFLOW_ROLL_CACHE = {}


def roll_speed(signal, use_rb, fair):
    """Speed a car carries over the line when it doesn't stop (the harness's
    rolling-launch speed)."""
    return (FAIR_CAP_RING if use_rb else FAIR_CAP_4WAY[signal]) if fair else 2.0


def model_stop_penalty(v_cap):
    """This model's cost of one stop vs passing at v_cap: braking loss plus
    acceleration loss (constant-rate approximation)."""
    return v_cap / (2 * STOP_DECEL) + v_cap / (2 * LAUNCH_ACCEL)


def freeflow_roll_time(road, signal, use_rb, fair):
    """Solo car crossing the line at its rolling speed, line to intersection
    exit: the no-stop free-flow reference for `control_delay_sp`."""
    key = (road, signal, use_rb, fair)
    if key in _FREEFLOW_ROLL_CACHE:
        return _FREEFLOW_ROLL_CACHE[key]
    v = RollingVehicle(road, signal, 1, FourWayGeometry(), use_roundabout_paths=use_rb)
    vc = roll_speed(signal, use_rb, fair)
    if fair:
        v.INTERSECTION_SPEED = vc
    v.roll_deadline, v.roll_v0 = 0.0, vc
    v.activate(0.0)
    t = 0.0
    while v.active and t < 120.0:
        v.update(DT)
        t += DT
    ff = v.intersection_exit_time if v.intersection_exit_time is not None else t
    _FREEFLOW_ROLL_CACHE[key] = ff
    return ff

def freeflow_time(road, signal, use_rb, fair):
    key = (road, signal, use_rb, fair)
    if key in _FREEFLOW_CACHE:
        return _FREEFLOW_CACHE[key]
    geometry = FourWayGeometry()
    v = RealityVehicle(road, signal, 1, geometry, use_roundabout_paths=use_rb)
    if fair:
        v.INTERSECTION_SPEED = FAIR_CAP_RING if use_rb else FAIR_CAP_4WAY[signal]
    v.activate(0.0)
    t = 0.0
    while v.active and t < 120.0:
        v.update(DT)
        t += DT
    ff = v.intersection_exit_time if v.intersection_exit_time is not None else t
    _FREEFLOW_CACHE[key] = ff
    return ff


# ─────────────────────────────────────────────────────────────────────────────
# Single run: one algorithm, one arrival schedule
# ─────────────────────────────────────────────────────────────────────────────

def run_stream(alg_name, schedule, fair=True, jumpers=None, false_q=0.0):
    """Feed a Poisson arrival stream through one algorithm.

    Queueing abstraction: per-approach FIFO held OUTSIDE the algorithm; a
    vehicle is handed to the algorithm only when it reaches the stop line
    (previous head departed ≥ MOVE_UP_TIME ago). The algorithms themselves
    are unmodified.

    false_q: fraction of vehicles that are FALSE-SIGNALERS (deceptive intent,
    2026-07-21) — they declare "R" (the trusted low-conflict co-activation) to
    the controller but physically drive the "L" path (maximum conflict). Used
    by the cheat-rate sweep to find where the activation system stutters vs
    breaks. Default 0.0 = no deception.
    """
    AlgClass = ALG_MAP[alg_name]
    use_rb = issubclass(AlgClass, RoundaboutAlgorithm)
    platoon = issubclass(AlgClass, PlatoonSmartStop)
    rolling = getattr(AlgClass, 'USE_ROLLING', False)
    evasive = getattr(AlgClass, 'USE_EVASIVE', False)
    VehCls = (EvasiveVehicle if evasive
              else RollingVehicle if rolling
              else FollowingVehicle if platoon else RealityVehicle)
    jitter = alg_name not in NO_JITTER_ALGS
    geometry = FourWayGeometry()
    alg = AlgClass(geometry)

    def make_vehicle(road, sig, order, t_line):
        obs = None
        if false_q and not use_rb:
            crng = random.Random(f"{SEED}-cheat-{order}")
            if crng.random() < false_q:
                sig, obs = 'L', 'R'     # true path L, declared R (deception)
        v = VehCls(road, sig, order, geometry, use_roundabout_paths=use_rb,
                   observed_signal=obs)
        if fair:
            v.INTERSECTION_SPEED = (FAIR_CAP_RING if use_rb
                                    else FAIR_CAP_4WAY[sig])
        if jitter:
            vrng = random.Random(f"{SEED}-jit-{order}")
            v.reaction_delay = vrng.uniform(*JITTER)
        if evasive:
            v._peers = alg.active_vehicles      # live list; mutated in place
        if jumpers is not None:
            # Compliance model (CS2): a jumper is a driver who, after waiting
            # past their patience at the head of the queue, goes WITHOUT the
            # green flash. q = fraction of drivers; patience ~ U(lo, hi) s.
            q, p_lo, p_hi = jumpers
            jrng = random.Random(f"{SEED}-jump-{order}")
            v._is_jumper = jrng.random() < q
            v._patience = jrng.uniform(p_lo, p_hi)
        if rolling:
            v.roll_deadline = t_line + ROLL_WINDOW
            v.roll_v0 = ((FAIR_CAP_RING if use_rb else FAIR_CAP_4WAY[sig])
                         if fair else 2.0)
            # Prediction state while in the roll window: approaching at speed.
            v.state.velocity = v.roll_v0
            roll_watch.append(v)
        return v

    pending = {r: deque() for r in ROADS}          # not yet at the line
    for ev in schedule:
        pending[ev[1]].append(ev)
    at_line = {r: None for r in ROADS}             # handed to alg, not yet activated
    line_free = {r: 0.0 for r in ROADS}            # earliest next line arrival
    records = {}                                   # order -> record dict
    ev_iter_done = {r: False for r in ROADS}

    t = 0.0
    min_dist = float('inf')
    min_samepath = float('inf')
    max_queue = 0
    roll_watch = []      # rolling-capable vehicles not yet activated
    n_jumps = 0          # unauthorized launches (CS2 compliance model)
    steps = int(T_MAX / DT)

    for _ in range(steps):
        # Feed vehicles
        for r in ROADS:
            if platoon:
                # Platoon mode: the algorithm owns the queue — vehicles join
                # on arrival; discharge headway emerges from car-following
                # (no harness move-up abstraction).
                while pending[r] and t >= pending[r][0][0]:
                    t_arr, road, sig, order = pending[r].popleft()
                    v = make_vehicle(road, sig, order, t)
                    alg.add_vehicle(v)
                    records[order] = dict(order=order, road=road, signal=sig,
                                          t_arrival=t_arr, t_line=t,
                                          vehicle=v)
                continue
            occ = at_line[r]
            if occ is not None and occ.start_time is not None:
                # Head departed: line frees after queue move-up creep
                line_free[r] = occ.start_time + MOVE_UP_TIME
                at_line[r] = None
                occ = None
            if occ is None and pending[r]:
                t_arr, road, sig, order = pending[r][0]
                if t >= max(t_arr, line_free[r]):
                    pending[r].popleft()
                    v = make_vehicle(road, sig, order, t)
                    alg.add_vehicle(v)
                    at_line[r] = v
                    records[order] = dict(order=order, road=road, signal=sig,
                                          t_arrival=t_arr, t_line=t,
                                          vehicle=v)

        # Flash-jumpers (CS2): unauthorized launches by out-of-patience heads.
        # The controller neither predicted nor approved these — they simply
        # appear in active traffic (as a camera would see them). Only queue
        # heads can jump (cars behind are physically blocked).
        if jumpers is not None and platoon:
            heads = {}
            for v in alg.waiting_vehicles:
                if v.road_name not in heads:
                    heads[v.road_name] = v
            pending_roads = {p.road_name for p in getattr(alg, '_pending', [])}
            for v in heads.values():
                if not (getattr(v, '_is_jumper', False)
                        and v.arrival_time is not None
                        and t - v.arrival_time > v._patience):
                    continue
                # Physical-queue constraint: a driver can only jump if they
                # are ACTUALLY at the stop line — no claimed platoon
                # followers still queued ahead on this road, and no same-road
                # vehicle still inside the launch zone. (Without this, a
                # "jump" teleports a mid-queue car onto coordinates where an
                # authorized release is spawning — a 0.00 m co-location
                # artifact of the queue abstraction, not a traffic event.)
                if v.road_name in pending_roads:
                    continue
                if any(a.road_name == v.road_name and a.active
                       and a.current_position_meters < 7.0
                       for a in alg.active_vehicles):
                    continue
                alg.waiting_vehicles.remove(v)
                v.reaction_delay = 0.0
                v.activate(t)
                v.state.velocity = 0.0
                alg.active_vehicles.append(v)
                n_jumps += 1

        status = alg.step(DT)
        t = status['time'] if abs(status['time'] - (t + DT)) < 1e-6 else t + DT

        # Roll-window expiry: a car that wasn't flashed while still moving
        # has stopped at the line — its prediction state reverts to rest.
        if roll_watch:
            for v in roll_watch[:]:
                if v.active:
                    roll_watch.remove(v)
                elif t > v.roll_deadline:
                    v.state.velocity = 0.0
                    roll_watch.remove(v)

        # Safety observable
        actives = getattr(alg, 'active_vehicles', None)
        if actives is None:
            av = getattr(alg, 'active_vehicle', None)
            actives = [av] if av else []
        moving = [v for v in actives if v.active]
        for i in range(len(moving)):
            for j in range(i + 1, len(moving)):
                a, b = moving[i], moving[j]
                if a.road_name == b.road_name and a.signal == b.signal:
                    # Same track: safety = longitudinal arc gap (car-following
                    # law), not the radial margin. < CAR_LEN would be overlap.
                    gap = abs(a.current_position_meters
                              - b.current_position_meters)
                    if gap < min_samepath:
                        min_samepath = gap
                    continue
                d = math.hypot(a.state.x - b.state.x,
                               a.state.y - b.state.y) * METERS_PER_UNIT
                if d < min_dist:
                    min_dist = d

        q_now = sum(len(pending[r]) for r in ROADS) + status['waiting']
        if q_now > max_queue:
            max_queue = q_now

        if (t > T_WARMUP + T_MEASURE
                and status['waiting'] == 0 and status['active'] == 0
                and all(not pending[r] for r in ROADS)):
            break

    # Per-vehicle metrics for the measurement window
    out = []
    for order, rec in records.items():
        if not (T_WARMUP <= rec['t_arrival'] < T_WARMUP + T_MEASURE):
            continue
        v = rec['vehicle']
        served = v.intersection_exit_time is not None
        row = dict(order=order, road=rec['road'], signal=rec['signal'],
                   t_arrival=rec['t_arrival'], served=served)
        if served:
            total = v.intersection_exit_time - rec['t_arrival']
            ff = freeflow_time(rec['road'], rec['signal'], use_rb, fair)
            row['total_time'] = total
            row['control_delay'] = max(0.0, total - ff)
            # Stop penalty (see STOP_DECEL above). A car "stopped" unless it
            # launched rolling; cars that can't roll (non-rolling vehicle
            # classes, hesitation runs) always stop. Caveat: roundabout cars
            # are counted as stopped too (the model launches them from rest
            # at the yield line), which overcharges the roundabout.
            stopped = not getattr(v, 'rolled', False)
            vc = roll_speed(rec['signal'], use_rb, fair)
            ffr = freeflow_roll_time(rec['road'], rec['signal'], use_rb, fair)
            cd_sp = max(0.0, total - ffr) + (vc / (2 * STOP_DECEL) if stopped else 0.0)
            row['stopped'] = stopped
            row['control_delay_sp'] = cd_sp
            row['control_delay_hcm'] = cd_sp + (
                HCM_STOP_PENALTY_S - model_stop_penalty(vc) if stopped else 0.0)
        out.append(row)
    # Vehicles that arrived in-window but never even reached the line
    n_unreached = sum(1 for r in ROADS for ev in pending[r]
                      if T_WARMUP <= ev[0] < T_WARMUP + T_MEASURE)

    return dict(vehicles=out, min_dist=min_dist, min_samepath=min_samepath,
                max_queue=max_queue, n_unreached=n_unreached, n_jumps=n_jumps)


# ─────────────────────────────────────────────────────────────────────────────
# λ sweep
# ─────────────────────────────────────────────────────────────────────────────

def sweep(lam_points, reps, fair=True,
          out_csv="capacity_curves.csv", out_png="capacity_curves.png"):
    rows = []
    t0 = time.time()
    for lam in lam_points:
        for rep in range(reps):
            schedule = make_schedule(lam, rep)
            demand = sum(1 for e in schedule
                         if T_WARMUP <= e[0] < T_WARMUP + T_MEASURE)
            for alg in ALG_MAP:
                res = run_stream(alg, schedule, fair=fair)
                vs = res['vehicles']
                served = [v for v in vs if v['served']]
                delays = [v['control_delay'] for v in served]
                totals = [v['total_time'] for v in served]
                rows.append(dict(
                    lam_vph=lam, rep=rep, algorithm=alg,
                    demand_veh=demand,
                    served_veh=len(served),
                    served_frac=round(len(served) / demand, 4) if demand else 1.0,
                    mean_delay_s=round(np.mean(delays), 2) if delays else '',
                    p95_delay_s=round(np.percentile(delays, 95), 2) if delays else '',
                    mean_total_s=round(np.mean(totals), 2) if totals else '',
                    max_queue=res['max_queue'],
                    min_dist_m=(round(res['min_dist'], 2)
                                if res['min_dist'] != float('inf') else ''),
                    min_samepath_m=(round(res['min_samepath'], 2)
                                    if res['min_samepath'] != float('inf')
                                    else ''),
                ))
            el = time.time() - t0
            print(f"  λ={lam:>5} veh/h rep {rep}: done ({el:.0f}s elapsed)",
                  flush=True)

    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {out_csv}")
    plot(rows, lam_points, out_png)
    summarize(rows, lam_points)
    return rows


def _agg(rows, alg, lam, field):
    vals = [r[field] for r in rows
            if r['algorithm'] == alg and r['lam_vph'] == lam and r[field] != '']
    return float(np.mean(vals)) if vals else None


def summarize(rows, lam_points):
    print("\n" + "=" * 78)
    print("VOLUME-DELAY SUMMARY — mean control delay s/veh (served fraction)")
    print("=" * 78)
    header = f"{'λ veh/h':>8} |" + "".join(f" {a:>22} |" for a in ALG_MAP)
    print(header)
    print("-" * len(header))
    for lam in lam_points:
        cells = []
        for alg in ALG_MAP:
            d = _agg(rows, alg, lam, 'mean_delay_s')
            sf = _agg(rows, alg, lam, 'served_frac')
            cells.append(f"{d:>10.1f}s ({sf*100:>5.1f}%)" if d is not None
                         else f"{'—':>19}")
        print(f"{lam:>8} |" + " |".join(f" {c:>21}" for c in cells) + " |")

    print("\nCAPACITY ESTIMATE (largest λ with mean delay < "
          f"{DELAY_CAP_S:.0f} s and ≥{SERVED_FRAC*100:.0f}% served):")
    for alg in ALG_MAP:
        cap = None
        for lam in lam_points:
            d = _agg(rows, alg, lam, 'mean_delay_s')
            sf = _agg(rows, alg, lam, 'served_frac')
            if d is not None and sf is not None and d < DELAY_CAP_S and sf >= SERVED_FRAC:
                cap = lam
        print(f"  {alg:<12} ≈ {cap if cap else '< ' + str(lam_points[0])} veh/h")
    print("\nVALIDATION BANDS (approximate HCM/FHWA, verify before publication):")
    print("  All-way stop (Traditional) expected ~700-1,200 veh/h")
    print("  Single-lane roundabout expected     ~1,200-1,800 veh/h")

    present = sorted({r['algorithm'] for r in rows})
    for alg in [a for a in present if 'Smart' in a or a == 'Roundabout']:
        mins = [r['min_dist_m'] for r in rows
                if r['algorithm'] == alg and r['min_dist_m'] != '']
        sp = [r['min_samepath_m'] for r in rows
              if r['algorithm'] == alg and r.get('min_samepath_m', '') != '']
        if mins:
            line = f"\n{alg} min cross-path distance: {min(mins):.2f} m"
            if sp:
                line += (f"; min same-path arc gap: {min(sp):.2f} m "
                         f"(overlap if < 4.5 m car length)")
            print(line, end='')
    print("\n" + "=" * 78)


def plot(rows, lam_points, out_png):
    colors = {'Traditional': '#E74C3C', 'Roundabout': '#3498DB',
              'SmartStop': '#2ECC71', 'SmartStopPlatoon': '#9B59B6',
              'SmartStopReal': '#F39C12'}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    for alg in ALG_MAP:
        d = [_agg(rows, alg, lam, 'mean_delay_s') for lam in lam_points]
        s = [(_agg(rows, alg, lam, 'served_frac') or 0) * lam
             for lam in lam_points]
        ax1.plot(lam_points, d, 'o-', color=colors[alg], label=alg)
        ax2.plot(lam_points, s, 'o-', color=colors[alg], label=alg)
    ax1.axhline(DELAY_CAP_S, color='#999', ls='--', lw=1,
                label=f'{DELAY_CAP_S:.0f}s (LOS E/F)')
    ax1.set_xlabel('Demand λ (veh/h, all approaches)')
    ax1.set_ylabel('Mean control delay (s/veh)')
    ax1.set_title('Volume-delay curves')
    ax1.legend(); ax1.grid(alpha=0.3)
    ax2.plot(lam_points, lam_points, ':', color='#999', lw=1, label='demand')
    ax2.set_xlabel('Demand λ (veh/h)')
    ax2.set_ylabel('Served throughput (veh/h)')
    ax2.set_title('Throughput vs demand (capacity = departure from diagonal)')
    ax2.legend(); ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    print(f"Wrote {out_png}")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    fair = "--legacy" not in sys.argv
    quick = "--quick" in sys.argv
    if "--entry" in sys.argv:
        mode = sys.argv[sys.argv.index("--entry") + 1]
        ALG_MAP['Roundabout'] = {
            'realistic': RealisticRoundabout,
            'gap': GapAcceptanceRoundabout,
            'quadrant': QuadrantRoundabout,
            'permissive': RoundaboutAlgorithm,
        }[mode]
    print(f"Roundabout entry model: {ALG_MAP['Roundabout'].__name__}")
    lam_points = [600, 1200, 1800] if quick else [400, 600, 800, 1000, 1200,
                                                  1600, 2000, 2400, 2800]
    reps = 1 if quick else 2
    print(f"Capacity curves: λ ∈ {lam_points} veh/h × {reps} rep(s), "
          f"{'curvature-fair' if fair else 'legacy 2.0 m/s'} physics")
    print(f"Windows: warm-up {T_WARMUP:.0f}s, measure {T_MEASURE:.0f}s, "
          f"drain ≤{T_DRAIN:.0f}s; move-up {MOVE_UP_TIME}s; "
          f"turn mix L/T/R = {'/'.join(str(int(p*100)) for _, p in TURN_MIX)}")
    sweep(lam_points, reps, fair=fair)

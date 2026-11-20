#!/usr/bin/env python3
"""
Seed-2 probe 2 — predicted vs realized trajectories for Car124 x Car125
========================================================================
Theory under test: the collision predictor cleared Car125 (Green N through)
against a free-path prediction of Car124 (Main E through), but Car124 was
car-following a slower platoon leader and stayed in the conflict zone past
its predicted exit -> realized 2.26 m.

Logs every check_collision call involving Car124/Car125 in t in [212.5,
215.5] with each vehicle's PREDICTED positions (+0.5..+3.0 s), then records
their REALIZED positions each step, and prints the divergence.

Usage:  python diag_seed2_probe2.py
"""

import math
import random

from balance_preflash import BalancedPreflashSmartStop
from block3_reality import ROLL_WINDOW, RollingVehicle
from capacity_curves import DT, JITTER, SEED, T_MAX
from config import METERS_PER_UNIT
from path_based_smart_stop import FourWayGeometry
from reality_sweeps import FAIR_CAP_4WAY
from starvation_probe import make_probe_schedule

SCHEDULE = make_probe_schedule(2000, 2, 'poisson')
PAIR = {'Car124', 'Car125'}
T_LO, T_HI = 212.5, 215.5
DELTAS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def main():
    geometry = FourWayGeometry()
    alg = BalancedPreflashSmartStop(geometry)
    cur_t = [0.0]

    det = alg.collision_detector
    orig_check = det.check_collision
    check_log = []      # dicts: t, names, result, per-vehicle predictions

    def check_logged(v1, v2, time_horizon=3.0, signal1=None, signal2=None):
        result = orig_check(v1, v2, time_horizon,
                            signal1=signal1, signal2=signal2)
        t = cur_t[0]
        names = {getattr(v1, 'car_name', '?'), getattr(v2, 'car_name', '?')}
        if T_LO <= t <= T_HI and names & PAIR:
            entry = dict(t=round(t, 2), names=sorted(names), result=result,
                         pred={})
            for v in (v1, v2):
                nm = getattr(v, 'car_name', '?')
                st = dict(pos_m=round(getattr(v, 'current_position_meters',
                                              float('nan')), 2),
                          vel=round(v.state.velocity, 2),
                          active=getattr(v, 'active', False),
                          rolled=getattr(v, 'rolled', False))
                preds = []
                for d in DELTAS:
                    try:
                        p = v.get_future_position(d)
                        preds.append((d, round(float(p[0]), 3),
                                      round(float(p[1]), 3)))
                    except Exception:
                        preds.append((d, None, None))
                entry['pred'][nm] = dict(state=st, traj=preds)
            check_log.append(entry)
        return result

    det.check_collision = check_logged

    pending = list(SCHEDULE)
    records = {}
    roll_watch = []
    trace = {n: [] for n in PAIR}    # realized (t, x, y, pos_m, vel)
    min_ev = dict(d=float('inf'))
    t = 0.0
    fed = 0

    for _ in range(int(T_MAX / DT)):
        cur_t[0] = t
        while fed < len(pending) and t >= pending[fed][0]:
            t_arr, road, sig, order = pending[fed]
            v = RollingVehicle(road, sig, order, geometry,
                               use_roundabout_paths=False)
            v.INTERSECTION_SPEED = FAIR_CAP_4WAY[sig]
            vrng = random.Random(f"{SEED}-jit-{order}")
            v.reaction_delay = vrng.uniform(*JITTER)
            v.roll_deadline = t + ROLL_WINDOW
            v.roll_v0 = FAIR_CAP_4WAY[sig]
            v.state.velocity = v.roll_v0
            roll_watch.append(v)
            alg.add_vehicle(v)
            records[v.car_name] = v
            fed += 1

        status = alg.step(DT)
        t = status['time'] if abs(status['time'] - (t + DT)) < 1e-6 else t + DT

        for v in roll_watch[:]:
            if v.active:
                roll_watch.remove(v)
            elif t > v.roll_deadline:
                v.state.velocity = 0.0
                roll_watch.remove(v)

        if T_LO <= t <= T_HI + 2.0:
            for nm in PAIR:
                v = records.get(nm)
                if v is not None:
                    trace[nm].append((round(t, 2),
                                      round(float(v.state.x), 3),
                                      round(float(v.state.y), 3),
                                      round(v.current_position_meters, 2),
                                      round(v.state.velocity, 2)))

        moving = [v for v in alg.active_vehicles if v.active]
        for i in range(len(moving)):
            for j in range(i + 1, len(moving)):
                a, b = moving[i], moving[j]
                if a.road_name == b.road_name and a.signal == b.signal:
                    continue
                d = math.hypot(a.state.x - b.state.x,
                               a.state.y - b.state.y) * METERS_PER_UNIT
                if d < min_ev['d']:
                    min_ev = dict(d=d, t=round(t, 2),
                                  names=(a.car_name, b.car_name))

        if fed >= len(pending) and status['waiting'] == 0 \
                and status['active'] == 0:
            break
        if t > T_HI + 5.0 and min_ev['d'] < 3.0:
            break   # we have what we came for

    # ── Report ──────────────────────────────────────────────────────────────
    print(f"min event: {min_ev['d']:.2f} m at t={min_ev['t']} "
          f"between {min_ev.get('names')}")
    real = {nm: {row[0]: row for row in trace[nm]} for nm in PAIR}

    pair_checks = [c for c in check_log if set(c['names']) == PAIR]
    other_checks = [c for c in check_log if set(c['names']) != PAIR]
    print(f"\nchecks involving the pair together: {len(pair_checks)}; "
          f"involving one of them vs others: {len(other_checks)}")
    print("\n--- Car124 x Car125 checks (True = conflict predicted) ---")
    for c in pair_checks:
        print(f"t={c['t']}  result={'CONFLICT' if c['result'] else 'CLEAR'}")
        for nm, info in c['pred'].items():
            st = info['state']
            print(f"   {nm}: pos {st['pos_m']}m v={st['vel']} "
                  f"active={st['active']} rolled={st['rolled']}")
            line = []
            for d, px, py in info['traj']:
                t_abs = round(c['t'] + d, 2)
                # find realized sample at nearest recorded step
                r = real[nm].get(t_abs) or real[nm].get(round(t_abs + 0.1, 2)) \
                    or real[nm].get(round(t_abs - 0.1, 2))
                if px is None:
                    line.append(f"+{d}: pred=?")
                elif r:
                    err = math.hypot(px - r[1], py - r[2]) * METERS_PER_UNIT
                    line.append(f"+{d}: err {err:4.1f}m")
                else:
                    line.append(f"+{d}: (no trace)")
            print("      pred-vs-real  " + "  ".join(line))

    if not pair_checks:
        print("\n*** The pair was NEVER checked against each other in the "
              "window — gating-path hole, not a prediction error. ***")
        print("Context checks (vehicle, other, t, result):")
        for c in other_checks[:30]:
            print(f"  t={c['t']}  {c['names']}  "
                  f"{'CONFLICT' if c['result'] else 'CLEAR'}")


if __name__ == "__main__":
    main()

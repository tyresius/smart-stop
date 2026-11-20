#!/usr/bin/env python3
"""
Seed-2 diagnosis — 2.26 m under SmartStopBalanced (hot split, poisson 2,000)
=============================================================================
Hypothesis: leadership oscillation makes the pre-flash hypothesis relaxation
time-inconsistent — a clearance approved under one leader interleaves with a
clearance approved under the next.

Instrumented re-run records:
  1. every relaxed-set grant (t, road, car) from BalanceRoutedDetector,
  2. every leadership change (t, road -> road),
  3. the global min-distance pair with full context (names, roads, signals,
     activation times, reaction dwells, speeds at the event).

Then an A/B: LatchedBalanced (leader frozen while any active vehicle's
launch is unconfirmed) on the same schedule — if the floor returns to
>= 3.3 m, the oscillation hypothesis is confirmed and the latch is the fix.

Usage:  python diag_seed2_balance.py
"""

import math
import random

from balance_preflash import BalancedPreflashSmartStop
from block3_reality import ROLL_WINDOW, _uncertain
from capacity_curves import DT, JITTER, ROADS, SEED, T_MAX
from config import METERS_PER_UNIT
from path_based_smart_stop import FourWayGeometry
from reality_sweeps import FAIR_CAP_4WAY
from starvation_probe import make_probe_schedule

SCHEDULE = make_probe_schedule(2000, 2, 'poisson')


class LatchedBalanced(BalancedPreflashSmartStop):
    """Fix candidate: freeze the priority leader while any active vehicle's
    launch is still unconfirmed (i.e. while a granted pre-flash clearance is
    in flight). Leadership only re-evaluates on quiet boundaries, so every
    interleaved clearance decision sees ONE consistent leader."""

    def __init__(self, geometry):
        super().__init__(geometry)
        self._latched_leader = None

    def _priority_leader_road(self):
        if any(_uncertain(v) for v in self.active_vehicles):
            return self._latched_leader
        self._latched_leader = super()._priority_leader_road()
        return self._latched_leader


def run(AlgClass, instrument=False):
    geometry = FourWayGeometry()
    alg = AlgClass(geometry)
    cur_t = [0.0]
    grants, flips = [], []

    if instrument:
        det = alg.collision_detector
        orig = det._hyps

        def hyps_logged(v):
            h = orig(v)
            if h is det.PREFLASH_HYPOTHESES:
                grants.append((cur_t[0], v.road_name, v.car_name))
            return h
        det._hyps = hyps_logged

    from block2_platoon import FollowingVehicle  # noqa: F401
    from block3_reality import RollingVehicle
    pending = list(SCHEDULE)
    records = {}
    roll_watch = []
    last_leader = [None]

    min_ev = dict(d=float('inf'))
    t = 0.0
    steps = int(T_MAX / DT)
    fed = 0

    for _ in range(steps):
        cur_t[0] = t
        # feed arrivals (platoon mode: alg owns the queue)
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
            records[v.car_name] = dict(road=road, sig=sig, t_arr=t_arr,
                                       vehicle=v, t_act=None)
            fed += 1

        # leadership tracking
        lead = alg._priority_leader_road()
        if lead != last_leader[0]:
            flips.append((t, last_leader[0], lead))
            last_leader[0] = lead

        status = alg.step(DT)
        t = status['time'] if abs(status['time'] - (t + DT)) < 1e-6 else t + DT

        for v in roll_watch[:]:
            if v.active:
                roll_watch.remove(v)
            elif t > v.roll_deadline:
                v.state.velocity = 0.0
                roll_watch.remove(v)

        # record activations
        for v in alg.active_vehicles:
            r = records.get(v.car_name)
            if r and r['t_act'] is None:
                r['t_act'] = t

        # safety observable with pair identity
        moving = [v for v in alg.active_vehicles if v.active]
        for i in range(len(moving)):
            for j in range(i + 1, len(moving)):
                a, b = moving[i], moving[j]
                if a.road_name == b.road_name and a.signal == b.signal:
                    continue
                d = math.hypot(a.state.x - b.state.x,
                               a.state.y - b.state.y) * METERS_PER_UNIT
                if d < min_ev['d']:
                    min_ev = dict(
                        d=d, t=t,
                        a=(a.car_name, a.road_name, a.signal,
                           round(a.state.velocity, 2)),
                        b=(b.car_name, b.road_name, b.signal,
                           round(b.state.velocity, 2)))

        if fed >= len(pending) and status['waiting'] == 0 \
                and status['active'] == 0:
            break

    return min_ev, grants, flips, records


def main():
    print("=" * 76)
    print("RUN 1 — SmartStopBalanced (instrumented), hot split seed 2")
    print("=" * 76)
    ev, grants, flips, records = run(BalancedPreflashSmartStop,
                                     instrument=True)
    t_ev = ev['t']
    print(f"min cross-path: {ev['d']:.2f} m at t={t_ev:.1f}s")
    for tag in ('a', 'b'):
        name, road, sig, vel = ev[tag]
        r = records.get(name, {})
        print(f"  {tag}: {name:<8} {road:<8} sig={sig:<5} v={vel:>5} m/s  "
              f"arrived {r.get('t_arr', float('nan')):.1f}s  "
              f"activated {r.get('t_act') if r.get('t_act') else '—'}s  "
              f"dwell {getattr(r.get('vehicle'), 'reaction_delay', 0):.2f}s")
    w0, w1 = t_ev - 12.0, t_ev + 0.5
    near_flips = [f for f in flips if w0 <= f[0] <= w1]
    print(f"\nleadership flips total: {len(flips)}  "
          f"(rate {len(flips)/max(t_ev,1):.2f}/s over run)")
    print(f"flips in [{w0:.0f}s, {w1:.0f}s] around the event: {len(near_flips)}")
    for f in near_flips[-12:]:
        print(f"    t={f[0]:7.1f}s  {str(f[1]):>8} -> {f[2]}")
    ev_roads = {ev['a'][1], ev['b'][1]}
    near_grants = [g for g in grants
                   if w0 <= g[0] <= w1 and g[1] in ev_roads]
    by_road = {}
    for g in near_grants:
        by_road.setdefault(g[1], set()).add(g[2])
    print(f"relaxed-set grants to the PAIR's roads in-window: "
          + ", ".join(f"{r}: {sorted(cs)}" for r, cs in by_road.items())
          if by_road else "relaxed-set grants to pair's roads in-window: none")

    print("\n" + "=" * 76)
    print("RUN 2 — LatchedBalanced (fix candidate), same schedule")
    print("=" * 76)
    ev2, _, flips2, _ = run(LatchedBalanced, instrument=False)
    print(f"min cross-path: {ev2['d']:.2f} m at t={ev2['t']:.1f}s  "
          f"(flips: {len(flips2)})")
    print(f"\nVERDICT: baseline {ev['d']:.2f} m -> latched {ev2['d']:.2f} m  "
          + ("— oscillation hypothesis CONFIRMED, latch restores margin"
             if ev2['d'] >= 3.3 > ev['d'] else
             "— latch does NOT restore margin; hypothesis rejected, "
             "investigate further"))


if __name__ == "__main__":
    main()

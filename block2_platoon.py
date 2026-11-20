#!/usr/bin/env python3
"""
Block 2 — Car-Following + Platoon Release for Smart Stop
=========================================================
Block 1 showed the gap-acceptance roundabout out-serving Smart Stop at
stream volumes >= ~1,200 veh/h — but against a Smart Stop releasing ONE
vehicle per approach per green, from rest, with a 2 s queue move-up between
every release. That is a signal serving one car per cycle: no real
controller works that way. This module gives Smart Stop queue service:

  - FollowingVehicle: longitudinal car-following along the shared path
    (speed capped by bumper gap / time headway to the leader). The sim
    previously had NO following physics — two same-path vehicles would
    drive through each other.
  - PlatoonSmartStop: when a head is activated, the maximal run of
    same-signal vehicles behind it on the same approach is claimed as a
    platoon and released sequentially, each launching when its leader is
    RELEASE_DIST_M down the path (discharge headway thus emerges from the
    vehicle dynamics rather than a hardcoded saturation rate). Every
    release is still validated against all non-platoon active traffic
    with the full turn-aware check.
  - PlatoonDetector: same-road-same-signal pairs are exempt from the
    radial 3.5 m margin (they share one track; the car-following law is
    what keeps them apart — the radial margin would otherwise forbid any
    platoon from existing). All cross-path pairs keep the full check.

Scope note: followers still stage at the stop line (paths begin there —
Phase 2A). Approach-lane geometry, rolling green, and reaction/gating
realism are Block 3.
"""

from config import METERS_PER_UNIT  # noqa: F401  (kept for parity/debug use)
from path_based_smart_stop import PathBasedSmartStopAlgorithm
from reality_sweeps import RealityVehicle


class FollowingVehicle(RealityVehicle):
    """RealityVehicle + longitudinal car-following behind `leader` along the
    shared path (arc-length gap, constant-time-headway law)."""

    CAR_LEN_M = 4.5     # leader body length occupying the path
    MIN_GAP_M = 1.0     # standstill bumper gap
    HEADWAY_S = 0.8     # desired time headway while moving

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.leader = None

    def update(self, dt, target_speed=None):
        L = self.leader
        if self.active and L is not None and L.active and not L.completed:
            gap = (L.current_position_meters - self.current_position_meters
                   - self.CAR_LEN_M)
            v_allow = max(0.0, (gap - self.MIN_GAP_M) / self.HEADWAY_S)
            if target_speed is None:
                zone = (self.INTERSECTION_SPEED if self._is_in_slow_zone()
                        else self.max_speed)
                target_speed = min(zone, v_allow)
            else:
                target_speed = min(target_speed, v_allow)
            return super().update(dt, target_speed)
        return super().update(dt, target_speed)

    def _predicted_arc_meters(self, time_ahead: float) -> float:
        """Cap the free-path prediction by the leader's predicted position so
        the collision predictor cannot outrun a car-following-throttled
        follower. Bug #8 (July 2026): free-path prediction cleared cross
        traffic against a follower that car-following had actually slowed —
        the predictor put it 3.4 m ahead of reality at +2 s, and the
        clearance realized as a 2.26 m cross-path. The cap mirrors update()'s
        gap law (body + standstill gap + speed-dependent headway) and recurses
        up the platoon so a slow head constrains the whole tail. It only ever
        REDUCES the prediction (min with free), so it cannot introduce a new
        overshoot beyond the already-shipped free-path behavior."""
        free = super()._predicted_arc_meters(time_ahead)
        L = self.leader
        if not (self.active and L is not None and L.active and not L.completed):
            return free
        lead_m = L._predicted_arc_meters(time_ahead)
        spacing = (self.CAR_LEN_M + self.MIN_GAP_M
                   + self.state.velocity * self.HEADWAY_S)
        cap = lead_m - spacing
        return max(self.current_position_meters, min(free, cap))


class PlatoonDetector:
    """Same-road-same-signal pairs share one track, so the radial 3.5 m
    margin is the wrong test (it would forbid any platoon). The right test
    is longitudinal: the pair conflicts unless separated by at least the
    launch spacing — which is exactly the release condition, so an already-
    launched chain never re-flags, while activating a fresh head on top of
    a previous platoon's tail is blocked. (A blanket exemption here caused
    exactly that overlap; caught by the same-path arc-gap observable.)
    Everything else goes to the wrapped turn-aware detector."""

    def __init__(self, inner, launch_spacing_m):
        self.inner = inner
        self.safety_margin = inner.safety_margin
        self.launch_spacing_m = launch_spacing_m

    def check_collision(self, v1, v2, time_horizon=3.0,
                        signal1=None, signal2=None):
        if v1.road_name == v2.road_name and v1.signal == v2.signal:
            gap = abs(getattr(v1, 'current_position_meters', 0.0)
                      - getattr(v2, 'current_position_meters', 0.0))
            return gap < self.launch_spacing_m
        return self.inner.check_collision(v1, v2, time_horizon,
                                          signal1=signal1, signal2=signal2)


class PlatoonSmartStop(PathBasedSmartStopAlgorithm):
    """Smart Stop with queue service: activating a head claims its
    same-signal followers and releases them at a dynamics-derived discharge
    headway, subject to the full collision check against non-platoon
    traffic at each release."""

    PLATOON_MAX    = 4      # vehicles per green window (head + 3 followers)
    RELEASE_DIST_M = 7.0    # leader progress required before follower launch
                            # (car length + ~2.5 m: from rest at 1.5 m/s^2
                            # this is ~2.9 s -> emergent discharge headway)

    def __init__(self, geometry):
        super().__init__(geometry)
        self.collision_detector = PlatoonDetector(self.collision_detector,
                                                  self.RELEASE_DIST_M)
        self._pending = []           # followers claimed, awaiting release
        self._released_ids = set()   # activated via platoon release

    def _same_group(self, v, leader):
        """May `v` join `leader`'s platoon / car-follow it? Default: same
        declared signal. Signal-blind controllers override this (audit 3,
        2026-11-11): a camera can't see a queued car's movement. Default
        behaviour is unchanged for every existing controller."""
        return v.signal == leader.signal

    def _claim_followers(self, leader):
        """Claim the maximal same-signal run behind `leader` on its road."""
        road_q = [v for v in self.waiting_vehicles
                  if v.road_name == leader.road_name]
        chain = leader
        for v in road_q[:self.PLATOON_MAX - 1]:
            if not self._same_group(v, leader):
                break                       # different movement ends the platoon
            self.waiting_vehicles.remove(v)
            v.leader = chain
            self._pending.append(v)
            chain = v

    def _release_followers(self):
        for v in self._pending[:]:
            L = v.leader
            if not (L.completed or L.current_position_meters >= self.RELEASE_DIST_M):
                continue
            conflict = False
            for a in self.active_vehicles:
                if self.collision_detector.check_collision(
                        v, a, time_horizon=self.COLLISION_TIME_HORIZON):
                    conflict = True
                    break
            if not conflict:
                self._pending.remove(v)
                v.activate(self.current_time)
                self._released_ids.add(id(v))
                self.active_vehicles.append(v)

    def step(self, dt: float = 0.1):
        prev_active = {id(v) for v in self.active_vehicles}
        self._release_followers()
        result = super().step(dt)
        # Any vehicle the base coordination just activated is a platoon head:
        # link it behind any same-path predecessor still on the track (so
        # car-following governs cross-platoon spacing), then claim its
        # same-signal followers.
        for v in self.active_vehicles:
            if id(v) not in prev_active and id(v) not in self._released_ids:
                if getattr(v, 'leader', None) is None:
                    pred, best = None, None
                    for a in self.active_vehicles:
                        if (a is v or a.road_name != v.road_name
                                or not self._same_group(a, v) or not a.active):
                            continue
                        if a.current_position_meters > v.current_position_meters:
                            if best is None or a.current_position_meters < best:
                                best, pred = a.current_position_meters, a
                    if pred is not None and hasattr(v, 'leader'):
                        v.leader = pred
                self._claim_followers(v)
        result['waiting'] += len(self._pending)
        return result

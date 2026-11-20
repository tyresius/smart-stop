#!/usr/bin/env python3
"""
Roundabout entry models (shared by capacity_curves.py and block3_reality.py).

See the class docstrings and capacity_curves.py commit history for the
audit trail: the pre-git quadrant rule encoded ~5.3 s of upstream
clearance at the legacy 2.0 m/s ring speed (matching the HCM critical
gap); an early audit replaced it with a permissive physics check. The
time-gap form below is the speed-independent restoration.
"""

import math

from config import METERS_PER_UNIT
from path_based_smart_stop import RoundaboutAlgorithm

# ─────────────────────────────────────────────────────────────────────────────
# Behavioral gap acceptance for roundabout entry
# ─────────────────────────────────────────────────────────────────────────────
# History: the original (pre-git-audit) entry rule was "no entry while a car
# occupies the upstream quarter arc" — at the legacy 2.0 m/s ring speed that
# equals ~5.3 s of upstream clearance, almost exactly the HCM critical gap
# (~4.1-4.6 s). An early audit replaced it with a bare physics collision
# check ("realistic collision check", path_based_smart_stop.py:1430), which
# accepts 3.5 m / 3 s clearances no human driver would take — inflating
# roundabout capacity to ~2x the published single-lane ceiling. This class
# restores behavioral realism as a TIME gap so it stays correct at any ring
# speed. The physics check is kept as a second, independent guard.

RING_R_GRID  = 1.5     # ring centerline radius (grid units)
RING_TOL     = 0.2     # |r - RING_R| tolerance for "circulating" (grid units)
CRITICAL_GAP = 4.5     # s — HCM-style critical gap for roundabout entry
ENTRY_ANGLE_DEG = {    # ring merge angle per approach (from the path arrays)
    'Main E': 205.5, 'Main W': 25.5, 'Green S': 295.5, 'Green N': 115.5,
}


class GapAcceptanceRoundabout(RoundaboutAlgorithm):
    """Roundabout entry gated by behavioral gap acceptance: block entry if
    any circulating vehicle will reach this approach's merge point within
    CRITICAL_GAP seconds (traffic circulates CCW; upstream distance is the
    CCW angular distance to the merge angle)."""

    critical_gap = CRITICAL_GAP
    # 2026-11-15: the ring-only check ignores a car still on its ENTRY arc
    # that is about to reach this merge point (a driver would see it). With
    # GAP_INCLUDES_ENTERING, such cars count too: time to the merge point is
    # measured along their own path. Legacy default False keeps committed
    # results reproducible.
    GAP_INCLUDES_ENTERING = False
    MERGE_TOL = 0.15                          # grid units (~0.7 m)

    def _entering_arrival_s(self, v, mx, my):
        """Seconds until an off-ring car reaches the merge point (mx, my)
        along its own path, or None if its path doesn't pass it ahead."""
        import numpy as np
        px, py = np.asarray(v.path_x, float), np.asarray(v.path_y, float)
        near = np.where(np.hypot(px - mx, py - my) < self.MERGE_TOL)[0]
        if not len(near):
            return None
        arc = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(px), np.diff(py)))])
        here = v.current_position_meters / METERS_PER_UNIT
        ahead = [i for i in near if arc[i] > here]
        if not ahead:
            return None
        dist_m = (arc[ahead[0]] - here) * METERS_PER_UNIT
        return dist_m / max(v.state.velocity, 0.5)

    def _gap_ok(self, waiting_vehicle):
        theta_e = math.radians(ENTRY_ANGLE_DEG[waiting_vehicle.road_name])
        mx, my = RING_R_GRID * math.cos(theta_e), RING_R_GRID * math.sin(theta_e)
        for v in self.active_vehicles:
            if not v.active:
                continue
            r = math.hypot(v.state.x, v.state.y)
            if abs(r - RING_R_GRID) > RING_TOL:
                if (self.GAP_INCLUDES_ENTERING
                        and v.road_name != waiting_vehicle.road_name):
                    # same-approach leaders are followers' business
                    # (follow-up headway), not a crossing conflict
                    t = self._entering_arrival_s(v, mx, my)
                    if t is not None and t < self.critical_gap:
                        return False
                continue                      # on an entry/exit arc, not the ring
            theta_v = math.atan2(v.state.y, v.state.x)
            dtheta = (theta_e - theta_v) % (2 * math.pi)
            speed = max(v.state.velocity, 0.5)            # m/s; avoid div-by-0
            t_arrive = dtheta * RING_R_GRID * METERS_PER_UNIT / speed
            if t_arrive < self.critical_gap:
                return False
        return True

    def _try_enter_roundabout(self):
        for waiting_vehicle in self.waiting_vehicles[:]:
            if not self._gap_ok(waiting_vehicle):
                continue
            can_enter = True
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(
                        waiting_vehicle, active_vehicle, time_horizon=3.0):
                    can_enter = False
                    break
            if can_enter:
                self.waiting_vehicles.remove(waiting_vehicle)
                waiting_vehicle.activate(self.current_time)
                self.active_vehicles.append(waiting_vehicle)
                break                          # one entry per step (as before)


class QuadrantRoundabout(GapAcceptanceRoundabout):
    """The original pre-audit rule, verbatim: no entry while any circulating
    vehicle occupies the upstream quarter arc (between this entry and the
    previous one). Provided for comparison with the time-gap version."""

    def _gap_ok(self, waiting_vehicle):
        theta_e = math.radians(ENTRY_ANGLE_DEG[waiting_vehicle.road_name])
        for v in self.active_vehicles:
            if not v.active:
                continue
            r = math.hypot(v.state.x, v.state.y)
            if abs(r - RING_R_GRID) > RING_TOL:
                continue
            theta_v = math.atan2(v.state.y, v.state.x)
            dtheta = (theta_e - theta_v) % (2 * math.pi)
            if dtheta < math.pi / 2:
                return False
        return True

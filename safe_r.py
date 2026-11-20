#!/usr/bin/env python3
"""
Smart Safe R — close the false-right hole explicitly
=====================================================
(2026-07-21, Patrick.) Base Smart Safe treats only NO-SIGNAL as a worst-case
left; it TRUSTS a declared right. So a "signal right, turn left" driver is
handled only incidentally (by the 4.0 m margin and the true-path distance
check), not by design. This closes it explicitly and cheaply:

  A declared RIGHT is treated as a potential LEFT (worst case) for
  co-activation UNTIL the vehicle's motion confirms the right turn. A right
  turn diverges early in the path arc, so confirmation is fast — the cost is
  a brief hold on co-activations that depend on the right being genuine, not
  a trust of the blinker.

"Confirmed" means the vehicle has physically committed to its right arc: it is
active and has travelled >= R_CONFIRM_M along its path. Because the vehicle
drives its TRUE path, a genuine right reveals as R and a false right (driving
the left arc) reveals as L — so the deceiver is never trusted. This is the
targeted, cheap version of motion-confirmed intent (the universal version cost
+242%): only declared-rights (~15% of traffic) are held, and only briefly.
"""

from path_based_smart_stop import SmartStopSafeAlgorithm


class SmartSafeR(SmartStopSafeAlgorithm):
    """Smart Safe + explicit false-right defense (motion-confirmed right)."""

    # Arc distance (m) by which a right turn has visibly diverged from a left
    # /straight. A vision-phase parameter: how early a camera can call the turn.
    R_CONFIRM_M = 2.0

    def _effective_signal(self, vehicle):
        sig = vehicle.signal            # declared (what the controller sees)
        if sig == "NS/S":
            return "L"                  # base Smart Safe: no-signal -> worst case
        if sig == "R":
            confirmed = (getattr(vehicle, 'active', False)
                         and vehicle.current_position_meters >= self.R_CONFIRM_M)
            if not confirmed:
                return "L"              # unconfirmed right -> treat as worst-case left
            # Confirmed by motion: the camera now sees the true movement — a
            # genuine right stays R; a driver actually turning left reveals L.
            return getattr(vehicle, 'true_signal', "R")
        return sig                      # declared left (already worst case)

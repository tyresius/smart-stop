#!/usr/bin/env python3
"""
Signal-blind Smart Safe, version 2 (audit 3 fixes, 2026-11-11)
==============================================================
Legacy `BlindSafe` (hesitation_sweep.py) is unchanged, so committed results
reproduce. V2 removes the places where the "blind" controller still used
knowledge a camera lacks, or predicted with physics the real cars don't
follow. Each was found by tracing every read of a real car's true movement
during a run (test_blind_no_truth.py), or by audit 3.

1. Priority. Legacy ranked waiting cars right turn > straight > left using
   their TRUE movement (path_based_smart_stop.py `_signal_bonus` call sites).
   V2 ranks by waiting time and arrival order only.
2. Platoon grouping and car-following links. Legacy grouped followers, and
   linked a new head to the car ahead, only if they shared the TRUE movement
   (block2_platoon.py `_claim_followers`, `step`). V2 groups by lane only;
   every follower still passes the all-hypotheses check before release.
3. Hypothesis ("phantom") cars. The controller predicts each unrevealed car
   under all three movements using stand-in cars. Legacy stand-ins used the
   old 2.0 m/s intersection speed cap (real cars: 3.2 / 4.4 / 6.0 m/s by
   movement) and ignored car-following (the bug #8 failure mode: predicting a
   follower ahead of where its leader lets it be). V2 stand-ins carry each
   hypothesis's own speed cap and the real car's car-following link.

Not changed here (known and documented in FINAL_AUDIT.md):
  - after REVEAL_M the true movement is read perfectly, with no latency (F6);
  - under rolling launches the approach speed equals the movement's speed
    cap, so speed itself reveals intent (not an issue under full stops);
  - a follower's prediction cap uses its leader's own prediction, which
    reflects the leader's true speed cap.

Use together with obb_survival_gate.HEADING_MODE = 'tangent'.
"""

import reality_sweeps
from reality_sweeps import PerceptionDetector, FAIR_CAP_4WAY, SIGNALS
from block3_reality import RollingVehicle
from hesitation_sweep import BlindSafe
from capacity_curves import ALG_MAP


class PerceptionDetectorV2(PerceptionDetector):
    """PerceptionDetector whose stand-ins also mirror the real car's
    car-following link and rolling state at check time."""

    def _variants(self, v):
        phantoms = self.variant_map.get(id(v))
        if not phantoms:
            return [v]
        if v.active and v.current_position_meters > reality_sweeps.REVEAL_M:
            true_ph = [p for p in phantoms if p.signal == v.true_signal]
            phantoms = true_ph or phantoms
        leader = getattr(v, 'leader', None)
        rolled = getattr(v, 'rolled', False)
        for p in phantoms:
            p.active = v.active
            p.completed = v.completed
            p.current_position_meters = v.current_position_meters
            p.state.velocity = v.state.velocity
            p.leader = leader
            p.rolled = rolled
        return phantoms


def make_phantoms_v2(vehicle, geometry):
    """One stand-in per hypothesis movement, with that movement's own
    dynamics. Only the PRESENCE of a fair speed cap on the real car is read
    (it says which physics model the run uses), never its value."""
    fair = 'INTERSECTION_SPEED' in vehicle.__dict__
    out = []
    for sig in SIGNALS:
        p = RollingVehicle(vehicle.road_name, sig, vehicle.order, geometry)
        if fair:
            p.INTERSECTION_SPEED = FAIR_CAP_4WAY[sig]
        out.append(p)
    return out


class BlindSafeV2(BlindSafe):
    """Signal-blind Smart Safe with the audit-3 leak and prediction fixes."""

    def __init__(self, geometry):
        super().__init__(geometry)
        # The legacy mixin wrapped the detector in a PerceptionDetector; swap
        # in the V2 behaviour (same attributes, different _variants).
        self.collision_detector.__class__ = PerceptionDetectorV2

    def add_vehicle(self, vehicle):
        super().add_vehicle(vehicle)
        if id(vehicle) in self._mci_variants:
            self._mci_variants[id(vehicle)] = make_phantoms_v2(
                vehicle, self.geometry)

    def _intent_of(self, vehicle):
        return None                    # no movement-based priority

    def _same_group(self, v, leader):
        return True                    # lane only, not movement


ALG_MAP['BlindSafeV2'] = BlindSafeV2


class BlindSafeV2Hes(BlindSafeV2):
    """BlindSafeV2 with the three hesitation factors as independent switches
    (audit 1 finding B; 2026-11-11). Legacy BlindSafe bundled them: any
    H > 0 added launch delay AND forbade rolling AND widened the controller's
    launch-delay hypotheses.

      H_S         hesitation (s) for drivers responding to the flash: a
                  stopped car launches H_S later; a rolling car crosses the
                  line H_S late, still at speed (it does not stop)
      ALLOW_ROLL  may a car flashed on arrival roll through without stopping
      WIDEN       does the controller allow for the hesitation: stopped-car
                  hypotheses widened as in legacy (0, 1.2 + H/2, 2.5 + H);
                  a flashed roller that hasn't crossed yet is checked at
                  delays 0, H/4, H/2, 3H/4, H

    Hypotheses are set on this controller's own detector, so other controllers
    in the same process (the signal) are unaffected.
    """
    H_S = 0.0
    ALLOW_ROLL = True
    WIDEN = True
    HESITATION_S = 0.0     # neutralise legacy BlindSafe's bundled handling
    NO_ROLL = False

    def __init__(self, geometry):
        super().__init__(geometry)
        from block3_reality import DwellRobustDetector, DWELL_HYPOTHESES
        h = self.H_S
        d = self.collision_detector
        while d is not None:
            if isinstance(d, DwellRobustDetector):
                if self.WIDEN:
                    b = DWELL_HYPOTHESES
                    d.stop_hyps = (b[0], b[1] + h / 2, b[2] + h)
                    d.roll_hyps = (0.0, h / 4, h / 2, 3 * h / 4, h) if h > 0 else None
                else:
                    d.stop_hyps, d.roll_hyps = DWELL_HYPOTHESES, None
            d = getattr(d, 'inner', None)

    def add_vehicle(self, vehicle):
        if not self.ALLOW_ROLL:
            vehicle.roll_v0 = 0.0
            vehicle.roll_deadline = -1.0
            vehicle.state.velocity = 0.0
        if self.H_S > 0.0:
            vehicle.reaction_delay = getattr(vehicle, 'reaction_delay', 0.0) + self.H_S
            vehicle.roll_hesitation = self.H_S
        super().add_vehicle(vehicle)


ALG_MAP['BlindSafeV2Hes'] = BlindSafeV2Hes

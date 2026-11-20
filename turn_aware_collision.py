#!/usr/bin/env python3
"""
Turn-Aware Collision Detection
================================

Fixes Smart Stop performance by recognizing non-conflicting turn combinations.

Key insight: Two right turns from perpendicular approaches don't conflict,
even if their paths pass close to each other.

Conflict Matrix:
                R (Right)   NS/S (Straight)   L (Left)
    R              SAFE         DEPENDS         DEPENDS
    NS/S         DEPENDS        DEPENDS         CONFLICT
    L            DEPENDS        CONFLICT        CONFLICT

This dramatically improves Smart Stop's ability to activate multiple
vehicles simultaneously.
"""

import numpy as np
import math
from typing import Tuple

from config import METERS_PER_UNIT


class TurnAwareCollisionDetector:
    """
    Enhanced collision detector that considers turn signal combinations.

    Non-conflicting combinations are allowed to proceed simultaneously
    without triggering collision detection.
    """

    # Exit arm each (road, signal) combination uses when leaving the intersection.
    # Derived directly from the path arrays in path_based_smart_stop.py.
    EXIT_ARM = {
        ("Main E",   "R"):    "Green N",   # curves south → exits Green N arm
        ("Main E",   "NS/S"): "Main E",    # straight east → exits Main E arm
        ("Main E",   "L"):    "Green S",   # curves north → exits Green S arm
        ("Main W",   "R"):    "Green S",   # curves north → exits Green S arm
        ("Main W",   "NS/S"): "Main W",    # straight west → exits Main W arm
        ("Main W",   "L"):    "Green N",   # curves south → exits Green N arm
        ("Green S",  "R"):    "Main E",    # curves east  → exits Main E arm
        ("Green S",  "NS/S"): "Green S",   # straight north→ exits Green S arm
        ("Green S",  "L"):    "Main W",    # curves west  → exits Main W arm
        ("Green N",  "R"):    "Main W",    # curves west  → exits Main W arm
        ("Green N",  "NS/S"): "Green N",   # straight south→ exits Green N arm
        ("Green N",  "L"):    "Main E",    # curves east  → exits Main E arm
    }

    def __init__(self, safety_margin: float = 3.0):
        self.safety_margin = safety_margin

        # Define safe turn combinations (both can proceed simultaneously)
        self.safe_combinations = set([
            ("R", "R"),  # Two right turns from different approaches - SAFE
            # Add more as needed based on geometry analysis
        ])

        # Parallel roads (opposite lanes on same street)
        self.parallel_roads = {
            ("Main E", "Main W"): True,
            ("Main W", "Main E"): True,
            ("Green N", "Green S"): True,
            ("Green S", "Green N"): True,
        }

        # Perpendicular roads
        self.perpendicular_roads = {
            ("Main E", "Green N"): True,
            ("Main E", "Green S"): True,
            ("Main W", "Green N"): True,
            ("Main W", "Green S"): True,
            ("Green N", "Main E"): True,
            ("Green N", "Main W"): True,
            ("Green S", "Main E"): True,
            ("Green S", "Main W"): True,
        }

    def check_collision(self, vehicle1, vehicle2, time_horizon: float = 3.0,
                        signal1: str = None, signal2: str = None) -> bool:
        """
        Check if vehicles will collide, considering turn signals and geometry.

        Optional signal overrides:
            signal1, signal2 — if provided, these replace vehicle1.signal /
            vehicle2.signal in the rule lookup (Rules 1-3). Smart Safe uses
            this to treat NS/S vehicles as L (worst-case path intent), so
            Rule 1 (parallel pass) and Rule 3 (R+NS/S exit-arm pass) cannot
            green-light a vehicle whose true intent is unknown.

            Note: the geometric distance check (Rule 4) still uses the
            vehicle's actual path arrays; only the rule selection is
            overridden. A future improvement would synthesize a hypothetical
            L-path vehicle for full geometric conservatism.

        Returns:
            bool: True if collision possible, False if safe
        """
        if not (vehicle1.active or vehicle2.active):
            if not vehicle1.active and not vehicle2.active:
                return False

        # Resolve effective signals (override → fallback to vehicle.signal).
        sig1 = signal1 if signal1 is not None else vehicle1.signal
        sig2 = signal2 if signal2 is not None else vehicle2.signal

        # RULE 1: Parallel paths (opposite lanes on same road)
        if self._are_on_parallel_paths(vehicle1, vehicle2, sig1, sig2):
            return False  # Median separates them

        # RULE 2: Two right turns from perpendicular approaches
        if (sig1, sig2) == ("R", "R"):
            road_combo = (vehicle1.road_name, vehicle2.road_name)
            if road_combo in self.perpendicular_roads:
                # Right turns from perpendicular approaches are safe
                return False

        # RULE 3: Right turn + straight from perpendicular — decided by exit arm.
        #
        # The distance-based check cannot be used here: the simulation's
        # coordinate scale makes the 3.0-unit margin larger than a lane width,
        # so any perpendicular pair that overlaps in x while one is at y=+0.5
        # and the other at y=-0.5 will be incorrectly blocked even when their
        # paths genuinely diverge after the corner.
        #
        # The exit-arm map is the authoritative geometric check:
        #   same exit arm  → paths merge on exit road → block.
        #   different arms → paths diverge after the corner → safe.
        if self._is_right_straight_perpendicular(vehicle1, vehicle2, sig1, sig2):
            exit1 = self.EXIT_ARM.get((vehicle1.road_name, sig1))
            exit2 = self.EXIT_ARM.get((vehicle2.road_name, sig2))
            if exit1 is not None and exit2 is not None:
                if exit1 == exit2:
                    # Shared exit arm — paths merge on exit road; block.
                    return True
                else:
                    # Different exit arms — paths diverge after corner; safe.
                    return False
            # Unknown combination — fall through to standard distance check.

        # RULE 4: Standard distance-based check for other combinations
        return self._check_distance_collision(vehicle1, vehicle2, time_horizon)

    def _are_on_parallel_paths(self, vehicle1, vehicle2,
                               sig1: str = None, sig2: str = None) -> bool:
        """Check if vehicles are on parallel paths (opposite lanes)."""
        s1 = sig1 if sig1 is not None else vehicle1.signal
        s2 = sig2 if sig2 is not None else vehicle2.signal
        road_pair = (vehicle1.road_name, vehicle2.road_name)

        if road_pair in self.parallel_roads:
            # Both going straight in opposite directions
            if s1 == "NS/S" and s2 == "NS/S":
                return True

        return False

    def _is_right_straight_perpendicular(self, vehicle1, vehicle2,
                                         sig1: str = None, sig2: str = None) -> bool:
        """
        Check if one vehicle is turning right and the other going straight
        from perpendicular approaches.
        """
        s1 = sig1 if sig1 is not None else vehicle1.signal
        s2 = sig2 if sig2 is not None else vehicle2.signal
        road_combo = (vehicle1.road_name, vehicle2.road_name)

        if road_combo in self.perpendicular_roads:
            # One right, one straight
            if (s1 == "R" and s2 == "NS/S") or \
               (s1 == "NS/S" and s2 == "R"):
                return True

        return False

    # Target sample interval for the time-horizon distance check (seconds).
    # M6 fix: previously hardcoded 15 samples regardless of horizon, which
    # gave 0.21 s/sample at horizon=3.0 but only 0.27 s/sample at
    # horizon=4.0 (Smart Safe).  Now scales with horizon while keeping a
    # minimum sample count for short horizons.
    SAMPLE_INTERVAL_SECONDS = 0.2
    MIN_SAMPLES = 15

    def _check_distance_collision(self, vehicle1, vehicle2,
                                  time_horizon: float,
                                  safety_margin: float = None) -> bool:
        """
        Standard distance-based collision check.

        `safety_margin` is in real metres; predicted positions live in
        grid units, so multiply the Euclidean grid distance by
        METERS_PER_UNIT before comparing.
        """
        if safety_margin is None:
            safety_margin = self.safety_margin

        # Sample positions over time horizon at fixed temporal resolution
        # so longer horizons (Smart Safe's 4 s) get proportionally more
        # samples.
        n_samples = max(self.MIN_SAMPLES,
                        int(time_horizon / self.SAMPLE_INTERVAL_SECONDS) + 1)
        time_steps = np.linspace(0, time_horizon, n_samples)

        for t in time_steps:
            pos1 = self._predict_position(vehicle1, t)
            pos2 = self._predict_position(vehicle2, t)

            if pos1 and pos2:
                distance_units = math.sqrt((pos1[0] - pos2[0]) ** 2 +
                                           (pos1[1] - pos2[1]) ** 2)
                distance_m = distance_units * METERS_PER_UNIT
                if distance_m < safety_margin:
                    return True

        return False

    def _predict_position(self, vehicle, time_ahead: float) -> Tuple[float, float]:
        """Predict vehicle position after time_ahead seconds.

        Phase 2A: inactive (candidate) vehicles are routed through
        ``get_future_position`` (which now models kinematic acceleration
        from the current state) so the collision check sees where a
        waiting car would be *if activated this step*, not stuck at its
        stop line.  Without this the predictor would treat a freshly
        activated v=0 vehicle as stationary for the full look-ahead and
        miss conflicts with active traffic.
        """
        if getattr(vehicle, 'completed', False):
            return None
        if hasattr(vehicle, 'get_future_position'):
            return vehicle.get_future_position(time_ahead)

        # Fallback: linear extrapolation (no path data available).
        if hasattr(vehicle, 'state'):
            future_x = vehicle.state.x + vehicle.state.velocity * math.cos(
                vehicle.state.heading) * time_ahead
            future_y = vehicle.state.y + vehicle.state.velocity * math.sin(
                vehicle.state.heading) * time_ahead
            return (future_x, future_y)

        return (vehicle.x, vehicle.y)


# =============================================================================
# Test the Turn-Aware Collision Detector
# =============================================================================

def test_turn_aware_detector():
    """Test the turn-aware collision detector on right-turn scenario"""
    from path_based_smart_stop import PathBasedVehicle, FourWayGeometry

    print("=" * 80)
    print("TESTING TURN-AWARE COLLISION DETECTOR")
    print("=" * 80)
    print()

    geometry = FourWayGeometry()

    # Two right-turning vehicles from perpendicular approaches
    car1 = PathBasedVehicle("Main E", "R", 1, geometry)
    car2 = PathBasedVehicle("Green N", "R", 2, geometry)

    car1.activate(0.0)
    car2.activate(0.0)

    print("Test Case: Two right turns from perpendicular approaches")
    print(f"  Car1: {car1.road_name} → {car1.signal}")
    print(f"  Car2: {car2.road_name} → {car2.signal}")
    print()

    # Original detector
    from path_based_smart_stop import CollisionDetector
    original = CollisionDetector(safety_margin=3.0)
    original_result = original.check_collision(car1, car2)

    print(f"Original detector (distance-based): {original_result}")

    # Turn-aware detector
    turn_aware = TurnAwareCollisionDetector(safety_margin=3.0)
    turn_aware_result = turn_aware.check_collision(car1, car2)

    print(f"Turn-aware detector:                 {turn_aware_result}")
    print()

    if original_result and not turn_aware_result:
        print("✅ IMPROVEMENT DETECTED!")
        print("   Turn-aware detector correctly identifies these as non-conflicting")
        print("   This should allow Smart Stop to activate both simultaneously")
    elif not original_result and not turn_aware_result:
        print("✓ Both detectors agree - no collision")
    elif original_result and turn_aware_result:
        print("⚠️ Both detectors report collision - vehicles truly conflict")
    else:
        print("⚠️ Turn-aware detector is MORE conservative (unexpected)")

    return original_result, turn_aware_result


# =============================================================================
# Integration Instructions
# =============================================================================

if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 23 + "TURN-AWARE COLLISION" + " " * 35 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    test_turn_aware_detector()

    print("\n" + "=" * 80)
    print("INTEGRATION GUIDE")
    print("=" * 80)
    print("""
To integrate the turn-aware collision detector:

1. In path_based_smart_stop.py, replace the collision detector:

   from turn_aware_collision import TurnAwareCollisionDetector

   class PathBasedSmartStopAlgorithm:
       def __init__(self, geometry):
           # OLD: self.collision_detector = CollisionDetector(safety_margin=3.0)
           # NEW:
           self.collision_detector = TurnAwareCollisionDetector(safety_margin=3.0)

2. Same for SmartStopSafeAlgorithm:

   class SmartStopSafeAlgorithm:
       def __init__(self, geometry):
           self.collision_detector = TurnAwareCollisionDetector(safety_margin=4.0)

3. Run comprehensive_performance_test.py to verify improvement

Expected improvements:
- Right-turn scenarios: Should activate both vehicles simultaneously
- Smart Stop should now consistently beat Roundabout
- Overall performance improvement: 15-30% in multi-vehicle scenarios
    """)
    print("=" * 80)
    print()

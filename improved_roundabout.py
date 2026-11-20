#!/usr/bin/env python3
"""
Improved Roundabout Algorithm
=============================

This module provides an enhanced roundabout implementation that fixes
the simultaneous entry issue with realistic traffic rules.

THREE SOLUTIONS PROVIDED:
1. Minimum Time Gap: Simple timing-based approach
2. Yield-to-Left: Realistic roundabout priority rule
3. Hybrid: Combines both for most realistic behavior
"""

import numpy as np
from path_based_smart_stop import (
    RoundaboutAlgorithm,
    IntersectionGeometry,
    CollisionDetector
)


# =============================================================================
# SOLUTION 1: Minimum Time Gap
# =============================================================================

class RoundaboutWithTimeGap(RoundaboutAlgorithm):
    """
    Enforces minimum time gap between any vehicle entries.

    Pros:
    - Simple to implement
    - Realistic (simulates human reaction time)
    - Prevents traffic jam at entry

    Cons:
    - Might be too conservative (slower than necessary)
    - Doesn't reflect actual roundabout priority rules
    """

    def __init__(self, geometry: IntersectionGeometry, min_gap: float = 0.8):
        super().__init__(geometry)
        self.min_entry_gap = min_gap  # seconds
        self.last_entry_time = -999.0

    def _try_enter_roundabout(self):
        """Entry with minimum time gap enforcement"""

        # Check if enough time has passed since last entry
        if (self.current_time - self.last_entry_time) < self.min_entry_gap:
            return  # Too soon

        # Original logic for checking first waiting vehicle
        for waiting_vehicle in self.waiting_vehicles[:]:
            can_enter = True

            # Check collision with active vehicles
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(
                    waiting_vehicle, active_vehicle, time_horizon=3.0
                ):
                    can_enter = False
                    break

            if can_enter:
                self.waiting_vehicles.remove(waiting_vehicle)
                waiting_vehicle.activate(self.current_time)
                self.active_vehicles.append(waiting_vehicle)
                self.last_entry_time = self.current_time
                break  # One entry per step


# =============================================================================
# SOLUTION 2: Yield-to-Left Rule
# =============================================================================

class RoundaboutWithYieldToLeft(RoundaboutAlgorithm):
    """
    Implements realistic roundabout rule: yield to traffic from the left.

    In a roundabout (in countries that drive on the right), you yield to
    vehicles approaching from your left (already in the circle).

    Pros:
    - Realistic traffic rule
    - Priority-based (not arbitrary timing)
    - Allows efficient flow when safe

    Cons:
    - More complex logic
    - Needs proper approach position tracking
    """

    def __init__(self, geometry: IntersectionGeometry):
        super().__init__(geometry)

        # Clockwise approach positions (for right-hand traffic)
        self.approach_positions = {
            "Main W": 0,    # West
            "Green N": 1,   # North
            "Main E": 2,    # East
            "Green S": 3    # South
        }

    def _try_enter_roundabout(self):
        """Entry with yield-to-left rule"""

        for waiting_vehicle in self.waiting_vehicles[:]:
            can_enter = True

            # Rule 1: Yield to left (check if vehicle from left is waiting)
            if not self._check_yield_to_left(waiting_vehicle):
                can_enter = False

            # Rule 2: Check collision with active vehicles
            if can_enter:
                for active_vehicle in self.active_vehicles:
                    if self.collision_detector.check_collision(
                        waiting_vehicle, active_vehicle, time_horizon=3.0
                    ):
                        can_enter = False
                        break

            if can_enter:
                self.waiting_vehicles.remove(waiting_vehicle)
                waiting_vehicle.activate(self.current_time)
                self.active_vehicles.append(waiting_vehicle)
                break  # One per step for stability

    def _check_yield_to_left(self, vehicle) -> bool:
        """
        Check if vehicle must yield to traffic from the left.

        Returns:
            bool: True if clear to enter, False if must yield
        """
        if vehicle.road_name not in self.approach_positions:
            return True

        my_position = self.approach_positions[vehicle.road_name]

        # In roundabout, yield to traffic from the left
        # "Left" means the next position clockwise
        left_position = (my_position + 1) % 4

        # Check if any vehicle from the left is waiting or active
        for other_vehicle in self.waiting_vehicles:
            if other_vehicle == vehicle:
                continue

            if other_vehicle.road_name in self.approach_positions:
                other_position = self.approach_positions[other_vehicle.road_name]

                # If vehicle is to my left AND arrived earlier, I must yield
                if other_position == left_position and other_vehicle.order < vehicle.order:
                    return False

        return True


# =============================================================================
# SOLUTION 3: Hybrid Approach (RECOMMENDED)
# =============================================================================

class ImprovedRoundabout(RoundaboutAlgorithm):
    """
    Combines time gap + yield-to-left for most realistic behavior.

    This is the RECOMMENDED implementation as it balances:
    - Realistic traffic rules (yield-to-left)
    - Human behavior (reaction time via min gap)
    - Safety (collision detection)
    - Efficiency (allows flow when safe)

    Use this as the replacement for RoundaboutAlgorithm in your code.
    """

    def __init__(self, geometry: IntersectionGeometry, min_gap: float = 0.5):
        super().__init__(geometry)

        # Time-based constraints
        self.min_entry_gap = min_gap  # Minimum time between ANY entries
        self.last_entry_time = -999.0
        self.approach_last_entry = {  # Track last entry per approach
            "Main W": -999.0,
            "Green N": -999.0,
            "Main E": -999.0,
            "Green S": -999.0
        }

        # Spatial constraints
        self.approach_positions = {
            "Main W": 0, "Green N": 1, "Main E": 2, "Green S": 3
        }

        # Slightly more aggressive for roundabouts (can handle tighter spacing)
        self.collision_detector = CollisionDetector(safety_margin=3.0)

    def _try_enter_roundabout(self):
        """
        Realistic roundabout entry with three-layer safety:

        1. Time gap: Prevent simultaneous entries (reaction time)
        2. Yield-to-left: Follow roundabout priority rules
        3. Collision check: Ensure physical safety
        """

        # Layer 1: Minimum time gap (reaction time)
        if (self.current_time - self.last_entry_time) < self.min_entry_gap:
            return

        # Try each waiting vehicle in order
        for waiting_vehicle in self.waiting_vehicles[:]:
            can_enter = True

            # Layer 2: Yield-to-left rule
            if not self._check_yield_to_left(waiting_vehicle):
                can_enter = False

            # Layer 3: Collision detection
            if can_enter:
                for active_vehicle in self.active_vehicles:
                    if self.collision_detector.check_collision(
                        waiting_vehicle, active_vehicle, time_horizon=3.0
                    ):
                        can_enter = False
                        break

            # All checks passed - enter!
            if can_enter:
                self.waiting_vehicles.remove(waiting_vehicle)
                waiting_vehicle.activate(self.current_time)
                self.active_vehicles.append(waiting_vehicle)

                # Update timing
                self.last_entry_time = self.current_time
                if waiting_vehicle.road_name in self.approach_last_entry:
                    self.approach_last_entry[waiting_vehicle.road_name] = self.current_time

                # Allow only one entry per simulation step
                break

    def _check_yield_to_left(self, vehicle) -> bool:
        """
        Realistic yield-to-left rule for roundabouts.

        Priority rules:
        1. Active vehicles already in roundabout have priority over all
        2. Among waiting vehicles, those from the left have priority
        3. If vehicles from same approach, earlier arrival has priority
        """
        if vehicle.road_name not in self.approach_positions:
            return True

        my_position = self.approach_positions[vehicle.road_name]
        left_position = (my_position + 1) % 4

        # Check all other waiting vehicles
        for other_vehicle in self.waiting_vehicles:
            if other_vehicle == vehicle:
                continue

            if other_vehicle.road_name not in self.approach_positions:
                continue

            other_position = self.approach_positions[other_vehicle.road_name]

            # Rule 1: Yield to vehicle from the left
            if other_position == left_position:
                # But only if they arrived earlier or at same time
                if other_vehicle.order <= vehicle.order:
                    return False

            # Rule 2: Among vehicles from same approach, earlier has priority
            elif other_position == my_position:
                if other_vehicle.order < vehicle.order:
                    return False

        return True


# =============================================================================
# Comparison Test
# =============================================================================

def test_all_roundabouts():
    """Compare original vs improved roundabout implementations"""

    from path_based_smart_stop import RoundaboutGeometry, PathBasedVehicle

    print("=" * 80)
    print("ROUNDABOUT IMPLEMENTATION COMPARISON")
    print("=" * 80)

    geometry = RoundaboutGeometry()

    # Test scenario: 4 vehicles from all approaches
    test_configs = [
        ("Main E", "R", 1),
        ("Main W", "R", 2),
        ("Green N", "R", 3),
        ("Green S", "R", 4)
    ]

    print("\nTest Scenario:")
    for road, signal, order in test_configs:
        print(f"  Car{order}: {road} → {signal}")
    print()

    implementations = [
        ("Original Roundabout", RoundaboutAlgorithm),
        ("Time Gap Only", RoundaboutWithTimeGap),
        ("Yield-to-Left Only", RoundaboutWithYieldToLeft),
        ("Hybrid (Recommended)", ImprovedRoundabout)
    ]

    results = []

    for name, AlgorithmClass in implementations:
        print(f"Testing {name}...", end=" ")

        algorithm = AlgorithmClass(geometry)

        # Add vehicles
        for road, signal, order in test_configs:
            vehicle = PathBasedVehicle(road, signal, order, geometry, use_roundabout_paths=True)
            algorithm.add_vehicle(vehicle)

        # Run simulation
        for step in range(600):
            status = algorithm.step(0.1)
            if status['waiting'] == 0 and status['active'] == 0:
                break

        metrics = algorithm.get_metrics()
        results.append((name, metrics))

        print(f"{metrics['total_time']:.2f}s")

    # Summary
    print("\n" + "-" * 80)
    print("COMPARISON SUMMARY:")
    print("-" * 80)

    print(f"\n{'Implementation':<25} {'Time (s)':<12} {'Avg Wait (s)':<15} {'Throughput':<12}")
    print("-" * 70)

    for name, metrics in results:
        print(f"{name:<25} {metrics['total_time']:<12.2f} "
              f"{metrics['avg_wait_time']:<15.2f} {metrics['throughput']:<12.3f}")

    print("\n" + "=" * 80)
    print("RECOMMENDATION:")
    print("=" * 80)
    print("\nUse 'ImprovedRoundabout' for most realistic behavior.")
    print("It balances realistic traffic rules with computational efficiency.")
    print("\nTo use in your code:")
    print("  from improved_roundabout import ImprovedRoundabout")
    print("  algorithm = ImprovedRoundabout(geometry)")
    print("=" * 80)
    print()


if __name__ == "__main__":
    test_all_roundabouts()

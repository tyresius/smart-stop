#!/usr/bin/env python3
"""
Lane-Aware Collision Detection
================================

Fixes the median separation issue by checking if vehicles are on parallel
paths (opposite lanes) before using distance-based collision detection.

This allows Smart Stop to activate vehicles in opposite lanes simultaneously,
dramatically improving its performance advantage over traditional methods.
"""

import numpy as np
import math
from typing import Tuple


class LaneAwareCollisionDetector:
    """
    Enhanced collision detector that considers lane separation.

    Key improvement: Vehicles on parallel paths (opposite lanes) are not
    flagged as conflicts, even if within the safety margin distance.
    """

    def __init__(self, safety_margin: float = 3.0):
        self.safety_margin = safety_margin

        # Define which roads are parallel
        self.parallel_roads = {
            ("Main E", "Main W"): True,   # Opposite directions on Main St
            ("Main W", "Main E"): True,
            ("Green N", "Green S"): True,  # Opposite directions on Green St
            ("Green S", "Green N"): True,
        }

    def check_collision(self, vehicle1, vehicle2, time_horizon: float = 3.0) -> bool:
        """
        Check if vehicles will collide, considering lane separation.

        Returns:
            bool: True if collision possible, False if safe
        """
        if not (vehicle1.active or vehicle2.active):
            if not vehicle1.active and not vehicle2.active:
                return False

        # NEW: Check if vehicles are on parallel paths (opposite lanes)
        if self._are_on_parallel_paths(vehicle1, vehicle2):
            # Vehicles in opposite lanes on same road
            # They're separated by median - no collision possible
            return False

        # Otherwise, use standard distance-based collision detection
        return self._check_distance_collision(vehicle1, vehicle2, time_horizon)

    def _are_on_parallel_paths(self, vehicle1, vehicle2) -> bool:
        """
        Check if two vehicles are on parallel paths (opposite lanes).

        Returns:
            bool: True if on parallel paths (safe to activate together)
        """
        # Check if they're on roads that run parallel
        road_pair = (vehicle1.road_name, vehicle2.road_name)

        if road_pair in self.parallel_roads:
            # They're on the same road in opposite directions
            # Check if they're both going straight (most common case)
            if vehicle1.signal == "NS/S" and vehicle2.signal == "NS/S":
                return True  # Both straight, opposite directions = parallel

            # If one is turning, they might intersect - be conservative
            # (Could be enhanced further to check specific turn combinations)

        return False

    def _check_distance_collision(self, vehicle1, vehicle2,
                                  time_horizon: float) -> bool:
        """
        Standard distance-based collision check (original logic).
        """
        # Sample positions over time horizon
        time_steps = np.linspace(0, time_horizon, 15)

        for t in time_steps:
            pos1 = self._predict_position(vehicle1, t)
            pos2 = self._predict_position(vehicle2, t)

            if pos1 and pos2:
                distance = math.sqrt((pos1[0] - pos2[0]) ** 2 +
                                    (pos1[1] - pos2[1]) ** 2)
                if distance < self.safety_margin:
                    return True

        return False

    def _predict_position(self, vehicle, time_ahead: float) -> Tuple[float, float]:
        """Predict vehicle position after time_ahead seconds"""
        if not vehicle.active:
            if hasattr(vehicle, 'path_x') and len(vehicle.path_x) > 0:
                return (vehicle.path_x[0], vehicle.path_y[0])
            return None

        if hasattr(vehicle, 'state'):
            future_x = vehicle.state.x + vehicle.state.velocity * math.cos(
                vehicle.state.heading) * time_ahead
            future_y = vehicle.state.y + vehicle.state.velocity * math.sin(
                vehicle.state.heading) * time_ahead
            return (future_x, future_y)

        return (vehicle.x, vehicle.y)


# =============================================================================
# Enhanced Algorithms Using Lane-Aware Collision Detection
# =============================================================================

class SmartStopWithLaneAwareness:
    """
    Smart Stop algorithm with lane-aware collision detection.

    This is the FIXED version that should dramatically outperform the original.
    """

    def __init__(self, geometry):
        self.geometry = geometry
        # Use lane-aware collision detector instead of standard one
        self.collision_detector = LaneAwareCollisionDetector(safety_margin=3.0)
        self.active_vehicles = []
        self.waiting_vehicles = []
        self.completed_vehicles = []
        self.current_time = 0.0

        self.approach_positions = {
            "Main W": 0,
            "Green N": 1,
            "Main E": 2,
            "Green S": 3
        }

    def add_vehicle(self, vehicle):
        self.waiting_vehicles.append(vehicle)
        self.waiting_vehicles.sort(key=lambda v: v.order)

    def step(self, dt: float = 0.1):
        self.current_time += dt

        # Update active vehicles
        for vehicle in self.active_vehicles[:]:
            still_active = vehicle.update(dt, target_speed=2.0)
            if not still_active:
                self.active_vehicles.remove(vehicle)
                self.completed_vehicles.append(vehicle)

        # Smart Stop coordination
        self._coordinate_smart_movements()

        return {
            'time': self.current_time,
            'active': len(self.active_vehicles),
            'waiting': len(self.waiting_vehicles),
            'completed': len(self.completed_vehicles)
        }

    def _coordinate_smart_movements(self):
        """Smart coordination using turn signal information and backward priority"""
        if not self.active_vehicles and self.waiting_vehicles:
            first_vehicle = self.waiting_vehicles.pop(0)
            first_vehicle.activate(self.current_time)
            self.active_vehicles.append(first_vehicle)

        if self.waiting_vehicles:
            self._try_activate_smart_coordination()

    def _try_activate_smart_coordination(self):
        """Use backward priority and turn signal optimization"""
        active_positions = set()
        for vehicle in self.active_vehicles:
            if vehicle.road_name in self.approach_positions:
                active_positions.add(self.approach_positions[vehicle.road_name])

        candidates = []

        for waiting_vehicle in self.waiting_vehicles:
            if waiting_vehicle.road_name not in self.approach_positions:
                continue

            waiting_pos = self.approach_positions[waiting_vehicle.road_name]

            # Backward priority
            is_backward_priority = False
            for active_pos in active_positions:
                if (active_pos - waiting_pos) % 4 in [1, 2]:
                    is_backward_priority = True
                    break

            # Check if this vehicle can move without conflicts
            # NOW USES LANE-AWARE COLLISION DETECTION
            can_move = True
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(waiting_vehicle, active_vehicle):
                    can_move = False
                    break

            if can_move:
                priority_score = 0

                if is_backward_priority:
                    priority_score += 10

                # Turn signal optimization
                if waiting_vehicle.signal == "R":
                    priority_score += 5
                elif waiting_vehicle.signal == "NS/S":
                    priority_score += 3

                candidates.append((waiting_vehicle, priority_score))

        # Sort by priority and activate
        candidates.sort(key=lambda x: x[1], reverse=True)

        for vehicle, score in candidates:
            # Double-check no conflicts
            conflicts = False
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(vehicle, active_vehicle):
                    conflicts = True
                    break

            if not conflicts and len(self.active_vehicles) < 4:
                self.waiting_vehicles.remove(vehicle)
                vehicle.activate(self.current_time)
                self.active_vehicles.append(vehicle)

    def get_metrics(self):
        """Calculate performance metrics"""
        if not self.completed_vehicles:
            return {'total_time': 0, 'avg_wait_time': 0, 'throughput': 0,
                   'completed_vehicles': 0}

        total_time = self.current_time
        wait_times = [v.start_time for v in self.completed_vehicles if v.start_time is not None]
        avg_wait_time = np.mean(wait_times) if wait_times else 0
        throughput = len(self.completed_vehicles) / total_time if total_time > 0 else 0

        return {
            'total_time': total_time,
            'avg_wait_time': avg_wait_time,
            'throughput': throughput,
            'completed_vehicles': len(self.completed_vehicles)
        }


# =============================================================================
# Test & Compare
# =============================================================================

def test_lane_aware_improvement():
    """
    Compare original vs lane-aware collision detection
    """
    from path_based_smart_stop import (
        PathBasedVehicle,
        FourWayGeometry,
        PathBasedSmartStopAlgorithm
    )

    print("=" * 80)
    print("TESTING LANE-AWARE COLLISION DETECTION")
    print("=" * 80)
    print()

    geometry = FourWayGeometry()

    # Test scenario: Two cars going straight in opposite directions
    # This SHOULD allow simultaneous movement (opposite lanes)
    vehicles_config = [
        ("Main E", "NS/S", 1),  # Eastbound
        ("Main W", "NS/S", 2),  # Westbound
    ]

    print("Test Scenario: Two cars passing in opposite lanes")
    print(f"  Car1: Main E → Straight (eastbound lane)")
    print(f"  Car2: Main W → Straight (westbound lane)")
    print(f"  Expected: Should activate simultaneously (no conflict)\n")

    # Test Original Smart Stop
    print("1. ORIGINAL SMART STOP (distance-based collision)")
    print("-" * 60)

    original_algo = PathBasedSmartStopAlgorithm(geometry)
    for road, signal, order in vehicles_config:
        vehicle = PathBasedVehicle(road, signal, order, geometry)
        original_algo.add_vehicle(vehicle)

    for step in range(600):
        status = original_algo.step(0.1)
        if status['waiting'] == 0 and status['active'] == 0:
            break

    original_metrics = original_algo.get_metrics()
    print(f"Completion time: {original_metrics['total_time']:.2f}s")
    print(f"Avg wait time: {original_metrics['avg_wait_time']:.2f}s")

    # Test Lane-Aware Smart Stop
    print("\n2. LANE-AWARE SMART STOP (considers median separation)")
    print("-" * 60)

    fixed_algo = SmartStopWithLaneAwareness(geometry)
    for road, signal, order in vehicles_config:
        vehicle = PathBasedVehicle(road, signal, order, geometry)
        fixed_algo.add_vehicle(vehicle)

    for step in range(600):
        status = fixed_algo.step(0.1)
        if status['waiting'] == 0 and status['active'] == 0:
            break

    fixed_metrics = fixed_algo.get_metrics()
    print(f"Completion time: {fixed_metrics['total_time']:.2f}s")
    print(f"Avg wait time: {fixed_metrics['avg_wait_time']:.2f}s")

    # Compare
    print("\n" + "=" * 80)
    print("RESULTS COMPARISON")
    print("=" * 80)

    improvement = ((original_metrics['total_time'] - fixed_metrics['total_time']) /
                   original_metrics['total_time'] * 100)

    print(f"\nOriginal: {original_metrics['total_time']:.2f}s")
    print(f"Fixed:    {fixed_metrics['total_time']:.2f}s")
    print(f"Improvement: {improvement:.1f}% faster")

    if improvement > 5:
        print(f"\n✅ SIGNIFICANT IMPROVEMENT!")
        print(f"   Lane-aware collision detection allows simultaneous movement")
    else:
        print(f"\n⚠️  Minimal improvement - may need further investigation")

    return original_metrics, fixed_metrics


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 25 + "LANE-AWARE COLLISION" + " " * 33 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    test_lane_aware_improvement()

    print("\n" + "=" * 80)
    print("INTEGRATION GUIDE")
    print("=" * 80)
    print("""
To use the fixed collision detector in your code:

1. Replace the collision detector in PathBasedSmartStopAlgorithm:

   from lane_aware_collision import LaneAwareCollisionDetector

   class PathBasedSmartStopAlgorithm:
       def __init__(self, geometry):
           # OLD: self.collision_detector = CollisionDetector(safety_margin=3.0)
           # NEW:
           self.collision_detector = LaneAwareCollisionDetector(safety_margin=3.0)

2. Or use the complete SmartStopWithLaneAwareness class:

   from lane_aware_collision import SmartStopWithLaneAwareness

   algorithm = SmartStopWithLaneAwareness(geometry)

This fix should restore Smart Stop's performance advantage!
    """)
    print("=" * 80)
    print()

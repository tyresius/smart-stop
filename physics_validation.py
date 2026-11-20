#!/usr/bin/env python3
"""
Path-Based Smart Stop Sign System
==================================

Production-ready implementation of Smart Stop intersection algorithm with
continuous coordinate movement, realistic vehicle physics, and advanced
collision detection.

Four Algorithms:
1. Traditional Stop: Sequential (first-come, first-served) - baseline
2. Roundabout: Parallel with forward iteration
3. Smart Stop: Backward priority with turn signal optimization - BEST
4. Smart Safe: Conservative variant for early deployment

Key Features:
- Continuous coordinate movement (x,y positions)
- Realistic vehicle physics (velocity, acceleration from stop)
- Distance-based collision detection
- Time-based simulation (dt increments)
- Support for both 4-way stop and roundabout geometries
"""

import numpy as np
import math
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict


@dataclass
class VehicleState:
    """Current state of a vehicle in continuous space"""
    x: float
    y: float
    velocity: float  # m/s
    heading: float  # radians
    acceleration: float = 0.0  # m/s²


class IntersectionGeometry:
    """Base class for intersection geometry definitions"""

    def __init__(self, intersection_type: str):
        self.intersection_type = intersection_type
        self.danger_zones = {}
        self.entry_points = {}
        self.exit_points = {}

    def get_danger_zone(self, approach: str) -> Tuple[float, float, float, float]:
        """Return danger zone bounds (xmin, xmax, ymin, ymax) for approach"""
        return self.danger_zones.get(approach, (0, 0, 0, 0))

    def is_in_intersection(self, x: float, y: float) -> bool:
        """Check if point is within intersection bounds"""
        raise NotImplementedError


class FourWayGeometry(IntersectionGeometry):
    """4-way stop intersection geometry"""

    def __init__(self):
        super().__init__("4way")

        # Danger zones for each approach
        self.danger_zones = {
            "Main W": (0.645, 1.35, -0.645, 1.35),
            "Green N": (-1.35, 1.35, -0.645, 1.35),
            "Main E": (-1.35, 0.645, -1.35, 1.35),
            "Green S": (-1.35, 1.35, -1.35, -0.645)
        }

        # Entry points for each approach
        self.entry_points = {
            "Main W": (2, 0.5),
            "Green N": (-0.5, 2),
            "Main E": (-2, -0.5),
            "Green S": (0.5, -2)
        }

        # Exit points for each direction
        self.exit_points = {
            "Main W": (-2, 0.5),
            "Green N": (-0.5, -2),
            "Main E": (2, -0.5),
            "Green S": (0.5, 2)
        }

    def is_in_intersection(self, x: float, y: float) -> bool:
        """Check if point is within 4-way intersection bounds"""
        return -1.35 <= x <= 1.35 and -1.35 <= y <= 1.35


class RoundaboutGeometry(IntersectionGeometry):
    """Roundabout intersection geometry"""

    def __init__(self, radius: float = 1.5):
        super().__init__("roundabout")
        self.radius = radius

    def is_in_intersection(self, x: float, y: float) -> bool:
        """Check if point is within roundabout circle"""
        return x * x + y * y <= (self.radius + 0.5) ** 2


class PathBasedVehicle:
    """Vehicle with continuous path-based movement and realistic physics"""

    def __init__(self, road_name: str, signal: str, order: int,
                 geometry: IntersectionGeometry, use_roundabout_paths: bool = False):
        self.road_name = road_name
        self.signal = signal
        self.order = order
        self.geometry = geometry
        self.car_name = f"Car{order}"
        self.use_roundabout_paths = use_roundabout_paths

        # Physics properties
        self.max_speed = 2.0
        self.max_acceleration = 1.5
        self.max_deceleration = -1.0
        self.length = 4.5
        self.width = 2.0

        # Path and movement
        self.path_x = None
        self.path_y = None
        self.path_length_meters = 0.0
        self.current_position_meters = 0.0
        self.state = VehicleState(0, 0, 0, 0)

        # Simulation state
        self.active = False
        self.completed = False
        self.start_time = None
        self.current_time = 0.0

        # Generate path
        self._generate_path()

    def _generate_path(self):
        """Generate continuous path based on road and signal"""
        self.path_x, self.path_y = self._generate_4way_path()
        self.path_length_meters = self._calculate_actual_path_length()

        if len(self.path_x) > 0:
            self.state.x = self.path_x[0]
            self.state.y = self.path_y[0]
            self.state.heading = self._calculate_initial_heading()

    def _generate_4way_path(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate path for 4-way intersection"""
        x_array = []
        y_array = []
        i = 0

        if self.road_name == "Main E":
            if self.signal == "R":
                x = np.linspace(-2, -1, 100)
                y = np.linspace(-1, -2, 100)
                curve = np.linspace(np.pi / 2, 0, 79)
                while i < 280:
                    if i < 100:
                        x_array.append(x[i])
                        y_array.append(-0.5)
                    elif 100 <= i <= 178:
                        c_dex = i - 100
                        x_array.append(0.5 * np.cos(curve[c_dex]) - 1)
                        y_array.append(0.5 * np.sin(curve[c_dex]) - 1)
                    elif 279 > i >= 179:
                        k_dex = i - 179
                        x_array.append(-0.5)
                        y_array.append(y[k_dex])
                    else:
                        break
                    i += 1
            elif self.signal == "NS/S":
                str_xx = np.linspace(-2, 2, 400)
                while i < 400:
                    x_array.append(str_xx[i])
                    y_array.append(-0.5)
                    i += 1
            elif self.signal == "L":
                lex = np.linspace(-2, 0, 200)
                lye = np.linspace(0, 2, 200)
                lurve = np.linspace(1.5 * np.pi, 2 * np.pi, 79)
                while i < 480:
                    if i < 200:
                        x_array.append(lex[i])
                        y_array.append(-0.5)
                        i += 1
                    elif 200 <= i <= 278:
                        l_dex = i - 200
                        x_array.append(0.5 * np.cos(lurve[l_dex]))
                        y_array.append(0.5 * np.sin(lurve[l_dex]))
                        i += 1
                    elif 479 > i >= 279:
                        k_dex = i - 279
                        x_array.append(0.5)
                        y_array.append(lye[k_dex])
                        i += 1
                    else:
                        break

        elif self.road_name == "Main W":
            if self.signal == "R":
                bw_rx = np.linspace(2, 1, 100)
                bw_ry = np.linspace(1, 2, 100)
                bw_r_curve = np.linspace(1.5 * np.pi, np.pi, 79)
                while i < 279:
                    if i < 100:
                        x_array.append(bw_rx[i])
                        y_array.append(0.5)
                    elif 100 <= i <= 178:
                        bw_r_c_dex = i - 100
                        x_array.append(0.5 * np.cos(bw_r_curve[bw_r_c_dex]) + 1)
                        y_array.append(0.5 * np.sin(bw_r_curve[bw_r_c_dex]) + 1)
                    elif 279 > i >= 179:
                        bw_r_k_dex = i - 179
                        x_array.append(0.5)
                        y_array.append(bw_ry[bw_r_k_dex])
                    else:
                        break
                    i += 1
            elif self.signal == "NS/S":
                bw_str_xx = np.linspace(2, -2, 400)
                while i < 400:
                    x_array.append(bw_str_xx[i])
                    y_array.append(0.5)
                    i += 1
            elif self.signal == "L":
                bw_lex = np.linspace(2, 0, 200)
                bw_lye = np.linspace(0, -2, 200)
                bw_lurve = np.linspace(np.pi / 2, np.pi, 79)
                while i < 480:
                    if i < 200:
                        x_array.append(bw_lex[i])
                        y_array.append(0.5)
                        i += 1
                    elif 200 <= i <= 278:
                        bw_l_dex = i - 200
                        x_array.append(0.5 * np.cos(bw_lurve[bw_l_dex]))
                        y_array.append(0.5 * np.sin(bw_lurve[bw_l_dex]))
                        i += 1
                    elif 479 > i >= 279:
                        bw_k_dex = i - 280
                        x_array.append(-0.5)
                        y_array.append(bw_lye[bw_k_dex])
                        i += 1
                    else:
                        break

        elif self.road_name == "Green S":
            if self.signal == "R":
                rs_rx = np.linspace(1, 2, 100)
                rs_ry = np.linspace(-2, -1, 100)
                rs_r_curve = np.linspace(np.pi, np.pi / 2, 79)
                while i < 280:
                    if i < 100:
                        x_array.append(0.5)
                        y_array.append(rs_ry[i])
                    elif 100 <= i <= 178:
                        rs_r_c_dex = i - 100
                        x_array.append(0.5 * np.cos(rs_r_curve[rs_r_c_dex]) + 1)
                        y_array.append(0.5 * np.sin(rs_r_curve[rs_r_c_dex]) - 1)
                    elif 279 > i >= 179:
                        rs_r_k_dex = i - 179
                        x_array.append(rs_rx[rs_r_k_dex])
                        y_array.append(-0.5)
                    else:
                        break
                    i += 1
            elif self.signal == "NS/S":
                rs_str_yy = np.linspace(-2, 2, 400)
                while i < 400:
                    x_array.append(0.5)
                    y_array.append(rs_str_yy[i])
                    i += 1
            elif self.signal == "L":
                rs_lex = np.linspace(0, -2, 200)
                rs_lye = np.linspace(-2, 0, 200)
                rs_lurve = np.linspace(0, np.pi / 2, 79)
                while i < 500:
                    if i < 200:
                        x_array.append(0.5)
                        y_array.append(rs_lye[i])
                        i += 1
                    elif 200 <= i <= 278:
                        rs_l_dex = i - 200
                        x_array.append(0.5 * np.cos(rs_lurve[rs_l_dex]))
                        y_array.append(0.5 * np.sin(rs_lurve[rs_l_dex]))
                        i += 1
                    elif 479 > i >= 279:
                        rs_k_dex = i - 279
                        x_array.append(rs_lex[rs_k_dex])
                        y_array.append(0.5)
                        i += 1
                    else:
                        break

        elif self.road_name == "Green N":
            if self.signal == "R":
                rn_rx = np.linspace(-1, -2, 100)
                rn_ry = np.linspace(2, 1, 100)
                rn_r_curve = np.linspace(2 * np.pi, 3 * np.pi / 2, 79)
                while i < 280:
                    if i < 100:
                        x_array.append(-0.5)
                        y_array.append(rn_ry[i])
                    elif 100 <= i <= 178:
                        rn_r_c_dex = i - 100
                        x_array.append(0.5 * np.cos(rn_r_curve[rn_r_c_dex]) - 1)
                        y_array.append(0.5 * np.sin(rn_r_curve[rn_r_c_dex]) + 1)
                    elif 279 > i >= 179:
                        rn_r_k_dex = i - 179
                        x_array.append(rn_rx[rn_r_k_dex])
                        y_array.append(0.5)
                    else:
                        break
                    i += 1
            elif self.signal == "NS/S":
                rn_str_yy = np.linspace(2, -2, 400)
                while i < 400:
                    x_array.append(-0.5)
                    y_array.append(rn_str_yy[i])
                    i += 1
            elif self.signal == "L":
                rn_lex = np.linspace(0, 2, 200)
                rn_lye = np.linspace(2, 0, 200)
                rn_lurve = np.linspace(np.pi, 1.5 * np.pi, 79)
                while i < 480:
                    if i < 200:
                        x_array.append(-0.5)
                        y_array.append(rn_lye[i])
                        i += 1
                    elif 200 <= i <= 278:
                        rn_l_dex = i - 200
                        x_array.append(0.5 * np.cos(rn_lurve[rn_l_dex]))
                        y_array.append(0.5 * np.sin(rn_lurve[rn_l_dex]))
                        i += 1
                    elif 479 > i >= 279:
                        rn_k_dex = i - 279
                        x_array.append(rn_lex[rn_k_dex])
                        y_array.append(-0.5)
                        i += 1
                    else:
                        break

        return np.array(x_array), np.array(y_array)

    def _calculate_actual_path_length(self) -> float:
        """Calculate actual path length in meters"""
        if len(self.path_x) < 2:
            return 0.0

        total_length = 0.0
        for i in range(1, len(self.path_x)):
            dx = self.path_x[i] - self.path_x[i - 1]
            dy = self.path_y[i] - self.path_y[i - 1]
            segment_length = math.sqrt(dx * dx + dy * dy)
            total_length += segment_length

        return total_length

    def _calculate_initial_heading(self) -> float:
        """Calculate initial heading based on path direction"""
        if len(self.path_x) < 2:
            return 0.0

        dx = self.path_x[1] - self.path_x[0]
        dy = self.path_y[1] - self.path_y[0]
        return math.atan2(dy, dx)

    def _update_position_from_meters(self):
        """Update x,y coordinates based on meters traveled along path"""
        if len(self.path_x) < 2:
            return

        cumulative_distances = [0.0]
        for i in range(1, len(self.path_x)):
            dx = self.path_x[i] - self.path_x[i - 1]
            dy = self.path_y[i] - self.path_y[i - 1]
            segment_length = math.sqrt(dx * dx + dy * dy)
            cumulative_distances.append(cumulative_distances[-1] + segment_length)

        for i in range(len(cumulative_distances) - 1):
            if cumulative_distances[i] <= self.current_position_meters <= cumulative_distances[i + 1]:
                segment_length = cumulative_distances[i + 1] - cumulative_distances[i]
                if segment_length > 0:
                    progress = (self.current_position_meters - cumulative_distances[i]) / segment_length
                    progress = min(1.0, max(0.0, progress))

                    self.state.x = self.path_x[i] + progress * (self.path_x[i + 1] - self.path_x[i])
                    self.state.y = self.path_y[i] + progress * (self.path_y[i + 1] - self.path_y[i])

                    if i + 1 < len(self.path_x):
                        dx = self.path_x[i + 1] - self.path_x[i]
                        dy = self.path_y[i + 1] - self.path_y[i]
                        if dx != 0 or dy != 0:
                            self.state.heading = math.atan2(dy, dx)
                return

        if len(self.path_x) > 0:
            self.state.x = self.path_x[-1]
            self.state.y = self.path_y[-1]

    def activate(self, current_time: float):
        """Activate vehicle for movement"""
        self.active = True
        self.start_time = current_time
        self.current_time = current_time
        self.current_position_meters = 0.0
        self.completed = False

    def update(self, dt: float, target_speed: float = None) -> bool:
        """Update vehicle physics and position"""
        if not self.active or self.completed:
            return False

        self.current_time += dt

        if target_speed is None:
            if self.geometry.is_in_intersection(self.state.x, self.state.y):
                target_speed = 1.0
            else:
                target_speed = self.max_speed

        speed_diff = target_speed - self.state.velocity
        if abs(speed_diff) > 0.1:
            accel = np.clip(speed_diff * 2.0, self.max_deceleration, self.max_acceleration)
            self.state.acceleration = accel
            self.state.velocity += accel * dt
        else:
            self.state.acceleration = 0.0
            self.state.velocity = target_speed

        distance_traveled = self.state.velocity * dt
        self.current_position_meters += distance_traveled

        if self.current_position_meters >= self.path_length_meters:
            self.completed = True
            self.active = False
            return False

        self._update_position_from_meters()
        return True


class CollisionDetector:
    """Realistic collision detection based on vehicle dynamics"""

    def __init__(self, safety_margin: float = 2.5):
        self.safety_margin = safety_margin

    def check_collision(self, vehicle1: PathBasedVehicle, vehicle2: PathBasedVehicle,
                        time_horizon: float = 3.0) -> bool:
        """Check if vehicles will be too close within time horizon"""
        if not (vehicle1.active or vehicle2.active):
            if not vehicle1.active and not vehicle2.active:
                return False

        time_steps = np.linspace(0, time_horizon, 15)

        for t in time_steps:
            pos1 = self._predict_position(vehicle1, t)
            pos2 = self._predict_position(vehicle2, t)

            if pos1 and pos2:
                distance = math.sqrt((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2)
                if distance < self.safety_margin:
                    return True

        return False

    def _predict_position(self, vehicle: PathBasedVehicle, time_ahead: float) -> Optional[Tuple]:
        """Predict vehicle position after time_ahead seconds"""
        if not vehicle.active:
            if hasattr(vehicle, 'path_x') and len(vehicle.path_x) > 0:
                return (vehicle.path_x[0], vehicle.path_y[0])
            return None

        if hasattr(vehicle, 'state'):
            future_x = vehicle.state.x + vehicle.state.velocity * math.cos(vehicle.state.heading) * time_ahead
            future_y = vehicle.state.y + vehicle.state.velocity * math.sin(vehicle.state.heading) * time_ahead
            return (future_x, future_y)

        return (vehicle.state.x, vehicle.state.y)


# ============================================================================
# ALGORITHMS
# ============================================================================

class TraditionalStopAlgorithm:
    """Traditional 4-way stop: First-come, first-served, one at a time"""

    def __init__(self, geometry: IntersectionGeometry):
        self.geometry = geometry
        self.waiting_vehicles = []
        self.active_vehicle = None
        self.completed_vehicles = []
        self.current_time = 0.0

    def add_vehicle(self, vehicle: PathBasedVehicle):
        self.waiting_vehicles.append(vehicle)
        self.waiting_vehicles.sort(key=lambda v: v.order)

    def step(self, dt: float = 0.1) -> Dict:
        self.current_time += dt

        if self.active_vehicle:
            still_active = self.active_vehicle.update(dt)
            if not still_active:
                self.completed_vehicles.append(self.active_vehicle)
                self.active_vehicle = None

        if self.active_vehicle is None and self.waiting_vehicles:
            self.active_vehicle = self.waiting_vehicles.pop(0)
            self.active_vehicle.activate(self.current_time)

        return {
            'time': self.current_time,
            'active': 1 if self.active_vehicle else 0,
            'waiting': len(self.waiting_vehicles),
            'completed': len(self.completed_vehicles)
        }

    def get_metrics(self) -> Dict:
        if not self.completed_vehicles:
            return {'total_time': 0, 'avg_wait_time': 0, 'throughput': 0, 'completed_vehicles': 0}

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


class RoundaboutAlgorithm:
    """Roundabout: Yield to traffic in circle, continuous flow when possible"""

    def __init__(self, geometry: IntersectionGeometry):
        self.geometry = geometry
        self.collision_detector = CollisionDetector(safety_margin=3.5)
        self.active_vehicles = []
        self.waiting_vehicles = []
        self.completed_vehicles = []
        self.current_time = 0.0

    def add_vehicle(self, vehicle: PathBasedVehicle):
        self.waiting_vehicles.append(vehicle)
        self.waiting_vehicles.sort(key=lambda v: v.order)

    def step(self, dt: float = 0.1) -> Dict:
        self.current_time += dt

        for vehicle in self.active_vehicles[:]:
            still_active = vehicle.update(dt, target_speed=3.5)
            if not still_active:
                self.active_vehicles.remove(vehicle)
                self.completed_vehicles.append(vehicle)

        self._try_enter_roundabout()

        return {
            'time': self.current_time,
            'active': len(self.active_vehicles),
            'waiting': len(self.waiting_vehicles),
            'completed': len(self.completed_vehicles)
        }

    def _try_enter_roundabout(self):
        """Roundabout entry: Yield to traffic already in the circle"""
        for waiting_vehicle in self.waiting_vehicles[:]:
            can_enter = True

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
                break  # Conservative: one entry at a time

    def get_metrics(self) -> Dict:
        if not self.completed_vehicles:
            return {'total_time': 0, 'avg_wait_time': 0, 'throughput': 0, 'completed_vehicles': 0}

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


class PathBasedSmartStopAlgorithm:
    """
    Smart Stop: Uses turn signals and backward priority for optimization

    Key Innovation: Activates vehicles entering from positions BEHIND active
    vehicles, enabling much more parallelism than traditional forward-only logic.
    """

    def __init__(self, geometry: IntersectionGeometry):
        self.geometry = geometry
        self.collision_detector = CollisionDetector(safety_margin=2.5)
        self.active_vehicles = []
        self.waiting_vehicles = []
        self.completed_vehicles = []
        self.current_time = 0.0

        self.approach_positions = {
            "Main W": 0, "Green N": 1, "Main E": 2, "Green S": 3
        }

    def add_vehicle(self, vehicle: PathBasedVehicle):
        self.waiting_vehicles.append(vehicle)
        self.waiting_vehicles.sort(key=lambda v: v.order)

    def step(self, dt: float = 0.1) -> Dict:
        self.current_time += dt

        for vehicle in self.active_vehicles[:]:
            still_active = vehicle.update(dt)
            if not still_active:
                self.active_vehicles.remove(vehicle)
                self.completed_vehicles.append(vehicle)

        self._coordinate_smart_movements()

        return {
            'time': self.current_time,
            'active': len(self.active_vehicles),
            'waiting': len(self.waiting_vehicles),
            'completed': len(self.completed_vehicles)
        }

    def _coordinate_smart_movements(self):
        """Smart coordination using backward priority and turn signals"""

        if not self.active_vehicles and self.waiting_vehicles:
            first_vehicle = self.waiting_vehicles.pop(0)
            first_vehicle.activate(self.current_time)
            self.active_vehicles.append(first_vehicle)

        if self.waiting_vehicles:
            self._try_activate_smart_coordination()

    def _try_activate_smart_coordination(self):
        """Activate non-conflicting vehicles using backward priority"""

        active_positions = set()
        for vehicle in self.active_vehicles:
            if vehicle.road_name in self.approach_positions:
                active_positions.add(self.approach_positions[vehicle.road_name])

        candidates = []

        for waiting_vehicle in self.waiting_vehicles:
            if waiting_vehicle.road_name not in self.approach_positions:
                continue

            waiting_pos = self.approach_positions[waiting_vehicle.road_name]

            # Backward priority: vehicles 1-2 positions behind get priority
            is_backward_priority = False
            for active_pos in active_positions:
                if (active_pos - waiting_pos) % 4 in [1, 2]:
                    is_backward_priority = True
                    break

            # Check for collisions
            can_move = True
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(waiting_vehicle, active_vehicle):
                    can_move = False
                    break

            if can_move:
                priority_score = 0

                if is_backward_priority:
                    priority_score += 10

                if waiting_vehicle.signal == "R":
                    priority_score += 5
                elif waiting_vehicle.signal == "NS/S":
                    priority_score += 3

                candidates.append((waiting_vehicle, priority_score))

        candidates.sort(key=lambda x: x[1], reverse=True)

        for vehicle, score in candidates:
            conflicts = False
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(vehicle, active_vehicle):
                    conflicts = True
                    break

            if not conflicts and len(self.active_vehicles) < 4:
                self.waiting_vehicles.remove(vehicle)
                vehicle.activate(self.current_time)
                self.active_vehicles.append(vehicle)

    def get_metrics(self) -> Dict:
        if not self.completed_vehicles:
            return {'total_time': 0, 'avg_wait_time': 0, 'throughput': 0, 'completed_vehicles': 0}

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


class SmartStopSafeAlgorithm(PathBasedSmartStopAlgorithm):
    """
    Smart Stop Safe Mode: Conservative variant for early deployment

    Same logic as Smart Stop but:
    - Larger safety margins (3.0m instead of 2.5m)
    - Treats NS/S (no signal) as left turn (worst case)
    - More conservative activation
    """

    def __init__(self, geometry: IntersectionGeometry):
        super().__init__(geometry)
        self.collision_detector = CollisionDetector(safety_margin=3.0)

    def step(self, dt: float = 0.1) -> Dict:
        self.current_time += dt

        for vehicle in self.active_vehicles[:]:
            still_active = vehicle.update(dt, target_speed=2.5)
            if not still_active:
                self.active_vehicles.remove(vehicle)
                self.completed_vehicles.append(vehicle)

        self._coordinate_safe_movements()

        return {
            'time': self.current_time,
            'active': len(self.active_vehicles),
            'waiting': len(self.waiting_vehicles),
            'completed': len(self.completed_vehicles)
        }

    def _coordinate_safe_movements(self):
        """Conservative coordination - same logic but more cautious"""

        if not self.active_vehicles and self.waiting_vehicles:
            first_vehicle = self.waiting_vehicles.pop(0)
            first_vehicle.activate(self.current_time)
            self.active_vehicles.append(first_vehicle)
            return

        if len(self.active_vehicles) >= 2:
            return

        if self.waiting_vehicles:
            self._try_activate_safe_coordination()

    def _try_activate_safe_coordination(self):
        """Conservative version with larger safety margins and limited parallelism"""

        active_positions = set()
        for vehicle in self.active_vehicles:
            if vehicle.road_name in self.approach_positions:
                active_positions.add(self.approach_positions[vehicle.road_name])

        candidates = []

        for waiting_vehicle in self.waiting_vehicles:
            if waiting_vehicle.road_name not in self.approach_positions:
                continue

            waiting_pos = self.approach_positions[waiting_vehicle.road_name]

            is_backward_priority = False
            for active_pos in active_positions:
                if (active_pos - waiting_pos) % 4 in [1, 2]:
                    is_backward_priority = True
                    break

            can_move = True
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(
                        waiting_vehicle, active_vehicle, time_horizon=4.0
                ):
                    can_move = False
                    break

            effective_signal = "L" if waiting_vehicle.signal == "NS/S" else waiting_vehicle.signal

            if can_move:
                priority_score = 0

                if is_backward_priority:
                    priority_score += 10

                if effective_signal == "R":
                    priority_score += 5
                elif waiting_vehicle.signal == "NS/S":
                    priority_score += 1

                candidates.append((waiting_vehicle, priority_score))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            vehicle, score = candidates[0]

            conflicts = False
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(vehicle, active_vehicle):
                    conflicts = True
                    break

            if not conflicts:
                self.waiting_vehicles.remove(vehicle)
                vehicle.activate(self.current_time)
                self.active_vehicles.append(vehicle)
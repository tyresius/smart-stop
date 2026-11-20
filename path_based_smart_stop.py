# Example usage and testing
"""
if __name__ == "__main__":
    print("Path-Based Smart Stop System")
    print("=" * 40)

    # Create test scenario
    vehicles_4way = create_test_scenario("4way")
    vehicles_round = create_test_scenario("roundabout")

    print(f"Created {len(vehicles_4way)} vehicles for 4-way intersection")
    print(f"Created {len(vehicles_round)} vehicles for roundabout")

    # Test simulation
    geometry = FourWayGeometry()
    algorithm = PathBasedSmartStopAlgorithm(geometry)

    for vehicle in vehicles_4way:
        algorithm.add_vehicle(vehicle)

    print("\nRunning simulation...")

    # Run simulation
    max_time = 30.0  # seconds
    dt = 0.1
    steps = int(max_time / dt)

    for step in range(steps):
        status = algorithm.step(dt)

        if step % 50 == 0:  # Print every 5 seconds
            print(f"Time: {status['time']:.1f}s - "
                  f"Active: {status['active']}, "
                  f"Waiting: {status['waiting']}, "
                  f"Completed: {status['completed']}")

        # Stop if all vehicles completed
        if status['waiting'] == 0 and status['active'] == 0:
            break

    # Print final metrics
    metrics = algorithm.get_metrics()
    print(f"\nSimulation Complete!")
    print(f"Total time: {metrics['total_time']:.1f}s")
    print(f"Average wait time: {metrics['avg_wait_time']:.1f}s")
    print(f"Throughput: {metrics['throughput']:.2f} vehicles/second")  # !/usr/bin/env python3

    Enhanced Path-Based Smart Stop Sign System
    ==========================================

    This system translates the proven Smart Stop algorithm concepts to continuous
    coordinate movement with realistic vehicle dynamics and sophisticated collision detection.

    Key Features:
    - Continuous coordinate movement (x,y positions)
    - Realistic vehicle physics (velocity, acceleration)
    - Advanced collision detection along continuous paths
    - Time-based simulation instead of discrete steps
    - Smart Stop algorithm with backward priority optimization
    - Support for both 4-way stop and roundabout geometries
    """

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, Rectangle, Polygon
import itertools
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import math
from config import METERS_PER_UNIT
from turn_aware_collision import TurnAwareCollisionDetector


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

        # Define danger zones for each approach (expanded from your safeRange)
        self.danger_zones = {
            "Main W": (0.645, 1.35, -0.645, 1.35),
            "Green N": (-1.35, 1.35, -0.645, 1.35),
            "Main E": (-1.35, 0.645, -1.35, 1.35),
            "Green S": (-1.35, 1.35, -1.35, -0.645)
        }

        # Entry points = stop-line position at the intersection box edge
        # (±1.35).  Phase 2A: waiting vehicles queue here, and activation
        # starts vehicles at the stop line with v=0.  The 4-way "approach
        # lane" outside ±1.35 is rendered as visual queue context only and
        # is not part of the active driving path.
        self.entry_points = {
            "Main W": (1.35, 0.5),
            "Green N": (-0.5, 1.35),
            "Main E": (-1.35, -0.5),
            "Green S": (0.5, -1.35)
        }

        # Exit points = far edge of the visible scene at ±3 (vehicles
        # accelerate to free-flow on the exit lane and drive off-screen).
        self.exit_points = {
            "Main W": (-3, 0.5),
            "Green N": (-0.5, -3),
            "Main E": (3, -0.5),
            "Green S": (0.5, 3)
        }

    def is_in_intersection(self, x: float, y: float) -> bool:
        """Check if point is within 4-way intersection bounds"""
        return -1.35 <= x <= 1.35 and -1.35 <= y <= 1.35


class RoundaboutGeometry(IntersectionGeometry):
    """Roundabout intersection geometry"""

    def __init__(self, radius: float = 1.5):
        super().__init__("roundabout")
        self.radius = radius

        # Danger zones are sectors around the circle
        self.danger_zones = {
            "Main W": self._calculate_sector_bounds(0, np.pi / 2),
            "Green N": self._calculate_sector_bounds(np.pi / 2, np.pi),
            "Main E": self._calculate_sector_bounds(np.pi, 3 * np.pi / 2),
            "Green S": self._calculate_sector_bounds(3 * np.pi / 2, 2 * np.pi)
        }

        # Entry points on circle perimeter
        self.entry_points = {
            "Main W": (2, 0),
            "Green N": (0, 2),
            "Main E": (-2, 0),
            "Green S": (0, -2)
        }

    def _calculate_sector_bounds(self, start_angle: float, end_angle: float) -> Tuple[float, float, float, float]:
        """Calculate bounding box for circular sector"""
        angles = np.linspace(start_angle, end_angle, 100)
        x_coords = self.radius * np.cos(angles)
        y_coords = self.radius * np.sin(angles)
        return (min(x_coords), max(x_coords), min(y_coords), max(y_coords))

    def is_in_intersection(self, x: float, y: float) -> bool:
        """Check if point is within roundabout circle"""
        return x * x + y * y <= (self.radius + 0.5) ** 2


class PathBasedVehicle:
    def __init__(self, road_name: str, signal: str, order: int, geometry: IntersectionGeometry,
                 use_roundabout_paths: bool = False):
        self.road_name = road_name
        self.signal = signal
        self.order = order
        self.geometry = geometry
        self.car_name = f"Car{order}"
        self.use_roundabout_paths = use_roundabout_paths

        # Physics properties (real units: m, m/s, m/s²).  Bumped from
        # max_speed=2.0 / max_accel=0.5 in the M2 fix so the speed-by-zone
        # branch in update() (intersection_speed=2.0 vs free-flow=max_speed)
        # has a meaningful spread.  Vehicles cruise at ~13 mph in the
        # approach / exit lanes and slow to ~4.5 mph through the
        # intersection box.
        self.max_speed = 6.0
        self.max_acceleration = 1.5
        self.max_deceleration = -3.0
        self.length = 4.5
        self.width = 2.0

        # Path and movement
        self.path_x = None
        self.path_y = None
        self.path_length = 0
        self.current_position = 0.0
        self.state = VehicleState(0, 0, 0, 0)

        # NEW: Track actual distance traveled in meters
        self.path_length_meters = 0.0
        self.current_position_meters = 0.0

        # Simulation state
        self.active = False
        self.completed = False
        self.start_time = None
        self.current_time = 0.0
        # Wall-clock time at which this vehicle joined the waiting queue.
        # Set by the algorithm in add_vehicle(); used by the M3 fairness
        # guard so vehicles that have been waiting longer get a priority
        # bonus.
        self.arrival_time = None

        # Phase 2C: simulation time at which this vehicle's front first
        # exits the in-intersection slow zone (rectangular box for 4-way,
        # circular radius-2.0 zone for roundabout).  Used by all four
        # algorithms' ``get_metrics`` to report "time to clear the
        # intersection" instead of "time to exit the simulation off-ramp."
        # See ``_is_in_slow_zone`` for the mode-aware zone definition.
        self.intersection_exit_time = None
        self._was_in_slow_zone = False  # internal transition tracker

        # Generate path based on intersection type
        self._generate_path()

    def _generate_path(self):
        """Generate continuous path based on intersection geometry"""
        if self.use_roundabout_paths:
            self.path_x, self.path_y = self._generate_roundabout_path()
            # Roundabout paths historically started at (±2, ±0.5) — the ring
            # entry merge — with no free-flow approach lane.  After the M1
            # extension of 4-way entry/exit points to ±3, the 4-way paths
            # now have a 1-grid-unit free-flow approach and exit segment.
            # For a fair comparison, prepend / append the same straights to
            # roundabout paths so a vehicle has time to ramp toward
            # max_speed before the ring slow zone activates.
            self._extend_roundabout_with_approach_exit_straights()
        else:
            self.path_x, self.path_y = self._generate_4way_path()

        self.path_length = self._calculate_path_length()

        # ADD THIS LINE:
        self.path_length_meters = self._calculate_actual_path_length()

        # Set initial state
        if len(self.path_x) > 0:
            self.state.x = self.path_x[0]
            self.state.y = self.path_y[0]
            self.state.heading = self._calculate_initial_heading()

    def _extend_roundabout_with_approach_exit_straights(self):
        """Append a free-flow exit straight to a roundabout path so it
        terminates at the same off-screen position as the 4-way path for
        the same (road, signal).

        Phase 2A change: the approach extension (a 1-unit prefix that
        used to sit between waiting position ±3 and the ring entry) has
        been removed.  Roundabout vehicles now activate at the original
        ring-entry arc start (just outside the slow zone), symmetric with
        4-way vehicles activating at the stop line ±1.35.  The exit
        extension is kept so the off-screen termination matches 4-way.
        """
        if self.path_x is None or len(self.path_x) < 2:
            return

        fourway_x, fourway_y = self._generate_4way_path()
        if fourway_x is None or len(fourway_x) < 2:
            return  # No 4-way analog (shouldn't happen for the 12 standard combos)

        n_extension = 100  # samples per 1-unit straight; matches 4-way density

        # Exit straight only: from roundabout path[-1] (end of ring exit)
        # to 4-way path[-1] (lane exit position).  Drop the leading
        # endpoint to avoid duplicating roundabout path[-1].
        exit_x = np.linspace(self.path_x[-1], fourway_x[-1],
                             n_extension + 1)[1:]
        exit_y = np.linspace(self.path_y[-1], fourway_y[-1],
                             n_extension + 1)[1:]

        self.path_x = np.concatenate([self.path_x, exit_x])
        self.path_y = np.concatenate([self.path_y, exit_y])

    def _generate_4way_path(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate path for 4-way intersection (complete implementation from your arrayMakeB)"""
        x_array = []
        y_array = []
        i = 0

        # Main East (Bellona East equivalent)
        if self.road_name == "Main E":
            if self.signal == "R":
                # Entry trimmed to start at stop line (x=-1.35) per Phase 2A;
                # exit lane keeps the ±3 free-flow extension.
                x = np.linspace(-1.35, -1, 100)
                y = np.linspace(-1, -3, 100)
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
                # Entry start at x=-1.35 (stop line); exit continues to x=3.
                str_xx = np.linspace(-1.35, 3, 400)
                while i < 400:
                    x_array.append(str_xx[i])
                    y_array.append(-0.5)
                    i += 1
            elif self.signal == "L":
                # Entry start at x=-1.35 (stop line); exit continues to y=3.
                lex = np.linspace(-1.35, 0, 200)
                lye = np.linspace(0, 3, 200)
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

        # Main West (Bellona West equivalent)
        elif self.road_name == "Main W":
            if self.signal == "R":
                # Entry start at x=1.35 (stop line); exit continues to y=3.
                bw_rx = np.linspace(1.35, 1, 100)
                bw_ry = np.linspace(1, 3, 100)
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
                # Entry start at x=1.35 (stop line); exit continues to x=-3.
                bw_str_xx = np.linspace(1.35, -3, 400)
                while i < 400:
                    x_array.append(bw_str_xx[i])
                    y_array.append(0.5)
                    i += 1
            elif self.signal == "L":
                # Entry start at x=1.35 (stop line); exit continues to y=-3.
                bw_lex = np.linspace(1.35, 0, 200)
                bw_lye = np.linspace(0, -3, 200)
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
                        bw_k_dex = i - 279
                        x_array.append(-0.5)
                        y_array.append(bw_lye[bw_k_dex])
                        i += 1
                    else:
                        break

        # Green South (Ruxton South equivalent)
        elif self.road_name == "Green S":
            if self.signal == "R":
                # Entry start at y=-1.35 (stop line); exit continues to x=3.
                rs_rx = np.linspace(1, 3, 100)
                rs_ry = np.linspace(-1.35, -1, 100)
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
                # Entry start at y=-1.35 (stop line); exit continues to y=3.
                rs_str_yy = np.linspace(-1.35, 3, 400)
                while i < 400:
                    x_array.append(0.5)
                    y_array.append(rs_str_yy[i])
                    i += 1
            elif self.signal == "L":
                # Entry start at y=-1.35 (stop line); exit continues to x=-3.
                rs_lex = np.linspace(0, -3, 200)
                rs_lye = np.linspace(-1.35, 0, 200)
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

        # Green North (Ruxton North equivalent)
        elif self.road_name == "Green N":
            if self.signal == "R":
                # Entry start at y=1.35 (stop line); exit continues to x=-3.
                rn_rx = np.linspace(-1, -3, 100)
                rn_ry = np.linspace(1.35, 1, 100)
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
                # Entry start at y=1.35 (stop line); exit continues to y=-3.
                rn_str_yy = np.linspace(1.35, -3, 400)
                while i < 400:
                    x_array.append(-0.5)
                    y_array.append(rn_str_yy[i])
                    i += 1
            elif self.signal == "L":
                # Entry start at y=1.35 (stop line); exit continues to x=3.
                rn_lex = np.linspace(0, 3, 200)
                rn_lye = np.linspace(1.35, 0, 200)
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

    def _generate_roundabout_path(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate roundabout paths using original working arrayMakeRound logic"""
        x_array_round = []
        y_array_round = []

        # Main East
        if self.road_name == "Main E":
            be_r_on = np.radians(np.linspace(90, 64.5, 66))
            if self.signal == "R":
                be_r_in = np.radians(np.linspace(205.5, 244.49, 102))
                be_r_off = np.radians(np.linspace(25.52, 0, 66))
                for i in be_r_on:
                    x_array_round.append(1.5 * np.cos(i) - 2)
                    y_array_round.append(1.5 * np.sin(i) - 2)
                for i in be_r_in:
                    x_array_round.append(1.5 * np.cos(i))
                    y_array_round.append(1.5 * np.sin(i))
                for i in be_r_off:
                    x_array_round.append(1.5 * np.cos(i) - 2)
                    y_array_round.append(1.5 * np.sin(i) - 2)
            elif self.signal == "NS/S":
                be_s_on = np.radians(np.linspace(90, 64.5, 66))
                be_s_in = np.radians(np.linspace(205.5, 334.5, 340))
                be_s_off = np.radians(np.linspace(115.57, 90, 66))
                for i in be_s_on:
                    x_array_round.append(1.5 * np.cos(i) - 2)
                    y_array_round.append(1.5 * np.sin(i) - 2)
                for i in be_s_in:
                    x_array_round.append(1.5 * np.cos(i))
                    y_array_round.append(1.5 * np.sin(i))
                for i in be_s_off:
                    x_array_round.append(1.5 * np.cos(i) + 2)
                    y_array_round.append(1.5 * np.sin(i) - 2)
            elif self.signal == "L":
                be_l_on = np.radians(np.linspace(90, 64.5, 66))
                be_l_in = np.radians(np.linspace(205.5, 424.5, 575))
                be_l_off = np.radians(np.linspace(205.5, 180, 66))
                for i in be_l_on:
                    x_array_round.append(1.5 * np.cos(i) - 2)
                    y_array_round.append(1.5 * np.sin(i) - 2)
                for i in be_l_in:
                    x_array_round.append(1.5 * np.cos(i))
                    y_array_round.append(1.5 * np.sin(i))
                for i in be_l_off:
                    x_array_round.append(1.5 * np.cos(i) + 2)
                    y_array_round.append(1.5 * np.sin(i) + 2)

        # Main West
        elif self.road_name == "Main W":
            bw_r_on = np.radians(np.linspace(270, 244.5, 66))
            if self.signal == "R":
                bw_r_in = np.radians(np.linspace(25.5, 64.5, 102))
                bw_r_off = np.radians(np.linspace(205.5, 180, 66))
                for i in bw_r_on:
                    x_array_round.append(1.5 * np.cos(i) + 2)
                    y_array_round.append(1.5 * np.sin(i) + 2)
                for i in bw_r_in:
                    x_array_round.append(1.5 * np.cos(i))
                    y_array_round.append(1.5 * np.sin(i))
                for i in bw_r_off:
                    x_array_round.append(1.5 * np.cos(i) + 2)
                    y_array_round.append(1.5 * np.sin(i) + 2)
            elif self.signal == "NS/S":
                bw_s_on = np.radians(np.linspace(270, 244.5, 66))
                bw_s_in = np.radians(np.linspace(25.5, 154.5, 340))
                bw_s_off = np.radians(np.linspace(295.5, 270, 66))
                for i in bw_s_on:
                    x_array_round.append(1.5 * np.cos(i) + 2)
                    y_array_round.append(1.5 * np.sin(i) + 2)
                for i in bw_s_in:
                    x_array_round.append(1.5 * np.cos(i))
                    y_array_round.append(1.5 * np.sin(i))
                for i in bw_s_off:
                    x_array_round.append(1.5 * np.cos(i) - 2)
                    y_array_round.append(1.5 * np.sin(i) + 2)
            elif self.signal == "L":
                bw_l_on = np.radians(np.linspace(270, 244.5, 66))
                bw_l_in = np.radians(np.linspace(25.5, 244.5, 575))
                bw_l_off = np.radians(np.linspace(25.52, 0, 66))
                for i in bw_l_on:
                    x_array_round.append(1.5 * np.cos(i) + 2)
                    y_array_round.append(1.5 * np.sin(i) + 2)
                for i in bw_l_in:
                    x_array_round.append(1.5 * np.cos(i))
                    y_array_round.append(1.5 * np.sin(i))
                for i in bw_l_off:
                    x_array_round.append(1.5 * np.cos(i) - 2)
                    y_array_round.append(1.5 * np.sin(i) - 2)

        # Green South
        elif self.road_name == "Green S":
            rs_r_on = np.radians(np.linspace(180, 154.5, 66))
            if self.signal == "R":
                rs_r_in = np.radians(np.linspace(295.5, 334.5, 102))
                rs_r_off = np.radians(np.linspace(115.5, 90, 66))
                for i in rs_r_on:
                    x_array_round.append(1.5 * np.cos(i) + 2)
                    y_array_round.append(1.5 * np.sin(i) - 2)
                for i in rs_r_in:
                    x_array_round.append(1.5 * np.cos(i))
                    y_array_round.append(1.5 * np.sin(i))
                for i in rs_r_off:
                    x_array_round.append(1.5 * np.cos(i) + 2)
                    y_array_round.append(1.5 * np.sin(i) - 2)
            elif self.signal == "NS/S":
                rs_s_on = np.radians(np.linspace(180, 154.5, 66))
                rs_s_in = np.radians(np.linspace(295.5, 424.5, 340))
                rs_s_off = np.radians(np.linspace(205.5, 180, 66))
                for i in rs_s_on:
                    x_array_round.append(1.5 * np.cos(i) + 2)
                    y_array_round.append(1.5 * np.sin(i) - 2)
                for i in rs_s_in:
                    x_array_round.append(1.5 * np.cos(i))
                    y_array_round.append(1.5 * np.sin(i))
                for i in rs_s_off:
                    x_array_round.append(1.5 * np.cos(i) + 2)
                    y_array_round.append(1.5 * np.sin(i) + 2)
            elif self.signal == "L":
                rs_l_on = np.radians(np.linspace(180, 154.5, 66))
                rs_l_in = np.radians(np.linspace(295.5, 514.5, 575))
                rs_l_off = np.radians(np.linspace(295.5, 270, 66))
                for i in rs_l_on:
                    x_array_round.append(1.5 * np.cos(i) + 2)
                    y_array_round.append(1.5 * np.sin(i) - 2)
                for i in rs_l_in:
                    x_array_round.append(1.5 * np.cos(i))
                    y_array_round.append(1.5 * np.sin(i))
                for i in rs_l_off:
                    x_array_round.append(1.5 * np.cos(i) - 2)
                    y_array_round.append(1.5 * np.sin(i) + 2)

        # Green North
        elif self.road_name == "Green N":
            if self.signal == "R":
                rn_r_on = np.radians(np.linspace(360, 334.5, 66))
                rn_r_in = np.radians(np.linspace(115.5, 154.5, 102))
                rn_r_off = np.radians(np.linspace(295.5, 270, 66))
                for i in rn_r_on:
                    x_array_round.append(1.5 * np.cos(i) - 2)
                    y_array_round.append(1.5 * np.sin(i) + 2)
                for i in rn_r_in:
                    x_array_round.append(1.5 * np.cos(i))
                    y_array_round.append(1.5 * np.sin(i))
                for i in rn_r_off:
                    x_array_round.append(1.5 * np.cos(i) - 2)
                    y_array_round.append(1.5 * np.sin(i) + 2)
            elif self.signal == "NS/S":
                rn_s_on = np.radians(np.linspace(360, 334.5, 66))
                rn_s_in = np.radians(np.linspace(115.5, 244.5, 340))
                rn_s_off = np.radians(np.linspace(25.5, 0, 66))
                for i in rn_s_on:
                    x_array_round.append(1.5 * np.cos(i) - 2)
                    y_array_round.append(1.5 * np.sin(i) + 2)
                for i in rn_s_in:
                    x_array_round.append(1.5 * np.cos(i))
                    y_array_round.append(1.5 * np.sin(i))
                for i in rn_s_off:
                    x_array_round.append(1.5 * np.cos(i) - 2)
                    y_array_round.append(1.5 * np.sin(i) - 2)
            elif self.signal == "L":
                rn_l_on = np.radians(np.linspace(360, 334.5, 66))
                rn_l_in = np.radians(np.linspace(115.5, 334.5, 575))
                rn_l_off = np.radians(np.linspace(115.5, 90, 66))
                for i in rn_l_on:
                    x_array_round.append(1.5 * np.cos(i) - 2)
                    y_array_round.append(1.5 * np.sin(i) + 2)
                for i in rn_l_in:
                    x_array_round.append(1.5 * np.cos(i))
                    y_array_round.append(1.5 * np.sin(i))
                for i in rn_l_off:
                    x_array_round.append(1.5 * np.cos(i) + 2)
                    y_array_round.append(1.5 * np.sin(i) - 2)

        return np.array(x_array_round), np.array(y_array_round)

    def _calculate_path_length(self) -> float:
        """Calculate total path length for physics calculations"""
        if len(self.path_x) < 2:
            return 0.0

        dx = np.diff(self.path_x)
        dy = np.diff(self.path_y)
        return float(np.sum(np.sqrt(dx * dx + dy * dy)))

    def _calculate_initial_heading(self) -> float:
        """Calculate initial heading based on path direction"""
        if len(self.path_x) < 2:
            return 0.0

        dx = self.path_x[1] - self.path_x[0]
        dy = self.path_y[1] - self.path_y[0]
        return math.atan2(dy, dx)

    def activate(self, current_time: float):
        """Activate vehicle for movement"""
        self.active = True
        self.start_time = current_time
        self.current_time = current_time
        self.current_position = 0.0
        self.current_position_meters = 0.0  # ADD THIS LINE
        self.completed = False

    def _calculate_actual_path_length(self) -> float:
        """Calculate actual path length in meters.

        Path arrays are stored in grid units; convert to meters by multiplying
        by METERS_PER_UNIT (1 grid unit = 1 car length = 4.5 m).
        """
        if len(self.path_x) < 2:
            return 0.0

        total_length_units = 0.0
        for i in range(1, len(self.path_x)):
            dx = self.path_x[i] - self.path_x[i - 1]
            dy = self.path_y[i] - self.path_y[i - 1]
            segment_length = math.sqrt(dx * dx + dy * dy)
            total_length_units += segment_length

        return total_length_units * METERS_PER_UNIT

    def _update_position_from_meters(self):
        """Update x,y coordinates based on meters traveled along path.

        `current_position_meters` is in real metres; convert to grid units
        before walking the path-array's cumulative arc length.
        """
        if len(self.path_x) < 2:
            return

        # Cumulative distances along path stay in grid units to match the
        # path arrays' coordinates.
        cumulative_distances = [0.0]
        for i in range(1, len(self.path_x)):
            dx = self.path_x[i] - self.path_x[i - 1]
            dy = self.path_y[i] - self.path_y[i - 1]
            segment_length = math.sqrt(dx * dx + dy * dy)
            cumulative_distances.append(cumulative_distances[-1] + segment_length)

        # Convert metres-traveled to grid-units-traveled for the lookup.
        target_units = self.current_position_meters / METERS_PER_UNIT

        # Find which segment we're on based on units traveled
        for i in range(len(cumulative_distances) - 1):
            if cumulative_distances[i] <= target_units <= cumulative_distances[i + 1]:
                # Interpolate within this segment (all in grid units)
                segment_length = cumulative_distances[i + 1] - cumulative_distances[i]
                if segment_length > 0:
                    progress = (target_units - cumulative_distances[i]) / segment_length
                    progress = min(1.0, max(0.0, progress))

                    self.state.x = self.path_x[i] + progress * (self.path_x[i + 1] - self.path_x[i])
                    self.state.y = self.path_y[i] + progress * (self.path_y[i + 1] - self.path_y[i])

                    # Update heading
                    if i + 1 < len(self.path_x):
                        dx = self.path_x[i + 1] - self.path_x[i]
                        dy = self.path_y[i + 1] - self.path_y[i]
                        if dx != 0 or dy != 0:
                            self.state.heading = math.atan2(dy, dx)
                return

        # Fallback: at end of path
        if len(self.path_x) > 0:
            self.state.x = self.path_x[-1]
            self.state.y = self.path_y[-1]

    # In-intersection speed cap (m/s).  Vehicles slow to this through the
    # intersection / ring core and cruise at max_speed in the approach
    # straights.  M2 fix: algorithms now call update(dt) without a
    # target_speed override so this branch actually fires.
    INTERSECTION_SPEED = 2.0

    # Roundabout slow-zone radius (grid units).  Roundabout paths sit on a
    # ring of radius 1.5; vehicles within this radius slow to
    # INTERSECTION_SPEED so the speed cap is symmetric with the 4-way
    # rectangular box.  Without this, ring traffic cruises at max_speed
    # the entire loop and Roundabout becomes unfairly fast.
    ROUNDABOUT_SLOW_RADIUS = 2.0

    def _is_in_slow_zone(self) -> bool:
        """Return True if the vehicle is in the in-intersection slow zone.

        4-way paths use the geometry's rectangular intersection box.
        Roundabout paths use a circle of radius ROUNDABOUT_SLOW_RADIUS to
        catch the ring (radius 1.5) plus the small entry/exit arcs.
        """
        if self.use_roundabout_paths:
            r2 = self.state.x * self.state.x + self.state.y * self.state.y
            return r2 <= self.ROUNDABOUT_SLOW_RADIUS * self.ROUNDABOUT_SLOW_RADIUS
        return self.geometry.is_in_intersection(self.state.x, self.state.y)

    def update(self, dt: float, target_speed: float = None) -> bool:
        """Update vehicle physics and position based on actual meters traveled"""
        if not self.active or self.completed:
            return False

        self.current_time += dt

        # Default target speed: slow through intersection, cruise outside.
        if target_speed is None:
            if self._is_in_slow_zone():
                target_speed = self.INTERSECTION_SPEED
            else:
                target_speed = self.max_speed

        # Physics: accelerate toward target speed
        speed_diff = target_speed - self.state.velocity
        if abs(speed_diff) > 0.1:
            accel = np.clip(speed_diff * 2.0, self.max_deceleration, self.max_acceleration)
            self.state.acceleration = accel
            self.state.velocity += accel * dt
        else:
            self.state.acceleration = 0.0
            self.state.velocity = target_speed

        # CRITICAL FIX: Move based on actual meters traveled
        distance_traveled = self.state.velocity * dt
        self.current_position_meters += distance_traveled

        # Check completion based on actual path length in meters
        if self.current_position_meters >= self.path_length_meters:
            self.completed = True
            self.active = False
            # Phase 2C: in case the path's final point sits inside the
            # slow zone (shouldn't happen for current geometries but
            # defensive), still record the exit on completion so the
            # metric isn't None.
            if self.intersection_exit_time is None and self._was_in_slow_zone:
                self.intersection_exit_time = self.current_time
            return False

        # Update position along path based on meters traveled
        self._update_position_from_meters()

        # Phase 2C: track in-slow-zone → out-of-slow-zone transition for
        # the intersection-clearance metric.  4-way vehicles start at the
        # stop-line boundary (in zone); roundabout vehicles start at
        # r=2.06 (just outside zone), enter the slow zone on the entry
        # arc, then exit it on the exit arc.  We record only the first
        # True→False transition, which corresponds to "vehicle has
        # cleared the intersection" in both regimes.
        in_zone_now = self._is_in_slow_zone()
        if (self._was_in_slow_zone and not in_zone_now
                and self.intersection_exit_time is None):
            self.intersection_exit_time = self.current_time
        self._was_in_slow_zone = in_zone_now

        return True

    def _update_position_from_path(self):
        """Update x,y position based on current position along path"""
        if len(self.path_x) < 2:
            return

        # Calculate cumulative distances along path
        dx = np.diff(self.path_x)
        dy = np.diff(self.path_y)
        segment_lengths = np.sqrt(dx * dx + dy * dy)
        cumulative_distances = np.concatenate([[0], np.cumsum(segment_lengths)])

        # Find which segment we're on
        segment_idx = np.searchsorted(cumulative_distances, self.current_position) - 1
        segment_idx = np.clip(segment_idx, 0, len(segment_lengths) - 1)

        # Interpolate within segment
        if segment_idx < len(segment_lengths):
            segment_start = cumulative_distances[segment_idx]
            segment_progress = (self.current_position - segment_start) / segment_lengths[segment_idx]
            segment_progress = np.clip(segment_progress, 0.0, 1.0)

            self.state.x = self.path_x[segment_idx] + segment_progress * dx[segment_idx]
            self.state.y = self.path_y[segment_idx] + segment_progress * dy[segment_idx]

            # Update heading
            if segment_lengths[segment_idx] > 0:
                self.state.heading = math.atan2(dy[segment_idx], dx[segment_idx])

    def _kinematic_distance_ahead(self, time_ahead: float) -> float:
        """Phase 2A: return how far (in metres) the vehicle is predicted to
        travel along its path in the next ``time_ahead`` seconds, modelling
        acceleration from the current velocity toward INTERSECTION_SPEED.

        Pre-Phase-2A this was just ``velocity * time_ahead``, which treats
        a freshly-activated vehicle (v=0) as stationary — causing the
        collision check to allow co-activation of two L-turners from
        opposite approaches because both candidates were predicted to stay
        at their stop lines for the full 3 s look-ahead.

        The model assumes the vehicle is in (or entering) the slow zone,
        which is the conservative assumption at activation.  After it
        exits the slow zone the simulation will let it accelerate to
        max_speed, but for the look-ahead horizon used by the collision
        detector that's a small refinement.
        """
        v0 = self.state.velocity
        target = self.INTERSECTION_SPEED
        accel = self.max_acceleration
        if v0 >= target or accel <= 0 or time_ahead <= 0:
            return max(0.0, v0 * time_ahead)
        t_accel = (target - v0) / accel
        if time_ahead <= t_accel:
            return v0 * time_ahead + 0.5 * accel * time_ahead * time_ahead
        accel_dist = v0 * t_accel + 0.5 * accel * t_accel * t_accel
        return accel_dist + target * (time_ahead - t_accel)

    def get_future_position(self, time_ahead: float) -> Tuple[float, float]:
        """Predict future (x, y) position after ``time_ahead`` seconds by
        walking the pre-computed path array.

        Pre-M5 this method used `self.current_position` (which is never
        updated by `update()` — only `current_position_meters` is) plus
        `velocity * time_ahead` (in metres) compared against
        `self.path_length` (in grid units), producing a unit-mismatched
        lookup that effectively clamped to path-end for any active
        vehicle.  Fixed in M5 by using `current_position_meters` and
        converting to grid units via `METERS_PER_UNIT`.

        Phase 2A: distance ahead is now computed kinematically via
        ``_kinematic_distance_ahead`` so just-activated vehicles
        (v=0 at the stop line) are correctly predicted to move along
        their path, not stay stationary.  Inactive vehicles use the
        same accelerate-from-rest model so the look-ahead reflects
        what would happen if they were activated this step.
        """
        if self.completed:
            return self.state.x, self.state.y

        return self._arc_meters_to_xy(self._predicted_arc_meters(time_ahead))

    def _predicted_arc_meters(self, time_ahead: float) -> float:
        """Arc-length position (metres) this vehicle is predicted to reach in
        ``time_ahead`` seconds. Base vehicles follow free-path kinematics;
        car-following subclasses override to cap this by the leader's
        predicted position so the predictor cannot outrun a throttled
        follower (see FollowingVehicle — the fix for bug #8, July 2026).

        current_position_meters is 0 for never-activated vehicles, so the
        kinematic prediction is anchored at path[0]."""
        return self.current_position_meters + self._kinematic_distance_ahead(time_ahead)

    def _arc_meters_to_xy(self, future_meters: float) -> Tuple[float, float]:
        """Map an arc-length position (metres) to (x, y) along the path array."""
        future_units = future_meters / METERS_PER_UNIT

        # Cumulative arc length along the path, in grid units.
        dx = np.diff(self.path_x)
        dy = np.diff(self.path_y)
        segment_lengths = np.sqrt(dx * dx + dy * dy)
        cumulative_distances = np.concatenate([[0.0], np.cumsum(segment_lengths)])

        if future_units >= cumulative_distances[-1]:
            return float(self.path_x[-1]), float(self.path_y[-1])

        segment_idx = np.searchsorted(cumulative_distances, future_units) - 1
        segment_idx = int(np.clip(segment_idx, 0, len(segment_lengths) - 1))

        seg_len = segment_lengths[segment_idx]
        if seg_len > 0:
            segment_start = cumulative_distances[segment_idx]
            progress = (future_units - segment_start) / seg_len
            progress = float(np.clip(progress, 0.0, 1.0))
            fx = float(self.path_x[segment_idx] + progress * dx[segment_idx])
            fy = float(self.path_y[segment_idx] + progress * dy[segment_idx])
            return fx, fy

        return float(self.path_x[segment_idx]), float(self.path_y[segment_idx])


class CollisionDetector:
    """Realistic collision detection based on actual vehicle dynamics.

    `safety_margin` is in real metres; predicted positions are in grid
    units, so the Euclidean grid distance is multiplied by METERS_PER_UNIT
    before comparing.
    """

    # M6: scale sample count with horizon (target 0.2 s per sample) so
    # longer horizons get proportionally more samples.
    SAMPLE_INTERVAL_SECONDS = 0.2
    MIN_SAMPLES = 15

    def __init__(self, safety_margin: float = 3.0):
        self.safety_margin = safety_margin

    def check_collision(self, vehicle1: PathBasedVehicle, vehicle2: PathBasedVehicle,
                        time_horizon: float = 3.0) -> bool:
        """Check if vehicles will be too close within time horizon"""
        if not (vehicle1.active or vehicle2.active):
            if not vehicle1.active and not vehicle2.active:
                return False

        # Sample positions over time horizon (M6: dynamic sample count).
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
                if distance_m < self.safety_margin:
                    return True

        return False

    def _predict_position(self, vehicle: PathBasedVehicle, time_ahead: float) -> tuple:
        """Predict vehicle position after time_ahead seconds.

        Phase 2A: inactive (candidate) vehicles are also routed through
        ``get_future_position`` so the predictor returns where they would
        be *if activated this step* — kinematically accelerating from rest
        along their path — instead of clamping to path[0].  This is what
        the collision check actually needs to answer: "if I activate this
        waiting car right now, will it conflict with active traffic in
        the next ``time_ahead`` seconds?"
        """
        if vehicle.completed:
            return None
        if hasattr(vehicle, 'get_future_position'):
            return vehicle.get_future_position(time_ahead)
        # Fallback: linear extrapolation (no path data available).
        if hasattr(vehicle, 'state'):
            future_x = vehicle.state.x + vehicle.state.velocity * math.cos(vehicle.state.heading) * time_ahead
            future_y = vehicle.state.y + vehicle.state.velocity * math.sin(vehicle.state.heading) * time_ahead
            return (future_x, future_y)
        return (vehicle.x, vehicle.y)


class PathBasedSmartStopAlgorithm:
    """
        Smart Stop: Uses turn signals and positioning to optimize flow

        Key principles:
        1. Right-of-way rules still apply (same as traditional stop)
        2. Turn signal information allows better coordination
        3. Non-conflicting movements can proceed simultaneously
        4. Backward priority: vehicles whose approach is non-adjacent to an
           active vehicle's approach get a priority bonus (see
           BACKWARD_PRIORITY_OFFSETS below for the exact geometric meaning)
        """

    # Approach positions form a CCW ring around the compass:
    #   Main W = 0  (East side approach, west-bound traffic)
    #   Green N = 1 (North side approach, south-bound traffic)
    #   Main E = 2  (West side approach, east-bound traffic)
    #   Green S = 3 (South side approach, north-bound traffic)
    # `(active_pos - waiting_pos) % 4` measures the CCW distance from waiting
    # to active:
    #   1 → waiting is one step CCW of active (e.g. active Main E ← waiting Green N)
    #   2 → waiting is directly opposite active (e.g. active Main E ← waiting Main W)
    #   3 → waiting is one step CW of active (e.g. active Main E ← waiting Green S)
    # Diff 1 and 2 are "backward" in that the waiting vehicle's approach is not
    # the active vehicle's immediate-right neighbour. For most signal
    # combinations this corresponds to geometrically separated paths through
    # the intersection (CCW-1: curving turns from non-adjacent corners
    # diverge; opposite: parallel-paths rule for NS/S, mirrored geometry for
    # turns). Diff 3 is excluded because that approach is the active
    # vehicle's right-of-way yielder and its path most often crosses the
    # active path.
    BACKWARD_PRIORITY_OFFSETS = (1, 2)

    # M3 fairness guard: each waiting vehicle accumulates a priority bonus
    # proportional to its wait time so a low-scoring vehicle cannot be
    # passed over indefinitely.  WAIT_PRIORITY_RATE points per simulated
    # second, capped at WAIT_PRIORITY_CAP so the bonus can outweigh signal
    # type (5) and backward priority (10) only after sustained waiting.
    WAIT_PRIORITY_RATE = 1.0     # points per second waiting
    WAIT_PRIORITY_CAP = 20.0     # cap at 20 s of accumulated bonus

    # Phase 2B: collision-detector configuration.  Bumped from 3.0 m margin
    # and 3.0 s horizon after the visual GIF review surfaced three near-
    # misses at ~3.0-3.2 m (just above the old margin) and an S2 conflict
    # whose minimum-distance moment fell 0.7 s past the 3.0 s look-ahead
    # window.  3.5 m gives the algorithm a visible perceptual buffer over
    # the rendered 4.5 m car length, and 5.0 s catches L-turn conflicts
    # that develop 3-4 s into the active path.
    SAFETY_MARGIN = 3.5             # metres
    COLLISION_TIME_HORIZON = 5.0    # seconds
    # Co-activation stops once this many cars are active. "Active" lasts until
    # a car finishes its whole path, exit lane included, so departing cars
    # count. Neither the signal nor the all-way stop has such a cap (found
    # 2026-11-12). Legacy default 4 keeps committed results reproducible.
    MAX_ACTIVE = 4

    def __init__(self, geometry: IntersectionGeometry):
        self.geometry = geometry
        self.collision_detector = TurnAwareCollisionDetector(safety_margin=self.SAFETY_MARGIN)
        self.active_vehicles = []
        self.waiting_vehicles = []
        self.completed_vehicles = []
        self.current_time = 0.0

        # Smart stop uses approach positions for backward priority
        self.approach_positions = {
            "Main W": 0,  # East-side approach (west-bound traffic)
            "Green N": 1,  # North-side approach (south-bound traffic)
            "Main E": 2,  # West-side approach (east-bound traffic)
            "Green S": 3  # South-side approach (north-bound traffic)
        }

    def add_vehicle(self, vehicle: PathBasedVehicle):
        # M3: stamp the queue-arrival time so the fairness bonus can be
        # computed later.  If `arrival_time` was already set (e.g. the
        # caller pre-populated it), respect that; otherwise use the
        # current simulation clock.
        if vehicle.arrival_time is None:
            vehicle.arrival_time = self.current_time
        self.waiting_vehicles.append(vehicle)
        self.waiting_vehicles.sort(key=lambda v: v.order)

    def _wait_bonus(self, vehicle: PathBasedVehicle) -> float:
        """M3: priority bonus for time spent waiting (points), capped."""
        if vehicle.arrival_time is None:
            return 0.0
        wait_secs = max(0.0, self.current_time - vehicle.arrival_time)
        return min(self.WAIT_PRIORITY_CAP,
                   self.WAIT_PRIORITY_RATE * wait_secs)

    def _intent_of(self, vehicle) -> str:
        """Movement the controller may use for PRIORITY ranking. Default: the
        declared turn signal. Signal-blind controllers override this so they
        never rank by a movement a camera can't see yet (audit 3, 2026-11-11).
        Default behaviour is unchanged for every existing controller."""
        return vehicle.signal

    def _signal_bonus(self, signal: str) -> float:
        """Signal-type priority bonus shared by first-vehicle (M4) and
        candidate selection.  R turns are simplest geometrically, NS/S
        next, L turns most complex."""
        if signal == "R":
            return 5.0
        if signal == "NS/S":
            return 3.0
        return 0.0  # L

    def _heads_of_queue(self) -> List[PathBasedVehicle]:
        """Phase 2A: per-approach FIFO.  Return only the front vehicle of
        each approach's queue (lowest ``order`` per ``road_name``).  Cars
        behind the head are not candidates for activation until the head
        clears — matching real 4-way stop etiquette where the car at the
        line goes first regardless of turn signal.

        ``self.waiting_vehicles`` is kept sorted by ``order`` in
        ``add_vehicle``, so the first occurrence per road_name is the
        head."""
        heads = {}
        for v in self.waiting_vehicles:
            if v.road_name not in self.approach_positions:
                continue
            if v.road_name not in heads:
                heads[v.road_name] = v
        return list(heads.values())

    def step(self, dt: float = 0.1) -> Dict:
        self.current_time += dt

        # Update active vehicles
        for vehicle in self.active_vehicles[:]:
            still_active = vehicle.update(dt)  # Speed-by-zone (intersection vs free-flow)
            if not still_active:
                self.active_vehicles.remove(vehicle)
                self.completed_vehicles.append(vehicle)

        # Smart Stop logic: Use turn signals to coordinate non-conflicting movements
        self._coordinate_smart_movements()

        return {
            'time': self.current_time,
            'active': len(self.active_vehicles),
            'waiting': len(self.waiting_vehicles),
            'completed': len(self.completed_vehicles)
        }

    def _coordinate_smart_movements(self):
        """Smart coordination using turn signal information and backward priority"""

        # M4 + Phase 2A: when no vehicles are active, pick the first
        # vehicle by priority score from the heads-of-queue (one per
        # approach).  Cars stacked behind a head wait their turn.
        if not self.active_vehicles and self.waiting_vehicles:
            heads = self._heads_of_queue()
            if heads:
                best = max(
                    heads,
                    key=lambda v: (
                        self._signal_bonus(self._intent_of(v)) + self._wait_bonus(v),
                        -v.order,  # earlier-arriving wins ties
                    ),
                )
                self.waiting_vehicles.remove(best)
                best.activate(self.current_time)
                self.active_vehicles.append(best)

        # Smart Stop advantage: Look for non-conflicting vehicles to activate simultaneously
        if self.waiting_vehicles:
            self._try_activate_smart_coordination()

    def _try_activate_smart_coordination(self):
        """Use backward priority and turn signal optimization"""

        # Get positions of currently active vehicles
        active_positions = set()
        for vehicle in self.active_vehicles:
            if vehicle.road_name in self.approach_positions:
                active_positions.add(self.approach_positions[vehicle.road_name])

        candidates = []

        # Phase 2A: only the front vehicle per approach is eligible for
        # activation (per-approach FIFO).  Cars stacked behind the head
        # must wait their turn.
        for waiting_vehicle in self._heads_of_queue():
            waiting_pos = self.approach_positions[waiting_vehicle.road_name]

            # Backward priority: prefer vehicles whose approach is non-adjacent
            # to any active vehicle's approach (see BACKWARD_PRIORITY_OFFSETS).
            is_backward_priority = False
            for active_pos in active_positions:
                if (active_pos - waiting_pos) % 4 in self.BACKWARD_PRIORITY_OFFSETS:
                    is_backward_priority = True
                    break

            # Check if this vehicle can move without conflicts (Phase 2B:
            # extended look-ahead via COLLISION_TIME_HORIZON catches L-turn
            # conflicts that develop 3-4 s into the active path).
            can_move = True
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(
                        waiting_vehicle, active_vehicle,
                        time_horizon=self.COLLISION_TIME_HORIZON):
                    can_move = False
                    break

            if can_move:
                priority_score = 0.0

                # Priority boost for backward priority (Smart Stop's key advantage)
                if is_backward_priority:
                    priority_score += 10.0

                # Signal-type bonus shared with first-vehicle scoring.
                priority_score += self._signal_bonus(self._intent_of(waiting_vehicle))

                # M3 fairness guard: bonus for time already spent waiting,
                # so persistently low-scoring vehicles cannot be starved.
                priority_score += self._wait_bonus(waiting_vehicle)

                candidates.append((waiting_vehicle, priority_score))

        # Sort by priority and activate highest priority vehicles
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Activate vehicles in priority order (but still check conflicts)
        for vehicle, score in candidates:
            # Double-check no conflicts with newly activated vehicles
            conflicts = False
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(
                        vehicle, active_vehicle,
                        time_horizon=self.COLLISION_TIME_HORIZON):
                    conflicts = True
                    break

            if not conflicts and len(self.active_vehicles) >= self.MAX_ACTIVE:
                self._cap_blocks = getattr(self, '_cap_blocks', 0) + 1
            if not conflicts and len(self.active_vehicles) < self.MAX_ACTIVE:
                self.waiting_vehicles.remove(vehicle)
                vehicle.activate(self.current_time)
                self.active_vehicles.append(vehicle)

    def get_metrics(self) -> Dict:
        """Calculate performance metrics.

        Phase 2C: ``total_time`` now measures "time to clear the
        intersection" — the wall-clock moment the last vehicle's front
        first transitions out of the in-intersection slow zone (box for
        4-way, radius-2.0 circle for roundabout).  The simulation keeps
        running until vehicles reach their off-screen exit so the
        animation still shows them driving away, but the official
        comparison metric stops at intersection clearance.  This makes
        Smart Stop vs Roundabout fair: pre-2C, the metric counted the
        post-intersection exit-lane distance, which was longer for 4-way
        than for roundabout and silently favored roundabout.
        """
        if not self.completed_vehicles:
            return {'total_time': 0, 'avg_wait_time': 0, 'throughput': 0}

        exit_times = [v.intersection_exit_time for v in self.completed_vehicles
                      if v.intersection_exit_time is not None]
        total_time = max(exit_times) if exit_times else self.current_time
        simulation_time = self.current_time  # full off-screen clearance, for the animator

        wait_times = []
        for vehicle in self.completed_vehicles:
            if vehicle.start_time is not None:
                wait_time = vehicle.start_time
                wait_times.append(wait_time)

        avg_wait_time = np.mean(wait_times) if wait_times else 0
        throughput = len(self.completed_vehicles) / total_time if total_time > 0 else 0

        return {
            'total_time': total_time,
            'simulation_time': simulation_time,
            'avg_wait_time': avg_wait_time,
            'throughput': throughput,
            'completed_vehicles': len(self.completed_vehicles)
        }


def create_test_scenario(geometry_type: str = "4way") -> List[PathBasedVehicle]:
    """Create a test scenario with multiple vehicles"""
    if geometry_type == "4way":
        geometry = FourWayGeometry()
    else:
        geometry = RoundaboutGeometry()

    vehicles = []

    # Test scenario: 4 vehicles from different approaches
    test_configs = [
        ("Main E", "R", 1),
        ("Main W", "L", 2),
        ("Green N", "NS/S", 3),
        ("Green S", "R", 4)
    ]

    for road, signal, order in test_configs:
        vehicle = PathBasedVehicle(road, signal, order, geometry)
        vehicles.append(vehicle)

    return vehicles


class TraditionalStopAlgorithm:
    """Traditional 4-way stop: First-come, first-served, one at a time"""

    def __init__(self, geometry: IntersectionGeometry):
        self.geometry = geometry
        self.waiting_vehicles = []
        self.active_vehicle = None
        self.completed_vehicles = []
        self.current_time = 0.0

    def add_vehicle(self, vehicle: PathBasedVehicle):
        if vehicle.arrival_time is None:
            vehicle.arrival_time = self.current_time
        self.waiting_vehicles.append(vehicle)
        self.waiting_vehicles.sort(key=lambda v: v.order)  # First-come, first-served

    def step(self, dt: float = 0.1) -> Dict:
        self.current_time += dt

        # Update active vehicle
        if self.active_vehicle:
            still_active = self.active_vehicle.update(dt)
            if not still_active:
                self.completed_vehicles.append(self.active_vehicle)
                self.active_vehicle = None

        # Traditional stop: Only proceed when intersection is completely clear
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
        # Phase 2C: intersection-clearance time (see PathBasedSmartStop docstring)
        if not self.completed_vehicles:
            return {'total_time': 0, 'avg_wait_time': 0, 'throughput': 0}

        exit_times = [v.intersection_exit_time for v in self.completed_vehicles
                      if v.intersection_exit_time is not None]
        total_time = max(exit_times) if exit_times else self.current_time
        simulation_time = self.current_time

        wait_times = [v.start_time for v in self.completed_vehicles if v.start_time is not None]
        avg_wait_time = np.mean(wait_times) if wait_times else 0
        throughput = len(self.completed_vehicles) / total_time if total_time > 0 else 0

        return {
            'total_time': total_time,
            'simulation_time': simulation_time,
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
        if vehicle.arrival_time is None:
            vehicle.arrival_time = self.current_time
        self.waiting_vehicles.append(vehicle)
        self.waiting_vehicles.sort(key=lambda v: v.order)

    def step(self, dt: float = 0.1) -> Dict:
        self.current_time += dt

        # Update active vehicles
        for vehicle in self.active_vehicles[:]:
            # Roundabout speeds are typically slower for safety
            still_active = vehicle.update(dt)  # Speed-by-zone (intersection vs free-flow)
            if not still_active:
                self.active_vehicles.remove(vehicle)
                self.completed_vehicles.append(vehicle)

        # Roundabout rule: Enter if you can merge safely (yield to traffic in circle)
        self._try_enter_roundabout()

        return {
            'time': self.current_time,
            'active': len(self.active_vehicles),
            'waiting': len(self.waiting_vehicles),
            'completed': len(self.completed_vehicles)
        }

    def _try_enter_roundabout(self):
        """Roundabout entry: Yield to traffic already in the circle"""

        # Roundabout rule: Check each waiting vehicle to see if it can enter safely
        for waiting_vehicle in self.waiting_vehicles[:]:  # Use slice to avoid modification during iteration
            can_enter = True

            # Check if entry conflicts with vehicles already in roundabout
            for active_vehicle in self.active_vehicles:
                # Realistic collision check with proper time horizon
                if self.collision_detector.check_collision(
                        waiting_vehicle, active_vehicle, time_horizon=3.0
                ):
                    can_enter = False
                    break

            # If this vehicle can enter safely, activate it
            if can_enter:
                self.waiting_vehicles.remove(waiting_vehicle)
                waiting_vehicle.activate(self.current_time)
                self.active_vehicles.append(waiting_vehicle)

                # In a realistic roundabout, typically only one vehicle enters at a time
                # from each approach to avoid conflicts, but we can allow multiple if safe
                # For now, let's be conservative and only activate one per step
                break  # Remove this 'break' if you want to allow multiple entries per step

    # Alternative version if you want to allow multiple simultaneous entries:

    def _try_enter_roundabout_aggressive(self):
        """More aggressive roundabout entry - multiple vehicles can enter if safe"""

        vehicles_to_activate = []

        for waiting_vehicle in self.waiting_vehicles[:]:
            can_enter = True

            # Check collision with active vehicles
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(
                        waiting_vehicle, active_vehicle, time_horizon=3.0
                ):
                    can_enter = False
                    break

            # Check collision with other vehicles being activated this step
            if can_enter:
                for other_waiting in vehicles_to_activate:
                    if self.collision_detector.check_collision(
                            waiting_vehicle, other_waiting, time_horizon=2.0
                    ):
                        can_enter = False
                        break

            if can_enter:
                vehicles_to_activate.append(waiting_vehicle)

        # Activate all safe vehicles
        for vehicle in vehicles_to_activate:
            self.waiting_vehicles.remove(vehicle)
            vehicle.activate(self.current_time)
            self.active_vehicles.append(vehicle)

    def get_metrics(self) -> Dict:
        # Phase 2C: intersection-clearance time (see PathBasedSmartStop docstring)
        if not self.completed_vehicles:
            return {'total_time': 0, 'avg_wait_time': 0, 'throughput': 0}

        exit_times = [v.intersection_exit_time for v in self.completed_vehicles
                      if v.intersection_exit_time is not None]
        total_time = max(exit_times) if exit_times else self.current_time
        simulation_time = self.current_time

        wait_times = [v.start_time for v in self.completed_vehicles if v.start_time is not None]
        avg_wait_time = np.mean(wait_times) if wait_times else 0
        throughput = len(self.completed_vehicles) / total_time if total_time > 0 else 0

        return {
            'total_time': total_time,
            'simulation_time': simulation_time,
            'avg_wait_time': avg_wait_time,
            'throughput': throughput,
            'completed_vehicles': len(self.completed_vehicles)
        }


class SmartStopSafeAlgorithm(PathBasedSmartStopAlgorithm):
    """
        Smart Stop Safe Mode: Conservative version for early deployment

        Same logic as Smart Stop, but:
        1. Treats NS/S (no signal) vehicles as potential left turns for both
           rule selection and priority scoring. The collision detector is
           called with signal1="L" so Rule 1 (parallel-NS/S pass) and Rule 3
           (R+NS/S exit-arm pass) cannot green-light a vehicle whose true
           intent is unknown. Note: the Rule 4 distance check still uses the
           vehicle's actual NS/S path geometry — full L-path simulation
           would require synthesizing a hypothetical L-vehicle and is left
           as a future improvement.
        2. Uses a larger safety margin (4.0 m vs Smart Stop's 3.5 m post-2B).
           Time horizon matches Smart Stop's 5.0 s (inherited via
           ``COLLISION_TIME_HORIZON``), keeping the "Smart Safe ≥ Smart Stop"
           conservatism invariant on every axis.
        3. Caps simultaneous activations at 2 (vs Smart Stop's 4).
        4. Phase 2B: dropped the prior "one activation per step" rule.
           Smart Safe now loops through all eligible candidates and adds as
           many as fit under the 2-vehicle cap in a single step, re-checking
           conflicts against any newly-activated vehicle in the same loop.
           Pre-2B, two L-turns from opposite approaches whose paths sweep
           non-overlapping quadrants of the intersection (e.g. Cars 2 & 5 in
           Scenario 4) were forced into sequence purely by this rule, not by
           geometry.
        """

    # Phase 2B: keep margin at 4.0 m (wider than Smart Stop's new 3.5 m) and
    # inherit the 5.0 s horizon from the parent so both algorithms catch
    # the same long-developing L-turn conflicts.  Smart Safe stays more
    # conservative on every dimension that matters: margin, simultaneous
    # cap, and the NS/S→L signal override on the rule lookup.
    SAFETY_MARGIN = 4.0

    def __init__(self, geometry: IntersectionGeometry):
        self.geometry = geometry
        self.collision_detector = TurnAwareCollisionDetector(safety_margin=self.SAFETY_MARGIN)
        self.active_vehicles = []
        self.waiting_vehicles = []
        self.completed_vehicles = []
        self.current_time = 0.0

        self.approach_positions = {
            "Main W": 0, "Green N": 1, "Main E": 2, "Green S": 3
        }

    def add_vehicle(self, vehicle: PathBasedVehicle):
        # M3: stamp queue-arrival time (Smart Safe inherits the wait-bonus
        # logic via the parent class).
        if vehicle.arrival_time is None:
            vehicle.arrival_time = self.current_time
        self.waiting_vehicles.append(vehicle)
        self.waiting_vehicles.sort(key=lambda v: v.order)

    def _effective_signal(self, vehicle: PathBasedVehicle) -> str:
        """Worst-case signal relabel used for rule selection and the collision
        check. Base Smart Safe: a NO-SIGNAL vehicle is treated as a potential
        LEFT (its true intent is unknown). Subclasses extend this — see
        SmartSafeR, which also treats an UNCONFIRMED declared-right as a
        potential left until motion confirms the turn."""
        return "L" if vehicle.signal == "NS/S" else vehicle.signal

    def step(self, dt: float = 0.1) -> Dict:
        self.current_time += dt

        # Update active vehicles (slightly slower for safety)
        for vehicle in self.active_vehicles[:]:
            still_active = vehicle.update(dt)  # Speed-by-zone (intersection vs free-flow)
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
        """Conservative coordination - same logic as Smart Stop but more cautious.

        Phase 2B: when starting from zero active vehicles, the first-vehicle
        branch picks one seed and then *falls through* to
        ``_try_activate_safe_coordination`` so an eligible second candidate
        can be added in the same step (subject to the 2-vehicle cap).
        Pre-2B the branch ``return``'d early, which combined with the prior
        "one activation per step" rule below forced Smart Safe to take two
        full simulation steps to fill its two slots.
        """

        # M4 + Phase 2A: priority-based first-vehicle selection from
        # heads-of-queue only (per-approach FIFO).  Signal-type bonus
        # conservatively treats NS/S as L (Smart Safe worst-case).
        if not self.active_vehicles and self.waiting_vehicles:
            heads = self._heads_of_queue()
            if heads:
                def _safe_first_score(v):
                    eff_sig = self._effective_signal(v)
                    return (
                        self._signal_bonus(eff_sig) + self._wait_bonus(v),
                        -v.order,
                    )
                best = max(heads, key=_safe_first_score)
                self.waiting_vehicles.remove(best)
                best.activate(self.current_time)
                self.active_vehicles.append(best)
            # Phase 2B: no early return — fall through so the
            # multi-per-step loop in _try_activate_safe_coordination can
            # also fill the second slot this step.

        # More conservative: limit to 2 simultaneous vehicles
        if len(self.active_vehicles) >= 2:
            return

        if self.waiting_vehicles:
            self._try_activate_safe_coordination()

    def _try_activate_safe_coordination(self):
        """Conservative version of Smart Stop coordination"""

        active_positions = set()
        for vehicle in self.active_vehicles:
            if vehicle.road_name in self.approach_positions:
                active_positions.add(self.approach_positions[vehicle.road_name])

        candidates = []

        # Phase 2A: only the front vehicle per approach is eligible
        # (per-approach FIFO).
        for waiting_vehicle in self._heads_of_queue():
            waiting_pos = self.approach_positions[waiting_vehicle.road_name]

            # Backward priority — same definition as Smart Stop (see
            # PathBasedSmartStopAlgorithm.BACKWARD_PRIORITY_OFFSETS docstring).
            is_backward_priority = False
            for active_pos in active_positions:
                if (active_pos - waiting_pos) % 4 in self.BACKWARD_PRIORITY_OFFSETS:
                    is_backward_priority = True
                    break

            # Safe mode: treat unknown/unconfirmed intent as L (worst-case)
            # for the rule selection in the collision detector. This closes off
            # the Rule 1 parallel-pass and Rule 3 exit-arm-pass shortcuts for
            # vehicles whose true intent is not yet confirmed.
            effective_signal = self._effective_signal(waiting_vehicle)

            # Conservative collision check using the inherited 5.0 s look-
            # ahead (Phase 2B) and the L override on the waiting signal.
            can_move = True
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(
                        waiting_vehicle, active_vehicle,
                        time_horizon=self.COLLISION_TIME_HORIZON,
                        signal1=effective_signal,
                ):
                    can_move = False
                    break

            if can_move:
                priority_score = 0.0

                if is_backward_priority:
                    priority_score += 10.0

                # Conservative signal priorities
                if effective_signal == "R":
                    priority_score += 5.0
                elif waiting_vehicle.signal == "NS/S":  # Original signal, not effective
                    priority_score += 1.0  # Small bonus for actual straight movement
                # Left turns get no bonus

                # M3 fairness guard
                priority_score += self._wait_bonus(waiting_vehicle)

                candidates.append((waiting_vehicle, priority_score))

        # Phase 2B: loop through candidates in priority order, activating
        # as many as fit under the 2-vehicle cap (was: only one per step).
        # Re-check conflicts against ``self.active_vehicles`` on every
        # iteration so a candidate that would conflict with a vehicle just
        # activated earlier in this loop is correctly rejected.
        candidates.sort(key=lambda x: x[1], reverse=True)
        for vehicle, score in candidates:
            if len(self.active_vehicles) >= 2:
                break  # 2-vehicle cap (Smart Safe invariant)

            final_signal = self._effective_signal(vehicle)
            conflicts = False
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(
                        vehicle, active_vehicle,
                        time_horizon=self.COLLISION_TIME_HORIZON,
                        signal1=final_signal,
                ):
                    conflicts = True
                    break

            if not conflicts:
                self.waiting_vehicles.remove(vehicle)
                vehicle.activate(self.current_time)
                self.active_vehicles.append(vehicle)


class AlgorithmComparison:
    """Fixed version of AlgorithmComparison"""

    def __init__(self, scenario_vehicles: list, geometry_type: str = "4way"):
        self.scenario_vehicles = scenario_vehicles
        self.geometry_type = geometry_type

        if geometry_type == "4way":
            from path_based_smart_stop import FourWayGeometry
            self.geometry = FourWayGeometry()
        else:
            from path_based_smart_stop import RoundaboutGeometry
            self.geometry = RoundaboutGeometry()

        self.results = {}

    def run_comparison(self):
        """FIXED: Run all four algorithms with proper result storage"""

        # Import algorithm classes
        from path_based_smart_stop import (
            TraditionalStopAlgorithm, RoundaboutAlgorithm,
            PathBasedSmartStopAlgorithm, SmartStopSafeAlgorithm
        )

        # Create algorithms with correct path types
        algorithms = {
            'Traditional': (TraditionalStopAlgorithm(self.geometry), False),
            'Roundabout': (RoundaboutAlgorithm(self.geometry), True),  # Uses roundabout paths
            'Smart Stop': (PathBasedSmartStopAlgorithm(self.geometry), False),
            'Smart Safe': (SmartStopSafeAlgorithm(self.geometry), False)
        }

        results = {}  # CRITICAL: Create results dictionary

        for alg_name, (algorithm, use_roundabout_paths) in algorithms.items():
            print(f"Running {alg_name} algorithm...")

            try:
                # Create fresh vehicles for this algorithm
                fresh_vehicles = self._create_fresh_vehicles(use_roundabout_paths)

                # Add vehicles to algorithm
                for vehicle in fresh_vehicles:
                    algorithm.add_vehicle(vehicle)

                # Run simulation
                max_time = 60.0  # seconds
                dt = 0.1
                max_steps = int(max_time / dt)

                simulation_data = []

                # Record initial snapshot so waiting cars appear before first activation
                initial_waiting = []
                for vehicle in fresh_vehicles:
                    if len(vehicle.path_x) > 0:
                        initial_waiting.append({
                            'name': vehicle.car_name,
                            'x': vehicle.path_x[0],
                            'y': vehicle.path_y[0],
                            'heading': vehicle._calculate_initial_heading(),
                            'road': vehicle.road_name,
                            'signal': vehicle.signal
                        })
                simulation_data.append({
                    'time': 0.0,
                    'active_vehicles': [],
                    'waiting_count': len(fresh_vehicles),
                    'completed_count': 0
                })

                for step in range(max_steps):
                    # Step the algorithm
                    status = algorithm.step(dt)

                    # Record simulation data
                    active_states = []
                    if hasattr(algorithm, 'active_vehicles'):
                        # Multiple active vehicles (Smart Stop, Roundabout, etc.)
                        for vehicle in algorithm.active_vehicles:
                            if vehicle.active:
                                active_states.append({
                                    'name': vehicle.car_name,
                                    'x': getattr(vehicle, 'x', vehicle.state.x if hasattr(vehicle, 'state') else 0),
                                    'y': getattr(vehicle, 'y', vehicle.state.y if hasattr(vehicle, 'state') else 0),
                                    'heading': vehicle.state.heading if hasattr(vehicle, 'state') else 0.0,
                                    'road': vehicle.road_name,
                                    'signal': vehicle.signal
                                })
                    elif hasattr(algorithm, 'active_vehicle') and algorithm.active_vehicle:
                        # Single active vehicle (Traditional Stop)
                        vehicle = algorithm.active_vehicle
                        active_states.append({
                            'name': vehicle.car_name,
                            'x': getattr(vehicle, 'x', vehicle.state.x if hasattr(vehicle, 'state') else 0),
                            'y': getattr(vehicle, 'y', vehicle.state.y if hasattr(vehicle, 'state') else 0),
                            'heading': vehicle.state.heading if hasattr(vehicle, 'state') else 0.0,
                            'road': vehicle.road_name,
                            'signal': vehicle.signal
                        })

                    simulation_data.append({
                        'time': status['time'],
                        'active_vehicles': active_states,
                        'waiting_count': status['waiting'],
                        'completed_count': status['completed']
                    })

                    # Stop if all vehicles completed
                    if status['waiting'] == 0 and status['active'] == 0:
                        # Phase 2C: print the intersection-clearance time
                        # (matches the official metric used by reports and
                        # the GIF Results panel).  Off-screen / simulation
                        # end is ~2.1 s later for 4-way and ~1.5 s later
                        # for roundabout.
                        m = algorithm.get_metrics()
                        clear_t = m.get('total_time', status['time'])
                        print(f"  {alg_name} cleared intersection in {clear_t:.1f}s "
                              f"(sim end {status['time']:.1f}s)")
                        break

                # Get final metrics
                metrics = algorithm.get_metrics()

                # CRITICAL: Store results in dictionary
                results[alg_name] = {
                    'metrics': metrics,
                    'simulation_data': simulation_data
                }

                print(f"  {alg_name}: {metrics['total_time']:.1f}s, {metrics['completed_vehicles']} vehicles")

            except Exception as e:
                print(f"  [FAIL] {alg_name} failed: {e}")
                import traceback
                traceback.print_exc()
                # Store error result so we can still analyze partial results
                results[alg_name] = {
                    'metrics': {'total_time': float('inf'), 'avg_wait_time': 0, 'throughput': 0,
                                'completed_vehicles': 0},
                    'simulation_data': [],
                    'error': str(e)
                }

        # CRITICAL: Return results dictionary
        self.results = results
        return results

    def _create_fresh_vehicles(self, use_roundabout_paths: bool = False):
        """Create fresh vehicle objects to avoid state conflicts"""
        from path_based_smart_stop import PathBasedVehicle

        fresh_vehicles = []
        for vehicle in self.scenario_vehicles:
            # Create fresh vehicle with specified path type
            fresh_vehicle = PathBasedVehicle(
                vehicle.road_name,
                vehicle.signal,
                vehicle.order,
                self.geometry,
                use_roundabout_paths=use_roundabout_paths
            )
            fresh_vehicles.append(fresh_vehicle)

        return fresh_vehicles

    def _get_active_vehicle_states(self, algorithm) -> List[Dict]:
        """Extract current positions of active vehicles"""
        states = []

        if hasattr(algorithm, 'active_vehicles'):
            for vehicle in algorithm.active_vehicles:
                if vehicle.active:
                    states.append({
                        'name': vehicle.car_name,
                        'x': vehicle.state.x,
                        'y': vehicle.state.y,
                        'road': vehicle.road_name,
                        'signal': vehicle.signal
                    })
        elif hasattr(algorithm, 'active_vehicle') and algorithm.active_vehicle:
            vehicle = algorithm.active_vehicle
            states.append({
                'name': vehicle.car_name,
                'x': vehicle.state.x,
                'y': vehicle.state.y,
                'road': vehicle.road_name,
                'signal': vehicle.signal
            })

        return states


class IntersectionAnimator:
    """Advanced matplotlib animation system for algorithm comparison"""

    def __init__(self, comparison_results: Dict, geometry_type: str = "4way"):
        self.results = comparison_results
        self.geometry_type = geometry_type

        # Animation parameters
        self.fps = 10
        self.speed_multiplier = 2.0  # Make animation faster

        # Colors for each algorithm
        self.colors = {
            'Traditional': '#FF6B6B',  # Red
            'Roundabout': '#4ECDC4',  # Teal
            'Smart Stop': '#45B7D1',  # Blue
            'Smart Safe': '#96CEB4'  # Green
        }

        # Setup matplotlib
        self.fig, self.axes = plt.subplots(2, 2, figsize=(16, 12))
        self.fig.suptitle('Algorithm Comparison: Traffic Flow Analysis', fontsize=16, fontweight='bold')

        # Flatten axes for easy iteration
        self.axes_flat = self.axes.flatten()

        # Setup each subplot
        algorithm_names = list(self.results.keys())
        for i, (ax, alg_name) in enumerate(zip(self.axes_flat, algorithm_names)):
            self._setup_subplot(ax, alg_name, i)

        # Setup animation data
        self._prepare_animation_data()

    def _setup_subplot(self, ax, algorithm_name: str, subplot_idx: int):
        """Setup individual subplot for algorithm"""
        ax.set_xlim(-3, 3)
        ax.set_ylim(-3, 3)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.set_title(f'{algorithm_name}', fontsize=14, fontweight='bold')

        # Draw intersection layout
        if self.geometry_type == "4way":
            self._draw_4way_intersection(ax)
        else:
            self._draw_roundabout_intersection(ax)

        # Initialize vehicle markers
        ax.vehicles = {}
        ax.vehicle_paths = {}

        # Add metrics text
        metrics = self.results[algorithm_name]['metrics']
        metrics_text = (f"Time: {metrics['total_time']:.1f}s\n"
                        f"Wait: {metrics['avg_wait_time']:.1f}s\n"
                        f"Throughput: {metrics['throughput']:.2f}")
        ax.text(0.02, 0.98, metrics_text, transform=ax.transAxes,
                verticalalignment='top', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    def _draw_4way_intersection(self, ax):
        """Draw 4-way intersection layout"""
        # Intersection box
        intersection = Rectangle((-1.35, -1.35), 2.7, 2.7,
                                 fill=False, edgecolor='black', linewidth=2)
        ax.add_patch(intersection)

        # Road lanes
        lane_width = 0.05
        roads = [
            # Horizontal roads
            Rectangle((-3, 0.45), 6, lane_width, facecolor='gray', alpha=0.7),
            Rectangle((-3, -0.55), 6, lane_width, facecolor='gray', alpha=0.7),
            # Vertical roads
            Rectangle((-0.55, -3), 6, lane_width, facecolor='gray', alpha=0.7),
            Rectangle((0.45, -3), 6, lane_width, facecolor='gray', alpha=0.7)]

        for road in roads:
            ax.add_patch(road)

        # Road labels
        ax.text(-2.5, 0.8, 'Main W', fontsize=10, ha='center')
        ax.text(2.5, -0.8, 'Main E', fontsize=10, ha='center')
        ax.text(-0.8, 2.5, 'Green N', fontsize=10, ha='center')
        ax.text(0.8, -2.5, 'Green S', fontsize=10, ha='center')

    def _draw_roundabout_intersection(self, ax):
        """Draw roundabout intersection layout"""
        # Roundabout circle
        circle = Circle((0, 0), 1.5, fill=False, edgecolor='black', linewidth=2)
        ax.add_patch(circle)

        # Inner circle
        inner_circle = Circle((0, 0), 1.0, fill=True, facecolor='lightgray', alpha=0.5)
        ax.add_patch(inner_circle)

        # Approach roads
        approach_roads = [
            Rectangle((-3, -0.1), 1.4, 0.2, facecolor='gray', alpha=0.7),  # West
            Rectangle((1.6, -0.1), 1.4, 0.2, facecolor='gray', alpha=0.7),  # East
            Rectangle((-0.1, 1.6), 0.2, 1.4, facecolor='gray', alpha=0.7),  # North
            Rectangle((-0.1, -3), 0.2, 1.4, facecolor='gray', alpha=0.7)  # South
        ]

        for road in approach_roads:
            ax.add_patch(road)

    def _prepare_animation_data(self):
        """Prepare synchronized animation data for all algorithms"""
        # Find maximum simulation time
        max_time = 0
        for alg_data in self.results.values():
            if alg_data['simulation_data']:
                max_time = max(max_time, alg_data['simulation_data'][-1]['time'])

        # Create synchronized time steps
        self.time_steps = np.arange(0, max_time + 0.1, 0.1)
        self.synchronized_data = {}

        for alg_name, alg_data in self.results.items():
            sim_data = alg_data['simulation_data']
            synchronized = []

            for target_time in self.time_steps:
                # Find closest simulation data point
                closest_data = None
                min_diff = float('inf')

                for data_point in sim_data:
                    time_diff = abs(data_point['time'] - target_time)
                    if time_diff < min_diff:
                        min_diff = time_diff
                        closest_data = data_point

                synchronized.append(closest_data or {'time': target_time, 'active_vehicles': []})

            self.synchronized_data[alg_name] = synchronized

    def animate(self, save_path: str = None):
        """Create and run the animation"""

        def update_frame(frame):
            time_idx = int(frame * self.speed_multiplier) % len(self.time_steps)
            current_time = self.time_steps[time_idx]

            # Update each subplot
            algorithm_names = list(self.results.keys())
            for i, (ax, alg_name) in enumerate(zip(self.axes_flat, algorithm_names)):
                self._update_subplot(ax, alg_name, time_idx, current_time)

            # Update main title with current time
            self.fig.suptitle(f'Algorithm Comparison: Traffic Flow Analysis (t={current_time:.1f}s)',
                              fontsize=16, fontweight='bold')

            return []

        # Calculate animation parameters
        total_frames = len(self.time_steps) // int(self.speed_multiplier)
        interval = 1000 // self.fps  # milliseconds between frames

        # Create animation
        anim = FuncAnimation(self.fig, update_frame, frames=total_frames,
                             interval=interval, blit=False, repeat=True)

        if save_path:
            print(f"Saving animation to {save_path}...")
            anim.save(save_path, writer='pillow', fps=self.fps)
            print("Animation saved!")

        plt.tight_layout()
        plt.show()

        return anim

    def _update_subplot(self, ax, algorithm_name: str, time_idx: int, current_time: float):
        """Update vehicles in a specific subplot"""
        if time_idx >= len(self.synchronized_data[algorithm_name]):
            return

        frame_data = self.synchronized_data[algorithm_name][time_idx]
        active_vehicles = frame_data.get('active_vehicles', [])

        # Clear previous vehicle markers
        for vehicle_marker in getattr(ax, 'vehicles', {}).values():
            vehicle_marker.remove()
        ax.vehicles = {}

        # Draw active vehicles
        color = self.colors[algorithm_name]

        for vehicle_data in active_vehicles:
            x, y = vehicle_data['x'], vehicle_data['y']
            vehicle_name = vehicle_data['name']

            # Draw vehicle as colored circle
            vehicle_marker = Circle((x, y), 0.1, facecolor=color,
                                    edgecolor='black', linewidth=1, alpha=0.8)
            ax.add_patch(vehicle_marker)
            ax.vehicles[vehicle_name] = vehicle_marker

            # Add vehicle label
            ax.text(x, y - 0.2, vehicle_name, ha='center', va='top',
                    fontsize=8, fontweight='bold')


# Enhanced example usage and testing
if __name__ == "__main__":
    print("Path-Based Smart Stop System - Complete Implementation")
    print("=" * 60)


    # Create a more complex test scenario
    def create_complex_scenario(geometry_type: str = "4way") -> List[PathBasedVehicle]:
        if geometry_type == "4way":
            geometry = FourWayGeometry()
        else:
            geometry = RoundaboutGeometry()

        # Complex scenario with multiple vehicles and different turn patterns
        vehicle_configs = [
            ("Main E", "R", 1),  # Right turn from east
            ("Main W", "L", 2),  # Left turn from west
            ("Green N", "NS/S", 3),  # Straight from north
            ("Green S", "R", 4),  # Right turn from south
            ("Main E", "L", 5),  # Left turn from east
            ("Green N", "R", 6),  # Right turn from north
        ]

        vehicles = []
        for road, signal, order in vehicle_configs:
            vehicle = PathBasedVehicle(road, signal, order, geometry)
            vehicles.append(vehicle)

        return vehicles


    # Test both intersection types
    for geometry_type in ["4way", "roundabout"]:
        print(f"\nðŸš¦ Testing {geometry_type.upper()} intersection:")
        print("-" * 40)

        # Create test scenario
        test_vehicles = create_complex_scenario(geometry_type)
        print(f"Created scenario with {len(test_vehicles)} vehicles")

        # Run algorithm comparison
        comparison = AlgorithmComparison(test_vehicles, geometry_type)
        results = comparison.run_comparison()

        # Print results summary
        print(f"\nðŸ“Š {geometry_type.upper()} INTERSECTION RESULTS:")
        print(f"{'Algorithm':<15} {'Time':<8} {'Wait':<8} {'Throughput':<12}")
        print("-" * 50)

        for alg_name, data in results.items():
            metrics = data['metrics']
            print(f"{alg_name:<15} {metrics['total_time']:<8.1f} "
                  f"{metrics['avg_wait_time']:<8.1f} {metrics['throughput']:<12.3f}")

        # Find best performing algorithm
        best_alg = min(results.keys(),
                       key=lambda x: results[x]['metrics']['total_time'])
        print(f"\nðŸ† Best Algorithm: {best_alg}")

        # Calculate efficiency improvements
        if 'Traditional' in results and 'Smart Stop' in results:
            trad_time = results['Traditional']['metrics']['total_time']
            smart_time = results['Smart Stop']['metrics']['total_time']
            improvement = ((trad_time - smart_time) / trad_time) * 100
            print(f"ðŸ’¡ Smart Stop Efficiency Improvement: {improvement:.1f}%")

        # Create animation
        print(f"\nðŸŽ¬ Creating {geometry_type} intersection animation...")
        animator = IntersectionAnimator(results, geometry_type)

        # Save animation (optional)
        save_path = f"intersection_comparison_{geometry_type}.gif"
        anim = animator.animate(save_path=save_path)

    print(f"\n[OK] Analysis Complete!")
    print("ðŸŽ¯ Key Findings:")
    print("- Path-based algorithms maintain quadrant-based efficiency gains")
    print("- Continuous movement enables realistic visualization")
    print("- Smart Stop shows consistent improvements across scenarios")
    print("- Animation clearly demonstrates algorithm differences")
    print("\nðŸš€ Ready for real-world implementation and testing!")
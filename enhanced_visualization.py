#!/usr/bin/env python3
"""
Enhanced Visualization for Smart Stop System
============================================

Features:
- Arrow-shaped vehicles showing direction
- Color-coded by turn signal:
  * Purple: Right turns
  * Green: Left turns
  * Orange: Straight (no signal)
- Octagonal stop signs at each approach
- Stop signs turn green when vehicle activates, red after delay

Usage:
    from enhanced_visualization import EnhancedIntersectionAnimator

    animator = EnhancedIntersectionAnimator(results, "4way")
    animator.animate(save_path="output/animation.gif")
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, Rectangle, Polygon, FancyBboxPatch, Wedge
from matplotlib.collections import PatchCollection
from typing import Dict, List, Tuple
import math


class EnhancedIntersectionAnimator:
    """
    Enhanced matplotlib animation with:
    - Arrow-shaped vehicles
    - Turn signal color coding
    - Dynamic stop signs
    """

    def __init__(self, comparison_results: Dict, geometry_type: str = "4way"):
        self.results = comparison_results
        self.geometry_type = geometry_type

        # Animation parameters
        self.fps = 12
        self.speed_multiplier = 0.6  # 0.6× real-time so vehicles are easy to follow

        # Turn signal color scheme
        self.signal_colors = {
            'R': '#9B59B6',    # Purple for right turns
            'L': '#2ECC71',    # Green for left turns
            'NS/S': '#E67E22'  # Orange for straight/no signal
        }

        # Stop sign colors
        self.stop_sign_red = '#E74C3C'
        self.stop_sign_green = '#2ECC71'
        self.stop_sign_inactive = '#95A5A6'  # Gray when no vehicles

        # Stop sign state tracking (per algorithm, per approach)
        self.stop_sign_states = {}
        self.stop_sign_activation_times = {}

        # Waiting-vehicle tracking (populated in _prepare_animation_data)
        # all_vehicles[alg_name] = {car_name: {road, signal}}
        self.all_vehicles = {}
        # completed_vehicles[alg_name] = set of car_names that have finished
        self.completed_vehicles = {}
        # prev_active_names[alg_name] = set of car_names active last frame
        self.prev_active_names = {}

        # Entry positions for waiting cars (4-way paths and roundabout paths share
        # very similar start points; we use the same table for both).
        # For queueing, each successive waiting car backs up one slot.
        # Entry / waiting positions for 4-way panels — stop-line at the
        # intersection box edge (±1.35), matching where 4-way path arrays
        # begin.
        self._entry_pos = {
            'Main W':  ( 1.35,  0.5),   # enters from east, travels west
            'Main E':  (-1.35, -0.5),   # enters from west, travels east
            'Green N': (-0.5,   1.35),  # enters from north, travels south
            'Green S': ( 0.5,  -1.35),  # enters from south, travels north
        }
        # Phase 2C: separate waiting positions for the Roundabout panel.
        # Roundabout paths actually start at the ring entry-arc (±2.0),
        # not at the stop-line ±1.35.  Pre-2C the visualizer drew waiting
        # roundabout cars at ±1.35 (inside the slow zone) and they then
        # "jumped" backwards to ±2.0 on activation.  Now waiting cars
        # render at their real activation point.
        self._entry_pos_roundabout = {
            'Main W':  ( 2.0,  0.5),
            'Main E':  (-2.0, -0.5),
            'Green N': (-0.5,  2.0),
            'Green S': ( 0.5, -2.0),
        }
        # Direction (and magnitude) each approach backs up when queueing
        # additional cars.  Phase 2C: bumped to 1.0 grid unit = 4.5 m =
        # one full car length, matching the user's stated visualization
        # intent that "the waiting car would appear 1 car length behind
        # the first car."  Pre-2C the 0.45-unit spacing was less than
        # half a car length and queued cars visually overlapped.
        self._entry_backup = {
            'Main W':  ( 1.0,  0.0),   # further east
            'Main E':  (-1.0,  0.0),   # further west
            'Green N': ( 0.0,  1.0),   # further north
            'Green S': ( 0.0, -1.0),   # further south
        }
        self._approach_heading = {
            'Main W':  math.pi,       # westbound
            'Main E':  0.0,           # eastbound
            'Green N': -math.pi/2,    # southbound
            'Green S':  math.pi/2,    # northbound
        }

        # Setup matplotlib
        self.fig, self.axes = plt.subplots(2, 2, figsize=(18, 14))
        self.fig.suptitle('Smart Stop Algorithm Comparison - Enhanced Visualization',
                         fontsize=16, fontweight='bold')

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
        ax.grid(True, alpha=0.2, linestyle='--', linewidth=0.5)
        ax.set_title(f'{algorithm_name}', fontsize=14, fontweight='bold', pad=10)

        # Initialize vehicle and stop sign storage FIRST
        ax.vehicles = {}
        ax.vehicle_labels = {}
        ax.stop_signs = {}

        # Draw intersection layout — Roundabout gets its own road design
        if algorithm_name == "Roundabout":
            self._draw_roundabout_intersection(ax)
        else:
            self._draw_4way_intersection(ax)
            self._add_stop_signs(ax, algorithm_name)

        # Add metrics text
        metrics = self.results[algorithm_name]['metrics']
        metrics_text = (f"Time: {metrics['total_time']:.1f}s\n"
                       f"Wait: {metrics['avg_wait_time']:.1f}s\n"
                       f"Throughput: {metrics['throughput']:.2f}")
        ax.text(0.02, 0.98, metrics_text, transform=ax.transAxes,
               verticalalignment='top', fontsize=11,
               bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                        alpha=0.9, edgecolor='gray', linewidth=1.5))

        # Add color legend
        self._add_signal_legend(ax)

    def _draw_4way_intersection(self, ax):
        """Draw 4-way intersection as two crossing 2-lane roads.

        Lane layout (matches FourWayGeometry entry/exit points):
          Horizontal (Main St):  Main W travels east in top lane  (y≈+0.5)
                                 Main E travels west in bottom lane (y≈-0.5)
          Vertical   (Green St): Green N travels south in left lane (x≈-0.5)
                                 Green S travels north in right lane (x≈+0.5)
        Road extends ±ROAD_HALF from the axis; lane centres sit at ±LANE_CTR.
        """
        ROAD_HALF = 0.85   # half-width of each 2-lane road
        ISECT     = 0.85   # half-side of the intersection box (same value)
        ASPHALT   = '#4A4A4A'
        ISECT_CLR = '#5A5A5A'  # slightly lighter for the intersection box

        # ── Road surfaces ──────────────────────────────────────────────────
        # Horizontal road (full span, behind intersection)
        ax.add_patch(Rectangle((-3, -ROAD_HALF), 6, 2*ROAD_HALF,
                               facecolor=ASPHALT, zorder=1))
        # Vertical road (full span, behind intersection)
        ax.add_patch(Rectangle((-ROAD_HALF, -3), 2*ROAD_HALF, 6,
                               facecolor=ASPHALT, zorder=1))

        # Intersection box (slightly lighter so it reads as a distinct zone)
        ax.add_patch(Rectangle((-ISECT, -ISECT), 2*ISECT, 2*ISECT,
                               facecolor=ISECT_CLR, edgecolor='#888888',
                               linewidth=1.5, zorder=2))

        # ── Outer road-edge lines (white solid) ───────────────────────────
        # Horizontal road: top edge
        ax.plot([-3, -ISECT], [ ROAD_HALF,  ROAD_HALF], 'w-', linewidth=2, zorder=5)
        ax.plot([ ISECT,  3], [ ROAD_HALF,  ROAD_HALF], 'w-', linewidth=2, zorder=5)
        # Horizontal road: bottom edge
        ax.plot([-3, -ISECT], [-ROAD_HALF, -ROAD_HALF], 'w-', linewidth=2, zorder=5)
        ax.plot([ ISECT,  3], [-ROAD_HALF, -ROAD_HALF], 'w-', linewidth=2, zorder=5)
        # Vertical road: left edge
        ax.plot([-ROAD_HALF, -ROAD_HALF], [-3, -ISECT], 'w-', linewidth=2, zorder=5)
        ax.plot([-ROAD_HALF, -ROAD_HALF], [ ISECT,  3], 'w-', linewidth=2, zorder=5)
        # Vertical road: right edge
        ax.plot([ ROAD_HALF,  ROAD_HALF], [-3, -ISECT], 'w-', linewidth=2, zorder=5)
        ax.plot([ ROAD_HALF,  ROAD_HALF], [ ISECT,  3], 'w-', linewidth=2, zorder=5)

        # ── Stop lines (white solid, at intersection mouth) ────────────────
        ax.plot([ ISECT,  ROAD_HALF], [ 0,      ROAD_HALF], 'w-', linewidth=3, zorder=5)  # Main W entry
        ax.plot([-ROAD_HALF, -ISECT], [-ROAD_HALF, 0],      'w-', linewidth=3, zorder=5)  # Main E entry
        ax.plot([-ROAD_HALF,  0],     [ ISECT,  ROAD_HALF], 'w-', linewidth=3, zorder=5)  # Green N entry
        ax.plot([ 0,  ROAD_HALF],     [-ROAD_HALF, -ISECT], 'w-', linewidth=3, zorder=5)  # Green S entry

        # ── Yellow dashed centre-line dividers ────────────────────────────
        dash_kw = dict(color='#F1C40F', linewidth=1.5, linestyle='--',
                       dashes=(6, 6), zorder=6)
        # Horizontal centre line (west arm)
        ax.plot([-3, -ISECT], [0, 0], **dash_kw)
        # Horizontal centre line (east arm)
        ax.plot([ ISECT, 3],  [0, 0], **dash_kw)
        # Vertical centre line (north arm)
        ax.plot([0, 0], [ ISECT,  3], **dash_kw)
        # Vertical centre line (south arm)
        ax.plot([0, 0], [-3, -ISECT], **dash_kw)

        # ── Road labels ────────────────────────────────────────────────────
        labels = [
            (-2.3,  ROAD_HALF + 0.22, 'Main W'),
            ( 2.3, -ROAD_HALF - 0.22, 'Main E'),
            (-ROAD_HALF - 0.22,  2.3, 'Green N'),
            ( ROAD_HALF + 0.22, -2.3, 'Green S'),
        ]
        for x, y, text in labels:
            ax.text(x, y, text, fontsize=9, ha='center', va='center',
                    color='white',
                    bbox=dict(boxstyle='round,pad=0.25', facecolor='#333333',
                              alpha=0.85, edgecolor='none'))

    def _add_stop_signs(self, ax, algorithm_name: str):
        """Add octagonal stop signs at each approach.

        Signs are placed in the corner whitespace (grass/sidewalk) between
        the road arms — i.e. just outside the road edge — as they appear in
        real life on the driver's right as they approach the intersection.
        With ROAD_HALF = 0.85 the four corners are the ±(0.9–1.3) zones.
        """
        sign_positions = {
            'Main W':  ( 1.2,  1.0),   # NE corner — Main W enters from east
            'Green N': (-1.0,  1.2),   # NW corner — Green N enters from north
            'Main E':  (-1.2, -1.0),   # SW corner — Main E enters from west
            'Green S': ( 1.0, -1.2),   # SE corner — Green S enters from south
        }

        # Initialize stop sign state tracking for this algorithm
        if algorithm_name not in self.stop_sign_states:
            self.stop_sign_states[algorithm_name] = {}
            self.stop_sign_activation_times[algorithm_name] = {}

        for approach, (x, y) in sign_positions.items():
            # Create octagon shape
            octagon = self._create_octagon(x, y, radius=0.22)

            # Draw stop sign
            stop_sign = Polygon(octagon, closed=True,
                              facecolor=self.stop_sign_red,
                              edgecolor='white', linewidth=2,
                              zorder=10)
            ax.add_patch(stop_sign)

            # Add "STOP" text
            text = ax.text(x, y, 'STOP', fontsize=9, ha='center', va='center',
                          color='white', fontweight='bold', zorder=11)

            # Store reference
            ax.stop_signs[approach] = {
                'patch': stop_sign,
                'text': text,
                'position': (x, y)
            }

            # Initialize state
            self.stop_sign_states[algorithm_name][approach] = 'red'
            self.stop_sign_activation_times[algorithm_name][approach] = -999

    def _create_octagon(self, x: float, y: float, radius: float = 0.15) -> np.ndarray:
        """Create octagon vertices for stop sign"""
        angles = np.linspace(0, 2*np.pi, 9)  # 8 sides + close
        vertices = np.column_stack([
            x + radius * np.cos(angles),
            y + radius * np.sin(angles)
        ])
        return vertices

    def _add_signal_legend(self, ax):
        """Add color legend for turn signals"""
        legend_y = 0.02
        legend_elements = [
            ('Right', self.signal_colors['R']),
            ('Straight', self.signal_colors['NS/S']),
            ('Left', self.signal_colors['L'])
        ]

        legend_text = "Turn Signals:\n"
        for i, (label, color) in enumerate(legend_elements):
            legend_text += f"● {label}  "

        ax.text(0.02, legend_y, legend_text, transform=ax.transAxes,
               verticalalignment='bottom', fontsize=9,
               bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                        alpha=0.85, edgecolor='gray', linewidth=1))

    def _draw_roundabout_intersection(self, ax):
        """Draw roundabout with proper wide approach roads.

        Geometry (matches RoundaboutGeometry — vehicles travel on r=1.5 circle):
          Ring outer radius : 1.8  (vehicle path r=1.5 sits at ring centre)
          Ring inner radius : 1.2
          Central island    : filled circle r=1.2
          Approach roads    : 1.1 wide, connecting from ±3 to ring outer edge
        """
        ROAD_HALF   = 0.55   # half-width of each approach road (total 1.1)
        RING_OUTER  = 1.8
        RING_INNER  = 1.2
        ASPHALT     = '#4A4A4A'
        ISLAND_CLR  = '#3D6B35'  # green central island
        RING_CLR    = '#5A5A5A'

        # ── Approach road surfaces (drawn first, under ring) ───────────────
        approach_roads = [
            Rectangle((-3,          -ROAD_HALF), 3 - RING_OUTER, 2*ROAD_HALF),  # West
            Rectangle((RING_OUTER,  -ROAD_HALF), 3 - RING_OUTER, 2*ROAD_HALF),  # East
            Rectangle((-ROAD_HALF,  RING_OUTER), 2*ROAD_HALF, 3 - RING_OUTER),  # North
            Rectangle((-ROAD_HALF, -3),          2*ROAD_HALF, 3 - RING_OUTER),  # South
        ]
        for r in approach_roads:
            r.set_facecolor(ASPHALT)
            r.set_zorder(1)
            ax.add_patch(r)

        # ── Roundabout ring (annular travel lane) ──────────────────────────
        ring = plt.matplotlib.patches.Wedge(
            (0, 0), RING_OUTER, 0, 360,
            width=RING_OUTER - RING_INNER,
            facecolor=RING_CLR, edgecolor='#888888', linewidth=1.5, zorder=2
        )
        ax.add_patch(ring)

        # ── Central island ─────────────────────────────────────────────────
        ax.add_patch(Circle((0, 0), RING_INNER,
                            facecolor=ISLAND_CLR, edgecolor='#2C7A1E',
                            linewidth=1.5, zorder=3))

        # ── Road-edge lines on approach arms (white) ───────────────────────
        edge_kw = dict(color='white', linewidth=2, zorder=5)
        # West arm
        ax.plot([-3, -RING_OUTER], [ ROAD_HALF,  ROAD_HALF], **edge_kw)
        ax.plot([-3, -RING_OUTER], [-ROAD_HALF, -ROAD_HALF], **edge_kw)
        # East arm
        ax.plot([ RING_OUTER,  3], [ ROAD_HALF,  ROAD_HALF], **edge_kw)
        ax.plot([ RING_OUTER,  3], [-ROAD_HALF, -ROAD_HALF], **edge_kw)
        # North arm
        ax.plot([ ROAD_HALF,  ROAD_HALF], [ RING_OUTER,  3], **edge_kw)
        ax.plot([-ROAD_HALF, -ROAD_HALF], [ RING_OUTER,  3], **edge_kw)
        # South arm
        ax.plot([ ROAD_HALF,  ROAD_HALF], [-3, -RING_OUTER], **edge_kw)
        ax.plot([-ROAD_HALF, -ROAD_HALF], [-3, -RING_OUTER], **edge_kw)

        # ── Dashed centre lines on approach arms (yellow) ──────────────────
        dash_kw = dict(color='#F1C40F', linewidth=1.5, linestyle='--',
                       dashes=(6, 6), zorder=6)
        ax.plot([-3, -RING_OUTER], [0, 0], **dash_kw)
        ax.plot([ RING_OUTER,  3], [0, 0], **dash_kw)
        ax.plot([0, 0], [ RING_OUTER,  3], **dash_kw)
        ax.plot([0, 0], [-3, -RING_OUTER], **dash_kw)

        # ── Yield lines at ring entry ──────────────────────────────────────
        yield_kw = dict(color='white', linewidth=2.5, linestyle='dotted', zorder=5)
        ax.plot([-RING_OUTER, -RING_OUTER], [-ROAD_HALF,  0           ], **yield_kw)  # West
        ax.plot([ RING_OUTER,  RING_OUTER], [ 0,           ROAD_HALF  ], **yield_kw)  # East
        ax.plot([-ROAD_HALF,   0          ], [ RING_OUTER, RING_OUTER ], **yield_kw)  # North
        ax.plot([ 0,            ROAD_HALF ], [-RING_OUTER,-RING_OUTER ], **yield_kw)  # South

        # Directional arrow removed (Phase 2C feedback) — the arrow was
        # pointing left→right at the top-inner of the ring, but US
        # counterclockwise traffic actually flows right→left there.
        # Rather than flip it, drop it: the entry yield-line markings
        # plus the moving vehicles in the GIF already communicate flow.

        # ── Road labels ────────────────────────────────────────────────────
        labels = [
            (-2.3,  ROAD_HALF + 0.25, 'Main W'),
            ( 2.3, -ROAD_HALF - 0.25, 'Main E'),
            (-ROAD_HALF - 0.25,  2.3, 'Green N'),
            ( ROAD_HALF + 0.25, -2.3, 'Green S'),
        ]
        for x, y, text in labels:
            ax.text(x, y, text, fontsize=9, ha='center', va='center',
                    color='white',
                    bbox=dict(boxstyle='round,pad=0.25', facecolor='#333333',
                              alpha=0.85, edgecolor='none'))

    def _prepare_animation_data(self):
        """Prepare synchronized animation data for all algorithms"""
        # Find maximum simulation time
        max_time = 0
        for alg_data in self.results.values():
            if alg_data['simulation_data']:
                max_time = max(max_time, alg_data['simulation_data'][-1]['time'])

        # Create synchronized time steps.
        # Phase 2C: prepend a 1-second warm-up window where every algorithm
        # holds at t=0 (all cars waiting at the stop line, no activations
        # yet).  This makes the initial 2-car queue visible long enough for
        # a human reviewer to actually see it — pre-warm-up, Main E's queue
        # in Smart Stop was only visible for 1 frame (~83 ms) because Car 1
        # activates almost immediately, so the head→follower stacking
        # appeared to "only work for Green N" (whose head doesn't activate
        # until t=6.3 s).  The simulation timer in the title displays
        # max(0, t - warmup) so post-warm-up time still reads natural.
        self._warmup_seconds = 1.0
        warmup_steps = np.full(int(self._warmup_seconds / 0.1), 0.0)
        post_warmup = np.arange(0, max_time + 0.1, 0.1)
        self.time_steps = np.concatenate([warmup_steps, post_warmup])
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

                synchronized.append(closest_data or {
                    'time': target_time,
                    'active_vehicles': [],
                    'waiting_count': 0,
                    'completed_count': 0
                })

            self.synchronized_data[alg_name] = synchronized

        # ── Build complete vehicle roster per algorithm ─────────────────────
        # Scan every frame to learn every vehicle that will ever appear.
        # all_vehicles[alg][name] = {road, signal, first_frame}
        # Also record each vehicle's last known position/heading for exit coasting.
        self.last_known_pos = {}  # {alg_name: {car_name: {x,y,heading,last_frame_idx}}}

        for alg_name, frames in self.synchronized_data.items():
            roster = {}
            last_pos = {}
            for frame_idx, frame in enumerate(frames):
                for v in frame.get('active_vehicles', []):
                    if v['name'] not in roster:
                        roster[v['name']] = {
                            'road':        v['road'],
                            'signal':      v['signal'],
                            'first_frame': frame_idx,
                        }
                    # Always overwrite so we keep the most recent position
                    last_pos[v['name']] = {
                        'x':              v['x'],
                        'y':              v['y'],
                        'heading':        v.get('heading', 0.0),
                        'last_frame_idx': frame_idx,
                    }
            self.all_vehicles[alg_name] = roster
            self.last_known_pos[alg_name] = last_pos
            self.completed_vehicles[alg_name] = set()
            self.prev_active_names[alg_name] = set()

    def _create_arrow_vehicle(self, x: float, y: float, heading: float,
                             signal: str, size: float = 0.34,
                             alpha: float = 0.92) -> Polygon:
        """Create arrow-shaped vehicle pointing in direction of travel."""
        arrow_shape = np.array([
            [ size,         0          ],  # Front tip
            [-size * 0.6,   size * 0.5 ],  # Back left
            [-size * 0.3,   0          ],  # Notch
            [-size * 0.6,  -size * 0.5 ],  # Back right
        ])

        cos_h = np.cos(heading)
        sin_h = np.sin(heading)
        rotation_matrix = np.array([[cos_h, -sin_h], [sin_h, cos_h]])
        arrow_vertices = (arrow_shape @ rotation_matrix.T) + np.array([x, y])

        color = self.signal_colors.get(signal, self.signal_colors['NS/S'])
        return Polygon(arrow_vertices, closed=True,
                       facecolor=color, edgecolor='white',
                       linewidth=1.5, alpha=alpha, zorder=15)

    def _update_stop_sign(self, ax, algorithm_name: str, approach: str,
                         state: str, current_time: float):
        """
        Update stop sign color based on state

        Args:
            ax: Matplotlib axes
            algorithm_name: Name of algorithm
            approach: Road approach name
            state: 'red', 'green', or 'inactive'
            current_time: Current simulation time
        """
        if approach not in ax.stop_signs:
            return

        stop_sign = ax.stop_signs[approach]

        # Determine color
        if state == 'green':
            color = self.stop_sign_green
            self.stop_sign_activation_times[algorithm_name][approach] = current_time
        elif state == 'red':
            color = self.stop_sign_red
        else:
            color = self.stop_sign_inactive

        # Update color
        stop_sign['patch'].set_facecolor(color)
        self.stop_sign_states[algorithm_name][approach] = state

    def _update_subplot(self, ax, algorithm_name: str, time_idx: int,
                       current_time: float):
        """Update vehicles and stop signs in a specific subplot"""
        if time_idx >= len(self.synchronized_data[algorithm_name]):
            return

        frame_data = self.synchronized_data[algorithm_name][time_idx]
        active_vehicles = frame_data.get('active_vehicles', [])

        # Clear previous vehicle markers
        for vehicle_marker in getattr(ax, 'vehicles', {}).values():
            vehicle_marker.remove()
        for label in getattr(ax, 'vehicle_labels', {}).values():
            label.remove()
        ax.vehicles = {}
        ax.vehicle_labels = {}

        # ── Track completions ───────────────────────────────────────────────
        current_active_names = {v['name'] for v in active_vehicles}
        prev = self.prev_active_names.get(algorithm_name, set())
        # Any vehicle that was active last frame and isn't now has completed
        just_finished = prev - current_active_names
        self.completed_vehicles[algorithm_name].update(just_finished)
        self.prev_active_names[algorithm_name] = current_active_names

        # ── Draw waiting vehicles ───────────────────────────────────────────
        # Group waiting vehicles by approach road so we can stack them
        waiting_by_road: Dict[str, List[str]] = {}
        roster = self.all_vehicles.get(algorithm_name, {})
        completed = self.completed_vehicles.get(algorithm_name, set())

        for car_name, info in roster.items():
            if car_name not in current_active_names and car_name not in completed:
                road = info['road']
                waiting_by_road.setdefault(road, [])
                waiting_by_road[road].append(car_name)

        # Phase 2C: roundabout panel uses a separate base-position table
        # (paths start at the ring entry-arc, not at the stop line).
        entry_pos_table = (self._entry_pos_roundabout
                           if algorithm_name == 'Roundabout'
                           else self._entry_pos)

        for road, waiting_names in waiting_by_road.items():
            # Sort by first_frame so the next-up car is always drawn first
            waiting_names.sort(key=lambda n: roster[n]['first_frame'])
            base_x, base_y = entry_pos_table.get(road, (2.5, 0))
            dx, dy = self._entry_backup.get(road, (0.4, 0))
            heading = self._approach_heading.get(road, 0)

            for slot_idx, car_name in enumerate(waiting_names):
                wx = base_x + slot_idx * dx
                wy = base_y + slot_idx * dy
                signal = roster[car_name]['signal']

                arrow = self._create_arrow_vehicle(wx, wy, heading, signal,
                                                   alpha=0.45)
                ax.add_patch(arrow)
                ax.vehicles[f'wait_{car_name}'] = arrow

                label = ax.text(wx, wy - 0.50, car_name,
                                ha='center', va='top',
                                fontsize=7, fontweight='bold', color='#CCCCCC',
                                bbox=dict(boxstyle='round,pad=0.15',
                                          facecolor='black', alpha=0.45,
                                          edgecolor='none'),
                                zorder=16)
                ax.vehicle_labels[f'wait_{car_name}'] = label

        # ── Track which approaches have active vehicles ─────────────────────
        active_approaches = set()

        # ── Draw active (moving) vehicles ───────────────────────────────────
        for vehicle_data in active_vehicles:
            x, y = vehicle_data['x'], vehicle_data['y']
            vehicle_name = vehicle_data['name']
            signal = vehicle_data['signal']
            road = vehicle_data['road']

            active_approaches.add(road)

            heading = vehicle_data.get('heading',
                       self._estimate_heading(x, y, road, signal))

            arrow = self._create_arrow_vehicle(x, y, heading, signal)
            ax.add_patch(arrow)
            ax.vehicles[vehicle_name] = arrow

            label = ax.text(x, y - 0.50, vehicle_name,
                           ha='center', va='top',
                           fontsize=8, fontweight='bold', color='white',
                           bbox=dict(boxstyle='round,pad=0.2', facecolor='black',
                                    alpha=0.7, edgecolor='none'),
                           zorder=16)
            ax.vehicle_labels[vehicle_name] = label

        # ── Draw exiting vehicles (coast off-screen after path completes) ─────
        # Show completed vehicles gliding out of the view window so they don't
        # abruptly vanish mid-road.  Pure visual — no effect on algorithm logic.
        EXIT_SIM_SECS = 1.5   # seconds of simulation time to coast after completion
        EXIT_SPEED    = 1.35  # units/sim-sec (matches vehicle max_speed of
                              # 6.0 m/s ÷ METERS_PER_UNIT 4.5 ≈ 1.33 units/sec)
        last_pos_map  = self.last_known_pos.get(algorithm_name, {})
        roster        = self.all_vehicles.get(algorithm_name, {})

        for car_name in self.completed_vehicles.get(algorithm_name, set()):
            info = last_pos_map.get(car_name)
            if info is None:
                continue
            elapsed = current_time - self.time_steps[info['last_frame_idx']]
            if elapsed <= 0 or elapsed > EXIT_SIM_SECS:
                continue
            heading = info['heading']
            ex = info['x'] + EXIT_SPEED * elapsed * math.cos(heading)
            ey = info['y'] + EXIT_SPEED * elapsed * math.sin(heading)
            # Stop drawing once the car has left the axes bounds
            if not (-3.2 <= ex <= 3.2 and -3.2 <= ey <= 3.2):
                continue
            signal = roster.get(car_name, {}).get('signal', 'NS/S')
            fade = max(0.15, 0.7 * (1.0 - elapsed / EXIT_SIM_SECS))
            arrow = self._create_arrow_vehicle(ex, ey, heading, signal, alpha=fade)
            ax.add_patch(arrow)
            ax.vehicles[f'exit_{car_name}'] = arrow

        # ── Update stop signs (only for algorithms that have them) ─────────
        if algorithm_name in self.stop_sign_activation_times:
            for approach in ['Main W', 'Green N', 'Main E', 'Green S']:
                if approach in active_approaches:
                    self._update_stop_sign(ax, algorithm_name, approach, 'green', current_time)
                else:
                    last_activation = self.stop_sign_activation_times[algorithm_name].get(approach, -999)
                    if current_time - last_activation > 1.5:
                        if self.stop_sign_states[algorithm_name].get(approach) == 'green':
                            self._update_stop_sign(ax, algorithm_name, approach, 'red', current_time)

    def _estimate_heading(self, x: float, y: float, road: str, signal: str) -> float:
        """
        Estimate vehicle heading based on position and road

        Returns heading in radians
        """
        # Simple heuristic based on road and position
        if road == "Main E":
            if signal == "R":
                if y < -0.3:
                    return 0  # East
                elif x > 0.3:
                    return -np.pi/2  # South
                else:
                    return -np.pi/4  # Southeast
            elif signal == "L":
                if y < 0:
                    return 0  # East
                elif x < 0:
                    return np.pi/2  # North
                else:
                    return np.pi/4  # Northeast
            else:  # Straight
                return 0  # East

        elif road == "Main W":
            if signal == "R":
                if y > 0.3:
                    return np.pi  # West
                elif x < -0.3:
                    return np.pi/2  # North
                else:
                    return 3*np.pi/4  # Northwest
            elif signal == "L":
                if y > 0:
                    return np.pi  # West
                elif x > 0:
                    return -np.pi/2  # South
                else:
                    return -3*np.pi/4  # Southwest
            else:  # Straight
                return np.pi  # West

        elif road == "Green N":
            if signal == "R":
                if x < -0.3:
                    return -np.pi/2  # South
                elif y < -0.3:
                    return np.pi  # West
                else:
                    return -3*np.pi/4  # Southwest
            elif signal == "L":
                if x < 0:
                    return -np.pi/2  # South
                elif y > 0:
                    return 0  # East
                else:
                    return -np.pi/4  # Southeast
            else:  # Straight
                return -np.pi/2  # South

        elif road == "Green S":
            if signal == "R":
                if x > 0.3:
                    return np.pi/2  # North
                elif y > 0.3:
                    return 0  # East
                else:
                    return np.pi/4  # Northeast
            elif signal == "L":
                if x > 0:
                    return np.pi/2  # North
                elif y < 0:
                    return np.pi  # West
                else:
                    return 3*np.pi/4  # Northwest
            else:  # Straight
                return np.pi/2  # North

        # Default: point east
        return 0

    def animate(self, save_path: str = None, show: bool = True):
        """Create and run the animation"""

        def update_frame(frame):
            time_idx = int(frame * self.speed_multiplier) % len(self.time_steps)
            current_time = self.time_steps[time_idx]

            # Update each subplot
            algorithm_names = list(self.results.keys())
            for ax, alg_name in zip(self.axes_flat, algorithm_names):
                self._update_subplot(ax, alg_name, time_idx, current_time)

            # Update main title with current time
            self.fig.suptitle(
                f'Smart Stop Algorithm Comparison - Enhanced Visualization (t={current_time:.1f}s)',
                fontsize=16, fontweight='bold')

            return []

        # Calculate animation parameters.
        # speed_multiplier may be < 1 (slow-down), so avoid int() truncating to 0.
        total_frames = max(1, int(len(self.time_steps) / self.speed_multiplier))
        interval = 1000 // self.fps  # milliseconds between frames

        # Create animation
        anim = FuncAnimation(self.fig, update_frame, frames=total_frames,
                           interval=interval, blit=False, repeat=True)

        if save_path:
            print(f"Saving animation to {save_path}...")
            anim.save(save_path, writer='pillow', fps=self.fps)
            print(f"✅ Animation saved!")

        if show:
            plt.tight_layout()
            plt.show()

        return anim


# =============================================================================
# Test and Demo
# =============================================================================

if __name__ == "__main__":
    """Test the enhanced visualization"""

    print("Enhanced Visualization Test")
    print("=" * 60)

    # Import necessary modules
    from path_based_smart_stop import (
        PathBasedVehicle, FourWayGeometry, AlgorithmComparison
    )
    from config import OUTPUT_DIR
    import os

    # Create test scenario
    geometry = FourWayGeometry()

    # Mix of different turn signals to show color coding
    vehicles = [
        PathBasedVehicle("Main E", "R", 1, geometry),      # Purple
        PathBasedVehicle("Green N", "L", 2, geometry),     # Green
        PathBasedVehicle("Main W", "NS/S", 3, geometry),   # Orange
        PathBasedVehicle("Green S", "R", 4, geometry),     # Purple
    ]

    print("\nRunning algorithm comparison...")
    comparison = AlgorithmComparison(vehicles, "4way")
    results = comparison.run_comparison()

    print("\nCreating enhanced animation...")
    animator = EnhancedIntersectionAnimator(results, "4way")

    # Save animation
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    save_path = os.path.join(OUTPUT_DIR, "enhanced_demo.gif")

    anim = animator.animate(save_path=save_path, show=False)

    print(f"\n✅ Enhanced visualization complete!")
    print(f"   Saved to: {save_path}")
    print("\nFeatures:")
    print("  • Arrow-shaped vehicles showing direction")
    print("  • Color-coded turn signals (Purple=R, Green=L, Orange=S)")
    print("  • Octagonal stop signs at each approach")
    print("  • Stop signs turn green when vehicle activates")
    print("  • Stop signs return to red after 1.5 second delay")

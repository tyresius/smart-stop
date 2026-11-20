#!/usr/bin/env python3
"""
render_reality_demos.py — two-panel reality-suite GIFs for the deck refresh
===========================================================================
NEW module (deck-refresh brief rule 3: no algorithm/physics file is touched).

It does three things:
  1. `simulate_and_record` — replicates `capacity_curves.run_stream`'s vehicle
     wiring (fair speed caps, reaction jitter, rolling fields, evasive peers,
     the queue/move-up abstraction) and its stepping loop, but records
     per-step vehicle positions in the `simulation_data` dict format that
     `EnhancedIntersectionAnimator` consumes (see
     `path_based_smart_stop.py::run_comparison`). It windows the recording to
     a chosen [t_start, t_end] and subsamples every N sim steps.
  2. `TwoPanelAnimator` — a subclass of the stock (2×2) animator that renders
     a 1×2 comparison and can highlight one tracked vehicle with a ring.
  3. `render_gif_A/B/C` — the three demos the brief specifies, each pinned to
     the exact schedule/controller in the brief and CLAIMS.md.

Playback: frames are relabelled to 0.1 s spacing so a subsampled ~90 s window
plays back compressed; with fps=10 / subsample=2 motion runs at 2.0x real
time (a 90 s window is ~45 s of GIF). The first cut used 4.5x per the
brief's "under ~25 s" target; Patrick's visual review found the cars too
fast to follow, and watchability wins over duration for live presentation.

Usage:
    python render_reality_demos.py A        # starvation (flagship)
    python render_reality_demos.py B        # arterial rout
    python render_reality_demos.py C        # platoon service
    python render_reality_demos.py all
    python render_reality_demos.py A --smoke # tiny window, fast sanity render
"""

import math
import os
import random
import sys
from collections import deque

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from config import METERS_PER_UNIT
from path_based_smart_stop import FourWayGeometry, RoundaboutAlgorithm
from block2_platoon import PlatoonSmartStop, FollowingVehicle
from block3_reality import RollingVehicle, EvasiveVehicle, ROLL_WINDOW
from reality_sweeps import RealityVehicle, FAIR_CAP_4WAY, FAIR_CAP_RING
from capacity_curves import (
    ROADS, DT, SEED, MOVE_UP_TIME, T_MAX, JITTER, NO_JITTER_ALGS, ALG_MAP,
    make_schedule, freeflow_time,
)
# Import so the extended controllers register their ALG_MAP names.
import block5_adaptive   # noqa: F401  SmartStopAdaptive / SmartStopPreflash
import block7_response   # noqa: F401  SmartStopResponse
import cs_final_runs     # noqa: F401  SmartStopPreflashOnly
from starvation_probe import make_probe_schedule, VICTIM, DOMINANT
from enhanced_visualization import EnhancedIntersectionAnimator

OUTPUT_DIR = "output"


# ─────────────────────────────────────────────────────────────────────────────
# Simulate one algorithm on a schedule, recording animator frames in a window
# ─────────────────────────────────────────────────────────────────────────────

def simulate_and_record(alg_name, schedule, *, fair=True, jumpers=None,
                        t_start=0.0, t_end=None, subsample=2):
    """Run `alg_name` on `schedule` (mirrors capacity_curves.run_stream) and
    return {'metrics', 'simulation_data', 'road_delay', 'track'} where
    simulation_data is the animator frame list for the [t_start, t_end] window.
    `track` maps road_name -> the order-id of that road's longest-waiting
    served vehicle in the window (used to pick a vehicle to highlight)."""
    AlgClass = ALG_MAP[alg_name]
    use_rb = issubclass(AlgClass, RoundaboutAlgorithm)
    platoon = issubclass(AlgClass, PlatoonSmartStop)
    rolling = getattr(AlgClass, 'USE_ROLLING', False)
    evasive = getattr(AlgClass, 'USE_EVASIVE', False)
    VehCls = (EvasiveVehicle if evasive
              else RollingVehicle if rolling
              else FollowingVehicle if platoon else RealityVehicle)
    jitter = alg_name not in NO_JITTER_ALGS
    geometry = FourWayGeometry()
    alg = AlgClass(geometry)
    roll_watch = []

    def make_vehicle(road, sig, order, t_line):
        v = VehCls(road, sig, order, geometry, use_roundabout_paths=use_rb)
        if fair:
            v.INTERSECTION_SPEED = (FAIR_CAP_RING if use_rb
                                    else FAIR_CAP_4WAY[sig])
        if jitter:
            vrng = random.Random(f"{SEED}-jit-{order}")
            v.reaction_delay = vrng.uniform(*JITTER)
        if evasive:
            v._peers = alg.active_vehicles
        if jumpers is not None:
            q, p_lo, p_hi = jumpers
            jrng = random.Random(f"{SEED}-jump-{order}")
            v._is_jumper = jrng.random() < q
            v._patience = jrng.uniform(p_lo, p_hi)
        if rolling:
            v.roll_deadline = t_line + ROLL_WINDOW
            v.roll_v0 = ((FAIR_CAP_RING if use_rb else FAIR_CAP_4WAY[sig])
                         if fair else 2.0)
            v.state.velocity = v.roll_v0
            roll_watch.append(v)
        return v

    pending = {r: deque() for r in ROADS}
    for ev in schedule:
        pending[ev[1]].append(ev)
    at_line = {r: None for r in ROADS}
    line_free = {r: 0.0 for r in ROADS}
    records = {}

    if t_end is None:
        t_end = T_MAX
    t = 0.0
    step_i = 0
    frames = []

    steps = int(T_MAX / DT)
    for _ in range(steps):
        # ── Feed vehicles (identical to run_stream) ─────────────────────────
        for r in ROADS:
            if platoon:
                while pending[r] and t >= pending[r][0][0]:
                    t_arr, road, sig, order = pending[r].popleft()
                    v = make_vehicle(road, sig, order, t)
                    alg.add_vehicle(v)
                    records[order] = dict(order=order, road=road, signal=sig,
                                          t_arrival=t_arr, vehicle=v)
                continue
            occ = at_line[r]
            if occ is not None and occ.start_time is not None:
                line_free[r] = occ.start_time + MOVE_UP_TIME
                at_line[r] = None
                occ = None
            if occ is None and pending[r]:
                t_arr, road, sig, order = pending[r][0]
                if t >= max(t_arr, line_free[r]):
                    pending[r].popleft()
                    v = make_vehicle(road, sig, order, t)
                    alg.add_vehicle(v)
                    at_line[r] = v
                    records[order] = dict(order=order, road=road, signal=sig,
                                          t_arrival=t_arr, vehicle=v)

        # ── Flash-jumpers (identical to run_stream) ─────────────────────────
        if jumpers is not None and platoon:
            heads = {}
            for v in alg.waiting_vehicles:
                if v.road_name not in heads:
                    heads[v.road_name] = v
            pending_roads = {p.road_name for p in getattr(alg, '_pending', [])}
            for v in heads.values():
                if not (getattr(v, '_is_jumper', False)
                        and v.arrival_time is not None
                        and t - v.arrival_time > v._patience):
                    continue
                if v.road_name in pending_roads:
                    continue
                if any(a.road_name == v.road_name and a.active
                       and a.current_position_meters < 7.0
                       for a in alg.active_vehicles):
                    continue
                alg.waiting_vehicles.remove(v)
                v.reaction_delay = 0.0
                v.activate(t)
                v.state.velocity = 0.0
                alg.active_vehicles.append(v)

        status = alg.step(DT)
        t = status['time'] if abs(status['time'] - (t + DT)) < 1e-6 else t + DT

        if roll_watch:
            for v in roll_watch[:]:
                if v.active:
                    roll_watch.remove(v)
                elif t > v.roll_deadline:
                    v.state.velocity = 0.0
                    roll_watch.remove(v)

        # ── Record a frame (windowed + subsampled) ──────────────────────────
        if t_start <= t <= t_end and (step_i % subsample == 0):
            actives = getattr(alg, 'active_vehicles', None)
            if actives is None:
                av = getattr(alg, 'active_vehicle', None)
                actives = [av] if av else []
            active_states = []
            for v in actives:
                if v is None or not v.active:
                    continue
                active_states.append(dict(
                    name=v.car_name,
                    x=getattr(v, 'x', v.state.x),
                    y=getattr(v, 'y', v.state.y),
                    heading=v.state.heading,
                    road=v.road_name, signal=v.signal))
            frames.append(dict(
                time=len(frames) * 0.1,          # compressed playback clock
                sim_time=t,
                active_vehicles=active_states,
                waiting_count=status['waiting'],
                completed_count=status['completed']))
        step_i += 1

        # Rendering only needs the window: stop once we're past it (either the
        # queues drained early, or we've simulated through t_end).
        if t > t_end and (status['active'] == 0 or t > t_end + 5.0):
            break

    # ── Per-vehicle control delay in the window (for panel captions/track) ──
    road_delay = {r: [] for r in ROADS}
    track = {}                       # road -> (order, delay) of worst waiter
    for order, rec in records.items():
        v = rec['vehicle']
        if v.intersection_exit_time is None:
            continue
        if not (t_start <= rec['t_arrival'] <= t_end):
            continue
        ff = freeflow_time(rec['road'], rec['signal'], use_rb, fair)
        d = max(0.0, (v.intersection_exit_time - rec['t_arrival']) - ff)
        road_delay[rec['road']].append(d)
        if rec['road'] not in track or d > track[rec['road']][1]:
            track[rec['road']] = (v.car_name, d)

    all_d = [d for ds in road_delay.values() for d in ds]
    metrics = dict(
        total_time=frames[-1]['sim_time'] if frames else 0.0,
        avg_wait_time=float(np.mean(all_d)) if all_d else 0.0,
        throughput=float(len(all_d)),
    )
    road_mean = {r: (float(np.mean(ds)) if ds else 0.0)
                 for r, ds in road_delay.items()}
    return dict(metrics=metrics, simulation_data=frames,
                road_delay=road_mean, track=track)


# ─────────────────────────────────────────────────────────────────────────────
# Two-panel animator with an optional tracked-vehicle ring
# ─────────────────────────────────────────────────────────────────────────────

class TwoPanelAnimator(EnhancedIntersectionAnimator):
    """1×2 comparison. `highlight_car` (a car_name) is ringed each frame,
    whether it is waiting or moving, so a reviewer can track one vehicle."""

    def __init__(self, results, geometry_type="4way", highlight_car=None,
                 scene_title=""):
        super().__init__(results, geometry_type)   # builds 2×2, preps data
        plt.close(self.fig)                        # discard the 2×2 canvas
        n = len(results)
        self.fig, axes = plt.subplots(1, n, figsize=(9 * n, 9))
        self.axes_flat = np.atleast_1d(axes).ravel()
        for i, (ax, alg_name) in enumerate(zip(self.axes_flat, results.keys())):
            self._setup_subplot(ax, alg_name, i)
        # 0.2 sim-s per recorded frame (subsample=2) at 10 fps = 2.0x real
        # time. Patrick's July 16 review of the first cut (0.3 s at 15 fps =
        # 4.5x) found the motion too fast to follow — this is half that.
        self.fps = 10
        self.speed_multiplier = 1.0
        self.highlight_car = highlight_car
        self.scene_title = scene_title

    def animate(self, save_path=None, show=False):
        """Same driver as the stock animator but with a clean, fixed scene
        title (real sim-time, not the compressed playback clock) instead of the
        stock 'Smart Stop Algorithm Comparison - Enhanced Visualization' suptitle."""
        from matplotlib.animation import FuncAnimation

        def update_frame(frame):
            time_idx = int(frame * self.speed_multiplier) % len(self.time_steps)
            current_time = self.time_steps[time_idx]
            names = list(self.results.keys())
            for ax, alg_name in zip(self.axes_flat, names):
                self._update_subplot(ax, alg_name, time_idx, current_time)
            # Real sim-time from the synchronized frame (compressed clock is
            # display-only); synchronized_data is aligned to self.time_steps.
            sd = self.synchronized_data[names[0]]
            st = sd[time_idx].get('sim_time') if time_idx < len(sd) else None
            suffix = f"   t = {st:.0f}s" if st is not None else ""
            self.fig.suptitle(self.scene_title + suffix,
                              fontsize=18, fontweight='bold')
            return []

        total_frames = max(1, int(len(self.time_steps) / self.speed_multiplier))
        anim = FuncAnimation(self.fig, update_frame, frames=total_frames,
                             interval=1000 // self.fps, blit=False, repeat=True)
        if save_path:
            print(f"Saving animation to {save_path}...")
            anim.save(save_path, writer='pillow', fps=self.fps)
        return anim

    def _setup_subplot(self, ax, algorithm_name, subplot_idx):
        """Same as the stock panel setup but WITHOUT the metrics text box —
        the authoritative delay numbers live on the deck slide (from CLAIMS),
        not baked into the visual (a 90 s window sample would misrepresent the
        full-window claim). Title + intersection + stop signs + legend only."""
        ax.set_xlim(-3, 3)
        ax.set_ylim(-3, 3)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.2, linestyle='--', linewidth=0.5)
        ax.set_title(f'{algorithm_name}', fontsize=16, fontweight='bold', pad=10)
        ax.vehicles = {}
        ax.vehicle_labels = {}
        ax.stop_signs = {}
        if algorithm_name == "Roundabout":
            self._draw_roundabout_intersection(ax)
        else:
            self._draw_4way_intersection(ax)
            self._add_stop_signs(ax, algorithm_name)
        self._add_signal_legend(ax)

    def _update_subplot(self, ax, algorithm_name, time_idx, current_time):
        ring = getattr(ax, '_hl_ring', None)
        if ring is not None:
            ring.remove()
            ax._hl_ring = None
        super()._update_subplot(ax, algorithm_name, time_idx, current_time)
        if not self.highlight_car:
            return
        for key in (self.highlight_car, f'wait_{self.highlight_car}'):
            patch = ax.vehicles.get(key)
            if patch is not None:
                xy = patch.get_xy()
                cx, cy = float(xy[:, 0].mean()), float(xy[:, 1].mean())
                r = Circle((cx, cy), 0.6, fill=False, edgecolor='#FFD400',
                           linewidth=3.0, zorder=25)
                ax.add_patch(r)
                ax._hl_ring = r
                break


def _render(results, save_name, highlight_car=None, scene_title=""):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, save_name)
    anim = TwoPanelAnimator(results, highlight_car=highlight_car,
                            scene_title=scene_title)
    anim.animate(save_path=path, show=False)
    n = len(next(iter(results.values()))['simulation_data'])
    print(f"  -> {path}  ({n} frames, ~{n/10:.0f}s)")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# The three demos
# ─────────────────────────────────────────────────────────────────────────────

def render_gif_A(smoke=False):
    """Starvation (flagship). Roundabout vs SmartStopReal on the probe hot
    split. GIF A uses SmartStopReal (NOT SmartStopResponse) — audit 2026-07-08
    found pre-flash forfeits side-street protection; SmartStopReal is the
    controller CLAIMS §4 attributes the 37 s victim delay to. Track one Green S
    victim: starved on the roundabout, served on schedule by Smart Stop."""
    sched = make_probe_schedule(2000, rep=0, mode='poisson')
    t_start, t_end = (200.0, 260.0) if smoke else (200.0, 290.0)
    print("GIF A — starvation: Roundabout vs SmartStopReal")
    rb = simulate_and_record('Roundabout', sched, t_start=t_start, t_end=t_end)
    ss = simulate_and_record('SmartStopReal', sched, t_start=t_start, t_end=t_end)
    # Highlight the worst-waiting Green S vehicle on the ROUNDABOUT (the
    # starved victim), and the same car_name on the Smart Stop panel.
    victim_car = rb['track'].get(VICTIM, (None, 0))[0]
    print(f"  tracked victim (Green S): {victim_car}  "
          f"rb victim-road mean={rb['road_delay'][VICTIM]:.1f}s  "
          f"ss victim-road mean={ss['road_delay'][VICTIM]:.1f}s")
    results = {"Roundabout": rb, "Smart Stop": ss}
    return _render(results, "reality_A_starvation.gif", highlight_car=victim_car,
                   scene_title="Side-street starvation  (hot split, 2,000 veh/h)  "
                               "-  ring = tracked Green S victim")


def render_gif_B(smoke=False):
    """Arterial rout. Roundabout vs PreflashOnlySmartStop, arterial split,
    steady state (skip 120 s warm-up). On-slide: 37.7 vs 73.3 s (CLAIMS §3)."""
    sched = make_schedule(2000, 0, split=[0.4, 0.4, 0.1, 0.1])
    t_start, t_end = (200.0, 260.0) if smoke else (200.0, 290.0)
    print("GIF B — arterial: Roundabout vs SmartStopPreflashOnly")
    rb = simulate_and_record('Roundabout', sched, t_start=t_start, t_end=t_end)
    ss = simulate_and_record('SmartStopPreflashOnly', sched,
                             t_start=t_start, t_end=t_end)
    print(f"  rb overall mean={rb['metrics']['avg_wait_time']:.1f}s  "
          f"ss overall mean={ss['metrics']['avg_wait_time']:.1f}s")
    results = {"Roundabout": rb, "Smart Stop": ss}
    return _render(results, "reality_B_arterial.gif",
                   scene_title="Arterial 40/40/10/10  (2,000 veh/h, steady state)")


def _platoon_schedule():
    """Hand-built: 5 same-signal cars on Main E over 10 s + 2 cross cars."""
    ev = []
    for k in range(5):
        ev.append((2.0 + k * 2.0, 'Main E', 'NS/S'))
    ev.append((4.0, 'Green N', 'NS/S'))
    ev.append((9.0, 'Green S', 'NS/S'))
    ev.sort()
    return [(t, r, s, i + 1) for i, (t, r, s) in enumerate(ev)]


def render_gif_C(smoke=False):
    """Platoon service. GatedPlatoonSmartStop vs Traditional on one Main E
    queue of 5 + light cross traffic: one green window drains the platoon at
    ~2.9 s headways vs one-car-per-clearance."""
    sched = _platoon_schedule()
    print("GIF C — platoon: SmartStopReal vs Traditional")
    # Same window + subsample on both panels so the shared playback clock is
    # real-time aligned: Smart Stop drains the platoon and empties while
    # Traditional is still serving one car per clearance.
    t_end = 75.0
    ss = simulate_and_record('SmartStopReal', sched, t_start=0.0, t_end=t_end)
    tr = simulate_and_record('Traditional', sched, t_start=0.0, t_end=t_end)
    results = {"Smart Stop": ss, "Traditional": tr}
    return _render(results, "reality_C_platoon.gif",
                   scene_title="Platoon service  (5-car queue + light cross traffic)")


if __name__ == "__main__":
    smoke = "--smoke" in sys.argv
    which = next((a for a in sys.argv[1:] if not a.startswith("-")), "all")
    todo = ['A', 'B', 'C'] if which == "all" else [which.upper()]
    for g in todo:
        {'A': render_gif_A, 'B': render_gif_B, 'C': render_gif_C}[g](smoke=smoke)

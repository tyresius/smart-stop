#!/usr/bin/env python3
"""
Reality Sweeps — kill-risk stress tests for Smart Stop
=======================================================
Product model under test: Smart Stop is a stop sign that behaves like a
stoplight — it flashes green per approach to tell a driver when to go.
Activation is therefore real (the flash), but three deployment realities
could erode or erase the simulated advantage:

  1. INTENT sweep — a fraction p of drivers don't signal their turn (or the
     camera can't read the blinker at night / in rain). The controller must
     treat unknown intent as worst-case L — the same convention as the H1
     audit fix. Vehicles still DRIVE their true path; only the controller's
     topological green-light shortcuts (Rules 1-3) degrade, forcing the
     conservative distance check. Safety is preserved by construction; the
     question is how much throughput advantage survives.

  2. REACTION sweep — the green flash is not instant actuation. Every
     activation, in EVERY algorithm (Traditional drivers self-start after
     deciding it's their turn; roundabout drivers judge a gap then go), incurs
     a driver perception-reaction delay before the vehicle moves. Uniform
     delays shift everyone; heterogeneous ("jitter") delays are the dangerous
     case because they break co-activation synchrony — so we also track the
     realized minimum inter-vehicle distance to see whether margins hold.

  3. RING-SPEED sweep — roundabout real-world fairness. The current model
     caps ring circulation at INTERSECTION_SPEED = 2.0 m/s (7.2 km/h); real
     mini-roundabouts circulate at ~15-30 km/h (4.2-8.3 m/s). Sweeps the
     roundabout's slow-zone speed to real-world values while leaving the
     4-way slow zone untouched (2.0 m/s is defensible there: it approximates
     a car accelerating from a legally-required dead stop across a 12 m box).

Known residual bias NOT corrected here (favors Smart Stop): roundabout
vehicles still activate from a dead stop at the yield line, whereas real
drivers entering a clear ring roll through without stopping. A fair fix
requires arrival-speed modeling; until then, even the "fair" ring-speed
numbers slightly flatter Smart Stop.

Method: stratified sample of the permutation space (all 108 two-vehicle
scenarios + seeded samples of 3- and 4-vehicle scenarios). The SAME scenario
set and the SAME per-vehicle random draws are used at every sweep point, so
all comparisons are paired.

Usage:
    python reality_sweeps.py            # full sweep -> reality_sweeps_results.csv
    python reality_sweeps.py --smoke    # 12-scenario timing smoke test

No existing module is modified: reaction delay and observed-signal
substitution are injected via a PathBasedVehicle subclass.
"""

import csv
import itertools
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import METERS_PER_UNIT
from path_based_smart_stop import (
    PathBasedVehicle, FourWayGeometry,
    TraditionalStopAlgorithm, RoundaboutAlgorithm,
    PathBasedSmartStopAlgorithm, SmartStopSafeAlgorithm,
)

ROADS   = ['Main E', 'Main W', 'Green N', 'Green S']
SIGNALS = ['R', 'L', 'NS/S']
DT        = 0.1
MAX_STEPS = 1500          # 150 sim-seconds safety ceiling (matches benchmark)
SEED      = 42

# Stratified sample sizes per vehicle count (2-vehicle runs exhaustively).
N_SAMPLE_3V = 120
N_SAMPLE_4V = 120

# Sweep points
INTENT_LEVELS   = [0.25, 0.50, 1.00]          # fraction of unsignaled drivers
REACTION_LEVELS = [0.8, 1.5]                  # fixed perception-reaction delay (s)
REACTION_JITTER = ("jitter", 0.5, 2.0)        # heterogeneous U(0.5, 2.0) draw
RING_SPEEDS     = [3.0, 4.2, 5.5]             # m/s; 4.2 ~ 15 km/h, 5.5 ~ 20 km/h


# ─────────────────────────────────────────────────────────────────────────────
# Vehicle with reality knobs
# ─────────────────────────────────────────────────────────────────────────────

class RealityVehicle(PathBasedVehicle):
    """PathBasedVehicle + (a) driver reaction delay after the green flash,
    (b) an observed signal distinct from the true signal.

    The TRUE signal generates the driving path in __init__; afterwards
    self.signal is overwritten with the OBSERVED signal so every controller
    lookup (rule selection, EXIT_ARM, priority bonus) sees only what a
    camera could see, while the vehicle drives its true path. The turn-aware
    detector's Rule 4 distance check walks the true path arrays, so treating
    unknown intent as L only disables green-light shortcuts — it never
    green-lights a genuinely conflicting pair.
    """

    def __init__(self, road_name, signal, order, geometry,
                 use_roundabout_paths=False,
                 reaction_delay=0.0, observed_signal=None,
                 ring_speed=None):
        super().__init__(road_name, signal, order, geometry,
                         use_roundabout_paths=use_roundabout_paths)
        self.true_signal = signal
        if observed_signal is not None:
            self.signal = observed_signal
        self.reaction_delay = reaction_delay
        self._go_time = None
        if ring_speed is not None and use_roundabout_paths:
            # Instance attribute shadows the class-level INTERSECTION_SPEED,
            # raising the ring slow-zone cap for this vehicle only. The
            # kinematic predictor reads the same attribute, so prediction
            # stays consistent with behavior.
            self.INTERSECTION_SPEED = ring_speed

    def activate(self, current_time):
        super().activate(current_time)
        self._go_time = current_time + self.reaction_delay

    def update(self, dt, target_speed=None):
        # Driver hasn't reacted to the flash yet: clock advances, car doesn't.
        if (self.active and self._go_time is not None
                and self.current_time + dt <= self._go_time):
            self.current_time += dt
            return True
        return super().update(dt, target_speed)


# ─────────────────────────────────────────────────────────────────────────────
# Curvature-fair physics (symmetric speed model)
# ─────────────────────────────────────────────────────────────────────────────
# The original model caps EVERY in-zone vehicle at 2.0 m/s — including 4-way
# straight-through cars that have no curvature reason to slow, and roundabout
# ring traffic that really circulates at 15-30 km/h. A symmetric model limits
# speed by path curvature only: v_cap = sqrt(a_lat * r), same comfortable
# lateral acceleration everywhere (2.5 m/s^2 ~ 0.25 g).
#
#   4-way NS/S:  straight, no curvature       -> cap = max_speed (6.0 m/s)
#   4-way R:     corner radius ~0.9 u = 4.0 m -> sqrt(2.5*4.0)  ~ 3.2 m/s
#   4-way L:     corner radius ~1.7 u = 7.7 m -> sqrt(2.5*7.7)  ~ 4.4 m/s
#   Roundabout:  ring radius 1.5 u = 6.75 m   -> sqrt(2.5*6.75) ~ 4.1 m/s
#
# Deliberately NOT corrected (still favors Smart Stop): roundabout vehicles
# continue to launch from a dead stop at the yield line instead of rolling
# into a clear ring. If the roundabout wins under this handicap, the result
# is solid; if Smart Stop wins, rolling entry must be modeled before claiming.
FAIR_CAP_4WAY = {"R": 3.2, "L": 4.4, "NS/S": 6.0}
FAIR_CAP_RING = 4.1


# ─────────────────────────────────────────────────────────────────────────────
# Perception-honest collision checking
# ─────────────────────────────────────────────────────────────────────────────

# Distance traveled (m) after which a camera can infer intent from the
# developing trajectory even without a blinker (~one car length into the box,
# where R/NS/L paths have visibly diverged).
REVEAL_M = 4.0


class PerceptionDetector:
    """Wraps the algorithm's collision detector so that unsignaled vehicles
    are checked against ALL THREE possible paths (R, NS/S, L), blocking unless
    every hypothesis is safe.

    Why: the turn-aware detector's Rule 4 fallback walks the vehicle's actual
    path arrays — ground truth a camera does not have for a car whose blinker
    it cannot read. Simply relabeling the signal (the H1 trick) still leaks
    the true trajectory through the distance check. The honest model
    substitutes phantom vehicles carrying each hypothetical path, kinematic
    state synced from the real vehicle at check time. The true-signal phantom
    is always among the hypotheses, so no genuinely conflicting pair can be
    green-lit — safety is preserved by construction; only throughput can
    suffer.

    Once the real vehicle has traveled REVEAL_M metres, its trajectory is
    visually unambiguous and the hypothesis set collapses to the true path.
    """

    def __init__(self, inner, variant_map):
        self.inner = inner
        self.variant_map = variant_map            # id(vehicle) -> [phantoms]
        self.safety_margin = inner.safety_margin  # keep attribute contract

    def _variants(self, v):
        phantoms = self.variant_map.get(id(v))
        if not phantoms:
            return [v]
        if v.active and v.current_position_meters > REVEAL_M:
            true_ph = [p for p in phantoms if p.signal == v.true_signal]
            phantoms = true_ph or phantoms
        for p in phantoms:
            p.active = v.active
            p.completed = v.completed
            p.current_position_meters = v.current_position_meters
            p.state.velocity = v.state.velocity
        return phantoms

    def check_collision(self, v1, v2, time_horizon=3.0,
                        signal1=None, signal2=None):
        for p1 in self._variants(v1):
            for p2 in self._variants(v2):
                if self.inner.check_collision(p1, p2, time_horizon,
                                              signal1=signal1, signal2=signal2):
                    return True
        return False


def make_phantoms(road, order, geometry):
    """Three hypothesis vehicles (one per signal), used only for path/position
    prediction inside PerceptionDetector — never stepped by the simulation."""
    return [RealityVehicle(road, sig, order, geometry) for sig in SIGNALS]


# ─────────────────────────────────────────────────────────────────────────────
# Scenario generation (identical ordering to benchmark_permutations.py)
# ─────────────────────────────────────────────────────────────────────────────

def generate_scenarios():
    scenarios = []
    for k in range(1, 5):
        for road_combo in itertools.combinations(ROADS, k):
            for signal_combo in itertools.product(SIGNALS, repeat=k):
                for order_perm in itertools.permutations(range(1, k + 1)):
                    scenarios.append(list(zip(road_combo, signal_combo, order_perm)))
    return scenarios


def stratified_sample():
    all_scen = generate_scenarios()
    by_n = {2: [], 3: [], 4: []}
    for idx, s in enumerate(all_scen):
        if len(s) in by_n:
            by_n[len(s)].append((idx, s))
    rng = random.Random(SEED)
    sample = list(by_n[2])                                   # all 108
    sample += rng.sample(by_n[3], min(N_SAMPLE_3V, len(by_n[3])))
    sample += rng.sample(by_n[4], min(N_SAMPLE_4V, len(by_n[4])))
    return sample


# ─────────────────────────────────────────────────────────────────────────────
# Single scenario runner
# ─────────────────────────────────────────────────────────────────────────────

def run_scenario(AlgClass, configs, scenario_id,
                 intent_p=0.0, reaction=None, ring_speed=None, fair=False):
    """Run one scenario under one algorithm with the given reality knobs.

    reaction: None | float (uniform fixed delay) | ("jitter", lo, hi)
    Returns (clearance_time, completed_all, min_distance_m).
    Per-vehicle random draws are seeded by (scenario_id, order) so the same
    vehicle gets the same draw in every algorithm and at every sweep point.
    """
    geometry = FourWayGeometry()
    use_rb = AlgClass is RoundaboutAlgorithm
    alg = AlgClass(geometry)

    variant_map = {}
    for road, sig, order in configs:
        vrng = random.Random(scenario_id * 100 + order)
        unsignaled = intent_p > 0.0 and vrng.random() < intent_p
        delay = 0.0
        if reaction is not None:
            if isinstance(reaction, tuple):
                _, lo, hi = reaction
                delay = vrng.uniform(lo, hi)
            else:
                delay = float(reaction)
        if fair:
            zone_cap = FAIR_CAP_RING if use_rb else FAIR_CAP_4WAY[sig]
        else:
            zone_cap = ring_speed if use_rb else None
        v = RealityVehicle(road, sig, order, geometry,
                           use_roundabout_paths=use_rb,
                           reaction_delay=delay,
                           observed_signal=("L" if unsignaled else None),
                           ring_speed=None)
        if zone_cap is not None:
            # Instance attribute shadows the class INTERSECTION_SPEED; the
            # kinematic predictor reads the same attribute, so prediction
            # stays consistent with behavior.
            v.INTERSECTION_SPEED = zone_cap
        alg.add_vehicle(v)
        if unsignaled and not use_rb:
            variant_map[id(v)] = make_phantoms(road, order, geometry)

    if variant_map and hasattr(alg, 'collision_detector'):
        alg.collision_detector = PerceptionDetector(alg.collision_detector,
                                                    variant_map)

    n_vehicles = len(configs)
    min_dist_m = float('inf')

    for _ in range(MAX_STEPS):
        status = alg.step(DT)

        # Track realized minimum inter-vehicle distance among moving vehicles
        # (safety observable — did margins actually hold under this knob?).
        actives = getattr(alg, 'active_vehicles', None)
        if actives is None:
            av = getattr(alg, 'active_vehicle', None)
            actives = [av] if av else []
        moving = [v for v in actives if v.active]
        for i in range(len(moving)):
            for j in range(i + 1, len(moving)):
                a, b = moving[i], moving[j]
                d = math.hypot(a.state.x - b.state.x,
                               a.state.y - b.state.y) * METERS_PER_UNIT
                if d < min_dist_m:
                    min_dist_m = d

        if status['waiting'] == 0 and status['active'] == 0:
            break

    m = alg.get_metrics()
    completed = m.get('completed_vehicles', 0) == n_vehicles
    return m.get('total_time', 0.0), completed, min_dist_m


# ─────────────────────────────────────────────────────────────────────────────
# Sweep driver
# ─────────────────────────────────────────────────────────────────────────────

ALG_MAP = {
    'Traditional': TraditionalStopAlgorithm,
    'Roundabout':  RoundaboutAlgorithm,
    'SmartStop':   PathBasedSmartStopAlgorithm,
}


def run_sweeps(sample, out_csv="reality_sweeps_results.csv"):
    rows = []
    t0 = time.time()

    def record(sweep, value, alg_name, sid, configs, **knobs):
        tt, ok, md = run_scenario(ALG_MAP[alg_name], configs, sid, **knobs)
        rows.append(dict(
            sweep=sweep, value=value, algorithm=alg_name,
            scenario_id=sid, n_vehicles=len(configs),
            total_time=round(tt, 2), completed=int(ok),
            min_dist_m=(round(md, 2) if md != float('inf') else ''),
        ))

    n = len(sample)
    for i, (sid, configs) in enumerate(sample):
        # Baseline (current model, no reality knobs)
        for alg in ('Traditional', 'Roundabout', 'SmartStop'):
            record('baseline', 0, alg, sid, configs)
        # Intent sweep (SmartStop only — Traditional/Roundabout ignore signals)
        for p in INTENT_LEVELS:
            record('intent', p, 'SmartStop', sid, configs, intent_p=p)
        # Reaction sweep (all algorithms — everyone has human drivers)
        for tau in REACTION_LEVELS:
            for alg in ('Traditional', 'Roundabout', 'SmartStop'):
                record('reaction', tau, alg, sid, configs, reaction=tau)
        for alg in ('Traditional', 'Roundabout', 'SmartStop'):
            record('reaction', 'jitter', alg, sid, configs, reaction=REACTION_JITTER)
        # Ring-speed sweep (Roundabout only; compared against baseline SmartStop)
        for rs in RING_SPEEDS:
            record('ring_speed', rs, 'Roundabout', sid, configs, ring_speed=rs)

        if (i + 1) % 20 == 0 or i == n - 1:
            el = time.time() - t0
            print(f"  [{i+1}/{n}] scenarios done, {el:.0f}s elapsed "
                  f"(~{el/(i+1)*(n-i-1):.0f}s remaining)", flush=True)

    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {out_csv} ({len(rows)} rows)")
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Aggregation
# ─────────────────────────────────────────────────────────────────────────────

def _index(rows):
    idx = {}
    for r in rows:
        idx[(r['sweep'], str(r['value']), r['algorithm'], r['scenario_id'])] = r
    return idx


def _mean_saving(rows, idx, sweep, value, alg, base_sweep, base_value, base_alg):
    """Mean per-scenario % time saving of (sweep,value,alg) vs the paired
    baseline run, over scenarios where both completed."""
    savings, n_v = [], {}
    for r in rows:
        if (r['sweep'], str(r['value']), r['algorithm']) != (sweep, str(value), alg):
            continue
        b = idx.get((base_sweep, str(base_value), base_alg, r['scenario_id']))
        if not b or not r['completed'] or not b['completed']:
            continue
        bt, rt = float(b['total_time']), float(r['total_time'])
        if bt > 0:
            savings.append((bt - rt) / bt * 100)
            n_v.setdefault(r['n_vehicles'], []).append((bt - rt) / bt * 100)
    if not savings:
        return None, {}
    return sum(savings) / len(savings), {k: sum(v)/len(v) for k, v in sorted(n_v.items())}


def _min_dist_stats(rows, sweep, value, alg):
    ds = [float(r['min_dist_m']) for r in rows
          if (r['sweep'], str(r['value']), r['algorithm']) == (sweep, str(value), alg)
          and r['min_dist_m'] != '' and r['completed']]
    if not ds:
        return None, None
    return min(ds), sum(1 for d in ds if d < 3.5)


def summarize(rows):
    idx = _index(rows)
    print("\n" + "=" * 74)
    print("REALITY SWEEPS — SUMMARY")
    print("=" * 74)

    # Baseline sanity check vs known benchmark numbers
    ss_v_tr, by_n = _mean_saving(rows, idx, 'baseline', 0, 'SmartStop',
                                 'baseline', 0, 'Traditional')
    ss_v_rb, _ = _mean_saving(rows, idx, 'baseline', 0, 'SmartStop',
                              'baseline', 0, 'Roundabout')
    print(f"\nBASELINE (sanity check vs ANALYSIS_REPORT ~58%/+20%):")
    print(f"  SmartStop vs Traditional: {ss_v_tr:+.1f}%   by n: "
          + "  ".join(f"{k}v={v:+.1f}%" for k, v in by_n.items()))
    print(f"  SmartStop vs Roundabout:  {ss_v_rb:+.1f}%")

    print(f"\nINTENT SWEEP — p% of drivers unsignaled (controller assumes L):")
    print(f"  {'p':>6} | {'SS vs Trad':>11} | {'SS vs RB':>9} | {'SS vs SS-baseline':>18}")
    for p in INTENT_LEVELS:
        vt, _ = _mean_saving(rows, idx, 'intent', p, 'SmartStop',
                             'baseline', 0, 'Traditional')
        vr, _ = _mean_saving(rows, idx, 'intent', p, 'SmartStop',
                             'baseline', 0, 'Roundabout')
        vs, _ = _mean_saving(rows, idx, 'intent', p, 'SmartStop',
                             'baseline', 0, 'SmartStop')
        print(f"  {p:>6.2f} | {vt:>+10.1f}% | {vr:>+8.1f}% | {vs:>+17.1f}%")

    print(f"\nREACTION SWEEP — perception-reaction delay applied to ALL algorithms:")
    print(f"  {'tau':>6} | {'SS vs Trad':>11} | {'SS vs RB':>9} | "
          f"{'SS min-dist (m)':>15} | {'runs < 3.5 m':>12}")
    for tau in REACTION_LEVELS + ['jitter']:
        vt, _ = _mean_saving(rows, idx, 'reaction', tau, 'SmartStop',
                             'reaction', tau, 'Traditional')
        vr, _ = _mean_saving(rows, idx, 'reaction', tau, 'SmartStop',
                             'reaction', tau, 'Roundabout')
        mn, nv = _min_dist_stats(rows, 'reaction', tau, 'SmartStop')
        mn_s = f"{mn:.2f}" if mn is not None else "n/a"
        print(f"  {str(tau):>6} | {vt:>+10.1f}% | {vr:>+8.1f}% | {mn_s:>15} | {nv:>12}")
    mn0, nv0 = _min_dist_stats(rows, 'baseline', 0, 'SmartStop')
    print(f"  (baseline SS min-dist for reference: {mn0:.2f} m, {nv0} runs < 3.5 m)")

    print(f"\nRING-SPEED SWEEP — roundabout circulating at real-world speeds")
    print(f"  (baseline SmartStop vs fair Roundabout; current model uses 2.0 m/s):")
    print(f"  {'ring m/s':>8} | {'SS advantage vs RB':>18}")
    for rs in RING_SPEEDS:
        # SS baseline vs RB at ring speed rs: saving of SS relative to RB run
        savings = []
        for r in rows:
            if (r['sweep'], str(r['value']), r['algorithm']) != ('ring_speed', str(rs), 'Roundabout'):
                continue
            s = idx.get(('baseline', '0', 'SmartStop', r['scenario_id']))
            if not s or not r['completed'] or not s['completed']:
                continue
            rt, st = float(r['total_time']), float(s['total_time'])
            if rt > 0:
                savings.append((rt - st) / rt * 100)
        adv = sum(savings) / len(savings) if savings else float('nan')
        print(f"  {rs:>8.1f} | {adv:>+17.1f}%")

    print("\n" + "=" * 74)


def run_fair_physics(sample, out_csv="reality_fair_results.csv"):
    """Symmetric curvature-fair physics: all three algorithms, same sample.
    Answers: with both modes at physically honest speeds (and the roundabout
    still handicapped by dead-stop entry), who wins?"""
    rows = []
    t0 = time.time()
    n = len(sample)
    for i, (sid, configs) in enumerate(sample):
        for alg in ('Traditional', 'Roundabout', 'SmartStop'):
            tt, ok, md = run_scenario(ALG_MAP[alg], configs, sid, fair=True)
            rows.append(dict(
                sweep='fair', value='curvature', algorithm=alg,
                scenario_id=sid, n_vehicles=len(configs),
                total_time=round(tt, 2), completed=int(ok),
                min_dist_m=(round(md, 2) if md != float('inf') else ''),
            ))
        if (i + 1) % 40 == 0 or i == n - 1:
            el = time.time() - t0
            print(f"  [{i+1}/{n}] {el:.0f}s elapsed", flush=True)

    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {out_csv} ({len(rows)} rows)")

    idx = _index(rows)
    vt, by_n_t = _mean_saving(rows, idx, 'fair', 'curvature', 'SmartStop',
                              'fair', 'curvature', 'Traditional')
    vr, by_n_r = _mean_saving(rows, idx, 'fair', 'curvature', 'SmartStop',
                              'fair', 'curvature', 'Roundabout')
    mn, nv = _min_dist_stats(rows, 'fair', 'curvature', 'SmartStop')
    print("\n" + "=" * 74)
    print("CURVATURE-FAIR PHYSICS — symmetric speed model, RB still dead-stop entry")
    print("=" * 74)
    print(f"  SmartStop vs Traditional: {vt:+.1f}%   by n: "
          + "  ".join(f"{k}v={v:+.1f}%" for k, v in by_n_t.items()))
    print(f"  SmartStop vs Roundabout:  {vr:+.1f}%   by n: "
          + "  ".join(f"{k}v={v:+.1f}%" for k, v in by_n_r.items()))
    print(f"  SmartStop min-dist: {mn:.2f} m ({nv} completed runs < 3.5 m)")
    # Win/loss/tie counts vs Roundabout
    wins = losses = ties = 0
    for r in rows:
        if r['algorithm'] != 'SmartStop' or not r['completed']:
            continue
        b = idx.get(('fair', 'curvature', 'Roundabout', r['scenario_id']))
        if not b or not b['completed']:
            continue
        d = float(b['total_time']) - float(r['total_time'])
        if d > 0.15: wins += 1
        elif d < -0.15: losses += 1
        else: ties += 1
    tot = wins + losses + ties
    print(f"  Head-to-head vs Roundabout: SS wins {wins}/{tot} "
          f"({wins/tot*100:.0f}%), loses {losses}/{tot} ({losses/tot*100:.0f}%), "
          f"ties {ties}/{tot}")
    print("=" * 74)
    return rows


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--fair" in sys.argv:
        sample = stratified_sample()
        print(f"Curvature-fair physics run: {len(sample)} scenarios × 3 algorithms")
        run_fair_physics(sample)
        sys.exit(0)

    smoke = "--smoke" in sys.argv
    sample = stratified_sample()
    if smoke:
        sample = sample[:6] + sample[-6:]   # a few 2v + a few 4v
        print(f"SMOKE TEST: {len(sample)} scenarios")
    else:
        counts = {}
        for _, s in sample:
            counts[len(s)] = counts.get(len(s), 0) + 1
        print(f"Full sweep: {len(sample)} scenarios "
              f"({', '.join(f'{v}x{k}-vehicle' for k, v in sorted(counts.items()))})")
        print(f"Sweep points per scenario: 3 baseline + {len(INTENT_LEVELS)} intent + "
              f"{3 * (len(REACTION_LEVELS) + 1)} reaction + {len(RING_SPEEDS)} ring = "
              f"{3 + len(INTENT_LEVELS) + 3 * (len(REACTION_LEVELS) + 1) + len(RING_SPEEDS)} runs")

    out = "reality_sweeps_smoke.csv" if smoke else "reality_sweeps_results.csv"
    rows = run_sweeps(sample, out_csv=out)
    summarize(rows)

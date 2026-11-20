#!/usr/bin/env python3
"""
Zone-Based vs TurnAware Collision Detection Comparison
=======================================================
Compares the original geometry-based "no-go zone" approach against the current
TurnAwareCollisionDetector across every ordered permutation of 0-1 car per approach.

Original zone logic (as described):
  When deciding whether to activate car B, check every currently active car A.
  If A's position lies inside the danger zone defined for B's approach, block B.
  Danger zones are rectangular regions from FourWayGeometry.danger_zones.

Current logic (TurnAwareCollisionDetector):
  Five signal-aware rules that explicitly model turn geometries:
  1. Parallel straights (MainE↔MainW or GreenN↔GreenS) → Safe
  2. R + R from perpendicular approaches → Safe
  3. R + NS/S from perpendicular, same exit arm → Block
  4. R + NS/S from perpendicular, different exit arms → Safe
  5. All others → standard distance check (3.0m horizon)

For the analytical comparison we check, for every (road_A, signal_A) vs
(road_B, signal_B) pair:
  • Does path A ever pass through road_B's danger zone?  (zone would block B)
  • Does path B ever pass through road_A's danger zone?  (zone would block A)
  • What does TurnAware say when A is active and B is waiting?

We also run both algorithms (ZoneBasedSmartStop vs TurnAwareSmartStop) on every
permutation scenario and compare completion times to quantify the throughput
impact.
"""

import itertools, csv, os, sys, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from config import OUTPUT_DIR
from path_based_smart_stop import (
    PathBasedVehicle, FourWayGeometry,
    TraditionalStopAlgorithm, PathBasedSmartStopAlgorithm,
)
from turn_aware_collision import TurnAwareCollisionDetector

ROADS   = ['Main E', 'Main W', 'Green N', 'Green S']
SIGNALS = ['R', 'L', 'NS/S']
MAX_STEPS = 1500


# ─────────────────────────────────────────────────────────────────────────────
# Zone-based collision detector (original approach)
# ─────────────────────────────────────────────────────────────────────────────

class ZoneBasedCollisionDetector:
    """
    Original rectangular no-go zone check.
    Blocks approach B if any active vehicle's position lies within B's danger zone.
    """
    def __init__(self, geometry: FourWayGeometry):
        self.geometry = geometry

    def is_approach_blocked(self, waiting_road: str, active_vehicles: list) -> bool:
        xmin, xmax, ymin, ymax = self.geometry.get_danger_zone(waiting_road)
        for v in active_vehicles:
            x, y = v.state.x, v.state.y
            if xmin <= x <= xmax and ymin <= y <= ymax:
                return True
        return False


class ZoneBasedSmartStopAlgorithm:
    """
    Smart Stop algorithm using the original zone-based collision check
    instead of TurnAwareCollisionDetector.  Keeps backward-priority scoring
    and simultaneous activation logic identical; only the safety gate differs.
    """

    def __init__(self, geometry: FourWayGeometry):
        self.geometry       = geometry
        self.zone_detector  = ZoneBasedCollisionDetector(geometry)
        self.active_vehicles  = []
        self.waiting_vehicles = []
        self.completed_vehicles = []
        self.current_time   = 0.0
        self.approach_positions = {
            'Main W': 0, 'Green N': 1, 'Main E': 2, 'Green S': 3
        }

    def add_vehicle(self, vehicle):
        self.waiting_vehicles.append(vehicle)
        self.waiting_vehicles.sort(key=lambda v: v.order)

    def step(self, dt=0.1):
        self.current_time += dt
        for v in self.active_vehicles[:]:
            if not v.update(dt):  # Speed-by-zone (M2 fix)
                self.active_vehicles.remove(v)
                self.completed_vehicles.append(v)

        if not self.active_vehicles and self.waiting_vehicles:
            first = self.waiting_vehicles.pop(0)
            first.activate(self.current_time)
            self.active_vehicles.append(first)

        if self.waiting_vehicles:
            self._try_activate()

        return dict(
            time=self.current_time,
            active=len(self.active_vehicles),
            waiting=len(self.waiting_vehicles),
            completed=len(self.completed_vehicles),
        )

    def _try_activate(self):
        active_positions = {
            self.approach_positions[v.road_name]
            for v in self.active_vehicles
            if v.road_name in self.approach_positions
        }
        # Phase 2A: per-approach FIFO — only the front car per approach
        # is a candidate.  waiting_vehicles is already sorted by `order`.
        heads = {}
        for w in self.waiting_vehicles:
            if w.road_name in self.approach_positions and w.road_name not in heads:
                heads[w.road_name] = w
        candidates = []
        for w in heads.values():
            wp = self.approach_positions[w.road_name]
            # Backward priority score
            score = 0
            for ap in active_positions:
                diff = (ap - wp) % 4
                if diff in (1, 2):
                    score += diff
            # Zone-based safety check
            if self.zone_detector.is_approach_blocked(w.road_name, self.active_vehicles):
                continue
            candidates.append((w, score))

        candidates.sort(key=lambda x: -x[1])
        for w, _ in candidates:
            if self.zone_detector.is_approach_blocked(w.road_name, self.active_vehicles):
                continue
            if len(self.active_vehicles) < 4:
                self.waiting_vehicles.remove(w)
                w.activate(self.current_time)
                self.active_vehicles.append(w)

    def get_metrics(self):
        # Phase 2C: intersection-clearance time (see PathBasedSmartStop docstring).
        all_v = self.active_vehicles + self.completed_vehicles
        if not all_v:
            return dict(total_time=0, avg_wait_time=0, throughput=0,
                        completed_vehicles=0)
        exit_times  = [v.intersection_exit_time for v in all_v
                       if v.intersection_exit_time is not None]
        start_times = [v.start_time   for v in all_v if v.start_time is not None]
        total_time  = max(exit_times) if exit_times else (
            max(v.current_time for v in all_v if v.start_time is not None)
            if start_times else 0
        )
        avg_wait    = sum(start_times) / len(start_times) if start_times else 0
        return dict(
            total_time=total_time,
            avg_wait_time=avg_wait,
            throughput=len(self.completed_vehicles) / total_time if total_time else 0,
            completed_vehicles=len(self.completed_vehicles),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Scenario generation (same as benchmark)
# ─────────────────────────────────────────────────────────────────────────────

def generate_scenarios():
    scenarios = [[]]
    for k in range(1, 5):
        for road_combo in itertools.combinations(ROADS, k):
            for signal_combo in itertools.product(SIGNALS, repeat=k):
                for order_perm in itertools.permutations(range(1, k + 1)):
                    scenarios.append(list(zip(road_combo, signal_combo, order_perm)))
    return scenarios


def run_algo_fast(AlgClass, cfg, geometry, use_roundabout=False):
    alg = AlgClass(geometry)
    for road, signal, order in cfg:
        v = PathBasedVehicle(road, signal, order, geometry,
                             use_roundabout_paths=use_roundabout)
        alg.add_vehicle(v)
    for _ in range(MAX_STEPS):
        s = alg.step(0.1)
        if s['waiting'] == 0 and s['active'] == 0:
            break
    return alg.get_metrics()['total_time']


# ─────────────────────────────────────────────────────────────────────────────
# Pairwise analytical comparison
# ─────────────────────────────────────────────────────────────────────────────

def path_enters_zone(path_x, path_y, zone):
    xmin, xmax, ymin, ymax = zone
    for x, y in zip(path_x, path_y):
        if xmin <= x <= xmax and ymin <= y <= ymax:
            return True
    return False


def build_pairwise_matrix(geometry):
    """
    For every (road_A, signal_A) vs (road_B, signal_B) pair build:
      zone_blocks_B: does path_A enter road_B's danger zone?
      zone_blocks_A: does path_B enter road_A's danger zone?
      ta_blocks:     does TurnAware say conflict exists?
    """
    ta = TurnAwareCollisionDetector(safety_margin=3.0)
    combos = [(r, s) for r in ROADS for s in SIGNALS]
    pairs  = []

    for (rA, sA), (rB, sB) in itertools.combinations(combos, 2):
        if rA == rB:
            continue  # same approach, not relevant

        vA = PathBasedVehicle(rA, sA, 1, geometry)
        vB = PathBasedVehicle(rB, sB, 2, geometry)

        zone_A = geometry.get_danger_zone(rA)
        zone_B = geometry.get_danger_zone(rB)

        # Zone check: does path_A enter zone_B? (would block B while A active)
        zone_a_blocks_b = path_enters_zone(vA.path_x, vA.path_y, zone_B)
        # Zone check: does path_B enter zone_A? (would block A while B active)
        zone_b_blocks_a = path_enters_zone(vB.path_x, vB.path_y, zone_A)

        # TurnAware check: activate A, check if B would be blocked
        vA.activate(0.0)
        ta_says_conflict = ta.check_collision(vB, vA)

        pairs.append(dict(
            road_A=rA, signal_A=sA,
            road_B=rB, signal_B=sB,
            zone_a_blocks_b=zone_a_blocks_b,
            zone_b_blocks_a=zone_b_blocks_a,
            zone_any_block=zone_a_blocks_b or zone_b_blocks_a,
            ta_conflict=ta_says_conflict,
        ))

    return pairs


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    geometry  = FourWayGeometry()
    scenarios = generate_scenarios()

    # ── Part A: Pairwise analytical matrix ───────────────────────────────────
    print("=" * 70)
    print("PART A — Pairwise Signal-Pair Analysis (Zone vs TurnAware)")
    print("=" * 70)

    pairs = build_pairwise_matrix(geometry)
    total_pairs = len(pairs)

    # Agreement/disagreement counts
    both_block   = [p for p in pairs if p['zone_any_block'] and p['ta_conflict']]
    zone_only    = [p for p in pairs if p['zone_any_block'] and not p['ta_conflict']]
    ta_only      = [p for p in pairs if not p['zone_any_block'] and p['ta_conflict']]
    both_allow   = [p for p in pairs if not p['zone_any_block'] and not p['ta_conflict']]

    print(f"\n  Total unique signal pairs: {total_pairs}")
    print(f"  Both block (agree — conflict):   {len(both_block):>4}  "
          f"({100*len(both_block)/total_pairs:.1f}%)")
    print(f"  Both allow (agree — safe):       {len(both_allow):>4}  "
          f"({100*len(both_allow)/total_pairs:.1f}%)")
    print(f"  Zone blocks, TurnAware allows    {len(zone_only):>4}  "
          f"({100*len(zone_only)/total_pairs:.1f}%)  ← Zone false positives (overly conservative)")
    print(f"  TurnAware blocks, Zone allows    {len(ta_only):>4}  "
          f"({100*len(ta_only)/total_pairs:.1f}%)  ← Zone false negatives (safety gaps)")

    print(f"\n  ZONE FALSE POSITIVES (Zone would block a pair TurnAware deems safe):")
    for p in zone_only:
        print(f"    {p['road_A']:7} {p['signal_A']:5} ←→ {p['road_B']:7} {p['signal_B']:5}"
              f"  zone_A_blocks_B={p['zone_a_blocks_b']}  zone_B_blocks_A={p['zone_b_blocks_a']}")

    print(f"\n  ZONE FALSE NEGATIVES (Zone would allow a pair TurnAware blocks):")
    for p in ta_only:
        print(f"    {p['road_A']:7} {p['signal_A']:5} ←→ {p['road_B']:7} {p['signal_B']:5}")

    # Save pairwise CSV
    pairwise_csv = os.path.join(OUTPUT_DIR, 'zone_pairwise_comparison.csv')
    with open(pairwise_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=pairs[0].keys())
        writer.writeheader()
        writer.writerows(pairs)
    print(f"\n  Pairwise CSV → {pairwise_csv}")

    # ── Part B: Full scenario simulation comparison ───────────────────────────
    print("\n" + "=" * 70)
    print("PART B — Full Scenario Simulation: Zone vs TurnAware Smart Stop")
    print("=" * 70)

    non_empty = [s for s in scenarios if s]
    rows = []
    t0 = time.time()

    print(f"\nRunning {len(non_empty)} non-empty scenarios × 2 algorithms ...")
    for idx, cfg in enumerate(non_empty):
        if idx % 300 == 0 and idx > 0:
            eta = (time.time() - t0) / idx * (len(non_empty) - idx)
            print(f"  {idx:>4}/{len(non_empty)}  —  "
                  f"{time.time()-t0:.0f}s elapsed, ~{eta:.0f}s remaining")

        ss_t  = run_algo_fast(PathBasedSmartStopAlgorithm, cfg, geometry)
        zb_t  = run_algo_fast(ZoneBasedSmartStopAlgorithm, cfg, geometry)

        rows.append(dict(
            num_vehicles=len(cfg),
            roads='|'.join(r for r,s,o in cfg),
            signals='|'.join(s for r,s,o in cfg),
            order='|'.join(str(o) for r,s,o in cfg),
            ss_time=round(ss_t, 3),
            zone_time=round(zb_t, 3),
            delta=round(zb_t - ss_t, 3),   # positive = zone is slower
        ))

    print(f"✅ Done in {time.time()-t0:.1f}s")

    sim_csv = os.path.join(OUTPUT_DIR, 'zone_simulation_comparison.csv')
    with open(sim_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV → {sim_csv}\n")

    # Summary stats
    total = len(rows)
    zone_slower  = [r for r in rows if r['delta'] > 0.15]
    zone_faster  = [r for r in rows if r['delta'] < -0.15]
    tied         = [r for r in rows if abs(r['delta']) <= 0.15]
    avg_delta    = sum(r['delta'] for r in rows) / total

    print("── Summary: Zone-Based vs TurnAware Smart Stop ─────────────────────")
    print(f"  Zone SLOWER than TurnAware:  {len(zone_slower):>4} / {total}  "
          f"({100*len(zone_slower)/total:.1f}%)  — conservative false positives")
    print(f"  Zone FASTER than TurnAware:  {len(zone_faster):>4} / {total}  "
          f"({100*len(zone_faster)/total:.1f}%)  — zone allows unsafe pairs")
    print(f"  Essentially tied (≤0.15s):   {len(tied):>4} / {total}  "
          f"({100*len(tied)/total:.1f}%)")
    print(f"  Average delta (zone−TA):     {avg_delta:+.3f}s  "
          f"({'zone slower' if avg_delta>0 else 'zone faster'})")

    # By vehicle count
    print(f"\n  Delta by vehicle count:")
    by_n = defaultdict(list)
    for r in rows:
        by_n[r['num_vehicles']].append(r['delta'])
    for n in sorted(by_n):
        vals = by_n[n]
        print(f"    n={n}: avg delta={sum(vals)/len(vals):+.3f}s  "
              f"max={max(vals):+.3f}s  min={min(vals):+.3f}s  "
              f"(zone slower in {sum(1 for v in vals if v>0.15)} / {len(vals)})")

    if zone_slower:
        zone_slower.sort(key=lambda r: -r['delta'])
        print(f"\n  Worst zone throughput losses vs TurnAware (top 10):")
        for r in zone_slower[:10]:
            print(f"    Δ={r['delta']:+.2f}s  n={r['num_vehicles']}  "
                  f"roads={r['roads']}  signals={r['signals']}")

    if zone_faster:
        zone_faster.sort(key=lambda r: r['delta'])
        print(f"\n  Cases where Zone is faster (TurnAware may be over-blocking, top 5):")
        for r in zone_faster[:5]:
            print(f"    Δ={r['delta']:+.2f}s  n={r['num_vehicles']}  "
                  f"roads={r['roads']}  signals={r['signals']}")

    print("\n" + "=" * 70)
    print("Zone comparison complete.")


if __name__ == '__main__':
    main()

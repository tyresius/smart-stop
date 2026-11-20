#!/usr/bin/env python3
"""
Full Permutation Efficiency Benchmark
======================================
Runs every ordered combination of 0–1 car per approach (0–4 vehicles total)
across all 4 algorithms and writes results to CSV + printed analysis.

Permutation space:
  4 approaches × {no car | R | L | NS/S} = 4 states each
  Ordered → sum_{k=0}^{4} C(4,k) × 3^k × k!  =  2,713 scenarios
"""

import itertools, csv, os, sys, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from config import OUTPUT_DIR
from path_based_smart_stop import (
    PathBasedVehicle, FourWayGeometry,
    TraditionalStopAlgorithm, RoundaboutAlgorithm,
    PathBasedSmartStopAlgorithm, SmartStopSafeAlgorithm,
)

ROADS   = ['Main E', 'Main W', 'Green N', 'Green S']
SIGNALS = ['R', 'L', 'NS/S']
MAX_STEPS = 1500   # 150 sim-seconds safety ceiling


# ─────────────────────────────────────────────────────────────────────────────
# Scenario generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_scenarios():
    """Return list of vehicle configs [(road, signal, order), ...]"""
    scenarios = [[] ]  # empty scenario first
    for k in range(1, 5):
        for road_combo in itertools.combinations(ROADS, k):
            for signal_combo in itertools.product(SIGNALS, repeat=k):
                for order_perm in itertools.permutations(range(1, k + 1)):
                    scenarios.append(list(zip(road_combo, signal_combo, order_perm)))
    return scenarios


# ─────────────────────────────────────────────────────────────────────────────
# Fast simulation runner (no animation data)
# ─────────────────────────────────────────────────────────────────────────────

def run_algo(AlgClass, vehicle_configs, geometry, use_roundabout=False):
    alg = AlgClass(geometry)
    for road, signal, order in vehicle_configs:
        v = PathBasedVehicle(road, signal, order, geometry,
                             use_roundabout_paths=use_roundabout)
        alg.add_vehicle(v)
    for _ in range(MAX_STEPS):
        s = alg.step(0.1)
        if s['waiting'] == 0 and s['active'] == 0:
            break
    m = alg.get_metrics()
    return m['total_time'], m.get('avg_wait_time', 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# Main benchmark loop
# ─────────────────────────────────────────────────────────────────────────────

def main():
    scenarios = generate_scenarios()
    print(f"Scenarios to run: {len(scenarios)}  ×  4 algorithms  =  "
          f"{len(scenarios) * 4:,} simulations")

    geometry = FourWayGeometry()
    rows = []
    t0 = time.time()

    for idx, cfg in enumerate(scenarios):
        if idx % 250 == 0 and idx > 0:
            eta = (time.time() - t0) / idx * (len(scenarios) - idx)
            print(f"  {idx:>4}/{len(scenarios)}  —  {time.time()-t0:.0f}s elapsed, "
                  f"~{eta:.0f}s remaining")

        n = len(cfg)
        roads_str   = '|'.join(r for r, s, o in cfg)
        signals_str = '|'.join(s for r, s, o in cfg)
        order_str   = '|'.join(str(o) for r, s, o in cfg)

        if n == 0:
            rows.append(dict(scenario_id=idx, num_vehicles=0,
                             roads='', signals='', order='',
                             trad_time=0, trad_wait=0,
                             rb_time=0,   rb_wait=0,
                             ss_time=0,   ss_wait=0,
                             sf_time=0,   sf_wait=0))
            continue

        trad_t, trad_w = run_algo(TraditionalStopAlgorithm,   cfg, geometry)
        rb_t,   rb_w   = run_algo(RoundaboutAlgorithm,        cfg, geometry, True)
        ss_t,   ss_w   = run_algo(PathBasedSmartStopAlgorithm, cfg, geometry)
        sf_t,   sf_w   = run_algo(SmartStopSafeAlgorithm,     cfg, geometry)

        rows.append(dict(
            scenario_id=idx, num_vehicles=n,
            roads=roads_str, signals=signals_str, order=order_str,
            trad_time=round(trad_t, 3), trad_wait=round(trad_w, 3),
            rb_time=round(rb_t,  3),    rb_wait=round(rb_w,  3),
            ss_time=round(ss_t,  3),    ss_wait=round(ss_w,  3),
            sf_time=round(sf_t,  3),    sf_wait=round(sf_w,  3),
        ))

    elapsed = time.time() - t0
    print(f"\n✅ Benchmark complete in {elapsed:.1f}s")

    # ── Save CSV ──────────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUTPUT_DIR, 'permutation_benchmark.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV → {csv_path}\n")

    # ── Analysis ──────────────────────────────────────────────────────────────
    analyze(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────────────────────

def pct_faster(baseline, comparison):
    """% time saved by comparison vs baseline (positive = faster)."""
    if baseline == 0:
        return 0.0
    return (baseline - comparison) / baseline * 100.0


def analyze(rows):
    non_empty = [r for r in rows if r['num_vehicles'] > 0]
    total     = len(non_empty)

    print("=" * 70)
    print("EFFICIENCY ANALYSIS — Smart Stop vs Traditional & Roundabout")
    print("=" * 70)

    # ── 1. Overall averages by vehicle count ─────────────────────────────────
    print("\n── 1. Average time savings by vehicle count ──────────────────────")
    print(f"  {'N':>2}   {'Scenarios':>9}   {'SS vs Trad':>10}   "
          f"{'SS vs RB':>10}   {'SF vs Trad':>10}")
    print("  " + "-" * 55)
    by_n = defaultdict(list)
    for r in non_empty:
        by_n[r['num_vehicles']].append(r)
    for n in sorted(by_n):
        grp = by_n[n]
        avg_ss_trad = sum(pct_faster(r['trad_time'], r['ss_time']) for r in grp) / len(grp)
        avg_ss_rb   = sum(pct_faster(r['rb_time'],   r['ss_time']) for r in grp) / len(grp)
        avg_sf_trad = sum(pct_faster(r['trad_time'], r['sf_time']) for r in grp) / len(grp)
        print(f"  {n:>2}   {len(grp):>9}   {avg_ss_trad:>9.1f}%   "
              f"{avg_ss_rb:>9.1f}%   {avg_sf_trad:>9.1f}%")

    # ── 2. Overall average across all non-empty scenarios ────────────────────
    avg_all_ss  = sum(pct_faster(r['trad_time'], r['ss_time']) for r in non_empty) / total
    avg_all_rb  = sum(pct_faster(r['trad_time'], r['rb_time']) for r in non_empty) / total
    print(f"\n  Overall (all {total} scenarios):")
    print(f"    Smart Stop saves  {avg_all_ss:.1f}% vs Traditional")
    print(f"    Roundabout saves  {avg_all_rb:.1f}% vs Traditional")

    # ── 3. Cases where Smart Stop equals Traditional (no improvement possible) ─
    tie_ss = [r for r in non_empty if abs(r['ss_time'] - r['trad_time']) < 0.15]
    print(f"\n── 2. Scenarios where Smart Stop ≈ Traditional (no gain) ─────────")
    print(f"  Count: {len(tie_ss)} / {total} ({100*len(tie_ss)/total:.1f}%)")
    if tie_ss:
        sig_counts = defaultdict(int)
        for r in tie_ss:
            sig_counts[r['signals']] += 1
        top = sorted(sig_counts.items(), key=lambda x: -x[1])[:5]
        print("  Most common signal combos:")
        for sig, cnt in top:
            print(f"    {sig:<30}  ×{cnt}")

    # ── 4. Cases where Smart Stop underperforms Roundabout ───────────────────
    ss_worse_rb = [r for r in non_empty if r['ss_time'] > r['rb_time'] + 0.15]
    print(f"\n── 3. Scenarios where Smart Stop is SLOWER than Roundabout ───────")
    print(f"  Count: {len(ss_worse_rb)} / {total} ({100*len(ss_worse_rb)/total:.1f}%)")
    if ss_worse_rb:
        ss_worse_rb.sort(key=lambda r: r['ss_time'] - r['rb_time'], reverse=True)
        print("  Top 10 worst cases (SS lag vs RB):")
        for r in ss_worse_rb[:10]:
            lag = r['ss_time'] - r['rb_time']
            print(f"    Δ={lag:+.2f}s  n={r['num_vehicles']}  "
                  f"roads={r['roads']}  signals={r['signals']}")

    # ── 5. Cases where Smart Stop underperforms Smart Safe ───────────────────
    ss_worse_sf = [r for r in non_empty if r['ss_time'] > r['sf_time'] + 0.15]
    print(f"\n── 4. Scenarios where Smart Stop is SLOWER than Smart Safe ────────")
    print(f"  Count: {len(ss_worse_sf)} / {total} ({100*len(ss_worse_sf)/total:.1f}%)")

    # ── 6. Best-case gains ────────────────────────────────────────────────────
    print(f"\n── 5. Best-case Smart Stop gains vs Traditional ──────────────────")
    gains = [(pct_faster(r['trad_time'], r['ss_time']), i, r) for i, r in enumerate(non_empty)]
    gains.sort(reverse=True)
    print("  Top 10 scenarios (% time saved):")
    for pct, _, r in gains[:10]:
        print(f"    {pct:>5.1f}%  n={r['num_vehicles']}  "
              f"roads={r['roads']}  signals={r['signals']}")

    # ── 7. Order sensitivity: same combo, different arrival order ────────────
    print(f"\n── 6. Arrival-order sensitivity ──────────────────────────────────")
    # Group by (frozenset of (road,signal)) pairs
    combo_groups = defaultdict(list)
    for r in non_empty:
        roads_s = r['roads'].split('|')
        sigs_s  = r['signals'].split('|')
        key = tuple(sorted(zip(roads_s, sigs_s)))
        combo_groups[key].append(r)

    order_sensitive = []
    for key, grp in combo_groups.items():
        if len(grp) < 2:
            continue
        ss_times = [r['ss_time'] for r in grp]
        spread = max(ss_times) - min(ss_times)
        if spread > 0.2:
            order_sensitive.append((spread, key, grp))

    order_sensitive.sort(reverse=True)
    print(f"  Combos where arrival order changes Smart Stop time by >0.2s: "
          f"{len(order_sensitive)}")
    if order_sensitive:
        print("  Top 5 most order-sensitive scenarios:")
        for spread, key, grp in order_sensitive[:5]:
            ss_times = sorted(r['ss_time'] for r in grp)
            print(f"    Spread={spread:.2f}s  combo={key}  "
                  f"SS range=[{ss_times[0]:.2f}, {ss_times[-1]:.2f}]")

    # ── 8. Signal-type breakdown ──────────────────────────────────────────────
    print(f"\n── 7. Avg Smart Stop gain by single-vehicle signal type ──────────")
    singles = [r for r in non_empty if r['num_vehicles'] == 1]
    sig_perf = defaultdict(list)
    for r in singles:
        sig_perf[r['signals']].append(pct_faster(r['trad_time'], r['ss_time']))
    for sig in sorted(sig_perf):
        vals = sig_perf[sig]
        print(f"  {sig:<10}  avg gain={sum(vals)/len(vals):.1f}%  "
              f"(n={len(vals)})")

    print("\n" + "=" * 70)
    print("Analysis complete.")


if __name__ == '__main__':
    main()

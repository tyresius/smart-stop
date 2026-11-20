#!/usr/bin/env python3
"""
Comprehensive Performance Test
===============================

Tests Smart Stop with and without lane-aware collision detection
across multiple realistic scenarios to measure true performance impact.
"""

import sys
from path_based_smart_stop import (
    PathBasedVehicle, FourWayGeometry, PathBasedSmartStopAlgorithm,
    RoundaboutAlgorithm, TraditionalStopAlgorithm
)
from lane_aware_collision import SmartStopWithLaneAwareness

print("=" * 80)
print("COMPREHENSIVE PERFORMANCE COMPARISON")
print("=" * 80)
print("\nComparing:")
print("  1. Traditional Stop (baseline)")
print("  2. Roundabout")
print("  3. Smart Stop (ORIGINAL - distance-based collision)")
print("  4. Smart Stop (FIXED - lane-aware collision)")
print()


def run_scenario(name, vehicle_configs):
    """Run all algorithms on a scenario"""
    print("\n" + "=" * 80)
    print(f"SCENARIO: {name}")
    print("=" * 80)

    geometry = FourWayGeometry()

    results = {}

    # 1. Traditional Stop
    print("\n1. Traditional Stop...")
    trad = TraditionalStopAlgorithm(geometry)
    for road, signal, order in vehicle_configs:
        v = PathBasedVehicle(road, signal, order, geometry)
        trad.add_vehicle(v)

    for step in range(1000):
        status = trad.step(0.1)
        if status['waiting'] == 0 and status['active'] == 0:
            break

    results['Traditional'] = trad.get_metrics()
    print(f"   Time: {results['Traditional']['total_time']:.2f}s")

    # 2. Roundabout
    print("\n2. Roundabout...")
    rb = RoundaboutAlgorithm(geometry)
    for road, signal, order in vehicle_configs:
        v = PathBasedVehicle(road, signal, order, geometry, use_roundabout_paths=True)
        rb.add_vehicle(v)

    for step in range(1000):
        status = rb.step(0.1)
        if status['waiting'] == 0 and status['active'] == 0:
            break

    results['Roundabout'] = rb.get_metrics()
    print(f"   Time: {results['Roundabout']['total_time']:.2f}s")

    # 3. Smart Stop (Original)
    print("\n3. Smart Stop (Original - distance-based)...")
    ss_orig = PathBasedSmartStopAlgorithm(geometry)
    for road, signal, order in vehicle_configs:
        v = PathBasedVehicle(road, signal, order, geometry)
        ss_orig.add_vehicle(v)

    for step in range(1000):
        status = ss_orig.step(0.1)
        if status['waiting'] == 0 and status['active'] == 0:
            break

    results['Smart Stop (Original)'] = ss_orig.get_metrics()
    print(f"   Time: {results['Smart Stop (Original)']['total_time']:.2f}s")

    # 4. Smart Stop (Fixed - Lane-Aware)
    print("\n4. Smart Stop (FIXED - lane-aware)...")
    ss_fixed = SmartStopWithLaneAwareness(geometry)
    for road, signal, order in vehicle_configs:
        v = PathBasedVehicle(road, signal, order, geometry)
        ss_fixed.add_vehicle(v)

    for step in range(1000):
        status = ss_fixed.step(0.1)
        if status['waiting'] == 0 and status['active'] == 0:
            break

    results['Smart Stop (Fixed)'] = ss_fixed.get_metrics()
    print(f"   Time: {results['Smart Stop (Fixed)']['total_time']:.2f}s")

    # Print comparison
    print("\n" + "-" * 80)
    print(f"{'Algorithm':<30} {'Time (s)':<12} {'vs Traditional':<15} {'vs Roundabout':<15}")
    print("-" * 80)

    trad_time = results['Traditional']['total_time']
    rb_time = results['Roundabout']['total_time']

    for alg_name, metrics in results.items():
        time = metrics['total_time']

        vs_trad = ((trad_time - time) / trad_time * 100) if trad_time > 0 else 0
        vs_rb = ((rb_time - time) / rb_time * 100) if rb_time > 0 else 0

        print(f"{alg_name:<30} {time:<12.2f} {vs_trad:>+6.1f}%        {vs_rb:>+6.1f}%")

    return results


# =============================================================================
# Test Scenarios
# =============================================================================

print("\n\n")

# Scenario 1: Simple opposite lanes (should show biggest improvement)
scenario1 = run_scenario(
    "Opposite Lanes (Main St)",
    [
        ("Main E", "NS/S", 1),  # Eastbound
        ("Main W", "NS/S", 2),  # Westbound
    ]
)

# Scenario 2: Perpendicular roads
scenario2 = run_scenario(
    "Perpendicular Roads",
    [
        ("Main E", "NS/S", 1),
        ("Green N", "NS/S", 2),
    ]
)

# Scenario 3: Mixed with turns
scenario3 = run_scenario(
    "Mixed Turns (4 vehicles)",
    [
        ("Main E", "R", 1),
        ("Green N", "L", 2),
        ("Main W", "NS/S", 3),
        ("Green S", "R", 4),
    ]
)

# Scenario 4: Heavy traffic (multiple from same approach)
scenario4 = run_scenario(
    "Heavy Traffic (6 vehicles)",
    [
        ("Main E", "NS/S", 1),
        ("Main E", "R", 2),
        ("Main W", "NS/S", 3),
        ("Green N", "L", 4),
        ("Green S", "R", 5),
        ("Green S", "NS/S", 6),
    ]
)

# Scenario 5: All straight (maximum parallel potential)
scenario5 = run_scenario(
    "All Straight (4-way)",
    [
        ("Main E", "NS/S", 1),
        ("Main W", "NS/S", 2),
        ("Green N", "NS/S", 3),
        ("Green S", "NS/S", 4),
    ]
)

# =============================================================================
# Summary
# =============================================================================

print("\n\n")
print("=" * 80)
print("OVERALL SUMMARY")
print("=" * 80)

all_scenarios = [scenario1, scenario2, scenario3, scenario4, scenario5]

# Calculate averages
avg_times = {}
for alg_name in ['Traditional', 'Roundabout', 'Smart Stop (Original)', 'Smart Stop (Fixed)']:
    times = [s[alg_name]['total_time'] for s in all_scenarios]
    avg_times[alg_name] = sum(times) / len(times)

print("\nAverage Times Across All Scenarios:")
print("-" * 80)

trad_avg = avg_times['Traditional']
rb_avg = avg_times['Roundabout']

for alg_name, avg_time in avg_times.items():
    vs_trad = ((trad_avg - avg_time) / trad_avg * 100) if trad_avg > 0 else 0
    vs_rb = ((rb_avg - avg_time) / rb_avg * 100) if rb_avg > 0 else 0

    print(f"{alg_name:<30} {avg_time:>6.2f}s   (vs Trad: {vs_trad:>+6.1f}%, vs RB: {vs_rb:>+6.1f}%)")

# Key comparison
orig_avg = avg_times['Smart Stop (Original)']
fixed_avg = avg_times['Smart Stop (Fixed)']
improvement = ((orig_avg - fixed_avg) / orig_avg * 100)

print("\n" + "=" * 80)
print("KEY FINDING")
print("=" * 80)

print(f"\nSmart Stop Original avg:  {orig_avg:.2f}s")
print(f"Smart Stop Fixed avg:     {fixed_avg:.2f}s")
print(f"Improvement from fix:     {improvement:+.1f}%")

if improvement > 5:
    print("\n✅ Lane-aware collision provides SIGNIFICANT improvement!")
    print("   Smart Stop can now activate more vehicles simultaneously")
elif improvement > 0:
    print("\n⚠️  Lane-aware collision provides modest improvement")
    print("   May need additional optimizations")
else:
    print("\n⚠️  No improvement detected")
    print("   The issue may be elsewhere in the algorithm")

# Compare to Roundabout
orig_vs_rb = ((rb_avg - orig_avg) / rb_avg * 100)
fixed_vs_rb = ((rb_avg - fixed_avg) / rb_avg * 100)

print(f"\nSmart Stop (Original) vs Roundabout: {orig_vs_rb:+.1f}%")
print(f"Smart Stop (Fixed) vs Roundabout:    {fixed_vs_rb:+.1f}%")

if fixed_vs_rb > 10:
    print("\n🎯 GOAL ACHIEVED: Smart Stop now significantly outperforms Roundabout!")
elif fixed_vs_rb > 0:
    print("\n📊 Smart Stop beats Roundabout, but margin could be larger")
else:
    print("\n⚠️  Smart Stop still not beating Roundabout - further investigation needed")

print("\n" + "=" * 80)
print()

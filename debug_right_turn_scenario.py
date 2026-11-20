#!/usr/bin/env python3
"""
Debug Right-Turn Scenario
==========================

Investigates why Roundabout beats Smart Stop in the specific
scenario with two right-turning vehicles.

From enhanced_animation_demo.py:
- Roundabout: 5.90s
- Smart Stop: 6.10s

Why does Roundabout win?
"""

import sys
from path_based_smart_stop import (
    PathBasedVehicle, FourWayGeometry, PathBasedSmartStopAlgorithm,
    RoundaboutAlgorithm
)

print("=" * 80)
print("DEBUGGING RIGHT-TURN SCENARIO")
print("=" * 80)
print("\nScenario: Two vehicles, both turning right")
print("  Car1: Main E → Right")
print("  Car2: Green N → Right")
print("\nFrom animations: Roundabout 5.90s, Smart Stop 6.10s")
print("Question: Why does Roundabout win?\n")

geometry = FourWayGeometry()

# Create the exact scenario from the animation demo
vehicles_config = [
    ("Main E", "R", 1),
    ("Green N", "R", 2),
]

# =============================================================================
# Smart Stop with detailed logging
# =============================================================================

print("=" * 80)
print("SMART STOP - DETAILED TIMELINE")
print("=" * 80)

smart_stop = PathBasedSmartStopAlgorithm(geometry)
for road, signal, order in vehicles_config:
    v = PathBasedVehicle(road, signal, order, geometry)
    smart_stop.add_vehicle(v)

print("\nInitial state:")
print(f"  Waiting vehicles: {len(smart_stop.waiting_vehicles)}")

activation_log = []

for step in range(100):
    t = smart_stop.current_time
    active_before = len(smart_stop.active_vehicles)

    status = smart_stop.step(0.1)

    active_after = status['active']

    # Log activation changes
    if step < 10 or active_before != active_after:
        activation_log.append({
            'step': step,
            'time': t,
            'active': active_after,
            'waiting': status['waiting'],
            'completed': status['completed']
        })

    if status['waiting'] == 0 and status['active'] == 0:
        break

smart_metrics = smart_stop.get_metrics()

print("\nActivation timeline (first 10 steps + changes):")
for log in activation_log[:15]:
    print(f"  t={log['time']:4.1f}s: Active={log['active']}, "
          f"Waiting={log['waiting']}, Completed={log['completed']}")

print(f"\n✅ Smart Stop completed in: {smart_metrics['total_time']:.2f}s")

# =============================================================================
# Roundabout with detailed logging
# =============================================================================

print("\n" + "=" * 80)
print("ROUNDABOUT - DETAILED TIMELINE")
print("=" * 80)

roundabout = RoundaboutAlgorithm(geometry)
for road, signal, order in vehicles_config:
    v = PathBasedVehicle(road, signal, order, geometry, use_roundabout_paths=True)
    roundabout.add_vehicle(v)

print("\nInitial state:")
print(f"  Waiting vehicles: {len(roundabout.waiting_vehicles)}")

activation_log_rb = []

for step in range(100):
    t = roundabout.current_time
    active_before = len(roundabout.active_vehicles)

    status = roundabout.step(0.1)

    active_after = status['active']

    if step < 10 or active_before != active_after:
        activation_log_rb.append({
            'step': step,
            'time': t,
            'active': active_after,
            'waiting': status['waiting'],
            'completed': status['completed']
        })

    if status['waiting'] == 0 and status['active'] == 0:
        break

rb_metrics = roundabout.get_metrics()

print("\nActivation timeline (first 10 steps + changes):")
for log in activation_log_rb[:15]:
    print(f"  t={log['time']:4.1f}s: Active={log['active']}, "
          f"Waiting={log['waiting']}, Completed={log['completed']}")

print(f"\n✅ Roundabout completed in: {rb_metrics['total_time']:.2f}s")

# =============================================================================
# Analysis
# =============================================================================

print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

time_diff = smart_metrics['total_time'] - rb_metrics['total_time']

print(f"\nSmart Stop: {smart_metrics['total_time']:.2f}s")
print(f"Roundabout: {rb_metrics['total_time']:.2f}s")
print(f"Difference: {time_diff:+.2f}s (Roundabout is faster!)")

# Compare activation patterns
print("\nActivation Patterns:")
print("-" * 60)

# When did each activate its first vehicle?
smart_first_active = next((log for log in activation_log if log['active'] > 0), None)
rb_first_active = next((log for log in activation_log_rb if log['active'] > 0), None)

if smart_first_active and rb_first_active:
    print(f"Smart Stop first activation: t={smart_first_active['time']:.1f}s")
    print(f"Roundabout first activation: t={rb_first_active['time']:.1f}s")

# When did each activate its second vehicle?
smart_second_active = next((log for log in activation_log if log['active'] == 2), None)
rb_second_active = next((log for log in activation_log_rb if log['active'] == 2), None)

if smart_second_active:
    print(f"\nSmart Stop second activation: t={smart_second_active['time']:.1f}s")
    print(f"  → Both vehicles active simultaneously? {'YES' if smart_second_active['time'] < 0.5 else 'NO'}")
else:
    print(f"\nSmart Stop: Never had 2 vehicles active simultaneously")

if rb_second_active:
    print(f"\nRoundabout second activation: t={rb_second_active['time']:.1f}s")
    print(f"  → Both vehicles active simultaneously? {'YES' if rb_second_active['time'] < 0.5 else 'NO'}")
else:
    print(f"\nRoundabout: Never had 2 vehicles active simultaneously")

# Check path lengths
print("\nPath Analysis:")
print("-" * 60)

# Create test vehicles to check paths
test_v1 = PathBasedVehicle("Main E", "R", 1, geometry, use_roundabout_paths=False)
test_v2 = PathBasedVehicle("Green N", "R", 2, geometry, use_roundabout_paths=False)
test_v1_rb = PathBasedVehicle("Main E", "R", 1, geometry, use_roundabout_paths=True)
test_v2_rb = PathBasedVehicle("Green N", "R", 2, geometry, use_roundabout_paths=True)

if hasattr(test_v1, 'path_x'):
    path_len_4way_v1 = len(test_v1.path_x)
    path_len_4way_v2 = len(test_v2.path_x)
    path_len_rb_v1 = len(test_v1_rb.path_x)
    path_len_rb_v2 = len(test_v2_rb.path_x)

    print(f"4-way paths:")
    print(f"  Car1 (Main E → R): {path_len_4way_v1} points")
    print(f"  Car2 (Green N → R): {path_len_4way_v2} points")
    print(f"\nRoundabout paths:")
    print(f"  Car1 (Main E → R): {path_len_rb_v1} points")
    print(f"  Car2 (Green N → R): {path_len_rb_v2} points")

    if path_len_rb_v1 < path_len_4way_v1:
        print(f"\n⚠️  Roundabout paths are SHORTER!")
        print(f"   This gives roundabout an advantage for right turns")

# Hypothesis
print("\n" + "=" * 80)
print("HYPOTHESIS")
print("=" * 80)

print("""
Why Roundabout might beat Smart Stop in this scenario:

1. PATH LENGTH: Right turns in a roundabout may be shorter than
   right turns in a 4-way intersection, leading to faster completion.

2. SEQUENTIAL vs PARALLEL: If both algorithms process vehicles
   sequentially (not simultaneously), the shorter path wins.

3. COORDINATION OVERHEAD: Smart Stop's backward priority logic
   might add slight overhead compared to roundabout's simple
   yield-to-active logic.

4. GEOMETRY DIFFERENCES: The roundabout geometry might be optimized
   for right turns specifically.
""")

print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)

if time_diff > 0.3:
    print("\n⚠️  Significant performance gap detected!")
    print("\nPotential fixes:")
    print("  1. Optimize 4-way right-turn paths to be shorter")
    print("  2. Ensure Smart Stop activates both vehicles simultaneously")
    print("  3. Reduce coordination overhead in Smart Stop logic")
    print("  4. Review backward priority for right-turn scenarios")
else:
    print("\n✓ Performance gap is small (<0.3s)")
    print("  This is likely due to natural geometric differences")
    print("  Smart Stop still outperforms in complex scenarios")

print("\n" + "=" * 80)
print()

#!/usr/bin/env python3
"""
Comprehensive Safe Mode Anomaly Finder
======================================

Tests multiple scenarios to find when Smart Safe beats Smart Stop
"""

import sys
from itertools import product

try:
    from path_based_smart_stop import (
        PathBasedVehicle,
        FourWayGeometry,
        PathBasedSmartStopAlgorithm,
        SmartStopSafeAlgorithm
    )
    print("✅ Imported successfully\n")
except ImportError as e:
    print(f"❌ Error: {e}")
    sys.exit(1)


def run_comparison(scenario_name, vehicle_configs):
    """Run both algorithms and compare times"""

    geometry = FourWayGeometry()

    # Test Smart Stop
    smart_stop = PathBasedSmartStopAlgorithm(geometry)
    for road, signal, order in vehicle_configs:
        vehicle = PathBasedVehicle(road, signal, order, geometry, use_roundabout_paths=False)
        smart_stop.add_vehicle(vehicle)

    for step in range(600):
        status = smart_stop.step(0.1)
        if status['waiting'] == 0 and status['active'] == 0:
            break

    smart_metrics = smart_stop.get_metrics()

    # Test Smart Safe
    smart_safe = SmartStopSafeAlgorithm(geometry)
    for road, signal, order in vehicle_configs:
        vehicle = PathBasedVehicle(road, signal, order, geometry, use_roundabout_paths=False)
        smart_safe.add_vehicle(vehicle)

    for step in range(600):
        status = smart_safe.step(0.1)
        if status['waiting'] == 0 and status['active'] == 0:
            break

    safe_metrics = smart_safe.get_metrics()

    # Compare
    smart_time = smart_metrics['total_time']
    safe_time = safe_metrics['total_time']
    diff = smart_time - safe_time

    return {
        'scenario': scenario_name,
        'smart_time': smart_time,
        'safe_time': safe_time,
        'difference': diff,
        'anomaly': diff > 0.5  # Safe is faster by more than 0.5s
    }


def main():
    print("=" * 80)
    print("SEARCHING FOR SAFE MODE ANOMALY")
    print("=" * 80)
    print("\nTesting multiple scenarios to find when Smart Safe beats Smart Stop...\n")

    # Define test scenarios
    scenarios = [
        ("2-vehicle opposite", [
            ("Main E", "NS/S", 1),
            ("Main W", "NS/S", 2)
        ]),
        ("2-vehicle perpendicular", [
            ("Main E", "NS/S", 1),
            ("Green N", "NS/S", 2)
        ]),
        ("2-vehicle right turns", [
            ("Main E", "R", 1),
            ("Green N", "R", 2)
        ]),
        ("3-vehicle all right", [
            ("Main E", "R", 1),
            ("Green N", "R", 2),
            ("Main W", "R", 3)
        ]),
        ("3-vehicle mixed", [
            ("Main E", "R", 1),
            ("Green N", "NS/S", 2),
            ("Main W", "L", 3)
        ]),
        ("4-vehicle all approaches right", [
            ("Main E", "R", 1),
            ("Green N", "R", 2),
            ("Main W", "R", 3),
            ("Green S", "R", 4)
        ]),
        ("4-vehicle all approaches straight", [
            ("Main E", "NS/S", 1),
            ("Green N", "NS/S", 2),
            ("Main W", "NS/S", 3),
            ("Green S", "NS/S", 4)
        ]),
        ("4-vehicle complex", [
            ("Main E", "L", 1),
            ("Green N", "R", 2),
            ("Main W", "NS/S", 3),
            ("Green S", "L", 4)
        ]),
        ("6-vehicle rush hour", [
            ("Main E", "R", 1),
            ("Main W", "L", 2),
            ("Green N", "NS/S", 3),
            ("Green S", "R", 4),
            ("Main E", "L", 5),
            ("Green N", "R", 6)
        ])
    ]

    results = []
    anomalies = []

    for scenario_name, vehicle_configs in scenarios:
        print(f"Testing: {scenario_name}...", end=" ")
        result = run_comparison(scenario_name, vehicle_configs)
        results.append(result)

        if result['anomaly']:
            print(f"⚠️  ANOMALY FOUND! (Safe: {result['safe_time']:.2f}s, Smart: {result['smart_time']:.2f}s, diff: {result['difference']:+.2f}s)")
            anomalies.append(result)
        else:
            print(f"✓ (Safe: {result['safe_time']:.2f}s, Smart: {result['smart_time']:.2f}s, diff: {result['difference']:+.2f}s)")

    # Summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)

    print(f"\nTotal scenarios tested: {len(results)}")
    print(f"Anomalies found: {len(anomalies)}")

    if anomalies:
        print("\n⚠️  ANOMALIES DETECTED:")
        for anomaly in anomalies:
            print(f"\n  Scenario: {anomaly['scenario']}")
            print(f"    Smart Stop: {anomaly['smart_time']:.2f}s")
            print(f"    Smart Safe: {anomaly['safe_time']:.2f}s")
            print(f"    Difference: {anomaly['difference']:+.2f}s (Safe is FASTER!)")
    else:
        print("\n✓ No anomalies found in these scenarios")
        print("  Smart Stop consistently performs as expected")

    # Statistics
    print("\n" + "-" * 80)
    print("PERFORMANCE STATISTICS:")
    print("-" * 80)

    avg_smart = sum(r['smart_time'] for r in results) / len(results)
    avg_safe = sum(r['safe_time'] for r in results) / len(results)

    print(f"\nAverage Smart Stop time: {avg_smart:.2f}s")
    print(f"Average Smart Safe time:  {avg_safe:.2f}s")
    print(f"Overall difference:       {avg_smart - avg_safe:+.2f}s")

    if avg_smart < avg_safe:
        improvement = ((avg_safe - avg_smart) / avg_safe) * 100
        print(f"\n✓ Smart Stop is {improvement:.1f}% faster on average (expected)")
    else:
        print(f"\n⚠️  Smart Safe is somehow faster on average (unexpected!)")

    print("\n")


if __name__ == "__main__":
    main()

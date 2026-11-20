#!/usr/bin/env python3
"""
Multi-Vehicle Validation Script - Testing Algorithm Coordination
=================================================================

PURPOSE:
Single-vehicle tests proved physics works correctly. Now we test the
ALGORITHMS themselves - how they coordinate multiple vehicles.

KEY INSIGHT:
For single vehicles, all algorithms should be identical (which we proved).
For multiple vehicles, algorithms SHOULD differ - that's the whole point!

- Traditional: Sequential (one car at a time)
- Smart Stop: Parallel (multiple cars when safe)

This script validates that these differences appear correctly.

LEARNING GOALS:
1. How to design test cases that reveal algorithm behavior
2. How to verify expected differences vs bugs
3. How to test coordination logic
4. How to compare algorithm efficiency
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

try:
    from path_based_smart_stop import (
        PathBasedVehicle, FourWayGeometry,
        TraditionalStopAlgorithm, PathBasedSmartStopAlgorithm,
        SmartStopSafeAlgorithm
    )

    print("✅ Successfully imported classes")
except ImportError as e:
    print(f"❌ Import error: {e}")
    exit(1)

# =============================================================================
# TEST CASE DESIGN: How to Create Meaningful Multi-Vehicle Scenarios
# =============================================================================
"""
PRINCIPLE: Test cases should reveal specific algorithm behaviors.

GOOD TEST CASES:
1. Non-conflicting cars (should move in parallel in Smart Stop)
2. Conflicting cars (should be sequential in both algorithms)
3. Backward priority scenarios (Smart Stop's key advantage)

BAD TEST CASES:
- Random scenarios without clear expected outcome
- Too complex to understand what went wrong
- Don't isolate specific algorithm features
"""


def create_test_scenario(scenario_type):
    """
    Create specific vehicle configurations that test different coordination patterns.

    Educational Note:
    Each scenario is DESIGNED to test a specific aspect of algorithm behavior.
    We're not just randomly testing - we're strategically probing for bugs.

    Args:
        scenario_type: String identifying which test pattern to create

    Returns:
        List of vehicle configurations (road, signal, order) and expected behavior
    """

    geometry = FourWayGeometry()

    if scenario_type == "non_conflicting":
        """
        TEST: Two cars that don't interfere with each other

        Main E → Right (turns to Green S)
        Green N → Right (turns to Main W)

        These paths don't intersect, so Smart Stop should allow parallel movement.
        Traditional should still be sequential (it always is).

        EXPECTED:
        - Traditional: ~5.6s (car1: 2.8s, car2: 2.8s, sequential)
        - Smart Stop: ~2.8s (both cars move simultaneously)

        If Smart Stop takes 5.6s, parallel movement isn't working!
        """
        vehicles = [
            PathBasedVehicle("Main E", "R", 1, geometry, use_roundabout_paths=False),
            PathBasedVehicle("Green N", "R", 2, geometry, use_roundabout_paths=False)
        ]
        expected = {
            'Traditional': {'time_range': (5.0, 6.0), 'behavior': 'sequential'},
            'Smart Stop': {'time_range': (2.5, 3.5), 'behavior': 'parallel'}
        }

    elif scenario_type == "conflicting":
        """
        TEST: Two cars that MUST go sequentially (paths intersect)

        Main E → Straight (crosses entire intersection)
        Main W → Straight (crosses entire intersection)

        These paths directly intersect, so BOTH algorithms must be sequential.

        EXPECTED:
        - Traditional: ~5.6s (sequential, as always)
        - Smart Stop: ~5.6s (must be sequential due to conflict)

        If Smart Stop is faster here, collision detection is broken!
        """
        vehicles = [
            PathBasedVehicle("Main E", "NS/S", 1, geometry, use_roundabout_paths=False),
            PathBasedVehicle("Green S", "L", 2, geometry, use_roundabout_paths=False)
        ]
        expected = {
            'Traditional': {'time_range': (5.0, 6.0), 'behavior': 'sequential'},
            'Smart Stop': {'time_range': (5.0, 6.0), 'behavior': 'sequential'}
        }

    elif scenario_type == "backward_priority":
        """
        TEST: Smart Stop's key innovation - backward priority

        Main E → Straight (enters first)
        Green S → Right (enters from position BEHIND Main E)

        Smart Stop should recognize Green S can safely enter while Main E 
        is moving, using the backward priority rule.

        EXPECTED:
        - Traditional: ~5.6s (sequential)
        - Smart Stop: ~2.8s (parallel via backward priority)

        This tests the CORE Smart Stop algorithm advantage!
        """
        vehicles = [
            PathBasedVehicle("Main E", "NS/S", 1, geometry, use_roundabout_paths=False),
            PathBasedVehicle("Green S", "R", 2, geometry, use_roundabout_paths=False)
        ]
        expected = {
            'Traditional': {'time_range': (5.0, 6.0), 'behavior': 'sequential'},
            'Smart Stop': {'time_range': (2.5, 3.5), 'behavior': 'parallel'}
        }

    else:
        raise ValueError(f"Unknown scenario type: {scenario_type}")

    return vehicles, expected


# =============================================================================
# STEP 1: Test Non-Conflicting Vehicles
# =============================================================================

def test_non_conflicting_scenario():
    """
    Test the simplest parallel case: two cars with non-intersecting paths.

    Learning Point:
    This is the "hello world" of multi-vehicle testing. If this doesn't work,
    nothing will. We test the simplest case first to establish a baseline.
    """
    print("\n" + "=" * 70)
    print("STEP 1: Non-Conflicting Vehicles Test")
    print("=" * 70)

    vehicles, expected = create_test_scenario("non_conflicting")

    print("\nScenario:")
    print("  Car 1: Main E → Right")
    print("  Car 2: Green N → Right")
    print("  These paths don't intersect - should allow parallel movement")

    results = run_scenario_comparison(vehicles, expected)

    # Validate results
    print("\n" + "-" * 70)
    print("VALIDATION:")

    trad_time = results['Traditional']['completion_time']
    smart_time = results['Smart Stop']['completion_time']

    print(f"\nTraditional: {trad_time:.2f}s (expected: sequential ~5.6s)")
    print(f"Smart Stop:  {smart_time:.2f}s (expected: parallel ~2.8s)")

    # Check if Smart Stop achieved parallelism
    speedup = ((trad_time - smart_time) / trad_time * 100) if trad_time > 0 else 0

    if speedup > 40:  # Smart Stop should be ~50% faster (parallel vs sequential)
        print(f"\n✅ PASS: Smart Stop achieved {speedup:.1f}% speedup via parallel movement")
    else:
        print(f"\n❌ FAIL: Smart Stop only {speedup:.1f}% faster - parallel movement not working!")
        print("   Expected ~50% speedup for non-conflicting vehicles")

    return results


# =============================================================================
# STEP 2: Test Conflicting Vehicles
# =============================================================================

def test_conflicting_scenario():
    """
    Test that conflicting vehicles are handled sequentially by BOTH algorithms.

    Learning Point:
    This is a NEGATIVE test - we're verifying that algorithms DON'T allow
    parallel movement when it would be unsafe. This is just as important as
    testing that they DO allow it when safe.

    Debugging Tip:
    If Smart Stop is faster here, it means collision detection is broken
    and it's allowing unsafe parallel movement!
    """
    print("\n" + "=" * 70)
    print("STEP 2: Conflicting Vehicles Test")
    print("=" * 70)

    vehicles, expected = create_test_scenario("conflicting")

    print("\nScenario:")
    print("  Car 1: Main E → Straight")
    print("  Car 2: Main W → Straight")
    print("  These paths intersect - MUST be sequential for safety")

    results = run_scenario_comparison(vehicles, expected)

    # Validate results
    print("\n" + "-" * 70)
    print("VALIDATION:")

    trad_time = results['Traditional']['completion_time']
    smart_time = results['Smart Stop']['completion_time']

    print(f"\nTraditional: {trad_time:.2f}s (expected: sequential ~5.6s)")
    print(f"Smart Stop:  {smart_time:.2f}s (expected: sequential ~5.6s)")

    # Check that times are similar (both sequential)
    time_diff = abs(trad_time - smart_time)

    if time_diff < 0.5:  # Should be nearly identical
        print(f"\n✅ PASS: Both algorithms sequential (diff: {time_diff:.2f}s)")
        print("   Collision detection is working correctly")
    else:
        print(f"\n❌ FAIL: Times differ by {time_diff:.2f}s")
        print("   Smart Stop may be allowing unsafe parallel movement!")

    return results


# =============================================================================
# STEP 3: Test Backward Priority (Smart Stop's Key Feature)
# =============================================================================

def test_backward_priority_scenario():
    """
    Test Smart Stop's signature feature: backward priority optimization.

    Learning Point:
    This tests the CORE INNOVATION of your research. If this doesn't work,
    the entire Smart Stop concept needs debugging.

    The backward priority rule: vehicles entering from positions BEHIND
    active vehicles can enter safely because they won't interfere.
    """
    print("\n" + "=" * 70)
    print("STEP 3: Backward Priority Test (Smart Stop's Key Innovation)")
    print("=" * 70)

    vehicles, expected = create_test_scenario("backward_priority")

    print("\nScenario:")
    print("  Car 1: Main E → Straight (enters first)")
    print("  Car 2: Green S → Right (enters from behind)")
    print("  Smart Stop should recognize Car 2 can enter safely via backward priority")

    results = run_scenario_comparison(vehicles, expected)

    # Validate results
    print("\n" + "-" * 70)
    print("VALIDATION:")

    trad_time = results['Traditional']['completion_time']
    smart_time = results['Smart Stop']['completion_time']

    print(f"\nTraditional: {trad_time:.2f}s (expected: sequential ~5.6s)")
    print(f"Smart Stop:  {smart_time:.2f}s (expected: parallel ~2.8s via backward priority)")

    speedup = ((trad_time - smart_time) / trad_time * 100) if trad_time > 0 else 0

    if speedup > 40:
        print(f"\n✅ PASS: Backward priority working! {speedup:.1f}% speedup")
        print("   This is the core Smart Stop algorithm advantage!")
    else:
        print(f"\n❌ FAIL: Backward priority not working - only {speedup:.1f}% speedup")
        print("   Expected ~50% improvement from parallel movement")
        print("   Debug: Check Smart Stop's safe position logic")

    return results


# =============================================================================
# HELPER FUNCTION: Run Scenario Through Multiple Algorithms
# =============================================================================

def run_scenario_comparison(vehicles, expected):
    """
    Run the same vehicle scenario through multiple algorithms and compare.

    Educational Note:
    This function encapsulates the "run and compare" pattern that's central
    to validation testing. We run the exact same scenario through different
    implementations and compare outcomes.

    Args:
        vehicles: List of PathBasedVehicle objects
        expected: Dictionary of expected behaviors per algorithm

    Returns:
        Dictionary with results from each algorithm
    """

    geometry = FourWayGeometry()

    # Algorithms to test
    algorithms_to_test = {
        'Traditional': TraditionalStopAlgorithm,
        'Smart Stop': PathBasedSmartStopAlgorithm,
        'Smart Safe': SmartStopSafeAlgorithm
    }

    results = {}

    print(f"\nRunning simulation with {len(vehicles)} vehicles...")

    for alg_name, AlgorithmClass in algorithms_to_test.items():
        # Create fresh vehicle copies for this algorithm
        # This is CRITICAL - each algorithm needs its own vehicle objects
        # to avoid state pollution between tests
        fresh_vehicles = []
        for v in vehicles:
            fresh_v = PathBasedVehicle(
                v.road_name, v.signal, v.order, geometry,
                use_roundabout_paths=False
            )
            fresh_vehicles.append(fresh_v)

        # Create algorithm and add vehicles
        algorithm = AlgorithmClass(geometry)
        for vehicle in fresh_vehicles:
            algorithm.add_vehicle(vehicle)

        # Run simulation
        dt = 0.1
        max_time = 20.0  # Longer for multi-vehicle scenarios
        max_steps = int(max_time / dt)

        # Track which vehicles are active at each timestep
        # This helps us visualize parallel vs sequential movement
        active_timeline = []

        for step in range(max_steps):
            status = algorithm.step(dt)

            # Record which vehicles are currently active
            active_count = status['active']
            active_timeline.append(active_count)

            # Stop when complete
            if status['waiting'] == 0 and status['active'] == 0:
                break

        # Get metrics
        metrics = algorithm.get_metrics()

        # Calculate parallelism metric
        # Average active vehicles > 1.0 means parallel movement occurred
        avg_active = np.mean(active_timeline) if active_timeline else 0

        results[alg_name] = {
            'completion_time': metrics['total_time'],
            'active_timeline': active_timeline,
            'avg_active_vehicles': avg_active,
            'max_active_vehicles': max(active_timeline) if active_timeline else 0
        }

        # Determine behavior
        behavior = "parallel" if avg_active > 1.2 else "sequential"

        print(f"  {alg_name:<15}: {metrics['total_time']:.2f}s "
              f"(avg active: {avg_active:.2f}, {behavior})")

    return results


# =============================================================================
# STEP 4: Visualize Multi-Vehicle Coordination
# =============================================================================

def visualize_multi_vehicle_timeline(all_results):
    """
    Create timeline visualization showing when vehicles are active.

    Learning Point:
    Visual debugging is powerful. A timeline showing active vehicles makes
    it immediately obvious whether algorithms are parallel or sequential.
    """
    print("\n" + "=" * 70)
    print("Creating coordination timeline visualization...")

    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    fig.suptitle('Multi-Vehicle Coordination Timeline\n(Higher bars = More Parallel Movement)',
                 fontsize=14, fontweight='bold')

    scenarios = ['non_conflicting', 'conflicting', 'backward_priority']
    titles = [
        'Non-Conflicting Vehicles\n(Should show parallelism)',
        'Conflicting Vehicles\n(Should be sequential)',
        'Backward Priority\n(Smart Stop should show parallelism)'
    ]

    for idx, (scenario, title) in enumerate(zip(scenarios, titles)):
        ax = axes[idx]
        results = all_results[scenario]

        for alg_name, data in results.items():
            timeline = data['active_timeline']
            if timeline:
                times = np.arange(len(timeline)) * 0.1
                ax.plot(times, timeline, label=alg_name, linewidth=2, alpha=0.7)

        ax.set_ylabel('Active Vehicles')
        ax.set_xlabel('Time (s)')
        ax.set_title(title, fontsize=11)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 2.5)

        # Add reference line at y=1
        ax.axhline(y=1, color='gray', linestyle='--', alpha=0.5,
                   label='1 vehicle (sequential)')

    plt.tight_layout()
    return fig


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("MULTI-VEHICLE VALIDATION TEST SUITE")
    print("=" * 70)
    print("\nPurpose: Test that algorithms coordinate multiple vehicles correctly")
    print("Expected: Traditional is always sequential, Smart Stop allows parallelism")
    print()

    # Store all results for visualization
    all_results = {}

    # Step 1: Non-conflicting (easiest parallel case)
    print("\n[1/3] Testing non-conflicting vehicles...")
    results_1 = test_non_conflicting_scenario()
    all_results['non_conflicting'] = results_1

    input("\nPress Enter to continue to conflicting test...")

    # Step 2: Conflicting (should be sequential for both)
    print("\n[2/3] Testing conflicting vehicles...")
    results_2 = test_conflicting_scenario()
    all_results['conflicting'] = results_2

    input("\nPress Enter to continue to backward priority test...")

    # Step 3: Backward priority (Smart Stop's key feature)
    print("\n[3/3] Testing backward priority...")
    results_3 = test_backward_priority_scenario()
    all_results['backward_priority'] = results_3

    input("\nPress Enter to view visualization...")

    # Visualize
    fig = visualize_multi_vehicle_timeline(all_results)

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)

    print("\nKey Findings:")
    print("1. Review each test's PASS/FAIL status above")
    print("2. Check the timeline visualization:")
    print("   - Flat line at y=1: Sequential movement")
    print("   - Line at y=2: Both cars moving simultaneously (parallel)")
    print("3. Smart Stop should show parallelism in tests 1 and 3")
    print("4. Both algorithms should be sequential in test 2 (safety)")

    print("\nIf any tests failed:")
    print("- Non-conflicting fail: Parallel movement logic broken")
    print("- Conflicting fail: Collision detection broken (DANGEROUS!)")
    print("- Backward priority fail: Core Smart Stop algorithm needs debugging")

    plt.show()
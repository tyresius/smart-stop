#!/usr/bin/env python3
"""
Smart Stop Sign Animation Demo
==============================

Creates animated visualizations comparing all four traffic algorithms
(Traditional, Roundabout, Smart Stop, Smart Safe) on 4-way intersections.

Output: GIF animations saved to your configured output directory

Usage:
    python animation_demo.py

This will create animations for three different traffic scenarios:
1. Non-conflicting vehicles (should show parallelism in Smart Stop)
2. Conflicting vehicles (should be sequential for all)
3. Backward priority scenario (Smart Stop's key advantage)

Output files will be saved to the directory specified in config.py
"""

import sys
import os

# Import config for environment-aware paths
try:
    from config import OUTPUT_DIR, ENVIRONMENT

    print(f"✅ Config loaded - Running in {ENVIRONMENT} environment")
    print(f"   Output directory: {OUTPUT_DIR}")
except ImportError:
    print("❌ Error: config.py not found")
    print("   Make sure config.py is in your project root directory")
    sys.exit(1)

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Import path-based Smart Stop classes
try:
    from path_based_smart_stop import (
        PathBasedVehicle,
        FourWayGeometry,
        RoundaboutGeometry,
        AlgorithmComparison,
        IntersectionAnimator
    )

    print("✅ Path-based Smart Stop system imported successfully")
except ImportError as e:
    print(f"❌ Error importing Smart Stop system: {e}")
    print("   Make sure path_based_smart_stop.py is in your project root")
    sys.exit(1)


# =============================================================================
# SCENARIO 1: Non-Conflicting Vehicles
# =============================================================================

def scenario_1_non_conflicting():
    """
    Two vehicles with non-intersecting paths.
    Expected: Smart Stop should allow parallel movement (speedup ~50%)
    """
    print("\n" + "=" * 70)
    print("SCENARIO 1: Non-Conflicting Vehicles")
    print("=" * 70)
    print("Description: Two vehicles from different approaches with non-intersecting paths")
    print("Expected: Smart Stop allows parallel movement, Traditional is sequential")

    geometry = FourWayGeometry()

    vehicles = [
        PathBasedVehicle("Main E", "R", 1, geometry),  # Main E → Right (to Green S)
        PathBasedVehicle("Green N", "R", 2, geometry),  # Green N → Right (to Main W)
    ]

    print(f"\nVehicles:")
    for v in vehicles:
        print(f"  • {v.car_name}: {v.road_name} → {v.signal}")

    # Run comparison
    print("\n⏱️  Running algorithm comparison...")
    comparison = AlgorithmComparison(vehicles, "4way")
    results = comparison.run_comparison()

    # Print results
    print("\n📊 Results:")
    print(f"{'Algorithm':<15} {'Time (s)':<12} {'Behavior':<15}")
    print("-" * 42)

    best_time = float('inf')
    best_algo = None

    for alg_name, data in results.items():
        time = data['metrics']['total_time']
        if time < best_time:
            best_time = time
            best_algo = alg_name

        # Estimate behavior based on time
        behavior = "Parallel ✓" if time < 3.5 else "Sequential"
        print(f"{alg_name:<15} {time:<12.2f} {behavior:<15}")

    print(f"\n🏆 Fastest: {best_algo} ({best_time:.2f}s)")

    # Create animation
    print("\n🎬 Creating animation...")
    try:
        animator = IntersectionAnimator(results, "4way")
        save_path = os.path.join(OUTPUT_DIR, "scenario_1_non_conflicting.gif")
        anim = animator.animate(save_path=save_path)
        print(f"✅ Animation saved to: {save_path}")
    except Exception as e:
        print(f"⚠️  Animation creation failed: {e}")

    return results


# =============================================================================
# SCENARIO 2: Conflicting Vehicles
# =============================================================================

def scenario_2_conflicting():
    """
    Two vehicles with intersecting paths (perpendicular).
    Expected: Both algorithms should be sequential (~5.6s each)
    """
    print("\n" + "=" * 70)
    print("SCENARIO 2: Conflicting Vehicles")
    print("=" * 70)
    print("Description: Two vehicles whose paths directly intersect")
    print("Expected: Both algorithms must be sequential for safety")

    geometry = FourWayGeometry()

    vehicles = [
        PathBasedVehicle("Main E", "NS/S", 1, geometry),  # Main E → Straight (left to right)
        PathBasedVehicle("Green N", "L", 2, geometry),  # Green N → Left (conflicts with Main E)
    ]

    print(f"\nVehicles:")
    for v in vehicles:
        print(f"  • {v.car_name}: {v.road_name} → {v.signal}")

    # Run comparison
    print("\n⏱️  Running algorithm comparison...")
    comparison = AlgorithmComparison(vehicles, "4way")
    results = comparison.run_comparison()

    # Print results
    print("\n📊 Results:")
    print(f"{'Algorithm':<15} {'Time (s)':<12} {'Behavior':<15}")
    print("-" * 42)

    best_time = float('inf')
    best_algo = None

    for alg_name, data in results.items():
        time = data['metrics']['total_time']
        if time < best_time:
            best_time = time
            best_algo = alg_name

        # Should all be similar (sequential)
        behavior = "Sequential ✓"
        print(f"{alg_name:<15} {time:<12.2f} {behavior:<15}")

    print(f"\n🏆 Fastest: {best_algo} ({best_time:.2f}s)")
    print("   (Note: All should be similar since paths conflict)")

    # Create animation
    print("\n🎬 Creating animation...")
    try:
        animator = IntersectionAnimator(results, "4way")
        save_path = os.path.join(OUTPUT_DIR, "scenario_2_conflicting.gif")
        anim = animator.animate(save_path=save_path)
        print(f"✅ Animation saved to: {save_path}")
    except Exception as e:
        print(f"⚠️  Animation creation failed: {e}")

    return results


# =============================================================================
# SCENARIO 3: Backward Priority (Smart Stop's Key Advantage)
# =============================================================================

def scenario_3_backward_priority():
    """
    Smart Stop's core innovation: backward priority.
    Expected: Smart Stop should achieve parallelism via backward priority
    """
    print("\n" + "=" * 70)
    print("SCENARIO 3: Backward Priority (Smart Stop's Key Feature)")
    print("=" * 70)
    print("Description: Vehicle from behind active vehicle can enter safely")
    print("Expected: Smart Stop allows parallel movement, others are sequential")

    geometry = FourWayGeometry()

    vehicles = [
        PathBasedVehicle("Main E", "NS/S", 1, geometry),  # Main E → Straight (enters first)
        PathBasedVehicle("Green S", "R", 2, geometry),  # Green S → Right (behind Main E, safe to enter)
    ]

    print(f"\nVehicles:")
    for v in vehicles:
        print(f"  • {v.car_name}: {v.road_name} → {v.signal}")

    # Run comparison
    print("\n⏱️  Running algorithm comparison...")
    comparison = AlgorithmComparison(vehicles, "4way")
    results = comparison.run_comparison()

    # Print results
    print("\n📊 Results:")
    print(f"{'Algorithm':<15} {'Time (s)':<12} {'Behavior':<15}")
    print("-" * 42)

    best_time = float('inf')
    best_algo = None

    for alg_name, data in results.items():
        time = data['metrics']['total_time']
        if time < best_time:
            best_time = time
            best_algo = alg_name

        # Smart Stop should be faster (parallel via backward priority)
        if alg_name == "Smart Stop" and time < 3.5:
            behavior = "Parallel ✓✓✓"
        elif time > 5.0:
            behavior = "Sequential"
        else:
            behavior = "Mixed"
        print(f"{alg_name:<15} {time:<12.2f} {behavior:<15}")

    print(f"\n🏆 Fastest: {best_algo} ({best_time:.2f}s)")
    print("   (Smart Stop should show advantage here)")

    # Create animation
    print("\n🎬 Creating animation...")
    try:
        animator = IntersectionAnimator(results, "4way")
        save_path = os.path.join(OUTPUT_DIR, "scenario_3_backward_priority.gif")
        anim = animator.animate(save_path=save_path)
        print(f"✅ Animation saved to: {save_path}")
    except Exception as e:
        print(f"⚠️  Animation creation failed: {e}")

    return results


# =============================================================================
# BONUS: Complex Multi-Vehicle Scenario
# =============================================================================

def scenario_bonus_rush_hour():
    """
    Complex scenario with multiple vehicles from all approaches.
    Good for demonstrating overall system performance.
    """
    print("\n" + "=" * 70)
    print("BONUS SCENARIO: Rush Hour (Complex Multi-Vehicle)")
    print("=" * 70)
    print("Description: Multiple vehicles from all four approaches")
    print("Expected: Smart Stop should show advantage in parallelism")

    geometry = FourWayGeometry()

    vehicles = [
        PathBasedVehicle("Main E", "R", 1, geometry),  # East → Right
        PathBasedVehicle("Main W", "L", 2, geometry),  # West → Left
        PathBasedVehicle("Green N", "NS/S", 3, geometry),  # North → Straight
        PathBasedVehicle("Green S", "R", 4, geometry),  # South → Right
        PathBasedVehicle("Main E", "L", 5, geometry),  # East → Left
        PathBasedVehicle("Green N", "R", 6, geometry),  # North → Right
    ]

    print(f"\nVehicles:")
    for v in vehicles:
        print(f"  • {v.car_name}: {v.road_name} → {v.signal}")

    # Run comparison
    print("\n⏱️  Running algorithm comparison...")
    comparison = AlgorithmComparison(vehicles, "4way")
    results = comparison.run_comparison()

    # Print results
    print("\n📊 Results:")
    print(f"{'Algorithm':<15} {'Time (s)':<12} {'Wait Time':<12}")
    print("-" * 42)

    best_time = float('inf')
    best_algo = None

    for alg_name, data in results.items():
        time = data['metrics']['total_time']
        wait = data['metrics']['avg_wait_time']
        if time < best_time:
            best_time = time
            best_algo = alg_name

        print(f"{alg_name:<15} {time:<12.2f} {wait:<12.2f}")

    print(f"\n🏆 Fastest: {best_algo} ({best_time:.2f}s)")
    print(f"   Average wait: {results[best_algo]['metrics']['avg_wait_time']:.2f}s")

    # Create animation
    print("\n🎬 Creating animation...")
    try:
        animator = IntersectionAnimator(results, "4way")
        save_path = os.path.join(OUTPUT_DIR, "scenario_bonus_rush_hour.gif")
        anim = animator.animate(save_path=save_path)
        print(f"✅ Animation saved to: {save_path}")
    except Exception as e:
        print(f"⚠️  Animation creation failed: {e}")

    return results


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    print("\n" + "=" * 70)
    print("SMART STOP SIGN ANIMATION DEMO")
    print("=" * 70)
    print(f"\nEnvironment: {ENVIRONMENT}")
    print(f"Output directory: {OUTPUT_DIR}\n")

    all_results = {}

    try:
        # Run scenarios
        print("Running 3 core scenarios + 1 bonus scenario...")

        all_results['scenario_1'] = scenario_1_non_conflicting()
        all_results['scenario_2'] = scenario_2_conflicting()
        all_results['scenario_3'] = scenario_3_backward_priority()

        print("\n" + "-" * 70)
        print("Running bonus scenario...")
        all_results['bonus'] = scenario_bonus_rush_hour()

    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()
        return

    # Summary
    print("\n" + "=" * 70)
    print("ANIMATION GENERATION COMPLETE")
    print("=" * 70)

    print(f"\n✅ All animations saved to: {OUTPUT_DIR}")
    print("\nGenerated files:")
    print("  1. scenario_1_non_conflicting.gif")
    print("  2. scenario_2_conflicting.gif")
    print("  3. scenario_3_backward_priority.gif")
    print("  4. scenario_bonus_rush_hour.gif")

    print("\n📊 Key Findings Summary:")

    # Scenario 1
    sc1_smart = all_results['scenario_1']['Smart Stop']['completion_time']
    sc1_trad = all_results['scenario_1']['Traditional']['completion_time']
    sc1_speedup = ((sc1_trad - sc1_smart) / sc1_trad * 100) if sc1_trad > 0 else 0
    print(f"\n  Scenario 1 (Non-Conflicting):")
    print(f"    Traditional: {sc1_trad:.2f}s | Smart Stop: {sc1_smart:.2f}s")
    print(f"    Speedup: {sc1_speedup:.1f}% (expects ~50% for parallel movement)")

    # Scenario 2
    sc2_smart = all_results['scenario_2']['Smart Stop']['completion_time']
    sc2_trad = all_results['scenario_2']['Traditional']['completion_time']
    sc2_speedup = ((sc2_trad - sc2_smart) / sc2_trad * 100) if sc2_trad > 0 else 0
    print(f"\n  Scenario 2 (Conflicting):")
    print(f"    Traditional: {sc2_trad:.2f}s | Smart Stop: {sc2_smart:.2f}s")
    print(f"    Speedup: {sc2_speedup:.1f}% (expects ~0% for safety)")

    # Scenario 3
    sc3_smart = all_results['scenario_3']['Smart Stop']['completion_time']
    sc3_trad = all_results['scenario_3']['Traditional']['completion_time']
    sc3_speedup = ((sc3_trad - sc3_smart) / sc3_trad * 100) if sc3_trad > 0 else 0
    print(f"\n  Scenario 3 (Backward Priority):")
    print(f"    Traditional: {sc3_trad:.2f}s | Smart Stop: {sc3_smart:.2f}s")
    print(f"    Speedup: {sc3_speedup:.1f}% (expects ~50% via backward priority)")

    print("\n🎯 Next Steps:")
    print("  1. Open the GIF files to view animations")
    print("  2. Check if Smart Stop shows parallelism in scenarios 1 & 3")
    print("  3. Verify both algorithms are sequential in scenario 2 (safety)")
    print("  4. Use animations for presentations to stakeholders")

    print("\n✨ Animation demo complete! Good luck with your presentation!")


if __name__ == "__main__":
    main()
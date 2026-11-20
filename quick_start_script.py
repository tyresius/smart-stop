#!/usr/bin/env python3
"""
QUICK START - Path-Based Smart Stop System
==========================================

Run this script to immediately see your Smart Stop algorithm in action
with continuous path movement and animated comparisons!

Usage:
1. Save the main system code as 'path_based_smart_stop.py'
2. Run: python quick_start_script.py
"""


def quick_demo():
    """Run a quick demonstration with better error handling"""

    try:
        # Import the system
        from path_based_smart_stop import (
            PathBasedVehicle, FourWayGeometry, AlgorithmComparison, IntersectionAnimator
        )
        print("✅ System imported successfully!")
    except ImportError as e:
        print(f"❌ Could not import system: {e}")
        print("Make sure 'path_based_smart_stop.py' is in this directory.")
        return

    print("\n🚦 QUICK DEMO: Path-Based Smart Stop System")
    print("=" * 50)

    # Create a simple but interesting scenario
    geometry = FourWayGeometry()

    # Scenario: Rush hour with multiple conflicts
    # vehicles = [
    #     PathBasedVehicle("Main E", "L", 1, geometry),  # Left turn (slow)
    #     PathBasedVehicle("Main W", "R", 2, geometry),  # Right turn (fast)
    #     PathBasedVehicle("Green N", "NS/S", 3, geometry),  # Straight (medium)
    #     PathBasedVehicle("Green S", "L", 4, geometry),  # Left turn (slow)
    #     PathBasedVehicle("Main E", "R", 5, geometry),  # Right turn (fast)
    # ]
    vehicles = [
        PathBasedVehicle("Main E", "NS/S", 1, geometry),
        # PathBasedVehicle("Main W", "L", 2, geometry),
        # PathBasedVehicle("Green N", "L", 3, geometry),
        # PathBasedVehicle("Green S", "L", 4, geometry),
    ]
    print(f"Created scenario with {len(vehicles)} vehicles:")
    for v in vehicles:
        print(f"  • {v.car_name}: {v.road_name} → {v.signal}")

    # Run comparison with error handling
    print(f"\n⏱️  Running algorithm comparison...")
    try:
        comparison = AlgorithmComparison(vehicles, "4way")
        results = comparison.run_comparison()

        # DEBUG: Show what we actually got back
        print(f"\n🔍 DEBUG: Results structure:")
        print(f"Type: {type(results)}")
        if isinstance(results, dict):
            print(f"Keys: {list(results.keys())}")
            for key, value in results.items():
                print(f"  {key}: {type(value)}")
                if isinstance(value, dict) and 'metrics' in value:
                    print(f"    metrics: {value['metrics']}")
        else:
            print(f"Results content: {results}")

    except Exception as e:
        print(f"❌ Algorithm comparison failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Check if we got valid results
    if not results:
        print("❌ No results returned from algorithm comparison")
        return

    if not isinstance(results, dict):
        print(f"❌ Results is not a dictionary: {type(results)}")
        return

    # Check what algorithms we actually have
    available_algorithms = list(results.keys())
    print(f"\n📋 Available algorithms: {available_algorithms}")

    if not available_algorithms:
        print("❌ No algorithms completed successfully")
        return

    # Show results with defensive programming
    print(f"\n📊 RESULTS:")
    print(f"{'Algorithm':<15} {'Time (s)':<10} {'Status':<15} {'Efficiency':<12}")
    print("-" * 65)

    # Find traditional time for baseline (with fallback)
    traditional_time = None
    if 'Traditional' in results:
        traditional_time = results['Traditional']['metrics']['total_time']
    elif available_algorithms:
        # Use first available algorithm as baseline
        baseline_alg = available_algorithms[0]
        traditional_time = results[baseline_alg]['metrics']['total_time']
        print(f"⚠️  Using {baseline_alg} as baseline (Traditional not available)")

    # Display results for each algorithm
    all_times = []
    for alg_name in available_algorithms:
        try:
            data = results[alg_name]
            if 'metrics' not in data:
                print(f"   {alg_name:<15} {'N/A':<10} {'No metrics':<15} {'N/A':<12}")
                continue

            time = data['metrics']['total_time']
            all_times.append(time)
            status = "✅ Complete"

            # Calculate efficiency
            if traditional_time and traditional_time > 0:
                if alg_name == 'Traditional' or (traditional_time == time):
                    efficiency = "Baseline"
                else:
                    improvement = ((traditional_time - time) / traditional_time) * 100
                    efficiency = f"+{improvement:.1f}%"
            else:
                efficiency = "N/A"

            print(f"   {alg_name:<15} {time:<10.1f} {status:<15} {efficiency:<12}")

        except Exception as e:
            print(f"   {alg_name:<15} {'ERROR':<10} {str(e)[:13]:<15} {'N/A':<12}")

    # Find winner
    if all_times:
        best_time = min(all_times)
        for alg_name in available_algorithms:
            if (alg_name in results and
                    'metrics' in results[alg_name] and
                    results[alg_name]['metrics']['total_time'] == best_time):
                print(f"\n🏆 Winner: {alg_name} ({best_time:.1f} seconds)")
                break

    # Try animation if we have results
    if len(available_algorithms) >= 2:
        print(f"\n🎬 Creating animated comparison...")
        try:
            animator = IntersectionAnimator(results, "4way")
            save_path = "quick_demo_animation.gif"
            anim = animator.animate(save_path=save_path)
            print(f"✅ Animation saved to: {save_path}")

        except Exception as e:
            print(f"⚠️  Animation creation failed: {e}")
            print(f"   Results available but animation system has issues")
    else:
        print(f"\n⚠️  Skipping animation (need at least 2 algorithms, got {len(available_algorithms)})")

    # Summary with defensive checks
    print(f"\n🎯 KEY FINDINGS:")
    if 'Smart Stop' in results and 'Traditional' in results:
        smart_time = results['Smart Stop']['metrics']['total_time']
        traditional_time = results['Traditional']['metrics']['total_time']
        improvement = ((traditional_time - smart_time) / traditional_time) * 100
        print(f"   • Smart Stop completed scenario in {smart_time:.1f} seconds")
        print(f"   • Traditional Stop took {traditional_time:.1f} seconds")
        print(f"   • Smart Stop achieved {improvement:.1f}% efficiency improvement!")
    elif available_algorithms:
        print(f"   • Successfully ran {len(available_algorithms)} algorithms:")
        for alg in available_algorithms:
            if alg in results and 'metrics' in results[alg]:
                time = results[alg]['metrics']['total_time']
                print(f"     - {alg}: {time:.1f} seconds")
    else:
        print(f"   • No algorithms completed successfully")
        return

    print(f"   • Path-based system successfully demonstrates continuous movement")
    print(f"\n🚀 SUCCESS! System is working!")


def debug_algorithm_creation():
    """Debug what happens when we create algorithms"""
    print("\n🔍 DEBUGGING ALGORITHM CREATION")
    print("=" * 40)

    try:
        from path_based_smart_stop import (
            PathBasedVehicle, FourWayGeometry, AlgorithmComparison,
            TraditionalStopAlgorithm, RoundaboutAlgorithm,
            PathBasedSmartStopAlgorithm, SmartStopSafeAlgorithm
        )
        print("✅ All classes imported successfully")

        # Test creating individual algorithms
        geometry = FourWayGeometry()
        print("✅ Geometry created")

        try:
            trad = TraditionalStopAlgorithm(geometry)
            print("✅ Traditional algorithm created")
        except Exception as e:
            print(f"❌ Traditional algorithm failed: {e}")

        try:
            round_alg = RoundaboutAlgorithm(geometry)
            print("✅ Roundabout algorithm created")
        except Exception as e:
            print(f"❌ Roundabout algorithm failed: {e}")

        try:
            smart = PathBasedSmartStopAlgorithm(geometry)
            print("✅ Smart Stop algorithm created")
        except Exception as e:
            print(f"❌ Smart Stop algorithm failed: {e}")

        try:
            safe = SmartStopSafeAlgorithm(geometry)
            print("✅ Smart Safe algorithm created")
        except Exception as e:
            print(f"❌ Smart Safe algorithm failed: {e}")

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("Some algorithm classes are missing or have errors")


if __name__ == "__main__":
    # First debug algorithm creation
    debug_algorithm_creation()

    # Then run main demo
    quick_demo()
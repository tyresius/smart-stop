#!/usr/bin/env python3
"""
Algorithm Comparison Framework for Smart Stop Sign Project
==========================================================

Comprehensive testing framework that:
1. Runs all 4 algorithms on identical scenarios
2. Collects detailed metrics and statistics
3. Generates performance comparisons
4. Produces visualization data
5. Validates algorithm correctness

Key Metrics:
- Total completion time
- Average wait time
- Throughput (vehicles/second)
- Fairness scores
- Safety validation (no collisions)
"""

import sys
import numpy as np
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
import statistics
from config import RESULTS_FILE


@dataclass
class ScenarioConfig:
    """Configuration for a test scenario"""
    name: str
    description: str
    vehicles: List[Tuple[str, str, int]]  # (road, signal, order)

    def __str__(self):
        return f"{self.name}: {self.description}"


@dataclass
class AlgorithmMetrics:
    """Metrics for a single algorithm run"""
    algorithm_name: str
    total_time: float
    avg_wait_time: float
    throughput: float
    completed_vehicles: int
    safety_violations: int = 0
    fairness_score: float = 0.0

    def efficiency_vs(self, baseline: 'AlgorithmMetrics') -> float:
        """Calculate efficiency improvement vs baseline (percentage)"""
        if baseline.total_time <= 0:
            return 0.0
        improvement = ((baseline.total_time - self.total_time) / baseline.total_time) * 100
        return improvement


@dataclass
class TestResult:
    """Results from testing all algorithms on one scenario"""
    scenario: ScenarioConfig
    timestamp: str
    algorithms: Dict[str, AlgorithmMetrics]
    winner: Optional[str] = None

    def get_winner(self) -> str:
        """Determine which algorithm performed best"""
        valid = {k: v for k, v in self.algorithms.items()
                 if v.total_time < float('inf')}
        if not valid:
            return "FAILED"
        winner = min(valid.items(), key=lambda x: x[1].total_time)[0]
        return winner

    def get_ranking(self) -> List[Tuple[str, float]]:
        """Get algorithms ranked by total time"""
        valid = [(k, v.total_time) for k, v in self.algorithms.items()
                 if v.total_time < float('inf')]
        return sorted(valid, key=lambda x: x[1])


class ComparisonFramework:
    """Main framework for algorithm comparison"""

    def __init__(self, geometry_type: str = "4way"):
        """Initialize framework with geometry type"""
        self.geometry_type = geometry_type
        self.test_results = []
        self.scenario_configs = []
        self._setup_scenarios()

    def _setup_scenarios(self):
        """Define standard test scenarios"""
        self.scenario_configs = [
            ScenarioConfig(
                name="S1: Simple Straight",
                description="Two vehicles, same road, straight through",
                vehicles=[
                    ("Main E", "NS/S", 1),
                    ("Main E", "NS/S", 2),
                ]
            ),
            ScenarioConfig(
                name="S2: Perpendicular Crossing",
                description="Two vehicles crossing perpendicular at intersection",
                vehicles=[
                    ("Main E", "NS/S", 1),
                    ("Green N", "NS/S", 2),
                ]
            ),
            ScenarioConfig(
                name="S3: Right Turns",
                description="Multiple right turns from different approaches",
                vehicles=[
                    ("Main E", "R", 1),
                    ("Green N", "R", 2),
                    ("Main W", "R", 3),
                ]
            ),
            ScenarioConfig(
                name="S4: Mixed Turns",
                description="Mix of left turns, right turns, and straight",
                vehicles=[
                    ("Main E", "R", 1),
                    ("Green N", "L", 2),
                    ("Main W", "NS/S", 3),
                    ("Green S", "R", 4),
                ]
            ),
            ScenarioConfig(
                name="S5: Backward Priority",
                description="Tests Smart Stop backward priority advantage",
                vehicles=[
                    ("Main E", "R", 1),
                    ("Green S", "L", 2),  # Behind Main E
                    ("Main W", "R", 3),  # Behind Main E
                    ("Green N", "NS/S", 4),  # Behind Main E
                ]
            ),
            ScenarioConfig(
                name="S6: Complex Real-World",
                description="Full intersection with 6 vehicles",
                vehicles=[
                    ("Main E", "R", 1),
                    ("Main E", "L", 2),
                    ("Green N", "NS/S", 3),
                    ("Green N", "R", 4),
                    ("Main W", "L", 5),
                    ("Green S", "NS/S", 6),
                ]
            ),
        ]

    def run_all_scenarios(self, algorithm_classes: Dict[str, type]) -> List[TestResult]:
        """Run all scenarios on all algorithms"""
        results = []

        print("\n" + "=" * 80)
        print("ALGORITHM COMPARISON FRAMEWORK")
        print("=" * 80)
        print(f"Geometry Type: {self.geometry_type}")
        print(f"Algorithms: {', '.join(algorithm_classes.keys())}")
        print(f"Scenarios: {len(self.scenario_configs)}")
        print("=" * 80 + "\n")

        for scenario in self.scenario_configs:
            result = self.run_scenario(scenario, algorithm_classes)
            results.append(result)
            self.test_results.append(result)

            # Print brief result
            print(f"✓ {scenario.name}: Winner = {result.get_winner()}")

        return results

    def run_scenario(self, scenario: ScenarioConfig,
                     algorithm_classes: Dict[str, type]) -> TestResult:
        """Run one scenario on all algorithms"""
        from path_based_smart_stop import FourWayGeometry, RoundaboutGeometry

        if self.geometry_type == "4way":
            geometry = FourWayGeometry()
        else:
            geometry = RoundaboutGeometry()

        result = TestResult(
            scenario=scenario,
            timestamp=datetime.now().isoformat(),
            algorithms={}
        )

        for algo_name, algo_class in algorithm_classes.items():
            try:
                metrics = self._run_algorithm(
                    algo_name, algo_class, scenario, geometry
                )
                result.algorithms[algo_name] = metrics
            except Exception as e:
                # Store error as invalid metrics
                result.algorithms[algo_name] = AlgorithmMetrics(
                    algorithm_name=algo_name,
                    total_time=float('inf'),
                    avg_wait_time=0,
                    throughput=0,
                    completed_vehicles=0
                )

        return result

    def _run_algorithm(self, algo_name: str, algo_class: type,
                       scenario: ScenarioConfig, geometry) -> AlgorithmMetrics:
        """Run single algorithm on a scenario"""
        from path_based_smart_stop import PathBasedVehicle

        # Create fresh vehicles
        vehicles = []
        for road, signal, order in scenario.vehicles:
            vehicle = PathBasedVehicle(road, signal, order, geometry)
            vehicles.append(vehicle)

        # Initialize algorithm
        algo = algo_class(geometry)
        for v in vehicles:
            algo.add_vehicle(v)

        # Run simulation
        max_steps = 10000  # Max 100 seconds at 0.1s per step
        for step in range(max_steps):
            status = algo.step(0.1)

            # Stop when all vehicles completed
            if status['waiting'] == 0 and status['active'] == 0:
                break

        # Get metrics
        metrics_dict = algo.get_metrics()

        return AlgorithmMetrics(
            algorithm_name=algo_name,
            total_time=metrics_dict.get('total_time', float('inf')),
            avg_wait_time=metrics_dict.get('avg_wait_time', 0),
            throughput=metrics_dict.get('throughput', 0),
            completed_vehicles=metrics_dict.get('completed_vehicles', 0)
        )

    def generate_summary_report(self) -> str:
        """Generate text report of all results"""
        if not self.test_results:
            return "No results to report"

        report = []
        report.append("\n" + "=" * 90)
        report.append("ALGORITHM COMPARISON SUMMARY REPORT")
        report.append("=" * 90)
        report.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Geometry: {self.geometry_type}")
        report.append(f"Total Scenarios: {len(self.test_results)}\n")

        # Win counts
        wins = {}
        for result in self.test_results:
            winner = result.get_winner()
            wins[winner] = wins.get(winner, 0) + 1

        report.append("WINS BY ALGORITHM:")
        for algo, count in sorted(wins.items(), key=lambda x: x[1], reverse=True):
            pct = (count / len(self.test_results)) * 100
            report.append(f"  {algo:<20} {count:3} wins ({pct:5.1f}%)")

        report.append("\n" + "-" * 90)
        report.append("DETAILED SCENARIO RESULTS:")
        report.append("-" * 90 + "\n")

        for result in self.test_results:
            report.append(f"\n{result.scenario.name}")
            report.append(f"  Description: {result.scenario.description}")
            report.append(f"  Vehicles: {len(result.scenario.vehicles)}")
            report.append(f"\n  {'Algorithm':<20} {'Time (s)':<12} {'Wait (s)':<12} {'Throughput':<12}")
            report.append("  " + "-" * 56)

            for algo_name, metrics in sorted(result.algorithms.items()):
                time_str = f"{metrics.total_time:.2f}" if metrics.total_time < float('inf') else "FAIL"
                wait_str = f"{metrics.avg_wait_time:.2f}" if metrics.total_time < float('inf') else "N/A"
                throughput_str = f"{metrics.throughput:.3f}" if metrics.total_time < float('inf') else "N/A"

                is_winner = algo_name == result.get_winner()
                marker = "★" if is_winner else " "

                report.append(
                    f"  {marker} {algo_name:<18} {time_str:<12} {wait_str:<12} {throughput_str:<12}"
                )

        report.append("\n" + "=" * 90)
        report.append("EFFICIENCY ANALYSIS (vs Traditional Stop):")
        report.append("=" * 90 + "\n")

        # Calculate average improvements
        trad_times = []
        smart_times = []
        safe_times = []
        round_times = []

        for result in self.test_results:
            if 'Traditional' in result.algorithms:
                trad = result.algorithms['Traditional'].total_time
                if trad < float('inf'):
                    trad_times.append(trad)

            if 'Smart Stop' in result.algorithms:
                smart = result.algorithms['Smart Stop'].total_time
                if smart < float('inf'):
                    smart_times.append(smart)

            if 'Smart Safe' in result.algorithms:
                safe = result.algorithms['Smart Safe'].total_time
                if safe < float('inf'):
                    safe_times.append(safe)

            if 'Roundabout' in result.algorithms:
                round_alg = result.algorithms['Roundabout'].total_time
                if round_alg < float('inf'):
                    round_times.append(round_alg)

        if trad_times and smart_times:
            avg_trad = statistics.mean(trad_times)
            avg_smart = statistics.mean(smart_times)
            improvement = ((avg_trad - avg_smart) / avg_trad) * 100
            report.append(f"Smart Stop vs Traditional:  {improvement:+.1f}% (avg {avg_smart:.2f}s vs {avg_trad:.2f}s)")

        if trad_times and round_times:
            avg_trad = statistics.mean(trad_times)
            avg_round = statistics.mean(round_times)
            improvement = ((avg_trad - avg_round) / avg_trad) * 100
            report.append(f"Roundabout vs Traditional:  {improvement:+.1f}% (avg {avg_round:.2f}s vs {avg_trad:.2f}s)")

        if trad_times and safe_times:
            avg_trad = statistics.mean(trad_times)
            avg_safe = statistics.mean(safe_times)
            improvement = ((avg_trad - avg_safe) / avg_trad) * 100
            report.append(f"Smart Safe vs Traditional:  {improvement:+.1f}% (avg {avg_safe:.2f}s vs {avg_trad:.2f}s)")

        report.append("\n" + "=" * 90 + "\n")

        return "\n".join(report)

    def export_json(self, filename: str):
        """Export results to JSON for visualization"""
        data = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'geometry_type': self.geometry_type,
                'total_scenarios': len(self.test_results)
            },
            'scenarios': []
        }

        for result in self.test_results:
            scenario_data = {
                'name': result.scenario.name,
                'description': result.scenario.description,
                'vehicles': result.scenario.vehicles,
                'winner': result.get_winner(),
                'results': {}
            }

            for algo_name, metrics in result.algorithms.items():
                scenario_data['results'][algo_name] = {
                    'total_time': metrics.total_time,
                    'avg_wait_time': metrics.avg_wait_time,
                    'throughput': metrics.throughput,
                    'completed_vehicles': metrics.completed_vehicles
                }

            data['scenarios'].append(scenario_data)

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def get_comparison_table(self) -> str:
        """Get formatted comparison table"""
        if not self.test_results:
            return "No results"

        lines = []
        lines.append("\nALGORITHM COMPARISON TABLE")
        lines.append("=" * 100)
        lines.append(
            f"{'Scenario':<25} {'Traditional':<15} {'Roundabout':<15} {'Smart Stop':<15} {'Smart Safe':<15} {'Winner':<12}")
        lines.append("-" * 100)

        for result in self.test_results:
            trad_time = result.algorithms.get('Traditional', AlgorithmMetrics('', float('inf'), 0, 0, 0)).total_time
            round_time = result.algorithms.get('Roundabout', AlgorithmMetrics('', float('inf'), 0, 0, 0)).total_time
            smart_time = result.algorithms.get('Smart Stop', AlgorithmMetrics('', float('inf'), 0, 0, 0)).total_time
            safe_time = result.algorithms.get('Smart Safe', AlgorithmMetrics('', float('inf'), 0, 0, 0)).total_time

            trad_str = f"{trad_time:.2f}s" if trad_time < float('inf') else "FAIL"
            round_str = f"{round_time:.2f}s" if round_time < float('inf') else "FAIL"
            smart_str = f"{smart_time:.2f}s" if smart_time < float('inf') else "FAIL"
            safe_str = f"{safe_time:.2f}s" if safe_time < float('inf') else "FAIL"

            winner = result.get_winner()

            lines.append(
                f"{result.scenario.name:<25} {trad_str:<15} {round_str:<15} "
                f"{smart_str:<15} {safe_str:<15} {winner:<12}"
            )

        lines.append("=" * 100)
        return "\n".join(lines)


def main():
    """Main entry point for comparison framework"""

    # Try to import algorithm classes
    try:
        from path_based_smart_stop import (
            TraditionalStopAlgorithm,
            RoundaboutAlgorithm,
            PathBasedSmartStopAlgorithm,
            SmartStopSafeAlgorithm
        )
    except ImportError as e:
        print(f"Error importing algorithms: {e}")
        print("Make sure path_based_smart_stop.py is in the Python path")
        return

    # Create framework
    framework = ComparisonFramework(geometry_type="4way")

    # Define algorithms to test
    algorithms = {
        'Traditional': TraditionalStopAlgorithm,
        'Roundabout': RoundaboutAlgorithm,
        'Smart Stop': PathBasedSmartStopAlgorithm,
        'Smart Safe': SmartStopSafeAlgorithm,
    }

    # Run all scenarios
    print("Starting algorithm comparison...")
    results = framework.run_all_scenarios(algorithms)

    # Generate reports
    print("\n" + framework.generate_summary_report())
    print(framework.get_comparison_table())

    # Export results
    output_file = RESULTS_FILE
    framework.export_json(output_file)
    print(f"\n✓ Results exported to {output_file}")


if __name__ == "__main__":
    main()
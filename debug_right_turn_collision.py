#!/usr/bin/env python3
"""
Debug Right-Turn Collision Detection
=====================================

Why aren't two right-turning vehicles from perpendicular approaches
being activated simultaneously?

Car1: Main E → Right (turning to Green S)
Car2: Green N → Right (turning to Main W)

These paths should NOT intersect!
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from path_based_smart_stop import (
    PathBasedVehicle, FourWayGeometry, CollisionDetector
)

print("=" * 80)
print("DEBUGGING RIGHT-TURN COLLISION DETECTION")
print("=" * 80)
print()

geometry = FourWayGeometry()

# Create the two vehicles
car1 = PathBasedVehicle("Main E", "R", 1, geometry)
car2 = PathBasedVehicle("Green N", "R", 2, geometry)

print("Vehicles:")
print(f"  Car1: {car1.road_name} → {car1.signal} (to Green S)")
print(f"  Car2: {car2.road_name} → {car2.signal} (to Main W)")
print()

# Check their paths
print("Path Information:")
print("-" * 60)
print(f"Car1 path: {len(car1.path_x)} points")
print(f"  Start: ({car1.path_x[0]:.2f}, {car1.path_y[0]:.2f})")
print(f"  End:   ({car1.path_x[-1]:.2f}, {car1.path_y[-1]:.2f})")
print()
print(f"Car2 path: {len(car2.path_x)} points")
print(f"  Start: ({car2.path_x[0]:.2f}, {car2.path_y[0]:.2f})")
print(f"  End:   ({car2.path_x[-1]:.2f}, {car2.path_y[-1]:.2f})")
print()

# Activate both vehicles (simulate them being active)
car1.activate(0.0)
car2.activate(0.0)

# Check collision
detector = CollisionDetector(safety_margin=3.0)
collision = detector.check_collision(car1, car2, time_horizon=3.0)

print("Collision Detection:")
print("-" * 60)
print(f"Safety margin: {detector.safety_margin} units")
print(f"Collision detected: {collision}")
print()

if collision:
    print("⚠️  COLLISION DETECTED - Why?")
    print("\nLet's trace through the paths to find where they get too close:\n")

    # Find minimum distance along paths
    min_distance = float('inf')
    min_idx1 = 0
    min_idx2 = 0

    # Sample every 10th point to speed up
    for i in range(0, len(car1.path_x), 10):
        for j in range(0, len(car2.path_x), 10):
            dist = np.sqrt((car1.path_x[i] - car2.path_x[j])**2 +
                          (car1.path_y[i] - car2.path_y[j])**2)
            if dist < min_distance:
                min_distance = dist
                min_idx1 = i
                min_idx2 = j

    print(f"Minimum distance between paths: {min_distance:.2f} units")
    print(f"  Car1 at point {min_idx1}: ({car1.path_x[min_idx1]:.2f}, {car1.path_y[min_idx1]:.2f})")
    print(f"  Car2 at point {min_idx2}: ({car2.path_x[min_idx2]:.2f}, {car2.path_y[min_idx2]:.2f})")
    print()

    if min_distance < detector.safety_margin:
        print(f"✗ Minimum distance ({min_distance:.2f}) < Safety margin ({detector.safety_margin})")
        print("  → Paths get too close, triggering collision detection")
    else:
        print(f"✓ Minimum distance ({min_distance:.2f}) >= Safety margin ({detector.safety_margin})")
        print("  → This should NOT trigger collision (may be time-based prediction issue)")

else:
    print("✓ NO COLLISION - Vehicles can move simultaneously!")

# Visualize the paths
print("\n" + "=" * 80)
print("VISUALIZING PATHS")
print("=" * 80)

fig, ax = plt.subplots(figsize=(10, 10))
ax.set_xlim(-2.5, 2.5)
ax.set_ylim(-2.5, 2.5)
ax.set_aspect('equal')
ax.grid(True, alpha=0.3)
ax.set_title('Right-Turn Path Collision Analysis', fontsize=14, fontweight='bold')

# Draw intersection
from matplotlib.patches import Rectangle
intersection = Rectangle((-1.35, -1.35), 2.7, 2.7,
                        fill=False, edgecolor='black', linewidth=2)
ax.add_patch(intersection)

# Draw paths
ax.plot(car1.path_x, car1.path_y, 'b-', linewidth=2, label='Car1: Main E → R', alpha=0.7)
ax.plot(car2.path_x, car2.path_y, 'r-', linewidth=2, label='Car2: Green N → R', alpha=0.7)

# Mark start and end points
ax.plot(car1.path_x[0], car1.path_y[0], 'bo', markersize=10, label='Car1 start')
ax.plot(car1.path_x[-1], car1.path_y[-1], 'bs', markersize=10, label='Car1 end')
ax.plot(car2.path_x[0], car2.path_y[0], 'ro', markersize=10, label='Car2 start')
ax.plot(car2.path_x[-1], car2.path_y[-1], 'rs', markersize=10, label='Car2 end')

# Mark closest approach point
if collision:
    ax.plot(car1.path_x[min_idx1], car1.path_y[min_idx1], 'g*', markersize=15,
            label=f'Closest point ({min_distance:.2f} units)')
    ax.plot(car2.path_x[min_idx2], car2.path_y[min_idx2], 'g*', markersize=15)

    # Draw line between closest points
    ax.plot([car1.path_x[min_idx1], car2.path_x[min_idx2]],
            [car1.path_y[min_idx1], car2.path_y[min_idx2]],
            'g--', linewidth=2, label='Min distance')

    # Draw safety margin circles at closest point
    circle1 = Circle((car1.path_x[min_idx1], car1.path_y[min_idx1]),
                     detector.safety_margin, fill=False,
                     edgecolor='blue', linestyle='--', linewidth=1, alpha=0.5)
    circle2 = Circle((car2.path_x[min_idx2], car2.path_y[min_idx2]),
                     detector.safety_margin, fill=False,
                     edgecolor='red', linestyle='--', linewidth=1, alpha=0.5)
    ax.add_patch(circle1)
    ax.add_patch(circle2)

# Add labels
ax.text(-2, 0, 'Main W', ha='center', va='center', fontsize=10,
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
ax.text(2, 0, 'Main E', ha='center', va='center', fontsize=10,
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
ax.text(0, 2, 'Green N', ha='center', va='center', fontsize=10,
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
ax.text(0, -2, 'Green S', ha='center', va='center', fontsize=10,
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

ax.legend(loc='upper right', fontsize=9)
plt.tight_layout()
plt.savefig('output/right_turn_paths.png', dpi=150)
print("\n✅ Path visualization saved to: output/right_turn_paths.png")
print()

# Summary and recommendations
print("=" * 80)
print("SUMMARY & RECOMMENDATIONS")
print("=" * 80)
print()

if collision:
    print("⚠️  PROBLEM IDENTIFIED:")
    print(f"   Right-turn paths from perpendicular approaches get within")
    print(f"   {min_distance:.2f} units of each other, which is less than the")
    print(f"   safety margin of {detector.safety_margin} units.")
    print()
    print("   This prevents Smart Stop from activating both vehicles")
    print("   simultaneously, even though their actual paths don't intersect.")
    print()
    print("SOLUTIONS:")
    print()
    print("1. REDUCE SAFETY MARGIN for right turns")
    print("   - Right turns are lower risk (no crossing paths)")
    print("   - Could use safety_margin = 2.0 instead of 3.0")
    print()
    print("2. TURN-AWARE COLLISION DETECTION")
    print("   - Check turn signals before collision detection")
    print("   - Two right turns from perpendicular approaches = safe")
    print("   - Only check collision for conflicting turn combinations")
    print()
    print("3. PATH INTERSECTION instead of DISTANCE")
    print("   - Check if paths actually intersect (geometrically)")
    print("   - Distance-based check is too conservative")
    print()
    print("RECOMMENDED: Option 2 (Turn-Aware)")
    print("  - Most intuitive and realistic")
    print("  - Aligns with real traffic rules")
    print("  - Biggest performance improvement for Smart Stop")
else:
    print("✓ No collision detected - vehicles should activate simultaneously")
    print("  If they're not, the issue is in the coordination logic, not")
    print("  collision detection.")

print()
print("=" * 80)

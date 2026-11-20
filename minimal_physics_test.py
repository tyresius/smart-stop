# minimal_physics_test.py
from path_based_smart_stop import PathBasedVehicle, FourWayGeometry

geometry = FourWayGeometry()

# Test just the vehicle physics, no algorithms
vehicles = [
    PathBasedVehicle("Main E", "NS/S", 1, geometry, use_roundabout_paths=False),
    PathBasedVehicle("Main E", "NS/S", 1, geometry, use_roundabout_paths=True),
]

print("=== PURE PHYSICS TEST (No Algorithms) ===")
for i, vehicle in enumerate(vehicles):
    vehicle.activate(0.0)
    path_type = "4-way" if i == 0 else "roundabout"
    print(f"\n{path_type} vehicle:")
    print(f"  Path length: {vehicle.path_length_meters:.3f}m")

    # Manually step physics with identical conditions
    for step in range(60):
        still_active = vehicle.update(0.1)  # Same target_speed for both
        if step % 10 == 0:
            print(f"  Step {step}: pos={vehicle.current_position_meters:.3f}")
        if not still_active:
            print(f"  Completed at step {step}")
            break
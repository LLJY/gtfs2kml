#!/usr/bin/env python3
"""
Example: Using road snapping and path densification with gtfs2kml.

This demonstrates the Python API for enhanced route visualization.
"""

from pathlib import Path
import sys

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gtfs2kml import GTFSParser, KMLGenerator
from gtfs2kml.road_snapper import RoadSnapper, PathDensifier, calculate_path_distance


def example_basic_densification():
    """Example 1: Add points every 100m without road snapping."""
    print("=" * 60)
    print("Example 1: Path Densification (100m intervals)")
    print("=" * 60)

    # Parse GTFS
    parser = GTFSParser(Path("../../"))  # Assuming we're in examples/
    routes = parser.parse()

    # Get first route
    route = list(routes.values())[0]
    original_shape = route.shapes[0] if route.shapes else None

    if not original_shape:
        print("No shapes found!")
        return

    print(f"Route: {route.display_name}")
    print(f"Original points: {original_shape.coordinate_count}")
    print(f"Original distance: {calculate_path_distance(original_shape):.0f}m")

    # Densify path
    densifier = PathDensifier(interval_meters=100.0)
    densified_shape = densifier.densify_shape(original_shape)

    print(f"Densified points: {densified_shape.coordinate_count}")
    print(f"Points added: {densified_shape.coordinate_count - original_shape.coordinate_count}")

    # Generate KML
    route.shapes = [densified_shape]
    generator = KMLGenerator()
    output_path = Path("./output_densified.kml")
    generator.generate_route_kml(route, output_path)

    print(f"✓ Saved to {output_path}")
    print()


def example_road_snapping_osrm():
    """Example 2: Snap to roads using free OSRM service."""
    print("=" * 60)
    print("Example 2: Road Snapping with OSRM (Free)")
    print("=" * 60)

    # Parse GTFS
    parser = GTFSParser(Path("../../"))
    routes = parser.parse()

    # Get a route with fewer points for faster demo
    route = list(routes.values())[2]  # Third route
    original_shape = route.shapes[0] if route.shapes else None

    if not original_shape:
        print("No shapes found!")
        return

    print(f"Route: {route.display_name}")
    print(f"Original points: {original_shape.coordinate_count}")

    # Snap to roads
    try:
        snapper = RoadSnapper(
            provider="osrm",
            cache_dir=Path("./snap_cache")
        )

        print("Snapping to roads (this may take a moment)...")
        snapped_shape = snapper.snap_shape(original_shape)

        print(f"Snapped points: {snapped_shape.coordinate_count}")
        print(f"✓ Route snapped to actual roads")

        # Generate KML
        route.shapes = [snapped_shape]
        generator = KMLGenerator()
        output_path = Path("./output_snapped.kml")
        generator.generate_route_kml(route, output_path)

        print(f"✓ Saved to {output_path}")

    except Exception as e:
        print(f"✗ Snapping failed: {e}")
        print("Note: OSRM public server has rate limits. Try again in a moment.")

    print()


def example_combined():
    """Example 3: Combine snapping and densification."""
    print("=" * 60)
    print("Example 3: Combined - Snap + Densify")
    print("=" * 60)

    # Parse GTFS
    parser = GTFSParser(Path("../../"))
    routes = parser.parse()

    # Get route
    route = list(routes.values())[1]
    original_shape = route.shapes[0] if route.shapes else None

    if not original_shape:
        print("No shapes found!")
        return

    print(f"Route: {route.display_name}")
    print(f"Step 1: Original - {original_shape.coordinate_count} points")

    try:
        # Step 1: Snap to roads
        snapper = RoadSnapper(
            provider="osrm",
            cache_dir=Path("./snap_cache")
        )

        print("Step 2: Snapping to roads...")
        snapped_shape = snapper.snap_shape(original_shape)
        print(f"        After snap - {snapped_shape.coordinate_count} points")

        # Step 2: Densify
        densifier = PathDensifier(interval_meters=100.0)

        print("Step 3: Densifying path (100m intervals)...")
        final_shape = densifier.densify_shape(snapped_shape)
        print(f"        After densify - {final_shape.coordinate_count} points")

        # Step 3: Generate KML
        route.shapes = [final_shape]
        generator = KMLGenerator()
        output_path = Path("./output_combined.kml")
        generator.generate_route_kml(route, output_path)

        print(f"✓ Saved to {output_path}")
        print(f"✓ Total distance: {calculate_path_distance(final_shape)/1000:.2f} km")

    except Exception as e:
        print(f"✗ Processing failed: {e}")

    print()


def example_comparison():
    """Example 4: Compare all routes before/after."""
    print("=" * 60)
    print("Example 4: Full Route Comparison")
    print("=" * 60)

    # Parse GTFS
    parser = GTFSParser(Path("../../"))
    routes = parser.parse()

    print(f"Analyzing {len(routes)} routes...\n")
    print(f"{'Route':<15} {'Original':<12} {'Distance (km)':<15}")
    print("-" * 50)

    for route in list(routes.values())[:5]:  # First 5 routes
        if not route.shapes:
            continue

        shape = route.shapes[0]
        distance = calculate_path_distance(shape) / 1000

        print(f"{route.display_name:<15} {shape.coordinate_count:<12} {distance:<15.2f}")

    print("\nUse CLI for batch processing:")
    print("  gtfs2kml ../../ ./output --snap-to-roads --densify-points 100")
    print()


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("GTFS2KML - Road Snapping & Densification Examples")
    print("=" * 60)
    print()

    examples = [
        ("1", "Path Densification", example_basic_densification),
        ("2", "Road Snapping (OSRM)", example_road_snapping_osrm),
        ("3", "Combined Processing", example_combined),
        ("4", "Route Comparison", example_comparison),
    ]

    print("Available examples:")
    for num, name, _ in examples:
        print(f"  {num}. {name}")

    print("\nSelect example (1-4) or 'all': ", end="")
    choice = input().strip()

    print()

    if choice == "all":
        for _, _, func in examples:
            try:
                func()
            except Exception as e:
                print(f"Error: {e}\n")
    elif choice in ["1", "2", "3", "4"]:
        idx = int(choice) - 1
        try:
            examples[idx][2]()
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Invalid choice!")

    print("=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

"""
Example usage of gtfs2kml Python API.

This demonstrates how to use gtfs2kml programmatically instead of via CLI.
"""

from pathlib import Path
from gtfs2kml import GTFSParser, KMLGenerator


def example_basic_usage():
    """Basic example: Convert all routes to individual KML files."""
    print("Example 1: Basic conversion of all routes")

    # Parse GTFS feed
    gtfs_dir = Path("./gtfs_data")
    parser = GTFSParser(gtfs_dir)
    routes = parser.parse()

    print(f"Parsed {len(routes)} routes")

    # Generate KML files
    generator = KMLGenerator(line_width=4, include_stops=True)
    output_dir = Path("./output")

    output_files = generator.generate_batch(
        routes=list(routes.values()),
        output_dir=output_dir,
        split_by_route=True
    )

    print(f"Generated {len(output_files)} KML files")


def example_filter_routes():
    """Example: Convert only specific routes."""
    print("\nExample 2: Filter specific routes")

    gtfs_dir = Path("./gtfs_data")
    parser = GTFSParser(gtfs_dir)

    # Parse only specific routes
    route_filter = {'route_1', 'route_2', 'route_express'}
    routes = parser.parse(route_filter=route_filter)

    print(f"Parsed {len(routes)} filtered routes")

    # Generate combined KML
    generator = KMLGenerator()
    output_file = Path("./output/selected_routes.kml")

    generator.generate_all_routes_kml(
        routes=list(routes.values()),
        output_path=output_file
    )

    print(f"Generated {output_file}")


def example_custom_styling():
    """Example: Custom styling options."""
    print("\nExample 3: Custom styling")

    gtfs_dir = Path("./gtfs_data")
    parser = GTFSParser(gtfs_dir)
    routes = parser.parse()

    # Create generator with custom settings
    generator = KMLGenerator(
        line_width=6,           # Thicker lines
        include_stops=False,    # No stop markers
        altitude_mode='relativeToGround'  # Different altitude mode
    )

    output_dir = Path("./output_custom")
    generator.generate_batch(
        routes=list(routes.values()),
        output_dir=output_dir,
        split_by_route=False  # Single file
    )

    print("Generated custom styled KML")


def example_inspect_route_data():
    """Example: Inspect parsed route data before generating KML."""
    print("\nExample 4: Inspect route data")

    gtfs_dir = Path("./gtfs_data")
    parser = GTFSParser(gtfs_dir)
    routes = parser.parse()

    for route_id, route in routes.items():
        print(f"\nRoute: {route.display_name}")
        print(f"  ID: {route.route_id}")
        print(f"  Type: {route.route_type}")
        print(f"  Color: #{route.route_color}")
        print(f"  Trips: {len(route.trips)}")
        print(f"  Shapes: {len(route.shapes)}")
        print(f"  Stops: {len(route.stops)}")

        # Inspect shape details
        for idx, shape in enumerate(route.shapes[:1]):  # First shape only
            print(f"  Shape {idx + 1}: {shape.coordinate_count} points")


def example_single_route():
    """Example: Generate KML for a single route."""
    print("\nExample 5: Single route")

    gtfs_dir = Path("./gtfs_data")
    parser = GTFSParser(gtfs_dir)
    routes = parser.parse()

    # Get first route
    if routes:
        route = list(routes.values())[0]
        print(f"Generating KML for route: {route.display_name}")

        generator = KMLGenerator()
        output_file = Path(f"./output/{route.safe_filename}.kml")

        generator.generate_route_kml(
            route=route,
            output_path=output_file,
            include_multiple_shapes=True
        )

        print(f"Generated {output_file}")


if __name__ == "__main__":
    # Run examples (comment out the ones you don't want to run)

    try:
        example_basic_usage()
    except Exception as e:
        print(f"Example 1 failed: {e}")

    try:
        example_filter_routes()
    except Exception as e:
        print(f"Example 2 failed: {e}")

    try:
        example_custom_styling()
    except Exception as e:
        print(f"Example 3 failed: {e}")

    try:
        example_inspect_route_data()
    except Exception as e:
        print(f"Example 4 failed: {e}")

    try:
        example_single_route()
    except Exception as e:
        print(f"Example 5 failed: {e}")

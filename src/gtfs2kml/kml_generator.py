"""
KML file generator for GTFS routes.

This module handles converting Route objects into KML format files.
"""

import logging
from pathlib import Path
from typing import List, Optional

try:
    import simplekml
except ImportError:
    raise ImportError(
        "simplekml is required. Install it with: pip install simplekml"
    )

from .models import Route

logger = logging.getLogger(__name__)


class KMLGenerator:
    """
    Generator for KML files from GTFS route data.

    Converts Route objects with shapes and stops into KML format
    for visualization in mapping tools like Google Earth.
    """

    def __init__(
        self,
        line_width: int = 4,
        include_stops: bool = True,
        altitude_mode: str = 'clampToGround'
    ):
        """
        Initialize KML generator.

        Args:
            line_width: Width of route lines in pixels
            include_stops: Whether to include stop markers in output
            altitude_mode: KML altitude mode (clampToGround, relativeToGround, absolute)
        """
        self.line_width = line_width
        self.include_stops = include_stops
        self.altitude_mode = altitude_mode

    def generate_route_kml(
        self,
        route: Route,
        output_path: Path,
        include_multiple_shapes: bool = True
    ) -> None:
        """
        Generate a KML file for a single route.

        Args:
            route: Route object to convert
            output_path: Path where KML file will be saved
            include_multiple_shapes: If True, include all shape variants (directions)
        """
        logger.info(f"Generating KML for route {route.display_name}")

        kml = simplekml.Kml()
        kml.document.name = f"Route {route.display_name}"

        # Add route description
        if route.route_desc:
            kml.document.description = route.route_desc

        # Create folders for organization
        if route.has_shapes:
            shapes_folder = kml.newfolder(name="Route Paths")
            self._add_shapes_to_folder(shapes_folder, route, include_multiple_shapes)

        if self.include_stops and route.has_stops:
            stops_folder = kml.newfolder(name="Stops")
            self._add_stops_to_folder(stops_folder, route)

        # Save KML file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        kml.save(str(output_path))
        logger.info(f"Saved KML to {output_path}")

    def generate_all_routes_kml(
        self,
        routes: List[Route],
        output_path: Path
    ) -> None:
        """
        Generate a single KML file containing all routes.

        Args:
            routes: List of Route objects to include
            output_path: Path where KML file will be saved
        """
        logger.info(f"Generating combined KML for {len(routes)} routes")

        kml = simplekml.Kml()
        kml.document.name = "All Routes"

        for route in routes:
            # Create a folder for each route
            route_folder = kml.newfolder(name=f"Route {route.display_name}")

            if route.route_desc:
                route_folder.description = route.route_desc

            # Add shapes
            if route.has_shapes:
                shapes_folder = route_folder.newfolder(name="Paths")
                self._add_shapes_to_folder(shapes_folder, route, include_multiple_shapes=True)

            # Add stops
            if self.include_stops and route.has_stops:
                stops_folder = route_folder.newfolder(name="Stops")
                self._add_stops_to_folder(stops_folder, route)

        # Save KML file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        kml.save(str(output_path))
        logger.info(f"Saved combined KML to {output_path}")

    def _add_shapes_to_folder(
        self,
        folder: simplekml.Folder,
        route: Route,
        include_multiple_shapes: bool
    ) -> None:
        """
        Add route shapes to a KML folder.

        Args:
            folder: KML folder to add shapes to
            route: Route containing shapes
            include_multiple_shapes: If False, only add first shape
        """
        shapes_to_add = route.shapes if include_multiple_shapes else route.shapes[:1]

        for idx, shape in enumerate(shapes_to_add):
            if shape.coordinate_count == 0:
                logger.warning(f"Shape {shape.shape_id} has no coordinates")
                continue

            # Create line
            linestring = folder.newlinestring()

            # Set name (include shape_id if multiple shapes)
            if len(shapes_to_add) > 1:
                linestring.name = f"{route.display_name} - Variant {idx + 1}"
            else:
                linestring.name = route.display_name

            # Set coordinates (KML expects lon, lat, altitude)
            linestring.coords = shape.kml_coordinates

            # Set style
            linestring.style.linestyle.color = route.kml_color
            linestring.style.linestyle.width = self.line_width

            # Set altitude mode
            linestring.altitudemode = self.altitude_mode

            logger.debug(
                f"Added shape {shape.shape_id} with {shape.coordinate_count} points"
            )

    def _add_stops_to_folder(
        self,
        folder: simplekml.Folder,
        route: Route
    ) -> None:
        """
        Add route stops to a KML folder.

        Args:
            folder: KML folder to add stops to
            route: Route containing stops
        """
        # Create a single shared style object for all stops
        # All points will reference this same style object
        shared_style = simplekml.Style()
        shared_style.iconstyle.color = route.kml_color
        shared_style.iconstyle.scale = 0.8
        shared_style.iconstyle.icon.href = (
            "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"
        )

        for stop in route.stops:
            point = folder.newpoint()
            point.name = stop.stop_name
            point.coords = [stop.kml_coordinates]

            # Add description with stop details
            description_parts = [f"Stop ID: {stop.stop_id}"]
            if stop.stop_code:
                description_parts.append(f"Stop Code: {stop.stop_code}")
            point.description = "\n".join(description_parts)

            # Assign the shared style object
            point.style = shared_style

        logger.debug(f"Added {len(route.stops)} stops")

    def generate_batch(
        self,
        routes: List[Route],
        output_dir: Path,
        split_by_route: bool = True
    ) -> List[Path]:
        """
        Generate KML files for multiple routes.

        Args:
            routes: List of routes to process
            output_dir: Directory where KML files will be saved
            split_by_route: If True, create one file per route. If False, create single file.

        Returns:
            List of paths to generated KML files
        """
        output_files = []

        if split_by_route:
            logger.info(f"Generating {len(routes)} KML files (one per route)")
            for route in routes:
                filename = f"{route.safe_filename}.kml"
                output_path = output_dir / filename
                self.generate_route_kml(route, output_path)
                output_files.append(output_path)
        else:
            logger.info(f"Generating single KML file with {len(routes)} routes")
            output_path = output_dir / "all_routes.kml"
            self.generate_all_routes_kml(routes, output_path)
            output_files.append(output_path)

        return output_files

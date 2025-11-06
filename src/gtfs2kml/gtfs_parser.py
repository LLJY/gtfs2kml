"""
GTFS feed parser.

This module handles reading and parsing GTFS CSV files into data model objects.
"""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from .models import Route, Shape, ShapePoint, Stop, Trip

logger = logging.getLogger(__name__)


class GTFSParser:
    """
    Parser for GTFS feed data.

    Reads GTFS CSV files and constructs Route objects with associated
    shapes, trips, and stops.
    """

    def __init__(self, gtfs_dir: Path):
        """
        Initialize parser with GTFS directory.

        Args:
            gtfs_dir: Path to directory containing GTFS CSV files
        """
        self.gtfs_dir = Path(gtfs_dir)
        self._validate_gtfs_directory()

        # Storage for parsed data
        self.routes: Dict[str, Route] = {}
        self.shapes: Dict[str, Shape] = {}
        self.stops: Dict[str, Stop] = {}
        self.trips: Dict[str, Trip] = {}

    def _validate_gtfs_directory(self) -> None:
        """Validate that GTFS directory exists and contains required files."""
        if not self.gtfs_dir.exists():
            raise FileNotFoundError(f"GTFS directory not found: {self.gtfs_dir}")

        required_files = ['routes.txt', 'trips.txt', 'stops.txt']
        missing_files = []

        for filename in required_files:
            if not (self.gtfs_dir / filename).exists():
                missing_files.append(filename)

        if missing_files:
            raise FileNotFoundError(
                f"Missing required GTFS files: {', '.join(missing_files)}"
            )

    def parse(self, route_filter: Optional[Set[str]] = None) -> Dict[str, Route]:
        """
        Parse GTFS feed and return routes with associated data.

        Args:
            route_filter: Optional set of route_ids to filter. If None, parse all routes.

        Returns:
            Dictionary mapping route_id to Route objects
        """
        logger.info(f"Parsing GTFS feed from {self.gtfs_dir}")

        # Parse in dependency order
        self._parse_routes(route_filter)
        self._parse_stops()
        self._parse_shapes()
        self._parse_trips()
        self._link_stops_to_routes()

        logger.info(f"Parsed {len(self.routes)} routes")
        return self.routes

    def _parse_routes(self, route_filter: Optional[Set[str]] = None) -> None:
        """Parse routes.txt file."""
        routes_file = self.gtfs_dir / 'routes.txt'
        logger.debug(f"Parsing {routes_file}")

        with open(routes_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                route_id = row['route_id']

                # Apply filter if provided
                if route_filter and route_id not in route_filter:
                    continue

                route = Route(
                    route_id=route_id,
                    route_short_name=row.get('route_short_name', ''),
                    route_long_name=row.get('route_long_name', ''),
                    route_type=int(row.get('route_type', 3)),
                    agency_id=row.get('agency_id'),
                    route_desc=row.get('route_desc'),
                    route_url=row.get('route_url'),
                    route_color=row.get('route_color', 'FFFFFF'),
                    route_text_color=row.get('route_text_color', '000000')
                )

                self.routes[route_id] = route

        logger.debug(f"Loaded {len(self.routes)} routes")

    def _parse_stops(self) -> None:
        """Parse stops.txt file."""
        stops_file = self.gtfs_dir / 'stops.txt'
        logger.debug(f"Parsing {stops_file}")

        with open(stops_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip non-stop location types (stations, entrances, etc.)
                location_type = int(row.get('location_type', 0))
                if location_type != 0:
                    continue

                stop = Stop(
                    stop_id=row['stop_id'],
                    stop_name=row['stop_name'],
                    stop_lat=float(row['stop_lat']),
                    stop_lon=float(row['stop_lon']),
                    stop_code=row.get('stop_code'),
                    location_type=location_type,
                    parent_station=row.get('parent_station'),
                    wheelchair_boarding=int(row['wheelchair_boarding'])
                        if row.get('wheelchair_boarding') else None
                )

                self.stops[stop.stop_id] = stop

        logger.debug(f"Loaded {len(self.stops)} stops")

    def _parse_shapes(self) -> None:
        """Parse shapes.txt file if it exists."""
        shapes_file = self.gtfs_dir / 'shapes.txt'

        if not shapes_file.exists():
            logger.warning("shapes.txt not found - routes will not have geometry")
            return

        logger.debug(f"Parsing {shapes_file}")

        with open(shapes_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                shape_id = row['shape_id']

                point = ShapePoint(
                    shape_id=shape_id,
                    shape_pt_lat=float(row['shape_pt_lat']),
                    shape_pt_lon=float(row['shape_pt_lon']),
                    shape_pt_sequence=int(row['shape_pt_sequence']),
                    shape_dist_traveled=float(row['shape_dist_traveled'])
                        if row.get('shape_dist_traveled') else None
                )

                if shape_id not in self.shapes:
                    self.shapes[shape_id] = Shape(shape_id=shape_id)

                self.shapes[shape_id].add_point(point)

        # Sort all shape points by sequence
        for shape in self.shapes.values():
            shape.sort_points()

        logger.debug(f"Loaded {len(self.shapes)} shapes")

    def _parse_trips(self) -> None:
        """Parse trips.txt file and link to routes and shapes."""
        trips_file = self.gtfs_dir / 'trips.txt'
        logger.debug(f"Parsing {trips_file}")

        with open(trips_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                route_id = row['route_id']

                # Only process trips for routes we've loaded
                if route_id not in self.routes:
                    continue

                trip = Trip(
                    trip_id=row['trip_id'],
                    route_id=route_id,
                    service_id=row['service_id'],
                    trip_headsign=row.get('trip_headsign'),
                    trip_short_name=row.get('trip_short_name'),
                    direction_id=int(row['direction_id']) if row.get('direction_id') else None,
                    block_id=row.get('block_id'),
                    shape_id=row.get('shape_id'),
                    wheelchair_accessible=int(row['wheelchair_accessible'])
                        if row.get('wheelchair_accessible') else None,
                    bikes_allowed=int(row['bikes_allowed'])
                        if row.get('bikes_allowed') else None
                )

                self.trips[trip.trip_id] = trip

                # Link trip to route
                route = self.routes[route_id]
                route.add_trip(trip)

                # Link shape to route if available
                if trip.shape_id and trip.shape_id in self.shapes:
                    shape = self.shapes[trip.shape_id]
                    # Only add unique shapes to route
                    if not any(s.shape_id == shape.shape_id for s in route.shapes):
                        route.add_shape(shape)

        logger.debug(f"Loaded {len(self.trips)} trips")

    def _link_stops_to_routes(self) -> None:
        """
        Parse stop_times.txt to link stops to routes.

        This is more memory-intensive so we only do it if needed.
        """
        stop_times_file = self.gtfs_dir / 'stop_times.txt'

        if not stop_times_file.exists():
            logger.warning("stop_times.txt not found - stops will not be linked to routes")
            return

        logger.debug(f"Parsing {stop_times_file} to link stops")

        # Track which stops belong to which routes
        route_stops: Dict[str, Set[str]] = {rid: set() for rid in self.routes.keys()}

        with open(stop_times_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                trip_id = row['trip_id']
                stop_id = row['stop_id']

                # Only process if we know this trip
                if trip_id in self.trips:
                    route_id = self.trips[trip_id].route_id
                    route_stops[route_id].add(stop_id)

        # Add stops to routes
        for route_id, stop_ids in route_stops.items():
            route = self.routes[route_id]
            for stop_id in stop_ids:
                if stop_id in self.stops:
                    route.add_stop(self.stops[stop_id])

        logger.debug("Linked stops to routes")

    def get_route(self, route_id: str) -> Optional[Route]:
        """Get a specific route by ID."""
        return self.routes.get(route_id)

    def get_all_routes(self) -> List[Route]:
        """Get all parsed routes."""
        return list(self.routes.values())

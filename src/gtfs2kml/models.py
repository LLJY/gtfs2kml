"""
Data models for GTFS entities.

This module defines the core data structures representing GTFS feed components.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Stop:
    """Represents a transit stop location."""

    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    stop_code: Optional[str] = None
    location_type: int = 0
    parent_station: Optional[str] = None
    wheelchair_boarding: Optional[int] = None

    @property
    def coordinates(self) -> Tuple[float, float]:
        """Return (latitude, longitude) tuple."""
        return (self.stop_lat, self.stop_lon)

    @property
    def kml_coordinates(self) -> Tuple[float, float, float]:
        """Return KML-formatted coordinates (lon, lat, altitude)."""
        return (self.stop_lon, self.stop_lat, 0)


@dataclass
class ShapePoint:
    """Represents a single point in a route shape."""

    shape_id: str
    shape_pt_lat: float
    shape_pt_lon: float
    shape_pt_sequence: int
    shape_dist_traveled: Optional[float] = None

    @property
    def kml_coordinates(self) -> Tuple[float, float, float]:
        """Return KML-formatted coordinates (lon, lat, altitude)."""
        return (self.shape_pt_lon, self.shape_pt_lat, 0)


@dataclass
class Shape:
    """Represents a complete route shape (path geometry)."""

    shape_id: str
    points: List[ShapePoint] = field(default_factory=list)

    def add_point(self, point: ShapePoint) -> None:
        """Add a point to the shape, maintaining sequence order."""
        self.points.append(point)

    def sort_points(self) -> None:
        """Sort points by sequence number."""
        self.points.sort(key=lambda p: p.shape_pt_sequence)

    @property
    def kml_coordinates(self) -> List[Tuple[float, float, float]]:
        """Return all points as KML coordinates (lon, lat, altitude)."""
        return [point.kml_coordinates for point in self.points]

    @property
    def coordinate_count(self) -> int:
        """Return the number of points in this shape."""
        return len(self.points)


@dataclass
class Trip:
    """Represents a single transit trip."""

    trip_id: str
    route_id: str
    service_id: str
    trip_headsign: Optional[str] = None
    trip_short_name: Optional[str] = None
    direction_id: Optional[int] = None
    block_id: Optional[str] = None
    shape_id: Optional[str] = None
    wheelchair_accessible: Optional[int] = None
    bikes_allowed: Optional[int] = None


@dataclass
class Route:
    """Represents a transit route."""

    route_id: str
    route_short_name: str
    route_long_name: str
    route_type: int
    agency_id: Optional[str] = None
    route_desc: Optional[str] = None
    route_url: Optional[str] = None
    route_color: str = "FFFFFF"
    route_text_color: str = "000000"

    # Related data
    trips: List[Trip] = field(default_factory=list)
    shapes: List[Shape] = field(default_factory=list)
    stops: List[Stop] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """Return a display-friendly route name."""
        if self.route_short_name:
            return self.route_short_name
        return self.route_long_name

    @property
    def safe_filename(self) -> str:
        """
        Return a filesystem-safe version of the route name.

        Removes or replaces characters that are problematic in filenames.
        """
        import re
        # Use route_short_name if available, otherwise route_long_name
        name = self.route_short_name or self.route_long_name
        # Replace spaces with underscores
        name = name.replace(" ", "_")
        # Remove or replace problematic characters
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # Remove any other non-alphanumeric characters except underscore and hyphen
        name = re.sub(r'[^\w\-]', '', name)
        # Truncate to reasonable length
        name = name[:100]
        return name or f"route_{self.route_id}"

    @property
    def kml_color(self) -> str:
        """
        Convert GTFS RGB color to KML AABBGGRR format.

        GTFS uses RGB hex (e.g., 'FF0000' for red)
        KML uses AABBGGRR hex (e.g., 'ff0000ff' for opaque red)
        """
        # Ensure 6-character hex
        color = self.route_color.upper().zfill(6)
        if len(color) != 6:
            color = "FFFFFF"  # Default to white if invalid

        # Convert RGB to BGR and add full opacity (FF)
        r, g, b = color[0:2], color[2:4], color[4:6]
        return f"ff{b}{g}{r}"

    def add_trip(self, trip: Trip) -> None:
        """Add a trip to this route."""
        self.trips.append(trip)

    def add_shape(self, shape: Shape) -> None:
        """Add a shape to this route."""
        self.shapes.append(shape)

    def add_stop(self, stop: Stop) -> None:
        """Add a stop to this route."""
        if stop not in self.stops:
            self.stops.append(stop)

    @property
    def has_shapes(self) -> bool:
        """Check if route has any shape data."""
        return len(self.shapes) > 0

    @property
    def has_stops(self) -> bool:
        """Check if route has any stop data."""
        return len(self.stops) > 0

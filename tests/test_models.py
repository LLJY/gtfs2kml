"""
Unit tests for data models.
"""

import pytest
from gtfs2kml.models import Route, Shape, ShapePoint, Stop


def test_stop_coordinates():
    """Test Stop coordinate conversion."""
    stop = Stop(
        stop_id="stop_1",
        stop_name="Main Street",
        stop_lat=1.5000,
        stop_lon=103.8000
    )

    assert stop.coordinates == (1.5000, 103.8000)
    assert stop.kml_coordinates == (103.8000, 1.5000, 0)


def test_shape_point_kml_coordinates():
    """Test ShapePoint KML coordinate conversion."""
    point = ShapePoint(
        shape_id="shape_1",
        shape_pt_lat=1.5000,
        shape_pt_lon=103.8000,
        shape_pt_sequence=1
    )

    assert point.kml_coordinates == (103.8000, 1.5000, 0)


def test_shape_sorting():
    """Test Shape point sorting."""
    shape = Shape(shape_id="shape_1")

    # Add points out of order
    shape.add_point(ShapePoint("shape_1", 1.5, 103.8, 3))
    shape.add_point(ShapePoint("shape_1", 1.6, 103.9, 1))
    shape.add_point(ShapePoint("shape_1", 1.7, 104.0, 2))

    shape.sort_points()

    sequences = [p.shape_pt_sequence for p in shape.points]
    assert sequences == [1, 2, 3]


def test_route_display_name():
    """Test Route display name logic."""
    # Route with short name
    route1 = Route(
        route_id="R1",
        route_short_name="101",
        route_long_name="Main Line Express",
        route_type=3
    )
    assert route1.display_name == "101"

    # Route without short name
    route2 = Route(
        route_id="R2",
        route_short_name="",
        route_long_name="Circle Line",
        route_type=3
    )
    assert route2.display_name == "Circle Line"


def test_route_safe_filename():
    """Test Route safe filename generation."""
    route = Route(
        route_id="R1",
        route_short_name="101-A",
        route_long_name="Main/Express Line",
        route_type=3
    )

    filename = route.safe_filename
    # Should remove problematic characters
    assert "/" not in filename
    assert "\\" not in filename
    assert "<" not in filename


def test_route_kml_color_conversion():
    """Test GTFS RGB to KML AABBGGRR color conversion."""
    # Red in GTFS (RGB: FF0000)
    route1 = Route(
        route_id="R1",
        route_short_name="1",
        route_long_name="Red Line",
        route_type=3,
        route_color="FF0000"
    )
    assert route1.kml_color == "ff0000ff"

    # Green in GTFS (RGB: 00FF00)
    route2 = Route(
        route_id="R2",
        route_short_name="2",
        route_long_name="Green Line",
        route_type=3,
        route_color="00FF00"
    )
    assert route2.kml_color == "ff00ff00"

    # Blue in GTFS (RGB: 0000FF)
    route3 = Route(
        route_id="R3",
        route_short_name="3",
        route_long_name="Blue Line",
        route_type=3,
        route_color="0000FF"
    )
    assert route3.kml_color == "ffff0000"


def test_route_relationships():
    """Test Route relationship management."""
    route = Route(
        route_id="R1",
        route_short_name="1",
        route_long_name="Test Route",
        route_type=3
    )

    # Add shape
    shape = Shape(shape_id="shape_1")
    route.add_shape(shape)
    assert route.has_shapes
    assert len(route.shapes) == 1

    # Add stop
    stop = Stop("stop_1", "Test Stop", 1.5, 103.8)
    route.add_stop(stop)
    assert route.has_stops
    assert len(route.stops) == 1

    # Adding same stop twice shouldn't duplicate
    route.add_stop(stop)
    assert len(route.stops) == 1

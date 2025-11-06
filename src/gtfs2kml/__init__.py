"""
gtfs2kml - Convert GTFS transit feeds to KML format

A Python library and CLI tool for converting GTFS (General Transit Feed Specification)
data into KML (Keyhole Markup Language) format for visualization in mapping tools.
"""

__version__ = "0.1.0"

from .models import Route, Shape, Stop, Trip
from .gtfs_parser import GTFSParser
from .kml_generator import KMLGenerator

__all__ = ["Route", "Shape", "Stop", "Trip", "GTFSParser", "KMLGenerator"]

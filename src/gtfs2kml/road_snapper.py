"""
Road snapping and path densification for GTFS shapes.

This module provides functionality to:
1. Snap GTFS shape points to actual road networks using map matching APIs
2. Densify paths by adding points at regular intervals
3. Support multiple backend providers (Mapbox, OSRM, Google)
"""

import logging
import time
from typing import List, Tuple, Optional, Dict
from pathlib import Path
import json

try:
    import requests
except ImportError:
    raise ImportError("requests is required. Install it with: pip install requests")

try:
    from geopy.distance import geodesic
except ImportError:
    raise ImportError("geopy is required. Install it with: pip install geopy")

from .models import Shape, ShapePoint

logger = logging.getLogger(__name__)


class RoadSnapperConfig:
    """Configuration for road snapping services."""

    # Local OSRM server (default) - change to public if not available
    # Public OSRM: "https://router.project-osrm.org"
    OSRM_BASE_URL = "http://localhost:5000"

    # Mapbox requires API key
    MAPBOX_BASE_URL = "https://api.mapbox.com/matching/v5/mapbox/driving"

    # Google Roads API requires API key
    GOOGLE_ROADS_URL = "https://roads.googleapis.com/v1/snapToRoads"

    # Rate limiting (requests per second)
    OSRM_RATE_LIMIT = 1000  # Much faster with local server!
    MAPBOX_RATE_LIMIT = 10
    GOOGLE_RATE_LIMIT = 10

    # Maximum points per request (API limits)
    OSRM_MAX_POINTS = 100
    MAPBOX_MAX_POINTS = 100
    GOOGLE_MAX_POINTS = 100

    # Optimal chunk sizes for best matching quality
    # Smaller chunks = better confidence, more accurate road following
    OSRM_CHUNK_SIZE = 6  # Sweet spot for local OSRM
    MAPBOX_CHUNK_SIZE = 10
    GOOGLE_CHUNK_SIZE = 10


class RoadSnapper:
    """
    Snaps GPS coordinates to road networks using map matching APIs.

    Supports multiple providers:
    - OSRM (free, open source)
    - Mapbox (generous free tier)
    - Google Roads API (paid)
    """

    def __init__(
        self,
        provider: str = "osrm",
        api_key: Optional[str] = None,
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize road snapper.

        Args:
            provider: One of 'osrm', 'mapbox', 'google'
            api_key: API key for Mapbox or Google (not needed for OSRM)
            cache_dir: Optional directory to cache snapped results
        """
        self.provider = provider.lower()
        self.api_key = api_key
        self.cache_dir = cache_dir

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Validate configuration
        if self.provider == "mapbox" and not api_key:
            raise ValueError("Mapbox provider requires api_key")
        if self.provider == "google" and not api_key:
            raise ValueError("Google provider requires api_key")

        logger.info(f"Initialized RoadSnapper with provider: {self.provider}")

    def snap_shape(self, shape: Shape, max_points_per_request: Optional[int] = None) -> Shape:
        """
        Snap a shape to roads.

        Args:
            shape: Shape object with raw GPS points
            max_points_per_request: Override default max points per API call

        Returns:
            New Shape object with snapped coordinates
        """
        logger.info(f"Snapping shape {shape.shape_id} with {shape.coordinate_count} points")

        # Check cache
        if self.cache_dir:
            cached_shape = self._load_from_cache(shape.shape_id)
            if cached_shape:
                logger.info(f"Loaded shape {shape.shape_id} from cache")
                return cached_shape

        # Extract coordinates
        coordinates = [(p.shape_pt_lat, p.shape_pt_lon) for p in shape.points]

        # Snap to roads based on provider
        if self.provider == "osrm":
            snapped_coords = self._snap_osrm(coordinates, max_points_per_request)
        elif self.provider == "mapbox":
            snapped_coords = self._snap_mapbox(coordinates, max_points_per_request)
        elif self.provider == "google":
            snapped_coords = self._snap_google(coordinates, max_points_per_request)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        # Create new shape with snapped coordinates
        snapped_shape = Shape(shape_id=f"{shape.shape_id}_snapped")
        for idx, (lat, lon) in enumerate(snapped_coords):
            point = ShapePoint(
                shape_id=snapped_shape.shape_id,
                shape_pt_lat=lat,
                shape_pt_lon=lon,
                shape_pt_sequence=idx,
            )
            snapped_shape.add_point(point)

        # Cache result
        if self.cache_dir:
            self._save_to_cache(shape.shape_id, snapped_shape)

        logger.info(f"Snapped shape to {len(snapped_coords)} points")
        return snapped_shape

    def _snap_osrm(
        self, coordinates: List[Tuple[float, float]], max_points: Optional[int] = None
    ) -> List[Tuple[float, float]]:
        """Snap coordinates using OSRM map matching."""
        chunk_size = RoadSnapperConfig.OSRM_CHUNK_SIZE
        max_points = max_points or RoadSnapperConfig.OSRM_MAX_POINTS

        # Handle short routes without chunking
        if len(coordinates) <= chunk_size:
            return self._snap_osrm_chunk(coordinates)

        # Split into overlapping chunks for continuity and better matching
        logger.info(f"Route has {len(coordinates)} points, splitting into chunks of {chunk_size}")

        all_snapped = []
        overlap = 2  # Overlap points between chunks for smooth transitions
        step_size = chunk_size - overlap

        for i in range(0, len(coordinates), step_size):
            chunk_end = min(i + chunk_size, len(coordinates))
            chunk = coordinates[i:chunk_end]

            logger.debug(f"Processing chunk: points {i} to {chunk_end} ({len(chunk)} points)")
            snapped_chunk = self._snap_osrm_chunk(chunk)

            # Remove overlap from all but first chunk to avoid duplication
            if i > 0:
                # Remove first overlap/2 points from snapped result
                snapped_chunk = snapped_chunk[overlap // 2 :]

            all_snapped.extend(snapped_chunk)

            # Break if we've processed the last chunk
            if chunk_end >= len(coordinates):
                break

        logger.info(
            f"Combined {len(all_snapped)} snapped points from {(len(coordinates) + step_size - 1) // step_size} chunks"
        )
        return all_snapped

    def _snap_osrm_chunk(self, coordinates: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Snap a single chunk of coordinates using OSRM map matching."""
        # OSRM expects lon,lat format
        coords_str = ";".join([f"{lon},{lat}" for lat, lon in coordinates])

        url = f"{RoadSnapperConfig.OSRM_BASE_URL}/match/v1/driving/{coords_str}"
        params = {"overview": "full", "geometries": "geojson", "annotations": "false"}

        logger.debug(f"Making OSRM request with {len(coordinates)} points")

        # Rate limiting
        time.sleep(1.0 / RoadSnapperConfig.OSRM_RATE_LIMIT)

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != "Ok":
                logger.warning(f"OSRM matching failed: {data.get('message')}")
                return coordinates  # Return original on failure

            # Check confidence score
            confidence = data["matchings"][0].get("confidence", 0)
            logger.debug(f"OSRM match confidence: {confidence:.3f}")

            if confidence < 0.75:
                logger.warning(
                    f"Low OSRM match confidence ({confidence:.3f}), "
                    f"using original coordinates to avoid gaps"
                )
                return coordinates

            # Extract matched coordinates
            geometry = data["matchings"][0]["geometry"]["coordinates"]
            # Convert back to lat,lon
            return [(lat, lon) for lon, lat in geometry]

        except Exception as e:
            logger.error(f"OSRM snapping failed: {e}")
            return coordinates  # Fallback to original

    def _snap_mapbox(
        self, coordinates: List[Tuple[float, float]], max_points: Optional[int] = None
    ) -> List[Tuple[float, float]]:
        """Snap coordinates using Mapbox Map Matching API."""
        chunk_size = RoadSnapperConfig.MAPBOX_CHUNK_SIZE
        max_points = max_points or RoadSnapperConfig.MAPBOX_MAX_POINTS

        # Handle short routes without chunking
        if len(coordinates) <= chunk_size:
            return self._snap_mapbox_chunk(coordinates)

        # Split into overlapping chunks for continuity and better matching
        logger.info(f"Route has {len(coordinates)} points, splitting into chunks of {chunk_size}")

        all_snapped = []
        overlap = 5
        step_size = chunk_size - overlap

        for i in range(0, len(coordinates), step_size):
            chunk_end = min(i + chunk_size, len(coordinates))
            chunk = coordinates[i:chunk_end]

            logger.debug(f"Processing chunk: points {i} to {chunk_end} ({len(chunk)} points)")
            snapped_chunk = self._snap_mapbox_chunk(chunk)

            if i > 0:
                snapped_chunk = snapped_chunk[overlap // 2 :]

            all_snapped.extend(snapped_chunk)

            if chunk_end >= len(coordinates):
                break

        logger.info(
            f"Combined {len(all_snapped)} snapped points from {(len(coordinates) + step_size - 1) // step_size} chunks"
        )
        return all_snapped

    def _snap_mapbox_chunk(
        self, coordinates: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """Snap a single chunk of coordinates using Mapbox Map Matching API."""
        # Mapbox expects lon,lat format
        coords_str = ";".join([f"{lon},{lat}" for lat, lon in coordinates])

        url = f"{RoadSnapperConfig.MAPBOX_BASE_URL}/{coords_str}"
        params = {"access_token": self.api_key, "geometries": "geojson", "overview": "full"}

        logger.debug(f"Making Mapbox request with {len(coordinates)} points")

        # Rate limiting
        time.sleep(1.0 / RoadSnapperConfig.MAPBOX_RATE_LIMIT)

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "matchings" not in data or len(data["matchings"]) == 0:
                logger.warning("Mapbox matching returned no results")
                return coordinates

            # Extract matched coordinates
            geometry = data["matchings"][0]["geometry"]["coordinates"]
            # Convert back to lat,lon
            return [(lat, lon) for lon, lat in geometry]

        except Exception as e:
            logger.error(f"Mapbox snapping failed: {e}")
            return coordinates

    def _snap_google(
        self, coordinates: List[Tuple[float, float]], max_points: Optional[int] = None
    ) -> List[Tuple[float, float]]:
        """Snap coordinates using Google Roads API."""
        chunk_size = RoadSnapperConfig.GOOGLE_CHUNK_SIZE
        max_points = max_points or RoadSnapperConfig.GOOGLE_MAX_POINTS

        # Handle short routes without chunking
        if len(coordinates) <= chunk_size:
            return self._snap_google_chunk(coordinates)

        # Split into overlapping chunks for continuity and better matching
        logger.info(f"Route has {len(coordinates)} points, splitting into chunks of {chunk_size}")

        all_snapped = []
        overlap = 5
        step_size = chunk_size - overlap

        for i in range(0, len(coordinates), step_size):
            chunk_end = min(i + chunk_size, len(coordinates))
            chunk = coordinates[i:chunk_end]

            logger.debug(f"Processing chunk: points {i} to {chunk_end} ({len(chunk)} points)")
            snapped_chunk = self._snap_google_chunk(chunk)

            if i > 0:
                snapped_chunk = snapped_chunk[overlap // 2 :]

            all_snapped.extend(snapped_chunk)

            if chunk_end >= len(coordinates):
                break

        logger.info(
            f"Combined {len(all_snapped)} snapped points from {(len(coordinates) + step_size - 1) // step_size} chunks"
        )
        return all_snapped

    def _snap_google_chunk(
        self, coordinates: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """Snap a single chunk of coordinates using Google Roads API."""
        # Google expects lat,lon format
        path = "|".join([f"{lat},{lon}" for lat, lon in coordinates])

        params = {"path": path, "key": self.api_key, "interpolate": "true"}

        logger.debug(f"Making Google Roads request with {len(coordinates)} points")

        # Rate limiting
        time.sleep(1.0 / RoadSnapperConfig.GOOGLE_RATE_LIMIT)

        try:
            response = requests.get(RoadSnapperConfig.GOOGLE_ROADS_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "snappedPoints" not in data:
                logger.warning("Google Roads returned no snapped points")
                return coordinates

            # Extract snapped coordinates
            snapped = [
                (point["location"]["latitude"], point["location"]["longitude"])
                for point in data["snappedPoints"]
            ]
            return snapped

        except Exception as e:
            logger.error(f"Google Roads snapping failed: {e}")
            return coordinates

    def _load_from_cache(self, shape_id: str) -> Optional[Shape]:
        """Load snapped shape from cache."""
        cache_file = self.cache_dir / f"{shape_id}_snapped.json"
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r") as f:
                data = json.load(f)

            shape = Shape(shape_id=data["shape_id"])
            for point_data in data["points"]:
                point = ShapePoint(
                    shape_id=shape.shape_id,
                    shape_pt_lat=point_data["lat"],
                    shape_pt_lon=point_data["lon"],
                    shape_pt_sequence=point_data["seq"],
                )
                shape.add_point(point)

            return shape

        except Exception as e:
            logger.warning(f"Failed to load cache for {shape_id}: {e}")
            return None

    def _save_to_cache(self, original_shape_id: str, snapped_shape: Shape) -> None:
        """Save snapped shape to cache."""
        cache_file = self.cache_dir / f"{original_shape_id}_snapped.json"

        try:
            data = {
                "shape_id": snapped_shape.shape_id,
                "points": [
                    {"lat": p.shape_pt_lat, "lon": p.shape_pt_lon, "seq": p.shape_pt_sequence}
                    for p in snapped_shape.points
                ],
            }

            with open(cache_file, "w") as f:
                json.dump(data, f)

            logger.debug(f"Cached snapped shape to {cache_file}")

        except Exception as e:
            logger.warning(f"Failed to cache shape: {e}")


class PathDensifier:
    """
    Adds points along a path at regular intervals.

    Useful for ensuring smooth visualization and animation.
    """

    def __init__(self, interval_meters: float = 100.0):
        """
        Initialize path densifier.

        Args:
            interval_meters: Distance between interpolated points in meters
        """
        self.interval_meters = interval_meters
        logger.info(f"Initialized PathDensifier with {interval_meters}m intervals")

    def densify_shape(self, shape: Shape, preserve_points: Optional[List[int]] = None) -> Shape:
        """
        Add points along the shape at regular intervals.

        Args:
            shape: Shape to densify
            preserve_points: Indices of points that must be preserved (e.g., bus stops)

        Returns:
            New Shape with densified points
        """
        logger.info(
            f"Densifying shape {shape.shape_id} "
            f"({shape.coordinate_count} points) at {self.interval_meters}m intervals"
        )

        if shape.coordinate_count < 2:
            return shape

        preserve_points = preserve_points or []
        densified_points = []
        sequence = 0

        for i in range(len(shape.points) - 1):
            p1 = shape.points[i]
            p2 = shape.points[i + 1]

            # Always add the first point
            densified_points.append(
                ShapePoint(
                    shape_id=f"{shape.shape_id}_dense",
                    shape_pt_lat=p1.shape_pt_lat,
                    shape_pt_lon=p1.shape_pt_lon,
                    shape_pt_sequence=sequence,
                )
            )
            sequence += 1

            # Calculate distance between points
            coord1 = (p1.shape_pt_lat, p1.shape_pt_lon)
            coord2 = (p2.shape_pt_lat, p2.shape_pt_lon)
            distance = geodesic(coord1, coord2).meters

            # Add intermediate points if distance exceeds interval
            if distance > self.interval_meters:
                num_segments = int(distance / self.interval_meters)

                for seg in range(1, num_segments + 1):
                    fraction = seg / (num_segments + 1)

                    # Linear interpolation
                    lat = p1.shape_pt_lat + fraction * (p2.shape_pt_lat - p1.shape_pt_lat)
                    lon = p1.shape_pt_lon + fraction * (p2.shape_pt_lon - p1.shape_pt_lon)

                    densified_points.append(
                        ShapePoint(
                            shape_id=f"{shape.shape_id}_dense",
                            shape_pt_lat=lat,
                            shape_pt_lon=lon,
                            shape_pt_sequence=sequence,
                        )
                    )
                    sequence += 1

        # Add final point
        last = shape.points[-1]
        densified_points.append(
            ShapePoint(
                shape_id=f"{shape.shape_id}_dense",
                shape_pt_lat=last.shape_pt_lat,
                shape_pt_lon=last.shape_pt_lon,
                shape_pt_sequence=sequence,
            )
        )

        # Create new shape
        densified_shape = Shape(shape_id=f"{shape.shape_id}_dense")
        densified_shape.points = densified_points

        logger.info(
            f"Densified shape from {shape.coordinate_count} to "
            f"{densified_shape.coordinate_count} points"
        )

        return densified_shape


def calculate_path_distance(shape: Shape) -> float:
    """
    Calculate total distance of a shape path in meters.

    Args:
        shape: Shape to measure

    Returns:
        Total distance in meters
    """
    if shape.coordinate_count < 2:
        return 0.0

    total_distance = 0.0
    for i in range(len(shape.points) - 1):
        p1 = shape.points[i]
        p2 = shape.points[i + 1]
        coord1 = (p1.shape_pt_lat, p1.shape_pt_lon)
        coord2 = (p2.shape_pt_lat, p2.shape_pt_lon)
        total_distance += geodesic(coord1, coord2).meters

    return total_distance

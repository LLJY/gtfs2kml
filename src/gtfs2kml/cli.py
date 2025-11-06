"""
Command-line interface for gtfs2kml.

Provides a Click-based CLI for converting GTFS feeds to KML format.
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Set

try:
    import click
except ImportError:
    raise ImportError(
        "click is required. Install it with: pip install click"
    )

from . import __version__
from .gtfs_parser import GTFSParser
from .kml_generator import KMLGenerator


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


@click.command()
@click.argument('gtfs_dir', type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument('output_dir', type=click.Path(path_type=Path))
@click.option(
    '--route', '-r',
    'routes',
    multiple=True,
    help='Filter specific routes by route_id (can be specified multiple times)'
)
@click.option(
    '--include-stops/--no-stops',
    default=True,
    help='Include stop markers in KML output (default: yes)'
)
@click.option(
    '--split-by',
    type=click.Choice(['route', 'all'], case_sensitive=False),
    default='route',
    help='Output mode: "route" creates one file per route, "all" creates single file (default: route)'
)
@click.option(
    '--line-width',
    type=int,
    default=4,
    help='Line width in pixels (default: 4)'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose logging'
)
@click.option(
    '--snap-to-roads',
    is_flag=True,
    help='Snap route paths to actual roads using map matching'
)
@click.option(
    '--snap-provider',
    type=click.Choice(['osrm', 'mapbox', 'google'], case_sensitive=False),
    default='osrm',
    help='Road snapping provider (default: osrm, free)'
)
@click.option(
    '--snap-api-key',
    type=str,
    help='API key for Mapbox or Google road snapping'
)
@click.option(
    '--densify-points',
    type=int,
    metavar='METERS',
    help='Add points along routes at specified interval (e.g., 100 for every 100m)'
)
@click.option(
    '--snap-cache-dir',
    type=click.Path(path_type=Path),
    help='Directory to cache snapped results (avoids re-processing)'
)
@click.version_option(version=__version__, prog_name='gtfs2kml')
def main(
    gtfs_dir: Path,
    output_dir: Path,
    routes: tuple,
    include_stops: bool,
    split_by: str,
    line_width: int,
    verbose: bool,
    snap_to_roads: bool,
    snap_provider: str,
    snap_api_key: Optional[str],
    densify_points: Optional[int],
    snap_cache_dir: Optional[Path]
) -> None:
    """
    Convert GTFS transit feeds to KML format.

    GTFS_DIR: Path to directory containing GTFS CSV files (routes.txt, shapes.txt, etc.)

    OUTPUT_DIR: Directory where KML files will be saved

    Examples:

      Convert all routes to individual KML files:
        gtfs2kml ./gtfs_data ./output

      Convert specific routes only:
        gtfs2kml ./gtfs_data ./output -r route_1 -r route_2

      Create a single KML file with all routes:
        gtfs2kml ./gtfs_data ./output --split-by all

      Exclude stop markers and use thicker lines:
        gtfs2kml ./gtfs_data ./output --no-stops --line-width 6

      Snap routes to roads and add points every 100m:
        gtfs2kml ./gtfs_data ./output --snap-to-roads --densify-points 100

      Use Mapbox for road snapping (requires API key):
        gtfs2kml ./gtfs_data ./output --snap-to-roads --snap-provider mapbox --snap-api-key YOUR_KEY
    """
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    try:
        # Parse route filter
        route_filter: Optional[Set[str]] = None
        if routes:
            route_filter = set(routes)
            logger.info(f"Filtering for routes: {', '.join(route_filter)}")

        # Parse GTFS feed
        logger.info(f"Reading GTFS data from {gtfs_dir}")
        parser = GTFSParser(gtfs_dir)
        parsed_routes = parser.parse(route_filter=route_filter)

        if not parsed_routes:
            logger.error("No routes found matching criteria")
            sys.exit(1)

        logger.info(f"Successfully parsed {len(parsed_routes)} routes")

        # Check if any routes have shapes
        routes_with_shapes = [r for r in parsed_routes.values() if r.has_shapes]
        if not routes_with_shapes:
            logger.warning(
                "No routes have shape data! KML files will only contain stops. "
                "Check if shapes.txt exists in GTFS feed."
            )

        # Apply road snapping if requested
        if snap_to_roads and routes_with_shapes:
            try:
                from .road_snapper import RoadSnapper
                logger.info(f"Applying road snapping with provider: {snap_provider}")

                snapper = RoadSnapper(
                    provider=snap_provider,
                    api_key=snap_api_key,
                    cache_dir=snap_cache_dir
                )

                for route in routes_with_shapes:
                    snapped_shapes = []
                    for shape in route.shapes:
                        snapped = snapper.snap_shape(shape)
                        snapped_shapes.append(snapped)
                    route.shapes = snapped_shapes

                logger.info("Road snapping completed")

            except ImportError as e:
                logger.error(f"Road snapping requires additional dependencies: {e}")
                click.echo(f"Error: Install dependencies with: pip install requests geopy", err=True)
                sys.exit(1)
            except Exception as e:
                logger.error(f"Road snapping failed: {e}")
                click.echo(f"Warning: Road snapping failed, using original paths", err=True)

        # Apply path densification if requested
        if densify_points and routes_with_shapes:
            try:
                from .road_snapper import PathDensifier
                logger.info(f"Densifying paths at {densify_points}m intervals")

                densifier = PathDensifier(interval_meters=float(densify_points))

                for route in routes_with_shapes:
                    densified_shapes = []
                    for shape in route.shapes:
                        densified = densifier.densify_shape(shape)
                        densified_shapes.append(densified)
                    route.shapes = densified_shapes

                logger.info("Path densification completed")

            except ImportError as e:
                logger.error(f"Path densification requires geopy: {e}")
                click.echo(f"Error: Install geopy with: pip install geopy", err=True)
                sys.exit(1)

        # Generate KML
        logger.info(f"Generating KML files in {output_dir}")
        generator = KMLGenerator(
            line_width=line_width,
            include_stops=include_stops
        )

        split_by_route = (split_by.lower() == 'route')
        output_files = generator.generate_batch(
            routes=list(parsed_routes.values()),
            output_dir=output_dir,
            split_by_route=split_by_route
        )

        # Summary
        logger.info(f"Successfully generated {len(output_files)} KML file(s)")
        click.echo(f"\nSuccess! Generated {len(output_files)} KML file(s) in {output_dir}")

        if verbose:
            click.echo("\nGenerated files:")
            for file_path in output_files:
                click.echo(f"  - {file_path}")

    except FileNotFoundError as e:
        logger.error(f"File error: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    except Exception as e:
        logger.exception("Unexpected error during conversion")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

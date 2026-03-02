"""Sample GEBCO bathymetry at each H3 hex cell centroid.

For each unique H3 cell in the grid, samples depth at 7 points
(6 hexagon vertices + centroid) and stores the mean depth.
This captures depth variation across the cell — important at
continental shelf edges where depth changes rapidly.

Writes a bathymetry_h3 table to PostGIS for use by the
int_bathymetry dbt model.

Run with:
    uv run python -m pipeline.aggregation.sample_bathymetry
"""

import logging
import time

import h3
import numpy as np
import psycopg2
import rasterio
from psycopg2.extras import execute_values

from pipeline.config import BATHYMETRY_RASTER, DB_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_sample_points(cell_hex: str) -> list[tuple[float, float]]:
    """Return 7 sample points for a hex cell: centroid + 6 vertices.

    Args:
        cell_hex: H3 cell index as hex string.

    Returns:
        List of (lat, lon) tuples.
    """
    centroid = h3.cell_to_latlng(cell_hex)
    vertices = h3.cell_to_boundary(cell_hex)
    return [centroid] + list(vertices)


def main() -> None:
    """Sample bathymetry raster at all H3 cell centroids."""

    t0 = time.time()

    # ── Read unique cells from PostGIS ────────────────────
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    logger.info("Reading unique H3 cells (UNION of AIS + cetacean)...")
    cur.execute("""
        SELECT h3_cell, cell_lat, cell_lon FROM (
            SELECT DISTINCT h3_cell, cell_lat, cell_lon
            FROM ais_h3_summary
            UNION
            SELECT DISTINCT h3_cell, cell_lat, cell_lon
            FROM cetacean_sighting_h3
        ) AS grid
    """)
    cells = cur.fetchall()
    logger.info("Read %s cells", f"{len(cells):,}")

    # ── Open raster ───────────────────────────────────────
    src = rasterio.open(BATHYMETRY_RASTER)
    raster_bounds = src.bounds
    band = src.read(1)  # Load full band into memory (187 MB as int16)
    nodata = src.nodata
    logger.info(
        "Raster loaded: %s x %s, bounds: %.1f–%.1f lon, %.1f–%.1f lat",
        band.shape[0],
        band.shape[1],
        raster_bounds.left,
        raster_bounds.right,
        raster_bounds.bottom,
        raster_bounds.top,
    )

    # ── Sample depth at each cell ─────────────────────────
    logger.info("Sampling depth at 7 points per cell...")
    records = []
    skipped = 0

    for h3_cell_int, _cell_lat, _cell_lon in cells:
        # Convert BIGINT back to hex string for h3 library
        cell_hex = format(h3_cell_int, "x")

        # Get 7 sample points
        points = get_sample_points(cell_hex)

        # Sample raster at each point
        depths = []
        for lat, lon in points:
            # Check bounds
            if not (
                raster_bounds.left <= lon <= raster_bounds.right
                and raster_bounds.bottom <= lat <= raster_bounds.top
            ):
                continue

            # Convert lat/lon to pixel row/col
            row, col = src.index(lon, lat)

            # Bounds check on pixel indices
            if 0 <= row < band.shape[0] and 0 <= col < band.shape[1]:
                val = band[row, col]
                if val != nodata:
                    depths.append(float(val))

        if not depths:
            skipped += 1
            continue

        avg_depth = float(np.mean(depths))
        min_depth = float(np.min(depths))
        max_depth = float(np.max(depths))
        depth_range = float(max_depth - min_depth)
        sample_count = len(depths)

        records.append(
            (
                h3_cell_int,
                round(avg_depth, 1),
                round(min_depth, 1),
                round(max_depth, 1),
                round(depth_range, 1),
                sample_count,
            )
        )

    logger.info(
        "Sampled %s cells (%s outside raster bounds)",
        f"{len(records):,}",
        f"{skipped:,}",
    )

    src.close()

    # ── Write to PostGIS ──────────────────────────────────
    logger.info("Writing bathymetry_h3 table...")

    cur.execute("DROP TABLE IF EXISTS bathymetry_h3 CASCADE;")
    cur.execute("""
        CREATE TABLE bathymetry_h3 (
            h3_cell        BIGINT           NOT NULL PRIMARY KEY,
            depth_m        DOUBLE PRECISION NOT NULL,
            min_depth_m    DOUBLE PRECISION NOT NULL,
            max_depth_m    DOUBLE PRECISION NOT NULL,
            depth_range_m  DOUBLE PRECISION NOT NULL,
            sample_count   INTEGER          NOT NULL
        );
    """)

    batch_size = 10_000
    total = len(records)
    for i in range(0, total, batch_size):
        batch = records[i : i + batch_size]
        execute_values(
            cur,
            """INSERT INTO bathymetry_h3
               (h3_cell, depth_m, min_depth_m, max_depth_m, depth_range_m, sample_count)
               VALUES %s""",
            batch,
        )
        if (i + batch_size) % 100_000 == 0 or i + batch_size >= total:
            logger.info(
                "  Inserted %s / %s",
                f"{min(i + batch_size, total):,}",
                f"{total:,}",
            )

    cur.execute("""
        CREATE INDEX idx_bathymetry_h3_cell
            ON bathymetry_h3 (h3_cell);
    """)

    conn.commit()
    cur.close()
    conn.close()

    elapsed = time.time() - t0
    logger.info("Done in %.1f seconds", elapsed)


if __name__ == "__main__":
    main()

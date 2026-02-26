"""Assign H3 cells to cetacean sightings.

Reads cetacean sightings from PostGIS, computes the H3
resolution-7 cell for each (lat, lon) using the Python h3
library, and writes the mapping back to PostGIS.

This avoids expensive spatial joins in dbt — instead the
int_cetacean_density model does a simple GROUP BY on the
pre-computed h3_cell column.

Run with:
    uv run python -m pipeline.aggregation.assign_cetacean_h3
"""

import logging
import time

import h3
import psycopg2
from psycopg2.extras import execute_values

H3_RESOLUTION = 7

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "marine_risk",
    "user": "marine",
    "password": "marine_dev",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Read sightings, assign H3 cells, write to PostGIS."""

    t0 = time.time()

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # ── Read sightings ────────────────────────────────────
    logger.info("Reading cetacean sightings from PostGIS...")
    cur.execute("""
        SELECT id, decimal_latitude, decimal_longitude
        FROM cetacean_sightings
        WHERE decimal_latitude IS NOT NULL
          AND decimal_longitude IS NOT NULL
    """)
    rows = cur.fetchall()
    logger.info("Read %s sightings", f"{len(rows):,}")

    # ── Assign H3 cells ──────────────────────────────────
    logger.info("Assigning H3 resolution-%d cells...", H3_RESOLUTION)
    records = []
    for sighting_id, lat, lon in rows:
        cell_hex = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
        cell_int = int(cell_hex, 16)
        cell_lat, cell_lon = h3.cell_to_latlng(cell_hex)
        records.append((sighting_id, cell_int, cell_lat, cell_lon))

    logger.info("Assigned %s cells", f"{len(records):,}")

    # ── Write to PostGIS ──────────────────────────────────
    logger.info("Writing cetacean_sighting_h3 table...")

    cur.execute("DROP TABLE IF EXISTS cetacean_sighting_h3 CASCADE;")
    cur.execute("""
        CREATE TABLE cetacean_sighting_h3 (
            sighting_id  INTEGER          NOT NULL REFERENCES cetacean_sightings(id),
            h3_cell      BIGINT           NOT NULL,
            cell_lat     DOUBLE PRECISION NOT NULL,
            cell_lon     DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (sighting_id)
        );
    """)

    batch_size = 10_000
    total = len(records)
    for i in range(0, total, batch_size):
        batch = records[i : i + batch_size]
        execute_values(
            cur,
            "INSERT INTO cetacean_sighting_h3 "
            "(sighting_id, h3_cell, cell_lat, cell_lon) "
            "VALUES %s",
            batch,
        )
        if (i + batch_size) % 100_000 == 0 or i + batch_size >= total:
            logger.info(
                "  Inserted %s / %s",
                f"{min(i + batch_size, total):,}",
                f"{total:,}",
            )

    # Index for GROUP BY h3_cell in dbt
    cur.execute("""
        CREATE INDEX idx_cetacean_h3_cell
            ON cetacean_sighting_h3 (h3_cell);
    """)

    conn.commit()
    cur.close()
    conn.close()

    elapsed = time.time() - t0
    logger.info("Done in %.1f seconds", elapsed)


if __name__ == "__main__":
    main()

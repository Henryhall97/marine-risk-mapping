"""Assign H3 cells to ship strike records.

Reads geocoded ship strikes from PostGIS, computes the H3
resolution-7 cell for each (lat, lon) using the Python h3
library, and writes the mapping back to PostGIS as the
ship_strike_h3 table.

Only strikes with non-null coordinates are assigned.
The resulting table is used by dbt to join strikes into
the hex grid without expensive spatial joins.

Run with:
    uv run python -m pipeline.aggregation.assign_ship_strike_h3
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
    """Read ship strikes, assign H3 cells, write to PostGIS."""

    t0 = time.time()

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # ── Read geocoded strikes ─────────────────────────────
    logger.info("Reading ship strikes from PostGIS...")
    cur.execute("""
        SELECT id, latitude, longitude
        FROM ship_strikes
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
    """)
    rows = cur.fetchall()
    logger.info("Read %s geocoded strikes (of 261 total)", f"{len(rows):,}")

    # ── Assign H3 cells ──────────────────────────────────
    logger.info("Assigning H3 resolution-%d cells...", H3_RESOLUTION)
    records = []
    for strike_id, lat, lon in rows:
        cell_hex = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
        cell_int = int(cell_hex, 16)
        cell_lat, cell_lon = h3.cell_to_latlng(cell_hex)
        records.append((strike_id, cell_int, cell_lat, cell_lon))

    logger.info(
        "Assigned %s cells (%d unique)",
        f"{len(records):,}",
        len({r[1] for r in records}),
    )

    # ── Write to PostGIS ──────────────────────────────────
    logger.info("Writing ship_strike_h3 table...")

    cur.execute("DROP TABLE IF EXISTS ship_strike_h3 CASCADE;")
    cur.execute("""
        CREATE TABLE ship_strike_h3 (
            strike_id    INTEGER          NOT NULL REFERENCES ship_strikes(id),
            h3_cell      BIGINT           NOT NULL,
            cell_lat     DOUBLE PRECISION NOT NULL,
            cell_lon     DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (strike_id)
        );
    """)

    execute_values(
        cur,
        "INSERT INTO ship_strike_h3 (strike_id, h3_cell, cell_lat, cell_lon) VALUES %s",
        records,
    )

    # Index for GROUP BY h3_cell in dbt
    cur.execute("""
        CREATE INDEX idx_strike_h3_cell
            ON ship_strike_h3 (h3_cell);
    """)

    conn.commit()
    cur.close()
    conn.close()

    elapsed = time.time() - t0
    logger.info(
        "Done in %.1f seconds — %s strikes assigned to H3 cells",
        elapsed,
        f"{len(records):,}",
    )


if __name__ == "__main__":
    main()

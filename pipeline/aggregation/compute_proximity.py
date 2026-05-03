"""Compute nearest-neighbour distances between grid cells and key features.

For each H3 cell in the hex grid, computes:
  - dist_to_nearest_whale_km:      distance to nearest cetacean sighting cell
  - dist_to_nearest_ship_km:       distance to nearest vessel traffic cell
  - dist_to_nearest_strike_km:     distance to nearest historical ship strike cell
  - dist_to_nearest_protection_km: distance to nearest speed zone / SMA boundary

Uses scipy KDTree for O(n log m) nearest-neighbour search — runs in
seconds for ~1.9M grid cells vs. hours with PostGIS cross-lateral
joins (CTEs lack GiST indexes).

Reads ONLY from source tables (ais_h3_summary, cetacean_sighting_h3,
ship_strike_h3, right_whale_speed_zones, seasonal_management_areas)
— no dependency on dbt-managed tables. This means the script can
run before, after, or independently of dbt.

Writes a cell_proximity table to PostGIS for use by the
int_proximity dbt model.

Run with:
    uv run python -m pipeline.aggregation.compute_proximity
"""

import logging
import time

import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from scipy.spatial import cKDTree

from pipeline.config import DB_CONFIG

# Approximate conversion for lat/lon → km at mid-US latitudes (~37°N)
# 1° latitude ≈ 111 km everywhere
# 1° longitude ≈ 111 * cos(37°) ≈ 88.7 km
# We use a proper haversine in post-processing, but KDTree needs
# Cartesian coordinates, so we project to approximate km.
REF_LAT = 37.0  # degrees — centre of study-area latitude range
KM_PER_DEG_LAT = 111.0
KM_PER_DEG_LON = 111.0 * np.cos(np.radians(REF_LAT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def haversine_km(
    lat1: np.ndarray,
    lon1: np.ndarray,
    lat2: np.ndarray,
    lon2: np.ndarray,
) -> np.ndarray:
    """Vectorised haversine distance in kilometres."""
    r = 6371.0  # Earth radius in km
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    )
    return 2 * r * np.arcsin(np.sqrt(a))


def to_cartesian(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Project lat/lon to approximate Cartesian (km) for KDTree.

    This is only used for nearest-neighbour SEARCH — the actual
    distance is computed with haversine after finding the nearest.
    """
    x = lons * KM_PER_DEG_LON
    y = lats * KM_PER_DEG_LAT
    return np.column_stack([x, y])


def main() -> None:
    """Compute proximity features and write to PostGIS."""

    t0 = time.time()

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # ── 1. Load all grid cells ────────────────────────────
    # Derive the grid from source tables (AIS ∪ cetacean ∪ strike)
    # so this script has NO dependency on dbt-managed tables.
    logger.info("Loading hex grid cells (UNION of AIS + cetacean + strikes)...")
    cur.execute("""
        SELECT h3_cell, cell_lat, cell_lon FROM (
            SELECT DISTINCT h3_cell, cell_lat, cell_lon
            FROM ais_h3_summary
            UNION
            SELECT DISTINCT h3_cell, cell_lat, cell_lon
            FROM cetacean_sighting_h3
            UNION
            SELECT DISTINCT h3_cell, cell_lat, cell_lon
            FROM ship_strike_h3
        ) AS grid
    """)
    grid_rows = cur.fetchall()
    grid_cells = np.array([r[0] for r in grid_rows], dtype=np.int64)
    grid_lats = np.array([r[1] for r in grid_rows], dtype=np.float64)
    grid_lons = np.array([r[2] for r in grid_rows], dtype=np.float64)
    logger.info(f"  {len(grid_cells):,} grid cells loaded")

    # ── 2. Load cetacean sighting cells ───────────────────
    logger.info("Loading cetacean sighting cells...")
    cur.execute("""
        SELECT DISTINCT h3_cell, cell_lat, cell_lon
        FROM cetacean_sighting_h3
    """)
    whale_rows = cur.fetchall()
    whale_lats = np.array([r[1] for r in whale_rows], dtype=np.float64)
    whale_lons = np.array([r[2] for r in whale_rows], dtype=np.float64)
    logger.info(f"  {len(whale_rows):,} whale cells loaded")

    # ── 3. Load vessel traffic cells ──────────────────────
    logger.info("Loading vessel traffic cells...")
    cur.execute("""
        SELECT DISTINCT h3_cell, cell_lat, cell_lon
        FROM ais_h3_summary
    """)
    ship_rows = cur.fetchall()
    ship_lats = np.array([r[1] for r in ship_rows], dtype=np.float64)
    ship_lons = np.array([r[2] for r in ship_rows], dtype=np.float64)
    logger.info(f"  {len(ship_rows):,} traffic cells loaded")

    # ── 4. Build KDTrees ──────────────────────────────────
    logger.info("Building KDTrees (whale + ship)...")
    whale_cart = to_cartesian(whale_lats, whale_lons)
    ship_cart = to_cartesian(ship_lats, ship_lons)
    grid_cart = to_cartesian(grid_lats, grid_lons)

    whale_tree = cKDTree(whale_cart)
    ship_tree = cKDTree(ship_cart)
    logger.info("  KDTrees built")

    # ── 5. Query nearest neighbours (whale + ship) ───────
    logger.info("Finding nearest whale cell for each grid cell...")
    _, whale_idx = whale_tree.query(grid_cart, k=1)
    dist_to_whale_km = haversine_km(
        grid_lats,
        grid_lons,
        whale_lats[whale_idx],
        whale_lons[whale_idx],
    )
    logger.info(
        f"  Nearest whale: min={dist_to_whale_km.min():.1f}km, "
        f"median={np.median(dist_to_whale_km):.1f}km, "
        f"max={dist_to_whale_km.max():.1f}km"
    )

    logger.info("Finding nearest ship cell for each grid cell...")
    _, ship_idx = ship_tree.query(grid_cart, k=1)
    dist_to_ship_km = haversine_km(
        grid_lats,
        grid_lons,
        ship_lats[ship_idx],
        ship_lons[ship_idx],
    )
    logger.info(
        f"  Nearest ship: min={dist_to_ship_km.min():.1f}km, "
        f"median={np.median(dist_to_ship_km):.1f}km, "
        f"max={dist_to_ship_km.max():.1f}km"
    )

    # ── 6. Load ship strike cells ─────────────────────────
    logger.info("Loading ship strike cells...")
    cur.execute("""
        SELECT DISTINCT h3_cell, cell_lat, cell_lon
        FROM ship_strike_h3
    """)
    strike_rows = cur.fetchall()
    strike_lats = np.array([r[1] for r in strike_rows], dtype=np.float64)
    strike_lons = np.array([r[2] for r in strike_rows], dtype=np.float64)
    logger.info(f"  {len(strike_rows):,} strike cells loaded")

    logger.info("Finding nearest strike cell for each grid cell...")
    strike_cart = to_cartesian(strike_lats, strike_lons)
    strike_tree = cKDTree(strike_cart)
    _, strike_idx = strike_tree.query(grid_cart, k=1)
    dist_to_strike_km = haversine_km(
        grid_lats,
        grid_lons,
        strike_lats[strike_idx],
        strike_lons[strike_idx],
    )
    logger.info(
        f"  Nearest strike: min={dist_to_strike_km.min():.1f}km, "
        f"median={np.median(dist_to_strike_km):.1f}km, "
        f"max={dist_to_strike_km.max():.1f}km"
    )

    # ── 7. Load protection zone boundary points ───────────
    # Speed zones and SMAs are polygons. We densify their
    # boundaries into points (one per ~0.05°, ≈5km) and
    # build a KDTree so "distance to nearest protection"
    # means distance to nearest zone boundary/interior.
    logger.info("Loading protection zone boundaries...")
    cur.execute("""
        SELECT ST_Y(pt) AS lat, ST_X(pt) AS lon
        FROM (
            SELECT (ST_DumpPoints(
                ST_Segmentize(geom::geography, 5000)::geometry
            )).geom AS pt
            FROM right_whale_speed_zones
            UNION ALL
            SELECT (ST_DumpPoints(
                ST_Segmentize(geom::geography, 5000)::geometry
            )).geom AS pt
            FROM seasonal_management_areas
        ) AS boundary_pts
    """)
    prot_rows = cur.fetchall()
    prot_lats = np.array([r[0] for r in prot_rows], dtype=np.float64)
    prot_lons = np.array([r[1] for r in prot_rows], dtype=np.float64)
    logger.info(f"  {len(prot_rows):,} protection boundary points loaded")

    logger.info("Finding nearest protection zone for each grid cell...")
    prot_cart = to_cartesian(prot_lats, prot_lons)
    prot_tree = cKDTree(prot_cart)
    _, prot_idx = prot_tree.query(grid_cart, k=1)
    dist_to_protection_km = haversine_km(
        grid_lats,
        grid_lons,
        prot_lats[prot_idx],
        prot_lons[prot_idx],
    )
    logger.info(
        f"  Nearest protection: min={dist_to_protection_km.min():.1f}km, "
        f"median={np.median(dist_to_protection_km):.1f}km, "
        f"max={dist_to_protection_km.max():.1f}km"
    )

    # ── 8. Write to PostGIS ───────────────────────────────
    logger.info("Writing cell_proximity table to PostGIS...")
    cur.execute("DROP TABLE IF EXISTS cell_proximity")
    cur.execute("""
        CREATE TABLE cell_proximity (
            h3_cell                       BIGINT PRIMARY KEY,
            dist_to_nearest_whale_km      DOUBLE PRECISION NOT NULL,
            dist_to_nearest_ship_km       DOUBLE PRECISION NOT NULL,
            dist_to_nearest_strike_km     DOUBLE PRECISION NOT NULL,
            dist_to_nearest_protection_km DOUBLE PRECISION NOT NULL
        )
    """)

    rows = [
        (
            int(grid_cells[i]),
            float(dist_to_whale_km[i]),
            float(dist_to_ship_km[i]),
            float(dist_to_strike_km[i]),
            float(dist_to_protection_km[i]),
        )
        for i in range(len(grid_cells))
    ]

    execute_values(
        cur,
        """
        INSERT INTO cell_proximity
            (h3_cell, dist_to_nearest_whale_km, dist_to_nearest_ship_km,
             dist_to_nearest_strike_km, dist_to_nearest_protection_km)
        VALUES %s
        """,
        rows,
        page_size=10_000,
    )

    conn.commit()

    # ── 9. Create index ───────────────────────────────────
    cur.execute("CREATE INDEX ON cell_proximity (h3_cell)")
    conn.commit()

    elapsed = time.time() - t0
    logger.info(
        f"Done — {len(rows):,} cells written to cell_proximity in {elapsed:.1f}s"
    )

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

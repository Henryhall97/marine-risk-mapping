"""Generate bathymetry depth contour lines as GeoJSON.

Reads the ``bathymetry_h3`` table (≈1 M H3 res-7 centroids with depth),
bins onto a regular 0.05° grid, smooths, extracts contour lines at
selected depth levels, and writes a GeoJSON FeatureCollection.

Output::

    data/processed/macro/bathymetry_contours.geojson

Usage::

    uv run python pipeline/aggregation/generate_contours.py
"""

import json
import logging
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter

from pipeline.utils import get_connection

matplotlib.use("Agg")  # headless backend

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Depth levels for contour lines (metres below surface, stored as negative)
DEPTH_LEVELS = [50, 100, 200, 500, 1000, 2000, 4000]

# Major contour lines (drawn thicker) — shelf break + abyss boundary
MAJOR_DEPTHS = {200, 1000, 4000}

# Grid resolution in degrees
GRID_RES = 0.05

# Gaussian smoothing sigma (grid cells)
SMOOTH_SIGMA = 1.5

OUTPUT_DIR = Path("data/processed/macro")
OUTPUT_FILE = OUTPUT_DIR / "bathymetry_contours.geojson"


def _read_bathymetry(conn) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read lat, lon, depth_m by joining bathymetry_h3 to int_hex_grid."""
    logger.info("Reading bathymetry_h3 + int_hex_grid …")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT g.cell_lat, g.cell_lon, b.depth_m"
            " FROM bathymetry_h3 b"
            " JOIN int_hex_grid g USING (h3_cell)"
        )
        rows = cur.fetchall()
    logger.info("  Read %s points", f"{len(rows):,}")
    arr = np.array(rows, dtype=np.float64)
    return arr[:, 0], arr[:, 1], arr[:, 2]


def _bin_to_grid(
    lats: np.ndarray,
    lons: np.ndarray,
    depths: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bin scattered points onto a regular grid, return centres + mean depth."""
    lat_min, lat_max = lats.min(), lats.max()
    lon_min, lon_max = lons.min(), lons.max()

    lat_edges = np.arange(lat_min, lat_max + GRID_RES, GRID_RES)
    lon_edges = np.arange(lon_min, lon_max + GRID_RES, GRID_RES)

    depth_sum, _, _ = np.histogram2d(
        lats, lons, bins=[lat_edges, lon_edges], weights=depths
    )
    count, _, _ = np.histogram2d(lats, lons, bins=[lat_edges, lon_edges])

    with np.errstate(invalid="ignore"):
        mean_depth = np.where(count > 0, depth_sum / count, np.nan)

    # Smooth to remove noise, preserving NaN regions
    # Fill NaN with 0 for filtering, then mask back
    filled = np.where(np.isnan(mean_depth), 0, mean_depth)
    smoothed = gaussian_filter(filled, sigma=SMOOTH_SIGMA)
    mask = gaussian_filter((~np.isnan(mean_depth)).astype(float), sigma=SMOOTH_SIGMA)
    with np.errstate(invalid="ignore"):
        result = np.where(mask > 0.1, smoothed / mask, np.nan)

    lat_centres = 0.5 * (lat_edges[:-1] + lat_edges[1:])
    lon_centres = 0.5 * (lon_edges[:-1] + lon_edges[1:])

    logger.info(
        "  Grid: %d × %d  (%.2f° resolution)",
        len(lat_centres),
        len(lon_centres),
        GRID_RES,
    )
    return lat_centres, lon_centres, result


def _extract_contours(
    lat_centres: np.ndarray,
    lon_centres: np.ndarray,
    depth_grid: np.ndarray,
) -> dict:
    """Run matplotlib contour and convert to GeoJSON FeatureCollection."""
    # Depths are stored as positive (below surface).
    # matplotlib contour needs a meshgrid with lon on x, lat on y.
    lon_mesh, lat_mesh = np.meshgrid(lon_centres, lat_centres)

    # Use absolute depth values (positive = deeper)
    abs_depth = np.abs(depth_grid)

    fig, ax = plt.subplots(figsize=(1, 1))
    cs = ax.contour(lon_mesh, lat_mesh, abs_depth, levels=sorted(DEPTH_LEVELS))
    plt.close(fig)

    features = []
    for i, level in enumerate(cs.levels):
        depth_m = int(level)
        coords_list: list[list[list[float]]] = []

        for seg in cs.allsegs[i]:
            if len(seg) < 2:
                continue
            # Round to 4 decimal places (≈11 m precision)
            line = [[round(float(v[0]), 4), round(float(v[1]), 4)] for v in seg]
            coords_list.append(line)

        if not coords_list:
            continue

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "depth_m": depth_m,
                    "label": f"{depth_m} m",
                    "style": ("major" if depth_m in MAJOR_DEPTHS else "minor"),
                },
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": coords_list,
                },
            }
        )
        logger.info(
            "  %4d m: %d line segments",
            depth_m,
            len(coords_list),
        )

    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    conn = get_connection()
    try:
        lats, lons, depths = _read_bathymetry(conn)
    finally:
        conn.close()

    lat_c, lon_c, grid = _bin_to_grid(lats, lons, depths)
    geojson = _extract_contours(lat_c, lon_c, grid)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(geojson, separators=(",", ":")))

    size_mb = OUTPUT_FILE.stat().st_size / 1024 / 1024
    logger.info(
        "✓ Wrote %s (%.1f MB, %d features)",
        OUTPUT_FILE,
        size_mb,
        len(geojson["features"]),
    )


if __name__ == "__main__":
    main()

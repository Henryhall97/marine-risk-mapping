"""Download US shipping lanes and routing regulations from NOAA.

Downloads nationwide shipping lane regulations from NOAA's Office
of Coast Survey MarineTransportation FeatureServer. This covers
all waters within the study bounding box and includes 8 categories of polygons:

  - Traffic Separation Schemes (TSS)
  - Traffic Separation Schemes / Traffic Lanes
  - Precautionary Areas
  - Shipping Fairways Lanes and Zones
  - Area to be Avoided (ATBA)
  - Recommended Routes
  - Particularly Sensitive Sea Area (PSSA)
  - Speed Restrictions / Right Whales

Extracted weekly from NOAA ENC chart data.

Source: NOAA Office of Coast Survey — Marine Transportation
  https://gis.charttools.noaa.gov/arcgis/rest/services/
  NavigationChartData/MarineTransportation/FeatureServer/0
"""

import logging
from pathlib import Path

import geopandas as gpd
import httpx

from pipeline.config import SHIPPING_LANES_FILE, US_BBOX

# NOAA Coast Survey — MarineTransportation FeatureServer layer 0
# "Shipping Lanes and Regulations" — nationwide polygon coverage
SERVICE_URL = (
    "https://gis.charttools.noaa.gov/arcgis/rest/services/"
    "NavigationChartData/MarineTransportation/"
    "FeatureServer/0/query"
)

# Fields: OBJECTID, THEMELAYER, INFORM, OBJNAM, SHAPE
# maxRecordCount = 10000, CRS = WGS 84
QUERY_PARAMS = {
    "where": "1=1",
    "outFields": "*",
    "f": "geojson",
    "returnGeometry": "true",
    "resultRecordCount": 5000,
}

OUTPUT_DIR: Path = SHIPPING_LANES_FILE.parent
OUTPUT_FILE: Path = SHIPPING_LANES_FILE

US_COAST_BBOX = (
    US_BBOX["lon_min"],
    US_BBOX["lat_min"],
    US_BBOX["lon_max"],
    US_BBOX["lat_max"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_shipping_features() -> gpd.GeoDataFrame:
    """Fetch all shipping lane/regulation polygons from NOAA.

    Uses offset-based pagination to handle the 10 000 record
    limit on the ArcGIS FeatureServer.  Returns a combined
    GeoDataFrame in EPSG:4326.
    """
    logger.info("Downloading shipping lanes from NOAA Coast Survey...")
    all_features: list[dict] = []
    offset = 0
    batch_size = 5000

    while True:
        params = {
            **QUERY_PARAMS,
            "resultOffset": offset,
            "resultRecordCount": batch_size,
        }
        try:
            response = httpx.get(
                SERVICE_URL,
                params=params,
                timeout=120,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error downloading shipping lanes: %s",
                e.response.status_code,
            )
            raise
        except httpx.RequestError as e:
            logger.error("Request failed for shipping lanes: %s", e)
            raise

        data = response.json()
        features = data.get("features", [])
        if not features:
            break
        all_features.extend(features)
        logger.info(
            "  Fetched %d features (offset %d)",
            len(features),
            offset,
        )
        if len(features) < batch_size:
            break
        offset += batch_size

    if not all_features:
        raise ValueError("No shipping lane features returned from service")

    geojson = {
        "type": "FeatureCollection",
        "features": all_features,
    }
    gdf = gpd.GeoDataFrame.from_features(geojson, crs="EPSG:4326")
    logger.info("Received %d total shipping lane polygons", len(gdf))
    return gdf


def filter_us_coast(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Filter features to the study bounding box.

    The service includes territories and Pacific possessions;
    we keep features whose bounding box intersects our study bbox.
    """
    lon_min, lat_min, lon_max, lat_max = US_COAST_BBOX
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        logger.info("Reprojecting from %s to EPSG:4326", gdf.crs)
        gdf = gdf.to_crs(epsg=4326)

    # Use centroid test — these are shipping polygons, some
    # may straddle the antimeridian near Alaska/Pacific.
    centroids = gdf.geometry.centroid
    mask = (
        (centroids.x >= lon_min)
        & (centroids.x <= lon_max)
        & (centroids.y >= lat_min)
        & (centroids.y <= lat_max)
    )
    filtered = gdf[mask].copy()
    logger.info(
        "Filtered to %d US features (from %d total)",
        len(filtered),
        len(gdf),
    )
    return filtered


def standardise_columns(
    gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Clean and standardise column names and values.

    Renames the ENC-derived fields to more descriptive names
    and strips whitespace from string values.
    """
    rename_map = {
        "THEMELAYER": "zone_type",
        "INFORM": "description",
        "OBJNAM": "name",
    }
    gdf = gdf.rename(columns={k: v for k, v in rename_map.items() if k in gdf.columns})
    # Strip whitespace from text columns
    for col in ("zone_type", "description", "name"):
        if col in gdf.columns:
            gdf[col] = gdf[col].astype(str).str.strip().replace("", None)
    return gdf


def log_summary(gdf: gpd.GeoDataFrame) -> None:
    """Log a summary of shipping lane types."""
    type_col = "zone_type"
    if type_col not in gdf.columns:
        return
    type_counts = gdf[type_col].value_counts()
    logger.info("Shipping lane/regulation types:")
    for zone_type, count in type_counts.items():
        logger.info("  %s: %d", zone_type, count)

    if "name" in gdf.columns:
        named = gdf["name"].dropna()
        logger.info("Named features: %d of %d", len(named), len(gdf))


def download_shipping_lanes(*, force: bool = False) -> None:
    """Download, filter, and save shipping lanes as GeoParquet."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists() and not force:
        logger.info(
            "Shipping lanes parquet already exists at %s — skipping",
            OUTPUT_FILE,
        )
        return

    if OUTPUT_FILE.exists() and force:
        OUTPUT_FILE.unlink()
        logger.info("Removed existing file (--force)")

    gdf = fetch_shipping_features()
    gdf_us = filter_us_coast(gdf)
    gdf_us = standardise_columns(gdf_us)
    log_summary(gdf_us)

    gdf_us.to_parquet(OUTPUT_FILE)
    size_mb = OUTPUT_FILE.stat().st_size / 1e6
    logger.info(
        "Saved %d shipping lane features to %s (%.1f MB)",
        len(gdf_us),
        OUTPUT_FILE,
        size_mb,
    )
    logger.info("Columns: %s", list(gdf_us.columns))


if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(
        description=(
            "Download US shipping lanes and routing regulations from NOAA Coast Survey"
        ),
    )
    _parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if file exists",
    )
    _args = _parser.parse_args()
    download_shipping_lanes(force=_args.force)

"""Download Cetacean Biologically Important Areas (BIAs) from NOAA.

Downloads the NOAA CetSound/CETMAP Biologically Important Areas
for cetaceans within the study bounding box. BIAs identify areas and times of
year that are important for feeding, migration, breeding, and
small/resident populations of cetaceans.

Source: NOAA NMFS — Cetacean & Sound Mapping (CetMap)
  https://cetsound.noaa.gov/biologically-important-areas
  ArcGIS FeatureServer:
  https://services2.arcgis.com/C8EMgrsFcRFL6LrL/ArcGIS/rest/services/
  CetMap_BIA/FeatureServer/0
"""

import logging

import geopandas as gpd
import httpx

from pipeline.config import BIA_FILE, US_BBOX

# NOAA CetMap BIA ArcGIS Feature Service — query endpoint
BIA_SERVICE_URL = (
    "https://services2.arcgis.com/C8EMgrsFcRFL6LrL/ArcGIS/rest/services/"
    "CetMap_BIA/FeatureServer/0/query"
)

# Query all features with geometry in GeoJSON format
BIA_QUERY_PARAMS = {
    "where": "1=1",
    "outFields": "*",
    "f": "geojson",
    "returnGeometry": "true",
    "resultRecordCount": 5000,
}

OUTPUT_DIR = BIA_FILE.parent
OUTPUT_FILE = BIA_FILE

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


def fetch_bia_features() -> gpd.GeoDataFrame:
    """Fetch all BIA features from NOAA ArcGIS FeatureServer."""
    logger.info("Downloading Cetacean BIAs from NOAA ArcGIS...")
    all_features: list[dict] = []
    offset = 0
    batch_size = 2000

    while True:
        params = {
            **BIA_QUERY_PARAMS,
            "resultOffset": offset,
            "resultRecordCount": batch_size,
        }
        try:
            response = httpx.get(
                BIA_SERVICE_URL,
                params=params,
                timeout=120,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error downloading BIAs: %s",
                e.response.status_code,
            )
            raise
        except httpx.RequestError as e:
            logger.error("Request failed for BIA data: %s", e)
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
        raise ValueError("No BIA features returned from service")

    geojson = {
        "type": "FeatureCollection",
        "features": all_features,
    }
    gdf = gpd.GeoDataFrame.from_features(geojson, crs="EPSG:4326")
    logger.info("Received %d total BIA polygons", len(gdf))
    return gdf


def filter_us_coast(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Filter BIA features to study bounding box."""
    lon_min, lat_min, lon_max, lat_max = US_COAST_BBOX
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        logger.info("Reprojecting from %s to EPSG:4326", gdf.crs)
        gdf = gdf.to_crs(epsg=4326)

    bounds = gdf.geometry.bounds
    mask = (
        (bounds["minx"] >= lon_min)
        & (bounds["maxx"] <= lon_max)
        & (bounds["miny"] >= lat_min)
        & (bounds["maxy"] <= lat_max)
    )
    filtered = gdf[mask].copy()
    logger.info(
        "Filtered to %d US Coast BIAs (from %d total)",
        len(filtered),
        len(gdf),
    )
    return filtered


def log_bia_summary(gdf: gpd.GeoDataFrame) -> None:
    """Log a summary of BIA types and species."""
    if "BIA_Type" in gdf.columns:
        type_counts = gdf["BIA_Type"].value_counts()
        logger.info("BIA types:")
        for bia_type, count in type_counts.items():
            logger.info("  %s: %d", bia_type, count)
    if "Species" in gdf.columns:
        species_counts = gdf["Species"].value_counts()
        logger.info("Species (%d unique):", len(species_counts))
        for species, count in species_counts.head(10).items():
            logger.info("  %s: %d", species, count)


def download_bia_data(*, force: bool = False) -> None:
    """Download, filter, and save BIA data as GeoParquet."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists() and not force:
        logger.info(
            "BIA parquet already exists at %s — skipping",
            OUTPUT_FILE,
        )
        return

    if OUTPUT_FILE.exists() and force:
        OUTPUT_FILE.unlink()
        logger.info("Removed existing BIA file (--force)")

    gdf = fetch_bia_features()
    gdf_us = filter_us_coast(gdf)
    log_bia_summary(gdf_us)

    gdf_us.to_parquet(OUTPUT_FILE)
    size_mb = OUTPUT_FILE.stat().st_size / 1e6
    logger.info(
        "Saved %d BIA features to %s (%.1f MB)",
        len(gdf_us),
        OUTPUT_FILE,
        size_mb,
    )
    logger.info("Columns: %s", list(gdf_us.columns))


if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(description="Download NOAA Cetacean BIAs")
    _parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if file exists",
    )
    _args = _parser.parse_args()
    download_bia_data(force=_args.force)

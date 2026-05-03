"""Download whale ESA Critical Habitat designations from NOAA.

Downloads whale-specific Critical Habitat polygons from the NMFS
ESA Critical Habitat MapServer. These are legally designated areas
under the Endangered Species Act that are essential for the
conservation of listed whale species.

We filter to whale species only (layers 190–197 + proposed 244),
skipping fish, corals, sea turtles, and other non-whale taxa.

Source: NMFS ESA Critical Habitat MapServer
  https://maps.fisheries.noaa.gov/server/rest/services/
  All_NMFS_Critical_Habitat/MapServer

Whale layers (designated):
  190 — Beluga Whale (Cook Inlet DPS)
  191 — False Killer Whale (Main Hawaiian Islands Insular DPS)
  192 — Humpback Whale (Central America DPS)
  193 — Humpback Whale (Mexico DPS)
  194 — Humpback Whale (Western North Pacific DPS)
  195 — Killer Whale (Southern Resident DPS)
  196 — North Atlantic Right Whale
  197 — North Pacific Right Whale
Proposed:
  244 — Rice's Whale (proposed 2023)
"""

import logging

import geopandas as gpd
import httpx
import pandas as pd

from pipeline.config import CRITICAL_HABITAT_FILE, US_BBOX

# NMFS Critical Habitat MapServer base URL
CH_BASE_URL = (
    "https://maps.fisheries.noaa.gov/server/rest/services/"
    "All_NMFS_Critical_Habitat/MapServer"
)

# Whale-specific layer IDs and their species names
WHALE_LAYERS: dict[int, str] = {
    190: "beluga_whale_cook_inlet",
    191: "false_killer_whale_hawaii",
    192: "humpback_whale_central_america",
    193: "humpback_whale_mexico",
    194: "humpback_whale_western_north_pacific",
    195: "killer_whale_southern_resident",
    196: "north_atlantic_right_whale",
    197: "north_pacific_right_whale",
    244: "rices_whale_proposed",
}

QUERY_PARAMS = {
    "where": "1=1",
    "outFields": "*",
    "f": "geojson",
    "returnGeometry": "true",
}

OUTPUT_DIR = CRITICAL_HABITAT_FILE.parent
OUTPUT_FILE = CRITICAL_HABITAT_FILE

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


def fetch_layer(layer_id: int, species_name: str) -> gpd.GeoDataFrame | None:
    """Fetch a single Critical Habitat layer from MapServer."""
    url = f"{CH_BASE_URL}/{layer_id}/query"
    logger.info("  Fetching layer %d (%s)...", layer_id, species_name)
    try:
        response = httpx.get(
            url,
            params=QUERY_PARAMS,
            timeout=120,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.warning(
            "  HTTP %s for layer %d — skipping",
            e.response.status_code,
            layer_id,
        )
        return None
    except httpx.RequestError as e:
        logger.warning(
            "  Request failed for layer %d: %s — skipping",
            layer_id,
            e,
        )
        return None

    data = response.json()
    features = data.get("features", [])
    if not features:
        logger.warning(
            "  No features for layer %d (%s)",
            layer_id,
            species_name,
        )
        return None

    gdf = gpd.GeoDataFrame.from_features(
        {"type": "FeatureCollection", "features": features},
        crs="EPSG:4326",
    )
    gdf["species_label"] = species_name
    gdf["layer_id"] = layer_id
    gdf["is_proposed"] = species_name.endswith("_proposed")
    logger.info("  Got %d polygons for %s", len(gdf), species_name)
    return gdf


def fetch_all_whale_habitat() -> gpd.GeoDataFrame:
    """Fetch all whale Critical Habitat layers and combine."""
    logger.info(
        "Downloading whale Critical Habitat from NMFS MapServer (%d layers)...",
        len(WHALE_LAYERS),
    )
    frames: list[gpd.GeoDataFrame] = []
    for layer_id, species_name in WHALE_LAYERS.items():
        gdf = fetch_layer(layer_id, species_name)
        if gdf is not None and len(gdf) > 0:
            frames.append(gdf)

    if not frames:
        raise ValueError("No whale Critical Habitat features returned")

    combined = pd.concat(frames, ignore_index=True)
    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs="EPSG:4326")
    logger.info(
        "Combined %d total Critical Habitat polygons across %d species",
        len(combined),
        len(frames),
    )
    return combined


def filter_us_coast(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Filter to study bounding box."""
    lon_min, lat_min, lon_max, lat_max = US_COAST_BBOX
    if gdf.crs and gdf.crs.to_epsg() != 4326:
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
        "Filtered to %d US Coast Critical Habitat polygons (from %d total)",
        len(filtered),
        len(gdf),
    )
    return filtered


def download_critical_habitat(*, force: bool = False) -> None:
    """Download, filter, and save whale Critical Habitat."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists() and not force:
        logger.info(
            "Critical Habitat parquet already exists at %s — skipping",
            OUTPUT_FILE,
        )
        return

    if OUTPUT_FILE.exists() and force:
        OUTPUT_FILE.unlink()
        logger.info("Removed existing Critical Habitat file (--force)")

    gdf = fetch_all_whale_habitat()
    gdf_us = filter_us_coast(gdf)

    # Log summary
    for species, count in gdf_us["species_label"].value_counts().items():
        logger.info("  %s: %d polygons", species, count)

    gdf_us.to_parquet(OUTPUT_FILE)
    size_mb = OUTPUT_FILE.stat().st_size / 1e6
    logger.info(
        "Saved %d Critical Habitat features to %s (%.1f MB)",
        len(gdf_us),
        OUTPUT_FILE,
        size_mb,
    )
    logger.info("Columns: %s", list(gdf_us.columns))


if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(description="Download whale ESA Critical Habitat")
    _parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if file exists",
    )
    _args = _parser.parse_args()
    download_critical_habitat(force=_args.force)

"""Download NARW Seasonal Management Area polygons from NOAA.

Downloads the current active Right Whale Seasonal Management
Areas (SMAs) defined under 50 CFR § 224.105 from NOAA's
ArcGIS feature service. These are the 10 zones where vessels
≥65 ft must travel at ≤10 knots during specified seasons.

Source: NOAA Fisheries — NARW Seasonal Management Areas
  https://services2.arcgis.com/C8EMgrsFcRFL6LrL/ArcGIS/rest/services/
  Seasonal_Management_Areas/FeatureServer/3
"""

import json
import logging
from pathlib import Path

import httpx

# ArcGIS Feature Service — layer 3 = SMA Polygons
SMA_SERVICE_URL = (
    "https://services2.arcgis.com/C8EMgrsFcRFL6LrL/ArcGIS/rest/services/"
    "Seasonal_Management_Areas/FeatureServer/3/query"
)
SMA_QUERY_PARAMS = {
    "where": "1=1",
    "outFields": "*",
    "f": "geojson",
    "returnGeometry": "true",
}

OUTPUT_DIR = Path("data/raw/mpa/seasonal_management_areas")
OUTPUT_FILE = OUTPUT_DIR / "seasonal_management_areas.geojson"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def download_sma(force: bool = False) -> Path:
    """Download SMA polygons from NOAA ArcGIS feature service.

    Args:
        force: If True, re-download even if file already exists.

    Returns:
        Path to the saved GeoJSON file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists() and not force:
        logger.info(
            "SMA GeoJSON already exists: %s — skipping (use force=True to re-download)",
            OUTPUT_FILE,
        )
        return OUTPUT_FILE

    logger.info("Downloading NARW Seasonal Management Areas from NOAA ArcGIS...")

    try:
        response = httpx.get(
            SMA_SERVICE_URL,
            params=SMA_QUERY_PARAMS,
            timeout=60,
            follow_redirects=True,
        )
        response.raise_for_status()

    except httpx.HTTPStatusError as e:
        logger.error("HTTP error downloading SMAs: %s", e.response.status_code)
        raise
    except httpx.RequestError as e:
        logger.error("Request failed for SMA data: %s", e)
        raise

    data = response.json()

    if data.get("type") != "FeatureCollection":
        raise ValueError(f"Unexpected response type: {data.get('type')}")

    n_features = len(data.get("features", []))
    if n_features == 0:
        raise ValueError("No SMA features returned from service")

    logger.info("Received %d SMA polygons:", n_features)
    for feat in data["features"]:
        props = feat["properties"]
        logger.info(
            "  %s (%s) — %s/%s to %s/%s",
            props["zone_name"],
            props["zone_abbr"],
            props["st_mo"],
            props["st_day"],
            props["end_mo"],
            props["end_day"],
        )

    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f)

    size_kb = OUTPUT_FILE.stat().st_size / 1024
    logger.info("Saved SMA GeoJSON (%.1f KB) to %s", size_kb, OUTPUT_FILE)

    return OUTPUT_FILE


if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(description="Download NARW SMAs")
    _parser.add_argument(
        "--force", action="store_true", help="Re-download even if file exists"
    )
    _args = _parser.parse_args()
    download_sma(force=_args.force)

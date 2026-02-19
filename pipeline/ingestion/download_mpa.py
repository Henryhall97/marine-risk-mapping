"""Download Marine Protected Areas data from NOAA MPA Inventory.

Downloads the NOAA MPA Inventory GIS geodatabase (2023 edition),
extracts it, and converts to GeoParquet for consistent storage
with other datasets. Filters to US coastal waters.
"""

import logging
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import httpx

# NOAA MPA Inventory 2023 — downloadable GIS data (zipped shapefile)
MPA_URL = (
    "https://marineprotectedareas.noaa.gov/media/data/"
    "NOAA_Marine_Protected_Areas_Inventory_2023.zip"
)
OUTPUT_DIR = Path("data/raw/mpa")
OUTPUT_FILE = OUTPUT_DIR / "mpa_inventory.parquet"
CHUNK_SIZE = 65536  # 64KB chunks for download

# Bounding box for US Coast (approximate)
# lon_min, lat_min, lon_max, lat_max
US_COAST_BBOX = (-130.0, 24.0, -65.0, 49.0)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def download_mpa_zip(output_path: Path) -> Path:
    """Download the NOAA MPA Inventory zip file.

    Args:
        output_path: Directory to save the zip file.

    Returns:
        Path to the downloaded zip file.
    """
    zip_path = output_path / "mpa_inventory.zip"

    if zip_path.exists():
        logger.info("Zip file already exists, skipping download")
        return zip_path

    logger.info("Downloading MPA Inventory from NOAA...")

    try:
        with httpx.stream(
            "GET", MPA_URL, follow_redirects=True, timeout=300
        ) as response:
            response.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                    f.write(chunk)

        size_mb = zip_path.stat().st_size / 1e6
        logger.info("Downloaded MPA zip (%.1f MB)", size_mb)
        return zip_path

    except httpx.HTTPStatusError as e:
        logger.error("HTTP error downloading MPA data: %s", e.response.status_code)
        if zip_path.exists():
            zip_path.unlink()
        raise

    except httpx.RequestError as e:
        logger.error("Request failed for MPA data: %s", e)
        if zip_path.exists():
            zip_path.unlink()
        raise


def extract_and_read_geodatabase(zip_path: Path) -> gpd.GeoDataFrame:
    """Extract File Geodatabase from zip and read into GeoDataFrame.

    Args:
        zip_path: Path to the downloaded zip file.

    Returns:
        GeoDataFrame with MPA boundaries.
    """
    logger.info("Extracting and reading geodatabase...")

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)

        # Find the .gdb directory inside the extracted contents
        gdb_dirs = list(Path(tmpdir).rglob("*.gdb"))
        if not gdb_dirs:
            raise FileNotFoundError("No .gdb directory found in downloaded zip")

        logger.info("Found geodatabase: %s", gdb_dirs[0].name)
        gdf = gpd.read_file(gdb_dirs[0])

    logger.info("Read %d MPA features", len(gdf))
    return gdf


def filter_us_coast(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Filter MPA features to the US Coast bounding box.

    Args:
        gdf: Full MPA GeoDataFrame.

    Returns:
        Filtered GeoDataFrame with only US Coast MPAs.
    """
    lon_min, lat_min, lon_max, lat_max = US_COAST_BBOX

    # Ensure CRS is WGS84 for consistent lon/lat filtering
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        logger.info("Reprojecting from %s to EPSG:4326", gdf.crs)
        gdf = gdf.to_crs(epsg=4326)

    # Filter using bounding box intersection
    bounds = gdf.geometry.bounds
    mask = (
        (bounds["minx"] >= lon_min)
        & (bounds["maxx"] <= lon_max)
        & (bounds["miny"] >= lat_min)
        & (bounds["maxy"] <= lat_max)
    )
    filtered = gdf[mask].copy()

    logger.info(
        "Filtered to %d US Coast MPAs (from %d total)",
        len(filtered),
        len(gdf),
    )
    return filtered


def save_to_parquet(gdf: gpd.GeoDataFrame, output_path: Path) -> None:
    """Save GeoDataFrame to GeoParquet format.

    Args:
        gdf: GeoDataFrame to save.
        output_path: Path for the output parquet file.
    """
    gdf.to_parquet(output_path)
    size_mb = output_path.stat().st_size / 1e6
    logger.info("Saved %d features to %s (%.1f MB)", len(gdf), output_path, size_mb)


def download_mpa_data() -> None:
    """Download, filter, and save MPA data as GeoParquet."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Skip if output already exists
    if OUTPUT_FILE.exists():
        logger.info("MPA parquet already exists at %s — skipping", OUTPUT_FILE)
        return

    # Step 1: Download zip
    zip_path = download_mpa_zip(OUTPUT_DIR)

    # Step 2: Extract and read geodatabase
    gdf = extract_and_read_geodatabase(zip_path)

    # Step 3: Filter to US Coast
    gdf_us = filter_us_coast(gdf)

    # Step 4: Save as GeoParquet
    save_to_parquet(gdf_us, OUTPUT_FILE)

    # Step 5: Clean up zip file
    zip_path.unlink()
    logger.info("Cleaned up zip file")

    # Log column summary
    logger.info("Columns: %s", list(gdf_us.columns))
    logger.info("CRS: %s", gdf_us.crs)


if __name__ == "__main__":
    download_mpa_data()

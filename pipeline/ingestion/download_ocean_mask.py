"""Download Natural Earth ocean polygon for land/inland filtering.

Downloads the 1:10m ocean shapefile from Natural Earth and saves
it as GeoParquet.  This polygon is loaded into PostGIS as the
``ocean_mask`` table and used in ``int_bathymetry`` to distinguish
open-ocean H3 cells from land and inland water bodies (e.g. Great
Lakes).  Without this mask, inland lakes with negative GEBCO depth
values (they *are* below sea level) slip through the ``is_land``
flag and pollute the risk heatmap.
"""

import logging
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import httpx

from pipeline.config import US_BBOX

# Natural Earth 1:10m ocean polygon — authoritative coastline mask
NE_OCEAN_URL = "https://naciscdn.org/naturalearth/10m/physical/ne_10m_ocean.zip"

OUTPUT_DIR = Path("data/raw/ocean_mask")
OUTPUT_FILE = OUTPUT_DIR / "ocean_mask.parquet"
CHUNK_SIZE = 65536

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


def download_ocean_mask(*, force: bool = False) -> None:
    """Download Natural Earth ocean polygon and save as parquet.

    Args:
        force: Re-download even if output file exists.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists() and not force:
        logger.info("Ocean mask already exists: %s — skipping", OUTPUT_FILE)
        return
    if OUTPUT_FILE.exists() and force:
        logger.info("Force mode — re-downloading ocean mask")

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "ne_10m_ocean.zip"

        # Download
        logger.info("Downloading Natural Earth ocean polygon...")
        with httpx.stream("GET", NE_OCEAN_URL, timeout=120) as resp:
            resp.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=CHUNK_SIZE):
                    f.write(chunk)
        logger.info("Downloaded %s", zip_path)

        # Extract
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)
        logger.info("Extracted to %s", tmpdir)

        # Read shapefile
        shp_files = list(Path(tmpdir).glob("*.shp"))
        if not shp_files:
            raise FileNotFoundError("No .shp file found in Natural Earth archive")
        gdf = gpd.read_file(shp_files[0])
        logger.info("Read %d ocean polygon(s), CRS=%s", len(gdf), gdf.crs)

        # Clip to US bbox (with generous margin for coastal cells)
        gdf = gdf.clip(US_COAST_BBOX)
        logger.info("Clipped to US bbox: %d polygon(s)", len(gdf))

        # Ensure CRS is WGS-84
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        # Save as parquet
        gdf.to_parquet(OUTPUT_FILE)
        logger.info(
            "Saved ocean mask: %s (%.1f MB)",
            OUTPUT_FILE,
            OUTPUT_FILE.stat().st_size / 1e6,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download Natural Earth ocean mask")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if file exists",
    )
    args = parser.parse_args()
    download_ocean_mask(force=args.force)

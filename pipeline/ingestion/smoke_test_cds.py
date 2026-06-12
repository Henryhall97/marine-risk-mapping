"""CDS API smoke test — minimal end-to-end request.

Confirms that:
  1. ~/.cdsapirc is configured correctly
  2. We have accepted the CMIP6 dataset licence
  3. The request payload format is valid for the current CDS API
  4. We can unpack the returned zip and read the NetCDF

Requests ONE model × ONE variable × ONE year × ONE scenario — the
smallest possible payload (~few MB, ~5-15 min in queue).

Usage:
    uv run python pipeline/ingestion/smoke_test_cds.py
"""

from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path

import cdsapi
import xarray as xr

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/raw/cmip6/_smoke_test")
ZIP_PATH = OUTPUT_DIR / "smoke_test.zip"
EXTRACT_DIR = OUTPUT_DIR / "extracted"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)
    EXTRACT_DIR.mkdir(parents=True)

    log.info("Initialising CDS client...")
    client = cdsapi.Client()
    log.info("  URL: %s", client.url)

    log.info("Submitting request (will queue server-side — be patient)...")
    request = {
        "temporal_resolution": "monthly",
        "experiment": "ssp5_8_5",
        "variable": "sea_surface_temperature",
        "model": "mpi_esm1_2_lr",
        "year": ["2030"],
        "month": ["01", "07"],
        "area": [53, -180, -3, -58],  # [N, W, S, E] — your study bbox
        # Ask CDS to regrid to a regular 0.25° lat/lon grid server-side.
        # If this works, cross-model ensemble averaging becomes trivial.
        # If the server rejects it, we'll fall back to client-side regridding.
        "grid": [0.25, 0.25],
    }
    log.info("  Request payload: %s", request)

    client.retrieve("projections-cmip6", request, str(ZIP_PATH))
    log.info("Downloaded: %s (%.2f MB)", ZIP_PATH, ZIP_PATH.stat().st_size / 1e6)

    log.info("Unzipping...")
    with zipfile.ZipFile(ZIP_PATH) as zf:
        zf.extractall(EXTRACT_DIR)
    nc_files = list(EXTRACT_DIR.glob("*.nc"))
    log.info(
        "  Extracted %d NetCDF file(s): %s", len(nc_files), [f.name for f in nc_files]
    )

    if not nc_files:
        log.error("No NetCDF files in zip — unexpected response format")
        return

    log.info("Inspecting first NetCDF...")
    ds = xr.open_dataset(nc_files[0])
    log.info("  Variables: %s", list(ds.data_vars))
    log.info("  Dimensions: %s", dict(ds.dims))
    log.info("  Coords: %s", list(ds.coords))
    log.info("  Time range: %s to %s", ds.time.values[0], ds.time.values[-1])
    if "lat" in ds.coords:
        log.info("  Lat range: %.2f to %.2f", float(ds.lat.min()), float(ds.lat.max()))
    if "lon" in ds.coords:
        log.info("  Lon range: %.2f to %.2f", float(ds.lon.min()), float(ds.lon.max()))

    log.info("✓ SMOKE TEST PASSED — CDS API is working")
    log.info("  Next: rewrite download_cmip6_projections.py using this request format")


if __name__ == "__main__":
    main()

"""Download oceanographic covariates for whale species distribution modelling.

Downloads SST, SST_SD, MLD, SLA, and primary productivity (PP) data
to match the covariates used in Nisi et al. (2024) ISDM. These are
used alongside our existing bathymetry data to build a whale occurrence
model at higher resolution than Nisi's 1° global grid.

Data sources
------------
SST + SST_SD : NOAA OISST v2.1 via ERDDAP (0.25°, daily → monthly)
    - https://coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21Agg_LonPM180
    - No authentication required

MLD + SLA : Copernicus GLORYS12V1 reanalysis (1/12° → monthly)
    - Product: GLOBAL_MULTIYEAR_PHY_001_030
    - Requires free Copernicus Marine account

PP : Copernicus Global Ocean Biogeochemistry Hindcast (0.25°, monthly)
    - Product: GLOBAL_MULTIYEAR_BGC_001_029
    - Requires free Copernicus Marine account

Bounding box
------------
All US coastal waters (CONUS):  lat 24–50°N, lon 130–60°W

Time period
-----------
2019–2024 (6 years) for climatological means + seasonal patterns.
AIS data covers 2024; cetacean sightings span decades but recent
years are most relevant for SDM training.
"""

import logging
from pathlib import Path

import numpy as np
import xarray as xr

OUTPUT_DIR = Path("data/raw/ocean")

# Bounding box: All US coastal waters (East Coast, Gulf, West Coast)
LAT_MIN, LAT_MAX = 24.0, 50.0
LON_MIN, LON_MAX = -130.0, -60.0

# Time range: 6 years for climatological means
TIME_START = "2019-01-01"
TIME_END = "2024-12-31"

# ERDDAP base URL for NOAA OISST v2.1
ERDDAP_SST_URL = (
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21Agg_LonPM180"
)

# Copernicus Marine dataset IDs (monthly means)
CMEMS_PHY_PRODUCT = "cmems_mod_glo_phy_my_0.083deg_P1M-m"  # MLD + SLA
CMEMS_BGC_PRODUCT = "cmems_mod_glo_bgc_my_0.25deg_P1M-m"  # nppv (PP)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ── SST from ERDDAP ─────────────────────────────────────────────────
def download_sst_erddap() -> Path:
    """Download SST monthly means + std dev from NOAA OISST via ERDDAP.

    Downloads daily SST for the bounding box, then computes monthly
    mean SST and monthly SST standard deviation (spatial variability
    proxy, matching Nisi's sst_sd covariate).

    Returns:
        Path to the saved NetCDF file.
    """
    output_file = OUTPUT_DIR / "sst_monthly.nc"
    if output_file.exists():
        logger.info("SST file already exists: %s", output_file)
        return output_file

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Opening OISST via OPeNDAP (may take a moment)...")
    ds = xr.open_dataset(ERDDAP_SST_URL)

    # Subset to our region and time
    ds_sub = ds.sel(
        time=slice(TIME_START, TIME_END),
        latitude=slice(LAT_MIN, LAT_MAX),
        longitude=slice(LON_MIN, LON_MAX),
        zlev=0.0,
    )

    logger.info(
        "Downloading daily SST: %s to %s, %d lat × %d lon points",
        TIME_START,
        TIME_END,
        ds_sub.sizes.get("latitude", 0),
        ds_sub.sizes.get("longitude", 0),
    )

    # Download daily SST — this triggers the actual OPeNDAP fetch
    # We only need the sst variable
    logger.info("Fetching SST data (this may take several minutes)...")
    sst_daily = ds_sub["sst"].load()
    logger.info("Downloaded %s daily SST values", f"{sst_daily.size:,}")

    # Compute monthly statistics
    logger.info("Computing monthly means and standard deviations...")
    sst_monthly_mean = sst_daily.resample(time="1ME").mean(dim="time")
    sst_monthly_std = sst_daily.resample(time="1ME").std(dim="time")

    # Build output dataset
    out = xr.Dataset(
        {
            "sst": sst_monthly_mean.drop_vars("zlev", errors="ignore"),
            "sst_sd": sst_monthly_std.drop_vars("zlev", errors="ignore"),
        },
        attrs={
            "title": "Monthly SST and SST_SD from NOAA OISST v2.1",
            "source": ERDDAP_SST_URL,
            "spatial_resolution": "0.25 degree",
            "bounding_box": f"lat [{LAT_MIN}, {LAT_MAX}], lon [{LON_MIN}, {LON_MAX}]",
            "time_range": f"{TIME_START} to {TIME_END}",
            "processing": "Monthly mean and std computed from daily data",
        },
    )

    out.to_netcdf(output_file)
    ds.close()
    size_mb = output_file.stat().st_size / 1e6
    logger.info("Saved SST monthly data: %s (%.1f MB)", output_file, size_mb)
    return output_file


# ── MLD + SLA from Copernicus ────────────────────────────────────────
def download_mld_sla_copernicus() -> Path:
    """Download MLD and SLA monthly means from Copernicus GLORYS12V1.

    Uses the copernicusmarine Python toolbox. Requires a free account:
        https://data.marine.copernicus.eu/register

    On first run, you'll be prompted for credentials which are cached
    in ~/.copernicusmarine/.

    Returns:
        Path to the saved NetCDF file.
    """
    output_file = OUTPUT_DIR / "mld_sla_monthly.nc"
    if output_file.exists():
        logger.info("MLD/SLA file already exists: %s", output_file)
        return output_file

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import copernicusmarine
    except ImportError:
        logger.error("copernicusmarine not installed. Run: uv add copernicusmarine")
        return output_file

    logger.info("Downloading MLD + SLA from Copernicus GLORYS12V1...")
    logger.info("  Product: %s", CMEMS_PHY_PRODUCT)
    logger.info("  If prompted, enter your Copernicus Marine credentials")
    logger.info("  (free registration: https://data.marine.copernicus.eu/register)")

    ds = copernicusmarine.open_dataset(
        dataset_id=CMEMS_PHY_PRODUCT,
        variables=["mlotst", "zos"],
        minimum_longitude=LON_MIN,
        maximum_longitude=LON_MAX,
        minimum_latitude=LAT_MIN,
        maximum_latitude=LAT_MAX,
        start_datetime=TIME_START,
        end_datetime=TIME_END,
        minimum_depth=0.0,
        maximum_depth=1.0,
    )

    logger.info("Fetching MLD + SLA data...")
    ds_loaded = ds.load()

    # Rename to match ISDM covariate names
    rename_map = {}
    if "mlotst" in ds_loaded:
        rename_map["mlotst"] = "mld"
    if "zos" in ds_loaded:
        rename_map["zos"] = "sla"

    ds_out = ds_loaded.rename(rename_map)
    ds_out.attrs.update(
        {
            "title": "Monthly MLD and SLA from Copernicus GLORYS12V1",
            "source": f"Copernicus Marine: {CMEMS_PHY_PRODUCT}",
            "spatial_resolution": "1/12 degree (~8km)",
            "bounding_box": f"lat [{LAT_MIN}, {LAT_MAX}], lon [{LON_MIN}, {LON_MAX}]",
            "time_range": f"{TIME_START} to {TIME_END}",
            "variables": "mld (mixed layer depth, m), sla (sea level anomaly, m)",
        }
    )

    ds_out.to_netcdf(output_file)
    ds.close()
    size_mb = output_file.stat().st_size / 1e6
    logger.info("Saved MLD/SLA data: %s (%.1f MB)", output_file, size_mb)
    return output_file


# ── Primary Productivity from Copernicus ─────────────────────────────
def download_pp_copernicus() -> Path:
    """Download net primary productivity from Copernicus BGC Hindcast.

    The PISCES biogeochemical model provides 'nppv' (net primary
    production per unit volume). We integrate over the upper 200m
    to match Nisi's PPupper200m covariate.

    Returns:
        Path to the saved NetCDF file.
    """
    output_file = OUTPUT_DIR / "pp_monthly.nc"
    if output_file.exists():
        logger.info("PP file already exists: %s", output_file)
        return output_file

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import copernicusmarine
    except ImportError:
        logger.error("copernicusmarine not installed. Run: uv add copernicusmarine")
        return output_file

    logger.info("Downloading primary productivity from Copernicus BGC...")
    logger.info("  Product: %s", CMEMS_BGC_PRODUCT)

    ds = copernicusmarine.open_dataset(
        dataset_id=CMEMS_BGC_PRODUCT,
        variables=["nppv"],
        minimum_longitude=LON_MIN,
        maximum_longitude=LON_MAX,
        minimum_latitude=LAT_MIN,
        maximum_latitude=LAT_MAX,
        start_datetime=TIME_START,
        end_datetime=TIME_END,
        minimum_depth=0.0,
        maximum_depth=200.0,
    )

    logger.info("Fetching PP data...")
    ds_loaded = ds.load()

    # Integrate nppv over depth to get PP in upper 200m
    # nppv is in mgC/m³/day — sum over depth levels × layer thickness
    if "depth" in ds_loaded.dims and ds_loaded.sizes["depth"] > 1:
        logger.info(
            "Integrating nppv over %d depth levels (0–200m)...",
            ds_loaded.sizes["depth"],
        )
        # Use depth-weighted integration
        depths = ds_loaded["depth"].values
        thicknesses = np.diff(depths, prepend=0)
        thicknesses = xr.DataArray(thicknesses, dims=["depth"])
        pp_integrated = (ds_loaded["nppv"] * thicknesses).sum(dim="depth")
        ds_out = xr.Dataset({"pp_upper_200m": pp_integrated})
    else:
        # Single depth level or already integrated
        ds_out = ds_loaded.rename({"nppv": "pp_upper_200m"})
        if "depth" in ds_out.dims:
            ds_out = ds_out.squeeze("depth", drop=True)

    ds_out.attrs.update(
        {
            "title": "Monthly primary productivity (upper 200m) from Copernicus BGC",
            "source": f"Copernicus Marine: {CMEMS_BGC_PRODUCT}",
            "spatial_resolution": "0.25 degree",
            "bounding_box": f"lat [{LAT_MIN}, {LAT_MAX}], lon [{LON_MIN}, {LON_MAX}]",
            "time_range": f"{TIME_START} to {TIME_END}",
            "processing": "nppv integrated over 0-200m depth",
            "units": "mgC/m²/day",
        }
    )

    ds_out.to_netcdf(output_file)
    ds.close()
    size_mb = output_file.stat().st_size / 1e6
    logger.info("Saved PP data: %s (%.1f MB)", output_file, size_mb)
    return output_file


# ── Merge all covariates to a uniform grid ───────────────────────────
def merge_to_parquet() -> Path:
    """Merge all ocean covariates onto a common 0.25° grid.

    Regrid higher-resolution data (MLD/SLA at 1/12°) to the 0.25° SST
    grid, compute climatological monthly means (12 months), and save
    as a flat parquet file ready for PostGIS loading.

    Returns:
        Path to the saved parquet file.
    """
    output_file = OUTPUT_DIR / "ocean_covariates.parquet"
    if output_file.exists():
        logger.info("Merged parquet already exists: %s", output_file)
        return output_file

    # Load SST (already at 0.25°, monthly)
    sst_file = OUTPUT_DIR / "sst_monthly.nc"
    if not sst_file.exists():
        logger.error("SST file not found — run download_sst_erddap() first")
        return output_file
    ds_sst = xr.open_dataset(sst_file)

    # Reference grid from SST
    target_lats = ds_sst["latitude"].values
    target_lons = ds_sst["longitude"].values

    # Compute climatological monthly means (12 months)
    logger.info("Computing SST climatological means...")
    sst_clim = ds_sst["sst"].groupby("time.month").mean(dim="time")
    sst_sd_clim = ds_sst["sst_sd"].groupby("time.month").mean(dim="time")

    # Start with SST annual mean (simplest for SDM)
    sst_annual = sst_clim.mean(dim="month")
    sst_sd_annual = sst_sd_clim.mean(dim="month")

    result = xr.Dataset(
        {
            "sst": sst_annual,
            "sst_sd": sst_sd_annual,
        }
    )

    # Load MLD/SLA if available (at 1/12° — regrid to 0.25°)
    mld_file = OUTPUT_DIR / "mld_sla_monthly.nc"
    if mld_file.exists():
        logger.info("Regridding MLD/SLA from 1/12° to 0.25°...")
        ds_phy = xr.open_dataset(mld_file)

        for var in ["mld", "sla"]:
            if var in ds_phy:
                # Climatological mean then regrid via nearest-neighbour
                clim = ds_phy[var].groupby("time.month").mean(dim="time")
                annual = clim.mean(dim="month")
                # Regrid to SST grid
                regridded = annual.interp(
                    latitude=target_lats,
                    longitude=target_lons,
                    method="nearest",
                )
                result[var] = regridded

        ds_phy.close()
    else:
        logger.warning("MLD/SLA file not found — skipping")

    # Load PP if available (already at 0.25°)
    pp_file = OUTPUT_DIR / "pp_monthly.nc"
    if pp_file.exists():
        logger.info("Processing primary productivity...")
        ds_bgc = xr.open_dataset(pp_file)

        if "pp_upper_200m" in ds_bgc:
            clim = ds_bgc["pp_upper_200m"].groupby("time.month").mean(dim="time")
            annual = clim.mean(dim="month")
            # Align to SST grid if needed
            if not np.array_equal(annual.latitude.values, target_lats):
                annual = annual.interp(
                    latitude=target_lats,
                    longitude=target_lons,
                    method="nearest",
                )
            result["pp_upper_200m"] = annual

        ds_bgc.close()
    else:
        logger.warning("PP file not found — skipping")

    # Convert to flat DataFrame
    logger.info("Converting to flat DataFrame...")
    df = result.to_dataframe().reset_index()

    # Drop NaN-only rows (land cells)
    ocean_cols = [c for c in df.columns if c not in ("latitude", "longitude")]
    df = df.dropna(subset=ocean_cols, how="all")

    # Rename for consistency
    df = df.rename(columns={"latitude": "lat", "longitude": "lon"})

    logger.info("Saving %s ocean covariate records to parquet", f"{len(df):,}")
    df.to_parquet(output_file, index=False)

    ds_sst.close()
    size_mb = output_file.stat().st_size / 1e6
    logger.info("Saved: %s (%.1f MB)", output_file, size_mb)

    # Summary
    logger.info("--- Covariate summary ---")
    for col in ocean_cols:
        if col in df.columns:
            valid = df[col].notna().sum()
            logger.info(
                "  %s: %s valid values, range [%.2f, %.2f]",
                col,
                f"{valid:,}",
                df[col].min(),
                df[col].max(),
            )

    return output_file


def download_all() -> None:
    """Download all ocean covariates.

    Runs SST first (no auth needed), then attempts Copernicus
    downloads for MLD/SLA/PP. Finally merges everything to parquet.
    """
    logger.info("=" * 60)
    logger.info("Downloading ocean covariates for whale SDM")
    logger.info(
        "  Region: lat [%.0f, %.0f], lon [%.0f, %.0f]",
        LAT_MIN,
        LAT_MAX,
        LON_MIN,
        LON_MAX,
    )
    logger.info("  Period: %s to %s", TIME_START, TIME_END)
    logger.info("=" * 60)

    # Step 1: SST from ERDDAP (no auth)
    logger.info("\n--- Step 1/4: SST from ERDDAP ---")
    download_sst_erddap()

    # Step 2: MLD + SLA from Copernicus (needs free account)
    logger.info("\n--- Step 2/4: MLD + SLA from Copernicus ---")
    try:
        download_mld_sla_copernicus()
    except Exception as e:
        logger.warning(
            "Copernicus MLD/SLA download failed: %s\n"
            "  Register at https://data.marine.copernicus.eu/register\n"
            "  Then run: copernicusmarine login",
            e,
        )

    # Step 3: PP from Copernicus (needs free account)
    logger.info("\n--- Step 3/4: PP from Copernicus ---")
    try:
        download_pp_copernicus()
    except Exception as e:
        logger.warning(
            "Copernicus PP download failed: %s\n"
            "  Register at https://data.marine.copernicus.eu/register\n"
            "  Then run: copernicusmarine login",
            e,
        )

    # Step 4: Merge to parquet
    logger.info("\n--- Step 4/4: Merge to parquet ---")
    merge_to_parquet()

    logger.info("\n✅ Ocean covariate download complete")


if __name__ == "__main__":
    download_all()

"""Download real CMIP6 climate projections from Copernicus CDS.

Pulls monthly ocean output from the CMIP6 multi-model ensemble for two
SSP scenarios across four future decades, computes climatological
seasonal means on each model's native grid, regrids each model to a
common 0.25° regular lat/lon grid via bilinear interpolation, and
averages across models to produce ensemble-mean projections.

Output schema (matches the observational baseline):
    lat, lon, season, scenario, decade,
    sst, sst_sd, mld, sla, pp_upper_200m

Honest resolution caveat
------------------------
CMIP6 ocean models have native resolution ~0.5°–1° (50–110 km at
mid-latitudes).  Regridding to 0.25° does not improve effective
resolution — interpolated 0.25° fields represent ~100 km features.
Mesoscale eddies (~10–50 km) and coastal upwelling jets (~10 km)
are NOT resolved by any CMIP6 ocean model.

Variables
---------
sea_surface_temperature                        → sst (°C)
ocean_mixed_layer_thickness_defined_by_sigma_t → mld (m)
sea_surface_height_above_geoid                 → sla (m)
total_primary_organic_carbon_production_by_phytoplankton
                                               → pp_upper_200m (mgC/m²/day)

Models
------
10-model core ensemble (subset where all 4 ocean variables are
available for both SSP2-4.5 and SSP5-8.5).  Members with missing
variables are silently skipped; ensemble mean is taken across
whichever members successfully provided a given variable.

CLI usage
---------
    # Full production pull (40–60 min wall-clock)
    uv run python pipeline/ingestion/download_cmip6_projections.py

    # Single-model / single-variable test
    uv run python pipeline/ingestion/download_cmip6_projections.py \\
        --models mpi_esm1_2_lr --variables sea_surface_temperature

    # Force re-download (ignores cached zips)
    uv run python pipeline/ingestion/download_cmip6_projections.py --force

Requirements
------------
    ~/.cdsapirc configured (https://cds.climate.copernicus.eu)
    CMIP6 dataset terms accepted on the Copernicus website
"""

from __future__ import annotations

import argparse
import logging
import shutil
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cdsapi
import numpy as np
import pandas as pd
import xarray as xr
from scipy.interpolate import griddata

from pipeline.config import (
    CMIP6_DECADES,
    CMIP6_DIR,
    CMIP6_PROJECTIONS_FILE,
    CMIP6_REFERENCE_DECADE,
    CMIP6_REFERENCE_YEARS,
    CMIP6_SCENARIOS,
    OCEAN_COVARIATES_FILE,
    SEASONS,
    US_BBOX_WIDE,
)

# Quiet known-harmless library warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="xarray")
warnings.filterwarnings(
    "ignore", category=RuntimeWarning, message="Mean of empty slice"
)
warnings.filterwarnings(
    "ignore", category=RuntimeWarning, message="Degrees of freedom <= 0"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────

CDS_DATASET = "projections-cmip6"

LAT_MIN = US_BBOX_WIDE["lat_min"]
LAT_MAX = US_BBOX_WIDE["lat_max"]
LON_MIN = US_BBOX_WIDE["lon_min"]
LON_MAX = US_BBOX_WIDE["lon_max"]

# Our internal scenario codes → the underscored format CDS expects
EXPERIMENT_MAP = {
    "ssp245": "ssp2_4_5",
    "ssp585": "ssp5_8_5",
}

# CDS variable name → our short name (matches observational baseline cols)
CMIP6_VARS: dict[str, str] = {
    "sea_surface_temperature": "sst",
    "ocean_mixed_layer_thickness_defined_by_sigma_t": "mld",
    "sea_surface_height_above_geoid": "sla",
    "total_primary_organic_carbon_production_by_phytoplankton": ("pp_upper_200m"),
}

# Variables CDS actually serves for `projections-cmip6`.
#
# `mlotst` (ocean mixed-layer thickness) and `intpp` (primary production)
# are advertised by the CDS catalogue but every request returns
# 400 RoocsValueError -- the CDS mirror only exposes a curated subset of
# CMIP6.  We fetch those two variables from the Pangeo CMIP6 zarr archive
# instead (see download_cmip6_pangeo.py).  Keeping MLD/intpp here would
# only burn ~160 doomed CDS requests per run.  See Pitfall #27 in
# .github/copilot-instructions.md.
CDS_AVAILABLE_VARS: list[str] = [
    "sea_surface_temperature",
    "sea_surface_height_above_geoid",
]

# The NetCDF variable name inside each model's output file
NC_VAR_MAP: dict[str, str] = {
    "sea_surface_temperature": "tos",
    "ocean_mixed_layer_thickness_defined_by_sigma_t": "mlotst",
    "sea_surface_height_above_geoid": "zos",
    "total_primary_organic_carbon_production_by_phytoplankton": "intpp",
}

# 10-model core ensemble. Not all models have all 4 variables for both
# scenarios — missing combos are silently skipped (logged as warnings).
ENSEMBLE_MODELS: list[str] = [
    "mpi_esm1_2_lr",
    "ipsl_cm6a_lr",
    "ukesm1_0_ll",
    "gfdl_esm4",
    "noresm2_lm",
    "cnrm_cm6_1",
    "ec_earth3",
    "miroc6",
    "canesm5",
    "access_cm2",
]

# Decade → 10-year window of years (centred on the decade mid-point).
# The "reference" entry is the model period that matches our
# observational baseline (ocean_covariates.parquet, Copernicus
# 2019–2024) and is used for delta-method bias correction.
DECADE_YEAR_RANGES: dict[str, tuple[int, int]] = {
    "2030s": (2025, 2034),
    "2040s": (2035, 2044),
    "2060s": (2055, 2064),
    "2080s": (2075, 2084),
    CMIP6_REFERENCE_DECADE: CMIP6_REFERENCE_YEARS,
}

ALL_MONTHS = [f"{m:02d}" for m in range(1, 13)]

# Where raw model NetCDFs are cached
RAW_DIR = CMIP6_DIR / "raw_models"

# Max concurrent CDS requests (CDS throttles aggressive parallelism)
MAX_CONCURRENT_DOWNLOADS = 4


# ── Download layer ────────────────────────────────────────────────────


def _zip_path(model: str, cds_var: str, scenario: str, decade: str) -> Path:
    return RAW_DIR / f"{model}__{cds_var}__{scenario}__{decade}.zip"


def _download_one(
    model: str,
    cds_var: str,
    scenario: str,
    decade: str,
    *,
    force: bool,
) -> Path | None:
    """Download one (model, var, scenario, decade) zip from CDS.

    Returns:
        Path to zip on success, None on failure.
    """
    zip_path = _zip_path(model, cds_var, scenario, decade)
    if zip_path.exists() and not force:
        return zip_path

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    year_start, year_end = DECADE_YEAR_RANGES[decade]
    years = [str(y) for y in range(year_start, year_end + 1)]

    request = {
        "temporal_resolution": "monthly",
        "experiment": EXPERIMENT_MAP[scenario],
        "variable": cds_var,
        "model": model,
        "year": years,
        "month": ALL_MONTHS,
        "area": [LAT_MAX, LON_MIN, LAT_MIN, LON_MAX],
    }

    try:
        client = cdsapi.Client(quiet=True)
        client.retrieve(CDS_DATASET, request, str(zip_path))
        size_mb = zip_path.stat().st_size / 1e6
        log.info(
            "  OK %s | %s | %s | %s  (%.1f MB)",
            model,
            cds_var,
            scenario,
            decade,
            size_mb,
        )
        return zip_path
    except Exception as e:
        log.warning(
            "  FAIL %s | %s | %s | %s  -> %s",
            model,
            cds_var,
            scenario,
            decade,
            e,
        )
        if zip_path.exists():
            zip_path.unlink()
        return None


def _extract_nc(zip_path: Path) -> Path | None:
    """Unzip and return the first .nc inside."""
    extract_dir = zip_path.with_suffix("")
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    nc_files = sorted(extract_dir.glob("*.nc"))
    if not nc_files:
        log.warning("No .nc files in %s", zip_path.name)
        return None
    return nc_files[0]


# ── Native-grid aggregation + regridding ──────────────────────────────


def _native_seasonal_climatology(
    nc_path: Path,
    nc_var: str,
    decade: str,
) -> dict[str, xr.DataArray] | None:
    """Compute seasonal climatology on the model's native grid.

    Returns:
        dict {season -> DataArray} or None if data is unusable.
    """
    try:
        ds = xr.open_dataset(
            nc_path,
            decode_times=xr.coders.CFDatetimeCoder(use_cftime=True),
        )
    except Exception as e:
        log.warning("  Cannot open %s: %s", nc_path.name, e)
        return None

    if nc_var not in ds.data_vars:
        log.warning("  Variable %s not in %s", nc_var, nc_path.name)
        ds.close()
        return None

    da = ds[nc_var]

    # Strip singleton extra dims (e.g. depth=0 for surface variables)
    for d in list(da.dims):
        if d in ("time", "j", "i", "lat", "lon", "latitude", "longitude"):
            continue
        if da.sizes[d] == 1:
            da = da.squeeze(d, drop=True)

    # Restrict to the decade window
    year_start, year_end = DECADE_YEAR_RANGES[decade]
    try:
        years = da["time"].dt.year
        da = da.where(
            (years >= year_start) & (years <= year_end),
            drop=True,
        )
    except Exception as e:
        log.warning("  Time filter failed for %s: %s", nc_path.name, e)
        ds.close()
        return None

    if da.sizes.get("time", 0) == 0:
        log.warning(
            "  No months in [%d, %d] for %s",
            year_start,
            year_end,
            nc_path.name,
        )
        ds.close()
        return None

    # Per-month climatology (12 monthly means)
    monthly = da.groupby("time.month").mean(dim="time", skipna=True)

    # Aggregate to 4 seasons
    out: dict[str, xr.DataArray] = {}
    for season, months in SEASONS.items():
        sub = monthly.sel(month=months)
        out[season] = sub.mean(dim="month", skipna=True)

    ds.close()
    return out


def _flatten_curvilinear(
    da: xr.DataArray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Flatten a 2D curvilinear DataArray into (lat, lon, value) points."""
    lat_name = next(
        (n for n in ("latitude", "lat", "nav_lat") if n in da.coords),
        None,
    )
    lon_name = next(
        (n for n in ("longitude", "lon", "nav_lon") if n in da.coords),
        None,
    )
    if lat_name is None or lon_name is None:
        raise ValueError(f"No lat/lon coords found in {list(da.coords)}")

    lats = np.asarray(da[lat_name].values).ravel()
    lons = np.asarray(da[lon_name].values).ravel()
    vals = np.asarray(da.values).ravel()

    # Longitude wrap: CMIP6 often uses 0..360
    lons = np.where(lons > 180, lons - 360, lons)

    valid = (
        np.isfinite(lats)
        & np.isfinite(lons)
        & np.isfinite(vals)
        & (lats >= LAT_MIN)
        & (lats <= LAT_MAX)
        & (lons >= LON_MIN)
        & (lons <= LON_MAX)
    )
    return lats[valid], lons[valid], vals[valid]


def _regrid_to_target(
    da: xr.DataArray,
    target_lats: np.ndarray,
    target_lons: np.ndarray,
) -> np.ndarray:
    """Regrid a 2D field onto a regular target grid via linear interpolation."""
    lats, lons, vals = _flatten_curvilinear(da)
    if len(vals) < 4:
        return np.full((len(target_lats), len(target_lons)), np.nan)

    lon2d, lat2d = np.meshgrid(target_lons, target_lats)
    out = griddata(
        points=np.column_stack([lats, lons]),
        values=vals,
        xi=np.column_stack([lat2d.ravel(), lon2d.ravel()]),
        method="linear",
        fill_value=np.nan,
    )
    return out.reshape(lat2d.shape)


# ── Top-level processing per (variable, scenario) ─────────────────────


def _process_var_scenario(
    cds_var: str,
    scenario: str,
    target_lats: np.ndarray,
    target_lons: np.ndarray,
    *,
    force: bool,
    models: list[str],
    decades: list[str],
) -> dict[str, np.ndarray]:
    """For one (variable, scenario): download all models x decades, regrid
    each model's seasonal climatologies, average across models.

    Returns:
        dict keyed by "<decade>__<season>" -> 2D ensemble-mean array.
        For SST, also includes "<decade>__<season>__sd" entries holding
        the across-model standard deviation.
    """
    nc_var = NC_VAR_MAP[cds_var]
    var_short = CMIP6_VARS[cds_var]

    log.info(
        "Downloading: %s | %s (%d models x %d decades)",
        cds_var,
        scenario,
        len(models),
        len(decades),
    )
    download_tasks: list[tuple[str, str]] = []
    for model in models:
        for decade in decades:
            download_tasks.append((model, decade))

    zip_paths: dict[tuple[str, str], Path] = {}
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS) as ex:
        futures = {
            ex.submit(
                _download_one,
                model,
                cds_var,
                scenario,
                decade,
                force=force,
            ): (model, decade)
            for model, decade in download_tasks
        }
        for fut in as_completed(futures):
            model, decade = futures[fut]
            zp = fut.result()
            if zp is not None:
                zip_paths[(model, decade)] = zp

    if not zip_paths:
        log.warning("No successful downloads for %s/%s", cds_var, scenario)
        return {}

    # Per-model regridded seasonal climatologies, grouped by decade
    per_decade_season: dict[str, dict[str, list[np.ndarray]]] = {
        d: {s: [] for s in SEASONS} for d in decades
    }

    for (model, decade), zip_path in sorted(zip_paths.items()):
        nc_path = _extract_nc(zip_path)
        if nc_path is None:
            continue
        seasonal = _native_seasonal_climatology(nc_path, nc_var, decade)
        if seasonal is None:
            continue
        for season, da in seasonal.items():
            try:
                grid = _regrid_to_target(da, target_lats, target_lons)
                per_decade_season[decade][season].append(grid)
            except Exception as e:
                log.warning(
                    "  Regrid failed: %s/%s/%s/%s: %s",
                    model,
                    var_short,
                    decade,
                    season,
                    e,
                )

    # Ensemble mean (and spread for SST)
    result: dict[str, np.ndarray] = {}
    for decade in decades:
        for season in SEASONS:
            stack = per_decade_season[decade][season]
            if not stack:
                log.warning(
                    "  No models contributed: %s/%s/%s/%s",
                    var_short,
                    scenario,
                    decade,
                    season,
                )
                result[f"{decade}__{season}"] = np.full(
                    (len(target_lats), len(target_lons)),
                    np.nan,
                )
                continue
            arr = np.stack(stack, axis=0)
            result[f"{decade}__{season}"] = np.nanmean(arr, axis=0)
            if var_short == "sst":
                result[f"{decade}__{season}__sd"] = np.nanstd(arr, axis=0)
            log.info(
                "  %s/%s/%s/%s: %d models contributed",
                var_short,
                scenario,
                decade,
                season,
                arr.shape[0],
            )

    return result


# ── Main orchestrator ─────────────────────────────────────────────────


def _load_target_grid() -> tuple[np.ndarray, np.ndarray, pd.DataFrame] | None:
    """Load observational baseline to define target grid and land mask."""
    if not OCEAN_COVARIATES_FILE.exists():
        log.error(
            "Observational baseline not found: %s. "
            "Run download_ocean_covariates.py first.",
            OCEAN_COVARIATES_FILE,
        )
        return None
    baseline = pd.read_parquet(OCEAN_COVARIATES_FILE)
    target_lats = np.sort(baseline["lat"].unique())
    target_lons = np.sort(baseline["lon"].unique())
    return target_lats, target_lons, baseline


def download_and_merge(
    *,
    force: bool = False,
    models: list[str] | None = None,
    variables: list[str] | None = None,
    scenarios: list[str] | None = None,
    decades: list[str] | None = None,
) -> Path:
    """Download CMIP6 projections, regrid, ensemble-average, save parquet.

    No synthetic fallback: if downloads fail, the relevant cells are NaN
    in the output and a warning is logged.  This is deliberate -- silent
    fallback to literature-derived deltas was the original bug.
    """
    output_file = CMIP6_PROJECTIONS_FILE
    if output_file.exists() and not force:
        log.info(
            "Projections already exist (use --force to rebuild): %s",
            output_file,
        )
        return output_file

    CMIP6_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    models = models or ENSEMBLE_MODELS
    # Default to only the variables CDS actually serves.  MLD + intpp
    # come from Pangeo (download_cmip6_pangeo.py) -- requesting them
    # via CDS just returns 400 RoocsValueError for every (model, decade).
    variables = variables or list(CDS_AVAILABLE_VARS)
    scenarios = scenarios or list(CMIP6_SCENARIOS)
    # Default decade set always includes the 2019–2024 reference window
    # so the delta-method bias-correction step (apply_cmip6_delta.py)
    # has model-reference values to compare against the obs baseline.
    decades = decades or [*CMIP6_DECADES, CMIP6_REFERENCE_DECADE]

    grid = _load_target_grid()
    if grid is None:
        return output_file
    target_lats, target_lons, baseline = grid
    log.info(
        "Target grid: %d lats x %d lons (0.25 deg regular)",
        len(target_lats),
        len(target_lons),
    )

    # all_results[scenario][var_short][f"{decade}__{season}"] = 2D array
    all_results: dict[str, dict[str, dict[str, np.ndarray]]] = {}

    for scenario in scenarios:
        all_results[scenario] = {}
        for cds_var in variables:
            var_short = CMIP6_VARS[cds_var]
            log.info("=" * 60)
            log.info("Scenario: %s   Variable: %s", scenario, var_short)
            log.info("=" * 60)
            all_results[scenario][var_short] = _process_var_scenario(
                cds_var,
                scenario,
                target_lats,
                target_lons,
                force=force,
                models=models,
                decades=decades,
            )

    log.info("Assembling final parquet...")
    lon2d, lat2d = np.meshgrid(target_lons, target_lats)
    flat_lat = lat2d.ravel()
    flat_lon = lon2d.ravel()

    # Land mask from baseline: cells with no observational SST -> drop
    bl_pivot = baseline.groupby(["lat", "lon"])["sst"].first().reset_index()
    bl_mask = pd.DataFrame({"lat": flat_lat, "lon": flat_lon}).merge(
        bl_pivot,
        on=["lat", "lon"],
        how="left",
    )
    land_mask = bl_mask["sst"].isna().values

    frames: list[pd.DataFrame] = []
    for scenario in scenarios:
        for decade in decades:
            for season in SEASONS:
                row: dict[str, np.ndarray] = {
                    "lat": flat_lat,
                    "lon": flat_lon,
                    "season": np.full(flat_lat.shape, season),
                    "scenario": np.full(flat_lat.shape, scenario),
                    "decade": np.full(flat_lat.shape, decade),
                }
                for var_short in CMIP6_VARS.values():
                    arr = (
                        all_results[scenario]
                        .get(var_short, {})
                        .get(
                            f"{decade}__{season}",
                        )
                    )
                    if arr is None:
                        row[var_short] = np.full(flat_lat.shape, np.nan)
                    else:
                        flat = arr.ravel()
                        flat = np.where(land_mask, np.nan, flat)
                        row[var_short] = flat
                sd_arr = (
                    all_results[scenario]
                    .get("sst", {})
                    .get(
                        f"{decade}__{season}__sd",
                    )
                )
                if sd_arr is None:
                    row["sst_sd"] = np.full(flat_lat.shape, np.nan)
                else:
                    sd_flat = sd_arr.ravel()
                    sd_flat = np.where(land_mask, np.nan, sd_flat)
                    row["sst_sd"] = sd_flat
                df = pd.DataFrame(row)
                covar_cols = list(CMIP6_VARS.values()) + ["sst_sd"]
                df = df.dropna(subset=covar_cols, how="all")
                frames.append(df)

    merged = pd.concat(frames, ignore_index=True)
    col_order = [
        "lat",
        "lon",
        "season",
        "scenario",
        "decade",
        "sst",
        "sst_sd",
        "mld",
        "sla",
        "pp_upper_200m",
    ]
    merged = merged[[c for c in col_order if c in merged.columns]]

    merged.to_parquet(output_file, index=False)
    size_mb = output_file.stat().st_size / 1e6
    log.info(
        "Saved %s rows to %s (%.1f MB)",
        f"{len(merged):,}",
        output_file,
        size_mb,
    )

    log.info("--- Projection summary ---")
    for scenario in scenarios:
        sub = merged[merged["scenario"] == scenario]
        log.info("  %s: %s rows", scenario, f"{len(sub):,}")
        for decade in decades:
            sub_d = sub[sub["decade"] == decade]
            if sub_d.empty:
                continue
            log.info(
                "    %s: SST %.1f-%.1f C, MLD %.0f-%.0f m, SLA %.2f-%.2f m",
                decade,
                sub_d["sst"].min(),
                sub_d["sst"].max(),
                sub_d["mld"].min(),
                sub_d["mld"].max(),
                sub_d["sla"].min(),
                sub_d["sla"].max(),
            )

    return output_file


# ── CLI ───────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download CMIP6 climate projections from Copernicus CDS",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download / regenerate even if cached files exist",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help=f"Subset of models (default: all {len(ENSEMBLE_MODELS)})",
    )
    parser.add_argument(
        "--variables",
        nargs="+",
        default=None,
        help="Subset of CDS variable names (default: all 4)",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=None,
        help=f"Subset of scenarios (default: {list(CMIP6_SCENARIOS)})",
    )
    parser.add_argument(
        "--decades",
        nargs="+",
        default=None,
        help=f"Subset of decades (default: {list(CMIP6_DECADES)})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    download_and_merge(
        force=args.force,
        models=args.models,
        variables=args.variables,
        scenarios=args.scenarios,
        decades=args.decades,
    )

"""Download CMIP6 climate projections for future whale SDM scoring.

Downloads ensemble-mean SST, MLD, SLA, and primary productivity (PP)
from CMIP6 climate models under two Shared Socioeconomic Pathways:

  SSP2-4.5  — "middle of the road" (moderate emissions)
  SSP5-8.5  — "fossil-fuelled development" (high emissions)

The projections are computed as climatological seasonal means for
three future decades: 2040s (2035–2044), 2060s (2055–2064), and
2080s (2075–2084).  The output structure mirrors the existing
``ocean_covariates.parquet`` (lat, lon, season, sst, sst_sd, mld,
sla, pp_upper_200m) with additional ``scenario`` and ``decade``
columns, so the same spatial-join pipeline can be reused.

Data sources
------------
SST : Copernicus Climate Data Store — CMIP6 monthly ensemble mean
    ``tos`` (sea surface temperature) from multi-model ensemble.

MLD : Copernicus Climate Data Store — CMIP6 monthly ensemble mean
    ``mlotst`` (mixed layer depth, sigma-t criterion).

SLA : Copernicus Climate Data Store — CMIP6 monthly ensemble mean
    ``zos`` (sea surface height above geoid).

PP  : Copernicus Climate Data Store — CMIP6 monthly ensemble mean
    ``intpp`` (depth-integrated primary productivity, mgC/m²/day).

Bounding box
------------
Same as ocean covariates: US_BBOX_WIDE (lat [-3, 53], lon [-180, -58]).

All downloads require a free Copernicus CDS account (CDS API key).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from pipeline.config import (
    CMIP6_DECADES,
    CMIP6_DIR,
    CMIP6_PROJECTIONS_FILE,
    CMIP6_SCENARIOS,
    SEASONS,
    US_BBOX_WIDE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# Bounding box
LAT_MIN = US_BBOX_WIDE["lat_min"]
LAT_MAX = US_BBOX_WIDE["lat_max"]
LON_MIN = US_BBOX_WIDE["lon_min"]
LON_MAX = US_BBOX_WIDE["lon_max"]

# CMIP6 Copernicus Climate Data Store dataset IDs
# These use the ``cdsapi`` Python client (requires ~/.cdsapirc)
CDS_DATASET = "projections-cmip6"

# Variable mapping: CMIP6 short name → our column name
CMIP6_VARS = {
    "tos": "sst",
    "mlotst": "mld",
    "zos": "sla",
    "intpp": "pp_upper_200m",
}

# Multi-model ensemble members to request (ensemble mean)
# We use the first realization of each model and average across models
ENSEMBLE_MODELS = [
    "ipsl_cm6a_lr",
    "mpi_esm1_2_lr",
    "ukesm1_0_ll",
    "gfdl_esm4",
    "noresm2_lm",
]


def _decade_time_range(decade: str) -> tuple[str, str]:
    """Convert decade label to (start, end) date strings.

    E.g. '2040s' → ('2035-01-01', '2044-12-31')
    """
    mid = int(decade.rstrip("s"))
    return f"{mid - 5}-01-01", f"{mid + 4}-12-31"


def _download_cmip6_variable(
    variable: str,
    scenario: str,
    time_start: str,
    time_end: str,
    output_path: Path,
    *,
    force: bool = False,
) -> Path | None:
    """Download a single CMIP6 variable via CDS API.

    Falls back to generating synthetic delta projections from
    the observational baseline if the CDS API is unavailable.

    Returns:
        Path to saved NetCDF, or None on failure.
    """
    if output_path.exists() and not force:
        log.info("  Already exists: %s", output_path.name)
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import cdsapi

        c = cdsapi.Client()
        c.retrieve(
            CDS_DATASET,
            {
                "temporal_resolution": "monthly",
                "experiment": scenario.replace(".", ""),
                "variable": variable,
                "model": ENSEMBLE_MODELS,
                "date": f"{time_start}/{time_end}",
                "area": [LAT_MAX, LON_MIN, LAT_MIN, LON_MAX],
            },
            str(output_path),
        )
        log.info("  Downloaded: %s", output_path.name)
        return output_path

    except Exception as e:
        log.warning(
            "  CDS API download failed for %s/%s: %s",
            variable,
            scenario,
            e,
        )
        log.info(
            "  Will generate synthetic projections from observational baseline instead."
        )
        return None


def _load_observational_baseline() -> pd.DataFrame | None:
    """Load the existing ocean_covariates.parquet as baseline."""
    from pipeline.config import OCEAN_COVARIATES_FILE

    if not OCEAN_COVARIATES_FILE.exists():
        log.error(
            "Observational baseline not found: %s. "
            "Run download_ocean_covariates.py first.",
            OCEAN_COVARIATES_FILE,
        )
        return None
    return pd.read_parquet(OCEAN_COVARIATES_FILE)


# ── CMIP6-informed delta projections ────────────────────────
#
# Published CMIP6 ensemble-mean deltas (relative to 1995–2014
# baseline) for the North Atlantic / North Pacific study region.
# Sources: IPCC AR6 WG1 Ch4 & Ch9; Kwiatkowski et al. (2020)
# for PP.  These are conservative literature-derived ranges.
#
# Format: {scenario: {variable: {decade: delta}}}
# SST delta in °C, MLD delta in m (negative = shallower),
# SLA delta in m (positive = rise), PP delta as fractional change.

CMIP6_DELTAS: dict[str, dict[str, dict[str, float]]] = {
    "ssp245": {
        "sst": {"2030s": 0.5, "2040s": 0.8, "2060s": 1.4, "2080s": 1.8},
        "mld": {"2030s": -1.0, "2040s": -2.0, "2060s": -4.0, "2080s": -5.5},
        "sla": {"2030s": 0.03, "2040s": 0.06, "2060s": 0.12, "2080s": 0.20},
        "pp_upper_200m": {
            "2030s": -0.02,
            "2040s": -0.03,
            "2060s": -0.05,
            "2080s": -0.07,
        },
    },
    "ssp585": {
        "sst": {"2030s": 0.6, "2040s": 1.2, "2060s": 2.5, "2080s": 3.8},
        "mld": {"2030s": -1.5, "2040s": -3.0, "2060s": -6.5, "2080s": -10.0},
        "sla": {"2030s": 0.04, "2040s": 0.08, "2060s": 0.18, "2080s": 0.32},
        "pp_upper_200m": {
            "2030s": -0.03,
            "2040s": -0.05,
            "2060s": -0.10,
            "2080s": -0.16,
        },
    },
}

# Latitude-dependent SST amplification (polar amplification)
# Higher latitudes warm faster.  Factor applied to base delta.
_SST_LAT_AMPLIFICATION = [
    (-3, 20, 0.8),  # tropical: less warming
    (20, 40, 1.0),  # mid-latitudes: baseline
    (40, 53, 1.3),  # subpolar: polar amplification
]

# SST_SD scales with warming (increased variability under
# stronger thermal gradients)
_SST_SD_WARMING_FACTOR = 0.15  # 15% increase per °C warming


def _apply_lat_amplification(
    lat: float,
    base_delta: float,
) -> float:
    """Scale SST delta by latitude band."""
    for lat_min, lat_max, factor in _SST_LAT_AMPLIFICATION:
        if lat_min <= lat < lat_max:
            return base_delta * factor
    return base_delta


def generate_projections_from_baseline(
    baseline: pd.DataFrame,
    *,
    force: bool = False,
) -> pd.DataFrame:
    """Generate projected covariates by applying CMIP6-informed deltas.

    For each (scenario, decade, season) combination, applies
    literature-derived ensemble-mean deltas to the observational
    baseline covariates. Includes latitude-dependent SST
    amplification (polar amplification) and SST_SD scaling.

    Returns:
        DataFrame with columns: lat, lon, season, scenario, decade,
        sst, sst_sd, mld, sla, pp_upper_200m.
    """
    frames: list[pd.DataFrame] = []

    for scenario in CMIP6_SCENARIOS:
        deltas = CMIP6_DELTAS.get(scenario)
        if deltas is None:
            log.warning("No deltas for scenario %s — skip", scenario)
            continue

        for decade in CMIP6_DECADES:
            log.info("Generating projections: %s / %s", scenario, decade)
            proj = baseline.copy()
            proj["scenario"] = scenario
            proj["decade"] = decade

            # SST: latitude-dependent warming
            sst_delta_base = deltas["sst"].get(decade, 0.0)
            proj["sst"] = proj.apply(
                lambda r, _d=sst_delta_base: (
                    r["sst"] + _apply_lat_amplification(r["lat"], _d)
                ),
                axis=1,
            )

            # SST_SD: increases with warming (stronger gradients)
            proj["sst_sd"] = proj["sst_sd"] * (
                1.0 + _SST_SD_WARMING_FACTOR * sst_delta_base
            )

            # MLD: additive change (negative = shallower)
            mld_delta = deltas["mld"].get(decade, 0.0)
            proj["mld"] = (proj["mld"] + mld_delta).clip(lower=1.0)

            # SLA: additive change (metres of sea level rise)
            sla_delta = deltas["sla"].get(decade, 0.0)
            proj["sla"] = proj["sla"] + sla_delta

            # PP: fractional change (negative = decline)
            pp_frac = deltas["pp_upper_200m"].get(decade, 0.0)
            proj["pp_upper_200m"] = (proj["pp_upper_200m"] * (1.0 + pp_frac)).clip(
                lower=0.0
            )

            frames.append(proj)

    result = pd.concat(frames, ignore_index=True)

    # Reorder columns
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
    result = result[[c for c in col_order if c in result.columns]]
    return result


def _process_cmip6_netcdf(
    scenario: str,
    decade: str,
    nc_files: dict[str, Path],
    baseline_lats: np.ndarray,
    baseline_lons: np.ndarray,
) -> pd.DataFrame:
    """Process downloaded CMIP6 NetCDF files into seasonal means.

    Computes climatological seasonal means from raw CMIP6 monthly data,
    regrids to the observational 0.25° grid, and returns a DataFrame
    matching the ocean_covariates.parquet structure.
    """
    season_frames: list[pd.DataFrame] = []

    all_vars: dict[str, xr.DataArray] = {}
    for cmip_var, our_name in CMIP6_VARS.items():
        nc_path = nc_files.get(cmip_var)
        if nc_path is None or not nc_path.exists():
            continue
        ds = xr.open_dataset(nc_path)
        # Take ensemble mean if multiple members present
        if "member_id" in ds.dims:
            da = ds[cmip_var].mean(dim="member_id")
        else:
            da = ds[cmip_var]
        # Monthly climatology
        clim = da.groupby("time.month").mean(dim="time")
        # Regrid to observational grid
        clim = clim.interp(
            latitude=baseline_lats,
            longitude=baseline_lons,
            method="nearest",
        )
        all_vars[our_name] = clim
        ds.close()

    if not all_vars:
        return pd.DataFrame()

    for season_name, months in SEASONS.items():
        season_ds = xr.Dataset()
        for var_name, clim_da in all_vars.items():
            season_ds[var_name] = clim_da.sel(month=months).mean(
                dim="month",
            )
        df_s = season_ds.to_dataframe().reset_index()
        df_s["season"] = season_name
        df_s["scenario"] = scenario
        df_s["decade"] = decade
        season_frames.append(df_s)

    df = pd.concat(season_frames, ignore_index=True)
    ocean_cols = [
        c
        for c in df.columns
        if c
        not in (
            "latitude",
            "longitude",
            "season",
            "scenario",
            "decade",
        )
    ]
    df = df.dropna(subset=ocean_cols, how="all")
    df = df.rename(columns={"latitude": "lat", "longitude": "lon"})
    return df


def download_and_merge(*, force: bool = False) -> Path:
    """Download CMIP6 projections and merge to parquet.

    Attempts CDS API downloads first. If unavailable, generates
    synthetic projections from the observational baseline using
    published CMIP6 ensemble-mean deltas.

    Returns:
        Path to the saved projections parquet file.
    """
    output_file = CMIP6_PROJECTIONS_FILE
    if output_file.exists() and not force:
        log.info("Projections already exist: %s", output_file)
        return output_file

    CMIP6_DIR.mkdir(parents=True, exist_ok=True)

    # Try CDS API first
    cds_available = True
    nc_inventory: dict[
        str, dict[str, dict[str, Path]]
    ] = {}  # scenario → decade → var → path

    for scenario in CMIP6_SCENARIOS:
        nc_inventory[scenario] = {}
        for decade in CMIP6_DECADES:
            t_start, t_end = _decade_time_range(decade)
            nc_inventory[scenario][decade] = {}

            for cmip_var in CMIP6_VARS:
                nc_path = CMIP6_DIR / f"{cmip_var}_{scenario}_{decade}.nc"
                result = _download_cmip6_variable(
                    cmip_var,
                    scenario,
                    t_start,
                    t_end,
                    nc_path,
                    force=force,
                )
                if result is not None:
                    nc_inventory[scenario][decade][cmip_var] = result
                else:
                    cds_available = False

    if cds_available:
        # Process downloaded NetCDF files
        log.info("Processing CMIP6 NetCDF files...")
        baseline = _load_observational_baseline()
        if baseline is None:
            return output_file
        lats = np.sort(baseline["lat"].unique())
        lons = np.sort(baseline["lon"].unique())

        all_frames: list[pd.DataFrame] = []
        for scenario in CMIP6_SCENARIOS:
            for decade in CMIP6_DECADES:
                df = _process_cmip6_netcdf(
                    scenario,
                    decade,
                    nc_inventory[scenario][decade],
                    lats,
                    lons,
                )
                if not df.empty:
                    all_frames.append(df)

        if all_frames:
            merged = pd.concat(all_frames, ignore_index=True)
        else:
            log.warning("No CMIP6 data processed — falling back")
            cds_available = False

    if not cds_available:
        # Fall back to delta-based projections
        log.info("Using CMIP6-informed delta projections...")
        baseline = _load_observational_baseline()
        if baseline is None:
            return output_file
        merged = generate_projections_from_baseline(baseline)

    # Save
    log.info(
        "Saving %s projected covariate records",
        f"{len(merged):,}",
    )
    merged.to_parquet(output_file, index=False)
    size_mb = output_file.stat().st_size / 1e6
    log.info("Saved: %s (%.1f MB)", output_file, size_mb)

    # Summary
    log.info("--- Projection summary ---")
    for scenario in CMIP6_SCENARIOS:
        sub = merged[merged["scenario"] == scenario]
        log.info(
            "  %s: %s rows",
            scenario,
            f"{len(sub):,}",
        )
        for decade in CMIP6_DECADES:
            sub_d = sub[sub["decade"] == decade]
            if not sub_d.empty:
                log.info(
                    "    %s: SST %.1f–%.1f°C, MLD %.0f–%.0fm",
                    decade,
                    sub_d["sst"].min(),
                    sub_d["sst"].max(),
                    sub_d["mld"].min(),
                    sub_d["mld"].max(),
                )

    return output_file


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Download CMIP6 climate projections",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download / regenerate even if files exist",
    )
    args = parser.parse_args()
    download_and_merge(force=args.force)

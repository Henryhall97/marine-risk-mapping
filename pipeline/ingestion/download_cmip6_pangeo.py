"""Download CMIP6 mlotst (MLD) + intpp (primary production) from Pangeo.

Copernicus CDS does not expose ocean mixed-layer thickness or primary
production for the ``projections-cmip6`` dataset (confirmed by 400
RoocsValueError on every (model, scenario) probe).  Both variables do
exist in the upstream CMIP6 archive on ESGF and are mirrored as zarr
stores on Google Cloud Storage via Pangeo.  This module fills that gap
so the merged ``cmip6_projections.parquet`` has real climate signal for
all four ocean covariates used by the seasonal SDMs (SST, MLD, SLA, PP).

Approach
--------
1. Query the Pangeo CMIP6 intake-esm catalogue for each
   (source_id, variable_id, experiment_id, table_id=Omon).
2. Open the canonical ensemble member's zarr store lazily via
   ``xr.open_zarr`` (no local cache, GCS-anonymous read).
3. Subset to each decade, compute monthly climatology, aggregate to
   four seasonal means.
4. Regrid each season onto the same 0.25 deg target grid used by the
   CDS-derived projections (re-uses ``_regrid_to_target`` from the
   sibling module so spatial mechanics are identical).
5. Ensemble-mean across models for each (variable, scenario, decade,
   season), drop land cells using the observational SST mask, and
   write to ``cmip6_projections_pangeo.parquet``.
6. ``merge_into_projections()`` rewrites the main ``cmip6_projections``
   parquet in place: keeps CDS-sourced sst / sst_sd / sla and replaces
   the all-NaN mld / pp_upper_200m columns with Pangeo values.

Unit handling
-------------
* ``mlotst`` is already in metres; no conversion.
* ``intpp`` is in mol C m^-2 s^-1 in CMIP6.  We convert to
  mg C m^-2 day^-1 (matches Copernicus observational baseline) via
  ``12.011 g/mol x 1000 mg/g x 86400 s/day``.

Model coverage (probe results, both SSP2-4.5 and SSP5-8.5)
----------------------------------------------------------
mlotst (8 of 10): MPI-ESM1-2-LR, IPSL-CM6A-LR, UKESM1-0-LL, GFDL-ESM4,
                  NorESM2-LM, CNRM-CM6-1, CanESM5, ACCESS-CM2
intpp  (6 of 10): MPI-ESM1-2-LR, IPSL-CM6A-LR, UKESM1-0-LL, GFDL-ESM4,
                  NorESM2-LM, CanESM5
EC-Earth3 and MIROC6 are not in Pangeo for these vars.

CLI usage
---------
    # Fetch + merge into main parquet (default behaviour)
    uv run python pipeline/ingestion/download_cmip6_pangeo.py

    # Fetch only, skip merge
    uv run python pipeline/ingestion/download_cmip6_pangeo.py --no-merge

    # Subset for testing
    uv run python pipeline/ingestion/download_cmip6_pangeo.py \\
        --models mpi_esm1_2_lr --variables mlotst --decades 2030s

    # Recompute even if cached parquet exists
    uv run python pipeline/ingestion/download_cmip6_pangeo.py --force
"""

from __future__ import annotations

import argparse
import logging
import warnings
from pathlib import Path

import intake
import numpy as np
import pandas as pd
import xarray as xr

from pipeline.config import (
    CMIP6_DECADES,
    CMIP6_DIR,
    CMIP6_PROJECTIONS_FILE,
    CMIP6_REFERENCE_DECADE,
    CMIP6_SCENARIOS,
    SEASONS,
)
from pipeline.ingestion.download_cmip6_projections import (
    DECADE_YEAR_RANGES,
    _load_target_grid,
    _regrid_to_target,
)

warnings.filterwarnings("ignore", category=FutureWarning, module="xarray")
warnings.filterwarnings(
    "ignore", category=RuntimeWarning, message="Mean of empty slice"
)
warnings.filterwarnings(
    "ignore", category=RuntimeWarning, message="Degrees of freedom <= 0"
)
warnings.filterwarnings(
    "ignore", category=RuntimeWarning, message="invalid value encountered"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────

PANGEO_CAT_URL = "https://storage.googleapis.com/cmip6/pangeo-cmip6.json"

CMIP6_PANGEO_FILE = CMIP6_DIR / "cmip6_projections_pangeo.parquet"

# Our internal model codes -> Pangeo source_id (CMIP6 CMOR convention).
MODEL_MAP: dict[str, str] = {
    "mpi_esm1_2_lr": "MPI-ESM1-2-LR",
    "ipsl_cm6a_lr": "IPSL-CM6A-LR",
    "ukesm1_0_ll": "UKESM1-0-LL",
    "gfdl_esm4": "GFDL-ESM4",
    "noresm2_lm": "NorESM2-LM",
    "cnrm_cm6_1": "CNRM-CM6-1",
    "canesm5": "CanESM5",
    "access_cm2": "ACCESS-CM2",
    # EC-Earth3 and MIROC6 omitted: no mlotst or intpp in Pangeo.
}

# Pangeo variable_id -> our short column name in cmip6_projections.parquet.
PANGEO_VARS: dict[str, str] = {
    "mlotst": "mld",
    "intpp": "pp_upper_200m",
}

# Most models use r1i1p1f1; UKESM and CNRM use r1i1p1f2 for these
# scenarios.  If neither is available, the lowest-numbered member is used.
MEMBER_PREFS: dict[str, str] = {
    "UKESM1-0-LL": "r1i1p1f2",
    "CNRM-CM6-1": "r1i1p1f2",
}
DEFAULT_MEMBER = "r1i1p1f1"

# Convert intpp from mol C m^-2 s^-1 to mg C m^-2 day^-1.
INTPP_TO_MGC_M2_DAY = 12.011 * 1000.0 * 86400.0

# Catalogue scenario codes are lowercase, no underscore (matches our config).
EXPERIMENT_MAP: dict[str, str] = {
    "ssp245": "ssp245",
    "ssp585": "ssp585",
}


# ── Catalogue + zarr access ───────────────────────────────────────────


def _ensure_2d_coords(da: xr.DataArray) -> xr.DataArray:
    """Expand 1D rectilinear lat/lon coords into 2D so that the
    flatten/regrid logic from ``download_cmip6_projections`` (which
    assumes curvilinear 2D coords) works on Pangeo's ``gr`` grids.
    """
    lat_name = next(
        (n for n in ("latitude", "lat", "nav_lat") if n in da.coords),
        None,
    )
    lon_name = next(
        (n for n in ("longitude", "lon", "nav_lon") if n in da.coords),
        None,
    )
    if lat_name is None or lon_name is None:
        return da
    lat_coord = da[lat_name]
    lon_coord = da[lon_name]
    if lat_coord.ndim == 2 and lon_coord.ndim == 2:
        return da  # already curvilinear

    # Rectilinear case: 1D lat along its own dim, 1D lon along its own.
    lat_dim = lat_coord.dims[0] if lat_coord.dims else lat_name
    lon_dim = lon_coord.dims[0] if lon_coord.dims else lon_name
    lat_vals = np.asarray(lat_coord.values)
    lon_vals = np.asarray(lon_coord.values)
    lon2d, lat2d = np.meshgrid(lon_vals, lat_vals)
    return da.assign_coords(
        {
            lat_name: ((lat_dim, lon_dim), lat2d),
            lon_name: ((lat_dim, lon_dim), lon2d),
        }
    )


def _pick_member(members: list[str], model_pangeo: str) -> str:
    """Pick canonical ensemble member for a model."""
    if not members:
        raise ValueError("empty member list")
    pref = MEMBER_PREFS.get(model_pangeo, DEFAULT_MEMBER)
    if pref in members:
        return pref
    # Fall back to r1i1p1f1 if neither preferred nor default present.
    if DEFAULT_MEMBER in members:
        return DEFAULT_MEMBER
    return sorted(members)[0]


def _open_model_var(
    cat,
    model_pangeo: str,
    var_pangeo: str,
    scenario_pangeo: str,
) -> xr.Dataset | None:
    """Find canonical zarr entry and open it lazily.

    Returns None if no catalogue entry exists or the open fails.
    """
    sub = cat.search(
        source_id=model_pangeo,
        variable_id=var_pangeo,
        experiment_id=scenario_pangeo,
        table_id="Omon",
    )
    if len(sub.df) == 0:
        return None

    member = _pick_member(sorted(sub.df["member_id"].unique().tolist()), model_pangeo)
    rows = sub.df[sub.df["member_id"] == member]
    if rows.empty:
        return None

    # Prefer native grid (gn) over regridded (gr); both interpolate the
    # same after _regrid_to_target.
    grids = sorted(rows["grid_label"].unique().tolist())
    grid_label = "gn" if "gn" in grids else grids[0]
    rows = rows[rows["grid_label"] == grid_label]
    # Latest version
    rows = rows.sort_values("version", ascending=False)
    zstore = rows.iloc[0]["zstore"]

    try:
        ds = xr.open_zarr(
            zstore,
            consolidated=True,
            storage_options={"token": "anon"},
            decode_times=xr.coders.CFDatetimeCoder(use_cftime=True),
        )
    except Exception as e:
        log.warning(
            "  open_zarr failed: %s | %s | %s -> %s",
            model_pangeo,
            var_pangeo,
            scenario_pangeo,
            e,
        )
        return None
    return ds


# ── Per-model processing ──────────────────────────────────────────────


def _process_model_scenario(
    cat,
    model_pangeo: str,
    var_pangeo: str,
    scenario: str,
    target_lats: np.ndarray,
    target_lons: np.ndarray,
    decades: list[str],
) -> dict[str, np.ndarray]:
    """Open one (model, var, scenario) zarr and produce regridded
    seasonal climatologies for each requested decade.

    Returns:
        {f"{decade}__{season}": 2D regridded array}
    """
    scenario_pangeo = EXPERIMENT_MAP[scenario]
    ds = _open_model_var(cat, model_pangeo, var_pangeo, scenario_pangeo)
    if ds is None:
        log.info(
            "  miss: %s | %s | %s",
            model_pangeo,
            var_pangeo,
            scenario_pangeo,
        )
        return {}

    if var_pangeo not in ds.data_vars:
        log.warning(
            "  variable absent: %s in %s/%s",
            var_pangeo,
            model_pangeo,
            scenario_pangeo,
        )
        ds.close()
        return {}

    da = ds[var_pangeo]

    # Drop trivial extra dims (some models include depth=0).
    for d in list(da.dims):
        if d in ("time", "j", "i", "lat", "lon", "latitude", "longitude"):
            continue
        if da.sizes[d] == 1:
            da = da.squeeze(d, drop=True)

    if var_pangeo == "intpp":
        da = da * INTPP_TO_MGC_M2_DAY

    result: dict[str, np.ndarray] = {}
    for decade in decades:
        year_start, year_end = DECADE_YEAR_RANGES[decade]
        try:
            years = da["time"].dt.year
            sub_da = da.where(
                (years >= year_start) & (years <= year_end),
                drop=True,
            )
        except Exception as e:
            log.warning(
                "  time filter failed: %s/%s/%s: %s",
                model_pangeo,
                var_pangeo,
                decade,
                e,
            )
            continue

        if sub_da.sizes.get("time", 0) == 0:
            log.warning(
                "  no months in [%d, %d]: %s/%s",
                year_start,
                year_end,
                model_pangeo,
                var_pangeo,
            )
            continue

        # Monthly climatology, then aggregate to seasons.
        try:
            monthly = sub_da.groupby("time.month").mean(dim="time", skipna=True)
            monthly = monthly.compute()
        except Exception as e:
            log.warning(
                "  monthly clim failed: %s/%s/%s: %s",
                model_pangeo,
                var_pangeo,
                decade,
                e,
            )
            continue

        for season, months in SEASONS.items():
            try:
                seas = monthly.sel(month=months).mean(dim="month", skipna=True)
                seas = _ensure_2d_coords(seas)
                grid = _regrid_to_target(seas, target_lats, target_lons)
                result[f"{decade}__{season}"] = grid
            except Exception as e:
                log.warning(
                    "  regrid failed: %s/%s/%s/%s: %s",
                    model_pangeo,
                    var_pangeo,
                    decade,
                    season,
                    e,
                )

    ds.close()
    return result


# ── Top-level orchestrator ────────────────────────────────────────────


def download_pangeo_vars(
    *,
    force: bool = False,
    models: list[str] | None = None,
    variables: list[str] | None = None,
    scenarios: list[str] | None = None,
    decades: list[str] | None = None,
) -> Path:
    """Fetch MLD + intpp from Pangeo and write a parquet matching the
    main projections schema for those two columns.

    Returns:
        Path to ``cmip6_projections_pangeo.parquet``.
    """
    output_file = CMIP6_PANGEO_FILE
    if output_file.exists() and not force:
        log.info(
            "Pangeo projections already exist (use --force to rebuild): %s",
            output_file,
        )
        return output_file

    CMIP6_DIR.mkdir(parents=True, exist_ok=True)

    models = models or list(MODEL_MAP.keys())
    variables = variables or list(PANGEO_VARS.keys())
    scenarios = scenarios or list(CMIP6_SCENARIOS)
    # Mirror the CDS default: always include the 2019–2024 reference
    # window so the delta-method bias-correction step has model-reference
    # MLD / intpp values to compare against the obs baseline.
    decades = decades or [*CMIP6_DECADES, CMIP6_REFERENCE_DECADE]

    grid = _load_target_grid()
    if grid is None:
        return output_file
    target_lats, target_lons, baseline = grid
    log.info("Target grid: %d lats x %d lons", len(target_lats), len(target_lons))

    log.info("Opening Pangeo CMIP6 catalogue: %s", PANGEO_CAT_URL)
    cat = intake.open_esm_datastore(PANGEO_CAT_URL)
    log.info("Catalogue entries: %s", f"{len(cat.df):,}")

    # all_results[scenario][var_short][f"{decade}__{season}"] = [arr, ...]
    all_results: dict[str, dict[str, dict[str, list[np.ndarray]]]] = {
        s: {PANGEO_VARS[v]: {} for v in variables} for s in scenarios
    }

    for scenario in scenarios:
        for var_pangeo in variables:
            var_short = PANGEO_VARS[var_pangeo]
            log.info("=" * 60)
            log.info("Scenario: %s   Variable: %s", scenario, var_short)
            log.info("=" * 60)
            for model_code in models:
                model_pangeo = MODEL_MAP[model_code]
                log.info(
                    "Processing %s | %s | %s",
                    model_pangeo,
                    var_pangeo,
                    scenario,
                )
                grids = _process_model_scenario(
                    cat,
                    model_pangeo,
                    var_pangeo,
                    scenario,
                    target_lats,
                    target_lons,
                    decades,
                )
                for key, arr in grids.items():
                    all_results[scenario][var_short].setdefault(key, []).append(arr)
                if grids:
                    log.info(
                        "  OK %s: %d (decade,season) grids",
                        model_pangeo,
                        len(grids),
                    )

    # ── Assemble parquet ───────────────────────────────────────────
    log.info("Assembling Pangeo parquet...")
    lon2d, lat2d = np.meshgrid(target_lons, target_lats)
    flat_lat = lat2d.ravel()
    flat_lon = lon2d.ravel()

    bl_pivot = baseline.groupby(["lat", "lon"])["sst"].first().reset_index()
    bl_mask = pd.DataFrame({"lat": flat_lat, "lon": flat_lon}).merge(
        bl_pivot, on=["lat", "lon"], how="left"
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
                contributors: dict[str, int] = {}
                for var_pangeo in variables:
                    var_short = PANGEO_VARS[var_pangeo]
                    stack = all_results[scenario][var_short].get(
                        f"{decade}__{season}", []
                    )
                    contributors[var_short] = len(stack)
                    if not stack:
                        row[var_short] = np.full(flat_lat.shape, np.nan)
                    else:
                        arr = np.stack(stack, axis=0)
                        ensemble = np.nanmean(arr, axis=0)
                        flat = ensemble.ravel()
                        flat = np.where(land_mask, np.nan, flat)
                        row[var_short] = flat
                log.info(
                    "  %s/%s/%s: "
                    + ", ".join(f"{k}={v}" for k, v in contributors.items()),
                    scenario,
                    decade,
                    season,
                )
                df = pd.DataFrame(row)
                covar_cols = [PANGEO_VARS[v] for v in variables]
                df = df.dropna(subset=covar_cols, how="all")
                frames.append(df)

    merged = pd.concat(frames, ignore_index=True)
    col_order = ["lat", "lon", "season", "scenario", "decade"] + [
        PANGEO_VARS[v] for v in variables
    ]
    merged = merged[col_order]
    merged.to_parquet(output_file, index=False)
    size_mb = output_file.stat().st_size / 1e6
    log.info(
        "Saved %s rows to %s (%.1f MB)",
        f"{len(merged):,}",
        output_file,
        size_mb,
    )
    return output_file


# ── Merge into main projections parquet ───────────────────────────────


def merge_into_projections(
    *,
    pangeo_file: Path = CMIP6_PANGEO_FILE,
    main_file: Path = CMIP6_PROJECTIONS_FILE,
) -> Path:
    """Replace mld / pp_upper_200m columns in main projections parquet
    with Pangeo-sourced values.

    The merge key is (lat, lon, season, scenario, decade).  Keeps
    sst / sst_sd / sla from CDS untouched.
    """
    if not pangeo_file.exists():
        raise FileNotFoundError(f"Pangeo parquet missing: {pangeo_file}")
    if not main_file.exists():
        raise FileNotFoundError(f"Main parquet missing: {main_file}")

    main = pd.read_parquet(main_file)
    pangeo = pd.read_parquet(pangeo_file)
    log.info(
        "Main rows: %s   Pangeo rows: %s",
        f"{len(main):,}",
        f"{len(pangeo):,}",
    )

    pangeo_cols = [c for c in pangeo.columns if c in ("mld", "pp_upper_200m")]
    # Drop the all-NaN columns from main, then left-join Pangeo values.
    main = main.drop(columns=[c for c in pangeo_cols if c in main.columns])
    merged = main.merge(
        pangeo[["lat", "lon", "season", "scenario", "decade", *pangeo_cols]],
        on=["lat", "lon", "season", "scenario", "decade"],
        how="left",
    )

    # Restore canonical column order.
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

    # Back up before overwrite.
    backup = main_file.with_suffix(".parquet.pre_pangeo")
    if not backup.exists():
        main_file.replace(backup)
        log.info("Backed up previous main file -> %s", backup.name)
    else:
        log.info("Backup already exists (%s); overwriting main", backup.name)

    merged.to_parquet(main_file, index=False)
    size_mb = main_file.stat().st_size / 1e6
    log.info(
        "Wrote %s rows to %s (%.1f MB)",
        f"{len(merged):,}",
        main_file,
        size_mb,
    )

    # Coverage summary
    for col in pangeo_cols:
        coverage = 100.0 * merged[col].notna().mean()
        log.info(
            "  %s: %.1f%% non-null  (mean=%.3f, min=%.3f, max=%.3f)",
            col,
            coverage,
            merged[col].mean(skipna=True),
            merged[col].min(skipna=True),
            merged[col].max(skipna=True),
        )
    return main_file


# ── CLI ───────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch CMIP6 MLD + intpp from Pangeo (filling the CDS gap) "
            "and merge into cmip6_projections.parquet."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild Pangeo parquet even if cached",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Only fetch + write pangeo parquet; skip merge into main",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help=(f"Subset of internal model codes (default: all {len(MODEL_MAP)})"),
    )
    parser.add_argument(
        "--variables",
        nargs="+",
        default=None,
        choices=list(PANGEO_VARS.keys()),
        help="Pangeo variable_ids (default: mlotst intpp)",
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


def main() -> None:
    args = _parse_args()
    download_pangeo_vars(
        force=args.force,
        models=args.models,
        variables=args.variables,
        scenarios=args.scenarios,
        decades=args.decades,
    )
    if not args.no_merge:
        merge_into_projections()


if __name__ == "__main__":
    main()

"""Apply delta-method bias correction to CMIP6 projections.

CMIP6 model output has systematic biases relative to observations
(SST offsets of 1-3 C in some regions, factor-of-2 PP errors, etc.).
The delta method removes those biases by using only the model's
*change signal* and grafting it onto our observational baseline:

    X_projected(scenario, decade, lat, lon, season)
        = X_baseline(lat, lon, season)
        + [ X_model(scenario, decade, lat, lon, season)
            - X_model(scenario, reference, lat, lon, season) ]    (additive)

    PP_projected
        = PP_baseline * ( PP_model_future / max(PP_model_ref, floor) )  (multiplicative)

Reference period: 2019-2024, matching the observational baseline window
in ``ocean_covariates.parquet`` (Copernicus reanalysis).  All SSP
scenarios are functionally identical in 2019-2024 because cumulative
emissions have not yet diverged, but we use each scenario's own
reference run for internal consistency.

Variables and treatment
-----------------------
* sst  -- additive delta (preserves observed coastal gradients)
* mld  -- additive delta, floored at 1 m
* sla  -- additive delta (sea level anomaly)
* pp_upper_200m  -- multiplicative ratio (preserves non-negativity,
                    handles strong spatial skew between gyres / coasts;
                    model reference floored at 1 mg C / m^2 / day)

sst_sd is the cross-model ensemble spread for the future decade and
is not bias-corrected -- it is a measure of model agreement, not an
observable quantity.

Standard practice in ecological projection literature: Hazen et al.
2013, Becker et al. 2019, IPCC AR6 WG1 cross-chapter box 10.2, ISIMIP
bias-correction protocol.

CLI usage
---------
    uv run python pipeline/ingestion/apply_cmip6_delta.py
    uv run python pipeline/ingestion/apply_cmip6_delta.py --dry-run
    uv run python pipeline/ingestion/apply_cmip6_delta.py --force
"""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

import pandas as pd

from pipeline.config import (
    CMIP6_DECADES,
    CMIP6_PROJECTIONS_BACKUP_FILE,
    CMIP6_PROJECTIONS_FILE,
    CMIP6_REFERENCE_DECADE,
    CMIP6_SCENARIOS,
    OCEAN_COVARIATES_FILE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# Floors to prevent pathological deltas in degenerate cells.
PP_REF_FLOOR_MGC = 1.0  # mg C / m^2 / day
MLD_PROJECTED_FLOOR_M = 1.0  # m

ADDITIVE_VARS: tuple[str, ...] = ("sst", "mld", "sla")
MULTIPLICATIVE_VARS: tuple[str, ...] = ("pp_upper_200m",)
ALL_BIAS_VARS: tuple[str, ...] = ADDITIVE_VARS + MULTIPLICATIVE_VARS

JOIN_KEYS: list[str] = ["lat", "lon", "season"]


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load raw CMIP6 projections (with reference rows) and obs baseline."""
    if not CMIP6_PROJECTIONS_FILE.exists():
        raise FileNotFoundError(
            f"CMIP6 projections missing: {CMIP6_PROJECTIONS_FILE}. "
            "Run download_cmip6_projections.py then download_cmip6_pangeo.py first."
        )
    if not OCEAN_COVARIATES_FILE.exists():
        raise FileNotFoundError(
            f"Observational baseline missing: {OCEAN_COVARIATES_FILE}. "
            "Run download_ocean_covariates.py first."
        )
    proj = pd.read_parquet(CMIP6_PROJECTIONS_FILE)
    baseline = pd.read_parquet(OCEAN_COVARIATES_FILE)
    log.info(
        "Loaded projections: %s rows; baseline: %s rows",
        f"{len(proj):,}",
        f"{len(baseline):,}",
    )
    return proj, baseline


def _validate_inputs(proj: pd.DataFrame, baseline: pd.DataFrame) -> None:
    """Sanity-check that reference rows exist and grids align."""
    decades_present = set(proj["decade"].unique())
    if CMIP6_REFERENCE_DECADE not in decades_present:
        raise ValueError(
            f"Reference decade '{CMIP6_REFERENCE_DECADE}' missing from "
            f"projections parquet (found: {sorted(decades_present)}). "
            "Re-run the CMIP6 download scripts to fetch the 2019-2024 "
            "reference window."
        )
    missing_futures = set(CMIP6_DECADES) - decades_present
    if missing_futures:
        log.warning(
            "Future decades missing from projections: %s", sorted(missing_futures)
        )
    for scenario in CMIP6_SCENARIOS:
        ref_rows = proj[
            (proj["scenario"] == scenario) & (proj["decade"] == CMIP6_REFERENCE_DECADE)
        ]
        if ref_rows.empty:
            raise ValueError(
                f"No reference rows for scenario={scenario}. "
                "Re-run download with --scenarios "
                f"{' '.join(CMIP6_SCENARIOS)}."
            )

    proj_coords = set(zip(proj["lat"].round(4), proj["lon"].round(4), strict=True))
    base_coords = set(
        zip(baseline["lat"].round(4), baseline["lon"].round(4), strict=True)
    )
    overlap = len(proj_coords & base_coords)
    log.info(
        "Grid overlap: %s of %s projection cells match baseline",
        f"{overlap:,}",
        f"{len(proj_coords):,}",
    )
    if overlap < 0.5 * len(proj_coords):
        log.warning(
            "Low grid overlap (%.1f%%). Delta-method coverage will be limited.",
            100.0 * overlap / max(len(proj_coords), 1),
        )


def _compute_delta_table(proj: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    """Build the bias-corrected projection table.

    For each (scenario, future_decade, lat, lon, season) row, compute
    bias-corrected values from the obs baseline + model delta.
    """
    ref = proj[proj["decade"] == CMIP6_REFERENCE_DECADE].copy()
    futures = proj[proj["decade"] != CMIP6_REFERENCE_DECADE].copy()
    log.info(
        "Reference rows: %s  |  Future rows: %s",
        f"{len(ref):,}",
        f"{len(futures):,}",
    )

    # Reference indexed by (scenario, lat, lon, season) -> model ref values
    ref_cols = [*JOIN_KEYS, "scenario", *ALL_BIAS_VARS]
    ref_indexed = ref[ref_cols].rename(columns={v: f"{v}_ref" for v in ALL_BIAS_VARS})

    # Baseline indexed by (lat, lon, season) -> obs values
    base_cols = [*JOIN_KEYS, *ALL_BIAS_VARS]
    baseline_indexed = baseline[base_cols].rename(
        columns={v: f"{v}_obs" for v in ALL_BIAS_VARS}
    )

    # Join futures to its own scenario's reference, then to obs baseline.
    merged = futures.merge(
        ref_indexed, on=[*JOIN_KEYS, "scenario"], how="left", validate="m:1"
    )
    merged = merged.merge(baseline_indexed, on=JOIN_KEYS, how="left", validate="m:1")

    # Additive deltas: projected = obs + (future_model - ref_model)
    for var in ADDITIVE_VARS:
        delta = merged[var] - merged[f"{var}_ref"]
        merged[f"{var}_bc"] = merged[f"{var}_obs"] + delta

    # Multiplicative ratio: projected = obs * (future_model / max(ref, floor))
    for var in MULTIPLICATIVE_VARS:
        ref_floored = merged[f"{var}_ref"].clip(lower=PP_REF_FLOOR_MGC)
        ratio = merged[var] / ref_floored
        merged[f"{var}_bc"] = merged[f"{var}_obs"] * ratio

    # Floors / non-negativity
    merged["mld_bc"] = merged["mld_bc"].clip(lower=MLD_PROJECTED_FLOOR_M)
    merged["pp_upper_200m_bc"] = merged["pp_upper_200m_bc"].clip(lower=0.0)

    return merged


def _replace_raw_with_corrected(merged: pd.DataFrame) -> pd.DataFrame:
    """Replace raw model columns with bias-corrected values; preserve schema."""
    out = merged.copy()
    for var in ALL_BIAS_VARS:
        out[var] = out[f"{var}_bc"]

    # Drop helper columns
    drop_cols = (
        [f"{v}_ref" for v in ALL_BIAS_VARS]
        + [f"{v}_obs" for v in ALL_BIAS_VARS]
        + [f"{v}_bc" for v in ALL_BIAS_VARS]
    )
    out = out.drop(columns=drop_cols)

    # Preserve canonical column order
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
    out = out[[c for c in col_order if c in out.columns]]

    # Drop rows where all bias-corrected vars are NaN (e.g. land cells with
    # no observational baseline)
    out = out.dropna(subset=list(ALL_BIAS_VARS), how="all")
    return out


def _log_climate_signal(corrected: pd.DataFrame, raw: pd.DataFrame) -> None:
    """Compare raw vs bias-corrected projections to verify the delta math."""
    log.info("=" * 70)
    log.info("Climate signal sanity check (SSP5-8.5 ensemble mean)")
    log.info("=" * 70)
    log.info("%-12s %-8s %12s %12s %12s", "decade", "var", "raw", "corrected", "delta")
    log.info("-" * 70)
    for decade in CMIP6_DECADES:
        raw_d = raw[(raw["scenario"] == "ssp585") & (raw["decade"] == decade)]
        cor_d = corrected[
            (corrected["scenario"] == "ssp585") & (corrected["decade"] == decade)
        ]
        if cor_d.empty:
            continue
        for var in ALL_BIAS_VARS:
            raw_mean = raw_d[var].mean()
            cor_mean = cor_d[var].mean()
            log.info(
                "%-12s %-8s %12.3f %12.3f %12.3f",
                decade,
                var,
                raw_mean,
                cor_mean,
                cor_mean - raw_mean,
            )
        log.info("-" * 70)


def apply_delta_method(*, force: bool = False, dry_run: bool = False) -> Path:
    """Apply the delta method and overwrite ``cmip6_projections.parquet``.

    Backs up the raw model-output file to ``cmip6_projections.pre_delta``
    on first run.  Subsequent runs require ``--force`` and will overwrite
    the backup.
    """
    raw_proj, baseline = _load_inputs()
    _validate_inputs(raw_proj, baseline)

    merged = _compute_delta_table(raw_proj, baseline)
    corrected = _replace_raw_with_corrected(merged)

    log.info("Bias-corrected output: %s rows", f"{len(corrected):,}")
    _log_climate_signal(corrected, raw_proj)

    if dry_run:
        log.info("Dry-run: not writing parquet.")
        return CMIP6_PROJECTIONS_FILE

    if CMIP6_PROJECTIONS_BACKUP_FILE.exists() and not force:
        raise FileExistsError(
            f"Backup already exists: {CMIP6_PROJECTIONS_BACKUP_FILE}. "
            "Use --force to overwrite (note: this discards the previous "
            "raw-model-output backup)."
        )
    shutil.copy2(CMIP6_PROJECTIONS_FILE, CMIP6_PROJECTIONS_BACKUP_FILE)
    log.info("Backed up raw projections to %s", CMIP6_PROJECTIONS_BACKUP_FILE)

    corrected.to_parquet(CMIP6_PROJECTIONS_FILE, index=False)
    size_mb = CMIP6_PROJECTIONS_FILE.stat().st_size / 1e6
    log.info(
        "Wrote bias-corrected projections to %s (%.1f MB)",
        CMIP6_PROJECTIONS_FILE,
        size_mb,
    )

    # Final coverage report
    for var in ALL_BIAS_VARS:
        coverage = 100.0 * corrected[var].notna().mean()
        log.info("  %s coverage: %.1f%%", var, coverage)

    return CMIP6_PROJECTIONS_FILE


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Apply delta-method bias correction to CMIP6 ocean projections. "
            "Reads raw CMIP6 model ensemble means (with 2019-2024 reference "
            "rows) and the observational baseline; writes bias-corrected "
            "projections back to cmip6_projections.parquet."
        )
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the .pre_delta backup if it already exists.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute deltas and log stats without writing the parquet.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    apply_delta_method(force=args.force, dry_run=args.dry_run)

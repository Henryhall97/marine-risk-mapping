"""Extract ML training features from PostGIS mart tables to Parquet.

Pulls fct_whale_sdm_training and fct_whale_sdm_seasonal into local
parquet files with land-cell filtering, type handling, and spatial
block assignment for cross-validation.

Usage:
    uv run python pipeline/analysis/extract_features.py
    uv run python pipeline/analysis/extract_features.py --dataset seasonal
    uv run python pipeline/analysis/extract_features.py --dataset all
"""

import argparse
import logging

import h3
import numpy as np
import pandas as pd
import psycopg2

from pipeline.analysis.evaluate import (
    empirical_variogram,
    h3_resolution_for_range_km,
    variogram_range_km,
)
from pipeline.config import (
    DB_CONFIG,
    H3_CV_RESOLUTION,
    ML_DIR,
    N_CV_FOLDS,
    SDM_FEATURES_FILE,
    SDM_SEASONAL_FEATURES_FILE,
    SDM_TARGET_GROUP_BACKGROUND,
    SDM_THINNING_DIST_KM,
    STRIKE_FEATURES_FILE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)


def _assign_spatial_blocks(
    df: pd.DataFrame,
    h3_col: str = "h3_cell",
    cv_resolution: int | None = None,
) -> pd.DataFrame:
    """Assign each row to a spatial block and a CV fold.

    Uses H3 parent cells at the CV block resolution to group nearby
    cells. All features stay at res-7 — the parent cell is only used as
    a block identifier for fold assignment. When ``cv_resolution`` is
    None the configured default (``H3_CV_RESOLUTION``, res-2 ~158 km)
    is used; pass a variogram-driven resolution to size blocks to the
    data's spatial autocorrelation range (item E).

    For seasonal data, all 4 seasons for a given cell land in the
    same fold, preventing spatial leakage across the train/test
    boundary (since block assignment is purely spatial).
    """
    res = H3_CV_RESOLUTION if cv_resolution is None else cv_resolution
    df = df.copy()
    # h3_cell is stored as BIGINT; h3 v4 cell_to_parent expects hex strings.
    df["spatial_block"] = df[h3_col].apply(
        lambda c: h3.cell_to_parent(h3.int_to_str(int(c)), res)
    )
    # Deterministic fold assignment: sorted block IDs mod N_CV_FOLDS
    unique_blocks = sorted(df["spatial_block"].unique())
    block_to_fold = {b: i % N_CV_FOLDS for i, b in enumerate(unique_blocks)}
    df["cv_fold"] = df["spatial_block"].map(block_to_fold)
    return df


def _estimate_cv_resolution(
    df: pd.DataFrame,
    target_col: str,
    lat_col: str = "cell_lat",
    lon_col: str = "cell_lon",
) -> int | None:
    """Pick a CV block resolution from the target's spatial autocorrelation.

    Computes the empirical variogram of the binary target across space,
    estimates the practical autocorrelation range, and maps it to the
    finest H3 resolution whose blocks are still ≥ that range (item E).
    Falls back to the configured default if the variogram does not
    plateau. Logs the decision for traceability.
    """
    if not {target_col, lat_col, lon_col}.issubset(df.columns):
        return None
    sub = df[[target_col, lat_col, lon_col]].dropna()
    if len(sub) < 100:
        return None
    centres, gamma, _ = empirical_variogram(
        sub[target_col].to_numpy(dtype=float),
        sub[lat_col].to_numpy(dtype=float),
        sub[lon_col].to_numpy(dtype=float),
    )
    range_km = variogram_range_km(centres, gamma)
    res = h3_resolution_for_range_km(range_km)
    if res is None:
        log.info(
            "Variogram for %s did not plateau (range=%.1f km) — "
            "using default CV res-%d.",
            target_col,
            range_km,
            H3_CV_RESOLUTION,
        )
        return None
    edge = h3.average_hexagon_edge_length(res, unit="km")
    log.info(
        "Variogram-driven CV block: %s range=%.1f km → H3 res-%d (~%.0f km edge).",
        target_col,
        range_km,
        res,
        edge,
    )
    return res


# ── Sampling-bias correction (item C) ───────────────────────


def _equirect_km(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Equirectangular lat/lon → local planar km (short-range OK)."""
    lat0 = float(np.mean(lat)) if len(lat) else 0.0
    x = np.radians(lon) * 6371.0 * np.cos(np.radians(lat0))
    y = np.radians(lat) * 6371.0
    return np.column_stack([x, y])


def apply_spatial_thinning(
    lat: np.ndarray,
    lon: np.ndarray,
    min_dist_km: float,
    seed: int = 42,
) -> np.ndarray:
    """Greedy spatial thinning of presence points (Aiello-Lammens 2015).

    Returns a boolean mask selecting a subset such that no two retained
    points lie within ``min_dist_km`` of each other, reducing the weight
    of spatially oversampled survey areas. Random visit order (seeded).
    """
    n = len(lat)
    if min_dist_km <= 0 or n == 0:
        return np.ones(n, dtype=bool)
    coords = _equirect_km(np.asarray(lat, float), np.asarray(lon, float))
    rng = np.random.RandomState(seed)
    order = rng.permutation(n)
    keep = np.zeros(n, dtype=bool)
    kept_coords: list[np.ndarray] = []
    min_sq = min_dist_km * min_dist_km
    for i in order:
        c = coords[i]
        ok = True
        for kc in kept_coords:
            dx = c[0] - kc[0]
            dy = c[1] - kc[1]
            if dx * dx + dy * dy < min_sq:
                ok = False
                break
        if ok:
            keep[i] = True
            kept_coords.append(c)
    return keep


def build_training_mask(
    df: pd.DataFrame,
    focal_col: str,
    group_col: str = "total_sightings",
    lat_col: str = "cell_lat",
    lon_col: str = "cell_lon",
    thinning_dist_km: float = SDM_THINNING_DIST_KM,
    target_group_background: bool = SDM_TARGET_GROUP_BACKGROUND,
    seed: int = 42,
) -> np.ndarray:
    """Build a per-species training-row mask (item C).

    Combines target-group background and spatial thinning:
      * Target-group background (Phillips 2009): background/absence rows
        are restricted to cells where the target group (any cetacean,
        ``group_col`` > 0) was observed — i.e. where there was survey
        effort. Cells with no cetacean observation are excluded from
        *fitting* (they are still scored by the final model downstream).
      * Spatial thinning (Aiello-Lammens 2015): presence rows closer than
        ``thinning_dist_km`` to a retained presence are dropped.

    Returns a boolean mask aligned to ``df`` rows; non-selected rows are
    excluded from model fitting only.
    """
    presence = df[focal_col].to_numpy() > 0
    mask = np.ones(len(df), dtype=bool)

    if target_group_background and group_col in df.columns:
        surveyed = df[group_col].to_numpy() > 0
        # Target-group background only applies when the focal species is a
        # strict subset of the surveyed target group — i.e. there exist
        # surveyed cells that are NOT focal presences (genuine absences).
        # For the aggregate any-whale target, presence == surveyed, leaving
        # zero background; restricting there would drop every negative and
        # leave a single-class fit. Skip TGB in that degenerate case.
        background = surveyed & ~presence
        if background.any():
            # Eligible = presences OR surveyed (target-group) background.
            mask = presence | surveyed

    if thinning_dist_km and thinning_dist_km > 0 and presence.any():
        retain = apply_spatial_thinning(
            df.loc[presence, lat_col].to_numpy(),
            df.loc[presence, lon_col].to_numpy(),
            thinning_dist_km,
            seed=seed,
        )
        thin_mask = np.ones(len(df), dtype=bool)
        thin_mask[np.where(presence)[0]] = retain
        mask = mask & thin_mask

    return mask


# ── Feature lists ───────────────────────────────────────────
# Columns to extract from each mart table (exclude geometry).

STRIKE_QUERY = """
SELECT
    h3_cell,
    cell_lat,
    cell_lon,
    -- Targets
    has_strike,
    total_strikes,
    fatal_strikes,
    baleen_strikes,
    right_whale_strikes,
    -- Traffic features
    months_active,
    total_pings,
    avg_monthly_vessels,
    peak_monthly_vessels,
    avg_speed_knots,
    peak_speed_knots,
    avg_high_speed_vessels,
    avg_large_vessels,
    avg_vessel_length_m,
    avg_deep_draft_vessels,
    avg_night_vessels,
    avg_commercial_vessels,
    avg_fishing_vessels,
    avg_passenger_vessels,
    -- Cetacean features
    total_sightings,
    unique_species,
    baleen_whale_sightings,
    recent_sightings,
    -- Bathymetry features
    depth_m,
    depth_range_m,
    is_continental_shelf,
    is_shelf_edge,
    depth_zone,
    -- Ocean covariates
    sst,
    sst_sd,
    mld,
    sla,
    pp_upper_200m,
    -- Proximity features (strike-proximity excluded: target leakage)
    dist_to_nearest_whale_km,
    dist_to_nearest_ship_km,
    whale_proximity_score,
    ship_proximity_score,
    dist_to_nearest_protection_km,
    protection_proximity_score,
    -- Speed zone features
    in_speed_zone,
    in_current_sma,
    in_proposed_zone,
    zone_count,
    max_season_days,
    -- MPA features
    mpa_count,
    has_strict_protection,
    has_no_take_zone,
    -- Nisi reference
    nisi_all_risk,
    nisi_shipping_index,
    nisi_whale_space_use,
    nisi_hotspot_overlap
FROM fct_strike_risk_training;
"""

SDM_QUERY = """
SELECT
    h3_cell,
    cell_lat,
    cell_lon,
    -- Target
    whale_present,
    total_sightings,
    unique_species,
    baleen_whale_sightings,
    recent_sightings,
    -- Per-species targets
    right_whale_present,
    humpback_present,
    fin_whale_present,
    blue_whale_present,
    sperm_whale_present,
    minke_whale_present,
    -- Ocean covariates
    sst,
    sst_sd,
    mld,
    sla,
    pp_upper_200m,
    -- Bathymetry
    depth_m,
    depth_range_m,
    is_continental_shelf,
    is_shelf_edge,
    depth_zone,
    -- Nisi reference
    nisi_all_risk,
    nisi_shipping_index,
    nisi_whale_space_use,
    nisi_hotspot_overlap,
    -- Proximity (whale-proximity excluded: target leakage)
    dist_to_nearest_ship_km,
    ship_proximity_score,
    dist_to_nearest_strike_km,
    strike_proximity_score,
    dist_to_nearest_protection_km,
    protection_proximity_score,
    -- Speed zone context
    in_speed_zone,
    in_current_sma,
    -- MPA context
    mpa_count,
    has_strict_protection
    -- NOTE: traffic features (avg_monthly_vessels, avg_speed_knots,
    -- months_active) deliberately excluded — detection bias
FROM fct_whale_sdm_training;
"""

SDM_SEASONAL_QUERY = """
SELECT
    h3_cell,
    season,
    cell_lat,
    cell_lon,
    -- Target
    whale_present,
    total_sightings,
    unique_species,
    baleen_whale_sightings,
    recent_sightings,
    -- Per-species targets
    right_whale_present,
    humpback_present,
    fin_whale_present,
    blue_whale_present,
    sperm_whale_present,
    minke_whale_present,
    gray_whale_present,
    rices_whale_present,
    -- Ocean covariates (seasonal)
    sst,
    sst_sd,
    mld,
    sla,
    pp_upper_200m,
    -- Bathymetry (static)
    depth_m,
    depth_range_m,
    is_continental_shelf,
    is_shelf_edge,
    depth_zone,
    -- Nisi reference (static)
    nisi_all_risk,
    nisi_shipping_index,
    nisi_whale_space_use,
    nisi_hotspot_overlap,
    -- Nisi per-species risk (validation benchmarks)
    nisi_blue_risk,
    nisi_fin_risk,
    nisi_humpback_risk,
    nisi_sperm_risk,
    -- Proximity (static; whale-proximity excluded: leakage)
    dist_to_nearest_ship_km,
    ship_proximity_score,
    dist_to_nearest_strike_km,
    strike_proximity_score,
    dist_to_nearest_protection_km,
    protection_proximity_score,
    -- Speed zone context (seasonal)
    in_speed_zone,
    in_current_sma,
    -- MPA context (static)
    mpa_count,
    has_strict_protection
FROM fct_whale_sdm_seasonal;
"""


# ── Chunked extraction ──────────────────────────────────────
CHUNK_SIZE = 100_000  # rows per server-side cursor fetch


def _extract_table(query: str, label: str) -> pd.DataFrame:
    """Extract a table using a server-side cursor for memory efficiency.

    Reads in CHUNK_SIZE-row batches so the full 1.8M-row result set
    is never buffered entirely in the psycopg2 client layer.
    Raises if the result is empty (stale or missing mart table).
    """
    log.info("Extracting %s from PostGIS…", label)
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(name="ml_extract") as cur:
            cur.itersize = CHUNK_SIZE
            cur.execute(query)
            # Server-side cursors: description is only available after
            # the first fetch, not immediately after execute().
            chunks: list[pd.DataFrame] = []
            total_rows = 0
            columns: list[str] | None = None
            while True:
                rows = cur.fetchmany(CHUNK_SIZE)
                if not rows:
                    break
                if columns is None:
                    columns = [desc[0] for desc in cur.description]
                chunks.append(pd.DataFrame(rows, columns=columns))
                total_rows += len(rows)
                log.info("  fetched %d rows so far", total_rows)
        df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    finally:
        conn.close()

    if df.empty:
        raise RuntimeError(
            f"{label} returned 0 rows — is the mart table "
            f"populated? Run `dbt build` first."
        )

    log.info("  → %d rows × %d columns", len(df), len(df.columns))
    return df


def _encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode categorical columns (depth_zone)."""
    if "depth_zone" in df.columns:
        dummies = pd.get_dummies(df["depth_zone"], prefix="depth_zone", dtype=int)
        df = pd.concat([df.drop(columns=["depth_zone"]), dummies], axis=1)
    return df


def _prepare_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Convert types for XGBoost compatibility.

    - Boolean columns → float64 (True=1.0, False=0.0, None=NaN)
    - Numeric NaN left as-is — XGBoost's hist tree method natively
      learns the optimal split direction for missing values.
    """
    for col in df.columns:
        if df[col].dtype == "bool":
            df[col] = df[col].astype("float64")
        elif df[col].dtype == "object":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _check_fold_balance(
    df: pd.DataFrame,
    target_col: str,
    label: str,
    min_positives: int = 5,
) -> None:
    """Log positives per CV fold, warn if any fold has too few."""
    fold_counts = df.groupby("cv_fold")[target_col].agg(["sum", "count"])
    fold_counts.columns = ["positives", "total"]
    log.info("%s fold balance:\n%s", label, fold_counts.to_string())
    low_folds = fold_counts[fold_counts["positives"] < min_positives]
    if not low_folds.empty:
        log.warning(
            "%s: folds %s have fewer than %d positives — "
            "CV metrics will be unreliable for these folds.",
            label,
            list(low_folds.index),
            min_positives,
        )


def extract_strike_features() -> pd.DataFrame:
    """Extract and prepare strike risk training features."""
    df = _extract_table(STRIKE_QUERY, "fct_strike_risk_training")
    cv_res = _estimate_cv_resolution(df, "has_strike")
    df = _assign_spatial_blocks(df, cv_resolution=cv_res)
    df = _encode_categoricals(df)
    df = _prepare_dtypes(df)
    _check_fold_balance(df, "has_strike", "Strike")

    log.info(
        "Strike dataset: %d rows, %d positive (%.4f%%)",
        len(df),
        df["has_strike"].sum(),
        100 * df["has_strike"].mean(),
    )
    return df


def extract_sdm_features() -> pd.DataFrame:
    """Extract and prepare whale SDM training features."""
    df = _extract_table(SDM_QUERY, "fct_whale_sdm_training")
    cv_res = _estimate_cv_resolution(df, "whale_present")
    df = _assign_spatial_blocks(df, cv_resolution=cv_res)
    df = _encode_categoricals(df)
    df = _prepare_dtypes(df)
    _check_fold_balance(df, "whale_present", "SDM")

    log.info(
        "SDM dataset: %d rows, %d positive (%.2f%%)",
        len(df),
        df["whale_present"].sum(),
        100 * df["whale_present"].mean(),
    )
    return df


def _encode_season(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode the season column into 4 binary indicator columns.

    Drops the original 'season' string column and adds:
    season_winter, season_spring, season_summer, season_fall.
    """
    if "season" not in df.columns:
        return df
    dummies = pd.get_dummies(df["season"], prefix="season", dtype=int)
    df = pd.concat([df.drop(columns=["season"]), dummies], axis=1)
    return df


def extract_sdm_seasonal_features() -> pd.DataFrame:
    """Extract and prepare seasonal whale SDM training features."""
    df = _extract_table(SDM_SEASONAL_QUERY, "fct_whale_sdm_seasonal")

    # Spatial block CV — same cell → same fold across all 4 seasons.
    # Block size driven by the target's spatial autocorrelation range.
    cv_res = _estimate_cv_resolution(df, "whale_present")
    df = _assign_spatial_blocks(df, cv_resolution=cv_res)
    df = _encode_categoricals(df)
    df = _encode_season(df)
    df = _prepare_dtypes(df)
    _check_fold_balance(df, "whale_present", "SDM-seasonal")

    log.info(
        "SDM-seasonal dataset: %d rows, %d positive (%.2f%%)",
        len(df),
        df["whale_present"].sum(),
        100 * df["whale_present"].mean(),
    )
    return df


def _save_parquet(df: pd.DataFrame, path, label: str) -> None:
    """Save DataFrame to parquet and log file size."""
    df.to_parquet(path, index=False)
    log.info(
        "Saved %s: %s (%.1f MB)",
        label,
        path,
        path.stat().st_size / 1e6,
    )


def main(datasets: list[str] | None = None) -> None:
    """Extract training datasets to parquet.

    Parameters
    ----------
    datasets : list of {"strike", "sdm", "seasonal"}, optional
        Which datasets to extract. Default: ["sdm", "seasonal"]
        (strike model is parked — only 67 positives across 1.8M cells).
    """
    ML_DIR.mkdir(parents=True, exist_ok=True)
    datasets = datasets or ["sdm", "seasonal"]

    if "strike" in datasets:
        strike_df = extract_strike_features()
        _save_parquet(strike_df, STRIKE_FEATURES_FILE, "strike")

    if "sdm" in datasets:
        sdm_df = extract_sdm_features()
        _save_parquet(sdm_df, SDM_FEATURES_FILE, "sdm")

    if "seasonal" in datasets:
        sdm_s_df = extract_sdm_seasonal_features()
        _save_parquet(sdm_s_df, SDM_SEASONAL_FEATURES_FILE, "sdm-seasonal")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract ML training features from PostGIS to Parquet",
    )
    parser.add_argument(
        "--dataset",
        nargs="+",
        choices=["strike", "sdm", "seasonal", "all"],
        default=["sdm", "seasonal"],
        help="Datasets to extract (default: sdm seasonal)",
    )
    args = parser.parse_args()
    ds = ["strike", "sdm", "seasonal"] if "all" in args.dataset else args.dataset
    main(datasets=ds)

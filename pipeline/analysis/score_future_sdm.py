"""Score trained seasonal SDMs on CMIP6-projected covariates.

Loads the trained XGBoost seasonal SDMs (from MLflow file store)
and scores the full H3 grid under projected future ocean conditions
(SSP2-4.5 and SSP5-8.5 × 2040s/2060s/2080s).

For each (scenario, decade, season, species) combination:
1. Load projected ocean covariates from cmip6_projections.parquet
2. Join with static features (bathymetry, proximity) from the
   existing seasonal SDM features parquet
3. Build the feature matrix matching the trained model's columns
4. Predict whale habitat probability for all H3 cells
5. Save results to sdm_projections/ directory

Output grain: (h3_cell, season, scenario, decade) — one parquet
per species per scenario per decade.

Usage::

    # Score all species × scenarios × decades:
    uv run python pipeline/analysis/score_future_sdm.py

    # Score only one scenario:
    uv run python pipeline/analysis/score_future_sdm.py \\
        --scenario ssp585

    # Score only one decade:
    uv run python pipeline/analysis/score_future_sdm.py \\
        --decade 2080s

    # Force re-score even if outputs exist:
    uv run python pipeline/analysis/score_future_sdm.py --force
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from pipeline.analysis.evaluate import apply_calibrator
from pipeline.config import (
    CMIP6_DECADES,
    CMIP6_PROJECTIONS_FILE,
    CMIP6_SCENARIOS,
    ML_DIR,
    MLFLOW_TRACKING_URI,
    SDM_PROJECTIONS_DIR,
    SDM_SEASONAL_FEATURES_FILE,
    SEASON_ORDER,
)

# Local artifact root where train_sdm_seasonal.py persists the
# per-species isotonic calibrator (calibrator.joblib).
ARTIFACTS_DIR = ML_DIR / "artifacts" / "sdm_seasonal"

# MLflow experiment that holds the seasonal SDM models (must match
# train_sdm_seasonal.EXPERIMENT_NAME).
SDM_EXPERIMENT_NAME = "whale_sdm_seasonal"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# Same target mapping as train_sdm_seasonal.py
SCORE_TARGETS = {
    "whale_present": "sdm_any_whale",
    "blue_whale_present": "sdm_blue_whale",
    "fin_whale_present": "sdm_fin_whale",
    "humpback_present": "sdm_humpback_whale",
    "sperm_whale_present": "sdm_sperm_whale",
    "right_whale_present": "sdm_right_whale",
    "minke_whale_present": "sdm_minke_whale",
    "gray_whale_present": "sdm_gray_whale",
    "rices_whale_present": "sdm_rices_whale",
}

# Static features that do NOT change with climate projections.
# These are bathymetry + proximity + season indicators.
STATIC_FEATURE_COLS = [
    "depth_m",
    "depth_range_m",
    "is_continental_shelf",
    "is_shelf_edge",
    "depth_zone_shelf",
    "depth_zone_slope",
    "depth_zone_abyssal",
    "dist_to_nearest_strike_km",
    "strike_proximity_score",
    "season_winter",
    "season_spring",
    "season_summer",
    "season_fall",
]

# Projected ocean covariates — these change per scenario/decade
OCEAN_FEATURE_COLS = [
    "sst",
    "sst_sd",
    "mld",
    "sla",
    "pp_upper_200m",
]


def _load_trained_models() -> dict[str, tuple[xgb.XGBClassifier, float, object | None]]:
    """Load the latest item B+C seasonal SDM model per target.

    Queries the MLflow tracking store (SQLite backend,
    ``whale_sdm_seasonal`` experiment) via the MLflow API and picks the
    MOST RECENT finished run for each target column.  This deliberately
    mirrors how the current out-of-fold predictions in
    ``ml_sdm_predictions`` were produced (the last ``--score-grid`` run),
    so the projected − current delta reflects climate signal rather than a
    model-version mismatch (copilot-instructions §7).

    NOTE: an earlier version scanned the file store
    ``mlruns/691897149364591822/`` directly, but that directory only holds
    the *March* pre-item-C models.  Today's item B+C runs live under the
    SQLite-backed experiment (id 4), which has no file-based ``params/``
    entries — so the directory scan silently fell back to stale models.

    Returns:
        Dict mapping target_col → (model, auc, calibrator).
    """
    import mlflow
    import mlflow.xgboost

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    exp = mlflow.get_experiment_by_name(SDM_EXPERIMENT_NAME)
    if exp is None:
        raise RuntimeError(
            f"MLflow experiment '{SDM_EXPERIMENT_NAME}' not found at "
            f"{MLFLOW_TRACKING_URI}. Train seasonal SDMs first: "
            "uv run python pipeline/analysis/train_sdm_seasonal.py "
            "--score-grid"
        )

    runs = mlflow.search_runs(
        experiment_ids=[exp.experiment_id],
        filter_string="attributes.status = 'FINISHED'",
        order_by=["attributes.start_time DESC"],
    )

    models: dict[str, tuple[xgb.XGBClassifier, float, object | None]] = {}
    wanted = set(SCORE_TARGETS)
    for _, row in runs.iterrows():
        target = row.get("params.target_col")
        if not isinstance(target, str) or target not in wanted:
            continue
        if target in models:
            continue  # already have the most-recent run for this target

        run_id = row["run_id"]
        try:
            model = mlflow.xgboost.load_model(f"runs:/{run_id}/model")
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Run %s for %s has no loadable model: %s",
                run_id[:8],
                target,
                exc,
            )
            continue

        auc = row.get("metrics.cv_roc_auc_mean")
        auc = float(auc) if auc is not None and not pd.isna(auc) else float("nan")
        cal = _load_calibrator(target)
        models[target] = (model, auc, cal)
        log.info(
            "Loaded model: %s (run=%s, AUC=%.4f, calibrated=%s)",
            target,
            run_id[:8],
            auc,
            cal is not None,
        )

    missing = wanted - set(models)
    if missing:
        log.warning(
            "No FINISHED MLflow run found for: %s — these species will be "
            "skipped in projections.",
            ", ".join(sorted(missing)),
        )

    return models


def _load_calibrator(target_col: str):
    """Load the per-species isotonic calibrator (item B).

    The calibrator is fit on honest OOF predictions during training and
    persisted in the local ``artifacts/sdm_seasonal/<species>/`` directory
    (written alongside every score-grid run).  Applying it here keeps
    projected probabilities on the SAME calibrated scale as the current OOF
    predictions in ``ml_sdm_predictions`` — without this, the projected −
    current delta conflates the calibration gap with the climate signal
    (copilot-instructions §7).

    Returns the fitted calibrator, or ``None`` if not found.
    """
    import joblib

    target_short = target_col.replace("_present", "")
    path = ARTIFACTS_DIR / target_short / "calibrator.joblib"
    if path.exists():
        try:
            return joblib.load(path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to load calibrator %s: %s", path, exc)
    log.warning(
        "No calibrator found for %s — projections will be UNCALIBRATED "
        "and inconsistent with current OOF scale.",
        target_col,
    )
    return None


def _load_static_features() -> pd.DataFrame:
    """Load static (non-climate) features from the seasonal parquet.

    Extracts h3_cell + season indicators + bathymetry + proximity
    from the full seasonal SDM features file.  Deduplicates so we
    have one row per (h3_cell, season).
    """
    if not SDM_SEASONAL_FEATURES_FILE.exists():
        raise RuntimeError(
            f"Seasonal features not found: "
            f"{SDM_SEASONAL_FEATURES_FILE}. "
            f"Run: uv run python "
            f"pipeline/analysis/extract_features.py "
            f"--dataset seasonal"
        )

    log.info("Loading static features from seasonal parquet...")
    df = pd.read_parquet(SDM_SEASONAL_FEATURES_FILE)

    # Recover season from one-hot columns
    season_cols = [
        "season_winter",
        "season_spring",
        "season_summer",
        "season_fall",
    ]
    season_names = ["winter", "spring", "summer", "fall"]
    if all(c in df.columns for c in season_cols):
        idx = df[season_cols].values.argmax(axis=1)
        df["season"] = [season_names[i] for i in idx]
    elif "season" not in df.columns:
        raise ValueError("Cannot determine season from seasonal features")

    # Keep only the columns we need
    keep_cols = ["h3_cell", "season"] + [
        c for c in STATIC_FEATURE_COLS if c in df.columns
    ]
    df = df[keep_cols].copy()

    # Ensure one row per (h3_cell, season)
    before = len(df)
    df = df.drop_duplicates(subset=["h3_cell", "season"])
    if len(df) < before:
        log.info(
            "Deduplicated static features: %s → %s rows",
            f"{before:,}",
            f"{len(df):,}",
        )

    log.info(
        "Static features: %s rows (%s cells × %d seasons)",
        f"{len(df):,}",
        f"{df['h3_cell'].nunique():,}",
        df["season"].nunique(),
    )
    return df


def _load_projected_covariates(
    scenario: str,
    decade: str,
) -> pd.DataFrame:
    """Load projected ocean covariates for one scenario/decade.

    Returns a DataFrame with columns:
    lat, lon, season, sst, sst_sd, mld, sla, pp_upper_200m.
    """
    if not CMIP6_PROJECTIONS_FILE.exists():
        raise RuntimeError(
            f"CMIP6 projections not found: "
            f"{CMIP6_PROJECTIONS_FILE}. "
            f"Run: uv run python "
            f"pipeline/ingestion/"
            f"download_cmip6_projections.py"
        )

    df = pd.read_parquet(CMIP6_PROJECTIONS_FILE)
    mask = (df["scenario"] == scenario) & (df["decade"] == decade)
    proj = df[mask].copy()

    if proj.empty:
        raise ValueError(f"No data for {scenario}/{decade} in projections")

    log.info(
        "Projected covariates for %s/%s: %s rows",
        scenario,
        decade,
        f"{len(proj):,}",
    )
    return proj


def _spatial_join_covariates(
    static: pd.DataFrame,
    projected: pd.DataFrame,
) -> pd.DataFrame:
    """Join projected covariates to H3 cells by nearest lat/lon.

    The projected data is on a 0.25° grid; we need to assign each
    H3 centroid to the nearest projected grid cell.  We use the
    same approach as the existing ocean covariates intermediate
    model: spatial nearest-neighbour join.

    Since we need lat/lon for each h3_cell, we compute centroids
    from h3-py.
    """
    import h3

    # Get unique H3 cells and their centroids
    unique_cells = static["h3_cell"].unique()
    log.info(
        "Computing centroids for %s H3 cells...",
        f"{len(unique_cells):,}",
    )

    centroids = []
    for cell in unique_cells:
        try:
            cell_hex = h3.int_to_str(int(cell))
            lat, lon = h3.cell_to_latlng(cell_hex)
            centroids.append({"h3_cell": cell, "lat": lat, "lon": lon})
        except Exception:
            continue

    centroid_df = pd.DataFrame(centroids)

    # For each season, find nearest projected grid point
    frames: list[pd.DataFrame] = []
    for season in SEASON_ORDER:
        proj_s = projected[projected["season"] == season]
        static_s = static[static["season"] == season]

        if proj_s.empty or static_s.empty:
            continue

        # Build KDTree on projected grid
        from scipy.spatial import cKDTree

        proj_coords = proj_s[["lat", "lon"]].values
        tree = cKDTree(proj_coords)

        # Find nearest for each H3 centroid
        cell_coords = centroid_df[["lat", "lon"]].values
        _, indices = tree.query(cell_coords)

        # Map projected covariates to cells
        matched = proj_s.iloc[indices][OCEAN_FEATURE_COLS].reset_index(
            drop=True,
        )
        cell_match = centroid_df[["h3_cell"]].reset_index(drop=True)
        cell_match["season"] = season
        for col in OCEAN_FEATURE_COLS:
            cell_match[col] = matched[col].values

        frames.append(cell_match)

    if not frames:
        raise ValueError("No seasonal data matched")

    joined = pd.concat(frames, ignore_index=True)

    # Merge with static features
    result = static.merge(
        joined,
        on=["h3_cell", "season"],
        how="left",
    )

    # Fill missing ocean covariates with median (same as existing
    # pipeline — ~49% of cells lack covariate data)
    n_missing = result[OCEAN_FEATURE_COLS[0]].isna().sum()
    pct = 100 * n_missing / len(result)
    if n_missing > 0:
        log.info(
            "Filling %s rows (%.1f%%) with median covariates",
            f"{n_missing:,}",
            pct,
        )
        for col in OCEAN_FEATURE_COLS:
            median_val = result[col].median()
            result[col] = result[col].fillna(median_val)

    return result


def score_projections(
    *,
    scenarios: list[str] | None = None,
    decades: list[str] | None = None,
    force: bool = False,
) -> list[Path]:
    """Score all species under projected climate conditions.

    Returns:
        List of saved parquet file paths.
    """
    scenarios = scenarios or CMIP6_SCENARIOS
    decades = decades or CMIP6_DECADES

    # Load models
    models = _load_trained_models()
    if not models:
        raise RuntimeError("No trained models found")

    # Load static features once
    static = _load_static_features()

    SDM_PROJECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    for scenario in scenarios:
        for decade in decades:
            log.info(
                "=" * 60,
            )
            log.info("Scoring: %s / %s", scenario, decade)
            log.info("=" * 60)

            # Load projected covariates
            projected = _load_projected_covariates(scenario, decade)

            # Join to H3 grid
            feature_df = _spatial_join_covariates(static, projected)

            log.info(
                "Feature matrix: %s rows × %d cols",
                f"{len(feature_df):,}",
                len(feature_df.columns),
            )

            # Score each target
            for target_col, col_name in SCORE_TARGETS.items():
                if target_col not in models:
                    log.warning(
                        "No model for %s — skip",
                        target_col,
                    )
                    continue

                out_path = (
                    SDM_PROJECTIONS_DIR / f"{col_name}_{scenario}_{decade}"
                    f"_predictions.parquet"
                )

                if out_path.exists() and not force:
                    log.info(
                        "  Already exists: %s — skip",
                        out_path.name,
                    )
                    saved.append(out_path)
                    continue

                model, auc, calibrator = models[target_col]

                # Align features to trained model
                trained_feats = model.get_booster().feature_names
                feature_cols = [
                    c for c in feature_df.columns if c not in ("h3_cell", "season")
                ]
                X = feature_df[feature_cols].copy()
                X = X.reindex(
                    columns=trained_feats,
                    fill_value=0,
                )

                # Predict (raw), then apply the item B isotonic calibrator
                # so projected probabilities match the calibrated current
                # OOF scale (consistent methodology — §7).
                probs = model.predict_proba(X)[:, 1]
                if calibrator is not None:
                    probs = apply_calibrator(calibrator, probs)

                result = pd.DataFrame(
                    {
                        "h3_cell": feature_df["h3_cell"].values,
                        "season": feature_df["season"].values,
                        "scenario": scenario,
                        "decade": decade,
                        f"{col_name}_prob": probs,
                    }
                )

                result.to_parquet(out_path, index=False)
                saved.append(out_path)

                log.info(
                    "  %s: mean=%.4f, median=%.4f, >0.5=%s cells (%.1f%%)",
                    col_name,
                    probs.mean(),
                    np.median(probs),
                    f"{(probs > 0.5).sum():,}",
                    100 * (probs > 0.5).mean(),
                )

    # ── Summary comparison ──────────────────────────────────
    log.info("")
    log.info("=" * 60)
    log.info("Projection scoring complete ✅")
    log.info("Saved %d prediction files to %s", len(saved), SDM_PROJECTIONS_DIR)

    # Compare baseline (current) vs projected for any_whale
    _print_comparison_summary(saved)

    return saved


def _print_comparison_summary(saved_paths: list[Path]) -> None:
    """Print a summary comparing baseline and projected predictions."""
    from pipeline.config import SDM_PREDICTIONS_DIR

    baseline_path = SDM_PREDICTIONS_DIR / "sdm_any_whale_predictions.parquet"
    if not baseline_path.exists():
        log.info(
            "(Baseline predictions not found — skip comparison)",
        )
        return

    baseline = pd.read_parquet(baseline_path)
    baseline_mean = baseline["sdm_any_whale_prob"].mean()
    baseline_high = (baseline["sdm_any_whale_prob"] > 0.5).mean()

    log.info("")
    log.info("--- Habitat shift comparison (any whale) ---")
    log.info(
        "  Baseline (current): mean=%.4f, >0.5=%.1f%%",
        baseline_mean,
        100 * baseline_high,
    )

    for path in sorted(saved_paths):
        if "sdm_any_whale" not in path.name:
            continue
        df = pd.read_parquet(path)
        prob_col = [c for c in df.columns if c.endswith("_prob")][0]
        mean_p = df[prob_col].mean()
        high_p = (df[prob_col] > 0.5).mean()
        parts = path.stem.replace("sdm_any_whale_", "").replace("_predictions", "")
        log.info(
            "  %s: mean=%.4f (%+.4f), >0.5=%.1f%% (%+.1f%%)",
            parts,
            mean_p,
            mean_p - baseline_mean,
            100 * high_p,
            100 * (high_p - baseline_high),
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Score seasonal SDMs on CMIP6 projections",
    )
    parser.add_argument(
        "--scenario",
        choices=CMIP6_SCENARIOS,
        help="Score only this scenario (default: all)",
    )
    parser.add_argument(
        "--decade",
        choices=CMIP6_DECADES,
        help="Score only this decade (default: all)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-score even if output files exist",
    )
    args = parser.parse_args()

    score_projections(
        scenarios=[args.scenario] if args.scenario else None,
        decades=[args.decade] if args.decade else None,
        force=args.force,
    )

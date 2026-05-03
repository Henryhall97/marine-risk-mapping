"""Score trained ISDM models on CMIP6-projected covariates.

Loads the trained ISDM XGBoost models (from MLflow file store)
and scores the full H3 grid under projected future ocean conditions
(SSP2-4.5 and SSP5-8.5 × 2030s–2080s).

ISDM models use only 7 environmental covariates — no season
indicators.  But we still score per-season because ocean
covariates (SST, MLD, SLA, PP) vary seasonally.

For each (scenario, decade, season, species) combination:
1. Load projected ocean covariates from cmip6_projections.parquet
2. Join with static bathymetry (depth_m, depth_range_m) from the
   seasonal SDM features parquet
3. Build 7-column feature matrix matching ISDM training
4. Predict whale habitat probability for all H3 cells
5. Save results to isdm_projections/ directory

Output grain: (h3_cell, season, scenario, decade) — one parquet
per species per scenario per decade.

Usage::

    # Score all species × scenarios × decades:
    uv run python pipeline/analysis/score_future_isdm.py

    # Score only one scenario:
    uv run python pipeline/analysis/score_future_isdm.py \\
        --scenario ssp585

    # Score only one decade:
    uv run python pipeline/analysis/score_future_isdm.py \\
        --decade 2080s

    # Force re-score even if outputs exist:
    uv run python pipeline/analysis/score_future_isdm.py --force
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from pipeline.config import (
    CMIP6_DECADES,
    CMIP6_PROJECTIONS_FILE,
    CMIP6_SCENARIOS,
    ISDM_PROJECTIONS_DIR,
    MLRUNS_DIR,
    SDM_SEASONAL_FEATURES_FILE,
    SEASON_ORDER,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# ISDM species → output column name mapping
ISDM_SPECIES = {
    "blue_whale": "isdm_blue_whale",
    "fin_whale": "isdm_fin_whale",
    "humpback_whale": "isdm_humpback_whale",
    "sperm_whale": "isdm_sperm_whale",
}

# ISDM feature columns (7 environmental covariates, no season one-hots)
ISDM_FEATURE_COLS = [
    "sst",
    "sst_sd",
    "mld",
    "sla",
    "pp_upper_200m",
    "depth_m",
    "depth_range_m",
]

# Subset: static (bathymetry) vs projected (ocean)
STATIC_COLS = ["depth_m", "depth_range_m"]
OCEAN_COLS = ["sst", "sst_sd", "mld", "sla", "pp_upper_200m"]

# MLflow experiment ID for isdm_species_sdm
ISDM_EXPERIMENT_ID = "157334876467526577"


def _load_trained_models() -> dict[str, tuple[xgb.XGBClassifier, float]]:
    """Load trained ISDM XGBoost models from MLflow file store.

    Scans the ISDM experiment directory for the best model per
    species.

    Returns
    -------
    dict
        species → (model, auc)
    """
    exp_dir = MLRUNS_DIR / ISDM_EXPERIMENT_ID
    if not exp_dir.exists():
        raise RuntimeError(
            f"ISDM experiment not found: {exp_dir}. "
            "Train ISDM models first: "
            "uv run python pipeline/analysis/"
            "train_isdm_model.py --score-grid"
        )

    run_map: dict[str, tuple[str, str, float]] = {}

    # Search regular run directories
    for run_dir in exp_dir.iterdir():
        if not run_dir.is_dir() or run_dir.name == "models":
            continue
        param_file = run_dir / "params" / "species"
        if not param_file.exists():
            continue
        species = param_file.read_text().strip()

        # Find model artifact
        model_path = None
        for candidate in [
            run_dir / "artifacts" / "model" / "model.ubj",
            run_dir / "artifacts" / "model.ubj",
        ]:
            if candidate.exists():
                model_path = str(candidate)
                break

        if model_path is None:
            continue

        # Read AUC metric
        auc = 0.0
        auc_file = run_dir / "metrics" / "cv_roc_auc_mean"
        if auc_file.exists():
            try:
                parts = auc_file.read_text().strip().split()
                auc = float(parts[1]) if len(parts) >= 2 else 0.0
            except (ValueError, IndexError):
                pass

        if species not in run_map or auc > run_map[species][2]:
            run_map[species] = (run_dir.name, model_path, auc)

    # Also check registered-model directories (models/m-*/)
    models_dir = exp_dir / "models"
    if models_dir.is_dir():
        for model_dir in models_dir.iterdir():
            if not model_dir.is_dir():
                continue
            param_file = model_dir / "params" / "species"
            if not param_file.exists():
                continue
            species = param_file.read_text().strip()

            model_path = None
            for candidate in [
                model_dir / "artifacts" / "model" / "model.ubj",
                model_dir / "artifacts" / "model.ubj",
            ]:
                if candidate.exists():
                    model_path = str(candidate)
                    break

            if model_path is None:
                continue

            auc = 0.0
            auc_file = model_dir / "metrics" / "cv_roc_auc_mean"
            if auc_file.exists():
                try:
                    parts = auc_file.read_text().strip().split()
                    auc = float(parts[1]) if len(parts) >= 2 else 0.0
                except (ValueError, IndexError):
                    pass

            if species not in run_map or auc > run_map[species][2]:
                run_map[species] = (
                    model_dir.name,
                    model_path,
                    auc,
                )

    models: dict[str, tuple[xgb.XGBClassifier, float]] = {}
    for species, (run_id, model_path, auc) in run_map.items():
        if species not in ISDM_SPECIES:
            log.debug("Skipping unknown species: %s", species)
            continue
        m = xgb.XGBClassifier()
        m.load_model(model_path)
        models[species] = (m, auc)
        log.info(
            "Loaded ISDM model: %s (run=%s, AUC=%.4f)",
            species,
            run_id[:8],
            auc,
        )

    return models


def _load_static_features() -> pd.DataFrame:
    """Load static bathymetry features per (h3_cell, season).

    Extracts h3_cell + season + depth_m + depth_range_m from the
    seasonal SDM features parquet.
    """
    if not SDM_SEASONAL_FEATURES_FILE.exists():
        raise RuntimeError(
            f"Seasonal features not found: "
            f"{SDM_SEASONAL_FEATURES_FILE}. "
            f"Run: uv run python "
            f"pipeline/analysis/extract_features.py "
            f"--dataset seasonal"
        )

    log.info("Loading static features from seasonal parquet…")
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
        raise ValueError("Cannot determine season from features")

    keep = ["h3_cell", "season"] + [c for c in STATIC_COLS if c in df.columns]
    df = df[keep].drop_duplicates(subset=["h3_cell", "season"])

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
    """Load projected ocean covariates for one scenario/decade."""
    if not CMIP6_PROJECTIONS_FILE.exists():
        raise RuntimeError(
            f"CMIP6 projections not found: "
            f"{CMIP6_PROJECTIONS_FILE}. Run: uv run python "
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

    Same KDTree nearest-neighbour approach as score_future_sdm.py.
    """
    import h3
    from scipy.spatial import cKDTree

    # Compute H3 centroids
    unique_cells = static["h3_cell"].unique()
    log.info(
        "Computing centroids for %s H3 cells…",
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

        proj_coords = proj_s[["lat", "lon"]].values
        tree = cKDTree(proj_coords)

        cell_coords = centroid_df[["lat", "lon"]].values
        _, indices = tree.query(cell_coords)

        matched = proj_s.iloc[indices][OCEAN_COLS].reset_index(
            drop=True,
        )
        cell_match = centroid_df[["h3_cell"]].reset_index(
            drop=True,
        )
        cell_match["season"] = season
        for col in OCEAN_COLS:
            cell_match[col] = matched[col].values

        frames.append(cell_match)

    if not frames:
        raise ValueError("No seasonal data matched")

    joined = pd.concat(frames, ignore_index=True)

    # Merge with static bathymetry
    result = static.merge(
        joined,
        on=["h3_cell", "season"],
        how="left",
    )

    # Fill missing ocean covariates with median (~49% expected)
    n_missing = result[OCEAN_COLS[0]].isna().sum()
    pct = 100 * n_missing / len(result)
    if n_missing > 0:
        log.info(
            "Filling %s rows (%.1f%%) with median covariates",
            f"{n_missing:,}",
            pct,
        )
        for col in OCEAN_COLS:
            result[col] = result[col].fillna(result[col].median())

    return result


def score_projections(
    *,
    scenarios: list[str] | None = None,
    decades: list[str] | None = None,
    force: bool = False,
) -> list[Path]:
    """Score all ISDM species under projected climate conditions.

    Returns
    -------
    list[Path]
        Saved parquet file paths.
    """
    scenarios = scenarios or CMIP6_SCENARIOS
    decades = decades or CMIP6_DECADES

    models = _load_trained_models()
    if not models:
        raise RuntimeError(
            "No trained ISDM models found. "
            "Run: uv run python "
            "pipeline/analysis/train_isdm_model.py"
        )

    log.info(
        "Loaded %d ISDM models: %s",
        len(models),
        list(models.keys()),
    )

    static = _load_static_features()
    ISDM_PROJECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    for scenario in scenarios:
        for decade in decades:
            log.info("=" * 60)
            log.info("Scoring ISDM: %s / %s", scenario, decade)
            log.info("=" * 60)

            projected = _load_projected_covariates(scenario, decade)
            feature_df = _spatial_join_covariates(static, projected)

            log.info(
                "Feature matrix: %s rows × %d cols",
                f"{len(feature_df):,}",
                len(feature_df.columns),
            )

            for species, col_name in ISDM_SPECIES.items():
                if species not in models:
                    log.warning("No model for %s — skip", species)
                    continue

                out_path = (
                    ISDM_PROJECTIONS_DIR / f"{col_name}_{scenario}_{decade}"
                    f"_predictions.parquet"
                )

                if out_path.exists() and not force:
                    log.info(
                        "  Already exists: %s — skip",
                        out_path.name,
                    )
                    saved.append(out_path)
                    continue

                model, auc = models[species]

                # ISDM uses exactly 7 features — align columns
                X = feature_df[ISDM_FEATURE_COLS].copy()

                # Fill any remaining NaN with median
                for col in ISDM_FEATURE_COLS:
                    if X[col].isna().any():
                        X[col] = X[col].fillna(X[col].median())

                probs = model.predict_proba(X)[:, 1]

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

    # Summary
    log.info("")
    log.info("=" * 60)
    log.info("ISDM projection scoring complete ✅")
    log.info(
        "Saved %d prediction files to %s",
        len(saved),
        ISDM_PROJECTIONS_DIR,
    )

    _print_comparison_summary(saved)
    return saved


def _print_comparison_summary(saved_paths: list[Path]) -> None:
    """Compare baseline (current) vs projected ISDM predictions."""
    from pipeline.config import ML_DIR

    predictions_dir = ML_DIR / "isdm_predictions"

    for species, col_name in ISDM_SPECIES.items():
        baseline_path = predictions_dir / f"{col_name}_predictions.parquet"
        if not baseline_path.exists():
            continue

        baseline = pd.read_parquet(baseline_path)
        prob_col = f"{col_name}_prob"
        if prob_col not in baseline.columns:
            continue

        baseline_mean = baseline[prob_col].mean()
        baseline_high = (baseline[prob_col] > 0.5).mean()

        log.info("")
        log.info("--- Habitat shift: %s (ISDM) ---", species)
        log.info(
            "  Baseline (current): mean=%.4f, >0.5=%.1f%%",
            baseline_mean,
            100 * baseline_high,
        )

        for path in sorted(saved_paths):
            if col_name not in path.name:
                continue
            df = pd.read_parquet(path)
            pcol = [c for c in df.columns if c.endswith("_prob")][0]
            mean_p = df[pcol].mean()
            high_p = (df[pcol] > 0.5).mean()
            parts = path.stem.replace(f"{col_name}_", "").replace("_predictions", "")
            log.info(
                "  %s: mean=%.4f (%+.4f), >0.5=%.1f%% (%+.1f%%)",
                parts,
                mean_p,
                mean_p - baseline_mean,
                100 * high_p,
                100 * (high_p - baseline_high),
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Score ISDM models on CMIP6 climate projections"),
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
        scenarios=([args.scenario] if args.scenario else None),
        decades=[args.decade] if args.decade else None,
        force=args.force,
    )

"""Train a seasonal whale SDM with species-switchable targets.

Extends the static SDM to incorporate seasonal environmental variation.
The model learns P(species_present | environment, season) using
season-varying ocean covariates and speed zone coverage alongside
static features (bathymetry, proximity, MPA).

Key design decisions:
  - Spatial block CV (same cell → same fold across all 4 seasons)
  - Season as one-hot features (not ordinal — winter wraps)
  - Traffic features excluded (detection bias: survey effort ∝ traffic)
  - Whale proximity excluded (target leakage)
  - Nisi per-species risk cols excluded from features (validation only)
  - Species-switchable: --target right_whale_present, etc.
  - Per-season AUC breakdown in evaluation

Usage:
    uv run python pipeline/analysis/train_sdm_seasonal.py
    uv run python pipeline/analysis/train_sdm_seasonal.py --tune
    uv run python pipeline/analysis/train_sdm_seasonal.py \
        --target right_whale_present
    uv run python pipeline/analysis/train_sdm_seasonal.py \
        --target humpback_present --tune
"""

import argparse
import logging
import warnings

import matplotlib
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import optuna
import pandas as pd
import shap
import xgboost as xgb
from sklearn.metrics import roc_auc_score

from pipeline.analysis.evaluate import (
    compute_binary_metrics,
    plot_calibration,
    plot_feature_importance,
    plot_roc_pr_curves,
    spatial_cv_split,
)
from pipeline.analysis.extract_features import extract_sdm_seasonal_features
from pipeline.config import ML_DIR, MLFLOW_TRACKING_URI, SDM_SEASONAL_FEATURES_FILE
from pipeline.utils import patch_shap_for_xgboost3

warnings.filterwarnings("ignore", category=UserWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────
EXPERIMENT_NAME = "whale_sdm_seasonal"
ARTIFACTS_DIR = ML_DIR / "artifacts" / "sdm_seasonal"

# Available target columns (any can be passed via --target)
VALID_TARGETS = [
    "whale_present",
    "right_whale_present",
    "humpback_present",
    "fin_whale_present",
    "blue_whale_present",
    "sperm_whale_present",
    "minke_whale_present",
]

# Columns to EXCLUDE from features
# - Identifiers and spatial block info
# - All target columns (even the ones we're not predicting)
# - Validation benchmarks (Nisi per-species risk)
# - Sighting counts (encodes the target differently)
NON_FEATURE_COLS = {
    # Identifiers
    "h3_cell",
    "cell_lat",
    "cell_lon",
    "spatial_block",
    "cv_fold",
    # All possible targets
    "whale_present",
    "right_whale_present",
    "humpback_present",
    "fin_whale_present",
    "blue_whale_present",
    "sperm_whale_present",
    "minke_whale_present",
    # Sighting counts — these directly encode the target
    "total_sightings",
    "unique_species",
    "baleen_whale_sightings",
    "recent_sightings",
    # Nisi reference — model outputs, not independent data.
    # Kept in parquet for post-hoc comparison only.
    "nisi_all_risk",
    "nisi_shipping_index",
    "nisi_whale_space_use",
    "nisi_hotspot_overlap",
    # Nisi per-species risk — validation benchmarks
    "nisi_blue_risk",
    "nisi_fin_risk",
    "nisi_humpback_risk",
    "nisi_sperm_risk",
    # Ship proximity — detection bias (observations ∝ ship presence)
    "dist_to_nearest_ship_km",
    "ship_proximity_score",
    # Speed zones — circular for SDM (zones placed where whales are)
    "in_speed_zone",
    "in_current_sma",
    # MPA/protection — policy decisions, not environmental conditions
    "mpa_count",
    "has_strict_protection",
    "dist_to_nearest_protection_km",
    "protection_proximity_score",
}

DEFAULT_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "tree_method": "hist",
    "max_depth": 6,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "gamma": 0.5,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
}

EARLY_STOPPING_ROUNDS = 50

# Season columns for per-season evaluation
SEASON_INDICATORS = [
    "season_winter",
    "season_spring",
    "season_summer",
    "season_fall",
]


# ── Helpers ─────────────────────────────────────────────────


def _get_feature_cols(df: pd.DataFrame) -> list[str]:
    """Return sorted list of feature columns (everything except non-features)."""
    return sorted(set(df.columns) - NON_FEATURE_COLS)


def _compute_scale_pos_weight(y: pd.Series) -> float:
    """Compute class imbalance weight for XGBoost."""
    n_neg = int((y == 0).sum())
    n_pos = int((y == 1).sum())
    return float(n_neg / max(n_pos, 1))


def _identify_season(row: pd.Series) -> str:
    """Recover the season name from one-hot columns for reporting."""
    for s in SEASON_INDICATORS:
        if s in row.index and row[s] == 1:
            return s.replace("season_", "")
    return "unknown"


def _per_season_auc(
    df: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, float]:
    """Compute AUC-ROC for each season separately."""
    season_auc = {}
    for season_col in SEASON_INDICATORS:
        if season_col not in df.columns:
            continue
        mask = df[season_col].values == 1
        if mask.sum() == 0:
            continue
        y_s = y_true[mask]
        p_s = y_pred[mask]
        if len(np.unique(y_s)) < 2:
            season_auc[season_col.replace("season_", "")] = float("nan")
        else:
            season_auc[season_col.replace("season_", "")] = float(
                roc_auc_score(y_s, p_s)
            )
    return season_auc


# ── Training ────────────────────────────────────────────────


def train_single_model(
    df: pd.DataFrame,
    target_col: str = "whale_present",
    params: dict | None = None,
    log_to_mlflow: bool = True,
) -> tuple[xgb.XGBClassifier, dict]:
    """Train one XGBoost SDM with spatial block CV."""
    params = params or DEFAULT_PARAMS.copy()
    feature_cols = _get_feature_cols(df)

    X = df[feature_cols]
    y = df[target_col].astype(float)

    scale_pos_weight = _compute_scale_pos_weight(y)
    params["scale_pos_weight"] = scale_pos_weight
    n_pos = int(y.sum())
    n_neg = int((y == 0).sum())

    log.info("Target: %s", target_col)
    log.info("Features: %d columns", len(feature_cols))
    log.info("Samples: %d pos / %d neg (weight=%.2f)", n_pos, n_neg, scale_pos_weight)

    # ── Spatial block CV ────────────────────────────────
    fold_metrics = []
    oof_preds = np.full(len(df), np.nan)
    best_iterations = []

    for fold_idx, (train_idx, val_idx) in enumerate(spatial_cv_split(df)):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        model = xgb.XGBClassifier(
            **params,
            early_stopping_rounds=EARLY_STOPPING_ROUNDS,
        )
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
        best_iterations.append(model.best_iteration + 1)

        y_prob = model.predict_proba(X_val)[:, 1]
        oof_preds[val_idx] = y_prob

        fold_m = compute_binary_metrics(y_val.values, y_prob)
        fold_m["fold"] = fold_idx
        fold_metrics.append(fold_m)

        # Per-season AUC for this fold
        season_auc = _per_season_auc(df.iloc[val_idx], y_val.values, y_prob)
        season_str = "  ".join(f"{s}={a:.4f}" for s, a in season_auc.items())

        log.info(
            "  Fold %d: AUC=%.4f  AP=%.4f  |  %s",
            fold_idx,
            fold_m["roc_auc"],
            fold_m["avg_precision"],
            season_str,
        )

    # ── Aggregate CV metrics ────────────────────────────
    cv_df = pd.DataFrame(fold_metrics)
    cv_metrics = {
        "cv_roc_auc_mean": float(cv_df["roc_auc"].mean()),
        "cv_roc_auc_std": float(cv_df["roc_auc"].std()),
        "cv_avg_precision_mean": float(cv_df["avg_precision"].mean()),
        "cv_avg_precision_std": float(cv_df["avg_precision"].std()),
        "cv_log_loss_mean": float(cv_df["log_loss"].mean()),
        "cv_f1_mean": float(cv_df["f1"].mean()),
    }

    # OOF aggregate metrics
    oof_mask = ~np.isnan(oof_preds)
    oof_metrics = compute_binary_metrics(y.values[oof_mask], oof_preds[oof_mask])
    cv_metrics["oof_roc_auc"] = oof_metrics["roc_auc"]
    cv_metrics["oof_avg_precision"] = oof_metrics["avg_precision"]

    # OOF per-season AUC
    season_auc = _per_season_auc(
        df[oof_mask],
        y.values[oof_mask],
        oof_preds[oof_mask],
    )
    for season, auc in season_auc.items():
        cv_metrics[f"oof_auc_{season}"] = auc

    log.info(
        "CV: AUC=%.4f±%.4f  AP=%.4f±%.4f",
        cv_metrics["cv_roc_auc_mean"],
        cv_metrics["cv_roc_auc_std"],
        cv_metrics["cv_avg_precision_mean"],
        cv_metrics["cv_avg_precision_std"],
    )
    for season, auc in season_auc.items():
        log.info("  %s AUC: %.4f", season, auc)

    # ── Final model on all data ─────────────────────────
    avg_iters = max(int(np.mean(best_iterations)), 100)
    final_params = {k: v for k, v in params.items() if k != "early_stopping_rounds"}
    final_params["n_estimators"] = avg_iters
    final_model = xgb.XGBClassifier(**final_params)
    final_model.fit(X, y, verbose=False)

    # ── Feature importance ──────────────────────────────
    importance = pd.Series(
        final_model.feature_importances_,
        index=feature_cols,
    ).sort_values(ascending=False)

    # ── MLflow logging ──────────────────────────────────
    if log_to_mlflow:
        target_short = target_col.replace("_present", "")
        art_dir = ARTIFACTS_DIR / target_short
        art_dir.mkdir(parents=True, exist_ok=True)

        mlflow.log_params({k: v for k, v in params.items() if k != "scale_pos_weight"})
        mlflow.log_param("scale_pos_weight", round(scale_pos_weight, 2))
        mlflow.log_param("target_col", target_col)
        mlflow.log_param("n_features", len(feature_cols))
        mlflow.log_param("n_samples", len(df))
        mlflow.log_param("n_positives", n_pos)
        mlflow.log_param("n_seasons", 4)
        mlflow.log_param("cv_method", "spatial_block")
        mlflow.log_param("final_n_estimators", avg_iters)
        mlflow.log_metrics(cv_metrics)

        # Feature list for reproducibility
        feat_list_path = art_dir / "feature_columns.txt"
        feat_list_path.write_text("\n".join(feature_cols))
        mlflow.log_artifact(str(feat_list_path))

        # ROC / PR curves
        roc_path = art_dir / "roc_pr_curves.png"
        plot_roc_pr_curves(
            y.values[oof_mask],
            oof_preds[oof_mask],
            title_prefix=f"Seasonal SDM ({target_short}) — ",
            save_path=roc_path,
        )
        mlflow.log_artifact(str(roc_path))

        # Calibration
        cal_path = art_dir / "calibration.png"
        plot_calibration(
            y.values[oof_mask],
            oof_preds[oof_mask],
            title_prefix=f"Seasonal SDM ({target_short}) — ",
            save_path=cal_path,
        )
        mlflow.log_artifact(str(cal_path))

        # Feature importance
        imp_path = art_dir / "feature_importance.png"
        plot_feature_importance(
            importance,
            top_n=30,
            title=f"Seasonal SDM ({target_short}) — Feature Importance",
            save_path=imp_path,
        )
        mlflow.log_artifact(str(imp_path))

        imp_csv_path = art_dir / "feature_importance.csv"
        importance.to_csv(imp_csv_path, header=["importance"])
        mlflow.log_artifact(str(imp_csv_path))

        # Per-season AUC bar chart
        if season_auc:
            _plot_season_auc(season_auc, target_short, art_dir)
            mlflow.log_artifact(str(art_dir / "season_auc.png"))

        # Model artifact
        mlflow.xgboost.log_model(
            final_model,
            artifact_path="model",
            input_example=X.head(5),
        )

        # SHAP
        log.info("Computing SHAP values…")
        sample_size = min(10_000, len(X))
        sample_idx = np.random.RandomState(42).choice(
            len(X),
            size=sample_size,
            replace=False,
        )
        booster = final_model.get_booster()
        patch_shap_for_xgboost3()
        explainer = shap.TreeExplainer(booster)
        shap_values = explainer.shap_values(X.iloc[sample_idx])

        shap_path = art_dir / "shap_summary.png"
        plt.figure(figsize=(12, 8))
        shap.summary_plot(shap_values, X.iloc[sample_idx], show=False)
        plt.tight_layout()
        plt.savefig(shap_path, dpi=150, bbox_inches="tight")
        plt.close()
        mlflow.log_artifact(str(shap_path))

    return final_model, cv_metrics


# ── Season AUC visualisation ───────────────────────────────


def _plot_season_auc(
    season_auc: dict[str, float],
    target_short: str,
    save_dir,
) -> None:
    """Bar chart of per-season AUC-ROC."""
    order = ["winter", "spring", "summer", "fall"]
    seasons = [s for s in order if s in season_auc]
    aucs = [season_auc[s] for s in seasons]

    fig, ax = plt.subplots(figsize=(6, 4))
    colours = ["#4a90d9", "#7bc47f", "#e6c300", "#d97b4a"]
    bars = ax.bar(seasons, aucs, color=colours[: len(seasons)], edgecolor="white")

    for bar, auc in zip(bars, aucs, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.005,
            f"{auc:.3f}",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    ax.set_ylim(0.5, 1.0)
    ax.set_ylabel("AUC-ROC")
    ax.set_title(f"Seasonal SDM ({target_short}) — AUC by Season")
    ax.axhline(y=0.5, color="grey", linestyle="--", alpha=0.5, label="Random")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(save_dir / "season_auc.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Optuna tuning ───────────────────────────────────────────


def _optuna_objective(trial, df, target_col, feature_cols):
    """Optuna objective: spatial CV AUC-ROC."""
    X = df[feature_cols]
    y = df[target_col].astype(float)

    params = {
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "tree_method": "hist",
        "scale_pos_weight": _compute_scale_pos_weight(y),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 200, 1000),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 30),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
        "gamma": trial.suggest_float("gamma", 0.0, 5.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        "random_state": 42,
    }

    auc_scores = []
    for train_idx, val_idx in spatial_cv_split(df):
        model = xgb.XGBClassifier(
            **params,
            early_stopping_rounds=EARLY_STOPPING_ROUNDS,
        )
        model.fit(
            X.iloc[train_idx],
            y.iloc[train_idx],
            eval_set=[(X.iloc[val_idx], y.iloc[val_idx])],
            verbose=False,
        )
        y_prob = model.predict_proba(X.iloc[val_idx])[:, 1]
        auc_scores.append(roc_auc_score(y.iloc[val_idx], y_prob))

    return float(np.mean(auc_scores))


def tune_hyperparameters(
    df: pd.DataFrame,
    target_col: str = "whale_present",
    n_trials: int = 50,
) -> dict:
    """Run Optuna HP search, return best params."""
    feature_cols = _get_feature_cols(df)

    study = optuna.create_study(
        direction="maximize",
        study_name=f"seasonal_sdm_{target_col}_tuning",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    study.optimize(
        lambda trial: _optuna_objective(trial, df, target_col, feature_cols),
        n_trials=n_trials,
        show_progress_bar=True,
    )

    log.info(
        "Best trial: AUC=%.4f  params=%s",
        study.best_value,
        study.best_params,
    )

    best_params = DEFAULT_PARAMS.copy()
    best_params.update(study.best_params)

    mlflow.log_param("optuna_n_trials", n_trials)
    mlflow.log_param("optuna_best_auc", round(study.best_value, 4))
    mlflow.log_params({f"best_{k}": v for k, v in study.best_params.items()})

    return best_params


# ── Main ────────────────────────────────────────────────────


def main(
    target_col: str = "whale_present",
    tune: bool = False,
    n_trials: int = 50,
) -> None:
    """Load data, optionally tune, train, evaluate, log."""
    matplotlib.use("Agg")

    # ── Load / cache features ───────────────────────────
    if SDM_SEASONAL_FEATURES_FILE.exists():
        log.info("Loading cached features: %s", SDM_SEASONAL_FEATURES_FILE)
        df = pd.read_parquet(SDM_SEASONAL_FEATURES_FILE)
    else:
        log.info("Extracting seasonal features from PostGIS…")
        df = extract_sdm_seasonal_features()
        ML_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(SDM_SEASONAL_FEATURES_FILE, index=False)
        log.info("Saved: %s", SDM_SEASONAL_FEATURES_FILE)

    # Validate target
    if target_col not in df.columns:
        raise ValueError(
            f"Target '{target_col}' not found. Available: "
            f"{[c for c in VALID_TARGETS if c in df.columns]}"
        )

    n_pos = int(df[target_col].sum())
    n_tot = len(df)
    log.info(
        "Target '%s': %d positives out of %d (%.2f%%)",
        target_col,
        n_pos,
        n_tot,
        100 * n_pos / n_tot,
    )

    if n_pos < 100:
        log.warning(
            "Very few positives (%d) — model may be unreliable. "
            "Consider using whale_present (aggregate) instead.",
            n_pos,
        )

    # ── MLflow setup ────────────────────────────────────
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    target_short = target_col.replace("_present", "")
    with mlflow.start_run(run_name=f"seasonal_{target_short}"):
        mlflow.set_tag("model_type", "xgboost")
        mlflow.set_tag("data_source", "obis_seasonal")
        mlflow.set_tag("target", target_col)

        if tune:
            log.info("Running Optuna HP search (%d trials)…", n_trials)
            mlflow.set_tag("tuned", "true")
            best_params = tune_hyperparameters(df, target_col, n_trials)
        else:
            mlflow.set_tag("tuned", "false")
            best_params = None

        model, metrics = train_single_model(
            df,
            target_col=target_col,
            params=best_params,
            log_to_mlflow=True,
        )

    log.info("Done. Final AUC: %.4f", metrics["cv_roc_auc_mean"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train seasonal whale SDM")
    parser.add_argument(
        "--target",
        type=str,
        default="whale_present",
        choices=VALID_TARGETS,
        help="Target column to predict (default: whale_present)",
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="Run Optuna hyperparameter search",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=50,
        help="Number of Optuna trials (default: 50)",
    )
    args = parser.parse_args()
    main(target_col=args.target, tune=args.tune, n_trials=args.n_trials)

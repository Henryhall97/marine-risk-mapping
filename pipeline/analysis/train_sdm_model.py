"""Train a whale species distribution model (SDM) with MLflow tracking.

Trains an XGBoost binary classifier to predict cetacean presence
across H3 cells. Less imbalanced than the strike model (~4% positive
rate vs 0.004%), allowing more standard classification approaches.

Key design decisions:
  - Spatial block CV (same as strike model) for honest evaluation
  - Moderate class imbalance handled via scale_pos_weight
  - AUC-ROC as primary metric (AP also tracked)
  - Optuna for Bayesian hyperparameter search
  - MLflow logs params, metrics, plots, and model artifact

Usage:
    uv run python pipeline/analysis/train_sdm_model.py
    uv run python pipeline/analysis/train_sdm_model.py --tune
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
from pipeline.analysis.extract_features import extract_sdm_features
from pipeline.config import ML_DIR, MLFLOW_TRACKING_URI, SDM_FEATURES_FILE
from pipeline.utils import patch_shap_for_xgboost3

warnings.filterwarnings("ignore", category=UserWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ── MLflow config ───────────────────────────────────────────
EXPERIMENT_NAME = "whale_sdm"
ARTIFACTS_DIR = ML_DIR / "artifacts" / "sdm"

# ── Feature columns ────────────────────────────────────────
NON_FEATURE_COLS = {
    # Identifiers
    "h3_cell",
    "cell_lat",
    "cell_lon",
    "spatial_block",
    "cv_fold",
    "is_land",
    # All possible targets
    "whale_present",
    "right_whale_present",
    "humpback_present",
    "fin_whale_present",
    "blue_whale_present",
    "sperm_whale_present",
    "minke_whale_present",
    # Sighting counts — directly encode the target
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

TARGET_COL = "whale_present"


def _get_feature_cols(df: pd.DataFrame) -> list[str]:
    """Return feature column names."""
    return sorted(c for c in df.columns if c not in NON_FEATURE_COLS)


# ── Default hyperparameters ─────────────────────────────────
EARLY_STOPPING_ROUNDS = 50

DEFAULT_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "tree_method": "hist",
    "max_depth": 6,
    "learning_rate": 0.05,
    "n_estimators": 1000,
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "gamma": 0.5,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
}


def _compute_scale_pos_weight(y: pd.Series) -> float:
    """Compute XGBoost scale_pos_weight for class imbalance."""
    n_neg = (y == 0).sum()
    n_pos = (y == 1).sum()
    return float(n_neg / max(n_pos, 1))


def train_single_model(
    df: pd.DataFrame,
    params: dict | None = None,
    log_to_mlflow: bool = True,
) -> tuple[xgb.XGBClassifier, dict]:
    """Train a single XGBoost SDM with spatial CV evaluation."""
    params = params or DEFAULT_PARAMS.copy()
    feature_cols = _get_feature_cols(df)
    X = df[feature_cols]
    y = df[TARGET_COL]

    scale_pos_weight = _compute_scale_pos_weight(y)
    params["scale_pos_weight"] = scale_pos_weight
    log.info(
        "scale_pos_weight = %.1f  (%.0f neg / %d pos)",
        scale_pos_weight,
        (y == 0).sum(),
        (y == 1).sum(),
    )

    # ── Spatial cross-validation ────────────────────────
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
        fold_m["val_positives"] = int(y_val.sum())
        fold_metrics.append(fold_m)

        log.info(
            "  Fold %d: AUC-ROC=%.4f  AP=%.4f  (%d pos / %d val)",
            fold_idx,
            fold_m["roc_auc"],
            fold_m["avg_precision"],
            fold_m["val_positives"],
            len(val_idx),
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

    # Out-of-fold overall metrics
    oof_mask = ~np.isnan(oof_preds)
    oof_metrics = compute_binary_metrics(y.values[oof_mask], oof_preds[oof_mask])
    cv_metrics["oof_roc_auc"] = oof_metrics["roc_auc"]
    cv_metrics["oof_avg_precision"] = oof_metrics["avg_precision"]

    log.info(
        "CV summary: AUC-ROC=%.4f±%.4f  AP=%.4f±%.4f",
        cv_metrics["cv_roc_auc_mean"],
        cv_metrics["cv_roc_auc_std"],
        cv_metrics["cv_avg_precision_mean"],
        cv_metrics["cv_avg_precision_std"],
    )

    # ── Train final model on all data ───────────────────
    avg_iters = max(int(np.mean(best_iterations)), 100)
    final_params = {k: v for k, v in params.items() if k != "early_stopping_rounds"}
    final_params["n_estimators"] = avg_iters
    log.info("Final model: n_estimators=%d (avg CV best)", avg_iters)
    final_model = xgb.XGBClassifier(**final_params)
    final_model.fit(X, y, verbose=False)

    # ── Feature importance ──────────────────────────────
    importance = pd.Series(
        final_model.feature_importances_, index=feature_cols
    ).sort_values(ascending=False)

    # ── MLflow logging ──────────────────────────────────
    if log_to_mlflow:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

        mlflow.log_params({k: v for k, v in params.items() if k != "scale_pos_weight"})
        mlflow.log_param("scale_pos_weight", round(scale_pos_weight, 1))
        mlflow.log_param("n_features", len(feature_cols))
        mlflow.log_param("n_samples", len(df))
        mlflow.log_param("n_positives", int(y.sum()))
        mlflow.log_param("positive_rate", round(float(y.mean()), 6))
        mlflow.log_metrics(cv_metrics)

        # Plots
        roc_pr_path = ARTIFACTS_DIR / "roc_pr_curves.png"
        plot_roc_pr_curves(
            y.values[oof_mask],
            oof_preds[oof_mask],
            title_prefix="Whale SDM — ",
            save_path=roc_pr_path,
        )
        mlflow.log_artifact(str(roc_pr_path))

        cal_path = ARTIFACTS_DIR / "calibration.png"
        plot_calibration(
            y.values[oof_mask],
            oof_preds[oof_mask],
            title_prefix="Whale SDM — ",
            save_path=cal_path,
        )
        mlflow.log_artifact(str(cal_path))

        imp_path = ARTIFACTS_DIR / "feature_importance.png"
        plot_feature_importance(
            importance,
            top_n=25,
            title="Whale SDM — XGBoost Feature Importance",
            save_path=imp_path,
        )
        mlflow.log_artifact(str(imp_path))

        # Save importance CSV
        imp_csv_path = ARTIFACTS_DIR / "feature_importance.csv"
        importance.to_csv(imp_csv_path, header=["importance"])
        mlflow.log_artifact(str(imp_csv_path))

        # Log model
        mlflow.xgboost.log_model(
            final_model,
            artifact_path="model",
            input_example=X.head(5),
        )

        # SHAP summary
        log.info("Computing SHAP values (sampled)…")
        sample_idx = np.random.RandomState(42).choice(
            len(X), size=min(5000, len(X)), replace=False
        )
        X_sample = X.iloc[sample_idx]
        booster = final_model.get_booster()
        patch_shap_for_xgboost3()
        explainer = shap.TreeExplainer(booster)
        shap_values = explainer.shap_values(X_sample)

        shap_path = ARTIFACTS_DIR / "shap_summary.png"
        plt.figure(figsize=(10, 8))
        shap.summary_plot(shap_values, X_sample, show=False, max_display=20)
        plt.tight_layout()
        plt.savefig(shap_path, dpi=150, bbox_inches="tight")
        plt.close()
        mlflow.log_artifact(str(shap_path))
        log.info("SHAP summary saved: %s", shap_path)

    return final_model, cv_metrics


# ── Optuna hyperparameter tuning ────────────────────────────


def _optuna_objective(trial, df, feature_cols):
    """Optuna objective: maximize spatial CV AUC-ROC."""
    y = df[TARGET_COL]
    X = df[feature_cols]
    scale_pos_weight = _compute_scale_pos_weight(y)

    params = {
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "tree_method": "hist",
        "scale_pos_weight": scale_pos_weight,
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
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
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        model = xgb.XGBClassifier(
            **params,
            early_stopping_rounds=EARLY_STOPPING_ROUNDS,
        )
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        y_prob = model.predict_proba(X_val)[:, 1]

        if y_val.sum() > 0:
            auc_scores.append(roc_auc_score(y_val, y_prob))

    return float(np.mean(auc_scores)) if auc_scores else 0.5


def tune_hyperparameters(
    df: pd.DataFrame,
    n_trials: int = 50,
) -> dict:
    """Run Optuna Bayesian HP search, log best to MLflow."""
    feature_cols = _get_feature_cols(df)

    study = optuna.create_study(
        direction="maximize",
        study_name="whale_sdm_tuning",
        sampler=optuna.samplers.TPESampler(seed=42),
    )

    study.optimize(
        lambda trial: _optuna_objective(trial, df, feature_cols),
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


def main(tune: bool = False, n_trials: int = 50) -> None:
    """Run the full SDM training pipeline."""
    matplotlib.use("Agg")

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    # Load features
    if SDM_FEATURES_FILE.exists():
        log.info("Loading cached features: %s", SDM_FEATURES_FILE)
        df = pd.read_parquet(SDM_FEATURES_FILE)
    else:
        log.info("Extracting features from PostGIS…")
        df = extract_sdm_features()
        ML_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(SDM_FEATURES_FILE, index=False)

    log.info("Dataset: %d rows × %d cols", *df.shape)
    log.info(
        "Class balance: %d positive (%.2f%%)",
        df[TARGET_COL].sum(),
        100 * df[TARGET_COL].mean(),
    )

    with mlflow.start_run(run_name="sdm_xgboost"):
        mlflow.set_tag("model_type", "xgboost")
        mlflow.set_tag("target", TARGET_COL)
        mlflow.set_tag("cv_method", "spatial_block")

        if tune:
            log.info("Running Optuna HP search (%d trials)…", n_trials)
            best_params = tune_hyperparameters(df, n_trials=n_trials)
            mlflow.set_tag("tuned", "true")
        else:
            best_params = None
            mlflow.set_tag("tuned", "false")

        model, metrics = train_single_model(df, params=best_params, log_to_mlflow=True)

    log.info("Training complete. Metrics: %s", metrics)
    log.info("MLflow tracking: %s", MLFLOW_TRACKING_URI)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train whale SDM classifier")
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
    main(tune=args.tune, n_trials=args.n_trials)

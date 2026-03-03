"""Train per-species SDMs on Nisi et al. ISDM data with MLflow tracking.

Uses the curated presence/absence datasets from Nisi et al. (2024)
which include sighting, tagging, whaling, and survey data with
environmental covariates. Pre-balanced (~50/50) with expert-generated
pseudo-absences.

Available species: blue whale, fin whale, humpback whale, sperm whale.

After training, scores our H3 grid (via fct_whale_sdm_seasonal) to
produce predicted P(species | environment) for every cell × season,
enabling comparison with our OBIS-trained SDMs and Nisi's published
risk surfaces.

Usage:
    uv run python pipeline/analysis/train_isdm_model.py
    uv run python pipeline/analysis/train_isdm_model.py --tune
    uv run python pipeline/analysis/train_isdm_model.py --species blue_whale
    uv run python pipeline/analysis/train_isdm_model.py --score-grid
"""

import argparse
import logging
import warnings

import matplotlib
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from pipeline.analysis.evaluate import (
    compute_binary_metrics,
    plot_calibration,
    plot_feature_importance,
    plot_roc_pr_curves,
)
from pipeline.config import (
    ML_DIR,
    MLFLOW_TRACKING_URI,
    NISI_ISDM_FILES,
    SDM_SEASONAL_FEATURES_FILE,
)
from pipeline.utils import patch_shap_for_xgboost3

warnings.filterwarnings("ignore", category=UserWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────
EXPERIMENT_NAME = "isdm_species_sdm"
ARTIFACTS_DIR = ML_DIR / "artifacts" / "isdm"
PREDICTIONS_DIR = ML_DIR / "isdm_predictions"

# ISDM covariate columns → our equivalent column names
ISDM_FEATURE_COLS = [
    "sst",
    "sst_sd",
    "mld",
    "sla",
    "PPupper200m",
    "bathy",
    "bathy_sd",
]
OUR_FEATURE_COLS = [
    "sst",
    "sst_sd",
    "mld",
    "sla",
    "pp_upper_200m",
    "depth_m",
    "depth_range_m",
]
ISDM_TO_OURS = dict(zip(ISDM_FEATURE_COLS, OUR_FEATURE_COLS, strict=True))

TARGET_COL = "presence"
N_CV_FOLDS = 5
EARLY_STOPPING_ROUNDS = 50

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


# ── Data loading ────────────────────────────────────────────


def load_isdm_data(species: str) -> pd.DataFrame:
    """Load and clean one ISDM CSV for a given species."""
    path = NISI_ISDM_FILES[species]
    if not path.exists():
        raise FileNotFoundError(f"ISDM file not found: {path}")

    df = pd.read_csv(path)

    # Drop the unnamed index column
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")])

    # Rename covariates to match our naming convention
    df = df.rename(columns=ISDM_TO_OURS)

    # Keep only features + target + metadata
    keep_cols = OUR_FEATURE_COLS + [TARGET_COL, "species", "subpopulation", "data_type"]
    df = df[[c for c in keep_cols if c in df.columns]]

    # Drop rows with missing covariates
    n_before = len(df)
    df = df.dropna(subset=OUR_FEATURE_COLS)
    if len(df) < n_before:
        log.info("  Dropped %d rows with missing covariates", n_before - len(df))

    log.info(
        "Loaded %s: %d rows, %.1f%% positive, %d subpopulations",
        species,
        len(df),
        100 * df[TARGET_COL].mean(),
        df["subpopulation"].nunique() if "subpopulation" in df.columns else 0,
    )
    return df


# ── Training ────────────────────────────────────────────────


def train_species_model(
    df: pd.DataFrame,
    species: str,
    params: dict | None = None,
    log_to_mlflow: bool = True,
) -> tuple[xgb.XGBClassifier, dict]:
    """Train an XGBoost SDM for one species using stratified CV."""
    params = params or DEFAULT_PARAMS.copy()
    feature_cols = OUR_FEATURE_COLS
    X = df[feature_cols].copy()
    y = df[TARGET_COL].copy()

    # ISDM data is pre-balanced, so scale_pos_weight ≈ 1
    n_neg = (y == 0).sum()
    n_pos = (y == 1).sum()
    scale_pos_weight = float(n_neg / max(n_pos, 1))
    params["scale_pos_weight"] = scale_pos_weight

    log.info(
        "%s: %d pos / %d neg (weight=%.2f)",
        species,
        n_pos,
        n_neg,
        scale_pos_weight,
    )

    # ── Stratified CV (no spatial blocks — ISDM has no coords) ──
    skf = StratifiedKFold(n_splits=N_CV_FOLDS, shuffle=True, random_state=42)
    fold_metrics = []
    oof_preds = np.full(len(df), np.nan)
    best_iterations = []

    for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X, y)):
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

        log.info(
            "  Fold %d: AUC=%.4f  AP=%.4f",
            fold_idx,
            fold_m["roc_auc"],
            fold_m["avg_precision"],
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

    oof_mask = ~np.isnan(oof_preds)
    oof_metrics = compute_binary_metrics(y.values[oof_mask], oof_preds[oof_mask])
    cv_metrics["oof_roc_auc"] = oof_metrics["roc_auc"]
    cv_metrics["oof_avg_precision"] = oof_metrics["avg_precision"]

    log.info(
        "%s CV: AUC=%.4f±%.4f  AP=%.4f±%.4f",
        species,
        cv_metrics["cv_roc_auc_mean"],
        cv_metrics["cv_roc_auc_std"],
        cv_metrics["cv_avg_precision_mean"],
        cv_metrics["cv_avg_precision_std"],
    )

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
        species_dir = ARTIFACTS_DIR / species
        species_dir.mkdir(parents=True, exist_ok=True)

        mlflow.log_params({k: v for k, v in params.items() if k != "scale_pos_weight"})
        mlflow.log_param("scale_pos_weight", round(scale_pos_weight, 2))
        mlflow.log_param("species", species)
        mlflow.log_param("n_features", len(feature_cols))
        mlflow.log_param("n_samples", len(df))
        mlflow.log_param("n_positives", int(y.sum()))
        mlflow.log_param("cv_method", "stratified_kfold")
        mlflow.log_param("final_n_estimators", avg_iters)
        mlflow.log_metrics(cv_metrics)

        # Plots
        roc_pr_path = species_dir / "roc_pr_curves.png"
        plot_roc_pr_curves(
            y.values[oof_mask],
            oof_preds[oof_mask],
            title_prefix=f"ISDM {species} — ",
            save_path=roc_pr_path,
        )
        mlflow.log_artifact(str(roc_pr_path))

        cal_path = species_dir / "calibration.png"
        plot_calibration(
            y.values[oof_mask],
            oof_preds[oof_mask],
            title_prefix=f"ISDM {species} — ",
            save_path=cal_path,
        )
        mlflow.log_artifact(str(cal_path))

        imp_path = species_dir / "feature_importance.png"
        plot_feature_importance(
            importance,
            top_n=len(feature_cols),
            title=f"ISDM {species} — Feature Importance",
            save_path=imp_path,
        )
        mlflow.log_artifact(str(imp_path))

        imp_csv_path = species_dir / "feature_importance.csv"
        importance.to_csv(imp_csv_path, header=["importance"])
        mlflow.log_artifact(str(imp_csv_path))

        mlflow.xgboost.log_model(
            final_model,
            artifact_path="model",
            input_example=X.head(5),
        )

        # SHAP summary
        log.info("Computing SHAP values…")
        sample_idx = np.random.RandomState(42).choice(
            len(X),
            size=min(5000, len(X)),
            replace=False,
        )
        booster = final_model.get_booster()
        patch_shap_for_xgboost3()
        explainer = shap.TreeExplainer(booster)
        shap_values = explainer.shap_values(X.iloc[sample_idx])

        shap_path = species_dir / "shap_summary.png"
        plt.figure(figsize=(10, 6))
        shap.summary_plot(shap_values, X.iloc[sample_idx], show=False)
        plt.tight_layout()
        plt.savefig(shap_path, dpi=150, bbox_inches="tight")
        plt.close()
        mlflow.log_artifact(str(shap_path))

    return final_model, cv_metrics


# ── Grid scoring ────────────────────────────────────────────


def score_grid(
    model: xgb.XGBClassifier,
    species: str,
) -> pd.DataFrame:
    """Score our seasonal H3 grid with an ISDM-trained model.

    Reads the seasonal SDM features parquet, extracts the 7 shared
    covariates, and predicts P(species | environment) per cell-season.
    """
    if not SDM_SEASONAL_FEATURES_FILE.exists():
        raise FileNotFoundError(
            f"Seasonal features not found: {SDM_SEASONAL_FEATURES_FILE}\n"
            "Run extract_features.py first."
        )

    log.info("Loading seasonal grid features: %s", SDM_SEASONAL_FEATURES_FILE)
    grid = pd.read_parquet(SDM_SEASONAL_FEATURES_FILE)

    # Extract shared covariates (using our column names)
    missing = [c for c in OUR_FEATURE_COLS if c not in grid.columns]
    if missing:
        raise ValueError(f"Grid missing columns: {missing}")

    X_grid = grid[OUR_FEATURE_COLS].copy()

    # Predict (NaN-safe: fill missing covariates with median for scoring)
    n_missing = X_grid.isna().any(axis=1).sum()
    if n_missing > 0:
        log.warning(
            "  %d rows (%.1f%%) have missing covariates"
            " — filling with median for scoring",
            n_missing,
            100 * n_missing / len(X_grid),
        )
        X_grid = X_grid.fillna(X_grid.median())

    log.info("Scoring %d cell-seasons…", len(X_grid))
    probs = model.predict_proba(X_grid)[:, 1]

    # Reconstruct season label from one-hot columns
    season_cols = ["season_winter", "season_spring", "season_summer", "season_fall"]
    season_names = ["winter", "spring", "summer", "fall"]
    if "season" in grid.columns:
        result = grid[["h3_cell", "season"]].copy()
    elif all(c in grid.columns for c in season_cols):
        season_idx = grid[season_cols].values.argmax(axis=1)
        result = grid[["h3_cell"]].copy()
        result["season"] = [season_names[i] for i in season_idx]
    else:
        result = grid[["h3_cell"]].copy()
        result["season"] = "unknown"

    result[f"isdm_{species}_prob"] = probs

    # Save
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PREDICTIONS_DIR / f"isdm_{species}_predictions.parquet"
    result.to_parquet(out_path, index=False)
    log.info(
        "Saved %s predictions: %s (%.1f MB)",
        species,
        out_path,
        out_path.stat().st_size / 1e6,
    )
    return result


# ── Optuna tuning ───────────────────────────────────────────


def tune_species(
    df: pd.DataFrame,
    species: str,
    n_trials: int = 50,
) -> dict:
    """Optuna HP search for one species."""
    import optuna

    feature_cols = OUR_FEATURE_COLS
    X = df[feature_cols]
    y = df[TARGET_COL]

    def objective(trial):
        params = {
            "objective": "binary:logistic",
            "eval_metric": "auc",
            "tree_method": "hist",
            "scale_pos_weight": float((y == 0).sum() / max((y == 1).sum(), 1)),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 100, 800),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 30),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
            "gamma": trial.suggest_float("gamma", 0.0, 5.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            "random_state": 42,
        }

        skf = StratifiedKFold(n_splits=N_CV_FOLDS, shuffle=True, random_state=42)
        auc_scores = []
        for train_idx, val_idx in skf.split(X, y):
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

    study = optuna.create_study(
        direction="maximize",
        study_name=f"isdm_{species}_tuning",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    log.info(
        "%s best trial: AUC=%.4f  params=%s",
        species,
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
    species_list: list[str] | None = None,
    tune: bool = False,
    n_trials: int = 50,
    do_score: bool = False,
) -> None:
    """Train ISDM models for all (or selected) species."""
    matplotlib.use("Agg")

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    species_list = species_list or list(NISI_ISDM_FILES.keys())
    all_metrics = {}

    for species in species_list:
        log.info("=" * 60)
        log.info("Training ISDM model: %s", species)
        log.info("=" * 60)

        df = load_isdm_data(species)

        with mlflow.start_run(run_name=f"isdm_{species}"):
            mlflow.set_tag("model_type", "xgboost")
            mlflow.set_tag("data_source", "nisi_isdm")
            mlflow.set_tag("species", species)

            if tune:
                log.info("Running Optuna HP search (%d trials)…", n_trials)
                best_params = tune_species(df, species, n_trials)
                mlflow.set_tag("tuned", "true")
            else:
                best_params = None
                mlflow.set_tag("tuned", "false")

            model, metrics = train_species_model(
                df,
                species,
                params=best_params,
                log_to_mlflow=True,
            )
            all_metrics[species] = metrics

            if do_score:
                score_grid(model, species)

    # ── Summary ─────────────────────────────────────────
    log.info("=" * 60)
    log.info("ISDM Training Summary")
    log.info("=" * 60)
    for sp, m in all_metrics.items():
        log.info(
            "  %s: AUC=%.4f±%.4f  AP=%.4f±%.4f",
            sp,
            m["cv_roc_auc_mean"],
            m["cv_roc_auc_std"],
            m["cv_avg_precision_mean"],
            m["cv_avg_precision_std"],
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train ISDM species SDMs")
    parser.add_argument(
        "--species",
        type=str,
        default=None,
        help="Train single species (e.g., blue_whale). Default: all 4.",
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
    parser.add_argument(
        "--score-grid",
        action="store_true",
        help="Score our H3 grid after training",
    )
    args = parser.parse_args()

    species_list = [args.species] if args.species else None
    main(
        species_list=species_list,
        tune=args.tune,
        n_trials=args.n_trials,
        do_score=args.score_grid,
    )

"""ML model training assets for Dagster orchestration.

Wraps the ML training pipelines as Dagster assets, enabling
orchestrated retraining with dependency tracking and MLflow logging.

Asset lineage (SDM family):
    fct_strike_risk_training (dbt) --+
    fct_whale_sdm_training (dbt)  --+--> ml_features --> strike_model
    fct_whale_sdm_seasonal (dbt)  --+                --> sdm_model
                                                     --> sdm_seasonal_model
                                                     --> isdm_model
    {strike_model, sdm_model} --> model_comparison

Asset lineage (Prediction loading):
    isdm_model          --> ml_predictions_loaded  --> dbt int_ml_whale_predictions
    sdm_seasonal_model  --> sdm_predictions_loaded --> dbt int_sdm_whale_predictions

Asset lineage (Climate projections):
    sdm_seasonal_model + raw_cmip6_projections --> sdm_future_scores
        --> sdm_projections_loaded --> dbt fct_collision_risk_ml_projected
    isdm_model + raw_cmip6_projections --> isdm_future_scores
        --> isdm_projections_loaded --> dbt fct_collision_risk_ml_projected

Asset lineage (Audio family):
    raw_whale_audio --> audio_xgboost_model
                    --> audio_cnn_model

Asset lineage (Validation):
    fct_collision_risk (dbt) --> traffic_risk_validation
"""

import subprocess

from dagster import AssetExecutionContext, MaterializeResult, asset

from orchestration.constants import (
    AUDIO_MODEL_DIR,
    ISDM_PROJECTIONS_DIR,
    ML_DIR,
    PHOTO_MODEL_DIR,
    PROJECT_ROOT,
    SDM_PROJECTIONS_DIR,
    WHALE_AUDIO_RAW_DIR,
    WHALE_PHOTO_RAW_DIR,
)


def _run_script(
    context: AssetExecutionContext,
    script: str,
    extra_args: list[str] | None = None,
) -> None:
    """Run a pipeline script from project root."""
    cmd = ["uv", "run", "python", script]
    if extra_args:
        cmd.extend(extra_args)
    context.log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if result.stdout:
        context.log.info(result.stdout[-2000:])
    if result.stderr:
        context.log.warning(result.stderr[-2000:])
    if result.returncode != 0:
        raise RuntimeError(
            f"{script} exited with code {result.returncode}:\n{result.stderr[-1000:]}"
        )


def _file_size_mb(path) -> float:
    """Return file size in MB, or 0 if missing."""
    from pathlib import Path

    p = Path(path)
    return round(p.stat().st_size / 1e6, 1) if p.exists() else 0.0


# ═══════════════════════════════════════════════════════════
# Feature extraction
# ═══════════════════════════════════════════════════════════


@asset(
    group_name="ml",
    kinds={"python", "postgres"},
    deps=[
        "fct_strike_risk_training",
        "fct_whale_sdm_training",
        "fct_whale_sdm_seasonal",
    ],
    description=(
        "Extract ML training features from PostGIS mart tables "
        "to local Parquet files (SDM, seasonal SDM, strike) with "
        "spatial block CV assignment."
    ),
)
def ml_features(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Extract features from dbt marts -> parquet."""
    _run_script(context, "pipeline/analysis/extract_features.py", ["--dataset", "all"])

    strike_file = ML_DIR / "strike_risk_features.parquet"
    sdm_file = ML_DIR / "whale_sdm_features.parquet"
    seasonal_file = ML_DIR / "whale_sdm_seasonal_features.parquet"

    metadata = {
        "strike_file_mb": _file_size_mb(strike_file),
        "sdm_file_mb": _file_size_mb(sdm_file),
        "seasonal_file_mb": _file_size_mb(seasonal_file),
    }
    return MaterializeResult(metadata=metadata)


# ═══════════════════════════════════════════════════════════
# SDM model family
# ═══════════════════════════════════════════════════════════


@asset(
    group_name="ml",
    kinds={"python", "xgboost", "mlflow"},
    deps=["ml_features"],
    description=(
        "Train an XGBoost classifier for ship-strike risk prediction. "
        "Logs params, metrics, SHAP plots, and model to MLflow. "
        "Experimental -- only 67 positives in 1.8M cells."
    ),
)
def strike_model(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Train the strike risk model with spatial CV and MLflow tracking."""
    _run_script(context, "pipeline/analysis/train_strike_model.py")

    imp_file = ML_DIR / "artifacts" / "strike" / "feature_importance.csv"
    metadata = {"mlflow_experiment": "strike_risk"}
    if imp_file.exists():
        first_line = imp_file.read_text().splitlines()[1]  # skip header
        metadata["top_feature"] = first_line.split(",")[0]

    return MaterializeResult(metadata=metadata)


@asset(
    group_name="ml",
    kinds={"python", "xgboost", "mlflow"},
    deps=["ml_features"],
    description=(
        "Train an XGBoost classifier for whale species distribution "
        "modelling (static, 1.8M H3 cells, 47 features). "
        "Logs params, metrics, SHAP plots, and model to MLflow."
    ),
)
def sdm_model(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Train the whale SDM with spatial CV and MLflow tracking."""
    _run_script(context, "pipeline/analysis/train_sdm_model.py")

    imp_file = ML_DIR / "artifacts" / "sdm" / "feature_importance.csv"
    metadata = {"mlflow_experiment": "whale_sdm"}
    if imp_file.exists():
        first_line = imp_file.read_text().splitlines()[1]
        metadata["top_feature"] = first_line.split(",")[0]

    return MaterializeResult(metadata=metadata)


@asset(
    group_name="ml",
    kinds={"python", "xgboost", "mlflow"},
    deps=["ml_features"],
    description=(
        "Train seasonal all-species SDM (7.3M cell-seasons, 18 features). "
        "Also trains per-species models for right, humpback, fin, blue, "
        "sperm, and minke whales."
    ),
)
def sdm_seasonal_model(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Train seasonal SDM: all-species then 6 per-species targets."""
    targets = [
        "any_cetacean",
        "right_whale_present",
        "humpback_present",
        "fin_whale_present",
        "blue_whale_present",
        "sperm_whale_present",
        "minke_whale_present",
    ]
    for target in targets:
        context.log.info("Training seasonal SDM target: %s", target)
        _run_script(
            context,
            "pipeline/analysis/train_sdm_seasonal.py",
            ["--target", target],
        )

    metadata = {
        "mlflow_experiment": "whale_sdm_seasonal",
        "targets_trained": len(targets),
    }
    return MaterializeResult(metadata=metadata)


@asset(
    group_name="ml",
    kinds={"python", "xgboost", "mlflow"},
    deps=["ml_features"],
    description=(
        "Train ISDM models on Nisi et al. curated presence/absence data "
        "for 4 species (blue, fin, humpback, sperm), then score the full "
        "H3 grid (7.3M cell-seasons)."
    ),
)
def isdm_model(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Train ISDM cross-validation models and score the H3 grid."""
    _run_script(
        context,
        "pipeline/analysis/train_isdm_model.py",
        ["--score-grid"],
    )

    pred_dir = ML_DIR / "isdm_predictions"
    n_pred_files = len(list(pred_dir.glob("*.parquet"))) if pred_dir.exists() else 0
    metadata = {
        "mlflow_experiment": "isdm_species_sdm",
        "n_prediction_files": n_pred_files,
    }
    return MaterializeResult(metadata=metadata)


# ═══════════════════════════════════════════════════════════
# ML prediction loading (Python → PostGIS)
# ═══════════════════════════════════════════════════════════


@asset(
    group_name="ml",
    kinds={"python", "postgres"},
    deps=["isdm_model"],
    description=(
        "Load ISDM grid-scored predictions (4 species × 4 seasons "
        "× 1.8M cells) into PostGIS ml_whale_predictions table."
    ),
)
def ml_predictions_loaded(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Load ISDM predictions parquets into PostGIS."""
    _run_script(
        context,
        "pipeline/database/load_ml_predictions.py",
    )
    return MaterializeResult(
        metadata={"table": "ml_whale_predictions"},
    )


@asset(
    group_name="ml",
    kinds={"python", "postgres"},
    deps=["sdm_seasonal_model"],
    description=(
        "Load SDM out-of-fold predictions (7 species × 4 seasons "
        "× 1.8M cells) into PostGIS ml_sdm_predictions table."
    ),
)
def sdm_predictions_loaded(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Load SDM OOF predictions parquets into PostGIS."""
    _run_script(
        context,
        "pipeline/database/load_sdm_predictions.py",
    )
    return MaterializeResult(
        metadata={"table": "ml_sdm_predictions"},
    )


# ═══════════════════════════════════════════════════════════
# Climate projection scoring
# ═══════════════════════════════════════════════════════════


@asset(
    group_name="ml",
    kinds={"python", "xgboost"},
    deps=["sdm_seasonal_model", "raw_cmip6_projections"],
    description=(
        "Score trained seasonal SDMs on CMIP6-projected covariates. "
        "Produces parquets for 7 species × 2 scenarios × 4 decades."
    ),
)
def sdm_future_scores(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Score SDMs under projected future ocean conditions."""
    _run_script(
        context,
        "pipeline/analysis/score_future_sdm.py",
        ["--force"],
    )
    out_dir = SDM_PROJECTIONS_DIR
    n_files = len(list(out_dir.glob("*.parquet"))) if out_dir.exists() else 0
    return MaterializeResult(
        metadata={"n_projection_files": n_files},
    )


@asset(
    group_name="ml",
    kinds={"python", "xgboost"},
    deps=["isdm_model", "raw_cmip6_projections"],
    description=(
        "Score trained ISDM models on CMIP6-projected covariates. "
        "Produces parquets for 4 species × 2 scenarios × 4 decades."
    ),
)
def isdm_future_scores(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Score ISDMs under projected future ocean conditions."""
    _run_script(
        context,
        "pipeline/analysis/score_future_isdm.py",
        ["--force"],
    )
    out_dir = ISDM_PROJECTIONS_DIR
    n_files = len(list(out_dir.glob("*.parquet"))) if out_dir.exists() else 0
    return MaterializeResult(
        metadata={"n_projection_files": n_files},
    )


@asset(
    group_name="ml",
    kinds={"python", "postgres"},
    deps=["sdm_future_scores"],
    description=(
        "Load CMIP6-projected SDM predictions into PostGIS "
        "whale_sdm_projections table (58M rows)."
    ),
)
def sdm_projections_loaded(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Load projected SDM parquets into PostGIS."""
    _run_script(
        context,
        "pipeline/database/load_sdm_projections.py",
    )
    return MaterializeResult(
        metadata={"table": "whale_sdm_projections"},
    )


@asset(
    group_name="ml",
    kinds={"python", "postgres"},
    deps=["isdm_future_scores"],
    description=(
        "Load CMIP6-projected ISDM predictions into PostGIS "
        "whale_isdm_projections table."
    ),
)
def isdm_projections_loaded(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Load projected ISDM parquets into PostGIS."""
    _run_script(
        context,
        "pipeline/database/load_isdm_projections.py",
    )
    return MaterializeResult(
        metadata={"table": "whale_isdm_projections"},
    )


# ═══════════════════════════════════════════════════════════
# Comparison & validation
# ═══════════════════════════════════════════════════════════


@asset(
    group_name="ml",
    kinds={"python"},
    deps=["strike_model", "sdm_model"],
    description=(
        "Compare ML-learned feature importances against the "
        "hand-tuned sub-score weights in fct_collision_risk."
    ),
)
def model_comparison(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Run the importance comparison analysis."""
    _run_script(context, "pipeline/analysis/compare_importances.py")

    comparison_file = (
        ML_DIR / "artifacts" / "comparison" / "domain_weight_comparison.csv"
    )
    metadata = {}
    if comparison_file.exists():
        metadata["comparison_file"] = str(comparison_file)

    return MaterializeResult(metadata=metadata)


@asset(
    group_name="ml",
    kinds={"python", "postgres"},
    deps=["fct_collision_risk"],
    description=(
        "Validate traffic risk methodology: weight sums, Jensen's "
        "inequality, draft imputation, Nisi correlation, strike "
        "overlap, SMA overlap, weight perturbation, spatial bias, "
        "and composite sensitivity (9 tests)."
    ),
)
def traffic_risk_validation(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Run the 9-section traffic risk validation suite."""
    _run_script(
        context,
        "pipeline/analysis/validate_traffic_risk.py",
        ["--section", "all"],
    )

    report_pdf = PROJECT_ROOT / "docs" / "pdfs" / "traffic_risk_methodology.pdf"
    metadata = {"pdf_exists": report_pdf.exists()}
    return MaterializeResult(metadata=metadata)


# ═══════════════════════════════════════════════════════════
# Audio classification
# ═══════════════════════════════════════════════════════════


@asset(
    group_name="ingestion",
    kinds={"python"},
    description=(
        "Download whale audio training data from Watkins Marine Mammal "
        "Sound Database, Zenodo (3 datasets), and SanctSound catalogue. "
        "452 files across 8 species."
    ),
)
def raw_whale_audio(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Download whale audio training data."""
    _run_script(
        context,
        "pipeline/ingestion/download_whale_audio.py",
        ["--source", "all"],
    )

    manifest = WHALE_AUDIO_RAW_DIR / "training_manifest.csv"
    metadata = {
        "dir": str(WHALE_AUDIO_RAW_DIR),
        "manifest_exists": manifest.exists(),
    }
    if manifest.exists():
        import pandas as pd

        mf = pd.read_csv(manifest)
        metadata["n_files"] = len(mf)
        metadata["n_species"] = (
            mf["species"].nunique() if "species" in mf.columns else 0
        )

    return MaterializeResult(metadata=metadata)


@asset(
    group_name="ml",
    kinds={"python", "xgboost", "mlflow"},
    deps=["raw_whale_audio"],
    description=(
        "Train an XGBoost classifier on 64 acoustic features extracted "
        "from whale audio segments. 5-fold stratified CV. "
        "Three-stage class balancing: segment cap (2,000), augmentation "
        "(target 500), inverse-frequency weights. 97.9% accuracy."
    ),
)
def audio_xgboost_model(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Train XGBoost audio species classifier."""
    _run_script(context, "pipeline/analysis/train_audio_classifier.py")

    model_file = AUDIO_MODEL_DIR / "xgboost_audio_model.json"
    imp_file = ML_DIR / "artifacts" / "audio_classifier" / "feature_importance.csv"
    metadata = {
        "mlflow_experiment": "whale_audio_classifier",
        "backend": "xgboost",
        "model_exists": model_file.exists(),
    }
    if imp_file.exists():
        first_line = imp_file.read_text().splitlines()[1]
        metadata["top_feature"] = first_line.split(",")[0]

    return MaterializeResult(metadata=metadata)


@asset(
    group_name="ml",
    kinds={"python", "pytorch", "mlflow"},
    deps=["raw_whale_audio"],
    description=(
        "Train a ResNet18 CNN on mel spectrograms from whale audio. "
        "80/20 stratified split, inverse-frequency class weights, "
        "early stopping (patience=7). 99.3% accuracy, 99.4% macro F1."
    ),
)
def audio_cnn_model(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Train CNN audio species classifier."""
    _run_script(
        context,
        "pipeline/analysis/train_audio_classifier.py",
        ["--backend", "cnn"],
    )

    model_file = AUDIO_MODEL_DIR / "cnn_audio_model.pt"
    report_file = (
        ML_DIR / "artifacts" / "audio_classifier" / "cnn_classification_report.txt"
    )
    metadata = {
        "mlflow_experiment": "whale_audio_classifier",
        "backend": "cnn_resnet18",
        "model_exists": model_file.exists(),
        "model_size_mb": _file_size_mb(model_file),
    }
    if report_file.exists():
        metadata["report_exists"] = True

    return MaterializeResult(metadata=metadata)


# ═══════════════════════════════════════════════════════════
# Photo classification
# ═══════════════════════════════════════════════════════════


@asset(
    group_name="ingestion",
    kinds={"python"},
    description=(
        "Download Happywhale Kaggle dataset and filter to 8 target "
        "species (7 whales + other_cetacean). ~20K images after "
        "filtering and capping."
    ),
)
def raw_whale_photos(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Download whale photo training data from Happywhale."""
    _run_script(
        context,
        "pipeline/ingestion/download_whale_photos.py",
    )

    metadata = {
        "dir": str(WHALE_PHOTO_RAW_DIR),
        "dir_exists": WHALE_PHOTO_RAW_DIR.exists(),
    }
    if WHALE_PHOTO_RAW_DIR.exists():
        n_images = len(list(WHALE_PHOTO_RAW_DIR.rglob("*.jpg")))
        metadata["n_images"] = n_images

    return MaterializeResult(metadata=metadata)


@asset(
    group_name="ml",
    kinds={"python", "pytorch", "mlflow"},
    deps=["raw_whale_photos"],
    description=(
        "Fine-tune an EfficientNet-B4 CNN for whale species "
        "classification from photos. 8 classes (7 target species + "
        "other_cetacean). Differential LR, CosineAnnealing, "
        "early stopping on val macro F1."
    ),
)
def photo_classifier_model(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Train EfficientNet-B4 photo species classifier."""
    _run_script(context, "pipeline/analysis/train_photo_classifier.py")

    model_file = PHOTO_MODEL_DIR / "efficientnet_b4_whale.pt"
    report_dir = ML_DIR / "artifacts" / "photo_classifier"
    metadata = {
        "mlflow_experiment": "whale_photo_classifier",
        "model_exists": model_file.exists(),
        "model_size_mb": _file_size_mb(model_file),
    }
    if report_dir.exists():
        metadata["report_dir"] = str(report_dir)

    return MaterializeResult(metadata=metadata)


# ═══════════════════════════════════════════════════════════
# Backend database migrations
# ═══════════════════════════════════════════════════════════


@asset(
    group_name="database",
    kinds={"postgres"},
    deps=["postgis_schema"],
    description=(
        "Run backend database migrations: creates users, "
        "sighting_submissions, reputation_events, and "
        "user_credentials tables for the API."
    ),
)
def backend_migrations(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Run backend/migrations.py to create API-specific tables."""
    _run_script(context, "backend/migrations.py")
    return MaterializeResult(
        metadata={"status": "migrations_applied"},
    )

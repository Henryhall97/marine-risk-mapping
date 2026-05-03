"""Train a multi-species whale audio classifier.

Two training modes:
  1. **XGBoost on acoustic features** (default) — fast, lightweight, consistent
     with the project's ML stack.  Extracts ~60 acoustic descriptors per segment
     and trains a multi-class XGBoost model with spatial-aware CV.
  2. **CNN on mel spectrograms** (--backend cnn) — fine-tunes a ResNet18 on
     mel-spectrogram images.  Requires torch + torchvision.

Both modes log to MLflow (experiment: ``whale_audio_classifier``).

Usage
-----
    # XGBoost (default)
    uv run python pipeline/analysis/train_audio_classifier.py

    # With Optuna hyperparameter tuning
    uv run python pipeline/analysis/train_audio_classifier.py --tune

    # CNN backend
    uv run python pipeline/analysis/train_audio_classifier.py --backend cnn --epochs 30

    # Evaluate an existing model
    uv run python pipeline/analysis/train_audio_classifier.py --evaluate-only
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from pipeline.audio.classify import CNNAudioClassifier, XGBoostAudioClassifier

from pipeline.config import (
    AUDIO_AUGMENT_TARGET,
    AUDIO_BROAD_MODEL_DIR,
    AUDIO_CNN_EARLY_STOP_PATIENCE,
    AUDIO_MAX_SEGMENTS_PER_SPECIES,
    AUDIO_MODEL_DIR,
    AUDIO_RARE_EMBEDDINGS_DIR,
    AUDIO_SAMPLE_RATE,
    AUDIO_SEGMENT_DURATION,
    AUDIO_SEGMENT_HOP,
    ML_DIR,
    MLFLOW_TRACKING_URI,
    WHALE_AUDIO_RARE_SPECIES,
    WHALE_AUDIO_RAW_DIR,
)

log = logging.getLogger(__name__)

EXPERIMENT_NAME = "whale_audio_classifier"
ARTIFACTS_DIR = ML_DIR / "artifacts" / "audio_classifier"


# ── Feature extraction ──────────────────────────────────────


# Re-export from config for use as function defaults and CLI help text.
_DEFAULT_MAX_SEGMENTS_PER_SPECIES = AUDIO_MAX_SEGMENTS_PER_SPECIES
_DEFAULT_AUGMENT_TARGET = AUDIO_AUGMENT_TARGET


def _augment_underrepresented(
    df: pd.DataFrame,
    augment_target: int,
) -> pd.DataFrame:
    """Augment species with fewer than *augment_target* segments.

    For each underrepresented species, we re-load the original waveforms
    from the file paths stored in the DataFrame, apply random augmentations,
    and extract new feature rows.  Augmented rows are marked with
    ``is_augmented=True``.
    """
    from pipeline.audio.preprocess import (
        augment_waveform,
        compute_acoustic_features,
        load_audio,
        segment_audio,
    )

    aug_rows: list[dict] = []
    rng = np.random.default_rng(42)

    for sp, grp in df.groupby("species"):
        n_raw = len(grp)
        if n_raw >= augment_target:
            continue

        n_needed = augment_target - n_raw
        log.info(
            "Augmenting %s: %d raw segments → generating %d synthetic",
            sp,
            n_raw,
            n_needed,
        )

        # Collect unique source files for this species
        source_files = grp["file"].unique().tolist()

        # Build a pool of raw waveform segments to augment from
        segment_pool: list[np.ndarray] = []
        for fname in source_files:
            # We only have the filename, not the full path.  Reconstruct
            # by scanning the manifest species directory.
            species_dir = WHALE_AUDIO_RAW_DIR / sp
            candidates = list(species_dir.rglob(fname))
            if not candidates:
                continue
            try:
                y, sr = load_audio(candidates[0])
                segs = segment_audio(y, sr)
                segment_pool.extend(segs)
            except Exception:
                log.warning("Failed to reload %s for augmentation", fname)
                continue
            # Stop collecting if we have enough source material
            if len(segment_pool) >= n_needed:
                break

        if not segment_pool:
            log.warning("No waveform segments available to augment %s", sp)
            continue

        # Generate augmented feature rows
        generated = 0
        while generated < n_needed:
            src_seg = segment_pool[generated % len(segment_pool)]
            aug_wav = augment_waveform(
                src_seg, AUDIO_SAMPLE_RATE, strategy="all", rng=rng
            )
            feats = compute_acoustic_features(aug_wav, AUDIO_SAMPLE_RATE)
            row = {
                "file": "augmented",
                "segment_idx": generated,
                "start_sec": 0.0,
                "end_sec": AUDIO_SEGMENT_DURATION,
                "species": sp,
                "is_augmented": True,
                **feats,
            }
            aug_rows.append(row)
            generated += 1

        log.info("  %s: generated %d augmented segments", sp, generated)

    if not aug_rows:
        return df

    # Mark originals
    df = df.copy()
    if "is_augmented" not in df.columns:
        df["is_augmented"] = False

    aug_df = pd.DataFrame(aug_rows)
    combined = pd.concat([df, aug_df], ignore_index=True)
    log.info(
        "Augmentation complete: %d original + %d synthetic = %d total",
        len(df),
        len(aug_rows),
        len(combined),
    )
    return combined


def extract_training_features(
    manifest_path: Path | None = None,
    output_path: Path | None = None,
    max_files_per_species: int | None = None,
    max_segments_per_species: int | None = _DEFAULT_MAX_SEGMENTS_PER_SPECIES,
    augment_target: int | None = _DEFAULT_AUGMENT_TARGET,
) -> pd.DataFrame:
    """Extract acoustic features from training audio files.

    Reads the training manifest, loads each file, segments it, and
    extracts the feature vector for each segment.  Saves to parquet.

    Parameters
    ----------
    max_segments_per_species : int | None
        Cap the number of 4-second segments retained per species after
        extraction.  This keeps the training set balanced when source
        durations vary wildly (e.g. 96 h of blue whale vs 38 s of sei).
        Default 2000 (~2.2 hours of audio per species).  Set to None
        or 0 to disable.
    augment_target : int | None
        Species with fewer than this many raw segments are augmented
        (time-stretch, pitch-shift, noise, time-shift) up to this
        floor.  Default 500.  Set to None or 0 to disable.

    Returns the feature DataFrame.
    """
    from pipeline.audio.preprocess import extract_feature_matrix

    manifest_path = manifest_path or (WHALE_AUDIO_RAW_DIR / "training_manifest.csv")
    output_path = output_path or (ML_DIR / "audio_features.parquet")

    if output_path.exists():
        log.info("Loading cached features from %s", output_path)
        return pd.read_parquet(output_path)

    log.info("Reading training manifest from %s", manifest_path)
    manifest = pd.read_csv(manifest_path)
    log.info(
        "Manifest: %d files, %d species", len(manifest), manifest["species"].nunique()
    )

    # Optionally limit files per species for faster iteration
    if max_files_per_species:
        manifest = (
            manifest.groupby("species")
            .apply(lambda g: g.head(max_files_per_species))
            .reset_index(drop=True)
        )
        log.info(
            "Limited to %d files per species → %d total",
            max_files_per_species,
            len(manifest),
        )

    # Extract features
    audio_paths = manifest["file_path"].tolist()
    labels = manifest["species"].tolist()

    df = extract_feature_matrix(
        audio_paths, labels=labels, max_segments_per_label=max_segments_per_species
    )

    # Cap segments per species to keep training balanced (cap BEFORE augment)
    if (
        max_segments_per_species
        and max_segments_per_species > 0
        and "species" in df.columns
    ):
        before = len(df)
        df = (
            df.groupby("species", group_keys=False)
            .apply(
                lambda g: g.sample(
                    n=min(len(g), max_segments_per_species), random_state=42
                )
            )
            .reset_index(drop=True)
        )
        if len(df) < before:
            log.info(
                "Capped segments: %d → %d (max %d per species)",
                before,
                len(df),
                max_segments_per_species,
            )

    # Augment underrepresented species up to the target floor
    if augment_target and augment_target > 0 and "species" in df.columns:
        df = _augment_underrepresented(df, augment_target)

    # Log final class distribution
    if "species" in df.columns:
        log.info("Final segment counts per species:")
        for sp in sorted(df["species"].unique()):
            n = (df["species"] == sp).sum()
            aug = (df["species"] == sp) & df.get(
                "is_augmented", pd.Series(False)
            ).fillna(False)
            n_aug = aug.sum() if "is_augmented" in df.columns else 0
            log.info("  %-20s %5d segments (%d augmented)", sp, n, n_aug)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    log.info(
        "Saved features: %s (%d rows, %d columns)",
        output_path,
        len(df),
        len(df.columns),
    )

    return df


# ── XGBoost training ────────────────────────────────────────


def train_xgboost(
    features_df: pd.DataFrame,
    tune: bool = False,
    n_trials: int = 50,
    model_dir: Path | None = None,
    experiment_name: str | None = None,
) -> XGBoostAudioClassifier:
    """Train a multi-class XGBoost classifier on acoustic features.

    Uses stratified k-fold CV for evaluation, optional Optuna tuning.
    Logs metrics and model to MLflow.
    """
    import mlflow
    import xgboost as xgb
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
    )
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import LabelEncoder

    from pipeline.audio.classify import XGBoostAudioClassifier

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(experiment_name or EXPERIMENT_NAME)

    eff_model_dir = model_dir or AUDIO_MODEL_DIR
    eff_artifacts_dir = ARTIFACTS_DIR.parent / eff_model_dir.name

    # Prepare data
    meta_cols = ["file", "segment_idx", "start_sec", "end_sec", "species"]
    feature_cols = [c for c in features_df.columns if c not in meta_cols]
    X = features_df[feature_cols].values
    le = LabelEncoder()
    y = le.fit_transform(features_df["species"])
    label_map = {i: s for i, s in enumerate(le.classes_)}
    n_classes = len(label_map)

    log.info(
        "Training data: %d samples, %d features, %d classes",
        X.shape[0],
        X.shape[1],
        n_classes,
    )
    for i, cls_name in label_map.items():
        log.info("  Class %d: %-20s  %d samples", i, cls_name, (y == i).sum())

    # ── Inverse-frequency class weights ──────────────────────
    # w_i = total / (n_classes × count_i)  — gives rare classes higher weight.
    # Applied per-sample so XGBoost's loss function treats classes equally
    # even after augmentation and capping.
    class_counts = np.bincount(y, minlength=n_classes).astype(float)
    class_weights = len(y) / (n_classes * class_counts + 1e-6)
    sample_weights = class_weights[y]
    log.info("Class weights (inverse-frequency):")
    for i, cls_name in label_map.items():
        log.info(
            "  %-20s  weight=%.3f  (n=%d)",
            cls_name,
            class_weights[i],
            int(class_counts[i]),
        )

    # Default XGBoost params
    params = {
        "objective": "multi:softprob",
        "num_class": n_classes,
        "eval_metric": "mlogloss",
        "max_depth": 6,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "gamma": 0.1,
        "tree_method": "hist",
        "random_state": 42,
    }

    if tune:
        params = _optuna_tune_xgboost(X, y, n_classes, n_trials=n_trials)

    # Train with stratified CV for evaluation
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof_preds = np.zeros((len(y), n_classes))

    with mlflow.start_run(run_name="xgboost_audio"):
        mlflow.log_params({k: v for k, v in params.items() if not k.startswith("_")})
        mlflow.log_param("n_features", X.shape[1])
        mlflow.log_param("n_samples", X.shape[0])
        mlflow.log_param("n_classes", n_classes)
        mlflow.log_param("backend", "xgboost")
        mlflow.log_param("class_weighting", "inverse_frequency")

        for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
            dtrain = xgb.DMatrix(
                X[train_idx],
                label=y[train_idx],
                weight=sample_weights[train_idx],
                feature_names=feature_cols,
            )
            dval = xgb.DMatrix(
                X[val_idx],
                label=y[val_idx],
                weight=sample_weights[val_idx],
                feature_names=feature_cols,
            )

            model = xgb.train(
                params,
                dtrain,
                num_boost_round=300,
                evals=[(dval, "val")],
                early_stopping_rounds=30,
                verbose_eval=False,
            )
            oof_preds[val_idx] = model.predict(dval)
            log.info("Fold %d: best_iteration=%d", fold, model.best_iteration)

        # Overall metrics
        oof_labels = np.argmax(oof_preds, axis=1)
        accuracy = accuracy_score(y, oof_labels)
        macro_f1 = f1_score(y, oof_labels, average="macro")
        weighted_f1 = f1_score(y, oof_labels, average="weighted")

        mlflow.log_metric("cv_accuracy", accuracy)
        mlflow.log_metric("cv_macro_f1", macro_f1)
        mlflow.log_metric("cv_weighted_f1", weighted_f1)

        log.info("CV Accuracy: %.4f", accuracy)
        log.info("CV Macro F1: %.4f", macro_f1)
        log.info("CV Weighted F1: %.4f", weighted_f1)

        # Classification report
        report = classification_report(
            y, oof_labels, target_names=[label_map[i] for i in range(n_classes)]
        )
        log.info("\n%s", report)

        # Save artifacts
        eff_artifacts_dir.mkdir(parents=True, exist_ok=True)
        report_path = eff_artifacts_dir / "classification_report.txt"
        report_path.write_text(report)
        mlflow.log_artifact(str(report_path))

        # Confusion matrix plot
        _plot_confusion_matrix(
            confusion_matrix(y, oof_labels),
            [label_map[i] for i in range(n_classes)],
            eff_artifacts_dir / "confusion_matrix.png",
        )
        mlflow.log_artifact(str(eff_artifacts_dir / "confusion_matrix.png"))

        # Feature importance
        _plot_feature_importance(
            model, feature_cols, eff_artifacts_dir / "feature_importance.png"
        )
        mlflow.log_artifact(str(eff_artifacts_dir / "feature_importance.png"))

        # Train final model on all data
        log.info("Training final model on all %d samples", len(y))
        dtrain_full = xgb.DMatrix(
            X,
            label=y,
            weight=sample_weights,
            feature_names=feature_cols,
        )
        final_model = xgb.train(
            params,
            dtrain_full,
            num_boost_round=model.best_iteration + 10,
            verbose_eval=False,
        )

        # Save model
        classifier = XGBoostAudioClassifier(
            model=final_model,
            feature_names=feature_cols,
            label_encoder=label_map,
        )
        model_path = classifier.save(eff_model_dir)
        mlflow.log_artifact(str(model_path))
        mlflow.log_artifact(str(eff_model_dir / "model_metadata.json"))

        log.info("Model saved to %s", eff_model_dir)

    return classifier


def _optuna_tune_xgboost(
    X: np.ndarray,
    y: np.ndarray,
    n_classes: int,
    n_trials: int = 50,
) -> dict:
    """Bayesian hyperparameter search with Optuna."""
    import optuna
    import xgboost as xgb
    from sklearn.metrics import f1_score
    from sklearn.model_selection import StratifiedKFold

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    # Inverse-frequency class weights for tuning CV too
    class_counts = np.bincount(y, minlength=n_classes).astype(float)
    _cw = len(y) / (n_classes * class_counts + 1e-6)
    _sw = _cw[y]

    def objective(trial):
        params = {
            "objective": "multi:softprob",
            "num_class": n_classes,
            "eval_metric": "mlogloss",
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
            "gamma": trial.suggest_float("gamma", 0.0, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            "tree_method": "hist",
            "random_state": 42,
        }

        skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        f1s = []
        for train_idx, val_idx in skf.split(X, y):
            dtrain = xgb.DMatrix(
                X[train_idx], label=y[train_idx], weight=_sw[train_idx]
            )
            dval = xgb.DMatrix(X[val_idx], label=y[val_idx], weight=_sw[val_idx])
            model = xgb.train(
                params,
                dtrain,
                num_boost_round=200,
                evals=[(dval, "val")],
                early_stopping_rounds=20,
                verbose_eval=False,
            )
            preds = np.argmax(model.predict(dval), axis=1)
            f1s.append(f1_score(y[val_idx], preds, average="macro"))

        return np.mean(f1s)

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, n_jobs=1)

    log.info(
        "Best Optuna trial: F1=%.4f, params=%s", study.best_value, study.best_params
    )

    best = study.best_params
    best.update(
        {
            "objective": "multi:softprob",
            "num_class": n_classes,
            "eval_metric": "mlogloss",
            "tree_method": "hist",
            "random_state": 42,
        }
    )
    return best


# ── CNN training (optional) ─────────────────────────────────


def train_cnn(
    features_df: pd.DataFrame,
    epochs: int = 30,
    batch_size: int = 32,
    lr: float = 1e-3,
    model_dir: Path | None = None,
    experiment_name: str | None = None,
) -> CNNAudioClassifier:
    """Train a ResNet18-based CNN on mel spectrograms.

    This regenerates spectrograms from the audio files listed in the
    feature DataFrame (which stores file paths and species labels).
    """
    import mlflow
    import torch
    import torch.nn as nn
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        f1_score,
    )
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder
    from torch.utils.data import DataLoader, TensorDataset

    from pipeline.audio.classify import CNNAudioClassifier, _build_resnet18
    from pipeline.audio.preprocess import (
        augment_waveform,
        compute_mel_spectrogram,
        load_audio,
        segment_audio,
    )

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(experiment_name or EXPERIMENT_NAME)

    eff_model_dir = model_dir or AUDIO_MODEL_DIR
    eff_artifacts_dir = ARTIFACTS_DIR.parent / eff_model_dir.name

    # Get unique files + labels from the feature DataFrame
    # Exclude augmented rows — CNN re-generates spectrograms from source files
    real_df = features_df[
        ~features_df.get("is_augmented", pd.Series(False)).fillna(False).astype(bool)
    ]
    file_species = real_df.groupby("file")["species"].first().reset_index()

    # Build filename → full path lookup from the training manifest
    manifest_path = WHALE_AUDIO_RAW_DIR / "training_manifest.csv"
    manifest = pd.read_csv(manifest_path)
    fname_to_path: dict[str, str] = {}
    for _, mrow in manifest.iterrows():
        fname_to_path[Path(mrow["file_path"]).name] = mrow["file_path"]

    le = LabelEncoder()
    file_species["label"] = le.fit_transform(file_species["species"])
    label_map = {i: s for i, s in enumerate(le.classes_)}
    n_classes = len(label_map)

    # ── Generate spectrograms per species (with cap) ────────
    log.info("Generating spectrograms for %d files...", len(file_species))
    max_seg = AUDIO_MAX_SEGMENTS_PER_SPECIES
    # Collect waveform segments per species first, so we can cap + augment
    species_segments: dict[int, list[np.ndarray]] = {i: [] for i in range(n_classes)}

    # Track segments per species for early-exit cap
    seg_counts: dict[int, int] = {i: 0 for i in range(n_classes)}

    for _, row in file_species.iterrows():
        lbl = row["label"]
        # Early exit if this species already hit the cap
        if max_seg and seg_counts[lbl] >= max_seg:
            continue
        full_path = fname_to_path.get(row["file"])
        if not full_path:
            log.warning("No manifest path for %s — skipping", row["file"])
            continue
        # Compute max duration to load (avoids loading 24-hour files)
        remaining = max_seg - seg_counts[lbl] if max_seg else None
        max_dur = (
            (remaining * AUDIO_SEGMENT_HOP + AUDIO_SEGMENT_DURATION)
            if remaining
            else None
        )
        try:
            y, sr = load_audio(full_path, max_duration_sec=max_dur)
            segs = segment_audio(y, sr)
            species_segments[lbl].extend(segs)
            seg_counts[lbl] += len(segs)
        except Exception:
            log.warning("Failed to process %s", row["file"], exc_info=True)

    # Cap segments per species (consistent with XGBoost path)
    rng = np.random.default_rng(42)
    for lbl, segs in species_segments.items():
        if max_seg and len(segs) > max_seg:
            idx = rng.choice(len(segs), size=max_seg, replace=False)
            species_segments[lbl] = [segs[i] for i in sorted(idx)]
            log.info(
                "  %-20s capped %d → %d segments", label_map[lbl], len(segs), max_seg
            )

    # Augment underrepresented species (consistent with XGBoost path)
    augment_target = AUDIO_AUGMENT_TARGET
    for lbl, segs in species_segments.items():
        n_raw = len(segs)
        if not segs or n_raw >= augment_target:
            continue
        n_needed = augment_target - n_raw
        log.info(
            "  Augmenting %-20s: %d raw → +%d synthetic",
            label_map[lbl],
            n_raw,
            n_needed,
        )
        aug_segs: list[np.ndarray] = []
        for i in range(n_needed):
            src = segs[i % n_raw]
            aug_segs.append(
                augment_waveform(src, AUDIO_SAMPLE_RATE, strategy="all", rng=rng)
            )
        species_segments[lbl] = segs + aug_segs

    # Convert to spectrograms
    all_specs: list[np.ndarray] = []
    all_labels: list[int] = []
    for lbl in range(n_classes):
        for seg in species_segments[lbl]:
            spec = compute_mel_spectrogram(seg, AUDIO_SAMPLE_RATE)
            all_specs.append(spec)
            all_labels.append(lbl)
        log.info("  %-20s %d spectrograms", label_map[lbl], len(species_segments[lbl]))

    if not all_specs:
        raise ValueError("No spectrograms generated — check audio files")

    # Pad to uniform time dimension
    max_t = max(s.shape[1] for s in all_specs)
    specs_padded = np.stack(
        [
            np.pad(s, ((0, 0), (0, max_t - s.shape[1])))
            if s.shape[1] < max_t
            else s[:, :max_t]
            for s in all_specs
        ]
    )
    labels_arr = np.array(all_labels)

    log.info("Spectrogram dataset: %s, %d classes", specs_padded.shape, n_classes)

    # Train/val split
    X_train, X_val, y_train, y_val = train_test_split(
        specs_padded, labels_arr, test_size=0.2, stratify=labels_arr, random_state=42
    )

    # Convert to tensors — expand to 3 channels for ResNet
    X_train_t = (
        torch.tensor(X_train, dtype=torch.float32).unsqueeze(1).expand(-1, 3, -1, -1)
    )
    X_val_t = (
        torch.tensor(X_val, dtype=torch.float32).unsqueeze(1).expand(-1, 3, -1, -1)
    )
    y_train_t = torch.tensor(y_train, dtype=torch.long)
    y_val_t = torch.tensor(y_val, dtype=torch.long)

    train_ds = TensorDataset(X_train_t, y_train_t)
    val_ds = TensorDataset(X_val_t, y_val_t)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)

    # ── Inverse-frequency class weights (consistent with XGBoost path) ──
    class_counts = np.bincount(labels_arr, minlength=n_classes).astype(float)
    cw = len(labels_arr) / (n_classes * class_counts + 1e-6)
    log.info("CNN class weights (inverse-frequency):")
    for i, cls_name in label_map.items():
        log.info("  %-20s  weight=%.3f  (n=%d)", cls_name, cw[i], int(class_counts[i]))

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    cw_tensor = torch.tensor(cw, dtype=torch.float32).to(device)

    # Model
    model = _build_resnet18(n_classes).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss(weight=cw_tensor)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5)

    with mlflow.start_run(run_name="cnn_audio"):
        mlflow.log_param("backend", "cnn_resnet18")
        mlflow.log_param("epochs", epochs)
        mlflow.log_param("batch_size", batch_size)
        mlflow.log_param("lr", lr)
        mlflow.log_param("n_classes", n_classes)
        mlflow.log_param("n_train", len(X_train))
        mlflow.log_param("n_val", len(X_val))
        mlflow.log_param(
            "spectrogram_shape", f"{specs_padded.shape[1]}x{specs_padded.shape[2]}"
        )
        mlflow.log_param("class_weighting", "inverse_frequency")
        mlflow.log_param("segment_cap", max_seg)
        mlflow.log_param("augment_target", augment_target)
        mlflow.log_param("early_stop_patience", AUDIO_CNN_EARLY_STOP_PATIENCE)

        best_f1 = 0.0
        best_state = None
        patience_counter = 0

        for epoch in range(epochs):
            model.train()
            train_loss = 0.0
            for xb, yb in train_loader:
                xb, yb = xb.to(device), yb.to(device)
                optimizer.zero_grad()
                out = model(xb)
                loss = criterion(out, yb)
                loss.backward()
                optimizer.step()
                train_loss += loss.item() * xb.size(0)

            train_loss /= len(train_ds)

            # Validation
            model.eval()
            val_preds, val_true = [], []
            val_loss = 0.0
            with torch.no_grad():
                for xb, yb in val_loader:
                    xb, yb = xb.to(device), yb.to(device)
                    out = model(xb)
                    val_loss += criterion(out, yb).item() * xb.size(0)
                    val_preds.extend(out.argmax(dim=1).cpu().numpy())
                    val_true.extend(yb.cpu().numpy())

            val_loss /= len(val_ds)
            val_acc = accuracy_score(val_true, val_preds)
            val_f1 = f1_score(val_true, val_preds, average="macro")
            scheduler.step(val_loss)

            mlflow.log_metrics(
                {
                    "train_loss": train_loss,
                    "val_loss": val_loss,
                    "val_acc": val_acc,
                    "val_f1": val_f1,
                },
                step=epoch,
            )

            if val_f1 > best_f1:
                best_f1 = val_f1
                best_state = model.state_dict().copy()
                patience_counter = 0
            else:
                patience_counter += 1

            if (epoch + 1) % 5 == 0 or epoch == 0:
                log.info(
                    "Epoch %d/%d  loss=%.4f  val_loss=%.4f  val_acc=%.4f  val_f1=%.4f",
                    epoch + 1,
                    epochs,
                    train_loss,
                    val_loss,
                    val_acc,
                    val_f1,
                )

            if patience_counter >= AUDIO_CNN_EARLY_STOP_PATIENCE:
                log.info(
                    "Early stopping at epoch %d "
                    "-- no val F1 improvement for %d epochs "
                    "(best=%.4f)",
                    epoch + 1,
                    AUDIO_CNN_EARLY_STOP_PATIENCE,
                    best_f1,
                )
                break

        # Restore best model
        if best_state:
            model.load_state_dict(best_state)

        # Final report
        model.eval()
        val_preds_final = []
        with torch.no_grad():
            for xb, _yb in val_loader:
                out = model(xb.to(device))
                val_preds_final.extend(out.argmax(dim=1).cpu().numpy())

        report = classification_report(
            val_true,
            val_preds_final,
            target_names=[label_map[i] for i in range(n_classes)],
        )
        log.info("\n%s", report)
        mlflow.log_metric("best_val_f1", best_f1)

        eff_artifacts_dir.mkdir(parents=True, exist_ok=True)
        report_path = eff_artifacts_dir / "cnn_classification_report.txt"
        report_path.write_text(report)
        mlflow.log_artifact(str(report_path))

        # Save model
        classifier = CNNAudioClassifier(model=model, label_encoder=label_map)
        model_path = classifier.save(eff_model_dir)
        mlflow.log_artifact(str(model_path))

        log.info(
            "CNN model saved to %s  (best val F1: %.4f)",
            eff_model_dir,
            best_f1,
        )

    return classifier


# ── Plotting helpers ────────────────────────────────────────


def _plot_confusion_matrix(cm: np.ndarray, labels: list[str], save_path: Path):
    """Save a confusion matrix heatmap."""
    import matplotlib.pyplot as plt
    import seaborn as sns

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=labels,
        yticklabels=labels,
        ax=ax,
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Audio Classification — Confusion Matrix")
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    log.info("Saved confusion matrix → %s", save_path)


def _plot_feature_importance(
    model, feature_names: list[str], save_path: Path, top_n: int = 30
):
    """Save a feature importance bar chart."""
    import matplotlib.pyplot as plt

    scores = model.get_score(importance_type="gain")
    imp_df = (
        pd.DataFrame(
            {"feature": list(scores.keys()), "importance": list(scores.values())}
        )
        .sort_values("importance", ascending=False)
        .head(top_n)
    )

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(imp_df["feature"][::-1], imp_df["importance"][::-1], color="#2196F3")
    ax.set_xlabel("Gain")
    ax.set_title(f"Top {top_n} Feature Importances (XGBoost)")
    plt.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)

    # Also save CSV
    csv_path = save_path.parent / "feature_importance.csv"
    imp_df.to_csv(csv_path, index=False)
    log.info("Saved feature importance → %s", save_path)


# ── CLI ─────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Train whale audio species classifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--backend",
        choices=["xgboost", "cnn"],
        default="xgboost",
        help="Classification backend (default: xgboost)",
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="Run Optuna hyperparameter tuning (XGBoost only)",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=50,
        help="Number of Optuna trials (default: 50)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=30,
        help="Training epochs (CNN only, default: 30)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size (CNN only, default: 32)",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=1e-3,
        help="Learning rate (CNN only, default: 1e-3)",
    )
    parser.add_argument(
        "--max-files-per-species",
        type=int,
        default=None,
        help="Limit files per species for faster iteration",
    )
    parser.add_argument(
        "--max-segments-per-species",
        type=int,
        default=_DEFAULT_MAX_SEGMENTS_PER_SPECIES,
        help=(
            "Cap segments per species to keep training"
            f" balanced (default: {_DEFAULT_MAX_SEGMENTS_PER_SPECIES})"
        ),
    )
    parser.add_argument(
        "--augment-target",
        type=int,
        default=_DEFAULT_AUGMENT_TARGET,
        help=(
            "Augment species below this segment count"
            f" (default: {_DEFAULT_AUGMENT_TARGET})."
            " Set to 0 to disable."
        ),
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Skip downloads, just rebuild the training manifest from existing files",
    ) if False else None  # kept for reference; not used in this script
    parser.add_argument(
        "--stage",
        choices=["critical", "broad", "rare"],
        default="critical",
        help=(
            "Training stage: 'critical' trains the 9-species ESA large-whale "
            "model incl. bowhead (default). 'broad' trains the ~14-species "
            "non-critical cetacean model. 'rare' builds mean embedding vectors "
            "for rare species using the trained broad model backbone and saves "
            "them to AUDIO_RARE_EMBEDDINGS_DIR."
        ),
    )
    parser.add_argument(
        "--features-path",
        type=str,
        default=None,
        help="Path to pre-extracted features parquet (skip extraction)",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Only extract features, don't train",
    )
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Load existing model and evaluate on test data",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    t0 = time.time()

    # Extract features
    if args.features_path:
        features_df = pd.read_parquet(args.features_path)
        log.info(
            "Loaded features from %s: %d rows", args.features_path, len(features_df)
        )
    else:
        features_df = extract_training_features(
            max_files_per_species=args.max_files_per_species,
            max_segments_per_species=args.max_segments_per_species,
            augment_target=args.augment_target,
        )

    if args.extract_only:
        log.info("Feature extraction complete — exiting (--extract-only)")
        return

    if features_df.empty:
        log.error(
            "No training features available. Run download_whale_audio.py first "
            "to download training data."
        )
        return

    # Evaluate existing model
    if args.evaluate_only:
        from pipeline.audio.classify import WhaleAudioClassifier

        clf = WhaleAudioClassifier.load()
        preds = clf.predict_features(
            features_df.drop(
                columns=["file", "segment_idx", "start_sec", "end_sec", "species"],
                errors="ignore",
            )
        )
        log.info(
            "Predictions:\n%s", preds["predicted_species"].value_counts().to_string()
        )
        return

    # Resolve stage-specific model dir and experiment name
    if args.stage == "broad":
        stage_model_dir: Path = AUDIO_BROAD_MODEL_DIR
        stage_experiment = "whale_audio_classifier_broad"
        log.info(
            "Stage: broad — saving to %s, experiment '%s'",
            stage_model_dir,
            stage_experiment,
        )
    elif args.stage == "rare":
        # ── Rare stage: build embedding library from broad model ──────────
        log.info(
            "Stage: rare — building mean embedding library "
            "from broad XGBoost model backbone"
        )
        from pipeline.audio.classify import RareEmbeddingAudioClassifier

        rare_species = WHALE_AUDIO_RARE_SPECIES

        # Reuse extracted feature matrix; filter to rare species only
        rare_features = {
            sp: features_df[features_df["species"] == sp].drop(
                columns=["file", "segment_idx", "start_sec", "end_sec", "species"],
                errors="ignore",
            )
            for sp in rare_species
            if sp in features_df["species"].values
        }
        missing_rare = set(rare_species) - set(rare_features)
        if missing_rare:
            log.warning(
                "Rare species not found in features: %s — "
                "download and extract their audio first.",
                ", ".join(sorted(missing_rare)),
            )
        if not rare_features:
            log.error(
                "No rare-species segments found. "
                "Run download_whale_audio.py --stage rare and re-extract features."
            )
            return

        embedder = RareEmbeddingAudioClassifier(library={})
        embedder.build_library(
            features_by_species=rare_features,
            save_dir=AUDIO_RARE_EMBEDDINGS_DIR,
        )
        log.info(
            "Rare embedding library built for %d species → %s",
            len(rare_features),
            AUDIO_RARE_EMBEDDINGS_DIR,
        )
        elapsed = time.time() - t0
        log.info("Rare stage complete in %.1f s", elapsed)
        return
    else:
        stage_model_dir = AUDIO_MODEL_DIR
        stage_experiment = EXPERIMENT_NAME
        log.info("Stage: critical (default)")

    # Train
    if args.backend == "xgboost":
        clf = train_xgboost(
            features_df,
            tune=args.tune,
            n_trials=args.n_trials,
            model_dir=stage_model_dir,
            experiment_name=stage_experiment,
        )
    elif args.backend == "cnn":
        clf = train_cnn(
            features_df,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            model_dir=stage_model_dir,
            experiment_name=stage_experiment,
        )

    elapsed = time.time() - t0
    log.info("Training complete in %.1f s", elapsed)
    log.info("Model saved to %s", stage_model_dir)


if __name__ == "__main__":
    main()

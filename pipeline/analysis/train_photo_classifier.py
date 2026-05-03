"""Train a whale species photo classifier (EfficientNet-B4).

Fine-tunes an ImageNet-pretrained EfficientNet-B4 on Happywhale images
filtered to the 8 target whale species.  Uses differential learning
rates (lower for backbone, higher for head), CosineAnnealing scheduler,
weighted random sampling, and early stopping on validation macro F1.

Logs metrics and artefacts to MLflow (experiment: ``whale_photo_classifier``).

Usage
-----
    # Default training
    uv run python pipeline/analysis/train_photo_classifier.py

    # With Optuna hyperparameter tuning
    uv run python pipeline/analysis/train_photo_classifier.py --tune

    # Custom epochs / batch size
    uv run python pipeline/analysis/train_photo_classifier.py \\
        --epochs 20 --batch-size 16

    # Evaluate an existing model
    uv run python pipeline/analysis/train_photo_classifier.py --evaluate-only
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.config import (
    ML_DIR,
    MLFLOW_TRACKING_URI,
    PHOTO_BACKBONE_FREEZE_EPOCHS,
    PHOTO_BATCH_SIZE,
    PHOTO_BROAD_MODEL_DIR,
    PHOTO_EARLY_STOP_PATIENCE,
    PHOTO_EPOCHS,
    PHOTO_IMAGE_SIZE,
    PHOTO_LABEL_SMOOTHING,
    PHOTO_LR_BACKBONE,
    PHOTO_LR_HEAD,
    PHOTO_MODEL_DIR,
    PHOTO_RARE_EMBEDDINGS_DIR,
    WHALE_PHOTO_BROAD_TARGET_SPECIES,
    WHALE_PHOTO_RARE_SPECIES,
    WHALE_PHOTO_RAW_DIR,
    WHALE_PHOTO_SPECIES,
)

log = logging.getLogger(__name__)

EXPERIMENT_NAME = "whale_photo_classifier"
ARTIFACTS_DIR = ML_DIR / "artifacts" / "photo_classifier"


# ── Data loading ────────────────────────────────────────────


def load_training_data(
    manifest_path: Path | None = None,
) -> pd.DataFrame:
    """Load the training manifest created by download_whale_photos.py.

    Returns DataFrame with columns: image, species, file_path.
    """
    manifest_path = manifest_path or WHALE_PHOTO_RAW_DIR / "training_manifest.csv"

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Training manifest not found at {manifest_path}. "
            "Run download_whale_photos.py first."
        )

    df = pd.read_csv(manifest_path)
    if "source" not in df.columns:
        df["source"] = "happywhale"

    # Optionally merge in iNaturalist supplementary photos
    inat_manifest = WHALE_PHOTO_RAW_DIR / "inat_manifest.csv"
    if inat_manifest.exists():
        inat_df = pd.read_csv(inat_manifest)
        # Align columns: (image, species, individual_id, file_path, source)
        if not inat_df.empty:
            inat_df = inat_df.rename(columns={"photo_id": "individual_id"})
            inat_df["image"] = inat_df["file_path"].apply(lambda p: Path(p).name)
            keep = ["image", "species", "individual_id", "file_path", "source"]
            inat_df = inat_df[[c for c in keep if c in inat_df.columns]]
            df = pd.concat([df, inat_df], ignore_index=True)
            log.info(
                "Merged iNat manifest: +%d photos (now %d total)",
                len(inat_df),
                len(df),
            )

    # Validate file paths exist
    valid = df["file_path"].apply(lambda p: Path(p).exists())
    n_missing = (~valid).sum()
    if n_missing > 0:
        log.warning("%d images missing on disk — dropping", n_missing)
        df = df[valid].reset_index(drop=True)

    log.info(
        "Loaded manifest: %d images, %d species (sources: %s)",
        len(df),
        df["species"].nunique(),
        df["source"].value_counts().to_dict(),
    )
    return df


# ── Training loop ───────────────────────────────────────────


def train_model(
    df: pd.DataFrame,
    epochs: int = PHOTO_EPOCHS,
    batch_size: int = PHOTO_BATCH_SIZE,
    lr_head: float = PHOTO_LR_HEAD,
    lr_backbone: float = PHOTO_LR_BACKBONE,
    label_smoothing: float = PHOTO_LABEL_SMOOTHING,
    patience: int = PHOTO_EARLY_STOP_PATIENCE,
    tune: bool = False,
    n_trials: int = 30,
    model_dir: Path | None = None,
    experiment_name: str | None = None,
) -> None:
    """Train EfficientNet-B4 on whale photos.

    Uses 80/20 stratified split, weighted random sampling,
    differential LR, cosine annealing, and early stopping.
    Logs everything to MLflow.

    Parameters
    ----------
    model_dir :
        Directory to save model + metadata.  Defaults to
        ``PHOTO_MODEL_DIR`` (critical stage).  Pass
        ``PHOTO_BROAD_MODEL_DIR`` for the broad stage.
    experiment_name :
        MLflow experiment name.  Defaults to ``EXPERIMENT_NAME``.
    """
    import mlflow
    import torch
    import torch.nn as nn
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
    )
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder
    from torch.utils.data import DataLoader, WeightedRandomSampler

    from pipeline.photo.classify import (
        WhalePhotoClassifier,
        build_efficientnet_b4,
    )
    from pipeline.photo.preprocess import (
        WhalePhotoDataset,
        compute_sample_weights,
        get_train_transforms,
        get_val_transforms,
    )

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(experiment_name or EXPERIMENT_NAME)

    # ── Encode labels ────────────────────────────────────────
    # Fit on the species actually present in df (works for both critical
    # and broad stages, since the caller pre-filters the manifest).
    le = LabelEncoder()
    le.fit(sorted(df["species"].unique()))
    labels = le.transform(df["species"].values)
    label_map = {i: s for i, s in enumerate(le.classes_)}
    n_classes = len(label_map)
    image_paths = [Path(p) for p in df["file_path"].values]

    log.info(
        "Training data: %d images, %d classes",
        len(image_paths),
        n_classes,
    )
    for i, cls_name in label_map.items():
        n = (labels == i).sum()
        log.info("  Class %d: %-20s %d images", i, cls_name, n)

    # ── Train/val split ──────────────────────────────────────
    (
        train_paths,
        val_paths,
        train_labels,
        val_labels,
    ) = train_test_split(
        image_paths,
        labels,
        test_size=0.2,
        stratify=labels,
        random_state=42,
    )

    log.info(
        "Split: %d train, %d val",
        len(train_paths),
        len(val_paths),
    )

    # ── Device ───────────────────────────────────────────────
    device = _get_device()

    # ── Datasets & loaders ───────────────────────────────────
    train_ds = WhalePhotoDataset(train_paths, train_labels, get_train_transforms())
    val_ds = WhalePhotoDataset(val_paths, val_labels, get_val_transforms())

    # Weighted random sampler for balanced batches
    sample_weights = compute_sample_weights(train_labels, n_classes)
    sampler = WeightedRandomSampler(
        weights=sample_weights,
        num_samples=len(train_labels),
        replacement=True,
    )

    # MPS doesn't support pin_memory and has worker contention
    is_mps = str(device) == "mps"
    pin = not is_mps
    n_workers = 2 if is_mps else 4

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        sampler=sampler,
        num_workers=n_workers,
        pin_memory=pin,
        persistent_workers=True,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=n_workers,
        pin_memory=pin,
        persistent_workers=True,
    )

    # ── Model, optimizer, scheduler ──────────────────────────
    model = build_efficientnet_b4(n_classes).to(device)

    # Differential LR: lower for pretrained backbone
    backbone_params = []
    head_params = []
    for name, param in model.named_parameters():
        if "classifier" in name:
            head_params.append(param)
        else:
            backbone_params.append(param)

    if tune:
        lr_head, lr_backbone, label_smoothing = _optuna_tune(
            train_ds,
            val_ds,
            n_classes,
            device,
            n_trials=n_trials,
        )
        log.info(
            "Optuna best: lr_head=%.2e, lr_backbone=%.2e, label_smoothing=%.2f",
            lr_head,
            lr_backbone,
            label_smoothing,
        )

    optimizer = torch.optim.AdamW(
        [
            {"params": backbone_params, "lr": lr_backbone},
            {"params": head_params, "lr": lr_head},
        ],
        weight_decay=0.01,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.CrossEntropyLoss(label_smoothing=label_smoothing)

    # Mixed precision — MPS supports float16 autocast
    use_amp = str(device) in ("mps", "cuda")
    scaler = torch.amp.GradScaler(enabled=(str(device) == "cuda"))
    amp_dtype = torch.float16
    log.info(
        "Mixed precision: %s  image_size: %d  backbone_freeze_epochs: %d",
        use_amp,
        PHOTO_IMAGE_SIZE,
        PHOTO_BACKBONE_FREEZE_EPOCHS,
    )

    # Freeze backbone for first N epochs (head warmup)
    def _set_backbone_frozen(frozen: bool) -> None:
        for param in backbone_params:
            param.requires_grad = not frozen
        state = "frozen" if frozen else "unfrozen"
        log.info("Backbone %s", state)

    if PHOTO_BACKBONE_FREEZE_EPOCHS > 0:
        _set_backbone_frozen(True)

    # ── Training loop ────────────────────────────────────────
    best_f1 = 0.0
    best_epoch = 0
    best_state = None
    patience_counter = 0

    with mlflow.start_run(run_name="efficientnet_b4_photo"):
        mlflow.log_params(
            {
                "epochs": epochs,
                "batch_size": batch_size,
                "lr_head": lr_head,
                "lr_backbone": lr_backbone,
                "label_smoothing": label_smoothing,
                "n_classes": n_classes,
                "n_train": len(train_paths),
                "n_val": len(val_paths),
                "patience": patience,
                "backend": "efficientnet_b4",
            }
        )

        for epoch in range(epochs):
            # Unfreeze backbone after warmup epochs
            if (
                epoch == PHOTO_BACKBONE_FREEZE_EPOCHS
                and PHOTO_BACKBONE_FREEZE_EPOCHS > 0
            ):
                _set_backbone_frozen(False)

            # ── Train phase ──────────────────────────────────
            model.train()
            train_loss = 0.0
            train_correct = 0
            train_total = 0
            epoch_start = time.time()
            n_batches = len(train_loader)
            log_every = max(1, n_batches // 10)  # ~10 updates per epoch

            for batch_idx, (images, targets) in enumerate(train_loader):
                images = images.to(device)
                targets = targets.to(device)

                optimizer.zero_grad()
                with torch.autocast(
                    device_type=str(device),
                    dtype=amp_dtype,
                    enabled=use_amp,
                ):
                    outputs = model(images)
                    loss = criterion(outputs, targets)

                if str(device) == "cuda":
                    scaler.scale(loss).backward()
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    loss.backward()
                    optimizer.step()

                train_loss += loss.item() * images.size(0)
                _, predicted = outputs.max(1)
                train_total += targets.size(0)
                train_correct += predicted.eq(targets).sum().item()

                if (batch_idx + 1) % log_every == 0 or batch_idx == 0:
                    elapsed = time.time() - epoch_start
                    pct = 100.0 * (batch_idx + 1) / n_batches
                    batch_acc = train_correct / train_total
                    eta = elapsed / (batch_idx + 1) * (n_batches - batch_idx - 1)
                    log.info(
                        "  Epoch %d  batch %d/%d (%4.1f%%)  "
                        "loss=%.4f  acc=%.4f  "
                        "elapsed=%.0fs  ETA=%.0fs",
                        epoch + 1,
                        batch_idx + 1,
                        n_batches,
                        pct,
                        train_loss / train_total,
                        batch_acc,
                        elapsed,
                        eta,
                    )

            scheduler.step()

            train_loss /= train_total
            train_acc = train_correct / train_total

            # ── Validation phase ─────────────────────────────
            model.eval()
            val_loss = 0.0
            val_preds = []
            val_true = []

            with torch.no_grad():
                for images, targets in val_loader:
                    images = images.to(device)
                    targets = targets.to(device)
                    with torch.autocast(
                        device_type=str(device),
                        dtype=amp_dtype,
                        enabled=use_amp,
                    ):
                        outputs = model(images)
                        loss = criterion(outputs, targets)

                    val_loss += loss.item() * images.size(0)
                    _, predicted = outputs.max(1)
                    val_preds.extend(predicted.cpu().numpy())
                    val_true.extend(targets.cpu().numpy())

            val_loss /= len(val_labels)
            val_acc = accuracy_score(val_true, val_preds)
            val_f1 = f1_score(val_true, val_preds, average="macro")
            epoch_elapsed = time.time() - epoch_start

            # Log metrics
            mlflow.log_metrics(
                {
                    "train_loss": train_loss,
                    "train_acc": train_acc,
                    "val_loss": val_loss,
                    "val_acc": val_acc,
                    "val_macro_f1": val_f1,
                },
                step=epoch,
            )

            log.info(
                "Epoch %2d/%d  "
                "train_loss=%.4f  train_acc=%.4f  "
                "val_loss=%.4f  val_acc=%.4f  "
                "val_f1=%.4f  [%.0fs]",
                epoch + 1,
                epochs,
                train_loss,
                train_acc,
                val_loss,
                val_acc,
                val_f1,
                epoch_elapsed,
            )

            # ── Early stopping ───────────────────────────────
            if val_f1 > best_f1:
                best_f1 = val_f1
                best_epoch = epoch + 1
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
                patience_counter = 0
                log.info(
                    "  ↑ New best val F1: %.4f at epoch %d",
                    best_f1,
                    best_epoch,
                )
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    log.info(
                        "Early stopping at epoch %d (best F1 %.4f at epoch %d)",
                        epoch + 1,
                        best_f1,
                        best_epoch,
                    )
                    break

        # ── Restore best model & evaluate ────────────────────
        if best_state is not None:
            model.load_state_dict(best_state)
            model.to(device)

        model.eval()
        final_preds = []
        final_true = []
        final_proba = []

        with torch.no_grad():
            for images, targets in val_loader:
                images = images.to(device)
                outputs = model(images)
                proba = torch.softmax(outputs, dim=1)
                _, predicted = outputs.max(1)
                final_preds.extend(predicted.cpu().numpy())
                final_true.extend(targets.numpy())
                final_proba.extend(proba.cpu().numpy())

        final_acc = accuracy_score(final_true, final_preds)
        final_f1 = f1_score(final_true, final_preds, average="macro")
        final_wf1 = f1_score(final_true, final_preds, average="weighted")

        mlflow.log_metrics(
            {
                "best_epoch": best_epoch,
                "best_val_macro_f1": best_f1,
                "final_val_accuracy": final_acc,
                "final_val_macro_f1": final_f1,
                "final_val_weighted_f1": final_wf1,
            }
        )

        log.info("Best epoch: %d", best_epoch)
        log.info("Final val accuracy: %.4f", final_acc)
        log.info("Final val macro F1: %.4f", final_f1)

        # Classification report
        target_names = [label_map[i] for i in range(n_classes)]
        report = classification_report(
            final_true,
            final_preds,
            target_names=target_names,
        )
        log.info("\n%s", report)

        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = ARTIFACTS_DIR / "classification_report.txt"
        report_path.write_text(report)
        mlflow.log_artifact(str(report_path))

        # Confusion matrix
        cm = confusion_matrix(final_true, final_preds)
        _plot_confusion_matrix(
            cm,
            target_names,
            ARTIFACTS_DIR / "confusion_matrix.png",
        )
        mlflow.log_artifact(str(ARTIFACTS_DIR / "confusion_matrix.png"))

        # Per-class metrics CSV
        _save_per_class_metrics(
            final_true,
            final_preds,
            target_names,
            ARTIFACTS_DIR / "per_class_metrics.csv",
        )
        mlflow.log_artifact(str(ARTIFACTS_DIR / "per_class_metrics.csv"))

        # Save model
        save_dir = model_dir or PHOTO_MODEL_DIR
        classifier = WhalePhotoClassifier(
            model=model,
            label_encoder=label_map,
        )
        model_path = classifier.save(save_dir)
        mlflow.log_artifact(str(model_path))
        mlflow.log_artifact(str(save_dir / "model_metadata.json"))

        log.info("Model saved to %s", save_dir)


# ── Optuna tuning ───────────────────────────────────────────


def _optuna_tune(
    train_ds: object,
    val_ds: object,
    n_classes: int,
    device: object,
    n_trials: int = 30,
) -> tuple[float, float, float]:
    """Bayesian hyperparameter search with Optuna.

    Tunes lr_head, lr_backbone, and label_smoothing over short
    (5-epoch) runs.  Returns best values.
    """
    import optuna
    import torch
    import torch.nn as nn
    from sklearn.metrics import f1_score
    from torch.utils.data import DataLoader

    from pipeline.photo.classify import build_efficientnet_b4

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial: optuna.Trial) -> float:
        lr_h = trial.suggest_float("lr_head", 1e-5, 1e-3, log=True)
        lr_b = trial.suggest_float("lr_backbone", 1e-6, 1e-4, log=True)
        ls = trial.suggest_float("label_smoothing", 0.0, 0.2)

        model = build_efficientnet_b4(n_classes).to(device)

        backbone_params = []
        head_params = []
        for name, param in model.named_parameters():
            if "classifier" in name:
                head_params.append(param)
            else:
                backbone_params.append(param)

        optim = torch.optim.AdamW(
            [
                {"params": backbone_params, "lr": lr_b},
                {"params": head_params, "lr": lr_h},
            ],
            weight_decay=0.01,
        )
        crit = nn.CrossEntropyLoss(label_smoothing=ls)

        train_loader = DataLoader(
            train_ds,
            batch_size=PHOTO_BATCH_SIZE,
            shuffle=True,
            num_workers=2,
        )
        val_loader = DataLoader(
            val_ds,
            batch_size=PHOTO_BATCH_SIZE,
            shuffle=False,
            num_workers=2,
        )

        # Short training (5 epochs)
        for _epoch in range(5):
            model.train()
            for images, targets in train_loader:
                images = images.to(device)
                targets = targets.to(device)
                optim.zero_grad()
                loss = crit(model(images), targets)
                loss.backward()
                optim.step()

        # Evaluate
        model.eval()
        all_preds = []
        all_true = []
        with torch.no_grad():
            for images, targets in val_loader:
                images = images.to(device)
                outputs = model(images)
                _, preds = outputs.max(1)
                all_preds.extend(preds.cpu().numpy())
                all_true.extend(targets.numpy())

        return f1_score(all_true, all_preds, average="macro")

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)

    best = study.best_params
    log.info("Optuna best params: %s", best)

    return (
        best["lr_head"],
        best["lr_backbone"],
        best["label_smoothing"],
    )


# ── Plotting helpers ────────────────────────────────────────


def _plot_confusion_matrix(
    cm: np.ndarray,
    labels: list[str],
    output_path: Path,
) -> None:
    """Save a confusion matrix heatmap."""
    import matplotlib

    matplotlib.use("Agg")
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
    ax.set_title("Photo Classifier — Confusion Matrix")
    plt.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    log.info("Saved confusion matrix: %s", output_path)


def _save_per_class_metrics(
    y_true: list[int],
    y_pred: list[int],
    target_names: list[str],
    output_path: Path,
) -> None:
    """Save per-class precision, recall, F1 to CSV."""
    from sklearn.metrics import (
        f1_score,
        precision_score,
        recall_score,
    )

    records = []
    for i, name in enumerate(target_names):
        mask_true = np.array(y_true) == i
        mask_pred = np.array(y_pred) == i
        records.append(
            {
                "species": name,
                "n_true": int(mask_true.sum()),
                "n_pred": int(mask_pred.sum()),
                "precision": precision_score(
                    y_true,
                    y_pred,
                    labels=[i],
                    average="macro",
                    zero_division=0,
                ),
                "recall": recall_score(
                    y_true,
                    y_pred,
                    labels=[i],
                    average="macro",
                    zero_division=0,
                ),
                "f1": f1_score(
                    y_true,
                    y_pred,
                    labels=[i],
                    average="macro",
                    zero_division=0,
                ),
            }
        )

    metrics_df = pd.DataFrame(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(output_path, index=False)
    log.info("Saved per-class metrics: %s", output_path)


# ── Device selection ────────────────────────────────────────


def _get_device() -> object:
    """Select best available device: MPS (Apple), CUDA, or CPU."""
    import torch

    if torch.backends.mps.is_available():
        device = torch.device("mps")
        log.info("Using Apple MPS device")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
        log.info("Using CUDA device")
    else:
        device = torch.device("cpu")
        log.info("Using CPU device")
    return device


# ── CLI ─────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Train EfficientNet-B4 whale photo species classifier on Happywhale data."
        ),
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=PHOTO_EPOCHS,
        help=f"Max epochs (default: {PHOTO_EPOCHS})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=PHOTO_BATCH_SIZE,
        help=f"Batch size (default: {PHOTO_BATCH_SIZE})",
    )
    parser.add_argument(
        "--lr-head",
        type=float,
        default=PHOTO_LR_HEAD,
        help=f"Head learning rate (default: {PHOTO_LR_HEAD})",
    )
    parser.add_argument(
        "--lr-backbone",
        type=float,
        default=PHOTO_LR_BACKBONE,
        help=(f"Backbone learning rate (default: {PHOTO_LR_BACKBONE})"),
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="Run Optuna hyperparameter tuning first",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=30,
        help="Number of Optuna trials (default: 30)",
    )
    parser.add_argument(
        "--stage",
        choices=["critical", "broad", "rare"],
        default="critical",
        help=(
            "Training stage: 'critical' trains the 8-class ESA-species model "
            "(default). 'broad' trains the 19-class non-critical cetacean model. "
            "'rare' builds mean EfficientNet-B4 embedding vectors for rare "
            "species from the trained broad model backbone."
        ),
    )
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Load existing model and evaluate on val data",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to training manifest CSV",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    t0 = time.time()

    # Load data
    manifest_path = Path(args.manifest) if args.manifest else None
    df = load_training_data(manifest_path)

    if df.empty:
        log.error("No training data available. Run download_whale_photos.py first.")
        return

    if args.evaluate_only:
        from pipeline.photo.classify import WhalePhotoClassifier

        clf = WhalePhotoClassifier.load()
        results = clf.predict_batch([Path(p) for p in df["file_path"].values[:100]])
        species_counts = pd.Series(
            [r["predicted_species"] for r in results]
        ).value_counts()
        log.info(
            "Predictions (first 100):\n%s",
            species_counts.to_string(),
        )
        return

    # ── Stage routing ──────────────────────────────────────────────
    if args.stage == "rare":
        # Build mean embedding library from broad model backbone
        log.info(
            "Stage: rare — building mean embedding library "
            "from broad EfficientNet-B4 backbone"
        )
        from pipeline.photo.classify import (
            RareEmbeddingPhotoClassifier,
            WhalePhotoClassifier,
        )

        broad_clf = WhalePhotoClassifier.load(PHOTO_BROAD_MODEL_DIR)
        rare_species = WHALE_PHOTO_RARE_SPECIES

        # Build dict of species → list[Path] from manifest
        images_by_species: dict[str, list[Path]] = {
            sp: [Path(p) for p in df[df["species"] == sp]["file_path"].tolist()]
            for sp in rare_species
            if sp in df["species"].values
        }
        missing_rare = set(rare_species) - set(images_by_species)
        if missing_rare:
            log.warning(
                "Rare species not found in manifest: %s — download their images first.",
                ", ".join(sorted(missing_rare)),
            )
        if not images_by_species:
            log.error(
                "No rare-species images found in manifest. "
                "Run download_whale_photos.py --stage rare."
            )
            return

        embedder = RareEmbeddingPhotoClassifier(library={})
        embedder.build_library(
            model=broad_clf.model,
            images_by_species=images_by_species,
            save_dir=PHOTO_RARE_EMBEDDINGS_DIR,
        )
        log.info(
            "Rare embedding library built for %d species → %s",
            len(images_by_species),
            PHOTO_RARE_EMBEDDINGS_DIR,
        )
        elapsed = time.time() - t0
        log.info("Rare stage complete in %.1f s", elapsed)
        return

    if args.stage == "broad":
        stage_model_dir = PHOTO_BROAD_MODEL_DIR
        stage_experiment = EXPERIMENT_NAME + "_broad"
        # Filter manifest to broad species only
        broad_species = [
            s for s in WHALE_PHOTO_BROAD_TARGET_SPECIES if s != "unknown_cetacean"
        ]
        df = df[df["species"].isin(broad_species)].reset_index(drop=True)
        log.info(
            "Stage: broad — %d images, %d species",
            len(df),
            df["species"].nunique(),
        )
    else:
        stage_model_dir = PHOTO_MODEL_DIR
        stage_experiment = EXPERIMENT_NAME
        # Filter manifest to critical species only
        critical_species = [s for s in WHALE_PHOTO_SPECIES if s != "other_cetacean"]
        df = df[df["species"].isin(critical_species)].reset_index(drop=True)
        log.info(
            "Stage: critical — %d images, %d species",
            len(df),
            df["species"].nunique(),
        )

    # Train
    train_model(
        df,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr_head=args.lr_head,
        lr_backbone=args.lr_backbone,
        tune=args.tune,
        n_trials=args.n_trials,
        model_dir=stage_model_dir,
        experiment_name=stage_experiment,
    )

    elapsed = time.time() - t0
    log.info("Training complete in %.1f s", elapsed)
    log.info("Model saved to %s", stage_model_dir)


if __name__ == "__main__":
    main()

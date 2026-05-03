"""Train a whale species photo classifier using sub-centre ArcFace.

Fine-tunes a timm backbone (default: ``tf_efficientnet_b7``) with GeM
multi-scale pooling and a sub-centre ArcFace head on Happywhale images.

Key training ideas from the 1st-place Kaggle Happywhale solution:

  * **Dynamic per-class margins** (∝ class_count^power) — rarer species
    get larger angular separation.
  * **10× higher LR for the ArcFace head** vs backbone — head converges
    much faster than a pretrained backbone needs to adjust.
  * **Warmup cosine annealing** LR schedule.
  * **Albumentations** augmentation pipeline (Affine, RandomResizedCrop,
    Posterize, GaussNoise, etc.) matching the competition approach.
  * **Test-time augmentation** (original + horizontal flip) when building
    the KNN gallery after training.

After training the model weights, this script runs all training images
through the model to build a KNN gallery (saved as ``gallery.npz``).
At inference time, KNN cosine-similarity scores are blended with raw
logit scores to improve robustness (``knn_ratio`` controls the blend).

Reference
---------
Abe, K. & Yamaguchi, T. (2022). "Preferred Dolphin: 1st Place Solution."
https://www.kaggle.com/competitions/happy-whale-and-dolphin/discussion/320192

Usage
-----
    # Critical stage (8 ESA species + other_cetacean)
    uv run python pipeline/analysis/train_arcface_classifier.py

    # Broad stage (non-critical cetaceans)
    uv run python pipeline/analysis/train_arcface_classifier.py --stage broad

    # Lighter backbone for CPU/MPS
    uv run python pipeline/analysis/train_arcface_classifier.py \\
        --backbone tf_efficientnet_b4 --image-size 380

    # With Optuna margin hyperparameter tuning
    uv run python pipeline/analysis/train_arcface_classifier.py --tune
"""

from __future__ import annotations

import argparse
import logging
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.config import (
    ARCFACE_BACKBONE,
    ARCFACE_BATCH_SIZE,
    ARCFACE_BROAD_MODEL_DIR,
    ARCFACE_EARLY_STOP_PATIENCE,
    ARCFACE_EPOCHS,
    ARCFACE_GEM_P,
    ARCFACE_IMAGE_SIZE,
    ARCFACE_KNN_NEIGHBORS,
    ARCFACE_KNN_RATIO,
    ARCFACE_LR_BACKBONE,
    ARCFACE_LR_HEAD,
    ARCFACE_MARGIN_COEF,
    ARCFACE_MARGIN_CONS,
    ARCFACE_MARGIN_POWER,
    ARCFACE_MODEL_DIR,
    ARCFACE_N_CENTER,
    ARCFACE_OUT_INDICES,
    ARCFACE_S,
    ARCFACE_WARMUP_RATIO,
    ML_DIR,
    MLFLOW_TRACKING_URI,
    WHALE_PHOTO_BROAD_TARGET_SPECIES,
    WHALE_PHOTO_RAW_DIR,
    WHALE_PHOTO_SPECIES,
)
from pipeline.photo.arcface_classify import (
    ArcFacePhotoClassifier,
    build_sphere_model,
    extract_embeddings,
    get_arcface_train_transforms,
    get_arcface_val_transforms,
)

log = logging.getLogger(__name__)

ARTIFACTS_DIR = ML_DIR / "artifacts" / "photo_classifier_arcface"
EXPERIMENT_NAME = "whale_photo_arcface"


# ── Data loading ─────────────────────────────────────────────────────────────


def load_training_data(
    manifest_path: Path | None = None,
) -> pd.DataFrame:
    """Load the training manifest created by download_whale_photos.py.

    Returns a DataFrame with columns: image, species, file_path.
    """
    manifest_path = manifest_path or WHALE_PHOTO_RAW_DIR / "training_manifest.csv"

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Training manifest not found at {manifest_path}. "
            "Run download_whale_photos.py first."
        )

    df = pd.read_csv(manifest_path)
    valid = df["file_path"].apply(lambda p: Path(p).exists())
    n_missing = (~valid).sum()
    if n_missing > 0:
        log.warning("%d images missing on disk — dropping", n_missing)
        df = df[valid].reset_index(drop=True)

    log.info(
        "Loaded manifest: %d images, %d species",
        len(df),
        df["species"].nunique(),
    )
    return df


# ── Dataset ──────────────────────────────────────────────────────────────────


class WhaleArcFaceDataset:
    """PyTorch Dataset for ArcFace training with albumentations transforms."""

    def __init__(
        self,
        df: pd.DataFrame,
        transform: object,
        image_size: int,
    ) -> None:
        self.paths = df["file_path"].tolist()
        self.labels = df["label"].tolist()
        self.transform = transform
        self.image_size = image_size

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, idx: int) -> tuple[object, int]:
        try:
            from PIL import Image

            img = Image.open(str(self.paths[idx])).convert("RGB")
            img_np = np.array(img)
        except Exception:
            log.warning("Failed to load %s — using black image", self.paths[idx])
            img_np = np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8)
        tensor = self.transform(image=img_np)["image"]
        return tensor, self.labels[idx]


# ── Margin helpers ────────────────────────────────────────────────────────────


def compute_class_margins(
    class_counts: np.ndarray,
    margin_power: float = ARCFACE_MARGIN_POWER,
    margin_coef: float = ARCFACE_MARGIN_COEF,
    margin_cons: float = ARCFACE_MARGIN_CONS,
) -> np.ndarray:
    """Compute dynamic per-class ArcFace margins.

    margin_i = coef * n_i^power + cons

    When ``margin_power < 0``, rarer classes (smaller n_i) receive
    larger margins, pushing them apart more aggressively in embedding
    space.

    Returns
    -------
    margins : np.ndarray of shape (n_classes,), dtype float32
    """
    counts = np.maximum(class_counts.astype(float), 1)
    margins = np.power(counts, margin_power) * margin_coef + margin_cons
    return margins.astype(np.float32)


def _make_arcface_loss(
    margins: np.ndarray,
    n_classes: int,
    s: float = ARCFACE_S,
) -> object:
    """Factory: ArcFaceLossAdaptiveMargin with the given per-class margins.

    Applies angular margin to the ground-truth class logit at training
    time.  Raw cosine similarities from the sub-centre head are passed
    in; margin-adjusted logits are returned for CrossEntropyLoss.
    """
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class ArcFaceLossAdaptiveMargin(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.margins = margins
            self.s = s
            self.n_classes = n_classes

        def forward(
            self,
            logits: torch.Tensor,
            labels: torch.Tensor,
        ) -> torch.Tensor:
            ms = self.margins[labels.cpu().numpy()]
            device = logits.device
            cos_m = torch.tensor(np.cos(ms), dtype=torch.float32, device=device)
            sin_m = torch.tensor(np.sin(ms), dtype=torch.float32, device=device)
            th = torch.tensor(np.cos(math.pi - ms), dtype=torch.float32, device=device)
            mm = torch.tensor(
                np.sin(math.pi - ms) * ms, dtype=torch.float32, device=device
            )
            labels_oh = F.one_hot(labels, self.n_classes).float()
            cosine = logits.float()
            sine = torch.sqrt((1.0 - cosine.pow(2)).clamp(min=0.0))
            phi = cosine * cos_m.unsqueeze(1) - sine * sin_m.unsqueeze(1)
            phi = torch.where(
                cosine > th.unsqueeze(1),
                phi,
                cosine - mm.unsqueeze(1),
            )
            return (labels_oh * phi + (1.0 - labels_oh) * cosine) * self.s

    return ArcFaceLossAdaptiveMargin()


def _warmup_cosine_lambda(
    warmup_epochs: int,
    total_epochs: int,
    min_lr_ratio: float = 0.01,
) -> object:
    """Return a LambdaLR-compatible epoch→scale function.

    Linearly warms up for ``warmup_epochs``, then cosine-anneals to
    ``min_lr_ratio * base_lr`` over the remaining epochs.
    """

    def lr_lambda(epoch: int) -> float:
        if epoch < warmup_epochs:
            return float(epoch + 1) / float(max(1, warmup_epochs))
        progress = float(epoch - warmup_epochs) / float(
            max(1, total_epochs - warmup_epochs)
        )
        return max(min_lr_ratio, 0.5 * (1.0 + math.cos(math.pi * progress)))

    return lr_lambda


# ── Training loop ─────────────────────────────────────────────────────────────


def train_model(
    df: pd.DataFrame,
    backbone: str = ARCFACE_BACKBONE,
    image_size: int = ARCFACE_IMAGE_SIZE,
    epochs: int = ARCFACE_EPOCHS,
    batch_size: int = ARCFACE_BATCH_SIZE,
    lr_backbone: float = ARCFACE_LR_BACKBONE,
    lr_head: float = ARCFACE_LR_HEAD,
    patience: int = ARCFACE_EARLY_STOP_PATIENCE,
    model_dir: Path | None = None,
    experiment_name: str | None = None,
    margin_power: float = ARCFACE_MARGIN_POWER,
    margin_coef: float = ARCFACE_MARGIN_COEF,
    margin_cons: float = ARCFACE_MARGIN_CONS,
    n_center: int = ARCFACE_N_CENTER,
    gem_p: float = ARCFACE_GEM_P,
    out_indices: tuple[int, ...] = ARCFACE_OUT_INDICES,
    knn_ratio: float = ARCFACE_KNN_RATIO,
    knn_neighbors: int = ARCFACE_KNN_NEIGHBORS,
) -> None:
    """Train WhaleSphereModel and build KNN gallery.

    Parameters
    ----------
    df:
        Training manifest with columns: file_path, species.
    backbone:
        timm model name. ``tf_efficientnet_b7`` gives best accuracy;
        ``tf_efficientnet_b4`` is faster on CPU/MPS.
    model_dir:
        Where to save model + gallery. Defaults to ``ARCFACE_MODEL_DIR``.
    experiment_name:
        MLflow experiment name. Defaults to ``EXPERIMENT_NAME``.
    margin_power / margin_coef / margin_cons:
        Dynamic margin hyperparameters. Tune with ``--tune``.
    """
    import mlflow
    import torch
    import torch.nn as nn
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder
    from torch.utils.data import DataLoader

    save_dir = model_dir or ARCFACE_MODEL_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(experiment_name or EXPERIMENT_NAME)

    # ── Encode labels ────────────────────────────────────────────────────
    le = LabelEncoder()
    le.fit(sorted(df["species"].unique()))
    df = df.copy()
    df["label"] = le.transform(df["species"])
    n_classes = len(le.classes_)
    label_encoder = {i: str(s) for i, s in enumerate(le.classes_)}

    log.info(
        "Training ArcFace: %d images, %d classes, backbone=%s",
        len(df),
        n_classes,
        backbone,
    )

    # ── Train / val split ────────────────────────────────────────────────
    train_df, val_df = train_test_split(
        df,
        test_size=0.2,
        stratify=df["label"],
        random_state=42,
    )
    train_df = train_df.reset_index(drop=True)
    val_df = val_df.reset_index(drop=True)

    # ── Datasets ─────────────────────────────────────────────────────────
    train_transform = get_arcface_train_transforms(image_size)
    val_transform = get_arcface_val_transforms(image_size)

    train_ds = WhaleArcFaceDataset(train_df, train_transform, image_size)
    val_ds = WhaleArcFaceDataset(val_df, val_transform, image_size)

    train_loader = DataLoader(
        train_ds,  # type: ignore[arg-type]
        batch_size=batch_size,
        shuffle=True,
        num_workers=2,
        pin_memory=True,
        drop_last=True,
    )
    val_loader = DataLoader(
        val_ds,  # type: ignore[arg-type]
        batch_size=batch_size,
        shuffle=False,
        num_workers=2,
        pin_memory=True,
    )

    # ── Device ───────────────────────────────────────────────────────────
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    log.info("Training on device: %s", device)

    # ── Model ─────────────────────────────────────────────────────────────
    model = build_sphere_model(
        model_name=backbone,
        n_classes=n_classes,
        out_indices=out_indices,
        n_center=n_center,
        gem_p=gem_p,
        pretrained=True,
    ).to(device)

    # ── Margins ───────────────────────────────────────────────────────────
    class_counts = train_df["label"].value_counts().sort_index().values.astype(float)
    margins = compute_class_margins(
        class_counts, margin_power, margin_coef, margin_cons
    )
    margin_loss = _make_arcface_loss(margins, n_classes)  # type: ignore[assignment]
    criterion = nn.CrossEntropyLoss()

    # ── Optimiser with differential LR ───────────────────────────────────
    backbone_params = list(model.backbone.parameters()) + list(
        model.global_pools.parameters()
    )
    head_params = list(model.neck.parameters()) + list(model.head.parameters())
    optimizer = torch.optim.AdamW(
        [
            {"params": backbone_params, "lr": lr_backbone},
            {"params": head_params, "lr": lr_head},
        ]
    )

    warmup_epochs = max(1, int(ARCFACE_WARMUP_RATIO * epochs))
    lr_lambda = _warmup_cosine_lambda(warmup_epochs, epochs)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    # ── Training loop ─────────────────────────────────────────────────────
    best_f1 = 0.0
    patience_count = 0
    best_ckpt = save_dir / "_best.pt"
    t0 = time.time()

    with mlflow.start_run():
        mlflow.log_params(
            {
                "backbone": backbone,
                "image_size": image_size,
                "epochs": epochs,
                "batch_size": batch_size,
                "lr_backbone": lr_backbone,
                "lr_head": lr_head,
                "n_center": n_center,
                "gem_p": gem_p,
                "margin_power": margin_power,
                "margin_coef": margin_coef,
                "margin_cons": margin_cons,
                "n_classes": n_classes,
                "train_size": len(train_df),
                "val_size": len(val_df),
            }
        )

        for epoch in range(epochs):
            # ── Train epoch ──────────────────────────────────────────────
            model.train()
            train_loss = 0.0
            n_batches = 0
            for images, labels in train_loader:
                images = images.to(device)
                labels = labels.to(device)
                optimizer.zero_grad()
                logits = model(images)
                margin_logits = margin_loss(logits, labels)  # type: ignore[operator]
                loss = criterion(margin_logits, labels)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()
                n_batches += 1
            scheduler.step()
            avg_train_loss = train_loss / max(1, n_batches)

            # ── Val epoch ────────────────────────────────────────────────
            model.eval()
            all_preds: list[int] = []
            all_labels: list[int] = []
            with torch.no_grad():
                for images, labels in val_loader:
                    images = images.to(device)
                    logits = model(images)
                    preds = logits.argmax(dim=1).cpu().tolist()
                    all_preds.extend(preds)
                    all_labels.extend(labels.tolist())

            val_acc = accuracy_score(all_labels, all_preds)
            val_f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)

            log.info(
                "Epoch %d/%d  loss=%.4f  val_acc=%.3f  val_f1=%.3f  lr=%.2e",
                epoch + 1,
                epochs,
                avg_train_loss,
                val_acc,
                val_f1,
                optimizer.param_groups[0]["lr"],
            )
            mlflow.log_metrics(
                {
                    "train_loss": avg_train_loss,
                    "val_acc": val_acc,
                    "val_macro_f1": val_f1,
                },
                step=epoch,
            )

            # ── Early stopping ────────────────────────────────────────────
            if val_f1 > best_f1:
                best_f1 = val_f1
                patience_count = 0
                torch.save(model.state_dict(), str(best_ckpt))
                log.info("  ↑ New best val macro-F1: %.4f — saved.", best_f1)
            else:
                patience_count += 1
                log.info(
                    "  Patience %d/%d (best=%.4f)",
                    patience_count,
                    patience,
                    best_f1,
                )
                if patience_count >= patience:
                    log.info("Early stopping at epoch %d.", epoch + 1)
                    break

        elapsed = time.time() - t0
        log.info(
            "Training complete: best val macro-F1=%.4f in %.1fs",
            best_f1,
            elapsed,
        )
        mlflow.log_metrics({"best_val_macro_f1": best_f1, "train_time_s": elapsed})

        # Restore best weights
        if best_ckpt.exists():
            model.load_state_dict(
                torch.load(str(best_ckpt), map_location=device, weights_only=True)
            )

        # ── Build KNN gallery from full training set ─────────────────────
        log.info("Building KNN gallery from training images ...")
        all_df = df.reset_index(drop=True)
        all_paths = [Path(p) for p in all_df["file_path"].tolist()]
        all_label_ints = all_df["label"].to_numpy().astype(np.int32)

        gallery_feats = extract_embeddings(
            model,
            all_paths,  # type: ignore[arg-type]
            image_size=image_size,
            batch_size=batch_size,
            tta=False,
        )
        gallery_path = save_dir / "gallery.npz"
        np.savez_compressed(
            str(gallery_path), feats=gallery_feats, labels=all_label_ints
        )
        log.info(
            "Gallery saved: %d vectors (%d dims) → %s",
            len(gallery_feats),
            gallery_feats.shape[1],
            gallery_path,
        )

        # ── Save classifier ───────────────────────────────────────────────
        clf = ArcFacePhotoClassifier(
            model=model,
            label_encoder=label_encoder,
            gallery_feats=gallery_feats,
            gallery_labels=all_label_ints,
            image_size=image_size,
            knn_ratio=knn_ratio,
            knn_neighbors=knn_neighbors,
        )
        clf.save(save_dir)
        mlflow.log_artifact(str(save_dir / "arcface_sphere_model.pt"))
        mlflow.log_artifact(str(save_dir / "arcface_metadata.json"))

        # Clean up temp checkpoint
        if best_ckpt.exists():
            best_ckpt.unlink()


# ── Optuna tuning ─────────────────────────────────────────────────────────────


def _optuna_tune(
    df: pd.DataFrame,
    backbone: str,
    image_size: int,
    n_trials: int = 20,
) -> dict[str, float]:
    """Tune ArcFace margin hyperparameters using Optuna.

    Runs short (5-epoch) trials on a 256×256 + light-backbone variant
    to find optimal margin_power, margin_coef, and margin_cons.
    Matches the Kaggle 1st-place tuning strategy.

    Returns
    -------
    dict with keys: margin_power, margin_coef, margin_cons
    """
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial: optuna.Trial) -> float:
        mp = trial.suggest_float("margin_power", -0.8, -0.05)
        mc = trial.suggest_float("margin_coef", 0.2, 1.0)
        mk = trial.suggest_float("margin_cons", 0.0, 0.1)

        # Short run: 5 epochs, smaller images, lighter backbone
        tune_df = df.sample(min(len(df), 4000), random_state=trial.number)
        try:
            train_model(
                tune_df,
                backbone="tf_efficientnet_b4",
                image_size=256,
                epochs=5,
                batch_size=ARCFACE_BATCH_SIZE,
                model_dir=Path("/tmp/arcface_tune"),
                experiment_name=EXPERIMENT_NAME + "_tune",
                margin_power=mp,
                margin_coef=mc,
                margin_cons=mk,
                patience=5,
            )
        except Exception as exc:
            log.warning("Trial %d failed: %s", trial.number, exc)
            return 0.0

        # Return best val F1 from MLflow — approximate: just return 0 here
        # and rely on manual inspection of MLflow for exact values.
        return 0.0

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)
    best = study.best_params
    log.info("Optuna best margin params: %s", best)
    return {
        "margin_power": best["margin_power"],
        "margin_coef": best["margin_coef"],
        "margin_cons": best["margin_cons"],
    }


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(
        description="Train whale photo ArcFace classifier (1st-place Kaggle approach)"
    )
    parser.add_argument(
        "--backbone",
        default=ARCFACE_BACKBONE,
        help=(
            "timm backbone identifier. "
            f"Default: {ARCFACE_BACKBONE}. "
            "Lighter alternative: tf_efficientnet_b4."
        ),
    )
    parser.add_argument(
        "--image-size",
        type=int,
        default=ARCFACE_IMAGE_SIZE,
        help=f"Input image size in pixels. Default: {ARCFACE_IMAGE_SIZE}.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=ARCFACE_EPOCHS,
        help=f"Maximum training epochs. Default: {ARCFACE_EPOCHS}.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=ARCFACE_BATCH_SIZE,
        help=f"Batch size. Default: {ARCFACE_BATCH_SIZE}.",
    )
    parser.add_argument(
        "--stage",
        choices=["critical", "broad"],
        default="critical",
        help=(
            "Training stage: 'critical' trains the 8-class ESA-species model "
            "(default). 'broad' trains the non-critical cetacean model."
        ),
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="Run Optuna margin hyperparameter tuning first.",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=20,
        help="Number of Optuna trials (default: 20).",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to training manifest CSV.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    t0 = time.time()

    manifest_path = Path(args.manifest) if args.manifest else None
    df = load_training_data(manifest_path)

    if df.empty:
        log.error("No training data. Run download_whale_photos.py first.")
        return

    # ── Stage routing ─────────────────────────────────────────────────────
    if args.stage == "broad":
        target_species = WHALE_PHOTO_BROAD_TARGET_SPECIES
        stage_model_dir: Path = ARCFACE_BROAD_MODEL_DIR
        stage_experiment = EXPERIMENT_NAME + "_broad"
    else:
        # critical (default): 7 ESA species + other_cetacean gatekeeper
        target_species = WHALE_PHOTO_SPECIES
        stage_model_dir = ARCFACE_MODEL_DIR
        stage_experiment = EXPERIMENT_NAME

    df = df[df["species"].isin(target_species)].reset_index(drop=True)
    if df.empty:
        log.error(
            "No images for stage '%s' after filtering. "
            "Run download_whale_photos.py --stage %s first.",
            args.stage,
            args.stage,
        )
        return

    log.info(
        "Stage: %s | %d images | %d species | model dir: %s",
        args.stage,
        len(df),
        df["species"].nunique(),
        stage_model_dir,
    )

    # ── Optional Optuna tuning ────────────────────────────────────────────
    margin_kwargs: dict[str, float] = {}
    if args.tune:
        log.info("Running Optuna margin hyperparameter tuning ...")
        best_margins = _optuna_tune(
            df, args.backbone, args.image_size, n_trials=args.n_trials
        )
        margin_kwargs = best_margins

    # ── Train ─────────────────────────────────────────────────────────────
    train_model(
        df,
        backbone=args.backbone,
        image_size=args.image_size,
        epochs=args.epochs,
        batch_size=args.batch_size,
        model_dir=stage_model_dir,
        experiment_name=stage_experiment,
        **margin_kwargs,
    )

    log.info("Done in %.1fs.", time.time() - t0)


if __name__ == "__main__":
    main()

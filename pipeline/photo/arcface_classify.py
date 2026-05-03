"""Whale species photo classifier using sub-centre ArcFace with dynamic margins.

Architecture is based on the 1st-place Kaggle Happywhale solution (Abe &
Yamaguchi, 2022).  Key differences versus the EfficientNet-B4 softmax
classifier in ``pipeline/photo/classify.py``:

  * **Sub-centre ArcFace head** (k = 2) — angular margin in embedding
    space clusters each species more tightly across multiple body-view
    modes (fluke, dorsal fin, flank).

  * **Dynamic per-class margins** — rarer species receive larger margins
    (∝ n_samples^power), pushing them apart more aggressively during
    training.

  * **Generalised Mean (GeM) pooling** of the last two convolutional
    feature maps — richer texture representation than global average
    pooling for fine-grained patterns (callosities, chevrons, mottling).

  * **Gallery-based KNN inference** — cosine similarity between the
    query embedding and a gallery of training embeddings is blended
    with the raw logit score, improving open-set robustness.

The inference API is fully compatible with ``WhalePhotoClassifier``:
``predict()`` returns the same key set, plus ArcFace-specific extras.

Reference
---------
Abe, K. & Yamaguchi, T. (2022). "Preferred Dolphin: 1st Place Solution."
https://www.kaggle.com/competitions/happy-whale-and-dolphin/discussion/320192
Code: https://github.com/knshnb/kaggle-happywhale-1st-place

Dependencies
------------
``torch >= 2.0``, ``timm >= 0.9``, ``albumentations >= 1.3``
Install: ``uv add timm albumentations``

Usage
-----
    from pipeline.photo.arcface_classify import ArcFacePhotoClassifier

    clf = ArcFacePhotoClassifier.load()
    result = clf.predict("whale_fluke.jpg")
    # result["predicted_species"], result["confidence"], result["probabilities"]
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import (
    ARCFACE_BACKBONE,
    ARCFACE_GEM_P,
    ARCFACE_IMAGE_SIZE,
    ARCFACE_KNN_NEIGHBORS,
    ARCFACE_KNN_RATIO,
    ARCFACE_MODEL_DIR,
    ARCFACE_N_CENTER,
    ARCFACE_OUT_INDICES,
    DB_CONFIG,
    H3_RESOLUTION,
    PHOTO_IMAGENET_MEAN,
    PHOTO_IMAGENET_STD,
    WHALE_PHOTO_SPECIES,
)

log = logging.getLogger(__name__)


# ── Model factory ────────────────────────────────────────────────────────────


def build_sphere_model(
    model_name: str = ARCFACE_BACKBONE,
    n_classes: int = len(WHALE_PHOTO_SPECIES),
    out_indices: tuple[int, ...] = ARCFACE_OUT_INDICES,
    n_center: int = ARCFACE_N_CENTER,
    gem_p: float = ARCFACE_GEM_P,
    pretrained: bool = True,
) -> Any:
    """Construct a WhaleSphereModel for ArcFace training and inference.

    Requires ``torch >= 2.0`` and ``timm >= 0.9``.

    Architecture
    ------------
    timm backbone (features_only) → multi-scale GeM pools → concat →
    BatchNorm1d neck → ArcMarginProductSubcenter head

    Parameters
    ----------
    model_name:
        timm model identifier. Default: ``tf_efficientnet_b7``.
    n_classes:
        Number of output species classes.
    out_indices:
        Which backbone stage outputs to pool (last two by default).
    n_center:
        Sub-centre count k per class.  k = 2 handles multiple visual
        modes per species (fluke vs dorsal vs flank view).
    gem_p:
        GeM pooling exponent (fixed, not learned).
    pretrained:
        Load ImageNet-pretrained backbone weights.
    """
    try:
        import timm
    except ImportError as exc:
        raise ImportError(
            "timm is required for ArcFace training/inference. Install with: uv add timm"
        ) from exc

    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class GeM(nn.Module):
        """Generalised Mean pooling (GeM).

        Stronger than GAP for fine-grained recognition because it
        up-weights high-activation regions.  p is fixed to keep the
        model fully deterministic at inference.
        """

        def __init__(self, p: float = 3.0, eps: float = 1e-6) -> None:
            super().__init__()
            self.p = p
            self.eps = eps

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return x.clamp(min=self.eps).pow(self.p).mean((-2, -1)).pow(1.0 / self.p)

    class ArcMarginProductSubcenter(nn.Module):
        """Sub-centre ArcFace projection head.

        Maintains ``k`` weight prototypes per class.  At inference, the
        maximum cosine similarity across sub-centres is returned, which
        allows each class to capture multiple visual modes (e.g. the same
        species from a fluke vs dorsal perspective) without forcing them
        into a single centroid.
        """

        def __init__(
            self,
            in_features: int,
            out_features: int,
            k: int = 2,
        ) -> None:
            super().__init__()
            self.weight = nn.Parameter(torch.FloatTensor(out_features * k, in_features))
            stdv = 1.0 / math.sqrt(in_features)
            self.weight.data.uniform_(-stdv, stdv)
            self.k = k
            self.out_features = out_features

        def forward(self, features: torch.Tensor) -> torch.Tensor:
            cosine_all = F.linear(
                F.normalize(features),
                F.normalize(self.weight),
            )
            cosine_all = cosine_all.view(-1, self.out_features, self.k)
            cosine, _ = torch.max(cosine_all, dim=2)
            return cosine

    class WhaleSphereModel(nn.Module):
        """Whale species embedding model.

        Combines a pretrained timm backbone with multi-scale GeM pooling,
        a BatchNorm1d neck, and a sub-centre ArcFace head.
        """

        def __init__(self) -> None:
            super().__init__()
            self.backbone = timm.create_model(
                model_name,
                in_chans=3,
                pretrained=pretrained,
                num_classes=0,
                features_only=True,
                out_indices=list(out_indices),
            )
            feat_channels = self.backbone.feature_info.channels()
            self.global_pools = nn.ModuleList([GeM(p=gem_p) for _ in out_indices])
            self.mid_features: int = int(sum(feat_channels))
            self.neck = nn.BatchNorm1d(self.mid_features)
            self.head = ArcMarginProductSubcenter(
                self.mid_features,
                n_classes,
                k=n_center,
            )
            log.info(
                "WhaleSphereModel: backbone=%s out_indices=%s "
                "feat_dims=%s mid_features=%d n_classes=%d",
                model_name,
                out_indices,
                feat_channels,
                self.mid_features,
                n_classes,
            )

        def get_feat(self, x: torch.Tensor) -> torch.Tensor:
            """Neck embedding vector (used to build / query KNN gallery)."""
            maps = self.backbone(x)
            pooled = [pool(m) for m, pool in zip(maps, self.global_pools, strict=True)]
            h = torch.cat(pooled, dim=1)
            return self.neck(h)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """Per-class cosine logits (no ArcFace margin at test time)."""
            return self.head(self.get_feat(x))

    return WhaleSphereModel()


# ── Albumentations augmentations ─────────────────────────────────────────────


def get_arcface_train_transforms(image_size: int = ARCFACE_IMAGE_SIZE) -> Any:
    """Return albumentations training augmentation pipeline.

    Adapts the augmentation sequence from the 1st-place Kaggle Happywhale
    solution.  Requires ``albumentations >= 1.3``.
    """
    try:
        import albumentations as A
        from albumentations.pytorch import ToTensorV2
    except ImportError as exc:
        raise ImportError(
            "albumentations is required for ArcFace training. "
            "Install with: uv add albumentations"
        ) from exc

    return A.Compose(
        [
            A.Affine(
                rotate=(-15, 15),
                translate_percent=(0.0, 0.25),
                shear=(-3, 3),
                p=0.5,
            ),
            A.RandomResizedCrop(
                size=(image_size, image_size),
                scale=(0.9, 1.0),
                ratio=(0.75, 1.333),
            ),
            A.ToGray(p=0.1),
            A.GaussianBlur(blur_limit=(3, 7), p=0.05),
            A.GaussNoise(p=0.05),
            A.Posterize(p=0.2),
            A.RandomBrightnessContrast(p=0.5),
            A.CoarseDropout(
                num_holes_range=(1, 8),
                hole_height_range=(1, int(image_size * 0.07)),
                hole_width_range=(1, int(image_size * 0.07)),
                p=0.05,
            ),
            A.RandomSnow(p=0.1),
            A.RandomRain(p=0.05),
            A.HorizontalFlip(p=0.5),
            A.Normalize(
                mean=list(PHOTO_IMAGENET_MEAN),
                std=list(PHOTO_IMAGENET_STD),
            ),
            ToTensorV2(),
        ]
    )


def get_arcface_val_transforms(image_size: int = ARCFACE_IMAGE_SIZE) -> Any:
    """Return albumentations validation / inference transforms (no augmentation)."""
    try:
        import albumentations as A
        from albumentations.pytorch import ToTensorV2
    except ImportError as exc:
        raise ImportError(
            "albumentations is required for ArcFace inference. "
            "Install with: uv add albumentations"
        ) from exc

    return A.Compose(
        [
            A.Resize(height=image_size, width=image_size),
            A.Normalize(
                mean=list(PHOTO_IMAGENET_MEAN),
                std=list(PHOTO_IMAGENET_STD),
            ),
            ToTensorV2(),
        ]
    )


# ── Gallery helpers ───────────────────────────────────────────────────────────


def extract_embeddings(
    model: Any,
    image_paths: list[str | Path],
    image_size: int = ARCFACE_IMAGE_SIZE,
    batch_size: int = 32,
    tta: bool = True,
) -> np.ndarray:
    """Extract neck embeddings for a list of image paths.

    Parameters
    ----------
    tta:
        If True, average embeddings of original and horizontally-flipped
        images (test-time augmentation).

    Returns
    -------
    np.ndarray of shape (N, mid_features)
    """
    import torch

    transform = get_arcface_val_transforms(image_size)
    device = next(model.parameters()).device
    model.eval()
    all_feats: list[np.ndarray] = []

    for start in range(0, len(image_paths), batch_size):
        batch_paths = image_paths[start : start + batch_size]
        tensors: list[Any] = []
        for p in batch_paths:
            try:
                from PIL import Image

                img = Image.open(str(p)).convert("RGB")
                img_np = np.array(img)
            except Exception:
                log.warning("Failed to load %s — using black image", p)
                img_np = np.zeros((image_size, image_size, 3), dtype=np.uint8)
            tensors.append(transform(image=img_np)["image"])

        batch = torch.stack(tensors).to(device)
        with torch.no_grad():
            feats = model.get_feat(batch)
            if tta:
                feats_flip = model.get_feat(batch.flip(3))
                feats = (feats + feats_flip) / 2
        all_feats.append(feats.cpu().numpy())

    return np.concatenate(all_feats, axis=0)


def _knn_predict(
    test_feats: np.ndarray,
    gallery_feats: np.ndarray,
    gallery_labels: np.ndarray,
    n_classes: int,
    n_neighbors: int = ARCFACE_KNN_NEIGHBORS,
) -> np.ndarray:
    """KNN cosine-similarity prediction against a species gallery.

    For each test sample, finds the top ``n_neighbors`` gallery vectors
    by cosine similarity.  For each class, the *maximum* cosine similarity
    across its neighbours is used as the class score (matching the original
    Kaggle solution).

    Returns
    -------
    scores : np.ndarray of shape (n_test, n_classes)
    """
    from sklearn.neighbors import NearestNeighbors

    k = min(n_neighbors, len(gallery_feats))
    neigh = NearestNeighbors(n_neighbors=k, metric="cosine", algorithm="brute")
    neigh.fit(gallery_feats)
    distances, indices = neigh.kneighbors(test_feats)
    similarities = 1.0 - distances  # cosine distance → cosine similarity

    scores = np.zeros((len(test_feats), n_classes), dtype=np.float32)
    for i, (sims, idx) in enumerate(zip(similarities, indices, strict=True)):
        labels = gallery_labels[idx]
        for sim, label in zip(sims, labels, strict=True):
            if sim > scores[i, label]:
                scores[i, label] = float(sim)

    return scores


# ── Risk context helper ───────────────────────────────────────────────────────


def _lookup_risk_context(h3_int: int) -> dict[str, Any]:
    """Query fct_collision_risk for the H3 cell's risk summary."""
    import psycopg2
    import psycopg2.extras

    sql = """
        SELECT
            risk_score, risk_category,
            traffic_sub_score, cetacean_sub_score, habitat_sub_score,
            proximity_sub_score, strike_sub_score,
            protection_gap_sub_score, reference_sub_score
        FROM fct_collision_risk
        WHERE h3_cell = %s
        LIMIT 1
    """
    try:
        with (
            psycopg2.connect(**DB_CONFIG) as conn,
            conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur,
        ):
            cur.execute(sql, (h3_int,))
            row = cur.fetchone()
            return dict(row) if row else {"note": "H3 cell not in risk grid"}
    except Exception as exc:  # noqa: BLE001
        log.debug("Risk context lookup failed: %s", exc)
        return {"note": "Risk context unavailable"}


# ── Classifier class ──────────────────────────────────────────────────────────


class ArcFacePhotoClassifier:
    """ArcFace-based whale species photo classifier.

    Wraps a trained ``WhaleSphereModel`` with an optional gallery of
    training embeddings for KNN-enhanced inference.

    Inference output is compatible with ``WhalePhotoClassifier.predict()``:
    returns ``predicted_species``, ``confidence``, and ``probabilities``
    plus ArcFace-specific extras (``classifier_type``, ``knn_available``,
    ``knn_score``, ``logit_score``).

    KNN blend
    ---------
    final_score = knn_ratio * knn_score + (1 − knn_ratio) * logit_score

    When no gallery is present, logit-only inference is used.
    """

    def __init__(
        self,
        model: Any,
        label_encoder: dict[int, str],
        gallery_feats: np.ndarray | None = None,
        gallery_labels: np.ndarray | None = None,
        image_size: int = ARCFACE_IMAGE_SIZE,
        knn_ratio: float = ARCFACE_KNN_RATIO,
        knn_neighbors: int = ARCFACE_KNN_NEIGHBORS,
    ) -> None:
        self.model = model
        self.label_encoder = label_encoder
        self.label_decoder: dict[str, int] = {v: k for k, v in label_encoder.items()}
        self.gallery_feats = gallery_feats
        self.gallery_labels = gallery_labels
        self.image_size = image_size
        self.knn_ratio = knn_ratio
        self.knn_neighbors = knn_neighbors

    @property
    def _has_gallery(self) -> bool:
        return self.gallery_feats is not None and self.gallery_labels is not None

    def _image_to_tensor(self, image_path: str | Path) -> Any:
        """Load one image and return a ``(1, C, H, W)`` tensor."""
        from PIL import Image

        transform = get_arcface_val_transforms(self.image_size)
        img = Image.open(str(image_path)).convert("RGB")
        img_np = np.array(img)
        return transform(image=img_np)["image"].unsqueeze(0)

    def _predict_tensor(
        self,
        tensor: Any,
        tta: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(feat, logits)`` numpy vectors for one image tensor."""
        import torch

        device = next(self.model.parameters()).device
        tensor = tensor.to(device)
        self.model.eval()
        with torch.no_grad():
            feat1 = self.model.get_feat(tensor)
            logits1 = self.model.head(feat1)
            if tta:
                feat2 = self.model.get_feat(tensor.flip(3))
                logits2 = self.model.head(feat2)
                feat = (feat1 + feat2) / 2
                logits = (logits1 + logits2) / 2
            else:
                feat = feat1
                logits = logits1

        return (
            feat.squeeze(0).cpu().numpy(),
            logits.squeeze(0).cpu().numpy(),
        )

    def predict(
        self,
        image_path: str | Path,
        tta: bool = True,
    ) -> dict[str, Any]:
        """Classify a single whale photo.

        Blends KNN gallery score with raw logit score when a gallery is
        available (``knn_ratio`` controls the blend weight).  TTA averages
        original and horizontally-flipped image embeddings.

        Returns
        -------
        dict with keys: ``predicted_species``, ``confidence``,
        ``probabilities``, ``classifier_type``, ``knn_available``,
        and (when gallery is present) ``knn_score``, ``logit_score``.
        """
        tensor = self._image_to_tensor(image_path)
        feat, logits_np = self._predict_tensor(tensor, tta=tta)
        n_classes = len(self.label_encoder)

        if self._has_gallery:
            knn_scores = _knn_predict(
                feat.reshape(1, -1),
                self.gallery_feats,  # type: ignore[arg-type]
                self.gallery_labels,  # type: ignore[arg-type]
                n_classes=n_classes,
                n_neighbors=self.knn_neighbors,
            )[0]
            blended = self.knn_ratio * knn_scores + (1.0 - self.knn_ratio) * logits_np
        else:
            knn_scores = None
            blended = logits_np

        pred_idx = int(np.argmax(blended))
        predicted_species = self.label_encoder[pred_idx]
        confidence = float(blended[pred_idx])
        probabilities = {self.label_encoder[i]: float(s) for i, s in enumerate(blended)}

        log.info(
            "ArcFace classified %s → %s (%.1f%%, knn=%s)",
            Path(image_path).name,
            predicted_species,
            confidence * 100,
            self._has_gallery,
        )

        result: dict[str, Any] = {
            "predicted_species": predicted_species,
            "confidence": confidence,
            "probabilities": probabilities,
            "classifier_type": "arcface",
            "knn_available": self._has_gallery,
        }
        if knn_scores is not None:
            result["knn_score"] = float(knn_scores[pred_idx])
            result["logit_score"] = float(logits_np[pred_idx])

        return result

    def predict_batch(
        self,
        image_paths: list[str | Path],
        tta: bool = True,
    ) -> list[dict[str, Any]]:
        """Classify a list of whale photos using batched inference."""
        import torch

        transform = get_arcface_val_transforms(self.image_size)
        device = next(self.model.parameters()).device
        n_classes = len(self.label_encoder)

        tensors: list[Any] = []
        for p in image_paths:
            try:
                from PIL import Image

                img = Image.open(str(p)).convert("RGB")
                img_np = np.array(img)
            except Exception:
                log.warning("Failed to load %s — using black image", p)
                img_np = np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8)
            tensors.append(transform(image=img_np)["image"])

        batch = torch.stack(tensors).to(device)
        self.model.eval()
        with torch.no_grad():
            feats = self.model.get_feat(batch)
            logits = self.model.head(feats)
            if tta:
                feats2 = self.model.get_feat(batch.flip(3))
                logits2 = self.model.head(feats2)
                feats = (feats + feats2) / 2
                logits = (logits + logits2) / 2

        feats_np = feats.cpu().numpy()
        logits_np = logits.cpu().numpy()

        if self._has_gallery:
            knn_scores = _knn_predict(
                feats_np,
                self.gallery_feats,  # type: ignore[arg-type]
                self.gallery_labels,  # type: ignore[arg-type]
                n_classes=n_classes,
                n_neighbors=self.knn_neighbors,
            )
            blended = self.knn_ratio * knn_scores + (1.0 - self.knn_ratio) * logits_np
        else:
            knn_scores = None
            blended = logits_np

        results: list[dict[str, Any]] = []
        for i in range(len(image_paths)):
            pred_idx = int(np.argmax(blended[i]))
            confidence = float(blended[i, pred_idx])
            probabilities = {
                self.label_encoder[j]: float(blended[i, j]) for j in range(n_classes)
            }
            item: dict[str, Any] = {
                "predicted_species": self.label_encoder[pred_idx],
                "confidence": confidence,
                "probabilities": probabilities,
                "classifier_type": "arcface",
                "knn_available": self._has_gallery,
            }
            if knn_scores is not None:
                item["knn_score"] = float(knn_scores[i, pred_idx])
                item["logit_score"] = float(logits_np[i, pred_idx])
            results.append(item)

        return results

    def classify_and_enrich(
        self,
        image_path: str | Path,
        lat: float | None = None,
        lon: float | None = None,
    ) -> dict[str, Any]:
        """Classify image and optionally enrich with H3 risk context.

        GPS may come from EXIF metadata (if geotagged) or caller-supplied
        coordinates.  Risk context comes from ``fct_collision_risk``.
        """
        import h3

        # Try EXIF GPS if coordinates not provided
        if lat is None or lon is None:
            try:
                from PIL import Image
                from PIL.ExifTags import GPSTAGS, TAGS

                img = Image.open(str(image_path))
                exif_data = img._getexif() or {}
                gps_info: dict[str, Any] = {}
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, str(tag_id))
                    if tag == "GPSInfo":
                        for gps_tag_id, gps_val in value.items():
                            gps_tag = GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                            gps_info[gps_tag] = gps_val
                if gps_info:

                    def _dms_to_dd(dms: tuple, ref: str) -> float:
                        d = float(dms[0])
                        m = float(dms[1])
                        s = float(dms[2])
                        dd = d + m / 60.0 + s / 3600.0
                        return -dd if ref in ("S", "W") else dd

                    lat = _dms_to_dd(
                        gps_info["GPSLatitude"],
                        gps_info["GPSLatitudeRef"],
                    )
                    lon = _dms_to_dd(
                        gps_info["GPSLongitude"],
                        gps_info["GPSLongitudeRef"],
                    )
                    log.info("Extracted EXIF GPS: (%.4f, %.4f)", lat, lon)
            except Exception:  # noqa: BLE001
                pass

        prediction = self.predict(image_path)
        result: dict[str, Any] = {
            "file": str(Path(image_path).name),
            **prediction,
        }

        if lat is not None and lon is not None:
            h3_cell = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
            h3_int = int(h3_cell, 16)
            risk_context = _lookup_risk_context(h3_int)
            result.update(
                {
                    "lat": lat,
                    "lon": lon,
                    "h3_cell": h3_int,
                    "h3_hex": h3_cell,
                    "risk_context": risk_context,
                }
            )
        else:
            result.update(
                {
                    "lat": None,
                    "lon": None,
                    "risk_context": {"note": "No coordinates available"},
                }
            )

        return result

    def build_gallery(
        self,
        image_paths_by_species: dict[str, list[str | Path]],
        save_dir: str | Path | None = None,
    ) -> None:
        """Build KNN gallery from training images and save to disk.

        Runs the model on all training images to extract neck embeddings,
        then saves ``gallery.npz`` (``feats``, ``labels``) to ``save_dir``.

        Parameters
        ----------
        image_paths_by_species:
            Dict mapping species name → list of image paths.
        save_dir:
            Where to save ``gallery.npz``.  Defaults to
            ``ARCFACE_MODEL_DIR``.
        """
        save_dir = Path(save_dir) if save_dir else ARCFACE_MODEL_DIR
        save_dir.mkdir(parents=True, exist_ok=True)

        all_paths: list[str | Path] = []
        all_labels: list[int] = []
        for species, paths in image_paths_by_species.items():
            if species not in self.label_decoder:
                log.warning("Unknown species %s — skipping gallery", species)
                continue
            label_idx = self.label_decoder[species]
            all_paths.extend(paths)
            all_labels.extend([label_idx] * len(paths))

        log.info(
            "Building gallery: %d images across %d species",
            len(all_paths),
            len(image_paths_by_species),
        )

        # No TTA for gallery — we want variety, not averaged-out detail
        feats = extract_embeddings(
            self.model,
            all_paths,
            image_size=self.image_size,
            tta=False,
        )
        labels = np.array(all_labels, dtype=np.int32)
        gallery_path = save_dir / "gallery.npz"
        np.savez_compressed(str(gallery_path), feats=feats, labels=labels)
        log.info(
            "Gallery saved to %s (%d vectors, %d dims)",
            gallery_path,
            len(feats),
            feats.shape[1],
        )
        self.gallery_feats = feats
        self.gallery_labels = labels

    def save(self, model_dir: str | Path | None = None) -> Path:
        """Persist model weights, gallery, and metadata to disk."""
        import torch

        model_dir = Path(model_dir) if model_dir else ARCFACE_MODEL_DIR
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / "arcface_sphere_model.pt"
        torch.save(self.model.state_dict(), str(model_path))

        if self._has_gallery:
            gallery_path = model_dir / "gallery.npz"
            np.savez_compressed(
                str(gallery_path),
                feats=self.gallery_feats,
                labels=self.gallery_labels,
            )

        meta = {
            "classifier_type": "arcface",
            "backbone": ARCFACE_BACKBONE,
            "image_size": self.image_size,
            "knn_ratio": self.knn_ratio,
            "knn_neighbors": self.knn_neighbors,
            "label_encoder": {str(k): v for k, v in self.label_encoder.items()},
            "n_classes": len(self.label_encoder),
            "out_indices": list(ARCFACE_OUT_INDICES),
            "n_center": ARCFACE_N_CENTER,
            "gem_p": ARCFACE_GEM_P,
            "has_gallery": self._has_gallery,
        }
        meta_path = model_dir / "arcface_metadata.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        log.info("Saved ArcFace classifier to %s", model_dir)
        return model_path

    @classmethod
    def load(
        cls,
        model_dir: str | Path | None = None,
    ) -> ArcFacePhotoClassifier:
        """Load a trained ArcFace classifier from disk.

        Reads model weights, gallery (if present), and metadata.
        """
        import torch

        model_dir = Path(model_dir) if model_dir else ARCFACE_MODEL_DIR
        model_path = model_dir / "arcface_sphere_model.pt"
        meta_path = model_dir / "arcface_metadata.json"

        if not model_path.exists():
            raise FileNotFoundError(
                f"No trained ArcFace classifier found in {model_dir}. "
                "Run pipeline/analysis/train_arcface_classifier.py first."
            )

        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            label_encoder = {int(k): v for k, v in meta["label_encoder"].items()}
            n_classes = meta["n_classes"]
            image_size = meta.get("image_size", ARCFACE_IMAGE_SIZE)
            knn_ratio = meta.get("knn_ratio", ARCFACE_KNN_RATIO)
            knn_neighbors = meta.get("knn_neighbors", ARCFACE_KNN_NEIGHBORS)
            out_indices = tuple(meta.get("out_indices", list(ARCFACE_OUT_INDICES)))
            n_center = meta.get("n_center", ARCFACE_N_CENTER)
            gem_p = meta.get("gem_p", ARCFACE_GEM_P)
            backbone = meta.get("backbone", ARCFACE_BACKBONE)
        else:
            label_encoder = {i: s for i, s in enumerate(WHALE_PHOTO_SPECIES)}
            n_classes = len(WHALE_PHOTO_SPECIES)
            image_size = ARCFACE_IMAGE_SIZE
            knn_ratio = ARCFACE_KNN_RATIO
            knn_neighbors = ARCFACE_KNN_NEIGHBORS
            out_indices = ARCFACE_OUT_INDICES
            n_center = ARCFACE_N_CENTER
            gem_p = ARCFACE_GEM_P
            backbone = ARCFACE_BACKBONE

        model = build_sphere_model(
            model_name=backbone,
            n_classes=n_classes,
            out_indices=out_indices,
            n_center=n_center,
            gem_p=gem_p,
            pretrained=False,
        )
        model.load_state_dict(
            torch.load(str(model_path), map_location="cpu", weights_only=True)
        )
        model.eval()

        gallery_feats: np.ndarray | None = None
        gallery_labels: np.ndarray | None = None
        gallery_path = model_dir / "gallery.npz"
        if gallery_path.exists():
            data = np.load(str(gallery_path))
            gallery_feats = data["feats"]
            gallery_labels = data["labels"]
            log.info(
                "Loaded gallery: %d vectors from %s",
                len(gallery_feats),
                gallery_path,
            )
        else:
            log.warning(
                "No gallery found at %s — KNN inference disabled.",
                gallery_path,
            )

        log.info(
            "Loaded ArcFace classifier from %s (%d classes)",
            model_path,
            n_classes,
        )
        return cls(
            model=model,
            label_encoder=label_encoder,
            gallery_feats=gallery_feats,
            gallery_labels=gallery_labels,
            image_size=image_size,
            knn_ratio=knn_ratio,
            knn_neighbors=knn_neighbors,
        )

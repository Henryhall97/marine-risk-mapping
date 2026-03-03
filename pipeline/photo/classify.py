"""Whale species photo classifier.

Single-stage EfficientNet-B4 fine-tuned from ImageNet weights on mixed
body views (fluke, dorsal fin, flank).  Supports training and inference
with optional H3-based risk enrichment.

Usage
-----
    from pipeline.photo.classify import WhalePhotoClassifier

    clf = WhalePhotoClassifier.load()
    result = clf.predict("whale_fluke.jpg")
    enriched = clf.classify_and_enrich(
        "whale_fluke.jpg", lat=42.3, lon=-70.5
    )
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import (
    DB_CONFIG,
    H3_RESOLUTION,
    PHOTO_IMAGE_SIZE,
    PHOTO_IMAGENET_MEAN,
    PHOTO_IMAGENET_STD,
    PHOTO_MODEL_DIR,
    WHALE_PHOTO_SPECIES,
)

log = logging.getLogger(__name__)


# ── Model construction ──────────────────────────────────────


def build_efficientnet_b4(n_classes: int) -> Any:
    """Construct an EfficientNet-B4 with a custom classifier head.

    Loads ImageNet-pretrained weights for transfer learning, then
    replaces the final classifier layer with a Linear(1792, n_classes).
    """
    import torch.nn as nn
    from torchvision.models import (
        EfficientNet_B4_Weights,
        efficientnet_b4,
    )

    model = efficientnet_b4(weights=EfficientNet_B4_Weights.IMAGENET1K_V1)

    # Replace classifier head (original: Linear(1792, 1000))
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.4, inplace=True),
        nn.Linear(1792, n_classes),
    )

    return model


# ── Classifier class ────────────────────────────────────────


class WhalePhotoClassifier:
    """EfficientNet-B4 whale species photo classifier."""

    species_labels: list[str] = WHALE_PHOTO_SPECIES

    def __init__(
        self,
        model: Any,
        label_encoder: dict[int, str],
    ):
        self.model = model
        self.label_encoder = label_encoder
        self.label_decoder = {v: k for k, v in label_encoder.items()}

    def predict(
        self,
        image_path: str | Path,
    ) -> dict[str, Any]:
        """Classify a single whale photo.

        Returns
        -------
        dict with keys: predicted_species, confidence,
        probabilities (dict mapping species → float).
        """
        import torch
        from PIL import Image

        from pipeline.photo.preprocess import get_val_transforms

        self.model.eval()
        device = next(self.model.parameters()).device

        # Load and transform
        img = Image.open(str(image_path)).convert("RGB")
        transform = get_val_transforms()
        tensor = transform(img).unsqueeze(0).to(device)

        # Predict
        with torch.no_grad():
            logits = self.model(tensor)
            proba = torch.softmax(logits, dim=1).cpu().numpy()[0]

        pred_idx = int(np.argmax(proba))
        predicted_species = self.label_encoder[pred_idx]
        confidence = float(proba[pred_idx])

        probabilities = {self.label_encoder[i]: float(p) for i, p in enumerate(proba)}

        log.info(
            "Classified %s → %s (%.1f%%)",
            Path(image_path).name,
            predicted_species,
            confidence * 100,
        )

        return {
            "predicted_species": predicted_species,
            "confidence": confidence,
            "probabilities": probabilities,
        }

    def predict_batch(
        self,
        image_paths: list[str | Path],
    ) -> list[dict[str, Any]]:
        """Classify a batch of whale photos.

        More efficient than calling predict() in a loop because it
        batches the forward pass through the network.
        """
        import torch
        from PIL import Image

        from pipeline.photo.preprocess import get_val_transforms

        self.model.eval()
        device = next(self.model.parameters()).device
        transform = get_val_transforms()

        # Build batch tensor
        tensors = []
        for path in image_paths:
            try:
                img = Image.open(str(path)).convert("RGB")
            except Exception:
                log.warning("Failed to load %s — using black image", path)
                img = Image.new(
                    "RGB",
                    (PHOTO_IMAGE_SIZE, PHOTO_IMAGE_SIZE),
                )
            tensors.append(transform(img))

        batch = torch.stack(tensors).to(device)

        with torch.no_grad():
            logits = self.model(batch)
            proba = torch.softmax(logits, dim=1).cpu().numpy()

        results = []
        for i, path in enumerate(image_paths):
            pred_idx = int(np.argmax(proba[i]))
            results.append(
                {
                    "file": Path(path).name,
                    "predicted_species": self.label_encoder[pred_idx],
                    "confidence": float(proba[i][pred_idx]),
                    "probabilities": {
                        self.label_encoder[j]: float(p) for j, p in enumerate(proba[i])
                    },
                }
            )

        return results

    def classify_and_enrich(
        self,
        image_path: str | Path,
        lat: float | None = None,
        lon: float | None = None,
    ) -> dict[str, Any]:
        """Classify photo and enrich with H3-based collision risk context.

        If lat/lon are not provided, attempts to extract GPS from EXIF
        metadata.  If no coordinates are available, returns prediction
        without risk context.

        Returns
        -------
        dict with keys: file, predicted_species, confidence, probabilities,
        lat, lon, h3_cell, h3_hex, risk_context
        """
        import h3

        from pipeline.photo.preprocess import extract_exif_gps

        prediction = self.predict(image_path)

        # Try EXIF GPS if coordinates not provided
        if lat is None or lon is None:
            coords = extract_exif_gps(image_path)
            if coords:
                lat, lon = coords
                log.info("Extracted EXIF GPS: (%.4f, %.4f)", lat, lon)

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

    def save(self, model_dir: str | Path | None = None) -> Path:
        """Persist model checkpoint + metadata to disk."""
        import torch

        model_dir = Path(model_dir) if model_dir else PHOTO_MODEL_DIR
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / "efficientnet_b4_photo.pt"
        torch.save(self.model.state_dict(), str(model_path))

        meta = {
            "backend": "efficientnet_b4",
            "label_encoder": {str(k): v for k, v in self.label_encoder.items()},
            "n_classes": len(self.label_encoder),
            "image_size": PHOTO_IMAGE_SIZE,
            "imagenet_mean": list(PHOTO_IMAGENET_MEAN),
            "imagenet_std": list(PHOTO_IMAGENET_STD),
        }
        meta_path = model_dir / "model_metadata.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        log.info("Saved photo classifier to %s", model_dir)
        return model_path

    @classmethod
    def load(
        cls,
        model_dir: str | Path | None = None,
    ) -> WhalePhotoClassifier:
        """Load a trained classifier from disk."""
        import torch

        model_dir = Path(model_dir) if model_dir else PHOTO_MODEL_DIR

        meta_path = model_dir / "model_metadata.json"
        model_path = model_dir / "efficientnet_b4_photo.pt"

        if not model_path.exists():
            raise FileNotFoundError(
                f"No trained photo classifier found in "
                f"{model_dir}. Run "
                "pipeline/analysis/train_photo_classifier.py "
                "first."
            )

        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            label_encoder = {int(k): v for k, v in meta["label_encoder"].items()}
            n_classes = meta["n_classes"]
        else:
            label_encoder = {i: s for i, s in enumerate(WHALE_PHOTO_SPECIES)}
            n_classes = len(WHALE_PHOTO_SPECIES)

        model = build_efficientnet_b4(n_classes)
        model.load_state_dict(
            torch.load(
                str(model_path),
                map_location="cpu",
                weights_only=True,
            )
        )
        model.eval()

        log.info(
            "Loaded photo classifier from %s (%d classes)",
            model_path,
            n_classes,
        )
        return cls(model=model, label_encoder=label_encoder)


# ── Helpers ─────────────────────────────────────────────────


def _lookup_risk_context(h3_int: int) -> dict[str, Any]:
    """Query fct_collision_risk for risk scores at the given H3 cell."""
    try:
        import psycopg2

        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                risk_score,
                traffic_score,
                cetacean_score,
                proximity_score,
                strike_score,
                habitat_score,
                protection_gap,
                reference_risk_score
            FROM fct_collision_risk
            WHERE h3_cell = %s
            LIMIT 1
            """,
            (h3_int,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row is None:
            return {"note": "H3 cell not found in fct_collision_risk"}

        cols = [
            "risk_score",
            "traffic_score",
            "cetacean_score",
            "proximity_score",
            "strike_score",
            "habitat_score",
            "protection_gap",
            "reference_risk_score",
        ]
        return {
            c: float(v) if v is not None else None
            for c, v in zip(cols, row, strict=False)
        }

    except Exception as exc:
        log.warning("Could not fetch risk context: %s", exc)
        return {"error": str(exc)}

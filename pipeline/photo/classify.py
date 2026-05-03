"""Whale species photo classifier.

Two-pass classification pipeline mirroring the audio three-pass design:
  1. **Critical (Pass 1)** — 8-class EfficientNet-B4 covering 7 ESA-listed
     species + ``other_cetacean`` gatekeeper.  Escalates when the top
     prediction is ``other_cetacean`` OR confidence < 0.65.
  2. **Broad (Pass 2)** — 19-class model covering non-critical cetaceans
     (dolphins, pilot whales, beaked whales, etc.).  Escalates when the
     top prediction is ``unknown_cetacean`` OR confidence < 0.50.
  3. **Rare (Pass 3, optional)** — cosine-similarity lookup against
     EfficientNet-B4 penultimate-layer embeddings for rare species.
     Returns ranked ``possible_matches``; never emits a definitive label.

Single-stage ``WhalePhotoClassifier`` is retained for direct use and as
the underlying engine for each pass.

Usage
-----
    from pipeline.photo.classify import TwoPassPhotoClassifier

    clf = TwoPassPhotoClassifier.load()
    result = clf.predict("whale_fluke.jpg")
    # result["classifier_stage"] in {"critical", "broad", "rare"}
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
    PHOTO_BROAD_CONFIDENCE_THRESHOLD,
    PHOTO_BROAD_MODEL_DIR,
    PHOTO_CRITICAL_CONFIDENCE_THRESHOLD,
    PHOTO_IMAGE_SIZE,
    PHOTO_IMAGENET_MEAN,
    PHOTO_IMAGENET_STD,
    PHOTO_MODEL_DIR,
    PHOTO_RARE_EMBEDDINGS_DIR,
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


# ── Helpers ────────────────────────────────────────────────────────────


def _extract_backbone_features(
    model: Any,
    image_path: str | Path,
) -> np.ndarray:
    """Extract the 1792-dim penultimate-layer embedding from EfficientNet-B4.

    Removes the classifier head and runs a forward pass to obtain the
    global average-pooled feature vector used for cosine similarity.
    """
    import torch
    from PIL import Image

    from pipeline.photo.preprocess import get_val_transforms

    # Temporarily detach the classifier head
    original_classifier = model.classifier
    model.classifier = torch.nn.Identity()
    model.eval()
    device = next(model.parameters()).device

    img = Image.open(str(image_path)).convert("RGB")
    tensor = get_val_transforms()(img).unsqueeze(0).to(device)
    with torch.no_grad():
        features = model(tensor).cpu().numpy()[0]

    # Restore classifier head
    model.classifier = original_classifier
    return features.astype(np.float32)


# ── Rare-species embedding classifier (Pass 3) ──────────────────────────────


class RareEmbeddingPhotoClassifier:
    """Cosine-similarity embedding lookup for rare cetacean species.

    Uses 1792-dim EfficientNet-B4 penultimate features as the embedding
    space.  Maintains a library of mean embeddings per rare species built
    from training images.  At inference time, the query embedding is
    compared to each library vector and a ranked ``possible_matches``
    list is returned.

    Similarity labels
    -----------------
    - ``"possible match"`` : cosine similarity ≥ 0.80
    - ``"weak match"``     : cosine similarity ≥ 0.65
    - ``"unlikely"``       : cosine similarity < 0.65
    """

    SIMILARITY_POSSIBLE: float = 0.80
    SIMILARITY_WEAK: float = 0.65

    def __init__(self, library: dict[str, np.ndarray]) -> None:
        self.library = library
        self._normed = {
            sp: vec / (np.linalg.norm(vec) + 1e-10) for sp, vec in library.items()
        }

    @classmethod
    def load(
        cls, embeddings_dir: str | Path | None = None
    ) -> RareEmbeddingPhotoClassifier:
        """Load mean embedding vectors from ``{species}_mean_embedding.npy`` files."""
        embeddings_dir = Path(embeddings_dir or PHOTO_RARE_EMBEDDINGS_DIR)
        if not embeddings_dir.exists():
            raise FileNotFoundError(
                f"Rare photo embeddings directory not found: {embeddings_dir}. "
                "Run train_photo_classifier.py --stage rare first."
            )
        library: dict[str, np.ndarray] = {}
        for npy_path in sorted(embeddings_dir.glob("*_mean_embedding.npy")):
            species = npy_path.stem.replace("_mean_embedding", "")
            library[species] = np.load(npy_path)
        if not library:
            raise FileNotFoundError(
                f"No *_mean_embedding.npy files found in {embeddings_dir}."
            )
        log.info(
            "Loaded rare photo embeddings for %d species: %s",
            len(library),
            ", ".join(sorted(library)),
        )
        return cls(library)

    def build_library(
        self,
        model: Any,
        images_by_species: dict[str, list[Path]],
        save_dir: str | Path | None = None,
    ) -> None:
        """Compute and save mean embedding vectors from training images.

        Parameters
        ----------
        model :
            Trained ``WhalePhotoClassifier.model`` (EfficientNet-B4).
        images_by_species :
            Dict mapping species name → list of image file paths.
        save_dir :
            Directory to save ``{species}_mean_embedding.npy`` files.
        """
        save_dir = Path(save_dir or PHOTO_RARE_EMBEDDINGS_DIR)
        save_dir.mkdir(parents=True, exist_ok=True)
        for sp, paths in images_by_species.items():
            feats = []
            for p in paths:
                try:
                    feats.append(_extract_backbone_features(model, p))
                except Exception as exc:
                    log.warning("Skipping %s for rare embedding: %s", p, exc)
            if not feats:
                log.warning("No valid images for rare species '%s' — skipping", sp)
                continue
            vec = np.mean(feats, axis=0).astype(np.float32)
            self.library[sp] = vec
            self._normed[sp] = vec / (np.linalg.norm(vec) + 1e-10)
            np.save(save_dir / f"{sp}_mean_embedding.npy", vec)
            log.info(
                "Rare photo embedding saved: %s (%d dims, %d images)",
                sp,
                len(vec),
                len(feats),
            )

    def predict(self, model: Any, image_path: str | Path) -> list[dict[str, Any]]:
        """Rank rare species by cosine similarity to the query image.

        Returns
        -------
        List of dicts sorted descending by similarity::

            [
              {"species": "frasiers_dolphin",
               "similarity": 0.83,
               "confidence_label": "possible match"},
              ...
            ]
        """
        query = _extract_backbone_features(model, image_path)
        query_norm = query / (np.linalg.norm(query) + 1e-10)

        matches = []
        for sp, normed_lib in self._normed.items():
            min_len = min(len(query_norm), len(normed_lib))
            similarity = float(np.dot(query_norm[:min_len], normed_lib[:min_len]))
            if similarity >= self.SIMILARITY_WEAK:
                label = (
                    "possible match"
                    if similarity >= self.SIMILARITY_POSSIBLE
                    else "weak match"
                )
            else:
                label = "unlikely"
            matches.append(
                {
                    "species": sp,
                    "similarity": round(similarity, 4),
                    "confidence_label": label,
                }
            )
        return sorted(matches, key=lambda x: x["similarity"], reverse=True)


# ── Two-pass photo classifier ──────────────────────────────────────────────


class TwoPassPhotoClassifier:
    """Two-pass cetacean photo classifier with optional rare-embedding Pass 3.

    **Pass 1 — critical** (7 ESA species + ``other_cetacean`` gatekeeper)
        Escalates when: ``top_pred == "other_cetacean"``
        OR ``confidence < PHOTO_CRITICAL_CONFIDENCE_THRESHOLD`` (0.65).

    **Pass 2 — broad** (18 non-critical species + ``unknown_cetacean``)
        Escalates when: ``top_pred == "unknown_cetacean"``
        OR ``confidence < PHOTO_BROAD_CONFIDENCE_THRESHOLD`` (0.50).

    **Pass 3 — rare** (embedding similarity)
        Returns ranked ``possible_matches``; never emits a definitive label.

    Result dict always includes:
        ``classifier_stage``, ``escalated``, ``max_confidence``,
        ``critical_confidence``, ``broad_confidence``, ``possible_matches``
    """

    def __init__(
        self,
        critical: WhalePhotoClassifier,
        broad: WhalePhotoClassifier,
        rare: RareEmbeddingPhotoClassifier | None = None,
        critical_threshold: float = PHOTO_CRITICAL_CONFIDENCE_THRESHOLD,
        broad_threshold: float = PHOTO_BROAD_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.critical = critical
        self.broad = broad
        self.rare = rare
        self.critical_threshold = critical_threshold
        self.broad_threshold = broad_threshold

    @classmethod
    def load(
        cls,
        critical_dir: str | Path | None = None,
        broad_dir: str | Path | None = None,
        rare_dir: str | Path | None = None,
        critical_threshold: float | None = None,
        broad_threshold: float | None = None,
    ) -> TwoPassPhotoClassifier:
        """Load both classifiers + optional rare embeddings from disk."""
        critical = WhalePhotoClassifier.load(critical_dir)
        broad = WhalePhotoClassifier.load(broad_dir or PHOTO_BROAD_MODEL_DIR)

        rare: RareEmbeddingPhotoClassifier | None = None
        try:
            rare = RareEmbeddingPhotoClassifier.load(rare_dir)
        except FileNotFoundError:
            log.info(
                "Rare photo embeddings not found — Pass 3 disabled. "
                "Run train_photo_classifier.py --stage rare to enable."
            )

        return cls(
            critical=critical,
            broad=broad,
            rare=rare,
            critical_threshold=(
                critical_threshold
                if critical_threshold is not None
                else PHOTO_CRITICAL_CONFIDENCE_THRESHOLD
            ),
            broad_threshold=(
                broad_threshold
                if broad_threshold is not None
                else PHOTO_BROAD_CONFIDENCE_THRESHOLD
            ),
        )

    # ── helpers ───────────────────────────────────────────────

    @staticmethod
    def _should_escalate(
        prediction: dict[str, Any],
        threshold: float,
        gatekeeper_label: str,
    ) -> bool:
        return (
            prediction["predicted_species"] == gatekeeper_label
            or prediction["confidence"] < threshold
        )

    # ── main predict ─────────────────────────────────────────

    def predict(
        self,
        image_path: str | Path,
    ) -> dict[str, Any]:
        """Run two-pass classification on a whale photo.

        Returns
        -------
        dict with keys:
            predicted_species, confidence, probabilities,
            classifier_stage, escalated, max_confidence,
            critical_confidence, broad_confidence, possible_matches
        """
        base: dict[str, Any] = {
            "predicted_species": "unknown_cetacean",
            "confidence": 0.0,
            "probabilities": {},
            "classifier_stage": "critical",
            "escalated": False,
            "max_confidence": 0.0,
            "critical_confidence": None,
            "broad_confidence": None,
            "possible_matches": [],
        }

        # ── Pass 1: critical ─────────────────────────────────
        crit_pred = self.critical.predict(image_path)
        crit_conf = crit_pred["confidence"]
        base["critical_confidence"] = crit_conf

        if not self._should_escalate(
            crit_pred, self.critical_threshold, "other_cetacean"
        ):
            return {**base, **crit_pred, "max_confidence": crit_conf}

        log.info(
            "Two-pass photo: critical pred='%s', conf=%.3f → escalating to broad",
            crit_pred["predicted_species"],
            crit_conf,
        )

        # ── Pass 2: broad ────────────────────────────────────
        broad_pred = self.broad.predict(image_path)
        broad_conf = broad_pred["confidence"]
        base["broad_confidence"] = broad_conf

        if not self._should_escalate(
            broad_pred, self.broad_threshold, "unknown_cetacean"
        ):
            return {
                **base,
                **broad_pred,
                "classifier_stage": "broad",
                "escalated": True,
                "max_confidence": broad_conf,
            }

        log.info(
            "Two-pass photo: broad pred='%s', conf=%.3f → escalating to rare",
            broad_pred["predicted_species"],
            broad_conf,
        )

        # ── Pass 3: rare ──────────────────────────────────────
        if self.rare is None:
            log.warning("Two-pass photo: rare pass not loaded — returning broad result")
            return {
                **base,
                **broad_pred,
                "classifier_stage": "broad",
                "escalated": True,
                "max_confidence": broad_conf,
            }

        possible_matches = self.rare.predict(self.broad.model, image_path)
        log.info(
            "Two-pass photo: rare top match '%s' (sim=%.3f, %s)",
            possible_matches[0]["species"] if possible_matches else "none",
            possible_matches[0]["similarity"] if possible_matches else 0.0,
            possible_matches[0]["confidence_label"] if possible_matches else "n/a",
        )
        return {
            **base,
            **broad_pred,  # carry probabilities from broad for context
            "predicted_species": "unknown_cetacean",
            "classifier_stage": "rare",
            "escalated": True,
            "max_confidence": 0.0,
            "possible_matches": possible_matches,
        }

    def classify_and_enrich(
        self,
        image_path: str | Path,
        lat: float | None = None,
        lon: float | None = None,
    ) -> dict[str, Any]:
        """Two-pass classify + H3 risk context enrichment.

        GPS may come from EXIF metadata or user-supplied coordinates.
        Returns the two-pass predict result merged with spatial context.
        """
        import h3

        from pipeline.photo.preprocess import extract_exif_gps

        result = self.predict(image_path)

        if lat is None or lon is None:
            coords = extract_exif_gps(image_path)
            if coords:
                lat, lon = coords
                log.info("Extracted EXIF GPS: (%.4f, %.4f)", lat, lon)

        enriched: dict[str, Any] = {
            "file": str(Path(image_path).name),
            **result,
        }

        if lat is not None and lon is not None:
            h3_cell = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
            h3_int = int(h3_cell, 16)
            enriched.update(
                {
                    "lat": lat,
                    "lon": lon,
                    "h3_cell": h3_int,
                    "h3_hex": h3_cell,
                    "risk_context": _lookup_risk_context(h3_int),
                }
            )
        else:
            enriched.update(
                {
                    "lat": None,
                    "lon": None,
                    "risk_context": {"note": "No coordinates available"},
                }
            )

        return enriched


# ── Helpers ────────────────────────────────────────────────────────────


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

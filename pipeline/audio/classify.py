"""Whale species audio classifier.

Two classification backends:
  1. **XGBoost (default)** — trained on acoustic feature vectors extracted by
     ``preprocess.py``.  Lightweight, consistent with the project's ML stack.
  2. **CNN (optional)** — a mel-spectrogram image classifier using a fine-tuned
     ResNet18 (requires torch + torchvision).

Both backends expose the same ``WhaleAudioClassifier`` interface so callers
don't need to know which is active.

Usage
-----
    from pipeline.audio.classify import WhaleAudioClassifier

    clf = WhaleAudioClassifier.load()           # loads best available model
    results = clf.predict("recording.wav")      # list[dict] per segment
    enriched = clf.classify_and_enrich(          # + H3 risk context
        "recording.wav", lat=42.3, lon=-70.5
    )
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pipeline.config import (
    AUDIO_MODEL_DIR,
    AUDIO_N_MELS,
    AUDIO_SAMPLE_RATE,
    AUDIO_SEGMENT_DURATION,
    AUDIO_SEGMENT_HOP,
    DB_CONFIG,
    H3_RESOLUTION,
    WHALE_AUDIO_SPECIES,
)

log = logging.getLogger(__name__)


# ── Abstract base ───────────────────────────────────────────


class WhaleAudioClassifier(ABC):
    """Base class for whale audio classifiers."""

    species_labels: list[str] = WHALE_AUDIO_SPECIES

    @abstractmethod
    def predict_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """Classify from pre-extracted acoustic feature rows.

        Parameters
        ----------
        features : DataFrame with acoustic feature columns (no metadata).

        Returns
        -------
        DataFrame with columns: predicted_species, confidence,
        plus per-species probability columns (prob_right_whale, etc.).
        """

    def predict(
        self,
        audio_path: str | Path,
        species_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """End-to-end: load audio → segment → extract features → classify.

        Returns one dict per segment with keys:
            segment_idx, start_sec, end_sec, predicted_species,
            confidence, probabilities (dict)
        """
        from pipeline.audio.preprocess import preprocess_file

        segments = preprocess_file(
            audio_path,
            species_filter=species_filter,
        )
        if not segments:
            log.warning("No segments extracted from %s", audio_path)
            return []

        # Build feature matrix
        feat_rows = [seg["features"] for seg in segments]
        feat_df = pd.DataFrame(feat_rows)

        # Classify
        pred_df = self.predict_features(feat_df)

        # Merge with segment metadata
        results = []
        for idx, seg in enumerate(segments):
            pred_row = pred_df.iloc[idx]
            prob_cols = [c for c in pred_df.columns if c.startswith("prob_")]
            probs = {c.replace("prob_", ""): float(pred_row[c]) for c in prob_cols}

            results.append(
                {
                    "segment_idx": seg["segment_idx"],
                    "start_sec": seg["start_sec"],
                    "end_sec": seg["end_sec"],
                    "predicted_species": pred_row["predicted_species"],
                    "confidence": float(pred_row["confidence"]),
                    "probabilities": probs,
                }
            )

        # Summarise
        species_counts = pd.Series(
            [r["predicted_species"] for r in results]
        ).value_counts()
        log.info(
            "Classified %d segments from %s — %s",
            len(results),
            Path(audio_path).name,
            ", ".join(f"{s}: {c}" for s, c in species_counts.items()),
        )
        return results

    def classify_and_enrich(
        self,
        audio_path: str | Path,
        lat: float,
        lon: float,
        species_filter: str | None = None,
    ) -> dict[str, Any]:
        """Classify audio and enrich with H3-based collision risk context.

        Looks up the nearest H3 cell for the given coordinates and joins
        to fct_collision_risk for spatial risk context.

        Returns
        -------
        dict with keys:
            file, lat, lon, h3_cell, segments (list[dict]),
            dominant_species, risk_context (dict from fct_collision_risk)
        """
        import h3

        segments = self.predict(audio_path, species_filter=species_filter)

        # Determine dominant species (most frequently predicted, excl. unknown)
        non_unknown = [
            s["predicted_species"]
            for s in segments
            if s["predicted_species"] != "unknown_whale"
        ]
        dominant = (
            pd.Series(non_unknown).mode().iloc[0] if non_unknown else "unknown_whale"
        )

        # H3 lookup
        h3_cell = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
        h3_int = int(h3_cell, 16)

        # Risk context from PostGIS
        risk_context = _lookup_risk_context(h3_int)

        return {
            "file": str(Path(audio_path).name),
            "lat": lat,
            "lon": lon,
            "h3_cell": h3_int,
            "h3_hex": h3_cell,
            "dominant_species": dominant,
            "n_segments": len(segments),
            "segments": segments,
            "risk_context": risk_context,
        }

    @classmethod
    def load(cls, model_dir: str | Path | None = None) -> WhaleAudioClassifier:
        """Load the best available classifier from disk.

        Checks model_metadata.json ``backend`` field first so the
        correct loader is used even when both model files exist.
        Falls back to XGBoost-first if no metadata is present.
        """
        model_dir = Path(model_dir) if model_dir else AUDIO_MODEL_DIR

        xgb_path = model_dir / "xgboost_audio_model.json"
        cnn_path = model_dir / "cnn_audio_model.pt"
        meta_path = model_dir / "model_metadata.json"

        # Respect the backend recorded in metadata (avoids
        # loading XGBoost with CNN-written metadata or vice-versa)
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            backend = meta.get("backend", "")
            if "cnn" in backend and cnn_path.exists():
                return CNNAudioClassifier.from_disk(cnn_path, meta_path)
            if "xgboost" in backend and xgb_path.exists():
                return XGBoostAudioClassifier.from_disk(xgb_path, meta_path)

        # Fallback: try XGBoost first (lightweight), then CNN
        if xgb_path.exists():
            return XGBoostAudioClassifier.from_disk(xgb_path, meta_path)
        if cnn_path.exists():
            return CNNAudioClassifier.from_disk(cnn_path, meta_path)

        raise FileNotFoundError(
            f"No trained audio classifier found in {model_dir}. "
            "Run pipeline/analysis/train_audio_classifier.py first."
        )


# ── XGBoost backend ─────────────────────────────────────────


class XGBoostAudioClassifier(WhaleAudioClassifier):
    """Multi-class XGBoost classifier on acoustic feature vectors."""

    def __init__(
        self,
        model: Any,
        feature_names: list[str],
        label_encoder: dict[int, str],
    ):
        self.model = model
        self.feature_names = feature_names
        self.label_encoder = label_encoder  # {0: "right_whale", 1: "humpback", ...}
        self.label_decoder = {v: k for k, v in label_encoder.items()}

    def predict_features(self, features: pd.DataFrame) -> pd.DataFrame:
        import xgboost as xgb

        # Align columns
        missing = set(self.feature_names) - set(features.columns)
        if missing:
            log.warning(
                "Missing %d features -- filling with 0: %s",
                len(missing),
                missing,
            )
            for col in missing:
                features[col] = 0.0
        X = features[self.feature_names]

        dmat = xgb.DMatrix(X, feature_names=self.feature_names)
        proba = self.model.predict(dmat)  # shape (n_samples, n_classes)

        # Build result DataFrame
        pred_idx = np.argmax(proba, axis=1)
        result = pd.DataFrame(
            {
                "predicted_species": [self.label_encoder[i] for i in pred_idx],
                "confidence": np.max(proba, axis=1),
            }
        )
        for i, species in self.label_encoder.items():
            result[f"prob_{species}"] = proba[:, i]

        return result

    @classmethod
    def from_disk(
        cls,
        model_path: str | Path,
        meta_path: str | Path | None = None,
    ) -> XGBoostAudioClassifier:
        import xgboost as xgb

        model = xgb.Booster()
        model.load_model(str(model_path))

        if meta_path:
            meta_path = Path(meta_path)
        else:
            meta_path = Path(model_path).parent / "model_metadata.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            feature_names = meta.get("feature_names", None)
            label_encoder = {int(k): v for k, v in meta["label_encoder"].items()}
        else:
            feature_names = None
            label_encoder = {i: s for i, s in enumerate(WHALE_AUDIO_SPECIES)}

        # Fall back to model-embedded feature names when metadata
        # doesn't include them (e.g. CNN-written metadata file).
        if not feature_names:
            feature_names = list(model.feature_names or [])
            if not feature_names:
                log.warning(
                    "No feature_names in metadata or model; "
                    "classification may fail on column mismatch."
                )

        log.info(
            "Loaded XGBoost audio model from %s  (%d features, %d classes)",
            model_path,
            len(feature_names),
            len(label_encoder),
        )
        return cls(
            model=model,
            feature_names=feature_names,
            label_encoder=label_encoder,
        )

    def save(self, model_dir: str | Path | None = None) -> Path:
        """Persist model + metadata to disk."""
        model_dir = Path(model_dir) if model_dir else AUDIO_MODEL_DIR
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / "xgboost_audio_model.json"
        self.model.save_model(str(model_path))

        meta = {
            "backend": "xgboost",
            "feature_names": self.feature_names,
            "label_encoder": {str(k): v for k, v in self.label_encoder.items()},
            "n_classes": len(self.label_encoder),
            "sample_rate": AUDIO_SAMPLE_RATE,
            "segment_duration": AUDIO_SEGMENT_DURATION,
            "segment_hop": AUDIO_SEGMENT_HOP,
        }
        meta_path = model_dir / "model_metadata.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        log.info("Saved XGBoost audio model to %s", model_dir)
        return model_path


# ── CNN backend (optional, requires torch) ──────────────────


class CNNAudioClassifier(WhaleAudioClassifier):
    """Mel-spectrogram image classifier using a fine-tuned ResNet18.

    Only available if torch + torchvision are installed.
    """

    def __init__(self, model: Any, label_encoder: dict[int, str]):
        self.model = model
        self.label_encoder = label_encoder

    def predict_features(self, features: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError(
            "CNN classifier uses spectrogram images, not feature vectors. "
            "Call predict() or predict_spectrograms() instead."
        )

    def predict_spectrograms(self, spectrograms: list[np.ndarray]) -> pd.DataFrame:
        """Classify from pre-computed mel spectrograms."""
        import torch

        self.model.eval()
        device = next(self.model.parameters()).device

        # Stack spectrograms → (B, 1, n_mels, T) → repeat to 3-channel for ResNet
        batch = np.stack(spectrograms)
        tensor = torch.tensor(batch, dtype=torch.float32).unsqueeze(1)
        tensor = tensor.expand(-1, 3, -1, -1).to(device)

        with torch.no_grad():
            logits = self.model(tensor)
            proba = torch.softmax(logits, dim=1).cpu().numpy()

        pred_idx = np.argmax(proba, axis=1)
        result = pd.DataFrame(
            {
                "predicted_species": [self.label_encoder[i] for i in pred_idx],
                "confidence": np.max(proba, axis=1),
            }
        )
        for i, species in self.label_encoder.items():
            result[f"prob_{species}"] = proba[:, i]

        return result

    def predict(
        self,
        audio_path: str | Path,
        species_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """End-to-end: load → segment → spectrogram → classify."""
        from pipeline.audio.preprocess import preprocess_file

        segments = preprocess_file(audio_path, species_filter=species_filter)
        if not segments:
            return []

        spectrograms = [seg["mel_spectrogram"] for seg in segments]

        # Pad/truncate spectrograms to uniform time dimension
        max_t = max(s.shape[1] for s in spectrograms)
        uniform = []
        for s in spectrograms:
            if s.shape[1] < max_t:
                s = np.pad(s, ((0, 0), (0, max_t - s.shape[1])))
            uniform.append(s[:, :max_t])

        pred_df = self.predict_spectrograms(uniform)

        results = []
        for idx, seg in enumerate(segments):
            pred_row = pred_df.iloc[idx]
            prob_cols = [c for c in pred_df.columns if c.startswith("prob_")]
            probs = {c.replace("prob_", ""): float(pred_row[c]) for c in prob_cols}
            results.append(
                {
                    "segment_idx": seg["segment_idx"],
                    "start_sec": seg["start_sec"],
                    "end_sec": seg["end_sec"],
                    "predicted_species": pred_row["predicted_species"],
                    "confidence": float(pred_row["confidence"]),
                    "probabilities": probs,
                }
            )
        return results

    @classmethod
    def from_disk(
        cls,
        model_path: str | Path,
        meta_path: str | Path | None = None,
    ) -> CNNAudioClassifier:
        import torch

        if meta_path:
            meta_path = Path(meta_path)
        else:
            meta_path = Path(model_path).parent / "model_metadata.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            label_encoder = {int(k): v for k, v in meta["label_encoder"].items()}
            n_classes = meta["n_classes"]
        else:
            label_encoder = {i: s for i, s in enumerate(WHALE_AUDIO_SPECIES)}
            n_classes = len(WHALE_AUDIO_SPECIES)

        model = _build_resnet18(n_classes)
        model.load_state_dict(
            torch.load(
                str(model_path),
                map_location="cpu",
                weights_only=True,
            )
        )
        model.eval()

        log.info("Loaded CNN audio model from %s  (%d classes)", model_path, n_classes)
        return cls(model=model, label_encoder=label_encoder)

    def save(self, model_dir: str | Path | None = None) -> Path:
        import torch

        model_dir = Path(model_dir) if model_dir else AUDIO_MODEL_DIR
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / "cnn_audio_model.pt"
        torch.save(self.model.state_dict(), str(model_path))

        meta = {
            "backend": "cnn_resnet18",
            "label_encoder": {str(k): v for k, v in self.label_encoder.items()},
            "n_classes": len(self.label_encoder),
            "n_mels": AUDIO_N_MELS,
            "sample_rate": AUDIO_SAMPLE_RATE,
            "segment_duration": AUDIO_SEGMENT_DURATION,
            "segment_hop": AUDIO_SEGMENT_HOP,
        }
        meta_path = model_dir / "model_metadata.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        log.info("Saved CNN audio model to %s", model_dir)
        return model_path


# ── Helpers ─────────────────────────────────────────────────


def _build_resnet18(n_classes: int) -> Any:
    """Construct a ResNet18 adapted for single-channel spectrogram input."""
    import torch.nn as nn
    from torchvision.models import resnet18

    model = resnet18(weights=None)
    # Adapt first conv for 3-channel repeated spectrogram
    # (keep pretrained compatibility)
    model.fc = nn.Linear(model.fc.in_features, n_classes)
    return model


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

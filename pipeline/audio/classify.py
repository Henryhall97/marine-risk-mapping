"""Whale species audio classifier.

Three-pass classification pipeline:
  1. **Critical (Pass 1)** — 9-class high-precision model covering ESA-listed
     large whales + bowhead.  Escalates when the top prediction is
     ``other_cetacean`` OR max segment confidence < 0.65.
  2. **Broad (Pass 2)** — ~14-class model covering non-critical cetaceans
     (dolphins, pilot whales, beluga, etc.).  Escalates when the top
     prediction is ``unknown_cetacean`` OR max segment confidence < 0.50.
  3. **Rare (Pass 3)** — cosine-similarity embedding lookup against a library
     of mean feature vectors for rare species.  Returns ranked
     ``possible_matches`` with similarity scores; never emits a definitive
     classification.

Two XGBoost / CNN backends are available for passes 1 and 2:
  - **XGBoost (default)** — acoustic feature vectors
  - **CNN (optional)** — mel-spectrogram ResNet18 (requires torch)

Usage
-----
    from pipeline.audio.classify import ThreePassAudioClassifier

    clf = ThreePassAudioClassifier.load()
    result = clf.predict("recording.wav")
    # result["classifier_stage"] in {"critical", "broad", "rare"}
    # result["possible_matches"]   — populated only when stage == "rare"
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
    AUDIO_BROAD_CONFIDENCE_THRESHOLD,
    AUDIO_BROAD_MODEL_DIR,
    AUDIO_CRITICAL_CONFIDENCE_THRESHOLD,
    AUDIO_MODEL_DIR,
    AUDIO_N_MELS,
    AUDIO_RARE_EMBEDDINGS_DIR,
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


# ── Rare-species embedding classifier (Pass 3) ──────────────────────────────


class RareEmbeddingAudioClassifier:
    """Cosine-similarity embedding lookup for rare cetacean species.

    Rather than a softmax classifier, this class maintains a library of
    **mean feature vectors** — one per rare species — built from the broad
    model backbone.  At inference time the query segment's feature vector is
    compared to each library vector via cosine similarity and a ranked list of
    ``possible_matches`` is returned.

    Similarity labels
    -----------------
    - ``"possible match"`` : cosine similarity ≥ 0.80
    - ``"weak match"``     : cosine similarity ≥ 0.65
    - ``"unlikely"``       : cosine similarity < 0.65

    This is deliberately not a hard classification — the result surfaces
    uncertainty to the end user.
    """

    SIMILARITY_POSSIBLE: float = 0.80
    SIMILARITY_WEAK: float = 0.65

    def __init__(self, library: dict[str, np.ndarray]) -> None:
        """Construct from a pre-loaded embedding library.

        Parameters
        ----------
        library : dict mapping species name → 1-D mean feature vector.
        """
        self.library = library
        # Normalise once for fast cosine similarity
        self._normed = {
            sp: vec / (np.linalg.norm(vec) + 1e-10) for sp, vec in library.items()
        }

    @classmethod
    def load(
        cls, embeddings_dir: str | Path | None = None
    ) -> RareEmbeddingAudioClassifier:
        """Load mean embedding vectors from ``{species}_mean_embedding.npy``
        files saved during rare-stage training.
        """
        embeddings_dir = Path(embeddings_dir or AUDIO_RARE_EMBEDDINGS_DIR)
        if not embeddings_dir.exists():
            raise FileNotFoundError(
                f"Rare audio embeddings directory not found: {embeddings_dir}. "
                "Run train_audio_classifier.py --stage rare first."
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
            "Loaded rare audio embeddings for %d species: %s",
            len(library),
            ", ".join(sorted(library)),
        )
        return cls(library)

    def build_library(
        self,
        features_by_species: dict[str, pd.DataFrame],
        save_dir: str | Path | None = None,
    ) -> None:
        """Compute and optionally save mean embedding vectors.

        Parameters
        ----------
        features_by_species :
            Dict mapping species name → DataFrame of acoustic feature rows
            (same columns used by the broad XGBoost model).
        save_dir :
            If provided, saves ``{species}_mean_embedding.npy`` files here.
        """
        save_dir = Path(save_dir or AUDIO_RARE_EMBEDDINGS_DIR)
        save_dir.mkdir(parents=True, exist_ok=True)
        for sp, df in features_by_species.items():
            vec = df.to_numpy().mean(axis=0).astype(np.float32)
            self.library[sp] = vec
            self._normed[sp] = vec / (np.linalg.norm(vec) + 1e-10)
            np.save(save_dir / f"{sp}_mean_embedding.npy", vec)
            log.info(
                "Rare embedding saved: %s  (%d dims, %d segments)",
                sp,
                len(vec),
                len(df),
            )

    def predict_segment(
        self, feature_row: pd.Series | np.ndarray
    ) -> list[dict[str, Any]]:
        """Rank rare species by cosine similarity to a single feature vector.

        Returns
        -------
        List of dicts (sorted descending by similarity)::

            [
              {"species": "amazon_river_dolphin",
               "similarity": 0.87,
               "confidence_label": "possible match"},
              ...
            ]
        """
        if isinstance(feature_row, pd.Series):
            query = feature_row.to_numpy().astype(np.float32)
        else:
            query = np.asarray(feature_row, dtype=np.float32)
        query_norm = query / (np.linalg.norm(query) + 1e-10)

        matches = []
        for sp, normed_lib in self._normed.items():
            # Align length defensively (feature sets may differ slightly)
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

    def predict(self, features: pd.DataFrame) -> list[dict[str, Any]]:
        """Aggregate rare-species predictions across all segments.

        Returns the top candidate per segment combined into a consensus
        ranked list with mean similarity, plus the per-segment detail.
        """
        per_segment = [
            self.predict_segment(features.iloc[i]) for i in range(len(features))
        ]
        # Aggregate: mean similarity per species across all segments
        agg: dict[str, list[float]] = {}
        for seg_matches in per_segment:
            for m in seg_matches:
                agg.setdefault(m["species"], []).append(m["similarity"])
        consensus = []
        for sp, sims in agg.items():
            mean_sim = float(np.mean(sims))
            label = (
                "possible match"
                if mean_sim >= self.SIMILARITY_POSSIBLE
                else ("weak match" if mean_sim >= self.SIMILARITY_WEAK else "unlikely")
            )
            consensus.append(
                {
                    "species": sp,
                    "similarity": round(mean_sim, 4),
                    "confidence_label": label,
                }
            )
        consensus.sort(key=lambda x: x["similarity"], reverse=True)
        return consensus


# ── Three-pass classifier ────────────────────────────────────────────────────


class ThreePassAudioClassifier:
    """Three-stage cetacean audio classifier.

    **Pass 1 — critical** (ESA-listed large whales + bowhead)
        Escalates when: ``top_pred == "other_cetacean"``
        OR ``max_conf < AUDIO_CRITICAL_CONFIDENCE_THRESHOLD`` (default 0.65).

    **Pass 2 — broad** (non-critical cetaceans: dolphins, pilot whales, etc.)
        Escalates when: ``top_pred == "unknown_cetacean"``
        OR ``max_conf < AUDIO_BROAD_CONFIDENCE_THRESHOLD`` (default 0.50).

    **Pass 3 — rare** (embedding similarity lookup)
        Returns a ranked ``possible_matches`` list; never emits a definitive
        species label.  ``classifier_stage`` is set to ``"rare"``.

    The result dict always includes:
        - ``classifier_stage``     : ``"critical" | "broad" | "rare"``
        - ``escalated``            : bool
        - ``max_confidence``       : float (0.0 for rare stage)
        - ``critical_max_confidence`` : float | None
        - ``broad_max_confidence`` : float | None
        - ``possible_matches``     : list[dict] (only when stage=="rare")
    """

    def __init__(
        self,
        critical: WhaleAudioClassifier,
        broad: WhaleAudioClassifier,
        rare: RareEmbeddingAudioClassifier | None = None,
        critical_threshold: float = AUDIO_CRITICAL_CONFIDENCE_THRESHOLD,
        broad_threshold: float = AUDIO_BROAD_CONFIDENCE_THRESHOLD,
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
    ) -> ThreePassAudioClassifier:
        """Load all three passes from disk.

        Rare embeddings are optional — if the directory does not exist the
        rare pass is disabled and Pass 2 results are always final.
        """
        critical = WhaleAudioClassifier.load(critical_dir)
        broad = WhaleAudioClassifier.load(broad_dir or AUDIO_BROAD_MODEL_DIR)

        rare: RareEmbeddingAudioClassifier | None = None
        try:
            rare = RareEmbeddingAudioClassifier.load(rare_dir)
        except FileNotFoundError:
            log.info(
                "Rare audio embeddings not found — Pass 3 disabled. "
                "Run train_audio_classifier.py --stage rare to enable."
            )

        return cls(
            critical=critical,
            broad=broad,
            rare=rare,
            critical_threshold=(
                critical_threshold
                if critical_threshold is not None
                else AUDIO_CRITICAL_CONFIDENCE_THRESHOLD
            ),
            broad_threshold=(
                broad_threshold
                if broad_threshold is not None
                else AUDIO_BROAD_CONFIDENCE_THRESHOLD
            ),
        )

    # ── helpers ───────────────────────────────────────────────

    @staticmethod
    def _majority_species(segments: list[dict[str, Any]]) -> str:
        """Return the most-common predicted species across segments."""
        preds = [
            s["predicted_species"]
            for s in segments
            if s["predicted_species"] not in ("other_cetacean", "unknown_cetacean")
        ]
        if not preds:
            return "unknown_cetacean"
        return pd.Series(preds).mode().iloc[0]

    def _should_escalate_critical(
        self,
        segments: list[dict[str, Any]],
        max_conf: float,
    ) -> bool:
        """Escalate from Pass 1 to Pass 2."""
        majority = self._majority_species(segments)
        return majority == "other_cetacean" or max_conf < self.critical_threshold

    def _should_escalate_broad(
        self,
        segments: list[dict[str, Any]],
        max_conf: float,
    ) -> bool:
        """Escalate from Pass 2 to Pass 3."""
        majority = self._majority_species(segments)
        return majority == "unknown_cetacean" or max_conf < self.broad_threshold

    # ── main predict ─────────────────────────────────────────

    def predict(
        self,
        audio_path: str | Path,
        species_filter: str | None = None,
    ) -> dict[str, Any]:
        """Run three-pass classification on an audio file.

        Returns
        -------
        dict with keys:
            segments (list[dict]), classifier_stage, escalated, max_confidence,
            critical_max_confidence, broad_max_confidence, possible_matches
        """
        base: dict[str, Any] = {
            "segments": [],
            "classifier_stage": "critical",
            "escalated": False,
            "max_confidence": 0.0,
            "critical_max_confidence": None,
            "broad_max_confidence": None,
            "possible_matches": [],
        }

        # ── Pass 1: critical ─────────────────────────────────
        critical_segs = self.critical.predict(audio_path, species_filter=species_filter)
        if not critical_segs:
            return base

        crit_max = max(s["confidence"] for s in critical_segs)
        base["critical_max_confidence"] = crit_max

        if not self._should_escalate_critical(critical_segs, crit_max):
            return {
                **base,
                "segments": critical_segs,
                "max_confidence": crit_max,
            }

        log.info(
            "Three-pass audio: critical max=%.3f, majority='%s' → escalating to broad",
            crit_max,
            self._majority_species(critical_segs),
        )

        # ── Pass 2: broad ────────────────────────────────────
        broad_segs = self.broad.predict(audio_path, species_filter=species_filter)
        broad_max = max(s["confidence"] for s in broad_segs) if broad_segs else 0.0
        base["broad_max_confidence"] = broad_max

        if not self._should_escalate_broad(broad_segs, broad_max):
            return {
                **base,
                "segments": broad_segs,
                "classifier_stage": "broad",
                "escalated": True,
                "max_confidence": broad_max,
            }

        log.info(
            "Three-pass audio: broad max=%.3f, majority='%s' → escalating to rare",
            broad_max,
            self._majority_species(broad_segs),
        )

        # ── Pass 3: rare (embedding similarity) ─────────────
        if self.rare is None:
            log.warning(
                "Three-pass audio: rare pass not loaded — returning broad result"
            )
            return {
                **base,
                "segments": broad_segs,
                "classifier_stage": "broad",
                "escalated": True,
                "max_confidence": broad_max,
            }

        # Extract features from segments for cosine similarity
        from pipeline.audio.preprocess import preprocess_file

        raw_segs = preprocess_file(audio_path, species_filter=species_filter)
        possible_matches: list[dict[str, Any]] = []
        if raw_segs:
            feat_df = pd.DataFrame([seg["features"] for seg in raw_segs])
            possible_matches = self.rare.predict(feat_df)
            log.info(
                "Three-pass audio: rare pass top match '%s' (sim=%.3f, %s)",
                possible_matches[0]["species"] if possible_matches else "none",
                possible_matches[0]["similarity"] if possible_matches else 0.0,
                (
                    possible_matches[0]["confidence_label"]
                    if possible_matches
                    else "n/a"
                ),
            )

        return {
            **base,
            "segments": broad_segs,  # best available segment detail
            "classifier_stage": "rare",
            "escalated": True,
            "max_confidence": 0.0,  # no softmax confidence at rare stage
            "possible_matches": possible_matches,
        }

    def classify_and_enrich(
        self,
        audio_path: str | Path,
        lat: float,
        lon: float,
        species_filter: str | None = None,
    ) -> dict[str, Any]:
        """Three-pass classify + H3 risk context enrichment.

        Returns
        -------
        dict — three-pass predict result merged with:
            file, lat, lon, h3_cell, h3_hex, dominant_species, risk_context
        """
        import h3

        result = self.predict(audio_path, species_filter=species_filter)

        segs = result["segments"]
        dominant = self._majority_species(segs) if segs else "unknown_cetacean"
        # At rare stage, surface the top possible match species instead
        if result["classifier_stage"] == "rare" and result["possible_matches"]:
            top = result["possible_matches"][0]
            if top["confidence_label"] != "unlikely":
                dominant = top["species"]

        h3_cell = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
        h3_int = int(h3_cell, 16)
        risk_context = _lookup_risk_context(h3_int)

        return {
            "file": str(Path(audio_path).name),
            "lat": lat,
            "lon": lon,
            "h3_cell": h3_int,
            "h3_hex": h3_cell,
            "dominant_species": dominant,
            "n_segments": len(segs),
            **result,
            "risk_context": risk_context,
        }


# ── Backward-compatibility alias ─────────────────────────────────────────────
# Existing code that imports TwoPassAudioClassifier will continue to work;
# it now resolves to the three-pass implementation.
TwoPassAudioClassifier = ThreePassAudioClassifier


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

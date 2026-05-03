"""Audio classification service — wraps WhaleAudioClassifier for the API."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Lazy-loaded classifier singleton
_classifier = None


def _get_classifier():
    """Load the audio classifier on first use."""
    global _classifier  # noqa: PLW0603
    if _classifier is None:
        from pipeline.audio.classify import WhaleAudioClassifier

        _classifier = WhaleAudioClassifier.load()
        log.info("Audio classifier loaded")
    return _classifier


def classify_audio_only(
    audio_bytes: bytes,
    filename: str,
) -> dict[str, Any]:
    """Classify audio without GPS — species prediction only, no risk."""
    import pandas as pd

    clf = _get_classifier()

    suffix = Path(filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = Path(tmp.name)

    try:
        segments = clf.predict(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    # Determine dominant species
    non_unknown = [
        s["predicted_species"]
        for s in segments
        if s["predicted_species"] != "unknown_whale"
    ]
    dominant = pd.Series(non_unknown).mode().iloc[0] if non_unknown else "unknown_whale"

    return {
        "filename": filename,
        "dominant_species": dominant,
        "n_segments": len(segments),
        "segments": segments,
        "risk_context": None,
    }


def classify_audio(
    audio_bytes: bytes,
    filename: str,
    lat: float,
    lon: float,
) -> dict[str, Any]:
    """Classify a whale audio recording and enrich with risk context.

    Parameters
    ----------
    audio_bytes : bytes
        Raw audio file content (WAV, FLAC, MP3, AIF).
    filename : str
        Original filename (for temp file extension).
    lat, lon : float
        Recording location (required — audio has no EXIF GPS).

    Returns
    -------
    dict with keys: filename, lat, lon, h3_cell, dominant_species,
    n_segments, segments (list[dict]), risk_context (dict | None).
    """
    clf = _get_classifier()

    suffix = Path(filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = Path(tmp.name)

    try:
        result = clf.classify_and_enrich(tmp_path, lat=lat, lon=lon)
    finally:
        tmp_path.unlink(missing_ok=True)

    # Normalise risk_context — the classifier may return an error
    # dict or a note dict instead of real scores
    risk_ctx = result.get("risk_context", {})
    if "error" in risk_ctx or "note" in risk_ctx:
        risk_ctx = None

    return {
        "filename": result.get("file", filename),
        "lat": lat,
        "lon": lon,
        "h3_cell": result["h3_cell"],
        "dominant_species": result["dominant_species"],
        "n_segments": result["n_segments"],
        "segments": result.get("segments", []),
        "risk_context": risk_ctx,
    }

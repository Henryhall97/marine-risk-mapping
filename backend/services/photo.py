"""Photo classification service — wraps WhalePhotoClassifier for the API."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Lazy-loaded classifier singleton
_classifier = None


def _get_classifier():
    """Load the photo classifier on first use."""
    global _classifier  # noqa: PLW0603
    if _classifier is None:
        from pipeline.photo.classify import WhalePhotoClassifier

        _classifier = WhalePhotoClassifier.load()
        log.info("Photo classifier loaded")
    return _classifier


def classify_photo(
    image_bytes: bytes,
    filename: str,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any]:
    """Classify a whale photo and optionally enrich with risk context.

    Parameters
    ----------
    image_bytes : bytes
        Raw image file content.
    filename : str
        Original filename (for temp file extension).
    lat, lon : float | None
        User-supplied GPS coordinates.  If None, attempts EXIF
        extraction from the image.

    Returns
    -------
    dict with keys: predicted_species, confidence, probabilities,
    gps_source, and optionally risk_context (dict).
    """
    clf = _get_classifier()

    # Write to temp file (classifier expects a file path)
    suffix = Path(filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = Path(tmp.name)

    try:
        if lat is not None and lon is not None:
            result = clf.classify_and_enrich(tmp_path, lat=lat, lon=lon)
            gps_source = "user"
        else:
            # Try EXIF GPS first, then plain predict
            result = clf.classify_and_enrich(tmp_path)
            gps_source = "exif" if result.get("h3_cell") else None
    finally:
        tmp_path.unlink(missing_ok=True)

    # Build flat response dict
    response: dict[str, Any] = {
        "predicted_species": result["predicted_species"],
        "confidence": result["confidence"],
        "probabilities": result.get("probabilities", {}),
        "gps_source": gps_source,
    }

    if result.get("h3_cell"):
        response["risk_context"] = {
            "h3_cell": result["h3_cell"],
            "cell_lat": result.get("cell_lat", 0.0),
            "cell_lon": result.get("cell_lon", 0.0),
            "risk_score": result.get("risk_score"),
            "risk_category": result.get("risk_category"),
        }

    return response

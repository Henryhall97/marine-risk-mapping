"""Audio classification endpoint.

POST /api/v1/audio/classify — Upload underwater audio for species ID
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.models.audio import (
    AudioClassificationResponse,
    AudioRiskContext,
    AudioSegmentResult,
)
from backend.services import audio as audio_svc

router = APIRouter(prefix="/audio", tags=["audio"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)

_ALLOWED_CONTENT_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
    "audio/mpeg",
    "audio/aiff",
    "audio/x-aiff",
    "application/octet-stream",  # some clients send generic type
}
_MAX_FILE_SIZE_MB = 100  # audio files can be larger than images


@router.post("/classify", response_model=AudioClassificationResponse)
@limiter.limit("10/minute")
def classify_audio(
    request: Request,
    file: UploadFile = File(  # noqa: B008
        ...,
        description="Underwater audio recording (WAV/FLAC/MP3/AIF)",
    ),
    lat: float | None = Form(
        None,
        ge=-90,
        le=90,
        description="Recording latitude (WGS-84, optional)",
    ),
    lon: float | None = Form(
        None,
        ge=-180,
        le=180,
        description="Recording longitude (WGS-84, optional)",
    ),
):
    """Classify whale species from an underwater audio recording.

    Segments the audio into 4-second windows (2s hop), extracts
    acoustic features, and classifies each segment independently.
    Returns per-segment predictions plus a dominant species across
    all segments. GPS coordinates are optional — when provided the
    response includes H3 risk context.
    """
    # Validate content type
    if file.content_type and file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            415,
            f"Unsupported audio type: {file.content_type}. "
            f"Accepted: WAV, FLAC, MP3, AIF.",
        )

    # Read and validate size
    audio_bytes = file.file.read()
    size_mb = len(audio_bytes) / (1024 * 1024)
    if size_mb > _MAX_FILE_SIZE_MB:
        raise HTTPException(
            413,
            f"Audio file too large ({size_mb:.1f} MB). "
            f"Maximum: {_MAX_FILE_SIZE_MB} MB.",
        )
    if len(audio_bytes) == 0:
        raise HTTPException(400, "Empty file uploaded")

    # Classify
    try:
        if lat is not None and lon is not None:
            result = audio_svc.classify_audio(
                audio_bytes=audio_bytes,
                filename=file.filename or "upload.wav",
                lat=lat,
                lon=lon,
            )
        else:
            result = audio_svc.classify_audio_only(
                audio_bytes=audio_bytes,
                filename=file.filename or "upload.wav",
            )
    except FileNotFoundError as exc:
        raise HTTPException(
            503,
            "Audio classifier model not loaded. "
            "Ensure the model exists at "
            "data/processed/ml/audio_classifier/.",
        ) from exc
    except Exception as exc:
        logger.exception("Audio classification failed")
        raise HTTPException(500, "Classification failed — see server logs") from exc

    # Build typed response
    segments = [AudioSegmentResult(**seg) for seg in result["segments"]]

    risk_context = None
    if result.get("risk_context"):
        risk_context = AudioRiskContext(
            h3_cell=result["h3_cell"],
            **result["risk_context"],
        )

    return AudioClassificationResponse(
        filename=result["filename"],
        lat=result.get("lat"),
        lon=result.get("lon"),
        h3_cell=result.get("h3_cell"),
        dominant_species=result["dominant_species"],
        n_segments=result["n_segments"],
        segments=segments,
        risk_context=risk_context,
    )

"""Sighting report endpoint.

POST /api/v1/sightings/report — Submit a whale sighting with optional
photo, audio, species guess, description, and interaction type.
Returns combined model classifications, risk context, and advisory.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.models.sightings import (
    AudioResult,
    AudioSegmentDetail,
    InteractionType,
    PhotoResult,
    RiskAdvisory,
    RiskSummary,
    SightingLocation,
    SightingReportResponse,
    SpeciesAssessment,
    UserInput,
)
from backend.services import sightings as sighting_svc

router = APIRouter(prefix="/sightings", tags=["sightings"])
logger = logging.getLogger(__name__)

# Reuse content-type and size limits from the dedicated endpoints
_ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
}
_ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
    "audio/mpeg",
    "audio/aiff",
    "audio/x-aiff",
    "application/octet-stream",
}
_MAX_IMAGE_MB = 20
_MAX_AUDIO_MB = 100

_VALID_INTERACTIONS = {t.value for t in InteractionType}


@router.post("/report", response_model=SightingReportResponse)
async def submit_sighting_report(
    species_guess: str | None = Form(
        None,
        description="Your species identification guess",
    ),
    description: str | None = Form(
        None,
        max_length=2000,
        description="Free-text description of the encounter",
    ),
    interaction_type: str | None = Form(
        None,
        description=(
            "Type of interaction: passive_observation, "
            "vessel_approach, near_miss, strike, "
            "entanglement, stranding, acoustic_detection, other"
        ),
    ),
    lat: float | None = Form(
        None,
        ge=-90,
        le=90,
        description="Latitude (WGS-84)",
    ),
    lon: float | None = Form(
        None,
        ge=-180,
        le=180,
        description="Longitude (WGS-84)",
    ),
    image: UploadFile | None = File(  # noqa: B008
        None,
        description="Whale photograph (JPEG/PNG/WebP/TIFF, max 20 MB)",
    ),
    audio: UploadFile | None = File(  # noqa: B008
        None,
        description=("Underwater audio recording (WAV/FLAC/MP3/AIF, max 100 MB)"),
    ),
):
    """Submit a whale sighting report.

    At least one of ``image``, ``audio``, or ``species_guess``
    must be provided. The endpoint runs the relevant classifiers,
    reconciles predictions with the user's guess, looks up H3
    collision risk, and generates a plain-language advisory.
    """
    # ── Validation ──────────────────────────────────────────
    has_image = image is not None and image.filename
    has_audio = audio is not None and audio.filename
    if not has_image and not has_audio and not species_guess:
        raise HTTPException(
            400,
            "At least one of image, audio, or species_guess must be provided.",
        )

    if has_audio and lat is None:
        raise HTTPException(
            400,
            "Latitude and longitude are required when "
            "submitting audio (no EXIF in audio files).",
        )

    if interaction_type and interaction_type not in _VALID_INTERACTIONS:
        raise HTTPException(
            400,
            f"Invalid interaction_type '{interaction_type}'. "
            f"Valid: {sorted(_VALID_INTERACTIONS)}",
        )

    # ── Read + validate image ───────────────────────────────
    image_bytes: bytes | None = None
    image_filename: str | None = None
    if has_image:
        assert image is not None  # type narrowing
        if image.content_type not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                415,
                f"Unsupported image type: {image.content_type}. "
                f"Accepted: {sorted(_ALLOWED_IMAGE_TYPES)}",
            )
        image_bytes = await image.read()
        size_mb = len(image_bytes) / (1024 * 1024)
        if size_mb > _MAX_IMAGE_MB:
            raise HTTPException(
                413,
                f"Image too large ({size_mb:.1f} MB). Max: {_MAX_IMAGE_MB} MB.",
            )
        image_filename = image.filename

    # ── Read + validate audio ───────────────────────────────
    audio_bytes: bytes | None = None
    audio_filename: str | None = None
    if has_audio:
        assert audio is not None  # type narrowing
        ct = audio.content_type
        if ct and ct not in _ALLOWED_AUDIO_TYPES:
            raise HTTPException(
                415,
                f"Unsupported audio type: {ct}. Accepted: WAV, FLAC, MP3, AIF.",
            )
        audio_bytes = await audio.read()
        size_mb = len(audio_bytes) / (1024 * 1024)
        if size_mb > _MAX_AUDIO_MB:
            raise HTTPException(
                413,
                f"Audio too large ({size_mb:.1f} MB). Max: {_MAX_AUDIO_MB} MB.",
            )
        if len(audio_bytes) == 0:
            raise HTTPException(400, "Empty audio file uploaded.")
        audio_filename = audio.filename

    # ── Process ─────────────────────────────────────────────
    try:
        result = sighting_svc.process_sighting_report(
            species_guess=species_guess,
            description=description,
            interaction_type=interaction_type,
            lat=lat,
            lon=lon,
            image_bytes=image_bytes,
            image_filename=image_filename,
            audio_bytes=audio_bytes,
            audio_filename=audio_filename,
        )
    except RuntimeError as exc:
        logger.exception("Classifier unavailable")
        raise HTTPException(503, f"Classifier unavailable: {exc}") from exc
    except Exception as exc:
        logger.exception("Sighting report processing failed")
        raise HTTPException(500, "Internal error") from exc

    # ── Build typed response ────────────────────────────────
    location = None
    if result.get("location"):
        location = SightingLocation(**result["location"])

    user_input = UserInput(**result["user_input"])

    photo_cls = None
    if result.get("photo_classification"):
        photo_cls = PhotoResult(**result["photo_classification"])

    audio_cls = None
    if result.get("audio_classification"):
        ac = result["audio_classification"]
        segments = [AudioSegmentDetail(**s) for s in ac.get("segment_details", [])]
        audio_cls = AudioResult(
            dominant_species=ac["dominant_species"],
            n_segments=ac["n_segments"],
            segment_details=segments,
        )

    assessment = None
    if result.get("species_assessment"):
        assessment = SpeciesAssessment(**result["species_assessment"])

    risk_summary = None
    if result.get("risk_summary"):
        risk_summary = RiskSummary(**result["risk_summary"])

    advisory = None
    if result.get("advisory"):
        advisory = RiskAdvisory(**result["advisory"])

    return SightingReportResponse(
        location=location,
        user_input=user_input,
        photo_classification=photo_cls,
        audio_classification=audio_cls,
        species_assessment=assessment,
        risk_summary=risk_summary,
        advisory=advisory,
    )

"""Sighting report endpoint.

POST /api/v1/sightings/report — Submit a whale sighting with optional
photo, audio, species guess, description, and interaction type.
Returns combined model classifications, risk context, and advisory.

GET  /api/v1/sightings/check-location — Lightweight location validation
(land/ocean detection + risk coverage check) for pre-submit UX.
"""

from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.models.sightings import (
    AudioResult,
    AudioSegmentDetail,
    InteractionType,
    PhotoResult,
    RegionalAuthority,
    RiskAdvisory,
    RiskSummary,
    SightingLocation,
    SightingReportResponse,
    SpeciesAssessment,
    UserInput,
)
from backend.services import auth as auth_svc
from backend.services import sightings as sighting_svc
from backend.services import submissions as sub_svc

router = APIRouter(prefix="/sightings", tags=["sightings"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)


@router.get("/check-location", response_model=SightingLocation)
def check_location(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
):
    """Lightweight location validation for pre-submit UX.

    Returns land/ocean detection, risk coverage flag, and any
    warnings — without running classifiers or persisting anything.
    """
    h3_cell = sighting_svc._coords_to_h3(lat, lon)
    flags = sighting_svc.check_location(lat, lon, h3_cell)
    return SightingLocation(
        lat=lat,
        lon=lon,
        h3_cell=h3_cell,
        gps_source="user",
        is_ocean=flags["is_ocean"],
        in_risk_coverage=flags["in_risk_coverage"],
        location_warnings=flags["location_warnings"],
    )


def _persist_if_authenticated(
    authorization: str | None,
    result: dict,
    is_public: bool = True,
    image_bytes: bytes | None = None,
    image_filename: str | None = None,
    audio_bytes: bytes | None = None,
    audio_filename: str | None = None,
    vessel_id: int | None = None,
    privacy_level: str = "public",
) -> str | None:
    """Save the submission to the DB if the user is logged in."""
    user_id = auth_svc.get_current_user_id(authorization)
    if user_id is None:
        return None
    try:
        return sub_svc.save_submission(
            user_id,
            result,
            is_public=is_public,
            image_bytes=image_bytes,
            image_filename=image_filename,
            audio_bytes=audio_bytes,
            audio_filename=audio_filename,
            vessel_id=vessel_id,
            privacy_level=privacy_level,
        )
    except Exception:
        logger.warning("Failed to persist submission", exc_info=True)
        return None


def _persist_and_link(
    authorization: str | None,
    result: dict,
    is_public: bool = True,
    image_bytes: bytes | None = None,
    image_filename: str | None = None,
    audio_bytes: bytes | None = None,
    audio_filename: str | None = None,
    event_id: str | None = None,
    vessel_id: int | None = None,
    privacy_level: str = "public",
) -> str | None:
    """Save submission + optionally link to an event.

    When *event_id* is provided but *vessel_id* is not, the
    event's linked vessel (if any) is automatically used.
    """
    # Auto-fill vessel from event when not explicitly provided
    if event_id and vessel_id is None:
        try:
            from backend.services import events as event_svc

            vessel_id = event_svc.get_event_vessel_id(event_id)
        except Exception:
            logger.debug(
                "Could not resolve vessel for event %s",
                event_id,
            )

    sub_id = _persist_if_authenticated(
        authorization,
        result,
        is_public=is_public,
        image_bytes=image_bytes,
        image_filename=image_filename,
        audio_bytes=audio_bytes,
        audio_filename=audio_filename,
        vessel_id=vessel_id,
        privacy_level=privacy_level,
    )
    if sub_id and event_id:
        try:
            from backend.services import events as event_svc

            user_id = auth_svc.get_current_user_id(authorization)
            if user_id:
                event_svc.link_sighting(event_id, sub_id, user_id)
        except Exception:
            logger.warning(
                "Failed to link submission %s to event %s",
                sub_id,
                event_id,
                exc_info=True,
            )
    return sub_id


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
@limiter.limit("20/minute")
def submit_sighting_report(
    request: Request,
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
    share_publicly: bool = Form(
        True,
        description="Make the submission visible on the community feed",
    ),
    event_id: str | None = Form(
        None,
        description="Optional event ID to link this sighting to",
    ),
    group_size: int | None = Form(
        None,
        ge=1,
        le=500,
        description="Number of animals observed in the encounter",
    ),
    sighting_datetime: str | None = Form(
        None,
        description="ISO-8601 datetime of the sighting",
    ),
    behavior: str | None = Form(
        None,
        description=(
            "Observed behavior: feeding, traveling, "
            "resting, socializing, mating, breaching, "
            "logging, other"
        ),
    ),
    life_stage: str | None = Form(
        None,
        description="Life stage: adult, juvenile, calf, unknown",
    ),
    calf_present: bool | None = Form(
        None,
        description="Whether a calf was observed",
    ),
    sea_state_beaufort: int | None = Form(
        None,
        ge=0,
        le=12,
        description="Beaufort sea state (0-12)",
    ),
    observation_platform: str | None = Form(
        None,
        description=("Platform: vessel, shore, aircraft, drone, kayak, diving, other"),
    ),
    coordinate_uncertainty_m: float | None = Form(
        None,
        ge=0,
        description="GPS uncertainty in metres",
    ),
    vessel_id: int | None = Form(
        None,
        description=("ID of the user's vessel profile to link to this sighting"),
    ),
    submitted_rank: str | None = Form(
        None,
        description=(
            "Taxonomic rank of the species guess "
            "(species, genus, family, suborder, order)"
        ),
    ),
    submitted_scientific_name: str | None = Form(
        None,
        description=("Scientific name corresponding to the species guess selection"),
    ),
    confidence_level: str | None = Form(
        None,
        description=(
            "Confidence in species identification: certain, likely, possible, uncertain"
        ),
    ),
    group_size_min: int | None = Form(
        None,
        ge=1,
        le=500,
        description="Minimum estimated group size",
    ),
    group_size_max: int | None = Form(
        None,
        ge=1,
        le=500,
        description="Maximum estimated group size",
    ),
    visibility_km: float | None = Form(
        None,
        ge=0,
        le=100,
        description="Horizontal visibility in kilometres",
    ),
    sea_glare: str | None = Form(
        None,
        description=("Sea surface glare level: none, slight, moderate, severe"),
    ),
    distance_to_animal_m: float | None = Form(
        None,
        ge=0,
        le=50000,
        description="Estimated distance to the animal in metres",
    ),
    direction_of_travel: str | None = Form(
        None,
        description=(
            "Direction the animal was traveling: "
            "N, NE, E, SE, S, SW, W, NW, stationary, erratic"
        ),
    ),
    privacy_level: str | None = Form(
        "public",
        description=(
            "Privacy level for this report: "
            "private (not shared), anonymous (community, "
            "no name), public (community with name)"
        ),
    ),
    privacy_accepted: bool = Form(
        False,
        description="User accepted the privacy policy",
    ),
    authorization: str | None = Header(default=None),
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
        image_bytes = image.file.read()
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
        audio_bytes = audio.file.read()
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
            group_size=group_size,
            sighting_datetime=sighting_datetime,
            behavior=behavior,
            life_stage=life_stage,
            calf_present=calf_present,
            sea_state_beaufort=sea_state_beaufort,
            observation_platform=observation_platform,
            coordinate_uncertainty_m=coordinate_uncertainty_m,
            submitted_rank=submitted_rank,
            submitted_scientific_name=submitted_scientific_name,
            confidence_level=confidence_level,
            group_size_min=group_size_min,
            group_size_max=group_size_max,
            visibility_km=visibility_km,
            sea_glare=sea_glare,
            distance_to_animal_m=distance_to_animal_m,
            direction_of_travel=direction_of_travel,
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
        adv = result["advisory"]
        auth = None
        if adv.get("authority"):
            auth = RegionalAuthority(**adv["authority"])
        advisory = RiskAdvisory(
            level=adv["level"],
            message=adv["message"],
            authority=auth,
        )

    # Derive is_public from privacy_level (fallback to share_publicly)
    is_public = share_publicly
    if privacy_level == "private":
        is_public = False
    elif privacy_level in ("anonymous", "public"):
        is_public = True

    return SightingReportResponse(
        location=location,
        user_input=user_input,
        photo_classification=photo_cls,
        audio_classification=audio_cls,
        species_assessment=assessment,
        risk_summary=risk_summary,
        advisory=advisory,
        submission_id=_persist_and_link(
            authorization,
            result,
            is_public=is_public,
            image_bytes=image_bytes,
            image_filename=image_filename,
            audio_bytes=audio_bytes,
            audio_filename=audio_filename,
            event_id=event_id,
            vessel_id=vessel_id,
            privacy_level=privacy_level or "public",
        ),
    )

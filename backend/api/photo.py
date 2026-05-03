"""Photo classification endpoint.

POST /api/v1/photo/classify — Upload a whale photo for species ID
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.models.photo import (
    PhotoClassificationResponse,
    PhotoClassificationResult,
    RiskContext,
)
from backend.services import photo as photo_svc

router = APIRouter(prefix="/photo", tags=["photo"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
}
_MAX_FILE_SIZE_MB = 20


@router.post("/classify", response_model=PhotoClassificationResponse)
@limiter.limit("10/minute")
def classify_photo(
    request: Request,
    file: UploadFile = File(  # noqa: B008
        ..., description="Whale photograph (JPEG/PNG/WebP/TIFF)"
    ),
    lat: float | None = Form(
        None,
        ge=-90,
        le=90,
        description="Latitude (overrides EXIF if provided)",
    ),
    lon: float | None = Form(
        None,
        ge=-180,
        le=180,
        description="Longitude (overrides EXIF if provided)",
    ),
):
    """Classify a whale photograph and optionally enrich with risk.

    Accepts a multipart image upload. Returns top species prediction,
    confidence, and probability distribution over all 9 classes.
    If GPS coordinates are provided (or found in EXIF), returns
    the H3 cell's collision risk context from fct_collision_risk.
    """
    # Validate content type
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            415,
            f"Unsupported image type: {file.content_type}. "
            f"Accepted: {sorted(_ALLOWED_CONTENT_TYPES)}",
        )

    # Read file bytes and check size
    image_bytes = file.file.read()
    size_mb = len(image_bytes) / (1024 * 1024)
    if size_mb > _MAX_FILE_SIZE_MB:
        raise HTTPException(
            413,
            f"Image too large ({size_mb:.1f} MB). Maximum: {_MAX_FILE_SIZE_MB} MB.",
        )

    try:
        result = photo_svc.classify_photo(
            image_bytes=image_bytes,
            filename=file.filename or "upload.jpg",
            lat=lat,
            lon=lon,
        )
    except RuntimeError as exc:
        logger.exception("Photo classification failed")
        raise HTTPException(
            503,
            f"Photo classifier unavailable: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in photo classify")
        raise HTTPException(500, "Internal classification error") from exc

    # Build response
    classification = PhotoClassificationResult(
        predicted_species=result["predicted_species"],
        confidence=result["confidence"],
        probabilities=result["probabilities"],
    )

    risk_context = None
    if result.get("risk_context"):
        rc = result["risk_context"]
        risk_context = RiskContext(
            h3_cell=rc["h3_cell"],
            cell_lat=rc["cell_lat"],
            cell_lon=rc["cell_lon"],
            risk_score=rc["risk_score"],
            risk_category=rc["risk_category"],
        )

    return PhotoClassificationResponse(
        classification=classification,
        risk_context=risk_context,
        gps_source=result.get("gps_source"),
    )

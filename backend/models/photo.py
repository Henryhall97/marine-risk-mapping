"""Pydantic schemas for photo classification endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PhotoClassificationResult(BaseModel):
    """Species classification result for a single image."""

    predicted_species: str
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Top-1 softmax probability"
    )
    probabilities: dict[str, float] = Field(
        default_factory=dict,
        description="Per-species softmax probabilities",
    )


class RiskContext(BaseModel):
    """H3 cell risk context attached to a geo-located classification."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    risk_score: float | None = None
    risk_category: str | None = None
    traffic_score: float | None = None
    cetacean_score: float | None = None


class PhotoClassificationResponse(BaseModel):
    """Full response from the photo classification endpoint."""

    classification: PhotoClassificationResult
    risk_context: RiskContext | None = None
    gps_source: str | None = Field(
        None,
        description=("Where coordinates came from: 'exif', 'user', or null"),
    )

"""Pydantic schemas for the sighting report endpoint.

A sighting report combines user-supplied context (species guess,
description, interaction type, GPS) with optional photo and/or
audio uploads.  Both classifiers run when media is provided, and
the H3 cell's full risk breakdown is returned.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ── Enums ───────────────────────────────────────────────────


class InteractionType(StrEnum):
    """Type of whale–vessel or whale–human interaction observed."""

    passive_observation = "passive_observation"
    vessel_approach = "vessel_approach"
    near_miss = "near_miss"
    strike = "strike"
    entanglement = "entanglement"
    stranding = "stranding"
    acoustic_detection = "acoustic_detection"
    other = "other"


# ── Sub-models ──────────────────────────────────────────────


class SightingLocation(BaseModel):
    """Resolved location for the sighting."""

    lat: float
    lon: float
    h3_cell: int | None = None
    gps_source: str | None = Field(
        None,
        description="How coordinates were resolved: 'user', 'exif', or null",
    )


class UserInput(BaseModel):
    """Echo of the user-supplied metadata fields."""

    species_guess: str | None = None
    description: str | None = None
    interaction_type: str | None = None


class PhotoResult(BaseModel):
    """Photo classification output (if an image was submitted)."""

    predicted_species: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    probabilities: dict[str, float] = Field(default_factory=dict)


class AudioResult(BaseModel):
    """Audio classification summary (if audio was submitted)."""

    dominant_species: str
    n_segments: int
    segment_details: list[AudioSegmentDetail] = Field(default_factory=list)


class AudioSegmentDetail(BaseModel):
    """Per-segment audio classification."""

    segment_idx: int
    start_sec: float
    end_sec: float
    predicted_species: str
    confidence: float = Field(..., ge=0.0, le=1.0)


# Rebuild AudioResult to resolve forward reference
AudioResult.model_rebuild()


class SpeciesAssessment(BaseModel):
    """Reconciliation of user guess vs model predictions."""

    model_species: str = Field(..., description="Best species from model(s)")
    model_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence for model_species"
    )
    source: str = Field(
        ...,
        description=(
            "Which model produced the assessment: "
            "'photo', 'audio', 'photo+audio', or 'user_only'"
        ),
    )
    user_agrees: bool | None = Field(
        None,
        description=(
            "Whether user guess matches model prediction (null if no guess provided)"
        ),
    )


class RiskSummary(BaseModel):
    """Abridged risk context for the sighting's H3 cell."""

    h3_cell: int
    risk_score: float | None = None
    risk_category: str | None = None
    traffic_score: float | None = None
    cetacean_score: float | None = None
    proximity_score: float | None = None
    strike_score: float | None = None
    habitat_score: float | None = None
    protection_gap: float | None = None
    reference_risk_score: float | None = None


class RiskAdvisory(BaseModel):
    """Human-readable advisory derived from risk level + species."""

    level: str = Field(..., description="Advisory level: low, moderate, high, critical")
    message: str = Field(..., description="Plain-language risk advisory")


# ── Top-level response ──────────────────────────────────────


class SightingReportResponse(BaseModel):
    """Full response from the sighting report endpoint."""

    sighting_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for this sighting report",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        description="UTC timestamp of report submission",
    )
    location: SightingLocation | None = None
    user_input: UserInput
    photo_classification: PhotoResult | None = None
    audio_classification: AudioResult | None = None
    species_assessment: SpeciesAssessment | None = None
    risk_summary: RiskSummary | None = None
    advisory: RiskAdvisory | None = None

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
    is_ocean: bool | None = Field(
        None,
        description=(
            "Whether the location is over ocean (True), "
            "land (False), or unknown (null — outside "
            "bathymetry coverage)"
        ),
    )
    in_risk_coverage: bool = Field(
        False,
        description=(
            "Whether the location falls within the project's "
            "collision risk model coverage area"
        ),
    )
    location_warnings: list[str] = Field(
        default_factory=list,
        description=(
            "Human-readable location warnings (e.g. 'on land', 'outside risk coverage')"
        ),
    )


class UserInput(BaseModel):
    """Echo of the user-supplied metadata fields."""

    species_guess: str | None = None
    description: str | None = None
    interaction_type: str | None = None
    group_size: int | None = None
    # OBIS / biological enrichment fields
    sighting_datetime: str | None = Field(
        None,
        description="ISO-8601 datetime of the sighting (when it occurred)",
    )
    behavior: str | None = Field(
        None,
        description=(
            "Observed behavior: feeding, traveling, resting, "
            "socializing, mating, breaching, logging, other"
        ),
    )
    life_stage: str | None = Field(
        None,
        description="Life stage: adult, juvenile, calf, unknown",
    )
    calf_present: bool | None = Field(
        None,
        description="Whether a calf was observed with the group",
    )
    sea_state_beaufort: int | None = Field(
        None,
        ge=0,
        le=12,
        description="Beaufort sea state (0-12)",
    )
    observation_platform: str | None = Field(
        None,
        description=(
            "Observation platform: vessel, shore, aircraft, drone, kayak, diving, other"
        ),
    )
    coordinate_uncertainty_m: float | None = Field(
        None,
        ge=0,
        description="GPS coordinate uncertainty in metres",
    )
    confidence_level: str | None = Field(
        None,
        description=(
            "Confidence in species identification: certain, likely, possible, uncertain"
        ),
    )
    group_size_min: int | None = Field(
        None,
        ge=1,
        le=500,
        description="Minimum estimated group size",
    )
    group_size_max: int | None = Field(
        None,
        ge=1,
        le=500,
        description="Maximum estimated group size",
    )
    visibility_km: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Horizontal visibility in kilometres",
    )
    sea_glare: str | None = Field(
        None,
        description="Sea glare level: none, slight, moderate, severe",
    )
    distance_to_animal_m: float | None = Field(
        None,
        ge=0,
        le=50000,
        description="Estimated distance to the animal in metres",
    )
    direction_of_travel: str | None = Field(
        None,
        description=(
            "Direction the animal was traveling: "
            "N, NE, E, SE, S, SW, W, NW, stationary, erratic"
        ),
    )


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
    model_rank: str | None = Field(
        None,
        description=(
            "Taxonomic rank of the model prediction (always 'species' for classifiers)"
        ),
    )
    user_rank: str | None = Field(
        None,
        description=(
            "Taxonomic rank the user submitted at "
            "(species, genus, family, suborder, order)"
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


class RegionalAuthority(BaseModel):
    """NOAA regional authority contact for marine mammal incidents."""

    name: str = Field(
        ...,
        description="Region name (e.g. NOAA Greater Atlantic Region)",
    )
    office: str = Field(..., description="Office name (e.g. GARFO)")
    phone: str = Field(..., description="Primary phone number")
    stranding: str = Field(..., description="Stranding hotline name")
    stranding_phone: str = Field(..., description="Stranding hotline number")
    email: str = Field("", description="Contact email (if available)")


class RiskAdvisory(BaseModel):
    """Human-readable advisory derived from risk level + species."""

    level: str = Field(..., description="Advisory level: low, moderate, high, critical")
    message: str = Field(..., description="Plain-language risk advisory")
    authority: RegionalAuthority | None = Field(
        None,
        description="Regional NOAA authority for this location",
    )


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
    submission_id: str | None = Field(
        None,
        description=(
            "Database submission ID (present only when the "
            "user is authenticated; null for anonymous reports)"
        ),
    )

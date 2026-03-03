"""Pydantic schemas for audio classification endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AudioSegmentResult(BaseModel):
    """Classification result for a single audio segment (4s window)."""

    segment_idx: int
    start_sec: float
    end_sec: float
    predicted_species: str
    confidence: float = Field(..., ge=0.0, le=1.0, description="Top-1 probability")
    probabilities: dict[str, float] = Field(
        default_factory=dict,
        description="Per-species probabilities",
    )


class AudioRiskContext(BaseModel):
    """H3 cell risk context for the recording location."""

    h3_cell: int
    risk_score: float | None = None
    traffic_score: float | None = None
    cetacean_score: float | None = None
    proximity_score: float | None = None
    strike_score: float | None = None
    habitat_score: float | None = None
    protection_gap: float | None = None
    reference_risk_score: float | None = None


class AudioClassificationResponse(BaseModel):
    """Full response from the audio classification endpoint."""

    filename: str
    lat: float
    lon: float
    h3_cell: int
    dominant_species: str = Field(
        ...,
        description=(
            "Most frequently predicted species across segments (excludes unknown_whale)"
        ),
    )
    n_segments: int = Field(..., description="Total 4-second segments analysed")
    segments: list[AudioSegmentResult]
    risk_context: AudioRiskContext | None = None

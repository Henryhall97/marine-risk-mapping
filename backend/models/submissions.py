"""Pydantic schemas for sighting submissions list / public view."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


def _avatar_url_from_row(data: dict) -> dict:
    """Convert raw submitter_avatar filename → URL, if present."""
    avatar = data.pop("submitter_avatar", None)
    uid = data.get("submitter_id")
    if avatar and uid:
        data["submitter_avatar_url"] = f"/api/v1/media/avatar/{uid}"
    return data


def _comment_avatar_url(data: dict) -> dict:
    """Convert raw avatar_filename → URL for comments."""
    avatar = data.pop("avatar_filename", None)
    uid = data.get("user_id")
    if avatar and uid:
        data["avatar_url"] = f"/api/v1/media/avatar/{uid}"
    return data


class SubmissionSummary(BaseModel):
    """Compact summary for list views."""

    id: str
    created_at: datetime
    lat: float | None = None
    lon: float | None = None
    species_guess: str | None = None
    model_species: str | None = None
    model_confidence: float | None = None
    model_source: str | None = None
    interaction_type: str | None = None
    risk_category: str | None = None
    risk_score: float | None = None
    is_public: bool = False
    verification_status: str = "unverified"
    # Only present in user's own submissions
    advisory_level: str | None = None
    # Community-facing submitter info
    submitter_name: str | None = None
    submitter_id: int | None = None
    submitter_tier: str | None = None
    submitter_avatar_url: str | None = None
    # Media indicators
    has_photo: bool = False
    has_audio: bool = False

    @model_validator(mode="before")
    @classmethod
    def _resolve_avatar(cls, data: dict) -> dict:  # type: ignore[override]
        if isinstance(data, dict):
            return _avatar_url_from_row(data)
        return data


class SubmissionDetail(SubmissionSummary):
    """Full detail for a single submission (extends summary)."""

    h3_cell: int | None = None
    gps_source: str | None = None
    description: str | None = None
    photo_species: str | None = None
    photo_confidence: float | None = None
    audio_species: str | None = None
    audio_confidence: float | None = None
    advisory_message: str | None = None
    verification_notes: str | None = None
    verified_at: datetime | None = None
    photo_filename: str | None = None
    audio_filename: str | None = None


class SubmissionListResponse(BaseModel):
    """Paginated list of submissions."""

    total: int
    offset: int
    limit: int
    submissions: list[SubmissionSummary]


class VerifyRequest(BaseModel):
    """Request to verify or reject a public submission."""

    status: str = Field(..., description="verified, rejected, or disputed")
    notes: str | None = Field(
        None, max_length=500, description="Optional verification notes"
    )


# ── Comments ─────────────────────────────────────────────────


class CommentCreate(BaseModel):
    """Request body for creating a comment."""

    body: str = Field(..., min_length=1, max_length=2000, description="Comment text")


class CommentUpdate(BaseModel):
    """Request body for editing a comment."""

    body: str = Field(..., min_length=1, max_length=2000, description="Updated text")


class CommentResponse(BaseModel):
    """Single comment on a submission."""

    id: int
    submission_id: str
    user_id: int
    display_name: str | None = None
    reputation_tier: str | None = None
    avatar_url: str | None = None
    body: str
    created_at: datetime
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_avatar(cls, data: dict) -> dict:  # type: ignore[override]
        if isinstance(data, dict):
            return _comment_avatar_url(data)
        return data


class CommentListResponse(BaseModel):
    """Paginated list of comments."""

    total: int
    offset: int
    limit: int
    comments: list[CommentResponse]

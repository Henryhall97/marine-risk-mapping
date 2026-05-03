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
    community_agree: int = 0
    community_disagree: int = 0
    moderator_status: str | None = None
    # Only present in user's own submissions
    advisory_level: str | None = None
    # Community-facing submitter info
    submitter_name: str | None = None
    submitter_id: int | None = None
    submitter_tier: str | None = None
    submitter_avatar_url: str | None = None
    submitter_is_moderator: bool = False
    # Media indicators
    has_photo: bool = False
    has_audio: bool = False
    # Reputation-weighted verification confidence (0-100 or null)
    verification_score: float | None = None
    # Biological observation fields
    group_size: int | None = None
    behavior: str | None = None
    life_stage: str | None = None
    calf_present: bool | None = None
    sea_state_beaufort: int | None = None
    observation_platform: str | None = None
    scientific_name: str | None = None
    sighting_datetime: datetime | None = None
    # Taxonomic rank of the user's selection
    submitted_rank: str | None = None
    submitted_scientific_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_avatar(cls, data: dict) -> dict:  # type: ignore[override]
        if isinstance(data, dict):
            data = _avatar_url_from_row(data)
            # Derive verification_score from weighted vote counts
            agree = data.get("community_agree", 0) or 0
            disagree = data.get("community_disagree", 0) or 0
            total = agree + disagree
            if total > 0:
                data["verification_score"] = round((agree / total) * 100, 1)
        return data


class SubmissionDetail(SubmissionSummary):
    """Full detail for a single submission (extends summary).

    h3_cell is serialised as a string because H3 BIGINT values exceed
    JavaScript's Number.MAX_SAFE_INTEGER (2^53 − 1) and lose precision
    when parsed by JSON.parse().
    """

    h3_cell: str | None = None
    gps_source: str | None = None
    description: str | None = None
    photo_species: str | None = None
    photo_confidence: float | None = None
    audio_species: str | None = None
    audio_confidence: float | None = None
    advisory_message: str | None = None
    verification_notes: str | None = None
    verified_at: datetime | None = None
    moderator_id: int | None = None
    moderator_at: datetime | None = None
    moderator_notes: str | None = None
    photo_filename: str | None = None
    audio_filename: str | None = None


class SubmissionListResponse(BaseModel):
    """Paginated list of submissions."""

    total: int
    offset: int
    limit: int
    submissions: list[SubmissionSummary]


class MapSighting(BaseModel):
    """Lightweight sighting point for map display."""

    id: str
    lat: float
    lon: float
    species: str | None = None
    species_guess: str | None = None
    verification_status: str = "unverified"
    community_agree: int = 0
    community_disagree: int = 0
    has_photo: bool = False
    has_audio: bool = False
    interaction_type: str | None = None
    created_at: datetime


class MapSightingResponse(BaseModel):
    """Response wrapper for map sightings."""

    total: int
    data: list[MapSighting]


class VerifyRequest(BaseModel):
    """Request to verify or reject a public submission."""

    status: str = Field(..., description="verified, rejected, or disputed")
    notes: str | None = Field(
        None, max_length=500, description="Optional verification notes"
    )


class ModeratorVerifyRequest(BaseModel):
    """Moderator-only: set authoritative verification status."""

    status: str = Field(..., description="'verified' or 'rejected'")
    notes: str | None = Field(
        None, max_length=500, description="Optional moderator notes"
    )


class CommunityVoteRequest(BaseModel):
    """Community vote on a submission."""

    vote: str = Field(..., description="'agree', 'disagree', or 'refine'")
    notes: str | None = Field(None, max_length=500, description="Optional vote notes")
    species_suggestion: str | None = Field(
        None,
        max_length=50,
        description="Suggested species if disagreeing or refining ID",
    )
    suggested_rank: str | None = Field(
        None,
        max_length=20,
        description=("Taxonomic rank of the suggestion (species, genus, family, etc.)"),
    )


class VoteResponse(BaseModel):
    """A single community vote on a submission."""

    id: int
    user_id: int
    vote: str
    notes: str | None = None
    species_suggestion: str | None = None
    suggested_rank: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    display_name: str | None = None
    reputation_tier: str | None = None
    is_moderator: bool = False
    avatar_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_avatar(cls, data: dict) -> dict:  # type: ignore[override]
        if isinstance(data, dict):
            avatar = data.pop("avatar_filename", None)
            uid = data.get("user_id")
            if avatar and uid:
                data["avatar_url"] = f"/api/v1/media/avatar/{uid}"
        return data


# ── Comments ─────────────────────────────────────────────────


# ── Community stats ──────────────────────────────────────────


class RecentActivity(BaseModel):
    """Single recent-activity item for the feed."""

    id: str
    created_at: datetime
    lat: float | None = None
    lon: float | None = None
    species: str | None = None
    interaction_type: str | None = None
    verification_status: str = "unverified"
    has_photo: bool = False
    submitter_name: str | None = None
    submitter_id: int | None = None
    submitter_tier: str | None = None
    submitter_avatar_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_avatar(cls, data: dict) -> dict:  # type: ignore[override]
        if isinstance(data, dict):
            return _avatar_url_from_row(data)
        return data


class TopContributor(BaseModel):
    """A top contributor entry for the leaderboard."""

    user_id: int
    display_name: str | None = None
    reputation_score: int = 0
    reputation_tier: str = "newcomer"
    avatar_url: str | None = None
    submission_count: int = 0
    species_count: int = 0
    first_submission: datetime | None = None
    last_submission: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_avatar(cls, data: dict) -> dict:  # type: ignore[override]
        if isinstance(data, dict):
            avatar = data.pop("avatar_filename", None)
            uid = data.get("user_id")
            if avatar and uid:
                data["avatar_url"] = f"/api/v1/media/avatar/{uid}"
        return data


class CommunityStats(BaseModel):
    """Aggregate community statistics."""

    total_sightings: int = 0
    total_contributors: int = 0
    species_documented: int = 0
    verified_count: int = 0
    needs_review_count: int = 0
    photo_count: int = 0
    sightings_this_week: int = 0
    total_events: int = 0


class CommunityStatsResponse(BaseModel):
    """Full community stats response for the hero section."""

    stats: CommunityStats
    recent_activity: list[RecentActivity]
    top_contributors: list[TopContributor]
    activity_histogram: list[ActivityDay] = []
    whale_of_the_week: WhaleOfTheWeek | None = None


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


# ── Activity histogram + Whale of the Week ───────────────────


class ActivityDay(BaseModel):
    """Single day in the activity histogram."""

    date: str  # ISO date string
    count: int = 0


class WotWComment(BaseModel):
    """Comment attached to whale-of-the-week card."""

    id: int
    body: str
    created_at: datetime
    display_name: str | None = None
    reputation_tier: str | None = None
    avatar_url: str | None = None
    user_id: int | None = None


class WhaleOfTheWeek(BaseModel):
    """The most-engaged photo submission from the past week."""

    id: str
    created_at: datetime
    lat: float | None = None
    lon: float | None = None
    species: str | None = None
    model_confidence: float | None = None
    verification_status: str = "unverified"
    community_agree: int = 0
    community_disagree: int = 0
    comment_count: int = 0
    vote_count: int = 0
    submitter_name: str | None = None
    submitter_id: int | None = None
    submitter_tier: str | None = None
    submitter_avatar_url: str | None = None
    top_comments: list[WotWComment] = []

    @model_validator(mode="before")
    @classmethod
    def _resolve_avatar(cls, data: dict) -> dict:  # type: ignore[override]
        if isinstance(data, dict):
            return _avatar_url_from_row(data)
        return data

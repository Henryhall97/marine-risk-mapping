"""Pydantic schemas for community events."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


def _creator_avatar_url(data: dict) -> dict:
    """Convert raw creator_avatar filename → URL, if present."""
    avatar = data.pop("creator_avatar", None)
    uid = data.get("creator_id")
    if avatar and uid:
        data["creator_avatar_url"] = f"/api/v1/media/avatar/{uid}"
    return data


# ── Request schemas ──────────────────────────────────────────


class EventCreate(BaseModel):
    """Request body for creating a community event."""

    title: str = Field(..., min_length=3, max_length=200, description="Event title")
    description: str | None = Field(
        None, max_length=5000, description="Event description"
    )
    event_type: str = Field(
        default="whale_watching",
        description=(
            "Event type: whale_watching, research_expedition, "
            "citizen_science, cleanup, educational, other"
        ),
    )
    start_date: date | None = Field(None, description="Event start date")
    end_date: date | None = Field(None, description="Event end date")
    lat: float | None = Field(None, ge=-90, le=90, description="Centre latitude")
    lon: float | None = Field(None, ge=-180, le=180, description="Centre longitude")
    location_name: str | None = Field(
        None, max_length=200, description="Human-readable location"
    )
    is_public: bool = Field(
        default=True, description="Whether the event is publicly visible"
    )
    vessel_id: int | None = Field(None, description="Link a vessel to this event")


class EventUpdate(BaseModel):
    """Request body for updating a community event."""

    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=5000)
    event_type: str | None = None
    status: str | None = Field(
        None,
        description="upcoming, active, completed, cancelled",
    )
    start_date: date | None = None
    end_date: date | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    location_name: str | None = Field(None, max_length=200)
    is_public: bool | None = None
    vessel_id: int | None = None


# ── Response schemas ─────────────────────────────────────────


class EventMember(BaseModel):
    """A member of an event."""

    user_id: int
    display_name: str
    role: str = "member"
    joined_at: datetime
    reputation_tier: str = "newcomer"
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


class EventSummary(BaseModel):
    """Compact event for list views."""

    id: str
    title: str
    description: str | None = None
    event_type: str = "whale_watching"
    status: str = "upcoming"
    start_date: date | None = None
    end_date: date | None = None
    lat: float | None = None
    lon: float | None = None
    location_name: str | None = None
    is_public: bool = True
    invite_code: str
    created_at: datetime
    creator_id: int
    creator_name: str | None = None
    creator_avatar_url: str | None = None
    creator_tier: str | None = None
    member_count: int = 0
    sighting_count: int = 0
    my_role: str | None = None
    vessel_id: int | None = None
    vessel_name: str | None = None
    vessel_type: str | None = None
    cover_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_avatar(cls, data: dict) -> dict:  # type: ignore[override]
        if isinstance(data, dict):
            return _creator_avatar_url(data)
        return data


class EventDetail(EventSummary):
    """Full event detail — extends summary with members list."""

    updated_at: datetime | None = None
    members: list[EventMember] = Field(default_factory=list)


class EventListResponse(BaseModel):
    """Paginated list of events."""

    total: int
    offset: int
    limit: int
    events: list[EventSummary]


# ── Comment schemas ──────────────────────────────────────────


def _comment_avatar_url(data: dict) -> dict:
    """Convert raw avatar_filename → URL, if present."""
    avatar = data.pop("avatar_filename", None)
    uid = data.get("user_id")
    if avatar and uid:
        data["avatar_url"] = f"/api/v1/media/avatar/{uid}"
    return data


class EventCommentCreate(BaseModel):
    """Request body for adding a comment to an event."""

    body: str = Field(..., min_length=1, max_length=2000)


class EventCommentUpdate(BaseModel):
    """Request body for editing a comment."""

    body: str = Field(..., min_length=1, max_length=2000)


class EventComment(BaseModel):
    """An event comment with author information."""

    id: int
    event_id: str
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


class EventCommentListResponse(BaseModel):
    """Paginated list of event comments."""

    comments: list[EventComment]
    total: int
    limit: int
    offset: int


# ── Summary stats ────────────────────────────────────────────


class SpeciesCount(BaseModel):
    """A species + count pair."""

    species: str
    count: int


class EventStats(BaseModel):
    """Fun summary statistics for an event."""

    total_sightings: int = 0
    unique_species: int = 0
    species_breakdown: list[SpeciesCount] = Field(default_factory=list)
    unique_contributors: int = 0
    top_contributors: list[dict] = Field(default_factory=list)
    verified_count: int = 0
    has_photo_count: int = 0
    has_audio_count: int = 0
    highest_risk_score: float | None = None
    highest_risk_category: str | None = None
    avg_risk_score: float | None = None
    date_range_start: str | None = None
    date_range_end: str | None = None
    interaction_types: list[dict] = Field(default_factory=list)

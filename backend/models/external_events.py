"""Pydantic schemas for curated external events."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

# ── Request schemas ──────────────────────────────────────────


class ExternalEventCreate(BaseModel):
    """Request body for creating an external event (moderator only)."""

    title: str = Field(..., min_length=3, max_length=300)
    description: str | None = Field(None, max_length=5000)
    organizer: str = Field(..., min_length=2, max_length=200)
    source_url: str | None = Field(None, max_length=500)
    event_type: str = Field(
        default="other",
        description=(
            "workshop, webinar, public_comment, conference, "
            "education, research, cleanup, other"
        ),
    )
    tags: list[str] | None = Field(None, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    location_name: str | None = Field(None, max_length=200)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    is_virtual: bool = False
    is_featured: bool = False


class ExternalEventUpdate(BaseModel):
    """Request body for updating an external event (moderator only)."""

    title: str | None = Field(None, min_length=3, max_length=300)
    description: str | None = Field(None, max_length=5000)
    organizer: str | None = Field(None, min_length=2, max_length=200)
    source_url: str | None = Field(None, max_length=500)
    event_type: str | None = None
    tags: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None
    location_name: str | None = Field(None, max_length=200)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    is_virtual: bool | None = None
    is_featured: bool | None = None
    is_active: bool | None = None


# ── Response schemas ─────────────────────────────────────────


class ExternalEventResponse(BaseModel):
    """A curated external event."""

    id: int
    title: str
    description: str | None = None
    organizer: str
    source_url: str | None = None
    event_type: str = "other"
    tags: list[str] = Field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    location_name: str | None = None
    lat: float | None = None
    lon: float | None = None
    is_virtual: bool = False
    is_featured: bool = False
    is_active: bool = True
    created_at: datetime
    updated_at: datetime | None = None


class ExternalEventListResponse(BaseModel):
    """Paginated list of external events."""

    total: int
    offset: int
    limit: int
    events: list[ExternalEventResponse]

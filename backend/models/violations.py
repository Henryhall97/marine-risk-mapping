"""Pydantic schemas for vessel violation reports."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ViolationSummary(BaseModel):
    """Compact summary for list views."""

    id: str
    created_at: datetime
    lat: float
    lon: float
    violation_type: str
    vessel_name: str | None = None
    vessel_type: str | None = None
    estimated_speed_knots: float | None = None
    description: str | None = None
    zone_name: str | None = None
    zone_type: str | None = None
    risk_category: str | None = None
    is_public: bool = False
    review_status: str = "pending"
    community_confirm: int = 0
    community_dispute: int = 0
    has_photo: bool = False
    # Submitter info
    submitter_name: str | None = None
    submitter_id: int | None = None


class ViolationDetail(ViolationSummary):
    """Full detail for a single violation report."""

    h3_cell: str | None = None
    vessel_length_estimate: str | None = None
    heading: str | None = None
    observed_at: datetime | None = None
    risk_score: float | None = None
    review_notes: str | None = None
    reviewed_at: datetime | None = None


class ViolationListResponse(BaseModel):
    """Paginated list of violation reports."""

    reports: list[ViolationSummary]
    total: int
    limit: int
    offset: int


class ViolationDetailResponse(BaseModel):
    """Wrapper for single violation detail."""

    report: ViolationDetail


class ViolationCreateResponse(BaseModel):
    """Response after creating a new violation report."""

    id: str
    message: str = "Violation report submitted successfully"
    risk_score: float | None = None
    risk_category: str | None = None
    zone_name: str | None = None
    zone_type: str | None = None

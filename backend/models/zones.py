"""Pydantic schemas for regulatory zone geometry endpoints.

These return actual polygon/multipolygon geometries (as GeoJSON)
for map overlays — unlike the H3-aggregated layer endpoints.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Speed zones (current SMAs) ──────────────────────────────


class CurrentSpeedZone(BaseModel):
    """An active Seasonal Management Area (50 CFR § 224.105)."""

    id: int
    zone_name: str
    zone_abbr: str | None = None
    start_month: int
    start_day: int
    end_month: int
    end_day: int
    season_label: str | None = None
    is_active: bool | None = Field(
        None,
        description=(
            "Whether the zone is active on the requested date "
            "(or today if no date was supplied)."
        ),
    )
    area_sq_deg: float | None = None
    perimeter_deg: float | None = None
    geometry: dict[str, Any] = Field(..., description="GeoJSON Polygon geometry")


class CurrentSpeedZoneListResponse(BaseModel):
    """All current SMAs (small static dataset — no pagination)."""

    total: int
    data: list[CurrentSpeedZone]


# ── Speed zones (proposed) ──────────────────────────────────


class ProposedSpeedZone(BaseModel):
    """A proposed NARW speed restriction zone."""

    id: int
    zone_name: str
    start_month: int
    start_day: int
    end_month: int
    end_day: int
    season_label: str | None = None
    is_active: bool | None = Field(
        None,
        description=(
            "Whether the zone would be active on the "
            "requested date (or today if omitted)."
        ),
    )
    area_sq_deg: float | None = None
    perimeter_deg: float | None = None
    geometry: dict[str, Any] = Field(..., description="GeoJSON Polygon geometry")


class ProposedSpeedZoneListResponse(BaseModel):
    """All proposed speed zones (small static dataset)."""

    total: int
    data: list[ProposedSpeedZone]


# ── Marine Protected Areas ──────────────────────────────────


class MarineProtectedArea(BaseModel):
    """An MPA from the NOAA MPA Inventory."""

    id: int
    site_id: str | None = None
    site_name: str | None = None
    gov_level: str | None = None
    state: str | None = None
    protection_level: str | None = None
    managing_agency: str | None = None
    iucn_category: str | None = None
    established_year: int | None = None
    area_total_km2: float | None = None
    area_marine_km2: float | None = None
    marine_percent: int | None = None
    geometry: dict[str, Any] = Field(..., description="GeoJSON MultiPolygon geometry")


class MPAListDetailResponse(BaseModel):
    """Paginated MPA features with full geometry."""

    total: int
    offset: int
    limit: int
    data: list[MarineProtectedArea]

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


# ── Biologically Important Areas ────────────────────────────


class BiologicallyImportantArea(BaseModel):
    """A NOAA CetMap Biologically Important Area."""

    id: int
    bia_id: str | None = None
    region: str | None = None
    sci_name: str | None = None
    cmn_name: str | None = None
    bia_name: str | None = None
    bia_type: str | None = Field(
        None,
        description="BIA category: Feeding, Reproduction, Migration, etc.",
    )
    bia_months: str | None = Field(
        None,
        description="Active months as comma-separated numbers (e.g. '03,04,11,12')",
    )
    geometry: dict[str, Any] = Field(
        ..., description="GeoJSON Polygon/MultiPolygon geometry"
    )


class BIAListResponse(BaseModel):
    """Paginated BIA features."""

    total: int
    offset: int
    limit: int
    data: list[BiologicallyImportantArea]


# ── Critical Habitat ────────────────────────────────────────


class CriticalHabitat(BaseModel):
    """An ESA Critical Habitat designation for a whale species."""

    id: int
    species_label: str
    sci_name: str | None = None
    cmn_name: str | None = None
    list_status: str | None = None
    ch_status: str | None = Field(
        None,
        description="Final or Proposed",
    )
    unit: str | None = None
    area_sq_km: float | None = None
    is_proposed: bool = False
    geometry: dict[str, Any] = Field(
        ..., description="GeoJSON Polygon/MultiPolygon geometry"
    )


class CriticalHabitatListResponse(BaseModel):
    """Critical Habitat features (small dataset — light pagination)."""

    total: int
    data: list[CriticalHabitat]


# ── Shipping Lanes ──────────────────────────────────────────


class ShippingLane(BaseModel):
    """A shipping lane or routing regulation polygon."""

    id: int
    zone_type: str
    name: str | None = None
    description: str | None = None
    geometry: dict[str, Any] = Field(..., description="GeoJSON Polygon geometry")


class ShippingLaneListResponse(BaseModel):
    """Paginated shipping lane features."""

    total: int
    offset: int
    limit: int
    data: list[ShippingLane]


# ── Slow Zones ──────────────────────────────────────────────


class SlowZone(BaseModel):
    """An active Right Whale Slow Zone / DMA."""

    id: int
    zone_name: str
    zone_type: str | None = None
    effective_start: str | None = None
    effective_end: str | None = None
    speed_limit_kn: int | None = 10
    voluntary: bool = True
    duration_days: int | None = 15
    is_expired: bool | None = Field(
        None,
        description="Whether this zone has expired based on effective_end.",
    )
    geometry: dict[str, Any] = Field(..., description="GeoJSON Polygon geometry")


class SlowZoneListResponse(BaseModel):
    """All active slow zones (small dataset — no pagination)."""

    total: int
    data: list[SlowZone]

"""Regulatory zone geometry endpoints.

3 endpoints returning actual polygon/multipolygon GeoJSON for
map overlays: current SMAs, proposed speed zones, and MPAs.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.config import DEFAULT_PAGE_SIZE, MAX_BBOX_AREA_DEG2, MAX_PAGE_SIZE
from backend.models.zones import (
    CurrentSpeedZone,
    CurrentSpeedZoneListResponse,
    MarineProtectedArea,
    MPAListDetailResponse,
    ProposedSpeedZone,
    ProposedSpeedZoneListResponse,
)
from backend.services import zones as zone_svc

router = APIRouter(prefix="/zones", tags=["zones"])


# ── Current SMAs ────────────────────────────────────────────


@router.get(
    "/speed-zones/current",
    response_model=CurrentSpeedZoneListResponse,
)
def list_current_speed_zones(
    active_on: date | None = Query(  # noqa: B008
        None,
        description=(
            "Date to check zone activity (YYYY-MM-DD). "
            "Defaults to today. Each zone gets an "
            "is_active flag you can use for styling."
        ),
    ),
):
    """Active Seasonal Management Areas (50 CFR § 224.105).

    Returns all 10 SMAs with full polygon geometry for map overlay.
    Each zone includes an ``is_active`` flag indicating whether
    it is active on the given date (defaults to today).
    Small static dataset — no bbox or pagination needed.
    """
    rows = zone_svc.get_current_speed_zones(check_date=active_on)
    data = [CurrentSpeedZone(**r) for r in rows]
    return CurrentSpeedZoneListResponse(total=len(data), data=data)


# ── Proposed speed zones ────────────────────────────────────


@router.get(
    "/speed-zones/proposed",
    response_model=ProposedSpeedZoneListResponse,
)
def list_proposed_speed_zones(
    active_on: date | None = Query(  # noqa: B008
        None,
        description=(
            "Date to check zone activity (YYYY-MM-DD). "
            "Defaults to today. Each zone gets an "
            "is_active flag you can use for styling."
        ),
    ),
):
    """Proposed NARW speed restriction zones.

    Returns all 5 proposed zones with full polygon geometry.
    Each zone includes an ``is_active`` flag indicating whether
    it would be active on the given date (defaults to today).
    Small static dataset — no bbox or pagination needed.
    """
    rows = zone_svc.get_proposed_speed_zones(check_date=active_on)
    data = [ProposedSpeedZone(**r) for r in rows]
    return ProposedSpeedZoneListResponse(total=len(data), data=data)


# ── MPAs ────────────────────────────────────────────────────


def _validate_bbox(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> None:
    """Shared bbox validation."""
    if lat_min >= lat_max:
        raise HTTPException(400, "lat_min must be less than lat_max")
    if lon_min >= lon_max:
        raise HTTPException(400, "lon_min must be less than lon_max")
    area = (lat_max - lat_min) * (lon_max - lon_min)
    if area > MAX_BBOX_AREA_DEG2:
        raise HTTPException(
            400,
            f"Bounding box area ({area:.1f} deg²) exceeds "
            f"maximum ({MAX_BBOX_AREA_DEG2} deg²). "
            "Narrow your query region.",
        )


@router.get(
    "/mpas",
    response_model=MPAListDetailResponse,
)
def list_mpa_features(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    protection_level: str | None = Query(
        None,
        description=(
            "Filter by protection level "
            "(e.g. 'No Take', 'No Access', "
            "'Uniform Multiple Use')"
        ),
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Marine Protected Areas with full polygon geometry.

    Returns MPA features intersecting the bounding box.
    Includes site name, protection level, managing agency,
    and GeoJSON MultiPolygon geometry for overlay rendering.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    total = zone_svc.count_mpa_features(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        protection_level=protection_level,
    )
    rows = zone_svc.get_mpa_features(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        protection_level=protection_level,
        limit=limit,
        offset=offset,
    )
    data = [MarineProtectedArea(**r) for r in rows]
    return MPAListDetailResponse(total=total, offset=offset, limit=limit, data=data)

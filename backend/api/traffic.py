"""Traffic endpoints.

GET /api/v1/traffic/monthly  — Monthly vessel traffic within a bounding box
GET /api/v1/traffic/seasonal — Seasonal traffic aggregates within a bounding box
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.config import DEFAULT_PAGE_SIZE, MAX_BBOX_AREA_DEG2, MAX_PAGE_SIZE
from backend.models.layers import (
    SeasonalTrafficCell,
    SeasonalTrafficListResponse,
)
from backend.models.traffic import (
    MonthlyTrafficCell,
    MonthlyTrafficListResponse,
)
from backend.services import layers as layer_svc
from backend.services import traffic as traffic_svc

router = APIRouter(prefix="/traffic", tags=["traffic"])

_VALID_SEASONS = {"winter", "spring", "summer", "fall"}


@router.get("/monthly", response_model=MonthlyTrafficListResponse)
def list_monthly_traffic(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    month_start: str | None = Query(
        None,
        description="Start month filter (YYYY-MM-DD or YYYY-MM-01)",
    ),
    month_end: str | None = Query(
        None,
        description="End month filter (YYYY-MM-DD or YYYY-MM-01)",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Monthly vessel traffic aggregates within a bounding box.

    Returns H3 cells from fct_monthly_traffic with vessel counts,
    speed statistics, and vessel type breakdowns.
    Ordered by month descending, then total_pings descending.
    """
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

    total = traffic_svc.count_monthly_traffic(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        month_start=month_start,
        month_end=month_end,
    )
    rows = traffic_svc.get_monthly_traffic(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        month_start=month_start,
        month_end=month_end,
        limit=limit,
        offset=offset,
    )
    data = [MonthlyTrafficCell(**r) for r in rows]
    return MonthlyTrafficListResponse(
        total=total, offset=offset, limit=limit, data=data
    )


@router.get("/seasonal", response_model=SeasonalTrafficListResponse)
def list_seasonal_traffic(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    season: str | None = Query(
        None,
        description="Filter by season (winter/spring/summer/fall)",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Seasonal traffic aggregates within a bounding box.

    Vessel counts, speed, and type breakdowns at (h3_cell, season).
    From int_vessel_traffic_seasonal.
    """
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
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season. Must be one of: {sorted(_VALID_SEASONS)}",
        )

    total = layer_svc.count_seasonal_traffic(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
    )
    rows = layer_svc.get_seasonal_traffic(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        limit=limit,
        offset=offset,
    )
    data = [SeasonalTrafficCell(**r) for r in rows]
    return SeasonalTrafficListResponse(
        total=total, offset=offset, limit=limit, data=data
    )

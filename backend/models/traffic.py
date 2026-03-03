"""Pydantic schemas for vessel traffic endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class MonthlyTrafficCell(BaseModel):
    """Monthly traffic statistics for a single (h3_cell, month)."""

    h3_cell: int
    month: str  # ISO date string YYYY-MM-DD
    cell_lat: float
    cell_lon: float
    unique_vessels: int | None = None
    ping_count: int | None = None
    vw_avg_speed_knots: float | None = None
    max_speed_knots: float | None = None
    high_speed_vessel_count: int | None = None
    large_vessel_count: int | None = None
    day_unique_vessels: int | None = None
    night_unique_vessels: int | None = None
    cargo_vessels: int | None = None
    tanker_vessels: int | None = None
    fishing_vessels: int | None = None
    passenger_vessels: int | None = None
    depth_zone: str | None = None
    is_continental_shelf: bool | None = None
    in_mpa: bool | None = None


class MonthlyTrafficListResponse(BaseModel):
    """Paginated list of monthly traffic cells."""

    total: int
    offset: int
    limit: int
    data: list[MonthlyTrafficCell]

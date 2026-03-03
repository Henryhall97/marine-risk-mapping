"""Shared Pydantic schemas used across multiple endpoint groups."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Geographic bounding box (WGS-84)."""

    lat_min: float = Field(..., ge=-90, le=90)
    lat_max: float = Field(..., ge=-90, le=90)
    lon_min: float = Field(..., ge=-180, le=180)
    lon_max: float = Field(..., ge=-180, le=180)


class PaginationParams(BaseModel):
    """Pagination query parameters."""

    offset: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=5000)


class PaginatedResponse(BaseModel):
    """Wrapper for paginated list responses."""

    total: int
    offset: int
    limit: int
    data: list

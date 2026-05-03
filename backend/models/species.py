"""Pydantic schemas for species risk endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class SpeciesInfo(BaseModel):
    """Species metadata from the crosswalk seed."""

    species_group: str
    common_name: str | None = None
    scientific_name: str | None = None
    is_baleen: bool | None = None
    conservation_priority: str | None = None


class CrosswalkEntry(BaseModel):
    """Full crosswalk row — maps species across naming systems."""

    scientific_name: str
    common_name: str | None = None
    species_group: str | None = None
    nisi_species: str | None = None
    strike_species: str | None = None
    taxonomic_rank: str | None = None
    family: str | None = None
    is_baleen: bool | None = None
    conservation_priority: str | None = None


class CrosswalkResponse(BaseModel):
    """Full species crosswalk table."""

    total: int
    data: list[CrosswalkEntry]


class SpeciesRiskCell(BaseModel):
    """Per-species risk for a single H3 cell."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    species: str
    common_name: str | None = None
    species_group: str | None = None
    is_baleen: bool | None = None
    sighting_count: int | None = None
    earliest_year: int | None = None
    latest_year: int | None = None
    avg_monthly_vessels: float | None = None
    avg_speed_knots: float | None = None
    depth_m: float | None = None
    depth_zone: str | None = None
    in_speed_zone: bool | None = None
    mpa_count: int | None = None
    species_risk_score: float | None = None


class SpeciesListResponse(BaseModel):
    """Non-paginated list of all species."""

    total: int
    data: list[SpeciesInfo]


class SpeciesRiskListResponse(BaseModel):
    """Paginated list of per-species risk cells."""

    total: int
    offset: int
    limit: int
    data: list[SpeciesRiskCell]

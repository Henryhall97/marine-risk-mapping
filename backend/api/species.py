"""Species risk endpoints.

GET /api/v1/species          — List available species from crosswalk
GET /api/v1/species/risk     — Per-species risk cells within a bounding box
GET /api/v1/species/seasonal — Seasonal cetacean density within a bounding box
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.config import DEFAULT_PAGE_SIZE, MAX_BBOX_AREA_DEG2, MAX_PAGE_SIZE
from backend.models.layers import (
    SeasonalSpeciesCell,
    SeasonalSpeciesListResponse,
)
from backend.models.species import (
    CrosswalkEntry,
    CrosswalkResponse,
    SpeciesInfo,
    SpeciesListResponse,
    SpeciesRiskCell,
    SpeciesRiskListResponse,
)
from backend.services import layers as layer_svc
from backend.services import species as species_svc

router = APIRouter(prefix="/species", tags=["species"])

_VALID_SEASONS = {"winter", "spring", "summer", "fall"}


@router.get("", response_model=SpeciesListResponse)
def list_species():
    """Return all species from the crosswalk seed table.

    Includes common name, scientific name, baleen flag,
    and conservation priority.
    """
    rows = species_svc.list_species()
    data = [SpeciesInfo(**r) for r in rows]
    return SpeciesListResponse(total=len(data), data=data)


@router.get("/crosswalk", response_model=CrosswalkResponse)
def get_crosswalk():
    """Return the full species crosswalk table.

    Shows how species map across OBIS (scientific_name),
    Nisi ISDM (nisi_species), and NMFS ship-strike
    (strike_species) naming systems.
    """
    rows = species_svc.list_crosswalk()
    data = [CrosswalkEntry(**r) for r in rows]
    return CrosswalkResponse(total=len(data), data=data)


@router.get("/risk", response_model=SpeciesRiskListResponse)
def list_species_risk(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    species_group: str | None = Query(
        None,
        description="Filter by species_group (e.g. 'right_whale')",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Per-species risk data within a bounding box.

    Returns H3 cells from fct_species_risk with species-specific
    sightings, strike counts, and environment indicators.
    Ordered by risk_score descending, then species_group.
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

    total = species_svc.count_species_risk(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        species_group=species_group,
    )
    rows = species_svc.get_species_risk(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        species_group=species_group,
        limit=limit,
        offset=offset,
    )
    data = [SpeciesRiskCell(**r) for r in rows]
    return SpeciesRiskListResponse(total=total, offset=offset, limit=limit, data=data)


@router.get("/seasonal", response_model=SeasonalSpeciesListResponse)
def list_seasonal_species(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    season: str | None = Query(
        None,
        description="Filter by season (winter/spring/summer/fall)",
    ),
    min_sightings: int | None = Query(
        None,
        ge=1,
        description="Minimum total_sightings filter",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Seasonal cetacean density at (h3_cell, season) grain.

    Per-species sighting counts from int_cetacean_density_seasonal.
    Filter by season and/or minimum sightings.
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

    total = layer_svc.count_seasonal_species(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        min_sightings=min_sightings,
    )
    rows = layer_svc.get_seasonal_species(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        min_sightings=min_sightings,
        limit=limit,
        offset=offset,
    )
    data = [SeasonalSpeciesCell(**r) for r in rows]
    return SeasonalSpeciesListResponse(
        total=total, offset=offset, limit=limit, data=data
    )

"""Macro overview routes — coast-wide pre-aggregated data."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.models.macro import MacroCell, MacroOverviewResponse
from backend.services.macro import get_macro_overview

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/macro", tags=["macro"])

CONTOUR_PATH = Path("data/processed/macro/bathymetry_contours.geojson")

# Cache the contour GeoJSON in memory (static data, loaded once)
_contour_cache: dict | None = None


@router.get("/overview", response_model=MacroOverviewResponse)
def macro_overview(
    season: str = Query(
        "annual",
        description=("Season filter: annual, winter, spring, summer, fall"),
    ),
) -> MacroOverviewResponse:
    """Coast-wide risk overview at H3 res-4 (~57 km² hexagons).

    Returns all coarse cells for the requested season in a single
    response (typically ~5 500 cells).  No bbox or pagination needed.
    """
    rows = get_macro_overview(season)
    data = [MacroCell(**r) for r in rows]
    return MacroOverviewResponse(
        total=len(data),
        season=season,
        data=data,
    )


@router.get("/contours/bathymetry")
def bathymetry_contours() -> dict:
    """Pre-computed bathymetry depth contour lines as GeoJSON.

    Returns a FeatureCollection of MultiLineString features at
    standard depth levels (50, 100, 200, 500, 1000, 2000, 4000 m).
    """
    global _contour_cache  # noqa: PLW0603

    if _contour_cache is not None:
        return _contour_cache

    if not CONTOUR_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Bathymetry contours not generated yet. "
                "Run: uv run python "
                "pipeline/aggregation/generate_contours.py"
            ),
        )

    _contour_cache = json.loads(CONTOUR_PATH.read_text())
    logger.info(
        "Loaded bathymetry contours: %d features",
        len(_contour_cache.get("features", [])),
    )
    return _contour_cache

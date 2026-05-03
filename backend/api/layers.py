"""Spatial layer overlay endpoints.

9 layer endpoints exposing intermediate dbt tables as map overlays.
All endpoints follow the same pattern: bbox + optional filters + pagination.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.config import (
    DEFAULT_PAGE_SIZE,
    MAX_BBOX_AREA_DEG2,
    MAX_PAGE_SIZE,
    US_BBOX,
)
from backend.models.layers import (
    BathymetryCell,
    BathymetryListResponse,
    CetaceanDensityCell,
    CetaceanDensityListResponse,
    IsdmProjectionCell,
    IsdmProjectionListResponse,
    MPACell,
    MPAListResponse,
    NisiRiskCell,
    NisiRiskListResponse,
    OceanCovariateCell,
    OceanCovariateListResponse,
    ProjectionSummaryResponse,
    ProjectionSummaryRow,
    ProximityCell,
    ProximityListResponse,
    SdmPredictionCell,
    SdmPredictionListResponse,
    SdmProjectionCell,
    SdmProjectionListResponse,
    SpeedZoneCell,
    SpeedZoneListResponse,
    StrikeDensityCell,
    StrikeDensityListResponse,
    TrafficDensityCell,
    TrafficDensityListResponse,
    WhalePredictionCell,
    WhalePredictionListResponse,
)
from backend.services import layers as layer_svc

router = APIRouter(prefix="/layers", tags=["layers"])

_VALID_SEASONS = {"winter", "spring", "summer", "fall"}
_VALID_DEPTH_ZONES = {
    "shallow",
    "continental_shelf",
    "shelf_edge",
    "slope",
    "deep_ocean",
    "land",
}
_VALID_ISDM_SPECIES = {
    "blue_whale",
    "fin_whale",
    "humpback_whale",
    "sperm_whale",
}
_VALID_SDM_SPECIES = {
    "blue_whale",
    "fin_whale",
    "humpback_whale",
    "sperm_whale",
    "right_whale",
    "minke_whale",
}
_VALID_SCENARIOS = {"ssp245", "ssp585"}
_VALID_DECADES = {"2030s", "2040s", "2060s", "2080s"}


def _validate_bbox(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    *,
    skip_area_check: bool = False,
) -> None:
    """Shared bbox validation — raises HTTPException on failure."""
    if lat_min >= lat_max:
        raise HTTPException(400, "lat_min must be less than lat_max")
    if lon_min >= lon_max:
        raise HTTPException(400, "lon_min must be less than lon_max")
    if not skip_area_check:
        area = (lat_max - lat_min) * (lon_max - lon_min)
        if area > MAX_BBOX_AREA_DEG2:
            raise HTTPException(
                400,
                f"Bounding box area ({area:.1f} deg²) exceeds "
                f"maximum ({MAX_BBOX_AREA_DEG2} deg²). "
                "Narrow your query region.",
            )


# ── Bathymetry ──────────────────────────────────────────────


@router.get("/bathymetry", response_model=BathymetryListResponse)
def list_bathymetry(
    lat_min: float | None = Query(
        None,
        ge=-90,
        le=90,
        description="Defaults to US bbox (2°S) if omitted.",
    ),
    lat_max: float | None = Query(
        None,
        ge=-90,
        le=90,
        description="Defaults to US bbox (74°N) if omitted.",
    ),
    lon_min: float | None = Query(
        None,
        ge=-180,
        le=180,
        description="Defaults to US bbox (−180°W) if omitted.",
    ),
    lon_max: float | None = Query(
        None,
        ge=-180,
        le=180,
        description="Defaults to US bbox (−59°W) if omitted.",
    ),
    depth_zone: str | None = Query(None),
    exclude_land: bool = Query(
        True,
        description="Exclude land cells (default True).",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Bathymetry layer — depth, depth zone, shelf flags.

    Bbox is optional — omit to get the full study-area extent.
    Land cells are excluded by default (set exclude_land=false
    to include them).
    Optional filter by depth_zone (shallow, continental_shelf,
    shelf_edge, slope, deep_ocean, land).
    """
    using_defaults = (
        lat_min is None or lat_max is None or lon_min is None or lon_max is None
    )
    lat_min = lat_min if lat_min is not None else US_BBOX["lat_min"]
    lat_max = lat_max if lat_max is not None else US_BBOX["lat_max"]
    lon_min = lon_min if lon_min is not None else US_BBOX["lon_min"]
    lon_max = lon_max if lon_max is not None else US_BBOX["lon_max"]
    _validate_bbox(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        skip_area_check=using_defaults,
    )
    if depth_zone and depth_zone not in _VALID_DEPTH_ZONES:
        raise HTTPException(
            400,
            f"Invalid depth_zone. Must be one of: {sorted(_VALID_DEPTH_ZONES)}",
        )
    total = layer_svc.count_bathymetry(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        depth_zone=depth_zone,
        exclude_land=exclude_land,
    )
    rows = layer_svc.get_bathymetry(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        depth_zone=depth_zone,
        exclude_land=exclude_land,
        limit=limit,
        offset=offset,
    )
    data = [BathymetryCell(**r) for r in rows]
    return BathymetryListResponse(
        total=total,
        offset=offset,
        limit=limit,
        data=data,
    )


# ── Ocean covariates ────────────────────────────────────────


@router.get("/ocean", response_model=OceanCovariateListResponse)
def list_ocean_covariates(
    lat_min: float | None = Query(
        None,
        ge=-90,
        le=90,
        description="Defaults to US bbox (2°S) if omitted.",
    ),
    lat_max: float | None = Query(
        None,
        ge=-90,
        le=90,
        description="Defaults to US bbox (74°N) if omitted.",
    ),
    lon_min: float | None = Query(
        None,
        ge=-180,
        le=180,
        description="Defaults to US bbox (−180°W) if omitted.",
    ),
    lon_max: float | None = Query(
        None,
        ge=-180,
        le=180,
        description="Defaults to US bbox (−59°W) if omitted.",
    ),
    season: str | None = Query(
        None,
        description=(
            "Filter by season. Use 'winter', 'spring', 'summer', "
            "'fall' for one season, 'all' for all four seasons, "
            "or omit for the annual mean."
        ),
    ),
    scenario: str | None = Query(
        None,
        description=(
            "Climate scenario for projections: ssp245 or ssp585. "
            "When provided with decade, returns projected covariates."
        ),
    ),
    decade: str | None = Query(
        None,
        description=(
            "Projection decade: 2030s, 2040s, 2060s, or 2080s. "
            "Required when scenario is provided."
        ),
    ),
    mode: str = Query(
        "absolute",
        description=(
            "'absolute' returns projected values; 'change' returns "
            "projected values plus delta columns vs current baseline."
        ),
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Ocean covariates — SST, MLD, SLA, primary productivity.

    Bbox is optional — omit to get the full study-area extent.
    Without season: returns annual mean from int_ocean_covariates.
    With season=<name>: returns values for that season.
    With season=all: returns all 4 seasons (4× rows per cell).
    With scenario + decade: returns CMIP6 projected covariates.
    Set **mode=change** to include delta columns comparing each
    projected value against the current seasonal baseline.
    """
    using_defaults = (
        lat_min is None or lat_max is None or lon_min is None or lon_max is None
    )
    lat_min = lat_min if lat_min is not None else US_BBOX["lat_min"]
    lat_max = lat_max if lat_max is not None else US_BBOX["lat_max"]
    lon_min = lon_min if lon_min is not None else US_BBOX["lon_min"]
    lon_max = lon_max if lon_max is not None else US_BBOX["lon_max"]
    _validate_bbox(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        skip_area_check=using_defaults,
    )
    _valid_season_opts = _VALID_SEASONS | {"all"}
    if season and season not in _valid_season_opts:
        raise HTTPException(
            400,
            f"Invalid season. Must be one of: {sorted(_VALID_SEASONS)} or 'all'.",
        )
    # Validate projection params
    if scenario and scenario not in _VALID_SCENARIOS:
        raise HTTPException(
            400,
            f"Invalid scenario. Must be one of: {sorted(_VALID_SCENARIOS)}",
        )
    if decade and decade not in _VALID_DECADES:
        raise HTTPException(
            400,
            f"Invalid decade. Must be one of: {sorted(_VALID_DECADES)}",
        )
    if (scenario and not decade) or (decade and not scenario):
        raise HTTPException(
            400,
            "Both scenario and decade are required for projections.",
        )
    if mode not in ("absolute", "change"):
        raise HTTPException(
            400,
            "Invalid mode. Must be 'absolute' or 'change'.",
        )
    # Normalise: 'all' → uses seasonal table without season filter
    svc_season = season if season != "all" else "all"
    total = layer_svc.count_ocean_covariates(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=svc_season,
        scenario=scenario,
        decade=decade,
    )
    rows = layer_svc.get_ocean_covariates(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=svc_season,
        scenario=scenario,
        decade=decade,
        mode=mode,
        limit=limit,
        offset=offset,
    )
    data = [OceanCovariateCell(**r) for r in rows]
    return OceanCovariateListResponse(
        total=total, offset=offset, limit=limit, data=data
    )


# ── Whale predictions (ISDM) ───────────────────────────────


@router.get(
    "/whale-predictions",
    response_model=WhalePredictionListResponse,
)
def list_whale_predictions(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    season: str | None = Query(None),
    species: str | None = Query(
        None,
        description=(
            "ISDM species to filter by probability "
            "(blue_whale, fin_whale, humpback_whale, "
            "sperm_whale)"
        ),
    ),
    min_probability: float | None = Query(
        None,
        ge=0,
        le=1,
        description="Minimum probability threshold",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """ISDM whale predictions — per-species and aggregate probs.

    Filter by season, species, and/or minimum probability.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season. Must be one of: {sorted(_VALID_SEASONS)}",
        )
    if species and species not in _VALID_ISDM_SPECIES:
        raise HTTPException(
            400,
            f"Invalid species. Must be one of: {sorted(_VALID_ISDM_SPECIES)}",
        )
    total = layer_svc.count_whale_predictions(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        species=species,
        min_probability=min_probability,
    )
    rows = layer_svc.get_whale_predictions(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        species=species,
        min_probability=min_probability,
        limit=limit,
        offset=offset,
    )
    data = [WhalePredictionCell(**r) for r in rows]
    return WhalePredictionListResponse(
        total=total, offset=offset, limit=limit, data=data
    )


# ── SDM whale predictions (OBIS-trained) ───────────────────


@router.get(
    "/sdm-predictions",
    response_model=SdmPredictionListResponse,
)
def list_sdm_predictions(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    season: str | None = Query(None),
    species: str | None = Query(
        None,
        description=(
            "SDM species to filter by probability "
            "(blue_whale, fin_whale, humpback_whale, "
            "sperm_whale)"
        ),
    ),
    min_probability: float | None = Query(
        None,
        ge=0,
        le=1,
        description="Minimum probability threshold",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """SDM (OBIS-trained) whale predictions — OOF spatial CV.

    Comparable to ISDM predictions but trained on OBIS
    opportunistic sighting data instead of expert-curated
    Nisi et al. presence/absence.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season. Must be one of: {sorted(_VALID_SEASONS)}",
        )
    if species and species not in _VALID_SDM_SPECIES:
        raise HTTPException(
            400,
            f"Invalid species. Must be one of: {sorted(_VALID_SDM_SPECIES)}",
        )
    total = layer_svc.count_sdm_predictions(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        species=species,
        min_probability=min_probability,
    )
    rows = layer_svc.get_sdm_predictions(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        species=species,
        min_probability=min_probability,
        limit=limit,
        offset=offset,
    )
    data = [SdmPredictionCell(**r) for r in rows]
    return SdmPredictionListResponse(total=total, offset=offset, limit=limit, data=data)


# ── MPA coverage ────────────────────────────────────────────


@router.get("/mpa", response_model=MPAListResponse)
def list_mpa_coverage(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Marine Protected Area coverage — count, names, protection level."""
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    total = layer_svc.count_mpa_coverage(lat_min, lat_max, lon_min, lon_max)
    rows = layer_svc.get_mpa_coverage(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        limit=limit,
        offset=offset,
    )
    data = [MPACell(**r) for r in rows]
    return MPAListResponse(total=total, offset=offset, limit=limit, data=data)


# ── Speed zones ─────────────────────────────────────────────


@router.get("/speed-zones", response_model=SpeedZoneListResponse)
def list_speed_zones(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    season: str | None = Query(
        None,
        description="Filter by season for seasonal zone activity",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Speed zone coverage — SMA + proposed zones.

    Without season: static zone coverage.
    With season: seasonal variant showing active zones per season.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season. Must be one of: {sorted(_VALID_SEASONS)}",
        )
    total = layer_svc.count_speed_zones(
        lat_min, lat_max, lon_min, lon_max, season=season
    )
    rows = layer_svc.get_speed_zones(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        limit=limit,
        offset=offset,
    )
    data = [SpeedZoneCell(**r) for r in rows]
    return SpeedZoneListResponse(total=total, offset=offset, limit=limit, data=data)


# ── Proximity ───────────────────────────────────────────────


@router.get("/proximity", response_model=ProximityListResponse)
def list_proximity(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Proximity distances and exponential decay scores.

    4 distance features (whale, ship, strike, protection) and
    4 corresponding decay scores.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    total = layer_svc.count_proximity(lat_min, lat_max, lon_min, lon_max)
    rows = layer_svc.get_proximity(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        limit=limit,
        offset=offset,
    )
    data = [ProximityCell(**r) for r in rows]
    return ProximityListResponse(total=total, offset=offset, limit=limit, data=data)


# ── Nisi reference risk ─────────────────────────────────────


@router.get("/nisi-risk", response_model=NisiRiskListResponse)
def list_nisi_risk(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Nisi et al. 2024 reference risk — shipping, whale use, per-species."""
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    total = layer_svc.count_nisi_risk(lat_min, lat_max, lon_min, lon_max)
    rows = layer_svc.get_nisi_risk(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        limit=limit,
        offset=offset,
    )
    data = [NisiRiskCell(**r) for r in rows]
    return NisiRiskListResponse(total=total, offset=offset, limit=limit, data=data)


# ── Cetacean density ────────────────────────────────────────


@router.get(
    "/cetacean-density",
    response_model=CetaceanDensityListResponse,
)
def list_cetacean_density(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    min_sightings: int | None = Query(
        None,
        ge=1,
        description="Minimum total_sightings filter",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Cetacean sighting density — total, per-species, baleen, recent.

    Uses the static int_cetacean_density table.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    total = layer_svc.count_cetacean_density(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        min_sightings=min_sightings,
    )
    rows = layer_svc.get_cetacean_density(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        min_sightings=min_sightings,
        limit=limit,
        offset=offset,
    )
    data = [CetaceanDensityCell(**r) for r in rows]
    return CetaceanDensityListResponse(
        total=total, offset=offset, limit=limit, data=data
    )


# ── Ship strike density ─────────────────────────────────────


@router.get(
    "/strike-density",
    response_model=StrikeDensityListResponse,
)
def list_strike_density(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Ship strike density — only ~67 cells with non-zero strikes.

    Includes total, fatal, serious injury, baleen strikes, and
    species list per cell.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    total = layer_svc.count_strike_density(lat_min, lat_max, lon_min, lon_max)
    rows = layer_svc.get_strike_density(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        limit=limit,
        offset=offset,
    )
    data = [StrikeDensityCell(**r) for r in rows]
    return StrikeDensityListResponse(total=total, offset=offset, limit=limit, data=data)


# ── Traffic density ──────────────────────────────────────────


@router.get(
    "/traffic-density",
    response_model=TrafficDensityListResponse,
)
def list_traffic_density(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    season: str | None = Query(
        None,
        description="Filter by season",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Vessel traffic density and danger metrics per H3 cell.

    Exposes the 8 traffic sub-score components: speed lethality
    (V&T 2007), high-speed fraction, vessel volume, large vessels,
    draft risk, commercial traffic, night operations, plus
    supporting metrics (COG diversity, vessel length, draft).
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season: {season}. Valid: {sorted(_VALID_SEASONS)}",
        )
    total = layer_svc.count_traffic_density(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
    )
    rows = layer_svc.get_traffic_density(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        limit=limit,
        offset=offset,
    )
    data = [TrafficDensityCell(**r) for r in rows]
    return TrafficDensityListResponse(
        total=total,
        offset=offset,
        limit=limit,
        data=data,
    )


# ── SDM projections (CMIP6 climate) ─────────────────────────


@router.get(
    "/sdm-projections",
    response_model=SdmProjectionListResponse,
)
def list_sdm_projections(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    scenario: str = Query(
        ...,
        description="Climate scenario: ssp245 or ssp585",
    ),
    decade: str = Query(
        ...,
        description="Projection decade: 2030s, 2040s, 2060s, or 2080s",
    ),
    mode: str = Query(
        "absolute",
        description=(
            "Display mode: absolute (raw probabilities) or "
            "change (delta vs current baseline)"
        ),
    ),
    season: str | None = Query(None),
    species: str | None = Query(
        None,
        description=(
            "Filter by species probability "
            "(blue_whale, fin_whale, humpback_whale, "
            "sperm_whale)"
        ),
    ),
    min_probability: float | None = Query(
        None,
        ge=0,
        le=1,
        description="Minimum probability threshold",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Projected whale habitat under CMIP6 climate scenarios.

    Returns SDM-predicted whale habitat probabilities for future
    decades under SSP2-4.5 (moderate) or SSP5-8.5 (high emissions).

    Set **mode=change** to include delta columns comparing each
    projected probability against the current-climate baseline.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    if scenario not in _VALID_SCENARIOS:
        raise HTTPException(
            400,
            f"Invalid scenario. Must be one of: {sorted(_VALID_SCENARIOS)}",
        )
    if decade not in _VALID_DECADES:
        raise HTTPException(
            400,
            f"Invalid decade. Must be one of: {sorted(_VALID_DECADES)}",
        )
    if mode not in ("absolute", "change"):
        raise HTTPException(
            400,
            "Invalid mode. Must be 'absolute' or 'change'.",
        )
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season. Must be one of: {sorted(_VALID_SEASONS)}",
        )
    if species and species not in _VALID_SDM_SPECIES:
        raise HTTPException(
            400,
            f"Invalid species. Must be one of: {sorted(_VALID_SDM_SPECIES)}",
        )

    total = layer_svc.count_sdm_projections(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        scenario=scenario,
        decade=decade,
        season=season,
        species=species,
        min_probability=min_probability,
    )
    rows = layer_svc.get_sdm_projections(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        scenario=scenario,
        decade=decade,
        season=season,
        species=species,
        min_probability=min_probability,
        limit=limit,
        offset=offset,
        mode=mode,
    )
    data = [SdmProjectionCell(**r) for r in rows]
    return SdmProjectionListResponse(
        total=total,
        offset=offset,
        limit=limit,
        data=data,
    )


@router.get(
    "/sdm-projections/summary",
    response_model=ProjectionSummaryResponse,
)
def projection_summary(
    lat_min: float | None = Query(None, ge=-90, le=90),
    lat_max: float | None = Query(None, ge=-90, le=90),
    lon_min: float | None = Query(None, ge=-180, le=180),
    lon_max: float | None = Query(None, ge=-180, le=180),
    species: str | None = Query(
        None,
        description="Species to summarise (default: any_whale)",
    ),
):
    """Habitat change summary across all scenarios and decades.

    Returns mean probability, median, and high-probability cell
    counts for each (scenario, decade, season) combination.
    Useful for time-series charts showing projected habitat shifts.
    Bbox is optional — omit for coast-wide summary.
    """
    has_bbox = all(v is not None for v in (lat_min, lat_max, lon_min, lon_max))
    if has_bbox:
        _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    if species and species not in _VALID_SDM_SPECIES:
        raise HTTPException(
            400,
            f"Invalid species. Must be one of: {sorted(_VALID_SDM_SPECIES)}",
        )
    rows = layer_svc.get_projection_summary(
        lat_min if has_bbox else None,
        lat_max if has_bbox else None,
        lon_min if has_bbox else None,
        lon_max if has_bbox else None,
        species=species,
    )
    data = [ProjectionSummaryRow(**r) for r in rows]
    return ProjectionSummaryResponse(data=data)


# ── ISDM projections (CMIP6 climate) ───────────────────────


@router.get(
    "/isdm-projections",
    response_model=IsdmProjectionListResponse,
)
def list_isdm_projections(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    scenario: str = Query(
        ...,
        description="Climate scenario: ssp245 or ssp585",
    ),
    decade: str = Query(
        ...,
        description=("Projection decade: 2030s, 2040s, 2060s, or 2080s"),
    ),
    mode: str = Query(
        "absolute",
        description=(
            "Display mode: absolute (raw probabilities) or "
            "change (delta vs current baseline)"
        ),
    ),
    season: str | None = Query(None),
    species: str | None = Query(
        None,
        description=(
            "Filter by species probability "
            "(blue_whale, fin_whale, humpback_whale, "
            "sperm_whale)"
        ),
    ),
    min_probability: float | None = Query(
        None,
        ge=0,
        le=1,
        description="Minimum probability threshold",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Projected ISDM whale habitat under CMIP6 scenarios.

    ISDM models (Nisi et al. 2024) trained on expert-curated
    presence/absence data.  Available for 4 species: blue, fin,
    humpback, and sperm whale.

    Set **mode=change** to include delta columns comparing each
    projected probability against the current-climate baseline.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    if scenario not in _VALID_SCENARIOS:
        raise HTTPException(
            400,
            f"Invalid scenario. Must be one of: {sorted(_VALID_SCENARIOS)}",
        )
    if decade not in _VALID_DECADES:
        raise HTTPException(
            400,
            f"Invalid decade. Must be one of: {sorted(_VALID_DECADES)}",
        )
    if mode not in ("absolute", "change"):
        raise HTTPException(
            400,
            "Invalid mode. Must be 'absolute' or 'change'.",
        )
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season. Must be one of: {sorted(_VALID_SEASONS)}",
        )
    if species and species not in _VALID_ISDM_SPECIES:
        raise HTTPException(
            400,
            f"Invalid species. Must be one of: {sorted(_VALID_ISDM_SPECIES)}",
        )

    total = layer_svc.count_isdm_projections(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        scenario=scenario,
        decade=decade,
        season=season,
        species=species,
        min_probability=min_probability,
    )
    rows = layer_svc.get_isdm_projections(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        scenario=scenario,
        decade=decade,
        season=season,
        species=species,
        min_probability=min_probability,
        limit=limit,
        offset=offset,
        mode=mode,
    )
    data = [IsdmProjectionCell(**r) for r in rows]
    return IsdmProjectionListResponse(
        total=total,
        offset=offset,
        limit=limit,
        data=data,
    )


# ── Cell context (species + habitat for any cell) ──────────


@router.get("/context/{h3_cell}")
def cell_context(
    h3_cell: int,
    season: str | None = Query(None),
):
    """Species predictions and habitat designations for a cell.

    Returns ISDM whale predictions, observed cetacean species,
    Biologically Important Areas (BIAs), and ESA Critical Habitat
    designations that overlap this cell.
    """
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season: {season}. Valid: {sorted(_VALID_SEASONS)}",
        )
    return layer_svc.get_cell_context(h3_cell, season=season)

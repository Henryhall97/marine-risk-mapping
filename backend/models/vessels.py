"""Pydantic schemas for user vessel (boat) profiles."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

# ── Vessel type enum values ──────────────────────────────────
# These match the frontend dropdown options.
VESSEL_TYPES = [
    "sailing_yacht",
    "motorboat",
    "kayak_canoe",
    "research_vessel",
    "whale_watch_boat",
    "fishing_vessel",
    "cargo_ship",
    "tanker",
    "ferry_passenger",
    "tug_workboat",
    "coast_guard",
    "other",
]

HULL_MATERIALS = [
    "fiberglass",
    "aluminum",
    "steel",
    "wood",
    "carbon_composite",
    "inflatable",
    "other",
]

PROPULSION_TYPES = [
    "sail",
    "outboard",
    "inboard_diesel",
    "inboard_gas",
    "electric",
    "paddle",
    "jet",
    "other",
]


class VesselCreate(BaseModel):
    """Request body for creating / updating a vessel profile."""

    vessel_name: str = Field(
        ..., min_length=1, max_length=200, description="Vessel name"
    )
    vessel_type: str = Field(
        ..., description="Vessel type (e.g. sailing_yacht, motorboat)"
    )
    description: str | None = Field(
        None, max_length=2000, description="Boat description / bio"
    )
    length_m: float | None = Field(
        None, ge=0.5, le=500, description="Length overall in metres"
    )
    beam_m: float | None = Field(
        None, ge=0.3, le=100, description="Beam (width) in metres"
    )
    draft_m: float | None = Field(None, ge=0, le=30, description="Draft in metres")
    hull_material: str | None = Field(None, description="Hull material")
    propulsion: str | None = Field(None, description="Propulsion type")
    typical_speed_knots: float | None = Field(
        None, ge=0, le=60, description="Typical cruising speed in knots"
    )
    home_port: str | None = Field(None, max_length=200, description="Home port name")
    flag_state: str | None = Field(
        None, max_length=100, description="Flag state / country"
    )
    registration_number: str | None = Field(
        None, max_length=100, description="Registration / documentation number"
    )
    mmsi: int | None = Field(None, description="Maritime Mobile Service Identity")
    imo: str | None = Field(None, max_length=20, description="IMO number")
    call_sign: str | None = Field(None, max_length=20, description="Radio call sign")


class VesselResponse(BaseModel):
    """Full vessel profile returned from the API."""

    id: int
    user_id: int
    vessel_name: str
    vessel_type: str
    description: str | None = None
    length_m: float | None = None
    beam_m: float | None = None
    draft_m: float | None = None
    hull_material: str | None = None
    propulsion: str | None = None
    typical_speed_knots: float | None = None
    home_port: str | None = None
    flag_state: str | None = None
    registration_number: str | None = None
    mmsi: int | None = None
    imo: str | None = None
    call_sign: str | None = None
    is_active: bool = False
    profile_photo_url: str | None = None
    cover_photo_url: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_photos(cls, data: dict) -> dict:  # type: ignore[override]
        if isinstance(data, dict):
            vid = data.get("id")
            if data.pop("profile_photo_filename", None) and vid:
                data["profile_photo_url"] = f"/api/v1/vessels/{vid}/photo"
            if data.pop("cover_photo_filename", None) and vid:
                data["cover_photo_url"] = f"/api/v1/vessels/{vid}/cover"
        return data


class VesselListResponse(BaseModel):
    """List of user vessels."""

    vessels: list[VesselResponse]
    active_vessel_id: int | None = None


class VesselSummary(BaseModel):
    """Minimal vessel info embedded in sighting responses."""

    id: int
    vessel_name: str
    vessel_type: str
    length_m: float | None = None


# ── Crew ─────────────────────────────────────────────────────

CREW_ROLES = ["owner", "crew", "guest"]


class CrewMember(BaseModel):
    """A crew member on a vessel."""

    id: int
    user_id: int
    role: str
    joined_at: datetime
    display_name: str | None = None
    reputation_tier: str | None = None
    avatar_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_avatar(cls, data: dict) -> dict:  # type: ignore[override]
        if isinstance(data, dict):
            avatar = data.pop("avatar_filename", None)
            uid = data.get("user_id")
            if avatar and uid:
                data["avatar_url"] = f"/api/v1/media/avatar/{uid}"
        return data


class CrewAddRequest(BaseModel):
    """Request to add a crew member to a vessel."""

    user_id: int = Field(..., description="User to add as crew")
    role: str = Field(default="crew", description="Role: crew or guest")


class CrewListResponse(BaseModel):
    """List of crew members on a vessel."""

    crew: list[CrewMember]
    vessel_id: int


# ── Public boat profile ──────────────────────────────────────


class VesselStats(BaseModel):
    """Stats for a vessel's public profile page."""

    total_sightings: int = 0
    species_documented: int = 0
    verified_sightings: int = 0
    first_sighting: datetime | None = None
    last_sighting: datetime | None = None


class VesselPublicProfile(VesselResponse):
    """Public vessel profile with stats and crew."""

    stats: VesselStats = Field(default_factory=VesselStats)
    crew: list[CrewMember] = Field(default_factory=list)
    owner_name: str | None = None
    owner_id: int | None = None
    owner_avatar_url: str | None = None


# ── Boat leaderboard ─────────────────────────────────────────


class BoatLeaderboardItem(BaseModel):
    """A boat entry in the community leaderboard."""

    vessel_id: int
    vessel_name: str
    vessel_type: str
    profile_photo_url: str | None = None
    owner_name: str | None = None
    owner_id: int | None = None
    crew_count: int = 0
    submission_count: int = 0
    species_count: int = 0

    @model_validator(mode="before")
    @classmethod
    def _resolve_photo(cls, data: dict) -> dict:  # type: ignore[override]
        if isinstance(data, dict):
            vid = data.get("vessel_id")
            if data.pop("profile_photo_filename", None) and vid:
                data["profile_photo_url"] = f"/api/v1/vessels/{vid}/photo"
        return data


class BoatLeaderboardResponse(BaseModel):
    """Boat leaderboard for the community page."""

    boats: list[BoatLeaderboardItem]

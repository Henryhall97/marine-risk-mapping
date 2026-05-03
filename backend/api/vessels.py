"""Vessel profile API routes — CRUD for user boats.

Authenticated users can register multiple vessels (sailing yachts,
motorboats, kayaks, research vessels, etc.). The active vessel is
automatically linked to new sighting reports so that observation
platform metadata flows into every submission without re-entering it.

Boats support multi-user crews, profile/cover photos, public profile
pages with stats, and a community leaderboard.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse

from backend.config import PROJECT_ROOT
from backend.models.vessels import (
    BoatLeaderboardItem,
    BoatLeaderboardResponse,
    CrewAddRequest,
    CrewListResponse,
    CrewMember,
    VesselCreate,
    VesselListResponse,
    VesselPublicProfile,
    VesselResponse,
    VesselStats,
)
from backend.services import auth as auth_svc
from backend.services import vessels as vessel_svc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vessels", tags=["vessels"])

_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_PHOTO_MB = 10
_VESSEL_PHOTO_ROOT = PROJECT_ROOT / "data/uploads/vessel_photos"

_PHOTO_MEDIA_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _require_user(authorization: str | None) -> int:
    """Extract user ID from Authorization header or raise 401."""
    uid = auth_svc.get_current_user_id(authorization)
    if uid is None:
        raise HTTPException(401, "Authentication required")
    return uid


# ── Boat leaderboard (public, must be before /{vessel_id}) ───


@router.get("/leaderboard", response_model=BoatLeaderboardResponse)
def boat_leaderboard(
    limit: int = Query(default=10, ge=1, le=50),
) -> BoatLeaderboardResponse:
    """Top boats ranked by public submission count."""
    rows = vessel_svc.get_boat_leaderboard(limit)
    return BoatLeaderboardResponse(
        boats=[BoatLeaderboardItem(**r) for r in rows],
    )


# ── CRUD (auth required) ─────────────────────────────────────


@router.get("", response_model=VesselListResponse)
def list_my_vessels(
    authorization: str | None = Header(default=None),
) -> VesselListResponse:
    """List all vessels for the authenticated user."""
    uid = _require_user(authorization)
    vessels = vessel_svc.list_vessels(uid)
    active_id = next((v["id"] for v in vessels if v.get("is_active")), None)
    return VesselListResponse(
        vessels=[VesselResponse(**v) for v in vessels],
        active_vessel_id=active_id,
    )


@router.post("", response_model=VesselResponse, status_code=201)
def create_vessel(
    body: VesselCreate,
    authorization: str | None = Header(default=None),
) -> VesselResponse:
    """Register a new vessel profile."""
    uid = _require_user(authorization)
    vessel = vessel_svc.create_vessel(uid, body.model_dump())
    return VesselResponse(**vessel)


@router.get("/{vessel_id}", response_model=VesselResponse)
def get_vessel(
    vessel_id: int,
    authorization: str | None = Header(default=None),
) -> VesselResponse:
    """Get a vessel by ID (must be owned by the authenticated user)."""
    uid = _require_user(authorization)
    vessel = vessel_svc.get_vessel(vessel_id)
    if not vessel or vessel["user_id"] != uid:
        raise HTTPException(404, "Vessel not found")
    return VesselResponse(**vessel)


@router.put("/{vessel_id}", response_model=VesselResponse)
def update_vessel(
    vessel_id: int,
    body: VesselCreate,
    authorization: str | None = Header(default=None),
) -> VesselResponse:
    """Update a vessel profile."""
    uid = _require_user(authorization)
    updated = vessel_svc.update_vessel(vessel_id, uid, body.model_dump())
    if not updated:
        raise HTTPException(404, "Vessel not found")
    return VesselResponse(**updated)


@router.delete("/{vessel_id}", status_code=204)
def delete_vessel(
    vessel_id: int,
    authorization: str | None = Header(default=None),
) -> None:
    """Delete a vessel profile."""
    uid = _require_user(authorization)
    if not vessel_svc.delete_vessel(vessel_id, uid):
        raise HTTPException(404, "Vessel not found")


@router.post(
    "/{vessel_id}/activate",
    response_model=VesselResponse,
)
def activate_vessel(
    vessel_id: int,
    authorization: str | None = Header(default=None),
) -> VesselResponse:
    """Set a vessel as the active vessel for new sighting reports."""
    uid = _require_user(authorization)
    vessel = vessel_svc.set_active_vessel(vessel_id, uid)
    if not vessel:
        raise HTTPException(404, "Vessel not found")
    return VesselResponse(**vessel)


@router.post("/deactivate", status_code=204)
def deactivate_all(
    authorization: str | None = Header(default=None),
) -> None:
    """Clear the active vessel (e.g. reporting from shore)."""
    uid = _require_user(authorization)
    vessel_svc.clear_active_vessel(uid)


# ── Public vessel profile ────────────────────────────────────


@router.get(
    "/{vessel_id}/public",
    response_model=VesselPublicProfile,
)
def get_vessel_public(vessel_id: int) -> VesselPublicProfile:
    """Public vessel profile with stats and crew list."""
    profile = vessel_svc.get_vessel_public_profile(vessel_id)
    if not profile:
        raise HTTPException(404, "Vessel not found")
    stats = profile.pop("stats", {})
    crew = profile.pop("crew", [])
    return VesselPublicProfile(
        **profile,
        stats=VesselStats(**stats),
        crew=[CrewMember(**c) for c in crew],
    )


# ── Crew management ──────────────────────────────────────────


@router.get(
    "/{vessel_id}/crew",
    response_model=CrewListResponse,
)
def list_crew(vessel_id: int) -> CrewListResponse:
    """List all crew members on a vessel (public)."""
    vessel = vessel_svc.get_vessel(vessel_id)
    if not vessel:
        raise HTTPException(404, "Vessel not found")
    rows = vessel_svc.list_crew(vessel_id)
    return CrewListResponse(
        crew=[CrewMember(**r) for r in rows],
        vessel_id=vessel_id,
    )


@router.post(
    "/{vessel_id}/crew",
    response_model=CrewMember,
    status_code=201,
)
def add_crew_member(
    vessel_id: int,
    body: CrewAddRequest,
    authorization: str | None = Header(default=None),
) -> CrewMember:
    """Add a crew member to a vessel. Owner only."""
    uid = _require_user(authorization)
    if not vessel_svc.is_vessel_owner(vessel_id, uid):
        raise HTTPException(403, "Only the boat owner can add crew")
    member = vessel_svc.add_crew(vessel_id, body.user_id, body.role, invited_by=uid)
    if not member:
        raise HTTPException(409, "User is already a crew member or invalid role")
    return CrewMember(**member)


@router.delete(
    "/{vessel_id}/crew/{user_id}",
    status_code=204,
)
def remove_crew_member(
    vessel_id: int,
    user_id: int,
    authorization: str | None = Header(default=None),
) -> None:
    """Remove a crew member. Owner can remove anyone; members can
    self-remove. Cannot remove the owner."""
    uid = _require_user(authorization)
    if not vessel_svc.remove_crew(vessel_id, user_id, uid):
        raise HTTPException(
            403,
            "Not authorised or cannot remove the owner",
        )


@router.patch(
    "/{vessel_id}/crew/{user_id}/role",
    response_model=CrewMember,
)
def update_crew_role(
    vessel_id: int,
    user_id: int,
    role: str = Query(..., description="New role: crew or guest"),
    authorization: str | None = Header(default=None),
) -> CrewMember:
    """Change a crew member's role. Owner only."""
    uid = _require_user(authorization)
    if not vessel_svc.is_vessel_owner(vessel_id, uid):
        raise HTTPException(403, "Only the boat owner can change roles")
    updated = vessel_svc.update_crew_role(vessel_id, user_id, role)
    if not updated:
        raise HTTPException(404, "Crew member not found or cannot change owner")
    return CrewMember(**updated)


# ── Vessel photos ────────────────────────────────────────────


@router.post("/{vessel_id}/photo", status_code=201)
async def upload_vessel_profile_photo(
    vessel_id: int,
    image: UploadFile = File(  # noqa: B008
        ...,
        description="Profile photo (JPEG/PNG/WebP, max 10 MB)",
    ),
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    """Upload a profile photo for a vessel. Owner only."""
    uid = _require_user(authorization)
    if not vessel_svc.is_vessel_owner(vessel_id, uid):
        raise HTTPException(403, "Only the boat owner can upload photos")
    ext = Path(image.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported format {ext}. "
            f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )
    data = await image.read()
    if len(data) > _MAX_PHOTO_MB * 1024 * 1024:
        raise HTTPException(400, f"Photo exceeds {_MAX_PHOTO_MB} MB limit")
    stored = vessel_svc.upload_vessel_photo(
        vessel_id, "profile", data, image.filename or "profile.jpg"
    )
    if not stored:
        raise HTTPException(404, "Vessel not found")
    return {"status": "uploaded", "filename": stored}


@router.post("/{vessel_id}/cover", status_code=201)
async def upload_vessel_cover_photo(
    vessel_id: int,
    image: UploadFile = File(  # noqa: B008
        ...,
        description="Cover photo (JPEG/PNG/WebP, max 10 MB)",
    ),
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    """Upload a cover photo for a vessel. Owner only."""
    uid = _require_user(authorization)
    if not vessel_svc.is_vessel_owner(vessel_id, uid):
        raise HTTPException(403, "Only the boat owner can upload photos")
    ext = Path(image.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported format {ext}. "
            f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )
    data = await image.read()
    if len(data) > _MAX_PHOTO_MB * 1024 * 1024:
        raise HTTPException(400, f"Cover exceeds {_MAX_PHOTO_MB} MB limit")
    stored = vessel_svc.upload_vessel_photo(
        vessel_id, "cover", data, image.filename or "cover.jpg"
    )
    if not stored:
        raise HTTPException(404, "Vessel not found")
    return {"status": "uploaded", "filename": stored}


@router.get("/{vessel_id}/photo")
def serve_vessel_profile_photo(vessel_id: int) -> FileResponse:
    """Serve a vessel's profile photo."""
    folder = _VESSEL_PHOTO_ROOT / str(vessel_id)
    if folder.exists():
        for f in folder.glob("profile.*"):
            mt = _PHOTO_MEDIA_TYPES.get(f.suffix.lower(), "image/jpeg")
            return FileResponse(
                f,
                media_type=mt,
                headers={"Cache-Control": "public, max-age=3600"},
            )
    raise HTTPException(404, "No profile photo")


@router.get("/{vessel_id}/cover")
def serve_vessel_cover_photo(vessel_id: int) -> FileResponse:
    """Serve a vessel's cover photo."""
    folder = _VESSEL_PHOTO_ROOT / str(vessel_id)
    if folder.exists():
        for f in folder.glob("cover.*"):
            mt = _PHOTO_MEDIA_TYPES.get(f.suffix.lower(), "image/jpeg")
            return FileResponse(
                f,
                media_type=mt,
                headers={"Cache-Control": "public, max-age=3600"},
            )
    raise HTTPException(404, "No cover photo")

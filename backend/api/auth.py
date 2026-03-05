"""Authentication API routes — register, login, profile, avatar."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile

from backend.models.auth import (
    CredentialInfo,
    PublicProfile,
    SpeciesCount,
    TokenResponse,
    UserLogin,
    UserProfile,
    UserRegister,
)
from backend.services import auth as auth_svc
from backend.services import reputation as rep_svc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_AVATAR_ROOT = Path("data/uploads/avatars")
_ALLOWED_AVATAR_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: UserRegister) -> TokenResponse:
    """Register a new user account."""
    try:
        user = auth_svc.register_user(body.email, body.display_name, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    token = auth_svc.create_token(user["id"], user["email"])
    return TokenResponse(
        access_token=token,
        user=UserProfile(**user),
    )


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin) -> TokenResponse:
    """Authenticate and receive a JWT token."""
    user = auth_svc.authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = auth_svc.create_token(user["id"], user["email"])
    return TokenResponse(
        access_token=token,
        user=UserProfile(**user),
    )


@router.get("/me", response_model=UserProfile)
def get_me(
    authorization: str | None = Header(default=None),
) -> UserProfile:
    """Get the current user's profile."""
    user_id = auth_svc.get_current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = auth_svc.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserProfile(**user)


# ── Public profile ───────────────────────────────────────────


@router.get("/users/{user_id}", response_model=PublicProfile)
def get_public_profile(user_id: int) -> PublicProfile:
    """Get a public user profile by ID (no email)."""
    profile = auth_svc.get_public_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    return PublicProfile(
        id=profile["id"],
        display_name=profile["display_name"],
        avatar_url=profile.get("avatar_url"),
        created_at=profile["created_at"],
        submission_count=profile["submission_count"],
        verified_count=profile["verified_count"],
        reputation_score=profile["reputation_score"],
        reputation_tier=profile["reputation_tier"],
        credentials=[CredentialInfo(**c) for c in profile.get("credentials", [])],
        species_breakdown=[
            SpeciesCount(**s) for s in profile.get("species_breakdown", [])
        ],
    )


# ── Reputation history ───────────────────────────────────────


@router.get("/reputation/history")
def get_reputation_history(
    authorization: str | None = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Get the current user's reputation event history."""
    user_id = auth_svc.get_current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    events, total = rep_svc.get_reputation_history(user_id, limit, offset)
    return {"events": events, "total": total, "limit": limit, "offset": offset}


# ── Credentials ──────────────────────────────────────────────


@router.post("/credentials", response_model=CredentialInfo, status_code=201)
def add_credential(
    credential_type: str = Query(
        ...,
        description=(
            "Type: marine_biologist, certified_observer, "
            "noaa_affiliate, research_institution, "
            "vessel_operator, coast_guard, other"
        ),
    ),
    description: str = Query(
        ..., max_length=500, description="Details about the credential"
    ),
    authorization: str | None = Header(default=None),
) -> CredentialInfo:
    """Add a credential claim to your profile."""
    user_id = auth_svc.get_current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        cred = rep_svc.add_credential(user_id, credential_type, description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CredentialInfo(**cred)


# ── Avatar upload ────────────────────────────────────────────


@router.post("/avatar", response_model=UserProfile)
def upload_avatar(
    image: UploadFile = File(...),  # noqa: B008
    authorization: str | None = Header(default=None),
) -> UserProfile:
    """Upload or replace a user avatar (max 5 MB, JPG/PNG/WebP)."""
    user_id = auth_svc.get_current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Validate extension — try filename first, fall back to content-type
    ext = Path(image.filename or "").suffix.lower()
    if ext not in _ALLOWED_AVATAR_EXT:
        # Fall back to content-type header
        ext = _CONTENT_TYPE_TO_EXT.get(image.content_type or "", "")
    if ext not in _ALLOWED_AVATAR_EXT:
        log.warning(
            "Avatar rejected: filename=%r content_type=%r ext=%r",
            image.filename,
            image.content_type,
            ext,
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported image type '{ext or image.content_type}'. "
                "Use JPG, PNG, or WebP."
            ),
        )

    # Read + validate size
    data = image.file.read()
    if len(data) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Avatar must be under 5 MB",
        )

    # Store file
    folder = _AVATAR_ROOT / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)

    # Remove any previous avatar files
    for old in folder.iterdir():
        if old.stem == "avatar":
            old.unlink(missing_ok=True)

    filename = f"avatar{ext}"
    dest = folder / filename
    dest.write_bytes(data)

    # Update DB
    auth_svc.update_avatar(user_id, filename)

    # Return refreshed profile
    user = auth_svc.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(**user)


@router.delete("/avatar", status_code=204)
def delete_avatar(
    authorization: str | None = Header(default=None),
) -> None:
    """Remove the current user's avatar."""
    user_id = auth_svc.get_current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Remove files from disk
    folder = _AVATAR_ROOT / str(user_id)
    if folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)

    # Clear DB
    auth_svc.update_avatar(user_id, None)

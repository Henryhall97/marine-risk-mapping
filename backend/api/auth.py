"""Authentication API routes — register, login, profile, avatar."""

from __future__ import annotations

import contextlib
import logging
import shutil
from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import PROJECT_ROOT
from backend.models.auth import (
    CredentialInfo,
    PublicProfile,
    SpeciesCount,
    TokenResponse,
    UserLogin,
    UserProfile,
    UserRegister,
    UserSearchResult,
)
from backend.services import auth as auth_svc
from backend.services import reputation as rep_svc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

_AVATAR_ROOT = PROJECT_ROOT / "data/uploads/avatars"
_ALLOWED_AVATAR_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, body: UserRegister) -> TokenResponse:
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
@limiter.limit("10/minute")
def login(request: Request, body: UserLogin) -> TokenResponse:
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


# ── User search ──────────────────────────────────────────────


@router.get("/users/search", response_model=list[UserSearchResult])
def search_users(
    q: str = Query(..., min_length=1, max_length=100, description="Name search"),
    limit: int = Query(default=10, ge=1, le=50),
    exclude: str | None = Query(
        default=None,
        description="Comma-separated user IDs to exclude",
    ),
    authorization: str | None = Header(default=None),
) -> list[UserSearchResult]:
    """Search platform users by display name (for crew invites etc.).

    Requires authentication so anonymous users can't enumerate accounts.
    """
    uid = auth_svc.get_current_user_id(authorization)
    if uid is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    exclude_ids: list[int] = []
    if exclude:
        with contextlib.suppress(ValueError):
            exclude_ids = [int(x.strip()) for x in exclude.split(",") if x.strip()]

    rows = auth_svc.search_users(q, limit=limit, exclude_ids=exclude_ids or None)
    return [UserSearchResult(**r) for r in rows]


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
        bio=profile.get("bio"),
        avatar_url=profile.get("avatar_url"),
        created_at=profile["created_at"],
        submission_count=profile["submission_count"],
        verified_count=profile["verified_count"],
        reputation_score=profile["reputation_score"],
        reputation_tier=profile["reputation_tier"],
        is_moderator=profile.get("is_moderator", False),
        credentials=[CredentialInfo(**c) for c in profile.get("credentials", [])],
        species_breakdown=[
            SpeciesCount(**s) for s in profile.get("species_breakdown", [])
        ],
    )


# ── Update bio ───────────────────────────────────────────────


@router.patch("/bio", response_model=UserProfile)
def update_bio(
    bio: str = Query(..., max_length=500, description="Profile bio/summary"),
    authorization: str | None = Header(default=None),
) -> UserProfile:
    """Update the current user's profile bio."""
    user_id = auth_svc.get_current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    clean = bio.strip() or None
    auth_svc.update_bio(user_id, clean)

    user = auth_svc.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(**user)


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


_EVIDENCE_ROOT = PROJECT_ROOT / "data/uploads/credentials"
_ALLOWED_EVIDENCE_EXT = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
}
_MAX_EVIDENCE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/credentials", response_model=CredentialInfo, status_code=201)
def add_credential(
    credential_type: str = Form(
        ...,
        description=(
            "Type: marine_biologist, certified_observer, "
            "noaa_affiliate, research_institution, "
            "vessel_operator, coast_guard, other"
        ),
    ),
    description: str = Form(
        ..., max_length=500, description="Details about the credential"
    ),
    evidence: UploadFile | None = File(  # noqa: B008
        default=None,
        description=("Optional evidence file (image, PDF, or document, max 10 MB)"),
    ),
    authorization: str | None = Header(default=None),
) -> CredentialInfo:
    """Add a credential claim with optional evidence file."""
    user_id = auth_svc.get_current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    evidence_filename: str | None = None

    if evidence and evidence.filename:
        ext = Path(evidence.filename).suffix.lower()
        if ext not in _ALLOWED_EVIDENCE_EXT:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file type '{ext}'. "
                    "Use JPG, PNG, WebP, PDF, DOC, or DOCX."
                ),
            )
        data = evidence.file.read()
        if len(data) > _MAX_EVIDENCE_BYTES:
            raise HTTPException(
                status_code=400,
                detail="Evidence file must be under 10 MB",
            )
        # Save file temporarily — will rename after we get the cred ID
        evidence_filename = f"evidence{ext}"
        # We'll store after insert so we have the credential ID
        evidence_data = data
    else:
        evidence_data = None

    try:
        cred = rep_svc.add_credential(
            user_id, credential_type, description, evidence_filename
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Save evidence file to disk using credential ID
    if evidence_data and evidence_filename:
        folder = _EVIDENCE_ROOT / str(cred["id"])
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / evidence_filename
        dest.write_bytes(evidence_data)

    # Build evidence_url for the response
    cred["evidence_url"] = (
        f"/api/v1/media/credential-evidence/{cred['id']}" if evidence_filename else None
    )

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

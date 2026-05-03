"""Community events API routes."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from backend.config import PROJECT_ROOT
from backend.models.events import (
    EventComment,
    EventCommentCreate,
    EventCommentListResponse,
    EventCommentUpdate,
    EventCreate,
    EventDetail,
    EventListResponse,
    EventMember,
    EventStats,
    EventSummary,
    EventUpdate,
)
from backend.services import auth as auth_svc
from backend.services import events as event_svc

_COVER_ROOT = PROJECT_ROOT / "data/uploads/event_covers"
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_COVER_MB = 10

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])


def _require_auth(authorization: str | None) -> int:
    """Extract user_id from auth header or raise 401."""
    user_id = auth_svc.get_current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def _event_summary(row: dict) -> EventSummary:
    """Build an EventSummary from a service row dict."""
    return EventSummary(
        id=str(row["id"]),
        title=row["title"],
        description=row.get("description"),
        event_type=row["event_type"],
        status=row["status"],
        start_date=row.get("start_date"),
        end_date=row.get("end_date"),
        lat=row.get("lat"),
        lon=row.get("lon"),
        location_name=row.get("location_name"),
        is_public=row["is_public"],
        invite_code=row.get("invite_code"),
        creator_id=row["creator_id"],
        creator_name=row["creator_name"],
        creator_avatar_url=(
            f"/api/v1/media/avatar/{row['creator_id']}"
            if row.get("creator_avatar")
            else None
        ),
        creator_tier=row.get("creator_tier"),
        member_count=row.get("member_count", 0),
        sighting_count=row.get("sighting_count", 0),
        my_role=row.get("my_role"),
        vessel_id=row.get("vessel_id"),
        vessel_name=row.get("vessel_name"),
        vessel_type=row.get("vessel_type"),
        cover_url=(
            f"/api/v1/events/{row['id']}/cover" if row.get("cover_filename") else None
        ),
        created_at=row["created_at"],
    )


def _event_detail(row: dict) -> EventDetail:
    """Build an EventDetail from a service row dict."""
    members = [
        EventMember(
            user_id=m["user_id"],
            display_name=m["display_name"],
            role=m["role"],
            joined_at=m["joined_at"],
            reputation_tier=m.get("reputation_tier"),
            avatar_url=(
                f"/api/v1/media/avatar/{m['user_id']}"
                if m.get("avatar_filename")
                else None
            ),
        )
        for m in row.get("members", [])
    ]
    return EventDetail(
        id=str(row["id"]),
        title=row["title"],
        description=row.get("description"),
        event_type=row["event_type"],
        status=row["status"],
        start_date=row.get("start_date"),
        end_date=row.get("end_date"),
        lat=row.get("lat"),
        lon=row.get("lon"),
        location_name=row.get("location_name"),
        is_public=row["is_public"],
        invite_code=row.get("invite_code"),
        creator_id=row["creator_id"],
        creator_name=row["creator_name"],
        creator_avatar_url=(
            f"/api/v1/media/avatar/{row['creator_id']}"
            if row.get("creator_avatar")
            else None
        ),
        creator_tier=row.get("creator_tier"),
        member_count=row.get("member_count", 0),
        sighting_count=row.get("sighting_count", 0),
        vessel_id=row.get("vessel_id"),
        vessel_name=row.get("vessel_name"),
        vessel_type=row.get("vessel_type"),
        created_at=row["created_at"],
        updated_at=row.get("updated_at"),
        cover_url=(
            f"/api/v1/events/{row['id']}/cover" if row.get("cover_filename") else None
        ),
        members=members,
    )


# ── Create ───────────────────────────────────────────────────


@router.post("", response_model=EventDetail, status_code=201)
def create_event(
    body: EventCreate,
    authorization: str | None = Header(default=None),
) -> EventDetail:
    """Create a new community event."""
    user_id = _require_auth(authorization)
    try:
        row = event_svc.create_event(
            creator_id=user_id,
            title=body.title,
            description=body.description,
            event_type=body.event_type,
            start_date=body.start_date,
            end_date=body.end_date,
            lat=body.lat,
            lon=body.lon,
            location_name=body.location_name,
            is_public=body.is_public,
            vessel_id=body.vessel_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _event_detail(row)


# ── List (public) ────────────────────────────────────────────


@router.get("", response_model=EventListResponse)
def list_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
) -> EventListResponse:
    """List public events with optional filters."""
    rows, total = event_svc.list_public_events(
        limit=limit,
        offset=offset,
        status=status,
        event_type=event_type,
    )
    return EventListResponse(
        events=[_event_summary(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── My events ───────────────────────────────────────────────


@router.get("/mine", response_model=EventListResponse)
def list_my_events(
    authorization: str | None = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> EventListResponse:
    """List events the authenticated user is a member of."""
    user_id = _require_auth(authorization)
    rows, total = event_svc.list_user_events(user_id, limit, offset)
    return EventListResponse(
        events=[_event_summary(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── Join by invite code ─────────────────────────────────────


@router.post(
    "/join/{invite_code}",
    response_model=EventDetail,
)
def join_by_invite(
    invite_code: str,
    authorization: str | None = Header(default=None),
) -> EventDetail:
    """Join an event using its invite code."""
    user_id = _require_auth(authorization)
    row = event_svc.join_event_by_invite(invite_code, user_id)
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Event not found or invite code invalid",
        )
    return _event_detail(row)


# ── Invite preview (unauthenticated) ────────────────────────


@router.get("/invite/{invite_code}", response_model=EventSummary)
def preview_invite(invite_code: str) -> EventSummary:
    """Preview an event by invite code (no auth needed).
    Allows unauthenticated users to see event details before
    creating an account."""
    row = event_svc.get_event_by_invite(invite_code)
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Event not found or invite code invalid",
        )
    return _event_summary(row)


# ── Event detail ─────────────────────────────────────────────


@router.get("/{event_id}", response_model=EventDetail)
def get_event(
    event_id: str,
    authorization: str | None = Header(default=None),
) -> EventDetail:
    """Get full details of an event."""
    user_id = auth_svc.get_current_user_id(authorization)
    row = event_svc.get_event_detail(event_id)
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")

    # Private events: only members (or creator) can view full detail
    if not row["is_public"]:
        is_member = any(m["user_id"] == user_id for m in row.get("members", []))
        if not is_member:
            raise HTTPException(
                status_code=403,
                detail="This is a private event. Use an invite link to join.",
            )
    return _event_detail(row)


# ── Update ───────────────────────────────────────────────────


@router.patch("/{event_id}", response_model=EventDetail)
def update_event(
    event_id: str,
    body: EventUpdate,
    authorization: str | None = Header(default=None),
) -> EventDetail:
    """Update an event. Creator or organizer only."""
    user_id = _require_auth(authorization)
    updates = body.model_dump(exclude_none=True)
    try:
        row = event_svc.update_event(event_id, user_id, **updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not row:
        raise HTTPException(
            status_code=403,
            detail="Not authorised or event not found",
        )
    return _event_detail(row)


# ── Delete ───────────────────────────────────────────────────


@router.delete("/{event_id}", status_code=204)
def delete_event(
    event_id: str,
    authorization: str | None = Header(default=None),
) -> None:
    """Delete an event. Creator only."""
    user_id = _require_auth(authorization)
    if not event_svc.delete_event(event_id, user_id):
        raise HTTPException(
            status_code=403,
            detail="Not authorised or event not found",
        )


# ── Members ──────────────────────────────────────────────────


@router.post("/{event_id}/join", response_model=EventDetail)
def join_event(
    event_id: str,
    authorization: str | None = Header(default=None),
) -> EventDetail:
    """Join a public event directly."""
    user_id = _require_auth(authorization)
    # Check event exists and is public
    detail = event_svc.get_event_detail(event_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Event not found")
    if not detail["is_public"]:
        raise HTTPException(
            status_code=403,
            detail="This is a private event. Use an invite link to join.",
        )
    row = event_svc.join_event(event_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_detail(row)


@router.delete("/{event_id}/leave", status_code=204)
def leave_event(
    event_id: str,
    authorization: str | None = Header(default=None),
) -> None:
    """Leave an event. Creator cannot leave (must delete)."""
    user_id = _require_auth(authorization)
    if not event_svc.leave_event(event_id, user_id):
        raise HTTPException(
            status_code=400,
            detail="Cannot leave (you may be the creator)",
        )


@router.patch("/{event_id}/members/{target_user_id}/role")
def change_member_role(
    event_id: str,
    target_user_id: int,
    role: str = Query(...),
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    """Change a member's role. Creator only."""
    user_id = _require_auth(authorization)
    if not event_svc.update_member_role(event_id, user_id, target_user_id, role):
        raise HTTPException(
            status_code=403,
            detail="Not authorised or invalid role",
        )
    return {"status": "updated", "role": role}


# ── Sighting linking ────────────────────────────────────────


@router.get("/{event_id}/sightings")
def list_event_sightings(
    event_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """List sightings linked to an event."""
    rows, total = event_svc.get_event_sightings(event_id, limit, offset)
    return {"sightings": rows, "total": total}


@router.post(
    "/{event_id}/sightings/{submission_id}",
    status_code=201,
)
def link_sighting(
    event_id: str,
    submission_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    """Link a sighting to an event. Must be event member and
    sighting owner."""
    user_id = _require_auth(authorization)
    if not event_svc.link_sighting(event_id, submission_id, user_id):
        raise HTTPException(
            status_code=403,
            detail="Not authorised or sighting not found",
        )
    return {"status": "linked"}


@router.delete("/{event_id}/sightings/{submission_id}")
def unlink_sighting(
    event_id: str,
    submission_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    """Unlink a sighting from an event."""
    user_id = _require_auth(authorization)
    if not event_svc.unlink_sighting(submission_id, user_id):
        raise HTTPException(
            status_code=403,
            detail="Not authorised or sighting not found",
        )
    return {"status": "unlinked"}


# ── Event stats ──────────────────────────────────────────────


@router.get("/{event_id}/stats", response_model=EventStats)
def event_stats(event_id: str) -> EventStats:
    """Get fun summary statistics for an event."""
    result = event_svc.get_event_stats(event_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventStats(**result)


# ── Comments ─────────────────────────────────────────────────


@router.get(
    "/{event_id}/comments",
    response_model=EventCommentListResponse,
)
def list_comments(
    event_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> EventCommentListResponse:
    """List comments on an event (oldest first)."""
    rows, total = event_svc.list_event_comments(event_id, limit, offset)
    return EventCommentListResponse(
        comments=[EventComment(**r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{event_id}/comments",
    response_model=EventComment,
    status_code=201,
)
def create_comment(
    event_id: str,
    body: EventCommentCreate,
    authorization: str | None = Header(default=None),
) -> EventComment:
    """Post a comment on an event."""
    user_id = _require_auth(authorization)
    result = event_svc.add_event_comment(event_id, user_id, body.body)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )
    return EventComment(**result)


@router.patch(
    "/{event_id}/comments/{comment_id}",
    response_model=EventComment,
)
def edit_comment(
    event_id: str,
    comment_id: int,
    body: EventCommentUpdate,
    authorization: str | None = Header(default=None),
) -> EventComment:
    """Edit your own comment."""
    user_id = _require_auth(authorization)
    result = event_svc.update_event_comment(comment_id, user_id, body.body)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Comment not found or not yours",
        )
    return EventComment(**result)


@router.delete(
    "/{event_id}/comments/{comment_id}",
    status_code=204,
)
def delete_comment(
    event_id: str,
    comment_id: int,
    authorization: str | None = Header(default=None),
) -> None:
    """Delete your own comment."""
    user_id = _require_auth(authorization)
    if not event_svc.delete_event_comment(comment_id, user_id):
        raise HTTPException(
            status_code=404,
            detail="Comment not found or not yours",
        )


# ── Cover photo ──────────────────────────────────────────────


@router.post("/{event_id}/cover", status_code=201)
async def upload_cover(
    event_id: str,
    image: UploadFile = File(  # noqa: B008
        ...,
        description="Cover photo (JPEG/PNG/WebP, max 10 MB)",
    ),
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    """Upload a cover photo for the event. Creator/organizer only."""
    user_id = _require_auth(authorization)

    ext = Path(image.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format {ext}. "
            f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    data = await image.read()
    if len(data) > _MAX_COVER_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"Cover exceeds {_MAX_COVER_MB} MB limit",
        )

    stored = event_svc.upload_event_cover(
        event_id, user_id, data, image.filename or "cover.jpg"
    )
    if not stored:
        raise HTTPException(
            status_code=403,
            detail="Not authorised (must be creator or organizer)",
        )
    return {"status": "uploaded", "filename": stored}


@router.get("/{event_id}/cover")
def get_cover(event_id: str) -> FileResponse:
    """Serve the event cover photo."""
    cover_dir = _COVER_ROOT / event_id
    if cover_dir.exists():
        for f in cover_dir.glob("cover.*"):
            media_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
            }
            mt = media_map.get(f.suffix.lower(), "image/jpeg")
            return FileResponse(f, media_type=mt)
    raise HTTPException(status_code=404, detail="No cover photo")


# ── Photo gallery ────────────────────────────────────────────


@router.get("/{event_id}/gallery")
def list_gallery(
    event_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """List gallery photos for an event."""
    photos, total = event_svc.list_gallery_photos(
        event_id,
        limit=limit,
        offset=offset,
    )
    return {"photos": photos, "total": total}


@router.post("/{event_id}/gallery", status_code=201)
async def upload_gallery_photo(
    event_id: str,
    image: UploadFile = File(  # noqa: B008
        ...,
        description="Gallery photo (JPEG/PNG/WebP, max 10 MB)",
    ),
    caption: str | None = Form(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """Upload a photo to the event gallery. Members only."""
    user_id = _require_auth(authorization)

    ext = Path(image.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format {ext}. "
            f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    data = await image.read()
    if len(data) > _MAX_COVER_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"Image exceeds {_MAX_COVER_MB} MB limit",
        )

    result = event_svc.upload_gallery_photo(
        event_id,
        user_id,
        data,
        image.filename or "photo.jpg",
        caption=caption,
    )
    if result is None:
        raise HTTPException(
            status_code=403,
            detail="Not authorised — must be an event member",
        )
    if result.get("error") == "limit_reached":
        raise HTTPException(
            status_code=400,
            detail="Gallery limit reached (max 50 photos per event)",
        )
    return result


@router.get("/{event_id}/gallery/{photo_id}")
def get_gallery_photo(event_id: str, photo_id: int) -> FileResponse:
    """Serve a gallery photo."""
    path = event_svc.get_gallery_photo_path(event_id, photo_id)
    if not path:
        raise HTTPException(status_code=404, detail="Photo not found")
    media_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    mt = media_map.get(path.suffix.lower(), "image/jpeg")
    return FileResponse(path, media_type=mt)


@router.delete("/{event_id}/gallery/{photo_id}", status_code=204)
def delete_gallery_photo(
    event_id: str,
    photo_id: int,
    authorization: str | None = Header(default=None),
) -> None:
    """Delete a gallery photo. Uploader, creator, or organizer only."""
    user_id = _require_auth(authorization)
    if not event_svc.delete_gallery_photo(event_id, photo_id, user_id):
        raise HTTPException(
            status_code=403,
            detail="Not authorised or photo not found",
        )

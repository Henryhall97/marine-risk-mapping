"""External (curated) events API routes.

Public users can list upcoming external events.
Moderators can create, update, and delete them.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Query

from backend.models.external_events import (
    ExternalEventCreate,
    ExternalEventListResponse,
    ExternalEventResponse,
    ExternalEventUpdate,
)
from backend.services import auth as auth_svc
from backend.services import external_events as ext_svc

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/external-events",
    tags=["external-events"],
)


def _require_auth(authorization: str | None) -> int:
    """Extract user_id from auth header or raise 401."""
    user_id = auth_svc.get_current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def _require_moderator(authorization: str | None) -> int:
    """Require authenticated moderator. Returns user_id."""
    user_id = _require_auth(authorization)
    if not ext_svc.is_moderator(user_id):
        raise HTTPException(
            status_code=403,
            detail="Moderator access required",
        )
    return user_id


# ── Public endpoints ─────────────────────────────────────────


@router.get(
    "",
    response_model=ExternalEventListResponse,
    summary="List external events",
)
def list_external_events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    featured_only: bool = Query(False),
    event_type: str | None = Query(None),
) -> ExternalEventListResponse:
    """Public listing of curated external events."""
    rows, total = ext_svc.list_external_events(
        limit=limit,
        offset=offset,
        featured_only=featured_only,
        event_type=event_type,
    )
    return ExternalEventListResponse(
        total=total,
        offset=offset,
        limit=limit,
        events=[ExternalEventResponse(**r) for r in rows],
    )


@router.get(
    "/{event_id}",
    response_model=ExternalEventResponse,
    summary="Get external event detail",
)
def get_external_event(event_id: int) -> ExternalEventResponse:
    """Fetch a single external event by ID."""
    row = ext_svc.get_external_event(event_id)
    if not row:
        raise HTTPException(status_code=404, detail="External event not found")
    return ExternalEventResponse(**row)


# ── Moderator endpoints ──────────────────────────────────────


@router.post(
    "",
    response_model=ExternalEventResponse,
    status_code=201,
    summary="Create external event (moderator)",
)
def create_external_event(
    body: ExternalEventCreate,
    authorization: str | None = Header(None),
) -> ExternalEventResponse:
    """Create a curated external event. Requires moderator role."""
    user_id = _require_moderator(authorization)
    try:
        row = ext_svc.create_external_event(
            user_id,
            title=body.title,
            description=body.description,
            organizer=body.organizer,
            source_url=body.source_url,
            event_type=body.event_type,
            tags=body.tags,
            start_date=body.start_date,
            end_date=body.end_date,
            location_name=body.location_name,
            lat=body.lat,
            lon=body.lon,
            is_virtual=body.is_virtual,
            is_featured=body.is_featured,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExternalEventResponse(**row)


@router.patch(
    "/{event_id}",
    response_model=ExternalEventResponse,
    summary="Update external event (moderator)",
)
def update_external_event(
    event_id: int,
    body: ExternalEventUpdate,
    authorization: str | None = Header(None),
) -> ExternalEventResponse:
    """Update an external event. Requires moderator role."""
    _require_moderator(authorization)
    fields = body.model_dump(exclude_unset=True)
    try:
        row = ext_svc.update_external_event(event_id, **fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="External event not found")
    return ExternalEventResponse(**row)


@router.delete(
    "/{event_id}",
    status_code=204,
    summary="Delete external event (moderator)",
)
def delete_external_event(
    event_id: int,
    authorization: str | None = Header(None),
) -> None:
    """Soft-delete an external event. Requires moderator role."""
    _require_moderator(authorization)
    if not ext_svc.delete_external_event(event_id):
        raise HTTPException(status_code=404, detail="External event not found")


# ── Seed endpoint (moderator) ────────────────────────────────


@router.post(
    "/seed",
    summary="Seed external events (moderator)",
)
def seed_external_events(
    authorization: str | None = Header(None),
) -> dict:
    """Seed the database with curated NOAA events.
    Idempotent — skips events that already exist."""
    user_id = _require_moderator(authorization)
    count = ext_svc.seed_external_events(user_id)
    return {"seeded": count}

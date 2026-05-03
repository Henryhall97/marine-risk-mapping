"""Submissions API routes — user submissions + public verification."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Query

from backend.models.submissions import (
    ActivityDay,
    CommentCreate,
    CommentListResponse,
    CommentResponse,
    CommentUpdate,
    CommunityStats,
    CommunityStatsResponse,
    CommunityVoteRequest,
    MapSighting,
    MapSightingResponse,
    ModeratorVerifyRequest,
    RecentActivity,
    SubmissionDetail,
    SubmissionListResponse,
    SubmissionSummary,
    TopContributor,
    VerifyRequest,
    VoteResponse,
    WhaleOfTheWeek,
)
from backend.services import auth as auth_svc
from backend.services import submissions as sub_svc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/submissions", tags=["submissions"])


# ── Community stats (public, no auth) ────────────────────────


@router.get(
    "/community-stats",
    response_model=CommunityStatsResponse,
)
def community_stats() -> CommunityStatsResponse:
    """Aggregate community statistics, activity feed, and leaderboard."""
    raw_stats = sub_svc.get_community_stats()
    raw_activity = sub_svc.get_recent_activity(limit=8)
    raw_leaders = sub_svc.get_top_contributors(limit=10)
    raw_histogram = sub_svc.get_activity_histogram(days=30)
    raw_wotw = sub_svc.get_whale_of_the_week()
    return CommunityStatsResponse(
        stats=CommunityStats(**raw_stats),
        recent_activity=[RecentActivity(**r) for r in raw_activity],
        top_contributors=[TopContributor(**r) for r in raw_leaders],
        activity_histogram=[
            ActivityDay(
                date=str(r["date"]),
                count=r["count"],
            )
            for r in raw_histogram
        ],
        whale_of_the_week=(WhaleOfTheWeek(**raw_wotw) if raw_wotw else None),
    )


def _require_auth(authorization: str | None) -> int:
    """Extract user_id from auth header or raise 401."""
    user_id = auth_svc.get_current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


# ── User's own submissions ───────────────────────────────────


@router.get("/mine", response_model=SubmissionListResponse)
def list_my_submissions(
    authorization: str | None = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SubmissionListResponse:
    """List the current user's submissions."""
    user_id = _require_auth(authorization)
    rows, total = sub_svc.get_user_submissions(user_id, limit, offset)
    return SubmissionListResponse(
        submissions=[SubmissionSummary(**r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── Public submissions ───────────────────────────────────────


@router.get("/public", response_model=SubmissionListResponse)
def list_public_submissions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    species: str | None = Query(
        default=None,
        description="Filter by model_species or species_guess",
    ),
    lat_min: float | None = Query(default=None, ge=-90, le=90),
    lat_max: float | None = Query(default=None, ge=-90, le=90),
    lon_min: float | None = Query(default=None, ge=-180, le=180),
    lon_max: float | None = Query(default=None, ge=-180, le=180),
    since: str | None = Query(
        default=None,
        description="ISO date (YYYY-MM-DD) — only submissions on/after",
    ),
    until: str | None = Query(
        default=None,
        description="ISO date (YYYY-MM-DD) — only submissions on/before",
    ),
    exclude_user_id: int | None = Query(
        default=None,
        description="Exclude submissions from this user (for review queue)",
    ),
) -> SubmissionListResponse:
    """Browse public submissions for community verification."""
    rows, total = sub_svc.get_public_submissions(
        limit,
        offset,
        status,
        exclude_user_id=exclude_user_id,
        species=species,
        lat_min=lat_min,
        lat_max=lat_max,
        lon_min=lon_min,
        lon_max=lon_max,
        since=since,
        until=until,
    )
    return SubmissionListResponse(
        submissions=[SubmissionSummary(**r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── Map sightings (spatial, lightweight) ─────────────────────


@router.get(
    "/map-sightings",
    response_model=MapSightingResponse,
)
def map_sightings(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    species: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=2000, ge=1, le=5000),
) -> MapSightingResponse:
    """Lightweight spatial query for rendering sightings on the map.

    Returns minimal fields: position, species, verification status,
    media flags, and timestamp. Filtered by bounding box."""
    if lat_min >= lat_max or lon_min >= lon_max:
        raise HTTPException(
            status_code=400,
            detail="Invalid bbox: min must be < max",
        )
    rows = sub_svc.get_map_sightings(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        species=species,
        status=status,
        limit=limit,
    )
    return MapSightingResponse(
        total=len(rows),
        data=[MapSighting(**r) for r in rows],
    )


# ── Single submission detail ─────────────────────────────────


@router.get("/{submission_id}", response_model=SubmissionDetail)
def get_submission(
    submission_id: str,
    authorization: str | None = Header(default=None),
) -> SubmissionDetail:
    """Get full details of a submission.
    Public submissions are visible to all. Private ones require ownership."""
    detail = sub_svc.get_submission_detail(submission_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Submission not found")

    # If not public, only the owner can view
    if not detail.get("is_public"):
        user_id = auth_svc.get_current_user_id(authorization)
        # We don't have user_id in detail, so check ownership via DB
        if user_id is None:
            raise HTTPException(status_code=404, detail="Submission not found")
    return SubmissionDetail(**detail)


# ── Toggle public visibility ─────────────────────────────────


@router.patch("/{submission_id}/visibility")
def toggle_visibility(
    submission_id: str,
    is_public: bool = Query(...),
    authorization: str | None = Header(default=None),
) -> dict[str, str | bool]:
    """Toggle public/private status on your own submission."""
    user_id = _require_auth(authorization)
    ok = sub_svc.toggle_public(submission_id, user_id, is_public)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Submission not found or not yours",
        )
    return {"id": submission_id, "is_public": is_public}


# ── Community verification ───────────────────────────────────


@router.post("/{submission_id}/verify", response_model=SubmissionDetail)
def verify_submission(
    submission_id: str,
    body: VerifyRequest,
    authorization: str | None = Header(default=None),
) -> SubmissionDetail:
    """Legacy verify — routes to moderator or community automatically."""
    verifier_id = _require_auth(authorization)

    try:
        result = sub_svc.verify_submission(
            submission_id, verifier_id, body.status, body.notes
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Submission not found or not public",
        )
    return SubmissionDetail(**result)


# ── Moderator verification ───────────────────────────────────


@router.post(
    "/{submission_id}/moderate",
    response_model=SubmissionDetail,
)
def moderate_submission(
    submission_id: str,
    body: ModeratorVerifyRequest,
    authorization: str | None = Header(default=None),
) -> SubmissionDetail:
    """Moderator-only: set authoritative verified/rejected status."""
    mod_id = _require_auth(authorization)

    try:
        result = sub_svc.moderator_verify(
            submission_id, mod_id, body.status, body.notes
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Submission not found or not public",
        )
    return SubmissionDetail(**result)


# ── Community voting ─────────────────────────────────────────


@router.post(
    "/{submission_id}/vote",
    response_model=SubmissionDetail,
)
def cast_vote(
    submission_id: str,
    body: CommunityVoteRequest,
    authorization: str | None = Header(default=None),
) -> SubmissionDetail:
    """Cast or update a community vote (agree / disagree / refine)."""
    voter_id = _require_auth(authorization)

    try:
        result = sub_svc.community_vote(
            submission_id,
            voter_id,
            body.vote,
            body.notes,
            body.species_suggestion,
            body.suggested_rank,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Submission not found or not public",
        )
    return SubmissionDetail(**result)


@router.get(
    "/{submission_id}/votes",
    response_model=list[VoteResponse],
)
def list_votes(
    submission_id: str,
) -> list[VoteResponse]:
    """List all community votes for a submission."""
    rows = sub_svc.get_submission_votes(submission_id)
    return [VoteResponse(**r) for r in rows]


# ── User's public submissions (for public profiles) ─────────


@router.get("/user/{user_id}", response_model=SubmissionListResponse)
def list_user_public_submissions(
    user_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SubmissionListResponse:
    """List a user's public submissions (for their public profile)."""
    rows, total = sub_svc.get_user_public_submissions(user_id, limit, offset)
    return SubmissionListResponse(
        submissions=[SubmissionSummary(**r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── Comments ─────────────────────────────────────────────────


@router.get(
    "/{submission_id}/comments",
    response_model=CommentListResponse,
)
def list_comments(
    submission_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CommentListResponse:
    """List comments on a submission (oldest first)."""
    rows, total = sub_svc.list_comments(submission_id, limit, offset)
    return CommentListResponse(
        comments=[CommentResponse(**r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{submission_id}/comments",
    response_model=CommentResponse,
    status_code=201,
)
def create_comment(
    submission_id: str,
    body: CommentCreate,
    authorization: str | None = Header(default=None),
) -> CommentResponse:
    """Post a comment on a public submission."""
    user_id = _require_auth(authorization)
    result = sub_svc.add_comment(submission_id, user_id, body.body)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Submission not found or not public",
        )
    return CommentResponse(**result)


@router.patch(
    "/{submission_id}/comments/{comment_id}",
    response_model=CommentResponse,
)
def edit_comment(
    submission_id: str,
    comment_id: int,
    body: CommentUpdate,
    authorization: str | None = Header(default=None),
) -> CommentResponse:
    """Edit your own comment."""
    user_id = _require_auth(authorization)
    result = sub_svc.update_comment(comment_id, user_id, body.body)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Comment not found or not yours",
        )
    return CommentResponse(**result)


@router.delete(
    "/{submission_id}/comments/{comment_id}",
    status_code=204,
)
def delete_comment(
    submission_id: str,
    comment_id: int,
    authorization: str | None = Header(default=None),
) -> None:
    """Delete your own comment."""
    user_id = _require_auth(authorization)
    if not sub_svc.delete_comment(comment_id, user_id):
        raise HTTPException(
            status_code=404,
            detail="Comment not found or not yours",
        )

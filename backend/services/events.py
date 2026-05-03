"""Community events service — create, join, manage events."""

from __future__ import annotations

import logging
import secrets
import string
from pathlib import Path
from typing import Any

from backend.config import PROJECT_ROOT
from backend.services.database import fetch_all, fetch_one, fetch_scalar, get_conn
from backend.services.reputation import _log_event as _rep_log

log = logging.getLogger(__name__)

_COVER_ROOT = PROJECT_ROOT / "data/uploads/event_covers"

# Valid event types
VALID_EVENT_TYPES = {
    "whale_watching",
    "research_expedition",
    "citizen_science",
    "cleanup",
    "educational",
    "other",
}

# Valid event statuses
VALID_STATUSES = {"upcoming", "active", "completed", "cancelled"}

# Valid member roles
VALID_ROLES = {"creator", "organizer", "member"}


def _generate_invite_code(length: int = 8) -> str:
    """Generate a short, URL-safe invite code."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ── Event CRUD ───────────────────────────────────────────────


def create_event(
    creator_id: int,
    title: str,
    *,
    description: str | None = None,
    event_type: str = "whale_watching",
    start_date: Any = None,
    end_date: Any = None,
    lat: float | None = None,
    lon: float | None = None,
    location_name: str | None = None,
    is_public: bool = True,
    vessel_id: int | None = None,
) -> dict[str, Any]:
    """Create a new community event. Returns the event dict."""
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"Invalid event_type: {event_type}. "
            f"Must be one of {sorted(VALID_EVENT_TYPES)}"
        )

    invite_code = _generate_invite_code()

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO community_events
                (creator_id, title, description, event_type,
                 start_date, end_date, lat, lon, location_name,
                 is_public, invite_code, vessel_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                creator_id,
                title,
                description,
                event_type,
                start_date,
                end_date,
                lat,
                lon,
                location_name,
                is_public,
                invite_code,
                vessel_id,
            ),
        )
        event_id = cur.fetchone()[0]

        # Creator is automatically the first member with 'creator' role
        cur.execute(
            """
            INSERT INTO event_members (event_id, user_id, role)
            VALUES (%s, %s, 'creator')
            """,
            (event_id, creator_id),
        )
        conn.commit()

    # Award reputation for creating an event
    _rep_log(
        creator_id,
        "event_created",
        5,
        description=f"Created event: {title}",
    )

    log.info("Created event %s by user %d", event_id, creator_id)
    return get_event_detail(str(event_id)) or {}


def update_event(
    event_id: str,
    user_id: int,
    **updates: Any,
) -> dict[str, Any] | None:
    """Update an event. Only creator/organizer can update.
    Returns updated event or None if not found/unauthorized."""
    # Check authorization
    role = _get_member_role(event_id, user_id)
    if role not in ("creator", "organizer"):
        return None

    # Build SET clause dynamically
    allowed = {
        "title",
        "description",
        "event_type",
        "status",
        "start_date",
        "end_date",
        "lat",
        "lon",
        "location_name",
        "is_public",
        "vessel_id",
    }
    sets: list[str] = []
    vals: list[Any] = []
    for key, val in updates.items():
        if key in allowed and val is not None:
            if key == "event_type" and val not in VALID_EVENT_TYPES:
                raise ValueError(f"Invalid event_type: {val}")
            if key == "status" and val not in VALID_STATUSES:
                raise ValueError(f"Invalid status: {val}")
            sets.append(f"{key} = %s")
            vals.append(val)

    if not sets:
        return get_event_detail(event_id)

    sets.append("updated_at = now()")
    vals.append(event_id)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE community_events SET {', '.join(sets)} "  # noqa: S608
            "WHERE id = %s",
            tuple(vals),
        )
        conn.commit()

    return get_event_detail(event_id)


def delete_event(event_id: str, user_id: int) -> bool:
    """Delete an event. Only the creator can delete."""
    role = _get_member_role(event_id, user_id)
    if role != "creator":
        return False

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM community_events WHERE id = %s",
            (event_id,),
        )
        conn.commit()
        return cur.rowcount > 0


# ── Query ────────────────────────────────────────────────────


def get_event_detail(event_id: str) -> dict[str, Any] | None:
    """Get full event detail with member/sighting counts."""
    row = fetch_one(
        """
        SELECT e.*,
               u.display_name  AS creator_name,
               u.avatar_filename AS creator_avatar,
               u.reputation_tier AS creator_tier,
               v.vessel_name  AS vessel_name,
               v.vessel_type  AS vessel_type,
               (SELECT count(*) FROM event_members em
                WHERE em.event_id = e.id) AS member_count,
               (SELECT count(*) FROM sighting_submissions s
                WHERE s.event_id = e.id) AS sighting_count
        FROM community_events e
        JOIN users u ON u.id = e.creator_id
        LEFT JOIN user_vessels v ON v.id = e.vessel_id
        WHERE e.id = %s
        """,
        (event_id,),
    )
    if not row:
        return None

    # Attach members list
    members = fetch_all(
        """
        SELECT em.user_id, u.display_name, em.role, em.joined_at,
               u.reputation_tier, u.avatar_filename
        FROM event_members em
        JOIN users u ON u.id = em.user_id
        WHERE em.event_id = %s
        ORDER BY em.joined_at
        """,
        (event_id,),
    )
    row["members"] = members
    return row


def get_event_by_invite(invite_code: str) -> dict[str, Any] | None:
    """Look up an event by its invite code."""
    row = fetch_one(
        """
        SELECT e.*,
               u.display_name  AS creator_name,
               u.avatar_filename AS creator_avatar,
               u.reputation_tier AS creator_tier,
               v.vessel_name AS vessel_name,
               v.vessel_type AS vessel_type,
               (SELECT count(*) FROM event_members em
                WHERE em.event_id = e.id) AS member_count,
               (SELECT count(*) FROM sighting_submissions s
                WHERE s.event_id = e.id) AS sighting_count
        FROM community_events e
        JOIN users u ON u.id = e.creator_id
        LEFT JOIN user_vessels v ON v.id = e.vessel_id
        WHERE e.invite_code = %s
        """,
        (invite_code,),
    )
    return row


def list_public_events(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    event_type: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """List public events with pagination."""
    where = ["e.is_public = TRUE"]
    params: list[Any] = []

    if status:
        where.append("e.status = %s")
        params.append(status)
    if event_type:
        where.append("e.event_type = %s")
        params.append(event_type)

    where_clause = " AND ".join(where)

    total = fetch_scalar(
        f"SELECT count(*) FROM community_events e "  # noqa: S608
        f"WHERE {where_clause}",
        tuple(params),
    )

    params.extend([limit, offset])
    rows = fetch_all(
        f"""
        SELECT e.*,
               u.display_name  AS creator_name,
               u.avatar_filename AS creator_avatar,
               u.reputation_tier AS creator_tier,
               v.vessel_name AS vessel_name,
               v.vessel_type AS vessel_type,
               (SELECT count(*) FROM event_members em
                WHERE em.event_id = e.id) AS member_count,
               (SELECT count(*) FROM sighting_submissions s
                WHERE s.event_id = e.id) AS sighting_count
        FROM community_events e
        JOIN users u ON u.id = e.creator_id
        LEFT JOIN user_vessels v ON v.id = e.vessel_id
        WHERE {where_clause}
        ORDER BY
            CASE e.status
                WHEN 'active' THEN 0
                WHEN 'upcoming' THEN 1
                WHEN 'completed' THEN 2
                WHEN 'cancelled' THEN 3
            END,
            e.start_date ASC NULLS LAST,
            e.created_at DESC
        LIMIT %s OFFSET %s
        """,  # noqa: S608
        tuple(params),
    )
    return rows, total or 0


def list_user_events(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List events a user is a member of."""
    total = fetch_scalar(
        """
        SELECT count(*)
        FROM event_members em
        JOIN community_events e ON e.id = em.event_id
        WHERE em.user_id = %s
        """,
        (user_id,),
    )

    rows = fetch_all(
        """
        SELECT e.*,
               u.display_name  AS creator_name,
               u.avatar_filename AS creator_avatar,
               u.reputation_tier AS creator_tier,
               em.role AS my_role,
               v.vessel_name AS vessel_name,
               v.vessel_type AS vessel_type,
               (SELECT count(*) FROM event_members em2
                WHERE em2.event_id = e.id) AS member_count,
               (SELECT count(*) FROM sighting_submissions s
                WHERE s.event_id = e.id) AS sighting_count
        FROM event_members em
        JOIN community_events e ON e.id = em.event_id
        JOIN users u ON u.id = e.creator_id
        LEFT JOIN user_vessels v ON v.id = e.vessel_id
        WHERE em.user_id = %s
        ORDER BY e.start_date ASC NULLS LAST,
                 e.created_at DESC
        LIMIT %s OFFSET %s
        """,
        (user_id, limit, offset),
    )
    return rows, total or 0


def get_event_sightings(
    event_id: str,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Get sightings linked to an event."""
    total = fetch_scalar(
        "SELECT count(*) FROM sighting_submissions WHERE event_id = %s",
        (event_id,),
    )

    rows = fetch_all(
        """
        SELECT s.id, s.created_at, s.lat, s.lon,
               s.species_guess, s.model_species, s.model_confidence,
               s.risk_category, s.risk_score,
               s.verification_status,
               s.community_agree, s.community_disagree,
               s.photo_filename IS NOT NULL AS has_photo,
               s.audio_filename IS NOT NULL AS has_audio,
               u.display_name AS submitter_name,
               u.id AS submitter_id,
               u.reputation_tier AS submitter_tier,
               u.avatar_filename AS submitter_avatar
        FROM sighting_submissions s
        LEFT JOIN users u ON u.id = s.user_id
        WHERE s.event_id = %s
        ORDER BY s.created_at DESC
        LIMIT %s OFFSET %s
        """,
        (event_id, limit, offset),
    )
    return rows, total or 0


# ── Membership ───────────────────────────────────────────────


def join_event(event_id: str, user_id: int) -> dict[str, Any] | None:
    """Join an event as a member. Returns event detail or None
    if event not found."""
    event = fetch_one(
        "SELECT id FROM community_events WHERE id = %s",
        (event_id,),
    )
    if not event:
        return None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event_members (event_id, user_id, role)
            VALUES (%s, %s, 'member')
            ON CONFLICT (event_id, user_id) DO NOTHING
            """,
            (event_id, user_id),
        )
        conn.commit()

    # Award reputation for joining
    _rep_log(
        user_id,
        "event_joined",
        2,
        description="Joined a community event",
    )

    return get_event_detail(event_id)


def join_event_by_invite(
    invite_code: str,
    user_id: int,
) -> dict[str, Any] | None:
    """Join an event using its invite code."""
    event = get_event_by_invite(invite_code)
    if not event:
        return None
    return join_event(str(event["id"]), user_id)


def leave_event(event_id: str, user_id: int) -> bool:
    """Leave an event. Creator cannot leave (must delete)."""
    role = _get_member_role(event_id, user_id)
    if role == "creator":
        return False  # Creator must delete the event

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM event_members WHERE event_id = %s AND user_id = %s",
            (event_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def update_member_role(
    event_id: str,
    requester_id: int,
    target_user_id: int,
    new_role: str,
) -> bool:
    """Promote/demote a member. Only creator can change roles."""
    if new_role not in VALID_ROLES or new_role == "creator":
        return False

    requester_role = _get_member_role(event_id, requester_id)
    if requester_role != "creator":
        return False

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE event_members SET role = %s "
            "WHERE event_id = %s AND user_id = %s "
            "AND role != 'creator'",
            (new_role, event_id, target_user_id),
        )
        conn.commit()
        return cur.rowcount > 0


# ── Vessel helpers ───────────────────────────────────────────


def get_event_vessel_id(event_id: str) -> int | None:
    """Return the vessel_id linked to an event, or None."""
    return fetch_scalar(
        "SELECT vessel_id FROM community_events WHERE id = %s",
        (event_id,),
    )


# ── Sighting linking ────────────────────────────────────────


def link_sighting(
    event_id: str,
    submission_id: str,
    user_id: int,
) -> bool:
    """Link a sighting to an event. User must be event member
    and sighting owner."""
    # Verify membership
    role = _get_member_role(event_id, user_id)
    if not role:
        return False

    # Verify sighting ownership
    owner = fetch_scalar(
        "SELECT user_id FROM sighting_submissions WHERE id = %s",
        (submission_id,),
    )
    if owner != user_id:
        return False

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE sighting_submissions SET event_id = %s "
            "WHERE id = %s AND user_id = %s",
            (event_id, submission_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def unlink_sighting(
    submission_id: str,
    user_id: int,
) -> bool:
    """Remove a sighting's event link. Owner only."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE sighting_submissions SET event_id = NULL "
            "WHERE id = %s AND user_id = %s",
            (submission_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


# ── Helpers ──────────────────────────────────────────────────


def _get_member_role(
    event_id: str,
    user_id: int,
) -> str | None:
    """Get a user's role in an event, or None if not a member."""
    return fetch_scalar(
        "SELECT role FROM event_members WHERE event_id = %s AND user_id = %s",
        (event_id, user_id),
    )


# ── Comments ─────────────────────────────────────────────────


def add_event_comment(
    event_id: str,
    user_id: int,
    body: str,
) -> dict[str, Any] | None:
    """Add a comment to an event. Returns the comment dict."""
    # Verify event exists
    row = fetch_one(
        "SELECT id FROM community_events WHERE id = %s",
        (event_id,),
    )
    if not row:
        return None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event_comments (event_id, user_id, body)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (event_id, user_id, body),
        )
        comment_id = cur.fetchone()[0]
        conn.commit()

    return get_event_comment(comment_id)


def get_event_comment(comment_id: int) -> dict[str, Any] | None:
    """Fetch a single event comment by ID."""
    return fetch_one(
        """
        SELECT c.id, c.event_id::text, c.user_id,
               u.display_name, u.reputation_tier,
               u.avatar_filename,
               c.body, c.created_at, c.updated_at
        FROM event_comments c
        LEFT JOIN users u ON u.id = c.user_id
        WHERE c.id = %s
        """,
        (comment_id,),
    )


def list_event_comments(
    event_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List comments for an event, oldest first."""
    total = (
        fetch_scalar(
            "SELECT count(*) FROM event_comments WHERE event_id = %s",
            (event_id,),
        )
        or 0
    )
    rows = fetch_all(
        """
        SELECT c.id, c.event_id::text, c.user_id,
               u.display_name, u.reputation_tier,
               u.avatar_filename,
               c.body, c.created_at, c.updated_at
        FROM event_comments c
        LEFT JOIN users u ON u.id = c.user_id
        WHERE c.event_id = %s
        ORDER BY c.created_at ASC
        LIMIT %s OFFSET %s
        """,
        (event_id, limit, offset),
    )
    return rows, total


def update_event_comment(
    comment_id: int,
    user_id: int,
    body: str,
) -> dict[str, Any] | None:
    """Edit a comment. Author only."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE event_comments
            SET body = %s, updated_at = now()
            WHERE id = %s AND user_id = %s
            RETURNING id
            """,
            (body, comment_id, user_id),
        )
        row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    return get_event_comment(comment_id)


def delete_event_comment(comment_id: int, user_id: int) -> bool:
    """Delete a comment. Author only."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM event_comments WHERE id = %s AND user_id = %s RETURNING id",
            (comment_id, user_id),
        )
        row = cur.fetchone()
        conn.commit()
    return row is not None


# ── Cover photo ──────────────────────────────────────────────


def upload_event_cover(
    event_id: str,
    user_id: int,
    image_bytes: bytes,
    filename: str,
) -> str | None:
    """Save a cover photo for the event. Creator/organizer only.
    Returns the stored filename or None on auth failure."""
    role = _get_member_role(event_id, user_id)
    if role not in ("creator", "organizer"):
        return None

    ext = Path(filename).suffix.lower() or ".jpg"
    stored_name = f"cover{ext}"
    dest_dir = _COVER_ROOT / event_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Remove previous cover files
    if dest_dir.exists():
        for old in dest_dir.glob("cover.*"):
            old.unlink(missing_ok=True)

    (dest_dir / stored_name).write_bytes(image_bytes)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE community_events SET cover_filename = %s WHERE id = %s",
            (stored_name, event_id),
        )
        conn.commit()

    log.info(
        "Saved cover %s for event %s (%d bytes)",
        stored_name,
        event_id,
        len(image_bytes),
    )
    return stored_name


# ── Event summary stats ─────────────────────────────────────


def get_event_stats(event_id: str) -> dict[str, Any] | None:
    """Compute fun summary stats for an event's sightings."""
    # Verify event exists
    ev = fetch_one(
        "SELECT id FROM community_events WHERE id = %s",
        (event_id,),
    )
    if not ev:
        return None

    # Species breakdown (coalesce model_species → species_guess)
    species_rows = fetch_all(
        """
        SELECT coalesce(model_species, species_guess) AS species,
               count(*) AS cnt
        FROM sighting_submissions
        WHERE event_id = %s
          AND coalesce(model_species, species_guess) IS NOT NULL
        GROUP BY species
        ORDER BY cnt DESC
        """,
        (event_id,),
    )

    # Top contributors
    contributor_rows = fetch_all(
        """
        SELECT s.user_id, u.display_name, u.avatar_filename,
               u.reputation_tier, count(*) AS cnt
        FROM sighting_submissions s
        LEFT JOIN users u ON u.id = s.user_id
        WHERE s.event_id = %s AND s.user_id IS NOT NULL
        GROUP BY s.user_id, u.display_name,
                 u.avatar_filename, u.reputation_tier
        ORDER BY cnt DESC
        LIMIT 10
        """,
        (event_id,),
    )

    # Aggregate stats
    agg = fetch_one(
        """
        SELECT count(*) AS total,
               count(DISTINCT coalesce(model_species, species_guess))
                   FILTER (WHERE coalesce(
                       model_species, species_guess
                   ) IS NOT NULL) AS unique_species,
               count(DISTINCT user_id)
                   FILTER (WHERE user_id IS NOT NULL)
                   AS unique_contributors,
               count(*) FILTER (
                   WHERE verification_status = 'verified'
               ) AS verified_count,
               count(*) FILTER (
                   WHERE photo_filename IS NOT NULL
               ) AS has_photo,
               count(*) FILTER (
                   WHERE audio_filename IS NOT NULL
               ) AS has_audio,
               max(risk_score) AS max_risk,
               avg(risk_score) FILTER (
                   WHERE risk_score IS NOT NULL
               ) AS avg_risk,
               min(created_at) AS earliest,
               max(created_at) AS latest
        FROM sighting_submissions
        WHERE event_id = %s
        """,
        (event_id,),
    )

    # Interaction type breakdown
    interaction_rows = fetch_all(
        """
        SELECT interaction_type, count(*) AS cnt
        FROM sighting_submissions
        WHERE event_id = %s
          AND interaction_type IS NOT NULL
        GROUP BY interaction_type
        ORDER BY cnt DESC
        """,
        (event_id,),
    )

    # Highest risk category
    highest_cat = None
    if agg and agg.get("max_risk") is not None:
        cat_row = fetch_one(
            """
            SELECT risk_category FROM sighting_submissions
            WHERE event_id = %s AND risk_score = %s
            LIMIT 1
            """,
            (event_id, agg["max_risk"]),
        )
        if cat_row:
            highest_cat = cat_row.get("risk_category")

    a = agg or {}
    return {
        "total_sightings": a.get("total", 0),
        "unique_species": a.get("unique_species", 0),
        "species_breakdown": [
            {"species": r["species"], "count": r["cnt"]} for r in (species_rows or [])
        ],
        "unique_contributors": a.get("unique_contributors", 0),
        "top_contributors": [
            {
                "user_id": r["user_id"],
                "display_name": r["display_name"],
                "avatar_filename": r.get("avatar_filename"),
                "reputation_tier": r.get("reputation_tier"),
                "count": r["cnt"],
            }
            for r in (contributor_rows or [])
        ],
        "verified_count": a.get("verified_count", 0),
        "has_photo_count": a.get("has_photo", 0),
        "has_audio_count": a.get("has_audio", 0),
        "highest_risk_score": (
            float(a["max_risk"]) if a.get("max_risk") is not None else None
        ),
        "highest_risk_category": highest_cat,
        "avg_risk_score": (
            round(float(a["avg_risk"]), 4) if a.get("avg_risk") is not None else None
        ),
        "date_range_start": (a["earliest"].isoformat() if a.get("earliest") else None),
        "date_range_end": (a["latest"].isoformat() if a.get("latest") else None),
        "interaction_types": [
            {"type": r["interaction_type"], "count": r["cnt"]}
            for r in (interaction_rows or [])
        ],
    }


# ── Event photo gallery ─────────────────────────────────────

_GALLERY_ROOT = PROJECT_ROOT / "data/uploads/event_gallery"
_MAX_GALLERY_PHOTOS = 50  # per event


def list_gallery_photos(
    event_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Return gallery photos for an event, newest first."""
    total = fetch_scalar(
        "SELECT count(*) FROM event_gallery WHERE event_id = %s",
        (event_id,),
    )
    rows = fetch_all(
        """
        SELECT g.id, g.event_id, g.user_id, g.filename, g.caption,
               g.created_at, u.display_name, u.avatar_filename,
               u.reputation_tier
        FROM event_gallery g
        JOIN users u ON u.id = g.user_id
        WHERE g.event_id = %s
        ORDER BY g.created_at DESC
        LIMIT %s OFFSET %s
        """,
        (event_id, limit, offset),
    )
    photos = []
    for r in rows:
        photos.append(
            {
                "id": r["id"],
                "event_id": str(r["event_id"]),
                "user_id": r["user_id"],
                "url": f"/api/v1/events/{event_id}/gallery/{r['id']}",
                "caption": r["caption"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "uploader_name": r["display_name"],
                "uploader_avatar_url": (
                    f"/api/v1/media/avatar/{r['user_id']}"
                    if r.get("avatar_filename")
                    else None
                ),
                "uploader_tier": r.get("reputation_tier"),
            }
        )
    return photos, total or 0


def upload_gallery_photo(
    event_id: str,
    user_id: int,
    image_bytes: bytes,
    filename: str,
    caption: str | None = None,
) -> dict[str, Any] | None:
    """Save a gallery photo. Must be an event member.

    Returns the photo metadata dict, or None if not authorised.
    """
    role = _get_member_role(event_id, user_id)
    if not role:
        return None

    # Check photo count limit
    current = fetch_scalar(
        "SELECT count(*) FROM event_gallery WHERE event_id = %s",
        (event_id,),
    )
    if (current or 0) >= _MAX_GALLERY_PHOTOS:
        return {"error": "limit_reached"}

    import uuid as _uuid

    ext = Path(filename).suffix.lower() or ".jpg"
    stored_name = f"{_uuid.uuid4().hex[:12]}{ext}"
    dest_dir = _GALLERY_ROOT / event_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / stored_name).write_bytes(image_bytes)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event_gallery (event_id, user_id, filename, caption)
            VALUES (%s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (event_id, user_id, stored_name, caption),
        )
        row = cur.fetchone()
        conn.commit()

    log.info(
        "Gallery photo %s uploaded to event %s by user %d (%d bytes)",
        stored_name,
        event_id,
        user_id,
        len(image_bytes),
    )

    return {
        "id": row[0],
        "event_id": event_id,
        "user_id": user_id,
        "url": f"/api/v1/events/{event_id}/gallery/{row[0]}",
        "caption": caption,
        "created_at": row[1].isoformat() if row[1] else None,
    }


def get_gallery_photo_path(
    event_id: str,
    photo_id: int,
) -> Path | None:
    """Return the filesystem path for a gallery photo, or None."""
    row = fetch_one(
        "SELECT filename FROM event_gallery WHERE id = %s AND event_id = %s",
        (photo_id, event_id),
    )
    if not row:
        return None
    path = _GALLERY_ROOT / event_id / row["filename"]
    return path if path.exists() else None


def delete_gallery_photo(
    event_id: str,
    photo_id: int,
    user_id: int,
) -> bool:
    """Delete a gallery photo. Uploader, creator, or organizer only."""
    row = fetch_one(
        "SELECT user_id, filename FROM event_gallery WHERE id = %s AND event_id = %s",
        (photo_id, event_id),
    )
    if not row:
        return False

    role = _get_member_role(event_id, user_id)
    is_uploader = row["user_id"] == user_id
    is_admin = role in ("creator", "organizer")
    if not (is_uploader or is_admin):
        return False

    # Delete file
    path = _GALLERY_ROOT / event_id / row["filename"]
    path.unlink(missing_ok=True)

    # Delete DB row
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM event_gallery WHERE id = %s AND event_id = %s",
            (photo_id, event_id),
        )
        conn.commit()

    log.info(
        "Gallery photo %d deleted from event %s by user %d",
        photo_id,
        event_id,
        user_id,
    )
    return True

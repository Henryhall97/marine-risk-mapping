"""Vessel profile CRUD service."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.config import PROJECT_ROOT
from backend.services.database import fetch_all, fetch_one, get_conn

log = logging.getLogger(__name__)

# ── Column list (reused across queries) ──────────────────────

_VESSEL_COLS = (
    "id, user_id, vessel_name, vessel_type, description, "
    "length_m, beam_m, draft_m, hull_material, propulsion, "
    "typical_speed_knots, home_port, flag_state, "
    "registration_number, mmsi, imo, call_sign, "
    "profile_photo_filename, cover_photo_filename, "
    "is_active, created_at, updated_at"
)

_VESSEL_PHOTO_ROOT = PROJECT_ROOT / "data/uploads/vessel_photos"


# ── CRUD ─────────────────────────────────────────────────────


def list_vessels(user_id: int) -> list[dict[str, Any]]:
    """Return all vessels for a user, ordered by active first."""
    rows = fetch_all(
        f"SELECT {_VESSEL_COLS} FROM user_vessels "
        "WHERE user_id = %s "
        "ORDER BY is_active DESC, created_at DESC",
        (user_id,),
    )
    return rows or []


def get_vessel(vessel_id: int) -> dict[str, Any] | None:
    """Fetch a single vessel by ID."""
    return fetch_one(
        f"SELECT {_VESSEL_COLS} FROM user_vessels WHERE id = %s",
        (vessel_id,),
    )


def get_active_vessel(user_id: int) -> dict[str, Any] | None:
    """Fetch the currently active vessel for a user."""
    return fetch_one(
        f"SELECT {_VESSEL_COLS} FROM user_vessels "
        "WHERE user_id = %s AND is_active = TRUE",
        (user_id,),
    )


def create_vessel(user_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Create a new vessel profile. Makes it active if it's the first."""
    # Check if user has any vessels yet — first one becomes active
    existing = fetch_one(
        "SELECT count(*) AS cnt FROM user_vessels WHERE user_id = %s",
        (user_id,),
    )
    is_first = (existing or {}).get("cnt", 0) == 0

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_vessels (
                user_id, vessel_name, vessel_type, description,
                length_m, beam_m, draft_m,
                hull_material, propulsion, typical_speed_knots,
                home_port, flag_state, registration_number,
                mmsi, imo, call_sign,
                is_active
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s
            )
            RETURNING id
            """,
            (
                user_id,
                data["vessel_name"],
                data["vessel_type"],
                data.get("description"),
                data.get("length_m"),
                data.get("beam_m"),
                data.get("draft_m"),
                data.get("hull_material"),
                data.get("propulsion"),
                data.get("typical_speed_knots"),
                data.get("home_port"),
                data.get("flag_state"),
                data.get("registration_number"),
                data.get("mmsi"),
                data.get("imo"),
                data.get("call_sign"),
                is_first,
            ),
        )
        vessel_id = cur.fetchone()[0]
        # Also create owner crew row
        cur.execute(
            """
            INSERT INTO vessel_crew (vessel_id, user_id, role)
            VALUES (%s, %s, 'owner')
            ON CONFLICT (vessel_id, user_id) DO NOTHING
            """,
            (vessel_id, user_id),
        )
        conn.commit()

    return get_vessel(vessel_id)  # type: ignore[return-value]


def update_vessel(
    vessel_id: int, user_id: int, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Update a vessel profile. Returns None if not found / not owned."""
    existing = get_vessel(vessel_id)
    if not existing or existing["user_id"] != user_id:
        return None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE user_vessels SET
                vessel_name = %s,
                vessel_type = %s,
                description = %s,
                length_m = %s,
                beam_m = %s,
                draft_m = %s,
                hull_material = %s,
                propulsion = %s,
                typical_speed_knots = %s,
                home_port = %s,
                flag_state = %s,
                registration_number = %s,
                mmsi = %s,
                imo = %s,
                call_sign = %s,
                updated_at = now()
            WHERE id = %s AND user_id = %s
            """,
            (
                data["vessel_name"],
                data["vessel_type"],
                data.get("description"),
                data.get("length_m"),
                data.get("beam_m"),
                data.get("draft_m"),
                data.get("hull_material"),
                data.get("propulsion"),
                data.get("typical_speed_knots"),
                data.get("home_port"),
                data.get("flag_state"),
                data.get("registration_number"),
                data.get("mmsi"),
                data.get("imo"),
                data.get("call_sign"),
                vessel_id,
                user_id,
            ),
        )
        conn.commit()

    return get_vessel(vessel_id)


def delete_vessel(vessel_id: int, user_id: int) -> bool:
    """Delete a vessel. Returns True if deleted."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_vessels WHERE id = %s AND user_id = %s RETURNING id",
            (vessel_id, user_id),
        )
        deleted = cur.fetchone() is not None
        conn.commit()
    return deleted


def set_active_vessel(vessel_id: int, user_id: int) -> dict[str, Any] | None:
    """Set a vessel as the user's active vessel.

    Deactivates all other vessels first (partial unique index enforces
    at most one active per user).
    """
    existing = get_vessel(vessel_id)
    if not existing or existing["user_id"] != user_id:
        return None

    with get_conn() as conn, conn.cursor() as cur:
        # Deactivate all
        cur.execute(
            "UPDATE user_vessels SET is_active = FALSE WHERE user_id = %s",
            (user_id,),
        )
        # Activate the chosen one
        cur.execute(
            "UPDATE user_vessels SET is_active = TRUE WHERE id = %s AND user_id = %s",
            (vessel_id, user_id),
        )
        conn.commit()

    return get_vessel(vessel_id)


def clear_active_vessel(user_id: int) -> None:
    """Deactivate all vessels for a user (e.g. reporting from shore)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE user_vessels SET is_active = FALSE WHERE user_id = %s",
            (user_id,),
        )
        conn.commit()


def get_vessel_for_submission(vessel_id: int) -> dict[str, Any] | None:
    """Fetch minimal vessel info for embedding in sighting responses."""
    return fetch_one(
        "SELECT id, vessel_name, vessel_type, length_m FROM user_vessels WHERE id = %s",
        (vessel_id,),
    )


# ── Crew management ──────────────────────────────────────────


def list_crew(vessel_id: int) -> list[dict[str, Any]]:
    """List all crew members for a vessel."""
    return (
        fetch_all(
            """
        SELECT vc.id, vc.user_id, vc.role, vc.joined_at,
               u.display_name, u.reputation_tier,
               u.avatar_filename
        FROM vessel_crew vc
        JOIN users u ON u.id = vc.user_id
        WHERE vc.vessel_id = %s
        ORDER BY
            CASE vc.role
                WHEN 'owner' THEN 0
                WHEN 'crew' THEN 1
                ELSE 2
            END,
            vc.joined_at
        """,
            (vessel_id,),
        )
        or []
    )


def add_crew(
    vessel_id: int,
    target_user_id: int,
    role: str,
    invited_by: int,
) -> dict[str, Any] | None:
    """Add a user as crew. Returns the crew row or None on conflict."""
    if role == "owner":
        return None  # cannot assign owner via add_crew
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vessel_crew
                (vessel_id, user_id, role, invited_by)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (vessel_id, user_id) DO NOTHING
            RETURNING id
            """,
            (vessel_id, target_user_id, role, invited_by),
        )
        row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    # Return full crew member info
    return fetch_one(
        """
        SELECT vc.id, vc.user_id, vc.role, vc.joined_at,
               u.display_name, u.reputation_tier,
               u.avatar_filename
        FROM vessel_crew vc
        JOIN users u ON u.id = vc.user_id
        WHERE vc.id = %s
        """,
        (row[0],),
    )


def remove_crew(vessel_id: int, target_user_id: int, requesting_user_id: int) -> bool:
    """Remove a crew member. Owner can remove anyone; crew can self-remove."""
    # Check permissions: owner or self-removal
    owner = fetch_one(
        "SELECT user_id FROM vessel_crew WHERE vessel_id = %s AND role = 'owner'",
        (vessel_id,),
    )
    is_owner = owner and owner["user_id"] == requesting_user_id
    is_self = target_user_id == requesting_user_id

    if not (is_owner or is_self):
        return False

    # Prevent removing the owner
    target_role = fetch_one(
        "SELECT role FROM vessel_crew WHERE vessel_id = %s AND user_id = %s",
        (vessel_id, target_user_id),
    )
    if target_role and target_role["role"] == "owner":
        return False

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM vessel_crew "
            "WHERE vessel_id = %s AND user_id = %s "
            "RETURNING id",
            (vessel_id, target_user_id),
        )
        deleted = cur.fetchone() is not None
        conn.commit()
    return deleted


def update_crew_role(
    vessel_id: int,
    target_user_id: int,
    new_role: str,
) -> dict[str, Any] | None:
    """Update a crew member's role. Cannot change owner role."""
    if new_role == "owner":
        return None
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE vessel_crew SET role = %s
            WHERE vessel_id = %s AND user_id = %s
                AND role != 'owner'
            RETURNING id
            """,
            (new_role, vessel_id, target_user_id),
        )
        row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    return fetch_one(
        """
        SELECT vc.id, vc.user_id, vc.role, vc.joined_at,
               u.display_name, u.reputation_tier,
               u.avatar_filename
        FROM vessel_crew vc
        JOIN users u ON u.id = vc.user_id
        WHERE vc.id = %s
        """,
        (row[0],),
    )


def is_vessel_owner(vessel_id: int, user_id: int) -> bool:
    """Check if a user is the owner of a vessel."""
    row = fetch_one(
        "SELECT 1 FROM vessel_crew "
        "WHERE vessel_id = %s AND user_id = %s AND role = 'owner'",
        (vessel_id, user_id),
    )
    return row is not None


def is_vessel_member(vessel_id: int, user_id: int) -> bool:
    """Check if a user is any member (owner/crew/guest) of a vessel."""
    row = fetch_one(
        "SELECT 1 FROM vessel_crew WHERE vessel_id = %s AND user_id = %s",
        (vessel_id, user_id),
    )
    return row is not None


# ── Vessel stats & public profile ─────────────────────────────


def get_vessel_stats(vessel_id: int) -> dict[str, Any]:
    """Compute stats for a vessel's public profile."""
    row = fetch_one(
        """
        SELECT
            count(*)::int AS total_sightings,
            count(DISTINCT coalesce(
                s.model_species, s.species_guess
            ))::int AS species_documented,
            count(*) FILTER (
                WHERE s.verification_status IN (
                    'verified', 'community_verified'
                )
            )::int AS verified_sightings,
            min(s.created_at) AS first_sighting,
            max(s.created_at) AS last_sighting
        FROM sighting_submissions s
        WHERE s.vessel_id = %s
            AND s.is_public = TRUE
        """,
        (vessel_id,),
    )
    return (
        dict(row)
        if row
        else {
            "total_sightings": 0,
            "species_documented": 0,
            "verified_sightings": 0,
            "first_sighting": None,
            "last_sighting": None,
        }
    )


def get_vessel_public_profile(
    vessel_id: int,
) -> dict[str, Any] | None:
    """Fetch full public profile for a vessel: details + stats + crew."""
    vessel = get_vessel(vessel_id)
    if not vessel:
        return None

    stats = get_vessel_stats(vessel_id)
    crew = list_crew(vessel_id)

    # Find the owner from crew list
    owner = next((c for c in crew if c["role"] == "owner"), None)

    return {
        **vessel,
        "stats": stats,
        "crew": crew,
        "owner_name": owner["display_name"] if owner else None,
        "owner_id": owner["user_id"] if owner else vessel["user_id"],
        "owner_avatar_url": (
            f"/api/v1/media/avatar/{owner['user_id']}"
            if owner and owner.get("avatar_filename")
            else None
        ),
    }


# ── Vessel photo management ──────────────────────────────────


def upload_vessel_photo(
    vessel_id: int,
    photo_type: str,
    data: bytes,
    filename: str,
) -> str | None:
    """Save a vessel photo (profile or cover) to disk + update DB.

    Returns the stored filename, or None if vessel not found.
    """
    vessel = get_vessel(vessel_id)
    if not vessel:
        return None

    ext = Path(filename).suffix.lower() or ".jpg"
    stem = "profile" if photo_type == "profile" else "cover"
    stored_name = f"{stem}{ext}"

    folder = _VESSEL_PHOTO_ROOT / str(vessel_id)
    folder.mkdir(parents=True, exist_ok=True)

    # Remove old photo if exists
    for old in folder.glob(f"{stem}.*"):
        old.unlink(missing_ok=True)

    (folder / stored_name).write_bytes(data)

    col = (
        "profile_photo_filename" if photo_type == "profile" else "cover_photo_filename"
    )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE user_vessels SET {col} = %s, updated_at = now() WHERE id = %s",
            (stored_name, vessel_id),
        )
        conn.commit()

    log.info(
        "Saved vessel %s photo for vessel %d: %s",
        photo_type,
        vessel_id,
        stored_name,
    )
    return stored_name


# ── Boat leaderboard ─────────────────────────────────────────


def get_boat_leaderboard(limit: int = 10) -> list[dict[str, Any]]:
    """Top boats ranked by public submission count."""
    return (
        fetch_all(
            """
        SELECT
            v.id              AS vessel_id,
            v.vessel_name,
            v.vessel_type,
            v.profile_photo_filename,
            o_user.display_name AS owner_name,
            o_crew.user_id    AS owner_id,
            (SELECT count(*)::int
             FROM vessel_crew vc2
             WHERE vc2.vessel_id = v.id) AS crew_count,
            count(s.id)::int  AS submission_count,
            count(DISTINCT coalesce(
                s.model_species, s.species_guess
            ))::int           AS species_count
        FROM user_vessels v
        JOIN sighting_submissions s ON s.vessel_id = v.id
            AND s.is_public = TRUE
        LEFT JOIN vessel_crew o_crew
            ON o_crew.vessel_id = v.id AND o_crew.role = 'owner'
        LEFT JOIN users o_user
            ON o_user.id = o_crew.user_id
        GROUP BY v.id, v.vessel_name, v.vessel_type,
                 v.profile_photo_filename,
                 o_user.display_name, o_crew.user_id
        HAVING count(s.id) > 0
        ORDER BY count(s.id) DESC, v.vessel_name
        LIMIT %s
        """,
            (limit,),
        )
        or []
    )


# ── Vessels for a user (all vessels where they are crew) ──────


def list_user_boats(user_id: int) -> list[dict[str, Any]]:
    """Return all vessels where a user is a member (any role)."""
    return (
        fetch_all(
            f"""
        SELECT {_VESSEL_COLS}, vc.role AS crew_role
        FROM user_vessels v
        JOIN vessel_crew vc ON vc.vessel_id = v.id
        WHERE vc.user_id = %s
        ORDER BY vc.role = 'owner' DESC,
                 v.vessel_name
        """,
            (user_id,),
        )
        or []
    )

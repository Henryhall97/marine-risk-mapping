"""Sighting submissions service — persist + query user submissions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.config import PROJECT_ROOT
from backend.services import reputation as rep_svc
from backend.services.database import fetch_all, fetch_one, fetch_scalar, get_conn

log = logging.getLogger(__name__)

# Valid moderator statuses
VALID_MODERATOR_STATUSES = {"verified", "rejected"}

# Valid community vote types
VALID_VOTE_TYPES = {"agree", "disagree", "refine"}

# Media upload storage root
_UPLOAD_ROOT = PROJECT_ROOT / "data/uploads/submissions"


def _save_media_file(
    submission_id: str,
    filename: str,
    data: bytes,
    kind: str,
) -> str:
    """Write media bytes to disk. Returns the stored filename."""
    ext = Path(filename).suffix or (".jpg" if kind == "photo" else ".wav")
    stored_name = f"{kind}{ext}"
    dest_dir = _UPLOAD_ROOT / submission_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / stored_name).write_bytes(data)
    log.info(
        "Saved %s for submission %s (%d bytes)",
        stored_name,
        submission_id,
        len(data),
    )
    return stored_name


def save_submission(
    user_id: int | None,
    report: dict[str, Any],
    *,
    is_public: bool = False,
    image_bytes: bytes | None = None,
    image_filename: str | None = None,
    audio_bytes: bytes | None = None,
    audio_filename: str | None = None,
    vessel_id: int | None = None,
    privacy_level: str = "public",
) -> str:
    """Persist a sighting report result to the database.
    Returns the submission UUID."""
    loc = report.get("location", {}) or {}
    ui = report.get("user_input", {}) or {}
    photo = report.get("photo_classification", {}) or {}
    audio = report.get("audio_classification", {}) or {}
    assess = report.get("species_assessment", {}) or {}
    risk = report.get("risk_summary", {}) or {}
    adv = report.get("advisory", {}) or {}

    # Compute audio confidence from segment details
    audio_confidence = None
    if audio:
        segs = audio.get("segment_details", [])
        dominant = audio.get("dominant_species")
        if segs and dominant:
            confs = [
                s.get("confidence", 0.0)
                for s in segs
                if s.get("predicted_species") == dominant
            ]
            audio_confidence = max(confs) if confs else None

    # Resolve scientific_name + aphia_id from the crosswalk
    scientific_name = None
    aphia_id = None
    model_sp = assess.get("model_species")
    user_sp = ui.get("species_guess")
    best_sp = model_sp or user_sp
    if best_sp:
        try:
            from backend.services.species import resolve_species

            resolved = resolve_species(best_sp)
            if resolved:
                scientific_name = resolved["scientific_name"]
                aphia_id = resolved.get("aphia_id")
        except Exception:
            log.warning("Species resolution failed for %s", best_sp)

    # Taxonomic rank info from user's selection
    submitted_rank = ui.get("submitted_rank")
    submitted_scientific_name = ui.get("submitted_scientific_name")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
                INSERT INTO sighting_submissions (
                    user_id, lat, lon, h3_cell, gps_source,
                    species_guess, description, interaction_type,
                    photo_species, photo_confidence,
                    audio_species, audio_confidence,
                    model_species, model_confidence, model_source,
                    risk_score, risk_category,
                    advisory_level, advisory_message,
                    is_public,
                    photo_filename, audio_filename,
                    group_size,
                    sighting_datetime, scientific_name, aphia_id,
                    behavior, life_stage, calf_present,
                    sea_state_beaufort, observation_platform,
                    coordinate_uncertainty_m,
                    vessel_id,
                    submitted_rank, submitted_scientific_name,
                    confidence_level, group_size_min, group_size_max,
                    visibility_km, sea_glare,
                    distance_to_animal_m, direction_of_travel,
                    privacy_level
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s,
                    %s, %s,
                    %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s,
                    %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s
                )
                RETURNING id::text
                """,
            (
                user_id,
                loc.get("lat"),
                loc.get("lon"),
                loc.get("h3_cell"),
                loc.get("gps_source"),
                ui.get("species_guess"),
                ui.get("description"),
                ui.get("interaction_type"),
                photo.get("predicted_species"),
                photo.get("confidence"),
                audio.get("dominant_species"),
                audio_confidence,
                assess.get("model_species"),
                assess.get("model_confidence"),
                assess.get("source"),
                risk.get("risk_score"),
                risk.get("risk_category"),
                adv.get("level"),
                adv.get("message"),
                is_public,
                image_filename,
                audio_filename,
                ui.get("group_size"),
                ui.get("sighting_datetime"),
                scientific_name,
                aphia_id,
                ui.get("behavior"),
                ui.get("life_stage"),
                ui.get("calf_present"),
                ui.get("sea_state_beaufort"),
                ui.get("observation_platform"),
                ui.get("coordinate_uncertainty_m"),
                vessel_id,
                submitted_rank,
                submitted_scientific_name,
                ui.get("confidence_level"),
                ui.get("group_size_min"),
                ui.get("group_size_max"),
                ui.get("visibility_km"),
                ui.get("sea_glare"),
                ui.get("distance_to_animal_m"),
                ui.get("direction_of_travel"),
                privacy_level,
            ),
        )
        row = cur.fetchone()
        conn.commit()
    submission_id = row[0]

    # Save media files to disk keyed by submission ID
    if image_bytes and image_filename:
        try:
            stored = _save_media_file(
                submission_id, image_filename, image_bytes, "photo"
            )
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE sighting_submissions "
                    "SET photo_filename = %s WHERE id = %s::uuid",
                    (stored, submission_id),
                )
                conn.commit()
        except Exception:
            log.warning("Failed to save photo", exc_info=True)

    if audio_bytes and audio_filename:
        try:
            stored = _save_media_file(
                submission_id, audio_filename, audio_bytes, "audio"
            )
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE sighting_submissions "
                    "SET audio_filename = %s WHERE id = %s::uuid",
                    (stored, submission_id),
                )
                conn.commit()
        except Exception:
            log.warning("Failed to save audio", exc_info=True)

    # Award reputation for model agreement
    if user_id is not None:
        guess = ui.get("species_guess")
        model_sp = assess.get("model_species")
        if guess and model_sp and guess.lower() == model_sp.lower():
            try:
                rep_svc.award_model_agreement(user_id, submission_id)
            except Exception:
                log.warning("Failed to award model_agreement rep", exc_info=True)

    return submission_id


def get_user_submissions(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Get submissions for a specific user. Returns (rows, total)."""
    total = (
        fetch_scalar(
            "SELECT count(*) FROM sighting_submissions WHERE user_id = %s",
            (user_id,),
        )
        or 0
    )

    rows = fetch_all(
        """
        SELECT id::text, created_at, lat, lon,
               species_guess, model_species, model_confidence, model_source,
               interaction_type, risk_category, risk_score,
               is_public, verification_status, advisory_level,
               community_agree, community_disagree,
               moderator_status,
               (photo_filename IS NOT NULL) AS has_photo,
               (audio_filename IS NOT NULL) AS has_audio,
               group_size, behavior, life_stage, calf_present,
               sea_state_beaufort, observation_platform,
               scientific_name, sighting_datetime
        FROM sighting_submissions
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        (user_id, limit, offset),
    )
    return rows, total


def get_public_submissions(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    *,
    exclude_user_id: int | None = None,
    species: str | None = None,
    lat_min: float | None = None,
    lat_max: float | None = None,
    lon_min: float | None = None,
    lon_max: float | None = None,
    since: str | None = None,
    until: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Get public submissions for community verification."""
    where = "WHERE s.is_public = TRUE"
    params: list[Any] = []
    if status:
        where += " AND s.verification_status = %s"
        params.append(status)
    if exclude_user_id is not None:
        where += " AND (s.user_id IS NULL OR s.user_id != %s)"
        params.append(exclude_user_id)
    if species:
        where += " AND (s.model_species = %s OR s.species_guess = %s)"
        params.extend([species, species])
    if lat_min is not None and lat_max is not None:
        where += " AND s.lat BETWEEN %s AND %s"
        params.extend([lat_min, lat_max])
    if lon_min is not None and lon_max is not None:
        where += " AND s.lon BETWEEN %s AND %s"
        params.extend([lon_min, lon_max])
    if since:
        where += " AND s.created_at >= %s::date"
        params.append(since)
    if until:
        where += " AND s.created_at < (%s::date + 1)"
        params.append(until)

    count_q = f"SELECT count(*) FROM sighting_submissions s {where}"
    total = fetch_scalar(count_q, tuple(params)) or 0

    params.extend([limit, offset])
    rows = fetch_all(
        f"""
        SELECT s.id::text, s.created_at, s.lat, s.lon,
               s.species_guess, s.model_species, s.model_confidence,
               s.model_source, s.interaction_type,
               s.risk_category, s.risk_score,
               s.is_public, s.verification_status,
               s.community_agree, s.community_disagree,
               s.moderator_status,
               (s.photo_filename IS NOT NULL) AS has_photo,
               (s.audio_filename IS NOT NULL) AS has_audio,
               s.group_size, s.behavior, s.life_stage, s.calf_present,
               s.sea_state_beaufort, s.observation_platform,
               s.scientific_name, s.sighting_datetime,
               s.direction_of_travel,
               u.display_name AS submitter_name,
               s.user_id AS submitter_id,
               u.reputation_tier AS submitter_tier,
               u.avatar_filename AS submitter_avatar,
               u.is_moderator AS submitter_is_moderator
        FROM sighting_submissions s
        LEFT JOIN users u ON u.id = s.user_id
        {where}
        ORDER BY s.created_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )
    return rows, total


def get_map_sightings(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    species: str | None = None,
    status: str | None = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    """Lightweight spatial query for map marker display.

    Returns only the fields needed for map rendering: position,
    species, verification status, media flags, and timestamp.
    """
    where_parts = [
        "is_public = TRUE",
        "lat IS NOT NULL",
        "lon IS NOT NULL",
        "lat BETWEEN %s AND %s",
        "lon BETWEEN %s AND %s",
    ]
    params: list[Any] = [lat_min, lat_max, lon_min, lon_max]

    if species:
        where_parts.append("coalesce(model_species, species_guess) = %s")
        params.append(species)

    if status:
        where_parts.append("verification_status = %s")
        params.append(status)

    where = " AND ".join(where_parts)
    params.append(limit)

    return fetch_all(
        f"""
        SELECT id::text,
               lat, lon,
               coalesce(model_species, species_guess) AS species,
               species_guess,
               verification_status,
               community_agree,
               community_disagree,
               (photo_filename IS NOT NULL) AS has_photo,
               (audio_filename IS NOT NULL) AS has_audio,
               interaction_type,
               created_at
        FROM sighting_submissions
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT %s
        """,
        tuple(params),
    )


def get_submission_detail(submission_id: str) -> dict[str, Any] | None:
    """Get full details of a single submission."""
    return fetch_one(
        """
        SELECT s.id::text, s.created_at, s.lat, s.lon,
               s.h3_cell::text AS h3_cell,
               s.gps_source, s.species_guess, s.description,
               s.interaction_type, s.group_size,
               s.photo_species, s.photo_confidence,
               s.audio_species, s.audio_confidence,
               s.model_species, s.model_confidence, s.model_source,
               s.risk_score, s.risk_category,
               s.advisory_level, s.advisory_message,
               s.is_public, s.verification_status,
               s.verification_notes, s.verified_at,
               s.moderator_status, s.moderator_id,
               s.moderator_at, s.moderator_notes,
               s.community_agree, s.community_disagree,
               s.photo_filename, s.audio_filename,
               s.behavior, s.life_stage, s.calf_present,
               s.sea_state_beaufort, s.observation_platform,
               s.scientific_name, s.sighting_datetime,
               u.display_name AS submitter_name,
               s.user_id AS submitter_id,
               u.reputation_tier AS submitter_tier,
               u.avatar_filename AS submitter_avatar,
               u.is_moderator AS submitter_is_moderator
        FROM sighting_submissions s
        LEFT JOIN users u ON u.id = s.user_id
        WHERE s.id = %s::uuid
        """,
        (submission_id,),
    )


def _compute_verification_status(row: dict) -> str:
    """Derive the overall verification_status from moderator + votes.

    Priority:
    1. Moderator ruling is authoritative (verified / rejected).
    2. Otherwise derived from community vote counts:
       - agree > disagree by ≥2 → "community_verified"
       - disagree > agree by ≥2 → "disputed"
       - any votes but no clear margin → "under_review"
       - no votes and no moderator → "unverified"
    """
    mod = row.get("moderator_status")
    if mod == "verified":
        return "verified"
    if mod == "rejected":
        return "rejected"
    agree = row.get("community_agree", 0) or 0
    disagree = row.get("community_disagree", 0) or 0
    if agree == 0 and disagree == 0:
        return "unverified"
    if agree - disagree >= 2:
        return "community_verified"
    if disagree - agree >= 2:
        return "disputed"
    return "under_review"


# Reputation-tier vote weights — higher tiers count more.
_TIER_VOTE_WEIGHT: dict[str | None, float] = {
    "newcomer": 1.0,
    "observer": 1.5,
    "contributor": 2.0,
    "expert": 3.0,
    "authority": 4.0,
}


def _refresh_vote_counts(
    cur: Any,
    submission_id: str,
) -> tuple[int, int]:
    """Re-count reputation-weighted votes and update cached tallies.

    Each vote is weighted by the voter's reputation tier so that
    experienced contributors have a larger influence on consensus.
    Returns (weighted_agree, weighted_disagree) rounded to int.
    """
    cur.execute(
        """
        SELECT v.vote, u.reputation_tier
        FROM submission_votes v
        LEFT JOIN users u ON u.id = v.user_id
        WHERE v.submission_id = %s::uuid
        """,
        (submission_id,),
    )
    agree = 0.0
    disagree = 0.0
    for vote, tier in cur.fetchall():
        w = _TIER_VOTE_WEIGHT.get(tier, 1.0)
        if vote in ("agree", "refine"):
            agree += w
        else:
            disagree += w
    agree_int = round(agree)
    disagree_int = round(disagree)
    cur.execute(
        """
        UPDATE sighting_submissions
        SET community_agree = %s, community_disagree = %s
        WHERE id = %s::uuid
        """,
        (agree_int, disagree_int, submission_id),
    )
    return agree_int, disagree_int


def _update_derived_status(cur: Any, submission_id: str) -> str:
    """Recompute and persist verification_status from current state."""
    cur.execute(
        """
        SELECT moderator_status, community_agree, community_disagree
        FROM sighting_submissions
        WHERE id = %s::uuid
        """,
        (submission_id,),
    )
    row = cur.fetchone()
    if not row:
        return "unverified"
    status = _compute_verification_status(
        {
            "moderator_status": row[0],
            "community_agree": row[1],
            "community_disagree": row[2],
        }
    )
    cur.execute(
        "UPDATE sighting_submissions SET verification_status = %s WHERE id = %s::uuid",
        (status, submission_id),
    )
    return status


def moderator_verify(
    submission_id: str,
    moderator_id: int,
    status: str,
    notes: str | None,
) -> dict[str, Any] | None:
    """Moderator sets an authoritative verification status."""
    if status not in VALID_MODERATOR_STATUSES:
        raise ValueError(
            f"Invalid moderator status '{status}'. "
            f"Valid: {sorted(VALID_MODERATOR_STATUSES)}"
        )

    # Confirm the user is actually a moderator
    is_mod = fetch_scalar(
        "SELECT is_moderator FROM users WHERE id = %s",
        (moderator_id,),
    )
    if not is_mod:
        raise PermissionError("User is not a moderator")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sighting_submissions
            SET moderator_status = %s,
                moderator_id = %s,
                moderator_at = now(),
                moderator_notes = %s
            WHERE id = %s::uuid AND is_public = TRUE
            RETURNING id::text, user_id
            """,
            (status, moderator_id, notes, submission_id),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return None

        new_status = _update_derived_status(cur, submission_id)
        conn.commit()

    # Reputation effects
    try:
        rep_svc.award_verification_given(moderator_id, submission_id)
        submitter_id = row[1]
        if submitter_id:
            if new_status == "verified":
                rep_svc.award_sighting_verified(submitter_id, submission_id)
            elif new_status == "rejected":
                rep_svc.penalise_sighting_rejected(submitter_id, submission_id)
    except Exception:
        log.warning("Failed to update reputation", exc_info=True)

    return get_submission_detail(submission_id)


def community_vote(
    submission_id: str,
    voter_id: int,
    vote: str,
    notes: str | None = None,
    species_suggestion: str | None = None,
    suggested_rank: str | None = None,
) -> dict[str, Any] | None:
    """Cast or update a community vote (agree / disagree / refine).

    Returns the updated submission detail, or None if not found.
    Self-voting is prevented.
    """
    if vote not in VALID_VOTE_TYPES:
        raise ValueError(f"Invalid vote '{vote}'. Valid: {sorted(VALID_VOTE_TYPES)}")

    # Check submission exists + not self-vote
    sub = fetch_one(
        "SELECT user_id FROM sighting_submissions "
        "WHERE id = %s::uuid AND is_public = TRUE",
        (submission_id,),
    )
    if not sub:
        return None
    if sub["user_id"] == voter_id:
        raise ValueError("Cannot vote on your own submission")

    with get_conn() as conn, conn.cursor() as cur:
        # Upsert vote (one vote per user per submission)
        cur.execute(
            """
            INSERT INTO submission_votes
                (submission_id, user_id, vote, notes,
                 species_suggestion, suggested_rank)
            VALUES (%s::uuid, %s, %s, %s, %s, %s)
            ON CONFLICT (submission_id, user_id) DO UPDATE
            SET vote = EXCLUDED.vote,
                notes = EXCLUDED.notes,
                species_suggestion = EXCLUDED.species_suggestion,
                suggested_rank = EXCLUDED.suggested_rank,
                updated_at = now()
            """,
            (
                submission_id,
                voter_id,
                vote,
                notes,
                species_suggestion,
                suggested_rank,
            ),
        )

        _refresh_vote_counts(cur, submission_id)
        _update_derived_status(cur, submission_id)
        conn.commit()

    # Reputation: voter gets participation points
    try:
        rep_svc.award_verification_given(voter_id, submission_id)
    except Exception:
        log.warning("Failed to award vote rep", exc_info=True)

    return get_submission_detail(submission_id)


def get_submission_votes(
    submission_id: str,
) -> list[dict[str, Any]]:
    """Get all community votes for a submission."""
    return fetch_all(
        """
        SELECT v.id, v.user_id, v.vote, v.notes,
               v.species_suggestion, v.suggested_rank,
               v.created_at, v.updated_at,
               u.display_name, u.reputation_tier,
               u.is_moderator, u.avatar_filename
        FROM submission_votes v
        LEFT JOIN users u ON u.id = v.user_id
        WHERE v.submission_id = %s::uuid
        ORDER BY v.created_at ASC
        """,
        (submission_id,),
    )


def get_user_vote(
    submission_id: str,
    user_id: int,
) -> dict[str, Any] | None:
    """Get a specific user's vote on a submission."""
    return fetch_one(
        """
        SELECT v.id, v.vote, v.notes, v.species_suggestion,
               v.created_at, v.updated_at
        FROM submission_votes v
        WHERE v.submission_id = %s::uuid AND v.user_id = %s
        """,
        (submission_id, user_id),
    )


def verify_submission(
    submission_id: str,
    verifier_id: int,
    status: str,
    notes: str | None,
) -> dict[str, Any] | None:
    """Legacy compatibility wrapper — routes to moderator or community.

    Moderators calling with 'verified'/'rejected' → moderator_verify.
    Others calling with 'agree'/'disagree' → community_vote.
    Old 'disputed' → mapped to 'disagree'.
    """
    is_mod = fetch_scalar(
        "SELECT is_moderator FROM users WHERE id = %s",
        (verifier_id,),
    )

    if is_mod and status in VALID_MODERATOR_STATUSES:
        return moderator_verify(submission_id, verifier_id, status, notes)

    # Map old status names to new vote types
    vote_map = {
        "agree": "agree",
        "disagree": "disagree",
        "disputed": "disagree",
        "verified": "agree",
        "rejected": "disagree",
    }
    mapped_vote = vote_map.get(status)
    if not mapped_vote:
        raise ValueError(
            f"Invalid status '{status}'. Use 'agree' or 'disagree' for community votes."
        )

    return community_vote(submission_id, verifier_id, mapped_vote, notes)


def toggle_public(
    submission_id: str,
    user_id: int,
    is_public: bool,
) -> bool:
    """Toggle the public/private status of a user's own submission."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
                UPDATE sighting_submissions
                SET is_public = %s
                WHERE id = %s::uuid AND user_id = %s
                RETURNING id
                """,
            (is_public, submission_id, user_id),
        )
        row = cur.fetchone()
        conn.commit()
    return row is not None


def get_user_public_submissions(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Get a user's public submissions (for their public profile)."""
    total = (
        fetch_scalar(
            "SELECT count(*) FROM sighting_submissions "
            "WHERE user_id = %s AND is_public = TRUE",
            (user_id,),
        )
        or 0
    )
    rows = fetch_all(
        """
        SELECT s.id::text, s.created_at, s.lat, s.lon,
               s.species_guess, s.model_species, s.model_confidence,
               s.model_source, s.interaction_type,
               s.risk_category, s.risk_score,
               s.is_public, s.verification_status,
               s.community_agree, s.community_disagree,
               s.moderator_status,
               (s.photo_filename IS NOT NULL) AS has_photo,
               (s.audio_filename IS NOT NULL) AS has_audio,
               s.group_size, s.behavior, s.life_stage, s.calf_present,
               s.sea_state_beaufort, s.observation_platform,
               s.scientific_name, s.sighting_datetime,
               u.display_name AS submitter_name,
               s.user_id AS submitter_id,
               u.reputation_tier AS submitter_tier,
               u.avatar_filename AS submitter_avatar,
               u.is_moderator AS submitter_is_moderator
        FROM sighting_submissions s
        LEFT JOIN users u ON u.id = s.user_id
        WHERE s.user_id = %s AND s.is_public = TRUE
        ORDER BY s.created_at DESC
        LIMIT %s OFFSET %s
        """,
        (user_id, limit, offset),
    )
    return rows, total


# ── Submission comments ──────────────────────────────────────


def add_comment(
    submission_id: str,
    user_id: int,
    body: str,
) -> dict[str, Any] | None:
    """Add a comment to a public submission.

    Returns the new comment dict, or None if the submission is
    not found / not public.
    """
    # Verify submission exists and is public
    row = fetch_one(
        "SELECT id FROM sighting_submissions WHERE id = %s::uuid AND is_public = TRUE",
        (submission_id,),
    )
    if not row:
        return None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO submission_comments
                (submission_id, user_id, body)
            VALUES (%s::uuid, %s, %s)
            RETURNING id
            """,
            (submission_id, user_id, body),
        )
        comment_id = cur.fetchone()[0]
        conn.commit()

    return get_comment(comment_id)


def get_comment(comment_id: int) -> dict[str, Any] | None:
    """Fetch a single comment by ID."""
    return fetch_one(
        """
        SELECT c.id, c.submission_id::text, c.user_id,
               u.display_name, u.reputation_tier,
               u.avatar_filename,
               c.body, c.created_at, c.updated_at
        FROM submission_comments c
        LEFT JOIN users u ON u.id = c.user_id
        WHERE c.id = %s
        """,
        (comment_id,),
    )


def list_comments(
    submission_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List comments for a submission, oldest first."""
    total = (
        fetch_scalar(
            "SELECT count(*) FROM submission_comments WHERE submission_id = %s::uuid",
            (submission_id,),
        )
        or 0
    )
    rows = fetch_all(
        """
        SELECT c.id, c.submission_id::text, c.user_id,
               u.display_name, u.reputation_tier,
               u.avatar_filename,
               c.body, c.created_at, c.updated_at
        FROM submission_comments c
        LEFT JOIN users u ON u.id = c.user_id
        WHERE c.submission_id = %s::uuid
        ORDER BY c.created_at ASC
        LIMIT %s OFFSET %s
        """,
        (submission_id, limit, offset),
    )
    return rows, total


def update_comment(
    comment_id: int,
    user_id: int,
    body: str,
) -> dict[str, Any] | None:
    """Edit a comment. Only the author may edit."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE submission_comments
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
    return get_comment(comment_id)


def delete_comment(comment_id: int, user_id: int) -> bool:
    """Delete a comment. Only the author may delete."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM submission_comments "
            "WHERE id = %s AND user_id = %s RETURNING id",
            (comment_id, user_id),
        )
        row = cur.fetchone()
        conn.commit()
    return row is not None


# ── Community stats ──────────────────────────────────────


def get_community_stats() -> dict[str, Any]:
    """Aggregate community-wide statistics for the hero section."""
    stats = fetch_one(
        """
        SELECT
            count(*)::int                              AS total_sightings,
            count(DISTINCT user_id)::int               AS total_contributors,
            count(DISTINCT coalesce(
                model_species, species_guess
            ))::int                                    AS species_documented,
            count(*) FILTER (
                WHERE verification_status IN (
                    'verified', 'community_verified'
                )
            )::int                                     AS verified_count,
            count(*) FILTER (
                WHERE verification_status = 'unverified'
            )::int                                     AS needs_review_count,
            count(*) FILTER (
                WHERE photo_filename IS NOT NULL
            )::int                                     AS photo_count,
            count(*) FILTER (
                WHERE created_at >= now() - interval '7 days'
            )::int                                     AS sightings_this_week
        FROM sighting_submissions
        WHERE is_public = TRUE
        """,
    )
    # Event count from community_events
    event_count = fetch_scalar("SELECT count(*)::int FROM community_events") or 0
    result = (
        dict(stats)
        if stats
        else {
            "total_sightings": 0,
            "total_contributors": 0,
            "species_documented": 0,
            "verified_count": 0,
            "needs_review_count": 0,
            "photo_count": 0,
            "sightings_this_week": 0,
        }
    )
    result["total_events"] = event_count
    return result


def get_recent_activity(limit: int = 8) -> list[dict[str, Any]]:
    """Recent public submissions for the activity feed."""
    return fetch_all(
        """
        SELECT s.id::text,
               s.created_at,
               s.lat, s.lon,
               coalesce(s.model_species, s.species_guess)
                   AS species,
               s.interaction_type,
               s.verification_status,
               (s.photo_filename IS NOT NULL) AS has_photo,
               u.display_name AS submitter_name,
               s.user_id      AS submitter_id,
               u.reputation_tier AS submitter_tier,
               u.avatar_filename AS submitter_avatar
        FROM sighting_submissions s
        LEFT JOIN users u ON u.id = s.user_id
        WHERE s.is_public = TRUE
        ORDER BY s.created_at DESC
        LIMIT %s
        """,
        (limit,),
    )


def get_top_contributors(limit: int = 10) -> list[dict[str, Any]]:
    """Top contributors ranked by public submission count."""
    return fetch_all(
        """
        SELECT u.id              AS user_id,
               u.display_name,
               u.reputation_score,
               u.reputation_tier,
               u.avatar_filename,
               count(*)::int     AS submission_count,
               count(DISTINCT coalesce(
                   s.model_species, s.species_guess
               ))::int           AS species_count,
               min(s.created_at) AS first_submission,
               max(s.created_at) AS last_submission
        FROM sighting_submissions s
        JOIN users u ON u.id = s.user_id
        WHERE s.is_public = TRUE
        GROUP BY u.id, u.display_name,
                 u.reputation_score, u.reputation_tier,
                 u.avatar_filename
        ORDER BY count(*) DESC, u.reputation_score DESC
        LIMIT %s
        """,
        (limit,),
    )


def get_activity_histogram(days: int = 30) -> list[dict[str, Any]]:
    """Daily sighting counts for the past N days."""
    return fetch_all(
        """
        SELECT d::date AS date,
               coalesce(c.cnt, 0)::int AS count
        FROM generate_series(
            (current_date - %s * interval '1 day')::date,
            current_date,
            '1 day'
        ) AS d
        LEFT JOIN (
            SELECT created_at::date AS day,
                   count(*)::int    AS cnt
            FROM sighting_submissions
            WHERE is_public = TRUE
              AND created_at >= current_date - %s * interval '1 day'
            GROUP BY created_at::date
        ) c ON c.day = d::date
        ORDER BY d
        """,
        (days - 1, days),
    )


def get_whale_of_the_week() -> dict[str, Any] | None:
    """Most-engaged photo submission from the past 14 days.

    Ranks by (comment_count + vote_count), ties broken by
    community_agree then created_at DESC.
    """
    row = fetch_one(
        """
        SELECT s.id::text,
               s.created_at,
               s.lat, s.lon,
               coalesce(s.model_species, s.species_guess)
                   AS species,
               s.model_confidence,
               s.verification_status,
               s.community_agree,
               s.community_disagree,
               u.display_name AS submitter_name,
               s.user_id      AS submitter_id,
               u.reputation_tier AS submitter_tier,
               u.avatar_filename AS submitter_avatar,
               (SELECT count(*)::int
                FROM submission_comments sc
                WHERE sc.submission_id = s.id) AS comment_count,
               (s.community_agree + s.community_disagree)
                   AS vote_count
        FROM sighting_submissions s
        LEFT JOIN users u ON u.id = s.user_id
        WHERE s.is_public = TRUE
          AND s.photo_filename IS NOT NULL
          AND s.created_at >= now() - interval '14 days'
        ORDER BY (
            (SELECT count(*) FROM submission_comments sc
             WHERE sc.submission_id = s.id)
            + s.community_agree + s.community_disagree
        ) DESC,
        s.community_agree DESC,
        s.created_at DESC
        LIMIT 1
        """,
    )
    if not row:
        return None
    # Fetch top comments for this submission
    comments = fetch_all(
        """
        SELECT c.id, c.body, c.created_at,
               u.display_name,
               u.reputation_tier,
               u.avatar_filename,
               c.user_id
        FROM submission_comments c
        LEFT JOIN users u ON u.id = c.user_id
        WHERE c.submission_id = %s::uuid
        ORDER BY c.created_at DESC
        LIMIT 5
        """,
        (row["id"],),
    )
    result = dict(row)
    result["top_comments"] = [_comment_to_dict(c) for c in comments]
    return result


def _comment_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a comment row to a frontend-friendly dict."""
    d = dict(row)
    avatar = d.pop("avatar_filename", None)
    uid = d.get("user_id")
    d["avatar_url"] = f"/api/v1/media/avatar/{uid}" if avatar and uid else None
    return d

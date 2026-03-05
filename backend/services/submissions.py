"""Sighting submissions service — persist + query user submissions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.services import reputation as rep_svc
from backend.services.database import fetch_all, fetch_one, fetch_scalar, get_conn

log = logging.getLogger(__name__)

# Valid verification statuses
VALID_VERIFICATION_STATUSES = {"verified", "rejected", "disputed"}

# Media upload storage root
_UPLOAD_ROOT = Path("data/uploads/submissions")


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
                    photo_filename, audio_filename
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s,
                    %s, %s
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
               (photo_filename IS NOT NULL) AS has_photo,
               (audio_filename IS NOT NULL) AS has_audio
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
) -> tuple[list[dict[str, Any]], int]:
    """Get public submissions for community verification."""
    where = "WHERE s.is_public = TRUE"
    params: list[Any] = []
    if status:
        where += " AND s.verification_status = %s"
        params.append(status)

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
               (s.photo_filename IS NOT NULL) AS has_photo,
               (s.audio_filename IS NOT NULL) AS has_audio,
               u.display_name AS submitter_name,
               s.user_id AS submitter_id,
               u.reputation_tier AS submitter_tier,
               u.avatar_filename AS submitter_avatar
        FROM sighting_submissions s
        LEFT JOIN users u ON u.id = s.user_id
        {where}
        ORDER BY s.created_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )
    return rows, total


def get_submission_detail(submission_id: str) -> dict[str, Any] | None:
    """Get full details of a single submission."""
    return fetch_one(
        """
        SELECT s.id::text, s.created_at, s.lat, s.lon, s.h3_cell,
               s.gps_source, s.species_guess, s.description,
               s.interaction_type,
               s.photo_species, s.photo_confidence,
               s.audio_species, s.audio_confidence,
               s.model_species, s.model_confidence, s.model_source,
               s.risk_score, s.risk_category,
               s.advisory_level, s.advisory_message,
               s.is_public, s.verification_status,
               s.verification_notes, s.verified_at,
               s.photo_filename, s.audio_filename,
               u.display_name AS submitter_name,
               s.user_id AS submitter_id,
               u.reputation_tier AS submitter_tier,
               u.avatar_filename AS submitter_avatar
        FROM sighting_submissions s
        LEFT JOIN users u ON u.id = s.user_id
        WHERE s.id = %s::uuid
        """,
        (submission_id,),
    )


def verify_submission(
    submission_id: str,
    verifier_id: int,
    status: str,
    notes: str | None,
) -> dict[str, Any] | None:
    """Update verification status of a public submission."""
    if status not in VALID_VERIFICATION_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Valid: {sorted(VALID_VERIFICATION_STATUSES)}"
        )

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
                UPDATE sighting_submissions
                SET verification_status = %s,
                    verified_by = %s,
                    verified_at = now(),
                    verification_notes = %s
                WHERE id = %s::uuid AND is_public = TRUE
                RETURNING id::text, user_id
                """,
            (status, verifier_id, notes, submission_id),
        )
        row = cur.fetchone()
        conn.commit()

    if not row:
        return None

    # Award / penalise reputation
    try:
        # Verifier gets points for participating
        rep_svc.award_verification_given(verifier_id, submission_id)
        # Submitter gets points/penalty based on outcome
        submitter_id = row[1]
        if submitter_id:
            if status == "verified":
                rep_svc.award_sighting_verified(submitter_id, submission_id)
            elif status == "rejected":
                rep_svc.penalise_sighting_rejected(submitter_id, submission_id)
            elif status == "disputed":
                rep_svc.penalise_sighting_disputed(submitter_id, submission_id)
    except Exception:
        log.warning("Failed to update reputation", exc_info=True)

    return get_submission_detail(submission_id)


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
               (s.photo_filename IS NOT NULL) AS has_photo,
               (s.audio_filename IS NOT NULL) AS has_audio,
               u.display_name AS submitter_name,
               s.user_id AS submitter_id,
               u.reputation_tier AS submitter_tier,
               u.avatar_filename AS submitter_avatar
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

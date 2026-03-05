"""Reputation service — scoring, tiers, credentials, event logging.

Points system
─────────────
  +10  sighting verified by community
  +5   sighting matches ML model prediction (auto-awarded on submit)
  +3   verification you gave reaches consensus (others agree)
  +2   providing a community verification vote
  +20  credential verified by admin
  −5   sighting rejected by community
  −2   sighting disputed

Tiers
─────
  Newcomer     0–49
  Observer     50–199
  Contributor  200–499
  Expert       500–999
  Authority    1000+
"""

from __future__ import annotations

import logging
from typing import Any

from backend.services.database import fetch_all, fetch_one, fetch_scalar, get_conn

log = logging.getLogger(__name__)

# ── Point values ─────────────────────────────────────────────

POINTS = {
    "sighting_verified": 10,
    "model_agreement": 5,
    "verification_consensus": 3,
    "verification_given": 2,
    "credential_verified": 20,
    "sighting_rejected": -5,
    "sighting_disputed": -2,
}

# ── Tier thresholds (inclusive lower bound) ──────────────────

TIERS = [
    (1000, "authority"),
    (500, "expert"),
    (200, "contributor"),
    (50, "observer"),
    (0, "newcomer"),
]


def _tier_for_score(score: int) -> str:
    """Determine reputation tier from raw score."""
    for threshold, tier in TIERS:
        if score >= threshold:
            return tier
    return "newcomer"


# ── Event logging ────────────────────────────────────────────


def _log_event(
    user_id: int,
    event_type: str,
    points: int,
    submission_id: str | None = None,
    description: str | None = None,
) -> None:
    """Insert a reputation event and update the user's aggregate score."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO reputation_events
                (user_id, event_type, points, submission_id, description)
            VALUES (%s, %s, %s, %s::uuid, %s)
            """,
            (user_id, event_type, points, submission_id, description),
        )
        # Update aggregate — floor at 0
        cur.execute(
            """
            UPDATE users
            SET reputation_score = GREATEST(0, reputation_score + %s),
                reputation_tier = CASE
                    WHEN GREATEST(0, reputation_score + %s) >= 1000 THEN 'authority'
                    WHEN GREATEST(0, reputation_score + %s) >= 500  THEN 'expert'
                    WHEN GREATEST(0, reputation_score + %s) >= 200  THEN 'contributor'
                    WHEN GREATEST(0, reputation_score + %s) >= 50   THEN 'observer'
                    ELSE 'newcomer'
                END
            WHERE id = %s
            """,
            (points, points, points, points, points, user_id),
        )
        conn.commit()


# ── Public API ───────────────────────────────────────────────


def award_model_agreement(user_id: int, submission_id: str) -> None:
    """Award points when user's species guess matches ML prediction."""
    pts = POINTS["model_agreement"]
    _log_event(
        user_id,
        "model_agreement",
        pts,
        submission_id,
        "Species guess matched ML model prediction",
    )
    log.info(
        "Awarded %+d rep to user %d (model_agreement, sub=%s)",
        pts,
        user_id,
        submission_id,
    )


def award_sighting_verified(user_id: int, submission_id: str) -> None:
    """Award points when a user's sighting is verified by community."""
    pts = POINTS["sighting_verified"]
    _log_event(
        user_id,
        "sighting_verified",
        pts,
        submission_id,
        "Sighting verified by community",
    )
    log.info(
        "Awarded %+d rep to user %d (sighting_verified, sub=%s)",
        pts,
        user_id,
        submission_id,
    )


def penalise_sighting_rejected(user_id: int, submission_id: str) -> None:
    """Deduct points when a user's sighting is rejected."""
    pts = POINTS["sighting_rejected"]
    _log_event(
        user_id,
        "sighting_rejected",
        pts,
        submission_id,
        "Sighting rejected by community",
    )


def penalise_sighting_disputed(user_id: int, submission_id: str) -> None:
    """Deduct points when a user's sighting is disputed."""
    pts = POINTS["sighting_disputed"]
    _log_event(
        user_id,
        "sighting_disputed",
        pts,
        submission_id,
        "Sighting disputed by community",
    )


def award_verification_given(verifier_id: int, submission_id: str) -> None:
    """Award points to a user for providing a verification vote."""
    pts = POINTS["verification_given"]
    _log_event(
        verifier_id,
        "verification_given",
        pts,
        submission_id,
        "Provided community verification",
    )


def award_credential_verified(user_id: int, credential_id: int) -> None:
    """Award points when a user's credential is verified."""
    pts = POINTS["credential_verified"]
    _log_event(
        user_id,
        "credential_verified",
        pts,
        description=f"Credential #{credential_id} verified",
    )


# ── Queries ──────────────────────────────────────────────────


def get_reputation(user_id: int) -> dict[str, Any]:
    """Get a user's reputation summary."""
    row = fetch_one(
        "SELECT reputation_score, reputation_tier FROM users WHERE id = %s",
        (user_id,),
    )
    if not row:
        return {"score": 0, "tier": "newcomer"}
    return {"score": row["reputation_score"], "tier": row["reputation_tier"]}


def get_reputation_history(
    user_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    """Get paginated reputation event history."""
    total = (
        fetch_scalar(
            "SELECT count(*) FROM reputation_events WHERE user_id = %s",
            (user_id,),
        )
        or 0
    )
    rows = fetch_all(
        """
        SELECT id, event_type, points, submission_id::text,
               description, created_at
        FROM reputation_events
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        (user_id, limit, offset),
    )
    return rows, total


# ── Credentials ──────────────────────────────────────────────

VALID_CREDENTIAL_TYPES = {
    "marine_biologist",
    "certified_observer",
    "noaa_affiliate",
    "research_institution",
    "vessel_operator",
    "coast_guard",
    "other",
}


def add_credential(
    user_id: int, credential_type: str, description: str
) -> dict[str, Any]:
    """Add a credential claim to a user's profile."""
    if credential_type not in VALID_CREDENTIAL_TYPES:
        raise ValueError(
            f"Invalid credential type '{credential_type}'. "
            f"Valid: {sorted(VALID_CREDENTIAL_TYPES)}"
        )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_credentials (user_id, credential_type, description)
            VALUES (%s, %s, %s)
            RETURNING id, credential_type, description,
                      is_verified, verified_at, created_at
            """,
            (user_id, credential_type, description),
        )
        row = cur.fetchone()
        conn.commit()
    return {
        "id": row[0],
        "credential_type": row[1],
        "description": row[2],
        "is_verified": row[3],
        "verified_at": row[4],
        "created_at": row[5],
    }


def get_user_credentials(user_id: int) -> list[dict[str, Any]]:
    """Get all credentials for a user."""
    return fetch_all(
        """
        SELECT id, credential_type, description,
               is_verified, verified_at, created_at
        FROM user_credentials
        WHERE user_id = %s
        ORDER BY created_at DESC
        """,
        (user_id,),
    )


def verify_credential(credential_id: int) -> dict[str, Any] | None:
    """Mark a credential as verified (admin action)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE user_credentials
            SET is_verified = TRUE, verified_at = now()
            WHERE id = %s
            RETURNING user_id
            """,
            (credential_id,),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return None
        conn.commit()

    # Award reputation points
    award_credential_verified(row[0], credential_id)
    return fetch_one(
        "SELECT id, credential_type, description, "
        "is_verified, verified_at FROM user_credentials WHERE id = %s",
        (credential_id,),
    )

"""Authentication service — user registration, login, JWT tokens."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from backend.services import reputation as rep_svc
from backend.services.database import fetch_all, fetch_one, fetch_scalar, get_conn

log = logging.getLogger(__name__)

# JWT config — override via environment variables in production
JWT_SECRET = os.environ.get("MR_JWT_SECRET", "marine-risk-dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.environ.get("MR_JWT_EXPIRY_HOURS", "24"))


# ── Avatar URL helper ────────────────────────────────────────


def _avatar_url(user_id: int, filename: str | None) -> str | None:
    """Build the public avatar URL from a stored filename."""
    if not filename:
        return None
    return f"/api/v1/media/avatar/{user_id}"


# ── Password hashing ────────────────────────────────────────


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT tokens ───────────────────────────────────────────────


def create_token(user_id: int, email: str) -> str:
    """Create a signed JWT access token."""
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ── User CRUD ────────────────────────────────────────────────


def register_user(email: str, display_name: str, password: str) -> dict[str, Any]:
    """Register a new user. Returns the user dict. Raises ValueError
    if email already exists."""
    existing = fetch_one("SELECT id FROM users WHERE email = %s", (email,))
    if existing:
        raise ValueError("Email already registered")

    pw_hash = hash_password(password)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
                INSERT INTO users (email, display_name, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, email, display_name, created_at
                """,
            (email, display_name, pw_hash),
        )
        row = cur.fetchone()
        conn.commit()

    return {
        "id": row[0],
        "email": row[1],
        "display_name": row[2],
        "created_at": row[3],
        "avatar_url": None,
        "submission_count": 0,
    }


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    """Verify credentials. Returns user dict or None."""
    row = fetch_one(
        "SELECT id, email, display_name, password_hash, created_at, "
        "reputation_score, reputation_tier, avatar_filename "
        "FROM users WHERE email = %s AND is_active = TRUE",
        (email,),
    )
    if not row:
        return None
    if not verify_password(password, row["password_hash"]):
        return None

    sub_count = (
        fetch_scalar(
            "SELECT count(*) FROM sighting_submissions WHERE user_id = %s",
            (row["id"],),
        )
        or 0
    )

    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "avatar_url": _avatar_url(row["id"], row["avatar_filename"]),
        "created_at": row["created_at"],
        "submission_count": sub_count,
        "reputation_score": row["reputation_score"],
        "reputation_tier": row["reputation_tier"],
        "credentials": rep_svc.get_user_credentials(row["id"]),
    }


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """Fetch user profile by ID."""
    row = fetch_one(
        "SELECT id, email, display_name, created_at, "
        "reputation_score, reputation_tier, avatar_filename "
        "FROM users WHERE id = %s AND is_active = TRUE",
        (user_id,),
    )
    if not row:
        return None

    sub_count = (
        fetch_scalar(
            "SELECT count(*) FROM sighting_submissions WHERE user_id = %s",
            (user_id,),
        )
        or 0
    )
    row["submission_count"] = sub_count
    row["avatar_url"] = _avatar_url(user_id, row.pop("avatar_filename", None))
    row["credentials"] = rep_svc.get_user_credentials(user_id)
    return row


def get_public_profile(user_id: int) -> dict[str, Any] | None:
    """Fetch a public profile (no email) for another user."""
    row = fetch_one(
        "SELECT id, display_name, created_at, "
        "reputation_score, reputation_tier, avatar_filename "
        "FROM users WHERE id = %s AND is_active = TRUE",
        (user_id,),
    )
    if not row:
        return None

    row["avatar_url"] = _avatar_url(user_id, row.pop("avatar_filename", None))

    sub_count = (
        fetch_scalar(
            "SELECT count(*) FROM sighting_submissions "
            "WHERE user_id = %s AND is_public = TRUE",
            (user_id,),
        )
        or 0
    )
    verified_count = (
        fetch_scalar(
            "SELECT count(*) FROM sighting_submissions "
            "WHERE user_id = %s AND verification_status = 'verified'",
            (user_id,),
        )
        or 0
    )

    # Species breakdown
    species_rows = fetch_all(
        """
        SELECT COALESCE(model_species, species_guess, 'unknown') AS species,
               count(*) AS count
        FROM sighting_submissions
        WHERE user_id = %s AND is_public = TRUE
        GROUP BY species
        ORDER BY count DESC
        LIMIT 10
        """,
        (user_id,),
    )

    row["submission_count"] = sub_count
    row["verified_count"] = verified_count
    row["species_breakdown"] = species_rows
    row["credentials"] = rep_svc.get_user_credentials(user_id)
    return row


# ── Avatar update ─────────────────────────────────────────────


def update_avatar(user_id: int, filename: str | None) -> None:
    """Set or clear the avatar_filename for a user."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET avatar_filename = %s WHERE id = %s",
            (filename, user_id),
        )
        conn.commit()


# ── Token extraction helper ──────────────────────────────────


def get_current_user_id(authorization: str | None) -> int | None:
    """Extract user_id from an Authorization header, or return None."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    try:
        payload = decode_token(parts[1])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None

"""Database migrations for user accounts and sighting submissions.

Run from project root::

    uv run python backend/migrations.py
"""

from __future__ import annotations

import logging

import psycopg2

from pipeline.config import DB_CONFIG

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

MIGRATIONS = [
    # ── Users table ──────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS users (
        id              SERIAL PRIMARY KEY,
        email           VARCHAR(255) NOT NULL UNIQUE,
        display_name    VARCHAR(100) NOT NULL,
        password_hash   VARCHAR(255) NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        is_active       BOOLEAN NOT NULL DEFAULT TRUE
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_users_email
        ON users (email);
    """,
    # ── Sighting submissions ─────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS sighting_submissions (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

        -- Location
        lat             DOUBLE PRECISION,
        lon             DOUBLE PRECISION,
        h3_cell         BIGINT,
        gps_source      VARCHAR(20),

        -- User input
        species_guess   VARCHAR(50),
        description     TEXT,
        interaction_type VARCHAR(30),

        -- Model results
        photo_species   VARCHAR(50),
        photo_confidence DOUBLE PRECISION,
        audio_species   VARCHAR(50),
        audio_confidence DOUBLE PRECISION,
        model_species   VARCHAR(50),
        model_confidence DOUBLE PRECISION,
        model_source    VARCHAR(20),

        -- Risk context
        risk_score      DOUBLE PRECISION,
        risk_category   VARCHAR(20),

        -- Advisory
        advisory_level  VARCHAR(20),
        advisory_message TEXT,

        -- Public verification
        is_public       BOOLEAN NOT NULL DEFAULT FALSE,
        verification_status VARCHAR(20) NOT NULL DEFAULT 'unverified',
        verified_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
        verified_at     TIMESTAMPTZ,
        verification_notes TEXT
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_submissions_user
        ON sighting_submissions (user_id, created_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_submissions_public
        ON sighting_submissions (is_public, created_at DESC)
        WHERE is_public = TRUE;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_submissions_verification
        ON sighting_submissions (verification_status)
        WHERE is_public = TRUE;
    """,
    # ── Media file columns (stored on disk) ──────────────────
    """
    ALTER TABLE sighting_submissions
        ADD COLUMN IF NOT EXISTS photo_filename VARCHAR(255),
        ADD COLUMN IF NOT EXISTS audio_filename VARCHAR(255);
    """,
    # ── Reputation system (v2) ───────────────────────────────
    # Add reputation columns to users
    """
    ALTER TABLE users
        ADD COLUMN IF NOT EXISTS reputation_score
            INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS reputation_tier
            VARCHAR(20) NOT NULL DEFAULT 'newcomer';
    """,
    # Reputation event log — immutable audit trail
    """
    CREATE TABLE IF NOT EXISTS reputation_events (
        id          SERIAL PRIMARY KEY,
        user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        event_type  VARCHAR(40) NOT NULL,
        points      INTEGER NOT NULL,
        submission_id UUID REFERENCES sighting_submissions(id) ON DELETE SET NULL,
        description TEXT,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_rep_events_user
        ON reputation_events (user_id, created_at DESC);
    """,
    # User credentials — qualifications that boost trust
    """
    CREATE TABLE IF NOT EXISTS user_credentials (
        id              SERIAL PRIMARY KEY,
        user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        credential_type VARCHAR(40) NOT NULL,
        description     TEXT NOT NULL,
        is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
        verified_at     TIMESTAMPTZ,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_credentials_user
        ON user_credentials (user_id);
    """,
    # ── Submission comments ──────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS submission_comments (
        id              SERIAL PRIMARY KEY,
        submission_id   UUID NOT NULL
            REFERENCES sighting_submissions(id) ON DELETE CASCADE,
        user_id         INTEGER NOT NULL
            REFERENCES users(id) ON DELETE CASCADE,
        body            TEXT NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_comments_submission
        ON submission_comments (submission_id, created_at ASC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_comments_user
        ON submission_comments (user_id, created_at DESC);
    """,
    # ── User avatar ──────────────────────────────────────────
    """
    ALTER TABLE users
        ADD COLUMN IF NOT EXISTS avatar_filename VARCHAR(255);
    """,
]


def run_migrations() -> None:
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            for i, sql in enumerate(MIGRATIONS, 1):
                log.info("Running migration %d/%d …", i, len(MIGRATIONS))
                cur.execute(sql)
            conn.commit()
        log.info("All %d migrations applied successfully.", len(MIGRATIONS))
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()

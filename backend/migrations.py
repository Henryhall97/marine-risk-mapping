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
    # ── Moderator role flag ───────────────────────────────────
    """
    ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_moderator
            BOOLEAN NOT NULL DEFAULT FALSE;
    """,
    # ── Community votes table (replaces last-write-wins) ──────
    """
    CREATE TABLE IF NOT EXISTS submission_votes (
        id              SERIAL PRIMARY KEY,
        submission_id   UUID NOT NULL
            REFERENCES sighting_submissions(id) ON DELETE CASCADE,
        user_id         INTEGER NOT NULL
            REFERENCES users(id) ON DELETE CASCADE,
        vote            VARCHAR(10) NOT NULL
            CHECK (vote IN ('agree', 'disagree')),
        species_suggestion VARCHAR(50),
        notes           TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ,
        UNIQUE (submission_id, user_id)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_votes_submission
        ON submission_votes (submission_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_votes_user
        ON submission_votes (user_id, created_at DESC);
    """,
    # ── Moderator verification columns on submissions ─────────
    """
    ALTER TABLE sighting_submissions
        ADD COLUMN IF NOT EXISTS moderator_status VARCHAR(20),
        ADD COLUMN IF NOT EXISTS moderator_id
            INTEGER REFERENCES users(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS moderator_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS moderator_notes TEXT;
    """,
    # ── Community vote tallies (cached on submission) ─────────
    """
    ALTER TABLE sighting_submissions
        ADD COLUMN IF NOT EXISTS community_agree
            INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS community_disagree
            INTEGER NOT NULL DEFAULT 0;
    """,
    # ── User bio / profile summary ────────────────────────────
    """
    ALTER TABLE users
        ADD COLUMN IF NOT EXISTS bio TEXT;
    """,
    # ── Vessel violation reports ──────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS vessel_violation_reports (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

        -- Location
        lat             DOUBLE PRECISION NOT NULL,
        lon             DOUBLE PRECISION NOT NULL,
        h3_cell         BIGINT,

        -- Violation details
        violation_type  VARCHAR(40) NOT NULL,
        vessel_name     VARCHAR(200),
        vessel_type     VARCHAR(60),
        vessel_length_estimate VARCHAR(40),
        heading         VARCHAR(20),
        estimated_speed_knots DOUBLE PRECISION,
        description     TEXT,

        -- Evidence
        photo_filename  VARCHAR(255),
        observed_at     TIMESTAMPTZ,

        -- Context (auto-enriched)
        zone_name       VARCHAR(200),
        zone_type       VARCHAR(60),
        risk_score      DOUBLE PRECISION,
        risk_category   VARCHAR(20),

        -- Moderation
        is_public       BOOLEAN NOT NULL DEFAULT FALSE,
        review_status   VARCHAR(20) NOT NULL DEFAULT 'pending',
        reviewed_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
        reviewed_at     TIMESTAMPTZ,
        review_notes    TEXT,

        -- Tallies
        community_confirm  INTEGER NOT NULL DEFAULT 0,
        community_dispute  INTEGER NOT NULL DEFAULT 0
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_violations_user
        ON vessel_violation_reports (user_id, created_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_violations_public
        ON vessel_violation_reports (is_public, created_at DESC)
        WHERE is_public = TRUE;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_violations_status
        ON vessel_violation_reports (review_status);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_violations_type
        ON vessel_violation_reports (violation_type);
    """,
    # ── Community events ─────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS community_events (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        creator_id      INTEGER NOT NULL
            REFERENCES users(id) ON DELETE CASCADE,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ,

        -- Core fields
        title           VARCHAR(200) NOT NULL,
        description     TEXT,
        event_type      VARCHAR(40) NOT NULL
            DEFAULT 'whale_watching',
        status          VARCHAR(20) NOT NULL
            DEFAULT 'upcoming',

        -- Schedule
        start_date      DATE,
        end_date        DATE,

        -- Location (optional centre point for map display)
        lat             DOUBLE PRECISION,
        lon             DOUBLE PRECISION,
        location_name   VARCHAR(200),

        -- Sharing
        invite_code     VARCHAR(12) NOT NULL UNIQUE,
        is_public       BOOLEAN NOT NULL DEFAULT TRUE,

        -- Cover image (stored on disk like avatars)
        cover_filename  VARCHAR(255)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_events_creator
        ON community_events (creator_id, created_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_events_public
        ON community_events (is_public, start_date DESC)
        WHERE is_public = TRUE;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_events_invite
        ON community_events (invite_code);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_events_status
        ON community_events (status);
    """,
    # ── Event members (participants) ─────────────────────────
    """
    CREATE TABLE IF NOT EXISTS event_members (
        id              SERIAL PRIMARY KEY,
        event_id        UUID NOT NULL
            REFERENCES community_events(id) ON DELETE CASCADE,
        user_id         INTEGER NOT NULL
            REFERENCES users(id) ON DELETE CASCADE,
        role            VARCHAR(20) NOT NULL DEFAULT 'member',
        joined_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (event_id, user_id)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_event_members_event
        ON event_members (event_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_event_members_user
        ON event_members (user_id);
    """,
    # ── Link submissions to events ───────────────────────────
    """
    ALTER TABLE sighting_submissions
        ADD COLUMN IF NOT EXISTS event_id UUID
            REFERENCES community_events(id) ON DELETE SET NULL;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_submissions_event
        ON sighting_submissions (event_id)
        WHERE event_id IS NOT NULL;
    """,
    # ── Event comments ───────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS event_comments (
        id              SERIAL PRIMARY KEY,
        event_id        UUID NOT NULL
            REFERENCES community_events(id) ON DELETE CASCADE,
        user_id         INTEGER NOT NULL
            REFERENCES users(id) ON DELETE CASCADE,
        body            TEXT NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_event_comments_event
        ON event_comments (event_id, created_at ASC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_event_comments_user
        ON event_comments (user_id);
    """,
    # ── External events (curated / scraped) ──────────────────
    """
    CREATE TABLE IF NOT EXISTS external_events (
        id              SERIAL PRIMARY KEY,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ,

        -- Core fields
        title           VARCHAR(300) NOT NULL,
        description     TEXT,
        organizer       VARCHAR(200) NOT NULL,
        source_url      VARCHAR(500),

        -- Classification
        event_type      VARCHAR(40) NOT NULL DEFAULT 'other',
        tags            TEXT[],

        -- Schedule
        start_date      DATE,
        end_date        DATE,

        -- Location (optional)
        location_name   VARCHAR(200),
        lat             DOUBLE PRECISION,
        lon             DOUBLE PRECISION,
        is_virtual      BOOLEAN NOT NULL DEFAULT FALSE,

        -- Visibility
        is_featured     BOOLEAN NOT NULL DEFAULT FALSE,
        is_active       BOOLEAN NOT NULL DEFAULT TRUE,

        -- Audit
        created_by      INTEGER
            REFERENCES users(id) ON DELETE SET NULL
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ext_events_active
        ON external_events (is_active, start_date ASC)
        WHERE is_active = TRUE;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ext_events_featured
        ON external_events (is_featured, start_date ASC)
        WHERE is_featured = TRUE AND is_active = TRUE;
    """,
    # ── Event photo gallery ──────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS event_gallery (
        id          SERIAL PRIMARY KEY,
        event_id    UUID NOT NULL
            REFERENCES community_events(id) ON DELETE CASCADE,
        user_id     INTEGER NOT NULL
            REFERENCES users(id) ON DELETE CASCADE,
        filename    VARCHAR(255) NOT NULL,
        caption     VARCHAR(500),
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_event_gallery_event
        ON event_gallery (event_id, created_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_event_gallery_user
        ON event_gallery (user_id);
    """,
    # ── Credential evidence file ──────────────────────────────
    """
    ALTER TABLE user_credentials
        ADD COLUMN IF NOT EXISTS evidence_filename VARCHAR(255);
    """,
    # ── Multi-whale encounter: group size ─────────────────────
    """
    ALTER TABLE sighting_submissions
        ADD COLUMN IF NOT EXISTS group_size INTEGER;
    """,
    # ── OBIS / biological enrichment columns ─────────────────
    """
    ALTER TABLE sighting_submissions
        ADD COLUMN IF NOT EXISTS sighting_datetime TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS scientific_name VARCHAR(100),
        ADD COLUMN IF NOT EXISTS aphia_id INTEGER,
        ADD COLUMN IF NOT EXISTS behavior VARCHAR(60),
        ADD COLUMN IF NOT EXISTS life_stage VARCHAR(30),
        ADD COLUMN IF NOT EXISTS calf_present BOOLEAN,
        ADD COLUMN IF NOT EXISTS sea_state_beaufort SMALLINT,
        ADD COLUMN IF NOT EXISTS observation_platform VARCHAR(60),
        ADD COLUMN IF NOT EXISTS coordinate_uncertainty_m DOUBLE PRECISION;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_submissions_scientific_name
        ON sighting_submissions (scientific_name)
        WHERE scientific_name IS NOT NULL;
    """,
    # ── User vessels (boat profiles) ─────────────────────────
    """
    CREATE TABLE IF NOT EXISTS user_vessels (
        id              SERIAL PRIMARY KEY,
        user_id         INTEGER NOT NULL
            REFERENCES users(id) ON DELETE CASCADE,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ,

        -- Identity
        vessel_name     VARCHAR(200) NOT NULL,
        vessel_type     VARCHAR(60) NOT NULL,

        -- Dimensions (metric)
        length_m        DOUBLE PRECISION,
        beam_m          DOUBLE PRECISION,
        draft_m         DOUBLE PRECISION,

        -- Operational
        hull_material   VARCHAR(40),
        propulsion      VARCHAR(40),
        typical_speed_knots DOUBLE PRECISION,

        -- Registration (all optional)
        home_port       VARCHAR(200),
        flag_state      VARCHAR(100),
        registration_number VARCHAR(100),
        mmsi            INTEGER,
        imo             VARCHAR(20),
        call_sign       VARCHAR(20),

        -- Active vessel selector
        is_active       BOOLEAN NOT NULL DEFAULT FALSE
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_vessels_user
        ON user_vessels (user_id);
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_vessels_active
        ON user_vessels (user_id)
        WHERE is_active = TRUE;
    """,
    # ── Link sightings to the vessel used during observation ──
    """
    ALTER TABLE sighting_submissions
        ADD COLUMN IF NOT EXISTS vessel_id INTEGER
            REFERENCES user_vessels(id) ON DELETE SET NULL;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_submissions_vessel
        ON sighting_submissions (vessel_id)
        WHERE vessel_id IS NOT NULL;
    """,
    # ── Taxonomic rank awareness on sighting submissions ──────
    """
    ALTER TABLE sighting_submissions
        ADD COLUMN IF NOT EXISTS submitted_rank VARCHAR(20);
    """,
    """
    ALTER TABLE sighting_submissions
        ADD COLUMN IF NOT EXISTS submitted_scientific_name VARCHAR(120);
    """,
    # ── Extend community votes to support 'refine' action ─────
    """
    ALTER TABLE submission_votes
        DROP CONSTRAINT IF EXISTS submission_votes_vote_check;
    """,
    """
    ALTER TABLE submission_votes
        ADD CONSTRAINT submission_votes_vote_check
            CHECK (vote IN ('agree', 'disagree', 'refine'));
    """,
    """
    ALTER TABLE submission_votes
        ADD COLUMN IF NOT EXISTS suggested_rank VARCHAR(20);
    """,
    # ── Vessel crew + boat profile enhancements ──────────────
    """
    ALTER TABLE user_vessels
        ADD COLUMN IF NOT EXISTS description TEXT,
        ADD COLUMN IF NOT EXISTS profile_photo_filename VARCHAR(255),
        ADD COLUMN IF NOT EXISTS cover_photo_filename VARCHAR(255);
    """,
    """
    CREATE TABLE IF NOT EXISTS vessel_crew (
        id          SERIAL PRIMARY KEY,
        vessel_id   INTEGER NOT NULL
            REFERENCES user_vessels(id) ON DELETE CASCADE,
        user_id     INTEGER NOT NULL
            REFERENCES users(id) ON DELETE CASCADE,
        role        VARCHAR(20) NOT NULL DEFAULT 'crew'
            CHECK (role IN ('owner', 'crew', 'guest')),
        joined_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        invited_by  INTEGER
            REFERENCES users(id) ON DELETE SET NULL,
        UNIQUE (vessel_id, user_id)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_vessel_crew_vessel
        ON vessel_crew (vessel_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_vessel_crew_user
        ON vessel_crew (user_id);
    """,
    # Backfill: insert owner rows for all existing vessels
    """
    INSERT INTO vessel_crew (vessel_id, user_id, role)
    SELECT id, user_id, 'owner'
    FROM user_vessels
    ON CONFLICT (vessel_id, user_id) DO NOTHING;
    """,
    # ── 67: Add vessel_id to community_events ──
    """
    ALTER TABLE community_events
        ADD COLUMN IF NOT EXISTS vessel_id INTEGER
            REFERENCES user_vessels(id) ON DELETE SET NULL;
    """,
    # ── 68: Enhanced sighting fields ──
    # confidence, group size min/max, visibility, glare, distance, privacy
    """
    ALTER TABLE sighting_submissions
        ADD COLUMN IF NOT EXISTS confidence_level VARCHAR(20),
        ADD COLUMN IF NOT EXISTS group_size_min INTEGER,
        ADD COLUMN IF NOT EXISTS group_size_max INTEGER,
        ADD COLUMN IF NOT EXISTS visibility_km REAL,
        ADD COLUMN IF NOT EXISTS sea_glare VARCHAR(20),
        ADD COLUMN IF NOT EXISTS distance_to_animal_m REAL,
        ADD COLUMN IF NOT EXISTS privacy_level VARCHAR(20)
            DEFAULT 'public';
    """,
    # ── 69: Direction of travel ──
    """
    ALTER TABLE sighting_submissions
        ADD COLUMN IF NOT EXISTS direction_of_travel VARCHAR(20);
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

"""Create external_events table and seed data."""

import psycopg2

DATABASE_URL = "postgresql://marine:marine_dev@localhost:5433/marine_risk"


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS external_events (
            id              SERIAL PRIMARY KEY,
            title           TEXT NOT NULL,
            description     TEXT,
            organizer       TEXT,
            source_url      TEXT,
            event_type      TEXT NOT NULL DEFAULT 'other',
            tags            TEXT[],
            start_date      DATE,
            end_date        DATE,
            location_name   TEXT,
            lat             DOUBLE PRECISION,
            lon             DOUBLE PRECISION,
            is_virtual      BOOLEAN NOT NULL DEFAULT FALSE,
            is_featured     BOOLEAN NOT NULL DEFAULT FALSE,
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            created_by      INTEGER REFERENCES users(id),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_external_events_active
            ON external_events (is_active);
        CREATE INDEX IF NOT EXISTS idx_external_events_start
            ON external_events (start_date);
        CREATE INDEX IF NOT EXISTS idx_external_events_type
            ON external_events (event_type);
    """)
    conn.commit()
    print("external_events table created successfully")

    # Seed data — init pool for service layer
    from backend.services.database import init_pool
    from backend.services.external_events import seed_external_events

    init_pool()

    # Find or create a moderator user for seeding
    cur2 = conn.cursor()
    cur2.execute("SELECT id FROM users WHERE is_moderator = TRUE LIMIT 1")
    row = cur2.fetchone()
    if row:
        mod_id = row[0]
    else:
        # Use first user and make them a moderator
        cur2.execute("SELECT id FROM users LIMIT 1")
        row = cur2.fetchone()
        if row:
            mod_id = row[0]
            cur2.execute(
                "UPDATE users SET is_moderator = TRUE WHERE id = %s",
                (mod_id,),
            )
            conn.commit()
        else:
            print("No users in DB — skipping seed")
            cur2.close()
            conn.close()
            return
    cur2.close()

    count = seed_external_events(mod_id)
    print(f"Seeded {count} external events (moderator_id={mod_id})")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

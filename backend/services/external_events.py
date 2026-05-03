"""Service layer for curated external events (moderator-managed)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from backend.services.database import (
    fetch_all,
    fetch_one,
    fetch_scalar,
    get_conn,
)

log = logging.getLogger(__name__)

# Valid external event types
VALID_EXTERNAL_TYPES = {
    "workshop",
    "webinar",
    "public_comment",
    "conference",
    "education",
    "research",
    "cleanup",
    "other",
}


def list_external_events(
    *,
    limit: int = 50,
    offset: int = 0,
    include_inactive: bool = False,
    featured_only: bool = False,
    event_type: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return paginated external events.

    By default only active events sorted by start_date ascending
    (upcoming first). Returns ``(rows, total_count)``.
    """
    where_clauses: list[str] = []
    params: list[Any] = []

    if not include_inactive:
        where_clauses.append("is_active = TRUE")
    if featured_only:
        where_clauses.append("is_featured = TRUE")
    if event_type:
        where_clauses.append("event_type = %s")
        params.append(event_type)

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    count_sql = f"SELECT count(*) FROM external_events {where_sql}"
    total = fetch_scalar(count_sql, tuple(params)) or 0

    query = f"""
        SELECT id, title, description, organizer, source_url,
               event_type, tags, start_date, end_date,
               location_name, lat, lon, is_virtual,
               is_featured, is_active, created_at, updated_at
        FROM external_events
        {where_sql}
        ORDER BY
            is_featured DESC,
            CASE WHEN start_date >= CURRENT_DATE THEN 0 ELSE 1 END,
            start_date ASC NULLS LAST,
            created_at DESC
        LIMIT %s OFFSET %s
    """
    params_q = list(params) + [limit, offset]
    rows = fetch_all(query, tuple(params_q))
    # Convert tags from PG array to list
    for r in rows:
        r["tags"] = list(r["tags"]) if r.get("tags") else []
    return rows, total


def get_external_event(event_id: int) -> dict[str, Any] | None:
    """Fetch a single external event by ID."""
    row = fetch_one(
        """
        SELECT id, title, description, organizer, source_url,
               event_type, tags, start_date, end_date,
               location_name, lat, lon, is_virtual,
               is_featured, is_active, created_at, updated_at
        FROM external_events
        WHERE id = %s
        """,
        (event_id,),
    )
    if row:
        row["tags"] = list(row["tags"]) if row.get("tags") else []
    return row


def create_external_event(
    created_by: int,
    *,
    title: str,
    description: str | None = None,
    organizer: str,
    source_url: str | None = None,
    event_type: str = "other",
    tags: list[str] | None = None,
    start_date: Any = None,
    end_date: Any = None,
    location_name: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    is_virtual: bool = False,
    is_featured: bool = False,
) -> dict[str, Any]:
    """Create a new external event. Returns the event dict."""
    if event_type not in VALID_EXTERNAL_TYPES:
        raise ValueError(
            f"Invalid event_type: {event_type}. "
            f"Must be one of {sorted(VALID_EXTERNAL_TYPES)}"
        )

    pg_tags = tags if tags else None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO external_events
                (title, description, organizer, source_url,
                 event_type, tags, start_date, end_date,
                 location_name, lat, lon, is_virtual,
                 is_featured, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                title,
                description,
                organizer,
                source_url,
                event_type,
                pg_tags,
                start_date,
                end_date,
                location_name,
                lat,
                lon,
                is_virtual,
                is_featured,
                created_by,
            ),
        )
        new_id = cur.fetchone()[0]
        conn.commit()

    log.info(
        "Created external event %d: %s (%s)",
        new_id,
        title,
        organizer,
    )
    return get_external_event(new_id)  # type: ignore[return-value]


def update_external_event(
    event_id: int,
    **fields: Any,
) -> dict[str, Any] | None:
    """Update an external event. Returns updated dict or None."""
    existing = get_external_event(event_id)
    if not existing:
        return None

    # Build SET clause from provided fields
    allowed = {
        "title",
        "description",
        "organizer",
        "source_url",
        "event_type",
        "tags",
        "start_date",
        "end_date",
        "location_name",
        "lat",
        "lon",
        "is_virtual",
        "is_featured",
        "is_active",
    }
    updates: dict[str, Any] = {}
    for k, v in fields.items():
        if k in allowed and v is not None:
            updates[k] = v

    if not updates:
        return existing

    if "event_type" in updates and updates["event_type"] not in VALID_EXTERNAL_TYPES:
        raise ValueError(f"Invalid event_type: {updates['event_type']}")

    updates["updated_at"] = datetime.now(UTC)

    set_parts = [f"{k} = %s" for k in updates]
    values = list(updates.values()) + [event_id]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE external_events SET {', '.join(set_parts)} WHERE id = %s",
            tuple(values),
        )
        conn.commit()

    log.info("Updated external event %d", event_id)
    return get_external_event(event_id)


def delete_external_event(event_id: int) -> bool:
    """Soft-delete an external event (set is_active = FALSE)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE external_events SET is_active = FALSE, "
            "updated_at = %s WHERE id = %s",
            (datetime.now(UTC), event_id),
        )
        affected = cur.rowcount
        conn.commit()
    return affected > 0


def is_moderator(user_id: int) -> bool:
    """Check if a user has moderator privileges."""
    val = fetch_scalar(
        "SELECT is_moderator FROM users WHERE id = %s",
        (user_id,),
    )
    return bool(val)


def seed_external_events(moderator_id: int) -> int:
    """Seed database with curated external events from NOAA and
    other marine conservation organisations.

    Returns the number of events inserted.
    """
    seeds = [
        {
            "title": "Ocean Fun Days 2026",
            "description": (
                "Free family-friendly event celebrating ocean science "
                "and conservation. Touch tanks, marine mammal talks, "
                "and hands-on activities for all ages."
            ),
            "organizer": "NOAA Fisheries",
            "source_url": ("https://www.fisheries.noaa.gov/event/ocean-fun-days-2026"),
            "event_type": "education",
            "tags": ["noaa", "family", "outreach", "free"],
            "start_date": "2026-06-06",
            "end_date": "2026-06-07",
            "location_name": "Sandy Hook, NJ",
            "lat": 40.4615,
            "lon": -73.9911,
            "is_featured": True,
        },
        {
            "title": ("North Atlantic Right Whale: Recovery Planning Workshop"),
            "description": (
                "A multi-day workshop bringing together scientists, "
                "policy experts, and stakeholders to review recovery "
                "progress for the critically endangered North "
                "Atlantic right whale and set new conservation "
                "priorities."
            ),
            "organizer": "NOAA Fisheries",
            "source_url": (
                "https://www.fisheries.noaa.gov/event/"
                "right-whale-recovery-workshop-2026"
            ),
            "event_type": "workshop",
            "tags": [
                "noaa",
                "right_whale",
                "conservation",
                "policy",
            ],
            "start_date": "2026-04-22",
            "end_date": "2026-04-24",
            "location_name": "Silver Spring, MD",
            "lat": 38.9907,
            "lon": -77.0261,
            "is_featured": True,
        },
        {
            "title": ("Marine Mammal Stock Assessment Peer Review — Atlantic"),
            "description": (
                "External peer review of draft NOAA marine mammal "
                "stock assessment reports for Atlantic species. "
                "Open to public observers via webinar."
            ),
            "organizer": "NOAA Fisheries",
            "source_url": (
                "https://www.fisheries.noaa.gov/event/"
                "atlantic-stock-assessment-peer-review-2026"
            ),
            "event_type": "public_comment",
            "tags": [
                "noaa",
                "stock_assessment",
                "peer_review",
                "webinar",
            ],
            "start_date": "2026-05-12",
            "end_date": "2026-05-14",
            "location_name": "Virtual (Webinar)",
            "is_virtual": True,
            "is_featured": False,
        },
        {
            "title": "International Whaling Commission — IWC69",
            "description": (
                "The 69th meeting of the International Whaling "
                "Commission. Discussions on whale conservation, "
                "Aboriginal subsistence whaling, and scientific "
                "permits."
            ),
            "organizer": "International Whaling Commission",
            "source_url": "https://iwc.int/meetings",
            "event_type": "conference",
            "tags": [
                "iwc",
                "international",
                "policy",
                "conservation",
            ],
            "start_date": "2026-09-14",
            "end_date": "2026-09-18",
            "location_name": "Lima, Peru",
            "lat": -12.0464,
            "lon": -77.0428,
            "is_featured": True,
        },
        {
            "title": (
                "Stellwagen Bank National Marine Sanctuary — "
                "Whale Watch Volunteer Training"
            ),
            "description": (
                "Volunteer training for citizen scientists joining "
                "Stellwagen Bank whale watch survey cruises this "
                "season. Learn species identification, data "
                "collection protocols, and safety procedures."
            ),
            "organizer": "NOAA Office of National Marine Sanctuaries",
            "source_url": ("https://stellwagen.noaa.gov/education/volunteer.html"),
            "event_type": "education",
            "tags": [
                "noaa",
                "sanctuary",
                "volunteer",
                "citizen_science",
            ],
            "start_date": "2026-04-05",
            "end_date": "2026-04-05",
            "location_name": "Scituate, MA",
            "lat": 42.1998,
            "lon": -70.7172,
            "is_featured": False,
        },
        {
            "title": "Sustainable Fisheries & Whale Protection Webinar",
            "description": (
                "Panel discussion on best practices for reducing "
                "bycatch and ship strike risk in commercial "
                "fisheries. Featuring researchers from Woods Hole, "
                "Duke Marine Lab, and NOAA."
            ),
            "organizer": "NOAA Fisheries",
            "source_url": (
                "https://www.fisheries.noaa.gov/event/"
                "sustainable-fisheries-whale-protection-2026"
            ),
            "event_type": "webinar",
            "tags": [
                "noaa",
                "fisheries",
                "bycatch",
                "ship_strike",
            ],
            "start_date": "2026-03-27",
            "end_date": "2026-03-27",
            "location_name": "Virtual (Webinar)",
            "is_virtual": True,
            "is_featured": False,
        },
        {
            "title": "World Whale Day — Hawaiian Islands",
            "description": (
                "Annual celebration of humpback whales in Maui with "
                "educational exhibits, guided whale watches, live "
                "music, and conservation fundraising."
            ),
            "organizer": "Pacific Whale Foundation",
            "source_url": ("https://www.pacificwhale.org/events/world-whale-day"),
            "event_type": "education",
            "tags": [
                "humpback",
                "hawaii",
                "festival",
                "conservation",
            ],
            "start_date": "2026-02-21",
            "end_date": "2026-02-21",
            "location_name": "Kīhei, Maui, HI",
            "lat": 20.7644,
            "lon": -156.4450,
            "is_featured": True,
        },
        {
            "title": (
                "NMFS Proposed Rule: Vessel Speed Restrictions — Public Comment Period"
            ),
            "description": (
                "NOAA Fisheries is accepting public comments on "
                "the proposed modifications to the North Atlantic "
                "right whale vessel speed rule (50 CFR Part 224). "
                "Comments may be submitted electronically."
            ),
            "organizer": "NOAA Fisheries",
            "source_url": (
                "https://www.fisheries.noaa.gov/action/"
                "modifications-north-atlantic-right-whale-"
                "vessel-speed-rule"
            ),
            "event_type": "public_comment",
            "tags": [
                "noaa",
                "right_whale",
                "speed_rule",
                "regulation",
            ],
            "start_date": "2026-03-15",
            "end_date": "2026-06-15",
            "location_name": "Virtual (Regulations.gov)",
            "is_virtual": True,
            "is_featured": True,
        },
    ]

    inserted = 0
    for seed in seeds:
        # Skip if title + organizer already exists
        existing = fetch_one(
            "SELECT id FROM external_events WHERE title = %s AND organizer = %s",
            (seed["title"], seed["organizer"]),
        )
        if existing:
            continue

        create_external_event(moderator_id, **seed)
        inserted += 1

    log.info("Seeded %d external events", inserted)
    return inserted

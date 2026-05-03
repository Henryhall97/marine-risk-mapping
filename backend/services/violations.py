from typing import Any

from psycopg2.extras import RealDictCursor

from .database import get_conn

# Service for vessel violation reports


def fetch_violation_reports(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                id,
                lat,
                lon,
                violation_type,
                description,
                evidence_url,
                timestamp,
                status,
                community_agree_count,
                community_disagree_count
            FROM vessel_violation_reports
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        results = cur.fetchall()
    return results


def fetch_violation_report_detail(report_id: int) -> dict[str, Any] | None:
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
                SELECT * FROM vessel_violation_reports WHERE id = %s
                """,
            (report_id,),
        )
        result = cur.fetchone()
    return result


def create_violation_report(
    lat: float,
    lon: float,
    violation_type: str,
    description: str,
    evidence_url: str | None,
    reporter_id: int | None = None,
) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO vessel_violation_reports
                (lat, lon, violation_type, description, evidence_url, reporter_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (lat, lon, violation_type, description, evidence_url, reporter_id),
            )
            report_id = cur.fetchone()[0]
        conn.commit()
    return report_id


def moderate_violation_report(report_id: int, status: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE vessel_violation_reports SET status = %s WHERE id = %s
                """,
                (status, report_id),
            )
        conn.commit()


def community_vote(report_id: int, agree: bool) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if agree:
                cur.execute(
                    """
                    UPDATE vessel_violation_reports
                    SET community_agree_count = community_agree_count + 1
                    WHERE id = %s
                    """,
                    (report_id,),
                )
            else:
                cur.execute(
                    """
                    UPDATE vessel_violation_reports
                    SET community_disagree_count = community_disagree_count + 1
                    WHERE id = %s
                    """,
                    (report_id,),
                )
        conn.commit()

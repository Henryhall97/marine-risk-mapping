"""Download active Right Whale Slow Zones from NOAA Fisheries.

Scrapes the NOAA Fisheries vessel strike reduction page for
current Right Whale Slow Zones and Dynamic Management Areas
(DMAs). These are voluntary 15-day speed restriction zones
established when right whales are detected visually (≥3 whales)
or acoustically.

Unlike SMAs (permanent seasonal), slow zones are **ephemeral** —
they expire 15 days after designation and new ones are created
as whales are detected. This script captures a snapshot of
whatever zones are active at the time of execution.

Re-run this script periodically (e.g. weekly) to keep the data
current. Each run overwrites the previous file.

Source: NOAA Fisheries — Reducing Vessel Strikes to NARW
  https://www.fisheries.noaa.gov/national/endangered-species-
  conservation/reducing-vessel-strikes-north-atlantic-right-whales
"""

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx

from pipeline.config import SLOW_ZONES_FILE

NOAA_SLOW_ZONE_URL = (
    "https://www.fisheries.noaa.gov/national/"
    "endangered-species-conservation/"
    "reducing-vessel-strikes-north-atlantic-right-whales"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── DMS coordinate parsing ──────────────────────────────────

# Matches patterns like: 40°00′ N, 40°35' N, 42°04'56.5" N
_DMS_RE = re.compile(
    r"(\d+)\s*[°]\s*"
    r"(\d+)\s*[′']\s*"
    r"(?:(\d+(?:\.\d+)?)\s*[″\"]?\s*)?"
    r"([NSEW])",
    re.IGNORECASE,
)


def _dms_to_decimal(dms_str: str) -> float:
    """Convert a DMS coordinate string to decimal degrees.

    Handles formats like '40°00′ N', '72°48′ W',
    '42°04\'56.5\" N'.
    """
    m = _DMS_RE.search(dms_str)
    if not m:
        raise ValueError(f"Cannot parse DMS coordinate: {dms_str!r}")
    deg = int(m.group(1))
    mins = int(m.group(2))
    secs = float(m.group(3)) if m.group(3) else 0.0
    direction = m.group(4).upper()

    decimal = deg + mins / 60.0 + secs / 3600.0
    if direction in ("S", "W"):
        decimal = -decimal
    return round(decimal, 6)


# ── HTML parsing ────────────────────────────────────────────

# Pattern to extract individual slow zone blocks:
# "#### <Name> Slow Zone: Effective <dates>\n\nWaters bounded by:\n\n
#  Northern Boundary: ...\nSouthern Boundary: ...\n
#  Eastern Boundary: ...\nWestern Boundary: ..."
_ZONE_BLOCK_RE = re.compile(
    r"####\s+(.+?Slow Zone):\s*Effective\s+(.+?)\n"
    r".*?"
    r"Northern Boundary:\s*(.+?)\n"
    r".*?"
    r"Southern Boundary:\s*(.+?)\n"
    r".*?"
    r"Eastern Boundary:\s*(.+?)\n"
    r".*?"
    r"Western Boundary:\s*(.+?)(?:\n|$)",
    re.DOTALL,
)

# Alternate pattern for raw HTML (no markdown conversion)
_ZONE_HTML_RE = re.compile(
    r"<h[34][^>]*>.*?"
    r"([\w\s,]+Slow Zone)\s*:\s*Effective\s+"
    r"([\w\s,–-]+\d{4})"
    r".*?"
    r"Northern Boundary:\s*([\d°′'\".\s]+[NS])"
    r".*?"
    r"Southern Boundary:\s*([\d°′'\".\s]+[NS])"
    r".*?"
    r"Eastern Boundary:\s*([\d°′'\".\s]+[EW])"
    r".*?"
    r"Western Boundary:\s*([\d°′'\".\s]+[EW])",
    re.DOTALL | re.IGNORECASE,
)


def _parse_effective_dates(
    date_str: str,
) -> tuple[str, str]:
    """Parse 'March 3 - 18, 2026' into ISO date strings.

    Returns (start_date, end_date) as 'YYYY-MM-DD' strings.
    Handles formats like:
      'March 3 - 18, 2026'
      'February 28 - March 15, 2026'
    """
    date_str = date_str.strip().rstrip(".")
    # Replace en-dash / em-dash with hyphen
    date_str = date_str.replace("–", "-").replace("—", "-")

    # Try "Month D - D, YYYY" (same month)
    m = re.match(r"(\w+)\s+(\d+)\s*-\s*(\d+),?\s*(\d{4})", date_str)
    if m:
        month_name, day1, day2, year = m.groups()
        try:
            start = datetime.strptime(f"{month_name} {day1} {year}", "%B %d %Y")
            end = datetime.strptime(f"{month_name} {day2} {year}", "%B %d %Y")
            return (
                start.strftime("%Y-%m-%d"),
                end.strftime("%Y-%m-%d"),
            )
        except ValueError:
            pass

    # Try "Month1 D - Month2 D, YYYY" (cross-month)
    m = re.match(
        r"(\w+)\s+(\d+)\s*-\s*(\w+)\s+(\d+),?\s*(\d{4})",
        date_str,
    )
    if m:
        m1, d1, m2, d2, year = m.groups()
        try:
            start = datetime.strptime(f"{m1} {d1} {year}", "%B %d %Y")
            end = datetime.strptime(f"{m2} {d2} {year}", "%B %d %Y")
            return (
                start.strftime("%Y-%m-%d"),
                end.strftime("%Y-%m-%d"),
            )
        except ValueError:
            pass

    # Fallback: return raw string
    logger.warning("Could not parse date range: %r — storing raw", date_str)
    return (date_str, date_str)


def _bbox_to_polygon(
    north: float,
    south: float,
    east: float,
    west: float,
) -> list[list[list[float]]]:
    """Convert N/S/E/W bounds to a GeoJSON polygon ring.

    Returns coordinates in GeoJSON order: [lon, lat].
    Ring is counter-clockwise (exterior) and closed.
    """
    return [
        [
            [west, south],  # SW corner
            [east, south],  # SE corner
            [east, north],  # NE corner
            [west, north],  # NW corner
            [west, south],  # close ring
        ]
    ]


def _parse_zones_from_text(html: str) -> list[dict]:
    """Extract slow zone features from page text.

    Tries markdown-style patterns first (from fetch_webpage),
    then falls back to raw HTML patterns.
    """
    zones: list[dict] = []

    # Try the markdown-style pattern first
    for m in _ZONE_BLOCK_RE.finditer(html):
        name = m.group(1).strip()
        date_str = m.group(2).strip()
        north_str = m.group(3).strip()
        south_str = m.group(4).strip()
        east_str = m.group(5).strip()
        west_str = m.group(6).strip()

        try:
            north = _dms_to_decimal(north_str)
            south = _dms_to_decimal(south_str)
            east = _dms_to_decimal(east_str)
            west = _dms_to_decimal(west_str)
        except ValueError as e:
            logger.warning(
                "Skipping zone %r — coordinate parse error: %s",
                name,
                e,
            )
            continue

        start_date, end_date = _parse_effective_dates(date_str)

        zones.append(
            {
                "type": "Feature",
                "properties": {
                    "zone_name": name,
                    "zone_type": "slow_zone",
                    "effective_start": start_date,
                    "effective_end": end_date,
                    "effective_raw": date_str,
                    "speed_limit_knots": 10,
                    "voluntary": True,
                    "duration_days": 15,
                    "north_lat": north,
                    "south_lat": south,
                    "east_lon": east,
                    "west_lon": west,
                    "source": "NOAA Fisheries",
                    "source_url": NOAA_SLOW_ZONE_URL,
                    "downloaded_utc": datetime.now(UTC).isoformat(),
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": _bbox_to_polygon(north, south, east, west),
                },
            }
        )

    if zones:
        return zones

    # Fallback: try HTML patterns
    for m in _ZONE_HTML_RE.finditer(html):
        name = m.group(1).strip()
        date_str = m.group(2).strip()

        try:
            north = _dms_to_decimal(m.group(3).strip())
            south = _dms_to_decimal(m.group(4).strip())
            east = _dms_to_decimal(m.group(5).strip())
            west = _dms_to_decimal(m.group(6).strip())
        except ValueError as e:
            logger.warning(
                "Skipping zone %r — coordinate parse error: %s",
                name,
                e,
            )
            continue

        start_date, end_date = _parse_effective_dates(date_str)

        zones.append(
            {
                "type": "Feature",
                "properties": {
                    "zone_name": name,
                    "zone_type": "slow_zone",
                    "effective_start": start_date,
                    "effective_end": end_date,
                    "effective_raw": date_str,
                    "speed_limit_knots": 10,
                    "voluntary": True,
                    "duration_days": 15,
                    "north_lat": north,
                    "south_lat": south,
                    "east_lon": east,
                    "west_lon": west,
                    "source": "NOAA Fisheries",
                    "source_url": NOAA_SLOW_ZONE_URL,
                    "downloaded_utc": datetime.now(UTC).isoformat(),
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": _bbox_to_polygon(north, south, east, west),
                },
            }
        )

    return zones


# ── Main download function ──────────────────────────────────


def download_slow_zones(*, force: bool = False) -> Path:
    """Download active Right Whale Slow Zones from NOAA.

    Scrapes the NOAA Fisheries vessel strike reduction page,
    parses bounding coordinates for each active slow zone, and
    saves as GeoJSON.

    These zones are ephemeral (15-day duration). Re-run this
    script periodically to capture the current active set.

    Args:
        force: If True, overwrite existing file.

    Returns:
        Path to the saved GeoJSON file.
    """
    output = Path(SLOW_ZONES_FILE)
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists() and not force:
        logger.info(
            "Slow zones file already exists: %s "
            "— skipping (use --force to re-download)",
            output,
        )
        return output

    logger.info("Fetching NOAA Fisheries page for active slow zones...")

    try:
        response = httpx.get(
            NOAA_SLOW_ZONE_URL,
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "marine-risk-mapping/1.0 (research; contact@example.com)"
                ),
            },
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            "HTTP error fetching NOAA page: %s",
            e.response.status_code,
        )
        raise
    except httpx.RequestError as e:
        logger.error("Request failed: %s", e)
        raise

    html = response.text
    logger.info(
        "Received %d bytes from NOAA Fisheries page",
        len(html),
    )

    zones = _parse_zones_from_text(html)

    if not zones:
        logger.warning(
            "No active slow zones found on NOAA page. "
            "This may mean no zones are currently active, "
            "or the page structure has changed."
        )
        # Still save an empty FeatureCollection
        geojson: dict = {
            "type": "FeatureCollection",
            "features": [],
            "properties": {
                "description": (
                    "Right Whale Slow Zones (none active at download time)"
                ),
                "source_url": NOAA_SLOW_ZONE_URL,
                "downloaded_utc": datetime.now(UTC).isoformat(),
            },
        }
    else:
        geojson = {
            "type": "FeatureCollection",
            "features": zones,
            "properties": {
                "description": (
                    "Active Right Whale Slow Zones / DMAs from NOAA Fisheries"
                ),
                "source_url": NOAA_SLOW_ZONE_URL,
                "downloaded_utc": datetime.now(UTC).isoformat(),
                "note": ("Ephemeral zones (15-day duration). Re-run script to update."),
            },
        }

    with open(output, "w") as f:
        json.dump(geojson, f, indent=2)

    size_kb = output.stat().st_size / 1024
    logger.info(
        "Saved %d active slow zones (%.1f KB) to %s",
        len(zones),
        size_kb,
        output,
    )

    for feat in zones:
        props = feat["properties"]
        logger.info(
            "  %s — %s to %s  [%.2f°N to %.2f°N, %.2f°W to %.2f°W]",
            props["zone_name"],
            props["effective_start"],
            props["effective_end"],
            props["south_lat"],
            props["north_lat"],
            abs(props["west_lon"]),
            abs(props["east_lon"]),
        )

    return output


if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(
        description=("Download active Right Whale Slow Zones from NOAA Fisheries"),
    )
    _parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing file",
    )
    _args = _parser.parse_args()
    download_slow_zones(force=_args.force)

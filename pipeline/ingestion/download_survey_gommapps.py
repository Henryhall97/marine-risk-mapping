"""Download and tidy GoMMAPPS visual line-transect survey data from NCEI.

The Gulf of Mexico Marine Assessment Program for Protected Species
(GoMMAPPS, 2017-2018) ran shipboard (NOAA Ships Gordon Gunter and Pisces)
and aerial (DHC-6 Twin Otter) distance-sampling surveys.  The raw data are
archived at NCEI as one accession per survey leg.  Three schema families
appear, with table-name drift between them:

    *_EffortPoints_*.csv        on/off-effort track positions (~30 s cadence)
    *_MMSights[_]BehObs_*.csv    cetacean sightings + behaviour (group size
                                inline on aerial via individualCount)
    *_MMGroupSizes_*.csv         observer group-size estimates (vessel only)
    *_MMSightsCues_*.csv         vessel detection cue: radial distance + bearing
    *_(MM|Mammal)SightsAndCues_  aerial detection cue: perpendicular distance
        *.csv                   (from declination angle + altitude)

Vessel legs ship one effort + one cue table; aerial legs split effort and
cue tables across two simultaneous observer teams (``T1``/``T2``) flying the
same trackline (double-platform).  We use the T1 tables as the trackline (to
avoid double-counting effort) and flag ``double_platform`` because the second
team exists.  Three further accessions are NOT raw line-transect data and are
excluded: two consolidated strip-transect products (coarse distance bins,
multi-taxon) and one published density-model shapefile set (validation
benchmark).

This script resolves each accession's NCEI archive path, crawls for the
tables, and harmonises them into three tidy tables shared across all
survey programmes (Phase 3 DSM density engine):

    survey_segments               effort geometry (one row per effort point)
    survey_sightings              perpendicular distance + group size
    survey_detection_covariates   Beaufort, observer, platform, double-platform

Python performs download + tidy ONLY.  All statistics (detection function,
segmentation, DSM GAM) live in the R density/ toolchain.

Source: NOAA SEFSC / NCEI archive — https://www.ncei.noaa.gov/archive/
  Programme: GoMMAPPS (https://doi.org/10.25923/xdnn-wg78)
"""

from __future__ import annotations

import argparse
import io
import logging
import re

import httpx
import numpy as np
import pandas as pd

from pipeline.config import (
    GOMMAPPS_ACCESSIONS,
    GOMMAPPS_CACHE_DIR,
    GOMMAPPS_COVARIATES_FILE,
    GOMMAPPS_DIR,
    GOMMAPPS_SEGMENTS_FILE,
    GOMMAPPS_SIGHTINGS_FILE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

NCEI_BASE = "https://www.ncei.noaa.gov"
ACCESSION_LANDING = NCEI_BASE + "/archive/accession/{accession}"
ARCHIVE_ROOT = NCEI_BASE + "/data/oceans/archive/{arc}/{accession}/"

# Regexes that classify a CSV filename into one of the visual tables.  The
# sights pattern allows an optional underscore (MMSights_BehObs on vessel /
# fall-summer aerial, MMSightsBehObs on winter aerial).  The cues pattern
# matches the vessel name (MMSightsCues) and both aerial variants
# (MMSightsAndCues, MammalSightsAndCues).
FILE_PATTERNS = {
    "effort": re.compile(r"EffortPoints.*\.csv$", re.IGNORECASE),
    "sights": re.compile(r"MMSights_?BehObs.*\.csv$", re.IGNORECASE),
    "groups": re.compile(r"MMGroupSizes.*\.csv$", re.IGNORECASE),
    "cues": re.compile(
        r"(?:MMSightsCues|(?:MM|Mammal)SightsAndCues).*\.csv$", re.IGNORECASE
    ),
}

# Accessions that hold GoMMAPPS data in a form NOT usable for cetacean DSM.
# Consolidated strip-transect products use coarse distance-bin codes and mix
# seabirds/fish/turtles with mammals; the SDM benchmark is published model
# output (shapefiles), retained only as an independent validation target.
_CONSOLIDATED_STRIP = frozenset({"0247205", "0247206"})
_SDM_BENCHMARK = frozenset({"0256800"})

# Apache autoindex hrefs that are navigation, not content.
_SKIP_HREF = re.compile(r"^(\?|/|parent)", re.IGNORECASE)

_HTTP_TIMEOUT = httpx.Timeout(120.0)


# ── NCEI directory crawling ────────────────────────────────


def _get(client: httpx.Client, url: str) -> httpx.Response:
    resp = client.get(url, timeout=_HTTP_TIMEOUT, follow_redirects=True)
    resp.raise_for_status()
    return resp


def _list_dir(client: httpx.Client, url: str) -> list[str]:
    """Return child hrefs (relative names) of an Apache autoindex page."""
    resp = _get(client, url)
    hrefs = re.findall(r'href="([^"]+)"', resp.text)
    children: list[str] = []
    for href in hrefs:
        if _SKIP_HREF.match(href):
            continue
        if href.startswith("http") or "/filter/" in href:
            continue
        children.append(href)
    return children


def _resolve_arc(client: httpx.Client, accession: str) -> str | None:
    """Find the arcNNNN bucket that holds an accession from its landing page."""
    url = ACCESSION_LANDING.format(accession=accession)
    try:
        resp = _get(client, url)
    except httpx.HTTPError as exc:
        logger.warning("Could not load landing page for %s: %s", accession, exc)
        return None
    match = re.search(r"arc\d{4}", resp.text)
    if not match:
        logger.warning("No arc bucket found for accession %s", accession)
        return None
    return match.group(0)


def _crawl_csvs(client: httpx.Client, base_url: str, max_depth: int = 8) -> list[str]:
    """Breadth-first crawl of an accession tree, returning all .csv URLs."""
    found: list[str] = []
    frontier: list[tuple[str, int]] = [(base_url, 0)]
    seen: set[str] = set()
    while frontier:
        url, depth = frontier.pop(0)
        if url in seen or depth > max_depth:
            continue
        seen.add(url)
        try:
            children = _list_dir(client, url)
        except httpx.HTTPError:
            continue
        for child in children:
            child_url = url + child
            if child.endswith("/"):
                frontier.append((child_url, depth + 1))
            elif child.lower().endswith(".csv"):
                found.append(child_url)
    return found


def _classify(csv_urls: list[str]) -> dict[str, str]:
    """Map each visual-table key to its CSV URL (first match wins).

    URLs are sorted so that, when an accession ships split observer-team
    tables (aerial T1/T2), the T1 table is selected deterministically.  T1
    and T2 cover the same flown trackline, so using one avoids double-
    counting effort; the second team is the double-observer copy used for
    g(0) perception-bias correction in R, read from the raw cache if needed.
    """
    tables: dict[str, str] = {}
    for url in sorted(csv_urls):
        name = url.rsplit("/", 1)[-1]
        for key, pattern in FILE_PATTERNS.items():
            if key not in tables and pattern.search(name):
                tables[key] = url
    return tables


# ── Download + parse ───────────────────────────────────────


def _read_csv(client: httpx.Client, url: str, accession: str) -> pd.DataFrame:
    """Download a CSV (with on-disk cache) into a DataFrame."""
    GOMMAPPS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    name = url.rsplit("/", 1)[-1]
    cache_path = GOMMAPPS_CACHE_DIR / f"{accession}__{name}"
    if cache_path.exists():
        return pd.read_csv(cache_path, low_memory=False)
    resp = _get(client, url)
    cache_path.write_bytes(resp.content)
    return pd.read_csv(io.BytesIO(resp.content), low_memory=False)


def _fetch_accession(
    client: httpx.Client, accession: str
) -> tuple[dict[str, pd.DataFrame], bool] | None:
    """Resolve, crawl, and download the visual tables for one accession.

    Returns ``(frames, multi_platform)`` or ``None`` when the accession holds
    no cetacean line-transect tables.  ``multi_platform`` is True when the
    accession ships two independent effort tables (aerial T1/T2 observer
    teams) — the double-platform signal for g(0) perception-bias correction.
    """
    if accession in _CONSOLIDATED_STRIP:
        logger.info(
            "  %s is a consolidated strip-transect product "
            "(coarse distance bins, multi-taxon) — excluded from DSM",
            accession,
        )
        return None
    if accession in _SDM_BENCHMARK:
        logger.info(
            "  %s holds published SEFSC density-model shapefiles "
            "(validation benchmark, not survey data) — skipping",
            accession,
        )
        return None
    arc = _resolve_arc(client, accession)
    if arc is None:
        return None
    base_url = ARCHIVE_ROOT.format(arc=arc, accession=accession)
    logger.info("Crawling %s (%s)...", accession, arc)
    csv_urls = _crawl_csvs(client, base_url)
    tables = _classify(csv_urls)
    if "effort" not in tables or "sights" not in tables:
        logger.info("  %s has no cetacean line-transect tables (skipping)", accession)
        return None
    n_effort = sum(
        1 for u in csv_urls if FILE_PATTERNS["effort"].search(u.rsplit("/", 1)[-1])
    )
    multi_platform = n_effort >= 2
    logger.info("  Found %d visual tables", len(tables))
    frames: dict[str, pd.DataFrame] = {}
    for key, url in tables.items():
        frames[key] = _read_csv(client, url, accession)
    return frames, multi_platform


# ── Harmonisation ──────────────────────────────────────────


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _col(df: pd.DataFrame, name: str, fill=np.nan) -> pd.Series:
    """Return a column if present, else a fill-valued Series of matching length."""
    if name in df.columns:
        return df[name]
    return pd.Series(fill, index=df.index)


def _on_effort_flags(effort: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Return (on_effort, double_platform) handling vessel vs aerial schemas.

    Vessel surveys have two observation stations (Flying Bridge =
    onEffort1, Bridge Wing = onEffort2); both on-effort means a
    double-platform (mark-recapture) observation for g(0) estimation.
    Aerial surveys have a single onEffort flag and no double platform.
    """
    if "onEffort1" in effort.columns:
        on1 = _col(effort, "onEffort1", "N").astype(str).str.upper().str.strip()
        on2 = _col(effort, "onEffort2", "N").astype(str).str.upper().str.strip()
        on_effort = (on1 == "Y") | (on2 == "Y")
        double = (on1 == "Y") & (on2 == "Y")
        return on_effort, double
    single = _col(effort, "onEffort", "N").astype(str).str.upper().str.strip()
    on_effort = single == "Y"
    return on_effort, pd.Series(False, index=effort.index)


def _on_effort_flags(
    effort: pd.DataFrame, multi_platform: bool = False
) -> tuple[pd.Series, pd.Series]:
    """Return (on_effort, double_platform) handling vessel vs aerial schemas.

    Vessel surveys have two observation stations in ONE effort table (Flying
    Bridge = onEffort1, Bridge Wing = onEffort2); both on-effort means a
    double-platform (mark-recapture) observation for g(0) estimation.  Aerial
    surveys record a single onEffort per observer-team table; their double-
    platform signal is the presence of a second (T2) team table flying the
    same trackline, passed in as ``multi_platform``.
    """
    if "onEffort1" in effort.columns:
        on1 = _col(effort, "onEffort1", "N").astype(str).str.upper().str.strip()
        on2 = _col(effort, "onEffort2", "N").astype(str).str.upper().str.strip()
        on_effort = (on1 == "Y") | (on2 == "Y")
        double = (on1 == "Y") & (on2 == "Y")
        return on_effort, double
    single = _col(effort, "onEffort", "N").astype(str).str.upper().str.strip()
    on_effort = single == "Y"
    double = on_effort & bool(multi_platform)
    return on_effort, double


def _tidy_segments(effort: pd.DataFrame, multi_platform: bool = False) -> pd.DataFrame:
    """One row per effort point: trackline geometry + survey conditions."""
    out = pd.DataFrame()
    out["survey_event_id"] = effort["surveyEventID"].astype(str)
    out["event_id"] = _to_num(_col(effort, "eventID")).astype("Int64")
    # Vessel effort has a UTC 'time'; aerial effort only has 'eventDate'.
    out["time_utc"] = pd.to_datetime(_col(effort, "time"), errors="coerce")
    out["event_date_local"] = pd.to_datetime(_col(effort, "eventDate"), errors="coerce")
    out["latitude"] = _to_num(_col(effort, "platformLatitude"))
    out["longitude"] = _to_num(_col(effort, "platformLongitude"))
    out["platform_speed_kn"] = _to_num(_col(effort, "platformSpeed"))
    out["platform_heading_deg"] = _to_num(_col(effort, "platformHeading"))
    out["trackline"] = _to_num(_col(effort, "trackline")).astype("Int64")
    on_effort, double = _on_effort_flags(effort, multi_platform)
    out["on_effort"] = on_effort
    out["double_platform"] = double
    out["beaufort"] = _to_num(_col(effort, "beaufortSeaState")).astype("Int64")
    out["platform_type"] = _col(effort, "platformVLTS", "").astype(str)
    out["platform_name"] = _col(effort, "platformAttributes", "").astype(str)
    out["program"] = _col(effort, "relatedProjectProgram", "").astype(str)
    return out


def _first_cue(cues: pd.DataFrame) -> pd.DataFrame:
    """One row per sighting: the first (initial-detection) cue."""
    cues = cues.copy()
    cues["surveyEventID"] = cues["surveyEventID"].astype(str)
    cues["sightingNumber"] = _to_num(_col(cues, "sightingNumber")).astype("Int64")
    # Vessel cue tables carry a UTC 'time' and may log several cues per
    # sighting (order by time to keep the initial detection); aerial cue
    # tables have one row per sighting and no 'time' column.
    if "time" in cues.columns:
        cues["_order"] = pd.to_datetime(cues["time"], errors="coerce")
        cues = cues.sort_values("_order")
    return cues.drop_duplicates(
        subset=["surveyEventID", "sightingNumber"], keep="first"
    )


def _perpendicular_distance(cue: pd.DataFrame) -> pd.Series:
    """Perpendicular distance (m) from the cue table, by platform geometry.

    Vessel cue tables record a radial horizontal distance
    (``sightingDistanceInMeters``) plus a horizontal ``bearingToAnimals`` to
    the trackline, so perp = radial * sin(bearing).  Aerial cue tables have
    no horizontal bearing: ``sightingDistanceInMeters`` is already the
    perpendicular offset (derived from the vertical declination angle and
    flight altitude), so it is used directly.
    """
    radial = _to_num(_col(cue, "sightingDistanceInMeters"))
    if "bearingToAnimals" in cue.columns:
        bearing = _to_num(cue["bearingToAnimals"])
        perp = radial * np.sin(np.radians(bearing))
        return perp.where(bearing.notna(), radial)
    return radial


def _tidy_sightings(
    sights: pd.DataFrame,
    groups: pd.DataFrame | None,
    cues: pd.DataFrame | None,
) -> pd.DataFrame:
    """One row per cetacean sighting: distance + group size + taxonomy."""
    out = pd.DataFrame()
    out["survey_event_id"] = sights["surveyEventID"].astype(str)
    out["sighting_number"] = _to_num(sights["sightingNumber"]).astype("Int64")
    out["event_id"] = _to_num(_col(sights, "eventID")).astype("Int64")
    # Vessel sightings carry a UTC 'time'; aerial carry a 'date' only.
    time_src = "time" if "time" in sights.columns else "date"
    out["time_utc"] = pd.to_datetime(_col(sights, time_src), errors="coerce")
    out["latitude"] = _to_num(_col(sights, "platformLatitude"))
    out["longitude"] = _to_num(_col(sights, "platformLongitude"))
    out["scientific_name"] = _col(sights, "scientificName", "").astype(str)
    out["vernacular_name"] = _col(sights, "vernacularName", "").astype(str)
    out["type_vlts"] = _col(sights, "typeVLTS", "").astype(str)
    on = _col(sights, "onEffort", "").astype(str).str.upper().str.strip()
    out["on_effort"] = on == "Y"
    # Vessel records a 0/1 calvesPresence flag; aerial an individualCountCalves
    # count — either positive value means a calf was present.
    calves_flag = _to_num(_col(sights, "calvesPresence"))
    calves_count = _to_num(_col(sights, "individualCountCalves"))
    out["calves_present"] = (calves_flag.fillna(0) > 0) | (calves_count.fillna(0) > 0)
    out["platform_type"] = _col(sights, "platformVLTS", "").astype(str)

    key = ["survey_event_id", "sighting_number"]

    if groups is not None:
        # Vessel surveys: group size lives in a separate MMGroupSizes table.
        grp = pd.DataFrame()
        grp["survey_event_id"] = groups["surveyEventID"].astype(str)
        grp["sighting_number"] = _to_num(groups["sightingNumber"]).astype("Int64")
        grp["group_size_min"] = _to_num(groups["observersCountsMin"])
        grp["group_size_best"] = _to_num(groups["observersCountsBest"])
        grp["group_size_max"] = _to_num(groups["observersCountsMax"])
        grp = grp.drop_duplicates(subset=key, keep="first")
        out = out.merge(grp, on=key, how="left")
    elif "individualCount" in sights.columns:
        # Aerial surveys: group size is recorded inline as individualCount.
        count = _to_num(sights["individualCount"])
        out["group_size_min"] = count
        out["group_size_best"] = count
        out["group_size_max"] = count

    if cues is not None:
        cue = _first_cue(cues)
        cue_out = pd.DataFrame()
        cue_out["survey_event_id"] = cue["surveyEventID"].astype(str)
        cue_out["sighting_number"] = cue["sightingNumber"].astype("Int64")
        cue_out["radial_distance_m"] = _to_num(_col(cue, "sightingDistanceInMeters"))
        cue_out["bearing_deg"] = _to_num(_col(cue, "bearingToAnimals"))
        cue_out["bearing_side"] = _col(cue, "bearingToAnimalsSide", "").astype(str)
        cue_out["perpendicular_distance_m"] = _perpendicular_distance(cue)
        cue_out["sighting_cue"] = _col(cue, "sightingCue", "").astype(str)
        cue_out = cue_out.drop_duplicates(subset=key, keep="first")
        out = out.merge(cue_out, on=key, how="left")
    else:
        # Fallback for any future programme that ships sightings without a
        # cue/distance table: keep the sighting as presence-only.
        out["radial_distance_m"] = np.nan
        out["bearing_deg"] = np.nan
        out["bearing_side"] = ""
        out["perpendicular_distance_m"] = np.nan
        out["sighting_cue"] = ""

    return out


def _tidy_covariates(
    sights: pd.DataFrame,
    effort: pd.DataFrame,
    cues: pd.DataFrame | None,
    multi_platform: bool = False,
) -> pd.DataFrame:
    """One row per sighting: detection-function covariates."""
    out = pd.DataFrame()
    out["survey_event_id"] = sights["surveyEventID"].astype(str)
    out["sighting_number"] = _to_num(sights["sightingNumber"]).astype("Int64")
    out["event_id"] = _to_num(_col(sights, "eventID")).astype("Int64")
    out["platform_type"] = _col(sights, "platformVLTS", "").astype(str)

    # Effort conditions at the sighting's effort point (join on eventID).
    # Aerial sightings have no eventID link, so the join yields NaN and the
    # sighting keeps platform_type only (presence-only record).
    eff = pd.DataFrame()
    eff["event_id"] = _to_num(_col(effort, "eventID")).astype("Int64")
    eff["beaufort"] = _to_num(_col(effort, "beaufortSeaState")).astype("Int64")
    eff["visibility"] = _to_num(_col(effort, "samplingConditionsVisibility")).astype(
        "Int64"
    )
    eff["glare"] = _to_num(_col(effort, "samplingConditionsGlare")).astype("Int64")
    eff["conditions"] = _to_num(_col(effort, "samplingConditionsConditions")).astype(
        "Int64"
    )
    eff["swell_height_ft"] = _to_num(_col(effort, "samplingConditionsSwellHeight"))
    _, double = _on_effort_flags(effort, multi_platform)
    eff["double_platform"] = double
    eff = eff.dropna(subset=["event_id"]).drop_duplicates(
        subset=["event_id"], keep="first"
    )
    out = out.merge(eff, on="event_id", how="left")

    if cues is not None:
        cue = _first_cue(cues)
        cue_out = pd.DataFrame()
        cue_out["survey_event_id"] = cue["surveyEventID"].astype(str)
        cue_out["sighting_number"] = cue["sightingNumber"].astype("Int64")
        cue_out["observation_location"] = _to_num(
            _col(cue, "observationLocation")
        ).astype("Int64")
        cue_out["distance_method"] = _col(cue, "distanceEstimationMethod", "").astype(
            str
        )
        cue_out["observation_height_m"] = _to_num(_col(cue, "observationHeight"))
        cue_out = cue_out.drop_duplicates(
            subset=["survey_event_id", "sighting_number"], keep="first"
        )
        out = out.merge(cue_out, on=["survey_event_id", "sighting_number"], how="left")

    return out


# ── Orchestration ──────────────────────────────────────────


def download_gommapps(accessions: list[str]) -> None:
    """Download every accession and write the three harmonised tidy tables."""
    seg_frames: list[pd.DataFrame] = []
    sight_frames: list[pd.DataFrame] = []
    cov_frames: list[pd.DataFrame] = []

    with httpx.Client(headers={"User-Agent": "marine-risk-mapping/1.0"}) as c:
        for accession in accessions:
            result = _fetch_accession(c, accession)
            if result is None:
                continue
            frames, multi_platform = result
            effort = frames["effort"]
            sights = frames["sights"]
            groups = frames.get("groups")
            cues = frames.get("cues")

            seg = _tidy_segments(effort, multi_platform)
            seg["accession"] = accession
            seg_frames.append(seg)

            sight = _tidy_sightings(sights, groups, cues)
            sight["accession"] = accession
            sight_frames.append(sight)

            cov = _tidy_covariates(sights, effort, cues, multi_platform)
            cov["accession"] = accession
            cov_frames.append(cov)

            platform = "aerial (double-platform)" if multi_platform else "vessel"
            n_dist = int(sight["perpendicular_distance_m"].notna().sum())
            logger.info(
                "  %s (%s): %d effort points, %d sightings (%d with distance)",
                accession,
                platform,
                len(seg),
                len(sight),
                n_dist,
            )

    if not seg_frames:
        logger.error("No GoMMAPPS visual line-transect data was retrieved.")
        return

    GOMMAPPS_DIR.mkdir(parents=True, exist_ok=True)
    segments = pd.concat(seg_frames, ignore_index=True)
    sightings = pd.concat(sight_frames, ignore_index=True)
    covariates = pd.concat(cov_frames, ignore_index=True)

    segments.to_parquet(GOMMAPPS_SEGMENTS_FILE, index=False)
    sightings.to_parquet(GOMMAPPS_SIGHTINGS_FILE, index=False)
    covariates.to_parquet(GOMMAPPS_COVARIATES_FILE, index=False)

    logger.info(
        "Wrote %d effort points -> %s",
        len(segments),
        GOMMAPPS_SEGMENTS_FILE,
    )
    logger.info(
        "Wrote %d sightings -> %s",
        len(sightings),
        GOMMAPPS_SIGHTINGS_FILE,
    )
    logger.info(
        "Wrote %d detection covariate rows -> %s",
        len(covariates),
        GOMMAPPS_COVARIATES_FILE,
    )
    on_effort_sightings = int((sightings["type_vlts"].str.upper() == "F").sum())
    logger.info(
        "On-transect (typeVLTS=F) sightings usable for DSM: %d",
        on_effort_sightings,
    )
    with_distance = int(sightings["perpendicular_distance_m"].notna().sum())
    logger.info(
        "Sightings with perpendicular distance (detection-function ready): %d",
        with_distance,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--accessions",
        nargs="+",
        default=GOMMAPPS_ACCESSIONS,
        help="NCEI accession numbers to download (default: all GoMMAPPS).",
    )
    args = parser.parse_args()
    download_gommapps(args.accessions)


if __name__ == "__main__":
    main()

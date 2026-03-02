#!/usr/bin/env python3
"""
parse_ship_strikes.py

Parses the NOAA 'Confirmed and Possible Ship Strikes to Large Whales' PDF
(noaa_23127_DS1.pdf) into a structured CSV with decimal-degree coordinates.

Source
------
NOAA InPort Record 23127 — Jensen & Silber, Office of Protected Resources.
PDF contains ~292 confirmed/possible ship-whale collision incidents spanning
the 1900s–2002 across global regions.  A subset of entries include lat/lon
coordinates in degree-minute format (e.g. 36-59N, 76-08W).

Layout
------
Pages 1-13:  introductory text, figures, references
Pages 14-39: two-page spreads
    Even pages (14,16,18,...,38): incident records
        Date | Species | Sex | Length | Location | Coordinates | Mortality | ID
    Odd pages (15,17,19,...,39): vessel details
        Vessel Type | Size | Speed | Damage | Source | Comments

The script extracts all incident records from the data (even) pages,
converts degree-minute coordinates to decimal degrees, and writes to CSV.

Output
------
data/processed/ship_strikes/ship_strikes.csv

Usage
-----
    uv run python pipeline/ingestion/parse_ship_strikes.py
"""

import csv
import logging
import re
from pathlib import Path

from PyPDF2 import PdfReader

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── paths ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "data/raw/cetacean/noaa_23127_DS1.pdf"
OUT = ROOT / "data/processed/ship_strikes/ship_strikes.csv"


# ── coordinate helpers ─────────────────────────────────────────────────

# Matches:  36-59N, 76-08W  |  20-46.74N, 156-35.96W  |  38N, 122W
COORD_RE = re.compile(
    r"(\d{1,3})(?:-(\d{1,2}\.?\d*))?\s*([NS])"  # lat
    r"\s*,?\s+"  # separator
    r"(\d{1,3})(?:-(\d{1,2}\.?\d*))?\s*([EW])"  # lon
)


def _dms(deg: str, mins: str | None, direction: str) -> float:
    """Convert degree-minute string components to signed decimal degrees."""
    dd = int(deg) + float(mins or 0) / 60.0
    return round(-dd if direction in "SW" else dd, 6)


def extract_coords(text: str) -> tuple[float | None, float | None]:
    """Return first (lat, lon) pair found in *text*, or (None, None)."""
    m = COORD_RE.search(text)
    if not m:
        return None, None
    return _dms(m[1], m[2], m[3]), _dms(m[4], m[5], m[6])


# ── date regex ─────────────────────────────────────────────────────────
# Records on data pages begin with one of these date formats.
DATE_RE = re.compile(
    r"("
    r"\d{1,2}/\d{1,2}/\d{2,4}"  # MM/DD/YY  or  MM/DD/YYYY
    r"|[A-Z][a-z]{2}-\d{2,4}"  # Mon-YY    (Jul-67, Oct-93)
    r"|\d{1,2}-[A-Z][a-z]{2}"  # DD-Mon    (28-Apr, 30-Jan)
    r"|(?:late |fall |early )\d{4}'?s?"  # late 1980's
    r"|\d{4}'s"  # 1930's
    r"|1[0-9]{3}"  # standalone year 1xxx
    r")"
)

# ── species (longest-first for greedy matching) ────────────────────────
SPECIES = sorted(
    [
        "southern right",
        "balaenopterid",
        "humpback",
        "finback",
        "bryde's",
        "unknown",
        "bowhead",
        "right",
        "sperm",
        "minke",
        "blue",
        "gray",
        "grey",
        "orca",
        "sei",
        "fin",
    ],
    key=len,
    reverse=True,
)

# ── region markers found in the data pages ─────────────────────────────
REGION_MAP = {
    "US East Coast": "US East Coast",
    "Eastern Canada": "Eastern Canada",
    "US and Canada West Coast": "US/Canada West Coast",
    "Alaska and Hawaii": "Alaska/Hawaii",
    "US Gulf Coast": "US Gulf Coast",
    "International": "International",
}


# ── parsing helpers ────────────────────────────────────────────────────


def _match_species(text: str) -> tuple[str, str]:
    """Return (species, remaining_text).

    Word-boundary rule: after matching a species name, the next character
    must NOT be a lowercase letter.  This prevents partial matches
    (e.g. "fin" inside "finback") while still handling the PDF's frequent
    missing-space artifacts like "humpbackApprox" → ("humpback", "Approx").
    """
    t = text.strip()
    lo = t.lower()
    for sp in SPECIES:
        if lo.startswith(sp):
            after = t[len(sp) :]
            if not after or not after[0].islower():
                return sp, after.lstrip(" ,\t\n")
    return "unknown", t


def _match_sex_length(text: str) -> tuple[str | None, float | None, str]:
    """Pull optional sex (M/F) and length (m) from front of text."""
    rest = text.strip()
    sex = None
    length_m = None

    # sex first
    m = re.match(r"^([MF])\b\s*", rest)
    if m:
        sex, rest = m[1], rest[m.end() :].strip()

    # skip qualifiers  (juv), adult, calf, cow/calf, N/A
    rest = re.sub(
        r"^(?:\(?(?:juv|calf|adult|cow/calf\s*pr|cow/cal\s*f\s*pr)\)?\s*)+",
        "",
        rest,
        flags=re.I,
    ).strip()

    # length — trailing whitespace is optional because the PDF often
    # concatenates columns ("8.6Floating in mouth of Chesapeake Bay")
    m = re.match(r"^([\d]+\.?\d*)(?:\s*est)?\s*", rest)
    if m:
        v = float(m[1])
        after = rest[m.end() :]
        # Accept if < 100 m AND next char is not lowercase (prevents
        # consuming "8 mi NW" where "8" is part of the location).
        if v < 100 and (not after or not after[0].islower()):
            length_m, rest = v, after

    # sex after length (sometimes order is reversed)
    if sex is None:
        m = re.match(r"^([MF])\b\s*", rest)
        if m:
            sex, rest = m[1], rest[m.end() :].strip()

    return sex, length_m, rest.strip()


def _classify_mortality(text: str) -> str:
    lo = text.lower()
    if "mortality" in lo or "dead" in lo:
        return "mortality"
    if "no sign of injury" in lo or "no sign of\ninjury" in lo:
        return "no injury"
    if "injur" in lo:
        return "injury"
    return "unknown"


def _extract_location(text: str) -> str:
    """Best-effort extraction of the location string from the record body."""
    loc = text

    # strip coordinate text
    cm = COORD_RE.search(loc)
    if cm:
        loc = loc[: cm.start()] + " " + loc[cm.end() :]

    # strip mortality/injury keywords and everything after
    for kw in ("mortality", "no sign of", "injury", "injured"):
        idx = loc.lower().find(kw)
        if idx >= 0:
            loc = loc[:idx]
            break

    # strip trailing field-ID patterns  (C 124, VM 2388, JEH 465, etc.)
    loc = re.sub(r"\s+[A-Z]{1,5}\s*[-\d]+\s*$", "", loc)
    # strip trailing bare page numbers
    loc = re.sub(r"\s+\d{1,2}\s*$", "", loc)
    # clean
    loc = loc.strip(" ,\t\n")
    # if what's left is just a number, discard
    if re.fullmatch(r"\d{0,3}", loc):
        loc = ""
    return loc


# ── main parsing pipeline ─────────────────────────────────────────────


def _preprocess_page(text: str) -> str:
    """Insert line breaks where the PDF jams columns together."""
    # "mortality10/04/01" → "mortality\n10/04/01"
    text = re.sub(
        r"(mortality|injury|unknown|stranded|"
        r"no sign of\s*injury|Field ID)"
        r"(\d{1,2}/\d{1,2}/\d{2})",
        r"\1\n\2",
        text,
        flags=re.IGNORECASE,
    )
    # "injuryUS Gulf Coast" → "injury\nUS Gulf Coast"
    # "mortalityInternational08/07/02" → "mortality\nInternational\n08/07/02"
    for marker in REGION_MAP:
        text = text.replace(f"injury{marker}", f"injury\n{marker}")
        text = text.replace(f"mortality{marker}", f"mortality\n{marker}")
        text = text.replace(f"unknown{marker}", f"unknown\n{marker}")
        # Region immediately before a date: "West Coast11/04/02"
        text = re.sub(
            re.escape(marker) + r"(\d{1,2}/\d{1,2}/\d{2})",
            marker + r"\n\1",
            text,
        )
    return text


def _split_records(
    text: str,
) -> list[tuple[str, str | None]]:
    """Split preprocessed text into (record_string, new_region|None) tuples.

    Region markers are detected inline and attached as a region-change
    signal to the *following* record.
    """
    lines = text.split("\n")
    buf: list[str] = []
    results: list[tuple[str, str | None]] = []
    pending_region: str | None = None

    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        # skip header noise
        if "NOAA Fisheries" in s:
            continue
        if s.startswith("Date Species"):
            continue
        if re.fullmatch(r"\d{1,2}", s):  # bare page number
            continue

        # ── check for region marker ────────────────────────────────
        matched_region = None
        remainder = ""
        for marker, name in REGION_MAP.items():
            if s == marker:
                matched_region = name
                break
            if s.startswith(marker):
                matched_region = name
                remainder = s[len(marker) :].strip()
                break

        if matched_region:
            # flush buffer as a record under the OLD region
            if buf:
                results.append((" ".join(buf), pending_region))
                buf = []
                pending_region = None
            pending_region = matched_region
            if remainder:
                if DATE_RE.match(remainder):
                    buf = [remainder]
                else:
                    buf.append(remainder)
            continue

        # ── new record starts with a date ──────────────────────────
        if DATE_RE.match(s):
            if buf:
                results.append((" ".join(buf), pending_region))
                pending_region = None
            buf = [s]
        else:
            buf.append(s)

    if buf:
        results.append((" ".join(buf), pending_region))
    return results


def parse_pdf(pdf_path: Path) -> list[dict]:
    """Read the PDF and return a list of parsed incident dicts."""
    reader = PdfReader(str(pdf_path))
    pages = [p.extract_text() or "" for p in reader.pages]
    log.info("Read %d pages from %s", len(pages), pdf_path.name)

    records: list[dict] = []
    region = "US East Coast"  # first data section

    # Data pages are even-numbered starting from page 14 (0-indexed: 13)
    for page_idx in range(len(pages)):
        text = pages[page_idx]
        if not text.strip():
            continue

        # Only process data pages (contain "Date Species Sex" header or
        # have ≥ 3 date patterns and are NOT vessel pages)
        is_data = (
            "Date Species Sex" in text[:200] or "Location (where struck" in text[:200]
        )
        if not is_data:
            continue

        text = _preprocess_page(text)
        split_results = _split_records(text)

        for raw, new_region in split_results:
            if new_region:
                region = new_region

            # Must start with a date
            dm = DATE_RE.match(raw)
            if not dm:
                continue
            date_str = dm[1]
            rest = raw[dm.end() :].strip()

            species, rest = _match_species(rest)
            sex, length_m, rest = _match_sex_length(rest)
            lat, lon = extract_coords(rest)
            mort = _classify_mortality(rest)
            location = _extract_location(rest)

            records.append(
                {
                    "date": date_str,
                    "species": species,
                    "sex": sex,
                    "length_m": length_m,
                    "location": location or None,
                    "latitude": lat,
                    "longitude": lon,
                    "region": region,
                    "mortality_injury": mort,
                    "raw_text": raw[:500],
                }
            )

    return records


# ── entry point ────────────────────────────────────────────────────────


def main() -> None:
    records = parse_pdf(PDF)
    log.info("Parsed %d total incident records", len(records))

    # ── summary stats ──────────────────────────────────────────────────
    geo = [r for r in records if r["latitude"] is not None]
    log.info(
        "  → %d with coordinates (%.0f%%)",
        len(geo),
        100 * len(geo) / max(len(records), 1),
    )

    sp_ct: dict[str, int] = {}
    for r in records:
        sp_ct[r["species"]] = sp_ct.get(r["species"], 0) + 1
    log.info(
        "Species: %s",
        ", ".join(f"{s}={n}" for s, n in sorted(sp_ct.items(), key=lambda x: -x[1])),
    )

    reg_ct: dict[str, int] = {}
    for r in records:
        reg_ct[r["region"]] = reg_ct.get(r["region"], 0) + 1
    log.info("Regions:")
    for reg, n in sorted(reg_ct.items(), key=lambda x: -x[1]):
        log.info("  %-28s %3d records", reg, n)

    mort_ct: dict[str, int] = {}
    for r in records:
        mort_ct[r["mortality_injury"]] = mort_ct.get(r["mortality_injury"], 0) + 1
    log.info(
        "Mortality: %s",
        ", ".join(f"{m}={n}" for m, n in sorted(mort_ct.items(), key=lambda x: -x[1])),
    )

    if geo:
        lats = [r["latitude"] for r in geo]
        lons = [r["longitude"] for r in geo]
        log.info(
            "Coordinate extent: lat [%.2f, %.2f]  lon [%.2f, %.2f]",
            min(lats),
            max(lats),
            min(lons),
            max(lons),
        )

    # ── write CSV ──────────────────────────────────────────────────────
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "date",
        "species",
        "sex",
        "length_m",
        "location",
        "latitude",
        "longitude",
        "region",
        "mortality_injury",
        "raw_text",
    ]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(records)
    log.info("Wrote %s", OUT)


if __name__ == "__main__":
    main()

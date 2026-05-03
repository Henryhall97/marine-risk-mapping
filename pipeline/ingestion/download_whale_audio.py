"""Download publicly available whale vocalisation recordings for classifier training.

Data sources (all open-access, no API keys required):
  1. **Watkins Marine Mammal Sound Database** — WHOI / New Bedford Whaling Museum.
     ~15,000 clips across ~60 species.  Primary mirror on Internet Archive:
     https://archive.org/details/watkins_best_of_whales_202008
     Falls back to WHOI server: https://whoicf2.whoi.edu/science/B/whalesounds/
     NOTE: WHOI periodically goes down for maintenance — IA mirror is preferred.
  2. **Zenodo annotated datasets** — species-specific labelled recordings:
     - Blue whale D/Z calls: zenodo.org/records/3624145
     - Right whale — PAMGuard/DCLDE 2013: zenodo.org/records/13880107
     - Multi-species baleen whale calls: zenodo.org/records/10719537
       (humpback, fin, minke, sei)
     - Killer whale vocalisations: zenodo.org/records/4996664
  3. **Watkins WMMSDB (full database)** — Internet Archive mirror of the
     complete Watkins database (15,254 individual MP3 clips, species-labelled
     via CSV metadata).  Used to gap-fill species missing from the "Best Of"
     zips (blue whale, sei whale).
     https://archive.org/details/wmmsdb
  4. **NOAA/NCEI Passive Acoustic Data** — SanctSound + HARP deployments on GCP
     bucket ``gs://noaa-passive-bioacoustic/``  (large, selective download)

Output directory: data/raw/whale_audio/{species}/

Usage
-----
    uv run python pipeline/ingestion/download_whale_audio.py --source all
    uv run python pipeline/ingestion/download_whale_audio.py --source watkins
    uv run python pipeline/ingestion/download_whale_audio.py --source wmmsdb
    uv run python pipeline/ingestion/download_whale_audio.py \
        --source zenodo --species blue_whale
"""

from __future__ import annotations

import argparse
import io
import logging
import shutil
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    import pandas as pd

from pipeline.config import WHALE_AUDIO_RAW_DIR

log = logging.getLogger(__name__)

# Timeout for HTTP requests (seconds)
HTTP_TIMEOUT = 120

# ── Zenodo dataset registry ─────────────────────────────────
# Each entry: species → record metadata.
# ``file_patterns``: list of case-insensitive substrings that a filename must
# match to be downloaded.  ``None`` means download every file.
# ``extract_zips``: whether zip files should be unpacked (WAVs extracted).
ZENODO_DATASETS: dict[str, dict] = {
    "blue_whale": {
        "record_id": "3624145",
        "description": "Antarctic blue whale D & Z calls",
        "file_patterns": [".wav"],  # only audio files
        "extract_zips": False,
    },
    "right_whale": {
        "record_id": "13880107",
        "description": "Right whale — PAMGuard / DCLDE 2013 Cape Cod Bay",
        "file_patterns": ["wav.zip"],  # only the wav zip, not the model
        "extract_zips": True,
    },
    "humpback_whale": {
        "record_id": "10719537",
        "description": "Baleen whale acoustic occurrence — humpback song",
        "file_patterns": ["HUMPBACK"],
        "extract_zips": False,
    },
    "fin_whale": {
        "record_id": "10719537",
        "description": "Baleen whale doublets — fin whale",
        "file_patterns": ["FIN_WHALE"],
        "extract_zips": False,
    },
    "minke_whale": {
        "record_id": "10719537",
        "description": "Baleen whale bioducks / song — minke",
        "file_patterns": ["MINKE"],
        "extract_zips": False,
    },
    "sei_whale": {
        "record_id": "10719537",
        "description": "Baleen whale upsweeps — sei whale",
        "file_patterns": ["SEI"],
        "extract_zips": False,
    },
    "killer_whale": {
        "record_id": "4996664",
        "description": "Killer whale vocalisations — Bremer Canyon, Australia",
        "file_patterns": [".zip"],
        "extract_zips": True,
    },
}

# ── Watkins database ────────────────────────────────────────
# The Watkins database organises clips by species under a consistent URL scheme.
# We target the 6 species we care about.
WATKINS_BASE_URL = "https://whoicf2.whoi.edu/science/B/whalesounds/bestOf.cfm"
WATKINS_SPECIES: dict[str, str] = {
    "right_whale": "Eubalaena glacialis",
    "humpback_whale": "Megaptera novaeangliae",
    "fin_whale": "Balaenoptera physalus",
    "blue_whale": "Balaenoptera musculus",
    "sperm_whale": "Physeter macrocephalus",
    "minke_whale": "Balaenoptera acutorostrata",
    "sei_whale": "Balaenoptera borealis",
    "killer_whale": "Orcinus orca",
}

# Alternative: Best-of-CUTs zip bundles (more reliable programmatic access)
WATKINS_BESTOF_ZIPS: dict[str, str] = {
    "right_whale": "https://whoicf2.whoi.edu/science/B/whalesounds/zip/Best_of_RightWhale.zip",
    "humpback_whale": "https://whoicf2.whoi.edu/science/B/whalesounds/zip/Best_of_HumpbackWhale.zip",
    "fin_whale": "https://whoicf2.whoi.edu/science/B/whalesounds/zip/Best_of_FinWhale.zip",
    "blue_whale": "https://whoicf2.whoi.edu/science/B/whalesounds/zip/Best_of_BlueWhale.zip",
    "sperm_whale": "https://whoicf2.whoi.edu/science/B/whalesounds/zip/Best_of_SpermWhale.zip",
    "minke_whale": "https://whoicf2.whoi.edu/science/B/whalesounds/zip/Best_of_MinkeWhale.zip",
    "sei_whale": "https://whoicf2.whoi.edu/science/B/whalesounds/zip/Best_of_SeiWhale.zip",
    "killer_whale": "https://whoicf2.whoi.edu/science/B/whalesounds/zip/Best_of_KillerWhale.zip",
}

# ── Internet Archive mirror of Watkins "Best Of" zips ──────
# Uploaded by a third party in Aug 2020 — reliable when WHOI is down.
INTERNET_ARCHIVE_WATKINS_BASE = (
    "https://archive.org/download/watkins_best_of_whales_202008"
)
INTERNET_ARCHIVE_WATKINS: dict[str, str] = {
    "right_whale": f"{INTERNET_ARCHIVE_WATKINS_BASE}/northern_right_whale.zip",
    "humpback_whale": f"{INTERNET_ARCHIVE_WATKINS_BASE}/humpback_whale.zip",
    "fin_whale": f"{INTERNET_ARCHIVE_WATKINS_BASE}/finback_whale.zip",
    "sperm_whale": f"{INTERNET_ARCHIVE_WATKINS_BASE}/sperm_whale.zip",
    "minke_whale": f"{INTERNET_ARCHIVE_WATKINS_BASE}/minke_whale.zip",
    "killer_whale": f"{INTERNET_ARCHIVE_WATKINS_BASE}/killer_whale.zip",
}

# ── WMMSDB — full Watkins database on Internet Archive ──────
# 15,254 individual MP3 clips identified by numeric recording codes.
# We use the raw-source.csv metadata (GS column = scientific name,
# RN column = recording code / filename stem) to select species.
#
# IMPORTANT: the GS column contains compound annotations like
#   "Orcinus orca  BE7A | Ambient X"
# We parse the PRIMARY species (text before " | ", stripped) so that
# noise-tagged variants are grouped with clean clips for the same species.
WMMSDB_BASE_URL = "https://archive.org/download/wmmsdb"
WMMSDB_CSV_URL = f"{WMMSDB_BASE_URL}/data/raw-source.csv"

# Critical-pass gap-fill species from WMMSDB.
# Blue whale and sei whale are under-represented in the Best-Of zips.
# Sperm whale is listed under its old synonym "Physeter catodon" in WMMSDB.
# Bowhead (bowhead_whale) is ESA-listed and has 306 clean clips.
WMMSDB_SPECIES: dict[str, str] = {
    # species_key → substring to match in the PRIMARY scientific name
    "blue_whale": "musculus",
    "sei_whale": "borealis",
    "sperm_whale": "catodon",  # Physeter catodon = old synonym
    "bowhead_whale": "mysticetus",
}

# Broad-pass species from WMMSDB — non-critical cetaceans only.
# Ordered by confirmed clip count from audit (highest first).
# harbor_porpoise / phocoenoides (Dall's) EXCLUDED: ultrasonic clicks
# (100-150 kHz) are outside our AUDIO_FMAX=8000 Hz mel pipeline.
# Non-cetaceans (walrus, seals, manatee) are listed in
# WMMSDB_HARD_NEGATIVE_SPECIES below — used for unknown_cetacean training.
WMMSDB_BROAD_SPECIES: dict[str, str] = {
    "spotted_dolphin": "attenuata",
    "long_finned_pilot_whale": "melaena",
    "atlantic_white_sided_dolphin": "acutus",
    "spinner_dolphin": "longirostris",
    "striped_dolphin": "coeruleoalba",
    "rissos_dolphin": "griseus",
    "clymene_dolphin": "clymene",
    "common_dolphin": "delphis",
    "atlantic_spotted_dolphin": "frontalis",
    "short_finned_pilot_whale": "macrorhynchus",
    "bottlenose_dolphin": "truncatus",
    "beluga": "leucas",
    "narwhal": "monoceros",
    "gray_whale": "robustus",
}

# Rare-pass species (5–19 WMMSDB clips) — used to build embedding library
# only, never trained with a softmax head.
WMMSDB_RARE_SPECIES: dict[str, str] = {
    "amazon_river_dolphin": "geoffrensis",
    "heavisides_dolphin": "heavisidii",
    "tucuxi": "fluviatilis",
    "melon_headed_whale": "electra",
    "lagenodelphis_dolphin": "hosei",
}

# Hard-negative sources — non-cetacean marine mammals with audible
# sub-8kHz calls. Their clips are mixed into other_cetacean /
# unknown_cetacean training pools but are never prediction targets.
WMMSDB_HARD_NEGATIVE_SPECIES: dict[str, str] = {
    "walrus": "rosmarus",
    "weddell_seal": "weddelli",
    "manatee": "manatus",
}

# ── NOAA SanctSound ─────────────────────────────────────────
# SanctSound provides continuous recordings from NOAA sanctuaries.
# We download the metadata catalogue first, then selectively fetch clips
# that overlap with known whale call periods.
SANCTSOUND_CATALOG_URL = "https://sanctsound.ioos.us/api/v1/deployments"


# ── Download functions ──────────────────────────────────────


def _download_watkins_zip(
    url: str,
    sp: str,
    sp_dir: Path,
    *,
    allow_redirects: bool,
) -> int:
    """Download a single Watkins zip and extract audio files.

    Returns the number of audio files extracted, or -1 on failure.
    """
    resp = requests.get(
        url,
        timeout=HTTP_TIMEOUT,
        stream=True,
        allow_redirects=allow_redirects,
    )

    # WHOI redirects to maintenance; IA redirects to CDN (expected)
    if not allow_redirects and resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get("Location", "unknown")
        log.warning(
            "Watkins/%s: redirected to %s — likely maintenance",
            sp,
            location,
        )
        return -1

    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    if "html" in content_type.lower() or "text" in content_type.lower():
        log.warning("Watkins/%s: got %s instead of zip", sp, content_type)
        return -1

    try:
        n = _extract_audio_from_zip(resp.content, sp_dir, f"Watkins/{sp}")
    except zipfile.BadZipFile:
        log.error("Watkins/%s: not a valid zip file", sp)
        return -1
    return n


def download_watkins(
    species: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, int]:
    """Download Best-of-CUTs zip bundles from the Watkins database.

    Tries Internet Archive mirror first (reliable), then falls back to the
    original WHOI server (which may be in maintenance).

    Returns dict of {species: n_files_downloaded}.
    """
    output_dir = output_dir or WHALE_AUDIO_RAW_DIR
    species = species or list(WATKINS_BESTOF_ZIPS.keys())
    stats: dict[str, int] = {}

    for sp in species:
        sp_dir = output_dir / sp / "watkins"
        sp_dir.mkdir(parents=True, exist_ok=True)

        # Check if already downloaded
        existing = list(sp_dir.glob("*.wav")) + list(sp_dir.glob("*.aif"))
        if existing:
            log.info(
                "Watkins/%s: %d files already present -- skipping",
                sp,
                len(existing),
            )
            stats[sp] = len(existing)
            continue

        # --- Try Internet Archive mirror first (allow_redirects=True for CDN) ---
        ia_url = INTERNET_ARCHIVE_WATKINS.get(sp)
        if ia_url:
            log.info("Downloading Watkins/%s from Internet Archive", sp)
            try:
                n = _download_watkins_zip(
                    ia_url,
                    sp,
                    sp_dir,
                    allow_redirects=True,
                )
                if n > 0:
                    stats[sp] = n
                    continue
                elif n == 0:
                    log.warning("Watkins/%s: IA zip was empty", sp)
            except requests.RequestException as exc:
                log.warning("Watkins/%s: IA download failed (%s)", sp, exc)

        # --- Fall back to WHOI (allow_redirects=False to detect maintenance) ---
        whoi_url = WATKINS_BESTOF_ZIPS.get(sp)
        if whoi_url:
            log.info("Trying WHOI server for Watkins/%s", sp)
            try:
                n = _download_watkins_zip(
                    whoi_url,
                    sp,
                    sp_dir,
                    allow_redirects=False,
                )
                if n > 0:
                    stats[sp] = n
                    continue
            except requests.RequestException as exc:
                log.warning("Watkins/%s: WHOI download failed (%s)", sp, exc)

        # Both sources failed
        if sp not in stats:
            log.error("Watkins/%s: no source available", sp)
            stats[sp] = 0

    return stats


_AUDIO_EXTENSIONS = (".wav", ".aif", ".aiff", ".mp3", ".flac", ".ogg")


def _extract_audio_from_zip(
    raw_bytes: bytes,
    output_dir: Path,
    label: str,
) -> int:
    """Extract audio files from a zip, handling nested zips (zip-in-zip).

    Returns the number of audio files written.
    """
    n_audio = 0
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        for member in zf.namelist():
            if member.startswith("__MACOSX") or member.endswith("/"):
                continue

            if member.lower().endswith(_AUDIO_EXTENSIONS):
                target = output_dir / Path(member).name
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                n_audio += 1

            elif member.lower().endswith(".zip"):
                # Recursively extract nested zips
                inner_bytes = zf.read(member)
                try:
                    n_audio += _extract_audio_from_zip(inner_bytes, output_dir, label)
                except zipfile.BadZipFile:
                    log.warning(
                        "%s: nested zip %s is invalid — skipping", label, member
                    )

    log.info("%s: extracted %d audio files", label, n_audio)
    return n_audio


def _parse_primary_gs(gs_value: str) -> str:
    """Extract the primary scientific name from a WMMSDB GS cell.

    The GS column often contains compound annotations, e.g.:
        "Orcinus orca  BE7A | Ambient X"
        "Physeter catodon  BA2A | Ship noise  X"
    We want only the part before " | " (the primary species), stripped of
    the recording-code suffix (all-caps token).  This ensures that
    noise-contaminated variants are grouped with clean clips for the same
    species rather than appearing as separate rows in the species tally.

    Examples
    --------
    >>> _parse_primary_gs("Orcinus orca  BE7A | Ambient X")
    "orcinus orca"
    >>> _parse_primary_gs("Physeter catodon  BA2A")
    "physeter catodon"
    """
    primary = gs_value.split("|")[0].strip()
    # Strip trailing recording-code tokens (all-uppercase, no spaces)
    tokens = primary.split()
    clean_tokens = [t for t in tokens if not (t.isupper() and len(t) <= 8)]
    return " ".join(clean_tokens).lower().strip()


def download_wmmsdb(
    species: list[str] | None = None,
    output_dir: Path | None = None,
    species_mapping: dict[str, str] | None = None,
    hard_negatives_mapping: dict[str, str] | None = None,
) -> dict[str, int]:
    """Download individual clips from the full Watkins database on Internet Archive.

    Uses the raw-source.csv metadata to identify recordings by scientific name.
    Parses the PRIMARY species from compound GS annotations (text before \" | \")
    so noise-tagged variants are correctly grouped with their species.

    Parameters
    ----------
    species_mapping :
        Dict mapping ``species_key → scientific-name substring`` for the
        primary GS name.  Defaults to ``WMMSDB_SPECIES``.
    hard_negatives_mapping :
        Optional additional dict of non-target species whose clips should be
        downloaded into an ``_hard_negatives/`` subdirectory of ``output_dir``
        for use in ``other_cetacean`` / ``unknown_cetacean`` training.

    Returns dict of {species: n_files_downloaded}.
    """
    import csv as csv_mod

    output_dir = output_dir or WHALE_AUDIO_RAW_DIR
    mapping = species_mapping or WMMSDB_SPECIES
    species = species or list(mapping.keys())
    stats: dict[str, int] = {}

    # Download the metadata CSV once
    log.info("Fetching WMMSDB metadata from %s", WMMSDB_CSV_URL)
    try:
        resp = requests.get(WMMSDB_CSV_URL, timeout=HTTP_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Failed to download WMMSDB metadata: %s", exc)
        return {sp: 0 for sp in species}

    reader = csv_mod.DictReader(resp.text.splitlines())
    rows = list(reader)
    log.info("WMMSDB metadata: %d records loaded", len(rows))

    # Build a list of (primary_gs, recording_id) pairs once for efficiency
    parsed_rows: list[tuple[str, str]] = []
    for r in rows:
        gs_raw = r.get("GS", "")
        rn = r.get("RN", "").strip()
        if rn:
            parsed_rows.append((_parse_primary_gs(gs_raw), rn))

    def _download_species_set(
        sp_mapping: dict[str, str],
        sp_list: list[str],
        base_dir: Path,
        label: str,
    ) -> dict[str, int]:
        result: dict[str, int] = {}
        for sp in sp_list:
            search_term = sp_mapping.get(sp)
            if not search_term:
                log.info("No WMMSDB mapping for '%s' — skipping", sp)
                result[sp] = 0
                continue

            sp_dir = base_dir / sp / "watkins"
            sp_dir.mkdir(parents=True, exist_ok=True)

            existing = [
                f for f in sp_dir.iterdir() if f.suffix.lower() in _AUDIO_EXTENSIONS
            ]
            if existing:
                log.info(
                    "%s/%s: %d files already present — skipping",
                    label,
                    sp,
                    len(existing),
                )
                result[sp] = len(existing)
                continue

            # Match on primary GS (parsed, lowercased)
            rec_ids = [
                rn
                for primary_gs, rn in parsed_rows
                if search_term.lower() in primary_gs
            ]
            log.info(
                "%s/%s: found %d recordings matching '%s' in primary GS",
                label,
                sp,
                len(rec_ids),
                search_term,
            )

            n_downloaded = 0
            for rid in rec_ids:
                mp3_url = f"{WMMSDB_BASE_URL}/{rid}.mp3"
                target = sp_dir / f"{rid}.mp3"
                if target.exists():
                    n_downloaded += 1
                    continue
                try:
                    file_resp = requests.get(
                        mp3_url,
                        timeout=HTTP_TIMEOUT,
                        allow_redirects=True,
                    )
                    file_resp.raise_for_status()
                    ct = file_resp.headers.get("Content-Type", "")
                    if "html" in ct.lower():
                        log.warning(
                            "%s/%s: %s returned HTML — skipping",
                            label,
                            sp,
                            rid,
                        )
                        continue
                    target.write_bytes(file_resp.content)
                    n_downloaded += 1
                    log.info(
                        "%s/%s: downloaded %s (%.0f KB)",
                        label,
                        sp,
                        rid,
                        len(file_resp.content) / 1024,
                    )
                except requests.RequestException as exc:
                    log.warning(
                        "%s/%s: failed to download %s: %s",
                        label,
                        sp,
                        rid,
                        exc,
                    )

            result[sp] = n_downloaded
            log.info("%s/%s: %d audio files ready", label, sp, n_downloaded)
        return result

    # ── Primary species ──────────────────────────────────────
    stats.update(_download_species_set(mapping, species, output_dir, "WMMSDB"))

    # ── Hard negatives ───────────────────────────────────────
    if hard_negatives_mapping:
        neg_dir = output_dir / "_hard_negatives"
        neg_dir.mkdir(parents=True, exist_ok=True)
        hn_stats = _download_species_set(
            hard_negatives_mapping,
            list(hard_negatives_mapping.keys()),
            neg_dir,
            "WMMSDB/hard_neg",
        )
        log.info(
            "Hard negatives: %d species downloaded",
            sum(1 for v in hn_stats.values() if v > 0),
        )

    return stats


def download_zenodo(
    species: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, int]:
    """Download annotated datasets from Zenodo.

    Supports file_patterns filtering (case-insensitive substring match) and
    automatic zip extraction when ``extract_zips`` is True.

    Returns dict of {species: n_audio_files_downloaded}.
    """
    output_dir = output_dir or WHALE_AUDIO_RAW_DIR
    species = species or list(ZENODO_DATASETS.keys())
    stats: dict[str, int] = {}

    for sp in species:
        meta = ZENODO_DATASETS.get(sp)
        if not meta:
            log.info("No Zenodo dataset for species '%s' — skipping", sp)
            continue

        sp_dir = output_dir / sp / "zenodo"
        sp_dir.mkdir(parents=True, exist_ok=True)

        # Check if audio files already exist
        existing_audio = [
            f
            for f in sp_dir.iterdir()
            if f.suffix.lower() in (".wav", ".aif", ".aiff", ".mp3", ".flac", ".ogg")
        ]
        if existing_audio:
            log.info(
                "Zenodo/%s: %d audio files already present — skipping",
                sp,
                len(existing_audio),
            )
            stats[sp] = len(existing_audio)
            continue

        record_id = meta["record_id"]
        file_patterns = meta.get("file_patterns")  # list[str] | None
        extract_zips = meta.get("extract_zips", False)
        api_url = f"https://zenodo.org/api/records/{record_id}"

        log.info("Fetching Zenodo record %s for %s", record_id, sp)
        try:
            resp = requests.get(api_url, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            record = resp.json()

            files = record.get("files", [])

            # Filter files by patterns if specified
            if file_patterns:
                files = [
                    f
                    for f in files
                    if any(pat.lower() in f["key"].lower() for pat in file_patterns)
                ]

            n_audio = 0
            for f in files:
                fname = f["key"]
                furl = f["links"]["self"]
                fsize = f.get("size", 0)

                # Skip very large files (> 500 MB) to avoid filling disk
                if fsize > 500 * 1024 * 1024:
                    log.warning(
                        "Zenodo/%s: skipping %s (%.0f MB — too large)",
                        sp,
                        fname,
                        fsize / 1024 / 1024,
                    )
                    continue

                log.info(
                    "Downloading %s (%.1f MB)",
                    fname,
                    fsize / 1024 / 1024,
                )
                file_resp = requests.get(furl, timeout=300, stream=True)
                file_resp.raise_for_status()

                if extract_zips and fname.lower().endswith(".zip"):
                    # Download and extract zip — keep only audio files
                    # Handles nested zips (zip-within-zip) automatically
                    try:
                        raw_bytes = file_resp.content
                        n_audio += _extract_audio_from_zip(raw_bytes, sp_dir, sp)
                    except zipfile.BadZipFile:
                        log.error(
                            "Zenodo/%s: %s is not a valid zip — skipping",
                            sp,
                            fname,
                        )
                else:
                    # Direct file download
                    target = sp_dir / fname
                    with open(target, "wb") as dst:
                        for chunk in file_resp.iter_content(chunk_size=8192):
                            dst.write(chunk)

                    # Count only audio files
                    if target.suffix.lower() in (
                        ".wav",
                        ".aif",
                        ".aiff",
                        ".mp3",
                        ".flac",
                        ".ogg",
                    ):
                        n_audio += 1

            stats[sp] = n_audio
            log.info("Zenodo/%s: %d audio files ready", sp, n_audio)

        except requests.RequestException as exc:
            log.error("Failed to download Zenodo/%s: %s", sp, exc)
            stats[sp] = 0

    return stats


def download_sanctsound_catalog(
    output_dir: Path | None = None,
) -> Path | None:
    """Download the SanctSound deployment catalogue JSON.

    This is a lightweight metadata-only call. Actual audio files are large
    (continuous recordings) and should be fetched selectively for specific
    sanctuaries and date ranges.
    """
    output_dir = output_dir or WHALE_AUDIO_RAW_DIR / "sanctsound"
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_file = output_dir / "deployments.json"

    if catalog_file.exists():
        log.info("SanctSound catalogue already exists at %s", catalog_file)
        return catalog_file

    log.info("Downloading SanctSound deployment catalogue")
    try:
        resp = requests.get(SANCTSOUND_CATALOG_URL, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        catalog_file.write_text(resp.text)
        log.info("SanctSound catalogue saved to %s", catalog_file)
        return catalog_file
    except requests.RequestException as exc:
        log.error("Failed to download SanctSound catalogue: %s", exc)
        return None


# ── Manifest / inventory ────────────────────────────────────


def build_training_manifest(
    audio_dir: Path | None = None,
) -> pd.DataFrame:
    """Scan downloaded audio and build a training manifest CSV.

    Returns DataFrame with columns: file_path, species, source, duration_sec
    (duration requires librosa to compute).
    """
    import pandas as pd

    audio_dir = audio_dir or WHALE_AUDIO_RAW_DIR
    rows = []

    for species_dir in sorted(audio_dir.iterdir()):
        if not species_dir.is_dir():
            continue
        species = species_dir.name
        for source_dir in sorted(species_dir.iterdir()):
            if not source_dir.is_dir():
                continue
            source = source_dir.name
            for audio_file in sorted(source_dir.iterdir()):
                suffix = audio_file.suffix.lower()
                if suffix in (".wav", ".aif", ".aiff", ".mp3", ".flac", ".ogg"):
                    rows.append(
                        {
                            "file_path": str(audio_file),
                            "species": species,
                            "source": source,
                            "filename": audio_file.name,
                        }
                    )

    df = pd.DataFrame(rows)

    # Optionally add duration (slow — requires reading each file)
    try:
        import librosa

        durations = []
        for fp in df["file_path"]:
            try:
                dur = librosa.get_duration(path=fp)
            except Exception:
                dur = None
            durations.append(dur)
        df["duration_sec"] = durations
    except ImportError:
        df["duration_sec"] = None

    # Save manifest
    manifest_path = audio_dir / "training_manifest.csv"
    df.to_csv(manifest_path, index=False)
    log.info(
        "Training manifest: %d files across %d species → %s",
        len(df),
        df["species"].nunique(),
        manifest_path,
    )
    return df


# ── CLI ─────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Download whale vocalisation training data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        choices=["watkins", "wmmsdb", "zenodo", "sanctsound", "all"],
        default="all",
        help="Which data source(s) to download",
    )
    parser.add_argument(
        "--species",
        nargs="*",
        default=None,
        help="Limit to specific species (e.g. right_whale humpback_whale)",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Skip downloads, just rebuild the training manifest from existing files",
    )
    parser.add_argument(
        "--stage",
        choices=["critical", "broad", "rare"],
        default="critical",
        help=(
            "Download stage: 'critical' fetches the 9 ESA-listed large-whale "
            "species incl. bowhead (default). 'broad' fetches ~14 non-critical "
            "cetaceans for the second-pass classifier. 'rare' downloads rare "
            "species for embedding library plus hard negatives "
            "(walrus/seal/manatee) for other_cetacean training."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    WHALE_AUDIO_RAW_DIR.mkdir(parents=True, exist_ok=True)

    if args.manifest_only:
        build_training_manifest()
        return

    if args.source in ("watkins", "all"):
        log.info("=" * 60)
        log.info("WATKINS MARINE MAMMAL SOUND DATABASE")
        log.info("=" * 60)
        stats = download_watkins(species=args.species)
        for sp, n in stats.items():
            log.info("  %-20s %d files", sp, n)

    if args.source in ("wmmsdb", "all"):
        log.info("=" * 60)
        log.info("WMMSDB — FULL WATKINS DATABASE (gap-fill)")
        log.info("=" * 60)
        if args.stage == "broad":
            wmmsdb_mapping = WMMSDB_BROAD_SPECIES
        elif args.stage == "rare":
            wmmsdb_mapping = WMMSDB_RARE_SPECIES
        else:
            wmmsdb_mapping = WMMSDB_SPECIES
        hard_negs = WMMSDB_HARD_NEGATIVE_SPECIES if args.stage == "rare" else None
        wmmsdb_species = args.species or list(wmmsdb_mapping.keys())
        stats = download_wmmsdb(
            species=wmmsdb_species,
            species_mapping=wmmsdb_mapping,
            hard_negatives_mapping=hard_negs,
        )
        for sp, n in stats.items():
            log.info("  %-20s %d files", sp, n)

    if args.source in ("zenodo", "all"):
        log.info("=" * 60)
        log.info("ZENODO ANNOTATED DATASETS")
        log.info("=" * 60)
        stats = download_zenodo(species=args.species)
        for sp, n in stats.items():
            log.info("  %-20s %d files", sp, n)

    if args.source in ("sanctsound", "all"):
        log.info("=" * 60)
        log.info("NOAA SANCTSOUND CATALOGUE")
        log.info("=" * 60)
        download_sanctsound_catalog()

    # Build manifest from everything downloaded
    log.info("=" * 60)
    log.info("BUILDING TRAINING MANIFEST")
    log.info("=" * 60)
    df = build_training_manifest()
    if not df.empty:
        print("\nTraining data summary:")
        print(df.groupby("species")["filename"].count().to_string())
    else:
        print("\nNo training data found. Check download logs above.")


if __name__ == "__main__":
    main()

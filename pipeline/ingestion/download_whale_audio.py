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
# Only used for species NOT covered by the "Best Of" zips above.
WMMSDB_BASE_URL = "https://archive.org/download/wmmsdb"
WMMSDB_CSV_URL = f"{WMMSDB_BASE_URL}/data/raw-source.csv"
WMMSDB_SPECIES: dict[str, str] = {
    # species_key → substring to match in the GS (Genus Species) CSV column
    "blue_whale": "musculus",
    "sei_whale": "borealis",
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


def download_wmmsdb(
    species: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, int]:
    """Download individual clips from the full Watkins database on Internet Archive.

    Uses the raw-source.csv metadata to identify recordings by scientific name,
    then fetches each MP3 individually.  Intended for species not covered by
    the "Best Of" zip bundles (blue whale, sei whale).

    Returns dict of {species: n_files_downloaded}.
    """
    import csv as csv_mod

    output_dir = output_dir or WHALE_AUDIO_RAW_DIR
    species = species or list(WMMSDB_SPECIES.keys())
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

    for sp in species:
        search_term = WMMSDB_SPECIES.get(sp)
        if not search_term:
            log.info("No WMMSDB mapping for '%s' — skipping", sp)
            stats[sp] = 0
            continue

        sp_dir = output_dir / sp / "watkins"
        sp_dir.mkdir(parents=True, exist_ok=True)

        # Check if we already have watkins files (from Best-Of zips or previous run)
        existing = [
            f for f in sp_dir.iterdir() if f.suffix.lower() in _AUDIO_EXTENSIONS
        ]
        if existing:
            log.info(
                "WMMSDB/%s: %d files already present -- skipping",
                sp,
                len(existing),
            )
            stats[sp] = len(existing)
            continue

        # Find matching recording IDs
        rec_ids = [
            r["RN"]
            for r in rows
            if search_term.lower() in r.get("GS", "").lower()
            and r.get("RN", "").strip()
        ]
        log.info(
            "WMMSDB/%s: found %d recordings matching '%s'",
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
                # Verify we got audio, not an error page
                ct = file_resp.headers.get("Content-Type", "")
                if "html" in ct.lower():
                    log.warning("WMMSDB/%s: %s returned HTML — skipping", sp, rid)
                    continue
                target.write_bytes(file_resp.content)
                n_downloaded += 1
                log.info(
                    "WMMSDB/%s: downloaded %s (%.0f KB)",
                    sp,
                    rid,
                    len(file_resp.content) / 1024,
                )
            except requests.RequestException as exc:
                log.warning("WMMSDB/%s: failed to download %s: %s", sp, rid, exc)

        stats[sp] = n_downloaded
        log.info("WMMSDB/%s: %d audio files ready", sp, n_downloaded)

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
        stats = download_wmmsdb(species=args.species)
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

"""Audit available training data across all cetacean classification sources.

Fetches lightweight metadata (no audio/image downloads) and prints:
  - WMMSDB: clip counts per species, tiered by sample size
  - Happywhale (if train.csv is already downloaded): image counts per species
  - Suggests three-pass tier assignments based on sample thresholds

Usage
-----
    uv run python pipeline/analysis/audit_training_data.py
    uv run python pipeline/analysis/audit_training_data.py --thresholds 100 30 10
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    import pandas as pd

log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────
WMMSDB_CSV_URL = "https://archive.org/download/wmmsdb/data/raw-source.csv"
HTTP_TIMEOUT = 60

# Pass assignment thresholds (clips / images)
# Species with ≥ CRITICAL_MIN are candidates for the critical model.
# Species with ≥ BROAD_MIN are candidates for the broad model.
# Species with ≥ RARE_MIN are candidates for the rare/few-shot model.
# Species below RARE_MIN are noted but excluded from training.
DEFAULT_THRESHOLDS = (50, 20, 5)

# Our existing critical species (8 ESA-listed large whales)
# — used to label them in the audit even if they have many clips.
CRITICAL_SPECIES_KEYS = {
    "musculus",  # blue whale
    "novaeangliae",  # humpback
    "physalus",  # fin whale
    "macrocephalus",  # sperm whale
    "acutorostrata",  # minke whale
    "borealis",  # sei whale
    "glacialis",  # right whale (also robustus/australis)
    "orca",  # killer whale
}

# Human-readable name mapping for display (GS column → common name)
COMMON_NAMES: dict[str, str] = {
    # Critical
    "Balaenoptera musculus": "Blue whale",
    "Megaptera novaeangliae": "Humpback whale",
    "Balaenoptera physalus": "Fin whale",
    "Physeter macrocephalus": "Sperm whale",
    "Balaenoptera acutorostrata": "Minke whale",
    "Balaenoptera borealis": "Sei whale",
    "Eubalaena glacialis": "N. Right whale",
    "Eubalaena australis": "S. Right whale",
    "Eubalaena japonica": "N. Pacific Right whale",
    "Orcinus orca": "Killer whale",
    # Broad / dolphin
    "Tursiops truncatus": "Bottlenose dolphin",
    "Delphinus delphis": "Common dolphin",
    "Stenella attenuata": "Spotted dolphin",
    "Stenella coeruleoalba": "Striped dolphin",
    "Globicephala macrorhynchus": "S.F. Pilot whale",
    "Globicephala melas": "L.F. Pilot whale",
    "Delphinapterus leucas": "Beluga",
    "Monodon monoceros": "Narwhal",
    "Eschrichtius robustus": "Gray whale",
    "Balaena mysticetus": "Bowhead whale",
    "Phocoena phocoena": "Harbor porpoise",
    "Ziphius cavirostris": "Cuvier's beaked whale",
    # Rarer / additional
    "Kogia breviceps": "Pygmy sperm whale",
    "Kogia sima": "Dwarf sperm whale",
    "Grampus griseus": "Risso's dolphin",
    "Pseudorca crassidens": "False killer whale",
    "Lagenorhynchus obliquidens": "Pacific white-sided dolphin",
    "Lagenorhynchus acutus": "Atlantic white-sided dolphin",
    "Stenella longirostris": "Spinner dolphin",
    "Stenella frontalis": "Atlantic spotted dolphin",
    "Cephalorhynchus commersonii": "Commerson's dolphin",
    "Sotalia fluviatilis": "Tucuxi",
    "Inia geoffrensis": "Amazon river dolphin",
    "Pontoporia blainvillei": "La Plata dolphin",
    "Berardius bairdii": "Baird's beaked whale",
    "Mesoplodon densirostris": "Blainville's beaked whale",
    "Hyperoodon ampullatus": "N. Bottlenose whale",
    "Balaenoptera edeni": "Bryde's whale",
    "Caperea marginata": "Pygmy right whale",
    "Neophocaena phocaenoides": "Indo-Pacific porpoise",
}

# Species known to have primary vocalizations above 8 kHz
# — our mel spectrogram pipeline (AUDIO_FMAX=8000) can't capture them reliably
HIGH_FREQ_SPECIES_SUBSTRINGS = {
    "phocoena",  # harbor porpoise (100-150 kHz echolocation clicks)
    "phocaenoid",  # all porpoises
    "neophocaena",  # Indo-Pacific finless porpoise
}


# ── WMMSDB audit ─────────────────────────────────────────────


def fetch_wmmsdb_csv() -> pd.DataFrame:
    """Download the WMMSDB metadata CSV (~500 KB) and return as DataFrame."""
    import pandas as pd

    log.info("Fetching WMMSDB metadata CSV from Internet Archive...")
    try:
        resp = requests.get(WMMSDB_CSV_URL, timeout=HTTP_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Failed to fetch WMMSDB CSV: %s", exc)
        sys.exit(1)

    log.info("Downloaded %d bytes", len(resp.content))
    df = pd.read_csv(io.StringIO(resp.text), on_bad_lines="skip")
    log.info("WMMSDB: %d records, columns: %s", len(df), list(df.columns))
    return df


def audit_wmmsdb(
    thresholds: tuple[int, int, int],
) -> list[dict]:
    """Fetch WMMSDB CSV, count clips per species, assign tiers.

    Returns list of dicts sorted by clip count descending.
    """
    df = fetch_wmmsdb_csv()

    # Identify the species column — try common names
    gs_col = None
    for candidate in ("GS", "gs", "Species", "species", "scientific_name"):
        if candidate in df.columns:
            gs_col = candidate
            break
    if gs_col is None:
        log.error(
            "Cannot find species column in WMMSDB CSV. Columns are: %s",
            list(df.columns),
        )
        sys.exit(1)

    log.info("Using species column: '%s'", gs_col)

    counts = df[gs_col].str.strip().value_counts().reset_index()
    counts.columns = ["scientific_name", "clips"]

    critical_min, broad_min, rare_min = thresholds
    rows = []
    for _, row in counts.iterrows():
        sci = str(row["scientific_name"])
        n = int(row["clips"])
        sci_lower = sci.lower()

        # Determine if this is one of our current critical species
        is_critical = any(k in sci_lower for k in CRITICAL_SPECIES_KEYS)

        # Determine if primary vocalizations are above our AUDIO_FMAX
        high_freq = any(h in sci_lower for h in HIGH_FREQ_SPECIES_SUBSTRINGS)

        common = COMMON_NAMES.get(sci, "")

        if is_critical:
            tier = "CRITICAL"
        elif high_freq:
            tier = "HIGH-FREQ (skip)"
        elif n >= critical_min:
            tier = "broad"
        elif n >= broad_min:
            tier = "broad (low data)"
        elif n >= rare_min:
            tier = "rare"
        else:
            tier = f"skip (< {rare_min})"

        rows.append(
            {
                "scientific_name": sci,
                "common_name": common,
                "clips": n,
                "tier": tier,
                "high_freq": high_freq,
            }
        )

    return rows


def print_wmmsdb_report(
    rows: list[dict],
    thresholds: tuple[int, int, int],
) -> None:
    """Print a formatted tier report for the WMMSDB audit."""
    critical_min, broad_min, rare_min = thresholds

    sep = "─" * 82
    print(f"\n{'WMMSDB CLIP COUNT AUDIT':^82}")
    print(
        f"Tiers: CRITICAL (built-in) | broad ≥{critical_min} clips | "
        f"broad(low) ≥{broad_min} | rare ≥{rare_min} | skip <{rare_min}"
    )
    print(sep)
    print(f"{'Scientific name':<36} {'Common name':<28} {'Clips':>6}  {'Tier'}")
    print(sep)

    current_tier = None
    tier_order = [
        "CRITICAL",
        "broad",
        "broad (low data)",
        "rare",
        f"skip (< {rare_min})",
        "HIGH-FREQ (skip)",
    ]

    # Sort rows by tier order then by clip count desc
    def tier_key(r: dict) -> tuple:
        t = r["tier"]
        try:
            return (tier_order.index(t), -r["clips"])
        except ValueError:
            return (99, -r["clips"])

    for row in sorted(rows, key=tier_key):
        if row["tier"] != current_tier:
            current_tier = row["tier"]
            print(f"\n  [{current_tier}]")
        flag = " ⚠ high-freq" if row["high_freq"] else ""
        print(
            f"  {row['scientific_name']:<34} "
            f"{row['common_name']:<28} "
            f"{row['clips']:>6}{flag}"
        )

    print(sep)

    # Summary counts per tier
    from collections import Counter

    tier_counts = Counter(r["tier"] for r in rows)
    total_clips = sum(r["clips"] for r in rows)
    print("\nSummary:")
    for tier in tier_order:
        k = tier_counts.get(tier, 0)
        if k:
            tier_clips = sum(r["clips"] for r in rows if r["tier"] == tier)
            print(f"  {tier:<24} {k:>3} species  {tier_clips:>6} clips")
    print(f"\n  Total across all species: {len(rows)} species, {total_clips:,} clips")

    # Three-pass candidate summary
    broad_candidates = [
        r["scientific_name"]
        for r in rows
        if "broad" in r["tier"] and not r["high_freq"]
    ]
    rare_candidates = [
        r["scientific_name"] for r in rows if r["tier"] == "rare" and not r["high_freq"]
    ]
    print(
        f"\n  → Broad model candidates (non-critical, capturable): "
        f"{len(broad_candidates)} species"
    )
    print(f"  → Rare/few-shot candidates: {len(rare_candidates)} species")


# ── Happywhale audit ─────────────────────────────────────────


def audit_happywhale(
    thresholds: tuple[int, int, int],
    manifest_path: Path | None = None,
) -> list[dict] | None:
    """Audit Happywhale train.csv if already downloaded.

    Returns None if the file is not found (i.e. Kaggle not yet downloaded).
    """
    import pandas as pd

    from pipeline.config import HAPPYWHALE_LABEL_FIXES, WHALE_PHOTO_RAW_DIR

    search_paths = [
        manifest_path,
        WHALE_PHOTO_RAW_DIR / "_kaggle_raw" / "train.csv",
        WHALE_PHOTO_RAW_DIR / "training_manifest.csv",
    ]
    csv_path = next(
        (p for p in search_paths if p and p.exists()),
        None,
    )
    if csv_path is None:
        log.info(
            "Happywhale train.csv not found — skipping photo audit. "
            "Run download_whale_photos.py first."
        )
        return None

    log.info("Loading Happywhale labels from %s", csv_path)
    df = pd.read_csv(csv_path)

    # Apply label fixes
    for old, new in HAPPYWHALE_LABEL_FIXES.items():
        df.loc[df["species"] == old, "species"] = new

    counts = df["species"].value_counts().reset_index()
    counts.columns = ["species", "images"]

    from pipeline.config import WHALE_PHOTO_TARGET_SPECIES

    critical_min, broad_min, rare_min = thresholds

    rows = []
    for _, row in counts.iterrows():
        sp = str(row["species"])
        n = int(row["images"])

        is_critical = sp in WHALE_PHOTO_TARGET_SPECIES

        if is_critical:
            tier = "CRITICAL"
        elif n >= critical_min:
            tier = "broad"
        elif n >= broad_min:
            tier = "broad (low data)"
        elif n >= rare_min:
            tier = "rare"
        else:
            tier = f"skip (< {rare_min})"

        rows.append({"species": sp, "images": n, "tier": tier})

    return rows


def print_happywhale_report(
    rows: list[dict],
    thresholds: tuple[int, int, int],
) -> None:
    """Print formatted tier report for Happywhale audit."""
    critical_min, broad_min, rare_min = thresholds

    sep = "─" * 60
    print(f"\n{'HAPPYWHALE IMAGE COUNT AUDIT':^60}")
    print(
        f"Tiers: CRITICAL | broad ≥{critical_min} | "
        f"broad(low) ≥{broad_min} | rare ≥{rare_min}"
    )
    print(sep)
    print(f"{'Species':<36} {'Images':>6}  {'Tier'}")
    print(sep)

    tier_order = [
        "CRITICAL",
        "broad",
        "broad (low data)",
        "rare",
        f"skip (< {rare_min})",
    ]

    def tier_key(r: dict) -> tuple:
        t = r["tier"]
        try:
            return (tier_order.index(t), -r["images"])
        except ValueError:
            return (99, -r["images"])

    current_tier = None
    for row in sorted(rows, key=tier_key):
        if row["tier"] != current_tier:
            current_tier = row["tier"]
            print(f"\n  [{current_tier}]")
        print(f"  {row['species']:<34} {row['images']:>6}")

    print(sep)
    from collections import Counter

    tier_counts = Counter(r["tier"] for r in rows)
    print("\nSummary:")
    for tier in tier_order:
        k = tier_counts.get(tier, 0)
        if k:
            tier_imgs = sum(r["images"] for r in rows if r["tier"] == tier)
            print(f"  {tier:<24} {k:>3} species  {tier_imgs:>7} images")
    total = sum(r["images"] for r in rows)
    print(f"\n  Total: {len(rows)} species, {total:,} images")


# ── CLI ──────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit WMMSDB audio and Happywhale photo training data. "
            "Prints clip/image counts and suggests three-pass tier assignments."
        ),
    )
    parser.add_argument(
        "--thresholds",
        nargs=3,
        type=int,
        metavar=("BROAD_MIN", "BROAD_LOW_MIN", "RARE_MIN"),
        default=list(DEFAULT_THRESHOLDS),
        help=(
            "Minimum clip/image counts for broad, broad-low-data, and rare "
            f"tiers (default: {DEFAULT_THRESHOLDS})"
        ),
    )
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="Only run the WMMSDB audio audit",
    )
    parser.add_argument(
        "--photo-only",
        action="store_true",
        help="Only run the Happywhale photo audit",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    thresholds = tuple(args.thresholds)

    if not args.photo_only:
        rows = audit_wmmsdb(thresholds)
        print_wmmsdb_report(rows, thresholds)

    if not args.audio_only:
        rows = audit_happywhale(thresholds)
        if rows:
            print_happywhale_report(rows, thresholds)
        else:
            print(
                "\nHappywhale train.csv not found — run "
                "download_whale_photos.py first to audit photo data."
            )


if __name__ == "__main__":
    main()

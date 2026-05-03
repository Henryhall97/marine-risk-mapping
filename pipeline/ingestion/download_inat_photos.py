"""Download research-grade cetacean photos from iNaturalist for ArcFace training.

iNaturalist is the world's largest biodiversity citizen-science platform.
Research-grade observations are community-verified for correct species ID,
making them high-quality labeled training data.

No API key required for read access.
Rate-limit: ≤60 requests/min unauthenticated (enforced via INAT_REQUEST_DELAY).
Licence filter: cc0, cc-by, cc-by-nc, cc-by-nc-sa — all suitable for
non-commercial research.

Key additions over the Happywhale Kaggle dataset
-------------------------------------------------
• sperm_whale       — absent from Happywhale (deep divers); ~2,800 iNat records
• bowhead_whale     — absent from Happywhale (Arctic); ~320 iNat records
• brydes_whale      — only 154 Happywhale images; ~480 iNat records
• cuviers_beaked_whale — 341 Happywhale; ~600 iNat records
• frasiers_dolphin  — only 14 Happywhale images; ~25 iNat records
• pygmy_killer_whale — 76 Happywhale; ~90 iNat records
• All other species: extra gallery images improve ArcFace KNN retrieval

Images are saved as JPEG at "large" resolution (1024 px long edge) under
data/raw/whale_photos/{species}/inat_{photo_id}.jpg so they co-locate with
Happywhale images and are picked up by the existing training manifests.

A download manifest is written to data/raw/whale_photos/inat_manifest.csv.

Usage
-----
    # All species, default per-species caps
    uv run python pipeline/ingestion/download_inat_photos.py

    # Critical species only (7 ESA + sperm_whale + bowhead_whale)
    uv run python pipeline/ingestion/download_inat_photos.py --stage critical

    # Broad stage (18 non-critical Happywhale species)
    uv run python pipeline/ingestion/download_inat_photos.py --stage broad

    # Specific species
    uv run python pipeline/ingestion/download_inat_photos.py \\
        --species sperm_whale bowhead_whale cuviers_beaked_whale

    # Dry run — print expected counts, download nothing
    uv run python pipeline/ingestion/download_inat_photos.py --dry-run

    # Rebuild manifest from already-downloaded files only
    uv run python pipeline/ingestion/download_inat_photos.py --manifest-only

Alternative image sources (not implemented here)
-------------------------------------------------
• GBIF Media API (aggregates iNat + 1,000+ institutions) — more complex,
  lower photo quality per observation, overlaps heavily with iNat.
• EOL (Encyclopedia of Life) — good reference images, fewer field photos.
• Flickr CC pools — no species taxonomy API; would require manual curation.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    import pandas as pd

from pipeline.config import (
    INAT_MAX_PER_SPECIES,
    INAT_PHOTO_SIZE,
    INAT_REQUEST_DELAY,
    WHALE_PHOTO_RAW_DIR,
)

log = logging.getLogger(__name__)

# ── API constants ───────────────────────────────────────────
INAT_API_BASE = "https://api.inaturalist.org/v1"
INAT_OBSERVATIONS_URL = f"{INAT_API_BASE}/observations"
INAT_PER_PAGE = 200  # maximum allowed by the API

# Licences suitable for non-commercial research use
INAT_LICENCES = ["cc0", "cc-by", "cc-by-nc", "cc-by-nc-sa", "cc-by-sa"]

# Seconds between individual photo file downloads
_PHOTO_DELAY = 0.05

# HTTP timeout for API requests and photo downloads (seconds)
HTTP_TIMEOUT = 60

# ── Species map ─────────────────────────────────────────────
# Maps our label keys → iNaturalist taxon names (binomial).
# All names are accepted by the iNat observations API ``taxon_name`` param,
# which resolves synonyms and returns only the canonical taxon and its children.
INAT_SPECIES_MAP: dict[str, str] = {
    # ── Critical: 7 ESA-listed large whales ─────────────────
    "right_whale": "Eubalaena glacialis",
    "humpback_whale": "Megaptera novaeangliae",
    "fin_whale": "Balaenoptera physalus",
    "blue_whale": "Balaenoptera musculus",
    "minke_whale": "Balaenoptera acutorostrata",
    "sei_whale": "Balaenoptera borealis",
    "killer_whale": "Orcinus orca",
    # ── Gap-fill: absent from Happywhale Kaggle dataset ─────
    # sperm_whale: deep divers rarely photographed in competition context
    # bowhead_whale: Arctic species under-represented in citizen science
    "sperm_whale": "Physeter macrocephalus",
    "bowhead_whale": "Balaena mysticetus",
    # ── Broad: Happywhale species needing gallery coverage ───
    "bottlenose_dolphin": "Tursiops truncatus",
    "beluga": "Delphinapterus leucas",
    "false_killer_whale": "Pseudorca crassidens",
    "dusky_dolphin": "Lagenorhynchus obscurus",
    "spinner_dolphin": "Stenella longirostris",
    "melon_headed_whale": "Peponocephala electra",
    "gray_whale": "Eschrichtius robustus",
    "short_finned_pilot_whale": "Globicephala macrorhynchus",
    "spotted_dolphin": "Stenella attenuata",
    "common_dolphin": "Delphinus delphis",
    "cuviers_beaked_whale": "Ziphius cavirostris",
    "long_finned_pilot_whale": "Globicephala melas",
    "white_sided_dolphin": "Lagenorhynchus acutus",
    "brydes_whale": "Balaenoptera brydei",
    "commersons_dolphin": "Cephalorhynchus commersonii",
    "pygmy_killer_whale": "Feresa attenuata",
    "rough_toothed_dolphin": "Steno bredanensis",
    "frasiers_dolphin": "Lagenodelphis hosei",
}

# Stage groupings
INAT_CRITICAL_SPECIES: list[str] = [
    "right_whale",
    "humpback_whale",
    "fin_whale",
    "blue_whale",
    "minke_whale",
    "sei_whale",
    "killer_whale",
    "sperm_whale",  # gap-fill: absent from Happywhale
    "bowhead_whale",  # gap-fill: absent from Happywhale
]

INAT_BROAD_SPECIES: list[str] = [
    sp for sp in INAT_SPECIES_MAP if sp not in INAT_CRITICAL_SPECIES
]

# Per-species caps — gap-fill species get higher caps since iNat is the only
# photo source; underrepresented Happywhale species get a moderate boost.
INAT_SPECIES_CAPS: dict[str, int] = {
    "sperm_whale": 2000,  # primary source — not in Happywhale
    "bowhead_whale": 1000,  # primary source — not in Happywhale
    "frasiers_dolphin": 500,  # 14 images in Happywhale
    "pygmy_killer_whale": 500,  # 76 images in Happywhale
    "brydes_whale": 500,  # 154 images in Happywhale
    "cuviers_beaked_whale": 500,  # 341 images in Happywhale
    "commersons_dolphin": 300,  # 90 images in Happywhale
    "rough_toothed_dolphin": 300,  # 60 images in Happywhale
}


# ── Helpers ─────────────────────────────────────────────────


def _large_photo_url(square_url: str, size: str = INAT_PHOTO_SIZE) -> str:
    """Convert an iNat square thumbnail URL to the requested size.

    iNat photo URLs follow the pattern:
      https://inaturalist-open-data.s3.amazonaws.com/photos/{id}/square.jpg
    Size options: square (75px), small (240px), medium (440px),
                  large (1024px), original.
    """
    for suffix in ("/square.", "/small.", "/medium.", "/large.", "/original."):
        if suffix in square_url:
            return square_url.replace(suffix, f"/{size}.")
    # Fallback: append size token before extension
    return square_url.replace(".jpg", f"_{size}.jpg")


def _fetch_observation_page(
    taxon_name: str,
    page: int,
    *,
    per_page: int = INAT_PER_PAGE,
    licences: list[str] | None = None,
) -> dict:
    """Fetch one page of research-grade observations from the iNat API.

    Returns the parsed JSON response dict.
    Raises requests.HTTPError on non-200 responses.
    """
    licences = licences or INAT_LICENCES
    params = {
        "taxon_name": taxon_name,
        "quality_grade": "research",
        "photos": "true",
        "photo_license": ",".join(licences),
        "per_page": per_page,
        "page": page,
        "order": "created_at",
        "order_by": "id",
    }
    resp = requests.get(INAT_OBSERVATIONS_URL, params=params, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _download_photo(url: str, dest: Path) -> bool:
    """Download a single photo to dest.

    Returns True on success, False on failure (logged but not re-raised).
    Creates parent directories as needed.
    """
    if dest.exists():
        return True  # already downloaded

    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type.lower():
            log.warning(
                "Unexpected content-type %s for %s — skipping",
                content_type,
                url,
            )
            return False

        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=16_384):
                fh.write(chunk)
        return True

    except requests.RequestException as exc:
        log.warning("Photo download failed %s: %s", url, exc)
        return False


# ── Main downloader ─────────────────────────────────────────


def download_species(
    species_key: str,
    taxon_name: str,
    output_dir: Path,
    max_images: int,
    *,
    dry_run: bool = False,
) -> int:
    """Download up to ``max_images`` photos for one species from iNaturalist.

    Photos are saved as ``inat_{photo_id}.jpg`` inside
    ``output_dir / species_key /``.

    Returns the number of photos downloaded (or that would be downloaded in
    dry-run mode).
    """
    sp_dir = output_dir / species_key
    sp_dir.mkdir(parents=True, exist_ok=True)

    # Count already-downloaded iNat files so we don't re-download on reruns
    existing = {p.stem for p in sp_dir.glob("inat_*.jpg")}
    needed = max_images - len(existing)

    if needed <= 0:
        log.info(
            "iNat/%s: %d images already present (cap %d) — skipping",
            species_key,
            len(existing),
            max_images,
        )
        return len(existing)

    log.info(
        "iNat/%s → '%s' | need %d more (have %d, cap %d)",
        species_key,
        taxon_name,
        needed,
        len(existing),
        max_images,
    )

    downloaded = 0
    page = 1
    total_available: int | None = None

    while downloaded < needed:
        try:
            data = _fetch_observation_page(taxon_name, page)
        except requests.RequestException as exc:
            log.error("iNat API error for %s page %d: %s", species_key, page, exc)
            break

        if total_available is None:
            total_available = data.get("total_results", 0)
            log.info(
                "iNat/%s: %d total research-grade observations",
                species_key,
                total_available,
            )

        observations = data.get("results", [])
        if not observations:
            log.info("iNat/%s: no more observations at page %d", species_key, page)
            break

        for obs in observations:
            if downloaded >= needed:
                break

            photos = obs.get("photos", [])
            if not photos:
                continue

            # Take first photo per observation (usually the best shot)
            photo = photos[0]
            photo_id = photo.get("id")
            square_url = photo.get("url", "")

            if not photo_id or not square_url:
                continue

            stem = f"inat_{photo_id}"
            if stem in existing:
                continue  # already have this photo from a previous run

            large_url = _large_photo_url(square_url)
            dest = sp_dir / f"{stem}.jpg"

            if dry_run:
                downloaded += 1
                log.debug("  [dry-run] would download %s", large_url)
                continue

            ok = _download_photo(large_url, dest)
            if ok:
                downloaded += 1
                existing.add(stem)
                if downloaded % 50 == 0:
                    log.info(
                        "iNat/%s: %d / %d downloaded",
                        species_key,
                        downloaded,
                        needed,
                    )

            time.sleep(_PHOTO_DELAY)

        if downloaded >= needed:
            break

        # Check if there are more pages
        fetched_so_far = (page - 1) * INAT_PER_PAGE + len(observations)
        if total_available is not None and fetched_so_far >= total_available:
            log.info(
                "iNat/%s: exhausted all %d observations", species_key, total_available
            )
            break

        page += 1
        time.sleep(INAT_REQUEST_DELAY)

    action = "would download" if dry_run else "downloaded"
    log.info("iNat/%s: %s %d images", species_key, action, downloaded)
    return downloaded


def download_all(
    species: list[str],
    output_dir: Path | None = None,
    max_per_species: int | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Download iNaturalist photos for all requested species.

    Returns dict of {species_key: n_images_downloaded}.
    """
    output_dir = output_dir or WHALE_PHOTO_RAW_DIR
    stats: dict[str, int] = {}

    for sp in species:
        taxon_name = INAT_SPECIES_MAP.get(sp)
        if not taxon_name:
            log.warning("No iNat taxon mapping for '%s' — skipping", sp)
            continue

        cap = max_per_species or INAT_SPECIES_CAPS.get(sp, INAT_MAX_PER_SPECIES)
        n = download_species(sp, taxon_name, output_dir, cap, dry_run=dry_run)
        stats[sp] = n

        # Pause between species to be polite to the API
        if not dry_run:
            time.sleep(INAT_REQUEST_DELAY * 2)

    return stats


# ── Manifest ────────────────────────────────────────────────


def build_manifest(photo_dir: Path | None = None) -> pd.DataFrame:
    """Scan downloaded iNat photos and write a manifest CSV.

    Returns a DataFrame with columns: file_path, species, photo_id, source.
    Saved to ``photo_dir / inat_manifest.csv``.
    """
    import pandas as pd

    photo_dir = photo_dir or WHALE_PHOTO_RAW_DIR
    rows: list[dict] = []

    for sp_dir in sorted(photo_dir.iterdir()):
        if not sp_dir.is_dir():
            continue
        species = sp_dir.name
        for f in sorted(sp_dir.glob("inat_*.jpg")):
            photo_id = f.stem.replace("inat_", "")
            rows.append(
                {
                    "file_path": str(f),
                    "species": species,
                    "photo_id": photo_id,
                    "source": "inaturalist",
                }
            )

    df = pd.DataFrame(rows)
    manifest_path = photo_dir / "inat_manifest.csv"
    df.to_csv(manifest_path, index=False)
    log.info(
        "iNat manifest: %d photos across %d species → %s",
        len(df),
        df["species"].nunique() if not df.empty else 0,
        manifest_path,
    )
    return df


# ── CLI ─────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Download research-grade cetacean photos from iNaturalist "
            "to supplement Happywhale training data for ArcFace."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Species added over Happywhale:\n"
            "  sperm_whale   (~2,800 iNat records — absent from Happywhale)\n"
            "  bowhead_whale (~320 iNat records  — absent from Happywhale)\n"
            "  brydes_whale  (~480 iNat records  — 154 Happywhale images)\n"
            "  cuviers_beaked_whale (~600 iNat   — 341 Happywhale images)\n"
            "  frasiers_dolphin (~25 iNat        — 14 Happywhale images)\n"
        ),
    )
    parser.add_argument(
        "--stage",
        choices=["critical", "broad", "all"],
        default="all",
        help=(
            "critical: 7 ESA large whales + sperm_whale + bowhead_whale. "
            "broad: 18 non-critical Happywhale species. "
            "all: everything (default)."
        ),
    )
    parser.add_argument(
        "--species",
        nargs="+",
        default=None,
        metavar="SPECIES",
        help=(
            "Override stage — download specific species only. "
            "Example: --species sperm_whale bowhead_whale"
        ),
    )
    parser.add_argument(
        "--max-per-species",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Cap images per species. Overrides per-species caps in config. "
            "Default: varies by species "
            f"(sperm_whale=2000, others={INAT_MAX_PER_SPECIES})."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print expected download counts without downloading anything.",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Skip downloads — rebuild inat_manifest.csv from existing files.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.manifest_only:
        df = build_manifest()
        if not df.empty:
            print(f"\niNat manifest: {len(df)} photos")
            print(df.groupby("species")["photo_id"].count().to_string())
        return

    # Select species list
    if args.species:
        unknown = [s for s in args.species if s not in INAT_SPECIES_MAP]
        if unknown:
            parser.error(
                f"Unknown species: {unknown}. Valid keys: {sorted(INAT_SPECIES_MAP)}"
            )
        target = args.species
    elif args.stage == "critical":
        target = INAT_CRITICAL_SPECIES
    elif args.stage == "broad":
        target = INAT_BROAD_SPECIES
    else:
        target = list(INAT_SPECIES_MAP.keys())

    if args.dry_run:
        log.info("[DRY RUN] No files will be downloaded.")

    log.info("=" * 60)
    log.info("iNaturalist Photo Download — %d species", len(target))
    log.info("=" * 60)

    stats = download_all(
        target,
        max_per_species=args.max_per_species,
        dry_run=args.dry_run,
    )

    log.info("=" * 60)
    log.info("SUMMARY")
    log.info("=" * 60)
    total = 0
    for sp, n in sorted(stats.items()):
        log.info("  %-30s %5d", sp, n)
        total += n
    log.info("  %-30s %5d", "TOTAL", total)

    if not args.dry_run:
        build_manifest()


if __name__ == "__main__":
    main()

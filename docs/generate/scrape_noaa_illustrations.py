"""
Download NOAA Fisheries species illustrations for the ID wizard.

Downloads 640×427 PNG/JPG illustrations from fisheries.noaa.gov and
resizes to 1024×1024 square (with padding) to match the Pillow annotation
pipeline. The ``--reoverlay`` flag on ``generate_wizard_graphics.py``
can then re-apply teal circle annotations on these NOAA images.

Usage::

    uv run python docs/generate/scrape_noaa_illustrations.py
    uv run python docs/generate/scrape_noaa_illustrations.py --pad-square
    # Then re-apply annotations:
    uv run python docs/generate/generate_wizard_graphics.py --reoverlay

Illustrations are credited to NOAA Fisheries. Some may be contractor-
created (Jack Hornady).  See attribution page for details.
"""

from __future__ import annotations

import argparse
import logging
import time
import urllib.request
from pathlib import Path

try:
    from PIL import Image

    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
SPECIES_RAW_DIR = ROOT / "frontend" / "public" / "wizard" / "species" / "raw"
NOAA_ORIG_DIR = ROOT / "frontend" / "public" / "wizard" / "species" / "noaa"

# ── NOAA Fisheries illustration URLs ─────────────────────────────
# Source: https://www.fisheries.noaa.gov/species/
# All URLs are 640×427 profile illustrations.
# Credit: NOAA Fisheries (some by Jack Hornady, contractor).

_BASE = "https://www.fisheries.noaa.gov/s3//styles/original/s3"

NOAA_URLS: dict[str, str] = {
    "right_whale": (
        f"{_BASE}/2024-06/640x427-North-Atlantic-Right-Whale-NOAAFisheries.png"
    ),
    "humpback": (f"{_BASE}/2023-03/640x427-Whale-Humpback-markedDW.png"),
    "blue_whale": (f"{_BASE}/dam-migration/640x427-blue-whale.jpg"),
    "fin_whale": (f"{_BASE}/2020-09/640x4270-fin-whale-v2.jpg"),
    "sperm_whale": (f"{_BASE}/dam-migration/640x427-sperm-whale.png"),
    "sei_whale": (f"{_BASE}/dam-migration/640x427-sei-whale.png"),
    "minke_whale": (f"{_BASE}/dam-migration/640x427-minke-whale.png"),
    "gray_whale": (f"{_BASE}/dam-migration/640x427-gray-whale.png"),
    "bowhead": (f"{_BASE}/2023-03/640x427-Whale-Bowhead-markedDW.png"),
    "brydes_whale": (f"{_BASE}/2023-03/640x427-Whale-Brydes-markedDW_0.png"),
    "orca": (f"{_BASE}/dam-migration/640x427-killer-whale.png"),
    "bottlenose_dolphin": (
        f"{_BASE}/dam-migration/640x427-dolphin_bottlenose_nb_w.png"
    ),
    "harbor_porpoise": (f"{_BASE}/dam-migration/640x427-harbor-porpoise.png"),
    "beluga": (f"{_BASE}/2023-03/640x427-Whale-Beluga-markedDW.png"),
    "narwhal": (f"{_BASE}/dam-migration/640x427-narwhal.jpg"),
    "dalls_porpoise": (f"{_BASE}/dam-migration/640x427-dalls-porpoise.png"),
    "spinner_dolphin": (f"{_BASE}/dam-migration/640x427-spinner-dolphin.png"),
    "rissos_dolphin": (f"{_BASE}/dam-migration/640x427-rissos-dolphin.png"),
    "pilot_whale": (f"{_BASE}/2023-03/640x427-Whale_Short-Finned_Pilot-markedDW.png"),
    "spotted_dolphin": (f"{_BASE}/dam-migration/640x427-atlantic-spotted-dolphin.png"),
    "striped_dolphin": (f"{_BASE}/dam-migration/640x427-striped-dolphin.png"),
    "whitesided_dolphin": (
        f"{_BASE}/dam-migration/640x427-atlantic-white-sided-dolphin.jpg"
    ),
    "common_dolphin": (
        f"{_BASE}/dam-migration/640x427-short-beaked-common-dolphin.png"
    ),
    "vaquita": (f"{_BASE}/dam-migration/640x427-vaquita.png"),
}

# Per-illustration credit (most are "NOAA Fisheries").
NOAA_CREDITS: dict[str, str] = {
    "dalls_porpoise": "Jack Hornady / NOAA Fisheries",
    "spotted_dolphin": "Jack Hornady / NOAA Fisheries",
}
_DEFAULT_CREDIT = "NOAA Fisheries"


def _download(url: str, dest: Path, max_retries: int = 3) -> bool:
    """Download a file with retries."""
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (marine-risk-mapping research project)"
                    ),
                },
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            dest.write_bytes(data)
            return True
        except Exception as e:
            log.warning(
                "  Attempt %d/%d failed for %s: %s",
                attempt,
                max_retries,
                dest.name,
                str(e)[:120],
            )
            if attempt < max_retries:
                time.sleep(2 * attempt)
    return False


def _pad_to_square(src: Path, dest: Path, size: int = 1024) -> None:
    """Resize an image to fit within a square canvas with padding.

    The original illustration is centred on a dark navy background
    matching the wizard's dark theme.
    """
    if not _HAS_PIL:
        log.warning("Pillow not installed — skipping pad")
        return
    img = Image.open(src).convert("RGBA")
    ow, oh = img.size

    # Scale to fit within size×size while preserving aspect ratio
    scale = min(size / ow, size / oh) * 0.88  # 88% fill
    nw = int(ow * scale)
    nh = int(oh * scale)
    img = img.resize((nw, nh), Image.LANCZOS)

    # Create dark navy background
    canvas = Image.new("RGBA", (size, size), (8, 12, 28, 255))
    # Centre the illustration
    x = (size - nw) // 2
    y = (size - nh) // 2
    canvas.paste(img, (x, y), img)

    canvas.convert("RGB").save(dest)
    log.info("  Padded %s → %d×%d", dest.name, size, size)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=("Download NOAA Fisheries species illustrations")
    )
    parser.add_argument(
        "--pad-square",
        action="store_true",
        help=(
            "Pad downloaded images to 1024×1024 square "
            "and copy to raw/ dir for annotation overlay"
        ),
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Download only one species key",
    )
    args = parser.parse_args()

    NOAA_ORIG_DIR.mkdir(parents=True, exist_ok=True)
    SPECIES_RAW_DIR.mkdir(parents=True, exist_ok=True)

    total = 0
    success = 0

    for key, url in NOAA_URLS.items():
        if args.only and args.only != key:
            continue
        total += 1
        ext = url.rsplit(".", 1)[-1].split("?")[0]
        noaa_path = NOAA_ORIG_DIR / f"{key}.{ext}"

        if noaa_path.exists():
            log.info("  Already exists: %s", noaa_path.name)
            success += 1
        else:
            log.info("  Downloading %s …", key)
            if _download(url, noaa_path):
                success += 1
                log.info("  ✓  Saved %s", noaa_path.name)
            else:
                log.error("  ✗  Failed: %s", key)
                continue

        # Optionally pad to square for annotation pipeline
        if args.pad_square:
            raw_dest = SPECIES_RAW_DIR / f"{key}.png"
            _pad_to_square(noaa_path, raw_dest, size=1024)

        # Be polite — small delay between requests
        time.sleep(0.5)

    log.info("Done: %d/%d downloaded.", success, total)
    credit = _DEFAULT_CREDIT
    log.info("Credit: %s", credit)
    log.info("Originals saved to: %s", NOAA_ORIG_DIR)
    if args.pad_square:
        log.info(
            "Padded squares saved to: %s",
            SPECIES_RAW_DIR,
        )
        log.info(
            "Run `uv run python docs/generate/"
            "generate_wizard_graphics.py --reoverlay` "
            "to apply annotations."
        )


if __name__ == "__main__":
    main()

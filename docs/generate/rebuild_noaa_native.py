"""
Rebuild NOAA species images at native resolution (800x534) instead of
upscaling to 1024x1024. This fixes the pixelation issue where 640x427
originals were being stretched to fill 88% of a 1024x1024 canvas.

The annotation pipeline still overlays teal circles + labels, but now
at the natural aspect ratio of the source illustrations.

Usage::

    uv run python docs/generate/rebuild_noaa_native.py
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_wizard_graphics import (  # noqa: E402
    SPECIES_ANNOTATIONS,
    SPECIES_DISPLAY_NAMES,
    overlay_species_annotations,
    overlay_species_label,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
NOAA_DIR = ROOT / "frontend" / "public" / "wizard" / "species" / "noaa"
RAW_DIR = ROOT / "frontend" / "public" / "wizard" / "species" / "raw"
OUT_DIR = ROOT / "frontend" / "public" / "wizard" / "species"
DARK_BG = (8, 12, 28, 255)


def _remove_white_bg(img: Image.Image) -> Image.Image:
    """Remove white/light background pixels — gentler threshold."""
    data = np.array(img.convert("RGBA"))
    r, g, b = data[:, :, 0], data[:, :, 1], data[:, :, 2]
    # Pure white → fully transparent
    white = (r > 240) & (g > 240) & (b > 240)
    data[white, 3] = 0
    # Near-white → semi-transparent
    light = (r > 220) & (g > 220) & (b > 220) & ~white
    data[light, 3] = (data[light, 3] * 0.5).astype(np.uint8)
    return Image.fromarray(data, "RGBA")


def _has_white_bg(img: Image.Image) -> bool:
    """Check if image corners are white (indicating a white bg)."""
    data = np.array(img.convert("RGBA"))
    h, w = data.shape[:2]
    corners = [
        data[3, 3],
        data[3, w - 3],
        data[h - 3, 3],
        data[h - 3, w - 3],
    ]
    return all(c[0] > 220 and c[1] > 220 and c[2] > 220 for c in corners)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    fixed = 0

    # Process all PNG files in noaa/ directory
    for f in sorted(NOAA_DIR.glob("*.png")):
        key = f.stem
        img = Image.open(f).convert("RGBA")

        # Fix white background if present
        if _has_white_bg(img):
            img = _remove_white_bg(img)
            img.save(f, "PNG")
            log.info("  Fixed white bg: %s", f.name)

        # Composite onto dark bg at NATIVE resolution — no upscaling
        ow, oh = img.size
        canvas = Image.new("RGBA", (ow, oh), DARK_BG)
        canvas.paste(img, (0, 0), img)

        # Save as raw (for annotation pipeline)
        raw_path = RAW_DIR / f"{key}.png"
        canvas.convert("RGB").save(raw_path)

        # Copy to output and overlay annotations
        out_path = OUT_DIR / f"{key}.png"
        shutil.copy2(raw_path, out_path)
        name = SPECIES_DISPLAY_NAMES.get(key)
        annot = SPECIES_ANNOTATIONS.get(key)
        if name and annot:
            overlay_species_annotations(out_path, name, annot)
        elif name:
            overlay_species_label(out_path, name)
        fixed += 1
        log.info(
            "  Rebuilt %s at %dx%d (native)",
            key,
            ow,
            oh,
        )

    # Handle JPG originals that lack a PNG version
    for f in sorted(NOAA_DIR.glob("*.jpg")):
        key = f.stem
        if (NOAA_DIR / f"{key}.png").exists():
            continue  # Already have PNG version

        img = Image.open(f).convert("RGBA")
        if _has_white_bg(img):
            img = _remove_white_bg(img)

        ow, oh = img.size
        canvas = Image.new("RGBA", (ow, oh), DARK_BG)
        canvas.paste(img, (0, 0), img)

        # Save as PNG in noaa dir for consistency
        noaa_png = NOAA_DIR / f"{key}.png"
        canvas.convert("RGB").save(noaa_png)

        raw_path = RAW_DIR / f"{key}.png"
        canvas.convert("RGB").save(raw_path)

        out_path = OUT_DIR / f"{key}.png"
        shutil.copy2(raw_path, out_path)
        name = SPECIES_DISPLAY_NAMES.get(key)
        annot = SPECIES_ANNOTATIONS.get(key)
        if name and annot:
            overlay_species_annotations(out_path, name, annot)
        elif name:
            overlay_species_label(out_path, name)
        fixed += 1
        log.info(
            "  Rebuilt %s (from JPG) at %dx%d",
            key,
            ow,
            oh,
        )

    log.info(
        "Done: %d species rebuilt at native resolution.",
        fixed,
    )


if __name__ == "__main__":
    main()

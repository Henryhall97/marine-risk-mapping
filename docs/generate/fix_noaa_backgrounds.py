"""Fix white backgrounds on NOAA illustrations.

Replaces white/near-white pixels with transparency, then re-composites
onto the dark navy background used by the wizard theme.  Also regenerates
the padded 1024×1024 raw images + final labelled output images.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
NOAA_DIR = ROOT / "frontend" / "public" / "wizard" / "species" / "noaa"
RAW_DIR = ROOT / "frontend" / "public" / "wizard" / "species" / "raw"
OUT_DIR = ROOT / "frontend" / "public" / "wizard" / "species"
DARK_BG = (8, 12, 28, 255)


def _remove_white_bg(img: Image.Image) -> Image.Image:
    """Replace white/near-white pixels with transparent."""
    data = np.array(img.convert("RGBA"))
    r, g, b = data[:, :, 0], data[:, :, 1], data[:, :, 2]

    # Fully white → fully transparent
    white = (r > 230) & (g > 230) & (b > 230)
    data[white, 3] = 0

    # Light grey fringe (anti-alias) → partial transparency
    light = (r > 200) & (g > 200) & (b > 200) & ~white
    data[light, 3] = (data[light, 3] * 0.4).astype(np.uint8)

    return Image.fromarray(data, "RGBA")


def _has_white_bg(img: Image.Image) -> bool:
    """Detect if an image has a white background."""
    data = np.array(img.convert("RGBA"))
    h, w = data.shape[:2]
    corners = [data[3, 3], data[3, w - 3], data[h - 3, 3], data[h - 3, w - 3]]
    return all(c[0] > 220 and c[1] > 220 and c[2] > 220 for c in corners)


def _pad_to_square(
    src: Image.Image, size: int = 1024, fill_frac: float = 0.88
) -> Image.Image:
    """Centre an RGBA image on a dark navy square canvas."""
    ow, oh = src.size
    scale = min(size / ow, size / oh) * fill_frac
    nw, nh = int(ow * scale), int(oh * scale)
    resized = src.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), DARK_BG)
    x, y = (size - nw) // 2, (size - nh) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas


def main() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "docs" / "generate"))
    from generate_wizard_graphics import (
        SPECIES_DISPLAY_NAMES,
        overlay_species_label,
    )

    fixed = 0
    total = 0
    for f in sorted(NOAA_DIR.glob("*.png")):
        key = f.stem
        total += 1
        img = Image.open(f).convert("RGBA")

        if _has_white_bg(img):
            clean = _remove_white_bg(img)
            # Save cleaned transparent NOAA original
            clean.save(f, "PNG")
            print(f"  Cleaned bg: {key}")
            fixed += 1
        else:
            clean = img

        # Re-pad onto dark background
        padded = _pad_to_square(clean)
        raw_path = RAW_DIR / f"{key}.png"
        padded.convert("RGB").save(raw_path)

        # Re-label final output
        out_path = OUT_DIR / f"{key}.png"
        shutil.copy2(raw_path, out_path)
        name = SPECIES_DISPLAY_NAMES.get(key)
        if name:
            overlay_species_label(out_path, name)

    # Also handle non-NOAA species that still have raw images
    for raw_f in sorted(RAW_DIR.glob("*.png")):
        key = raw_f.stem
        if not (NOAA_DIR / f"{key}.png").exists():
            out_path = OUT_DIR / f"{key}.png"
            if raw_f.exists():
                shutil.copy2(raw_f, out_path)
                name = SPECIES_DISPLAY_NAMES.get(key)
                if name:
                    overlay_species_label(out_path, name)
                print(f"  Re-labelled (non-NOAA): {key}")

    print(f"\nDone: {fixed}/{total} white backgrounds fixed.")
    print(f"All {total} NOAA species re-padded and re-labelled.")


if __name__ == "__main__":
    main()

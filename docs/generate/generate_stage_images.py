"""Generate wizard stage comparison PNGs from Wikimedia species SVGs.

Downloads are pre-cached in frontend/public/wizard/stages/raw/wikimedia/.
This script:
  1. Recolors black SVG silhouettes → themed colors for dark background
  2. Renders each SVG at high DPI via rsvg-convert
  3. Crops animal silhouette (strips human scale figure where possible)
  4. Composites species side-by-side with crisp labels + annotations
  5. Outputs 6 transparent PNGs to frontend/public/wizard/stages/

Source: Wikimedia Commons — "Cetacea size comparisons with human silhouettes"
Author: Chris huh (+ Jjw for humpback)
License: CC BY-SA 3.0 / CC BY-SA 4.0
"""

import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── Paths ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
WIKIMEDIA = ROOT / "frontend/public/wizard/stages/raw/wikimedia"
OUTPUT = ROOT / "frontend/public/wizard/stages"
RSVG = "/opt/homebrew/bin/rsvg-convert"

# ── Theme colours (matched to wizard selection boxes) ─────────
# Whale = blue/ocean  (selection: border-ocean-600, text-ocean-300)
# Baleen whale = teal (selection: border-teal-600, text-teal-300)
# Toothed whale = purple (selection: border-purple-600, text-purple-300)
# Dolphin = teal/green (selection: border-teal-600, text-teal-300)
# Porpoise = purple (selection: border-purple-600, text-purple-300)
BLUE = "#60a5fa"  # whale label (Tailwind blue-400)
BLUE_FILL = "#3b82f6"  # bright blue fill for whale body
TEAL = "#2dd4bf"  # baleen whales / dolphins
TEAL_FILL = "#14b8a6"  # bright teal fill (Tailwind teal-500)
PURPLE = "#c084fc"  # toothed whales / porpoises (Tailwind purple-400)
PURPLE_FILL = "#a855f7"  # bright purple fill (Tailwind purple-500)
HUMAN_COLOR = "#334155"  # subtle dark slate for human silhouette
LABEL_COLOR = "#e2e8f0"  # bright slate for labels
SUBLABEL = "#94a3b8"  # dimmer for sub-labels
ANN_BLUE = "#93c5fd"  # annotation text for generic whale (blue-300)
ANN_TEAL = "#5eead4"  # annotation text for baleen / dolphins (teal-300)
ANN_PURPLE = "#d8b4fe"  # annotation text for toothed / porpoises (purple-300)

# ── Rendering config ──────────────────────────────────────────
RENDER_HEIGHT = 500  # px height for each species SVG render
CANVAS_WIDTH = 1600  # final image width
DPI = 288  # 2x Retina

# Per-species left crop fractions — tuned so ≤2% pixel content
# is lost.  Large whales whose body extends far left get minimal
# crop; porpoises whose human silhouette is well-separated get
# a larger crop.
SPECIES_CROP: dict[str, float] = {
    # Large whales — body extends leftward
    "sperm_whale": 0.03,
    "humpback_whale": 0.03,
    "right_whale": 0.06,
    "fin_whale": 0.06,
    "blue_whale": 0.08,
    # Medium animals
    "beluga": 0.06,
    "orca": 0.06,
    "pilot_whale": 0.06,
    "cuviers_beaked_whale": 0.10,
    "narwhal": 0.10,
    # Dolphins — human well-separated
    "bottlenose_dolphin": 0.10,
    "common_dolphin": 0.10,
    "rissos_dolphin": 0.12,
    # Porpoises — human very well-separated
    "harbour_porpoise": 0.15,
    "dalls_porpoise": 0.15,
    "vaquita": 0.15,
}
DEFAULT_CROP = 0.08  # fallback


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get system font, preferring Avenir Next or SF Pro."""
    candidates = [
        "/System/Library/Fonts/Supplemental/Avenir Next.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        p = Path(path)
        if p.exists():
            idx = 2 if bold and "Avenir" in path else 0
            try:
                return ImageFont.truetype(str(p), size, index=idx)
            except Exception:
                continue
    return ImageFont.load_default()


FONT_LABEL = get_font(32, bold=True)
FONT_SUB = get_font(22, bold=False)
FONT_ANN = get_font(20, bold=False)
FONT_TITLE = get_font(26, bold=True)


# ── SVG recoloring ────────────────────────────────────────────


def recolor_svg(svg_text: str, fill_color: str, stroke_color: str) -> str:
    """Replace black fills/strokes in SVG with themed colours."""
    # Replace CSS class definitions like .fil0 {fill:black}
    svg_text = re.sub(
        r"\.fil0\s*\{fill:\s*black\s*\}",
        f".fil0 {{fill:{fill_color}}}",
        svg_text,
    )
    svg_text = re.sub(
        r"\.fil0\s*\{fill:\s*#000000\s*\}",
        f".fil0 {{fill:{fill_color}}}",
        svg_text,
    )

    # Replace inline style fill:black / fill:#000000
    svg_text = re.sub(
        r'fill:\s*black(?=[;"\s])',
        f"fill:{fill_color}",
        svg_text,
    )
    svg_text = re.sub(
        r"fill:\s*#000000",
        f"fill:{fill_color}",
        svg_text,
    )

    # Replace inline style stroke:black / stroke:#000000
    svg_text = re.sub(
        r'stroke:\s*black(?=[;"\s])',
        f"stroke:{stroke_color}",
        svg_text,
    )
    svg_text = re.sub(
        r"stroke:\s*#000000",
        f"stroke:{stroke_color}",
        svg_text,
    )

    # Replace fill="black" and fill="#000000" attributes
    svg_text = re.sub(
        r'fill="black"',
        f'fill="{fill_color}"',
        svg_text,
    )
    svg_text = re.sub(
        r'fill="#000000"',
        f'fill="{fill_color}"',
        svg_text,
    )

    # Replace stroke="black" / stroke="#000000"
    svg_text = re.sub(
        r'stroke="black"',
        f'stroke="{stroke_color}"',
        svg_text,
    )
    svg_text = re.sub(
        r'stroke="#000000"',
        f'stroke="{stroke_color}"',
        svg_text,
    )

    # For white backgrounds -> transparent
    svg_text = re.sub(
        r'pagecolor="#ffffff"',
        'pagecolor="none"',
        svg_text,
    )

    return svg_text


def recolor_svg_special(
    name: str, svg_text: str, fill_color: str, stroke_color: str
) -> str:
    """Handle species with existing coloring (orca, blue, sperm, etc.)."""
    if name == "orca":
        # Orca has real black/white coloring.
        # Brighten the black body to dark theme-colored fill,
        # keep white belly patches
        svg_text = re.sub(
            r"\.fil0\s*\{fill:\s*black\s*\}",
            f".fil0 {{fill:{fill_color}}}",
            svg_text,
        )
        svg_text = re.sub(
            r'fill:\s*#000000(?=[;"])',
            f"fill:{fill_color}",
            svg_text,
        )
        svg_text = re.sub(
            r"stroke:\s*#000000",
            f"stroke:{stroke_color}",
            svg_text,
        )
        # Keep white patches (.fil1) but make them slightly teal-tinted
        svg_text = re.sub(
            r"\.fil1\s*\{fill:\s*#FEFEFE\s*\}",
            ".fil1 {fill:#99f6e4}",
            svg_text,
        )
        # Brighten the grays
        svg_text = re.sub(
            r"\.fil5\s*\{fill:\s*#323232\s*\}",
            f".fil5 {{fill:{fill_color}}}",
            svg_text,
        )
        svg_text = re.sub(
            r"\.fil6\s*\{fill:\s*#8E8E8E\s*\}",
            ".fil6 {fill:#94a3b8}",
            svg_text,
        )
        svg_text = re.sub(
            r"\.fil7\s*\{fill:\s*#A2A2A2\s*\}",
            ".fil7 {fill:#5eead4}",
            svg_text,
        )
        # Yellow eye patch -> themed accent
        svg_text = re.sub(
            r"\.fil3\s*\{fill:\s*#DDDB2A\s*\}",
            ".fil3 {fill:#fbbf24}",
            svg_text,
        )
        svg_text = re.sub(
            r"\.fil2\s*\{fill:\s*#EDEE29\s*\}",
            ".fil2 {fill:#fcd34d}",
            svg_text,
        )
        svg_text = re.sub(
            r"\.fil4\s*\{fill:\s*#F4F10D\s*\}",
            ".fil4 {fill:#fde68a}",
            svg_text,
        )
        return svg_text

    elif name == "blue_whale":
        # Blue whale has #6b7c98 fill with black stroke — keep fill,
        # brighten it slightly, fix strokes
        svg_text = re.sub(
            r"fill:\s*#6b7c98",
            "fill:#7c94b8",
            svg_text,
        )
        svg_text = re.sub(
            r"stroke:\s*#000000",
            f"stroke:{stroke_color}",
            svg_text,
        )
        svg_text = re.sub(
            r"fill:\s*#000000",
            f"fill:{fill_color}",
            svg_text,
        )
        return svg_text

    elif name == "sperm_whale":
        # Sperm whale has #808080 fill with black stroke
        svg_text = re.sub(
            r"fill:\s*#808080",
            "fill:#c084fc",
            svg_text,
        )
        svg_text = re.sub(
            r"stroke:\s*#000000",
            f"stroke:{stroke_color}",
            svg_text,
        )
        svg_text = re.sub(
            r"fill:\s*#000000",
            f"fill:{fill_color}",
            svg_text,
        )
        svg_text = re.sub(
            r"fill:\s*#ffffff",
            "fill:#d8b4fe",
            svg_text,
        )
        return svg_text

    elif name == "bottlenose_dolphin":
        # Has black+white fills with strokes
        svg_text = re.sub(
            r'fill:\s*#ffffff(?=[;"])',
            "fill:#99f6e4",
            svg_text,
        )
        svg_text = re.sub(
            r"fill:\s*#000000",
            f"fill:{fill_color}",
            svg_text,
        )
        svg_text = re.sub(
            r"stroke:\s*#000000",
            f"stroke:{stroke_color}",
            svg_text,
        )
        svg_text = re.sub(
            r"stroke:\s*#ffffff",
            "stroke:#99f6e4",
            svg_text,
        )
        return svg_text

    elif name == "humpback_whale":
        # Has black body + white stroke details
        svg_text = re.sub(
            r"fill:\s*#000000",
            f"fill:{fill_color}",
            svg_text,
        )
        svg_text = re.sub(
            r"stroke:\s*#000000",
            f"stroke:{stroke_color}",
            svg_text,
        )
        svg_text = re.sub(
            r"stroke:\s*#ffffff",
            "stroke:#5eead4",
            svg_text,
        )
        return svg_text

    elif name in ("common_dolphin", "rissos_dolphin"):
        # These are single-path silhouettes that look faint at small size.
        # Use a much brighter fill so they pop on the dark background.
        bright = "#5eead4"  # teal-300 — significantly brighter
        svg_text = re.sub(
            r"fill:\s*#000000",
            f"fill:{bright}",
            svg_text,
        )
        svg_text = re.sub(
            r"stroke:\s*#000000",
            f"stroke:{stroke_color}",
            svg_text,
        )
        return svg_text

    # Default: simple recolor
    return recolor_svg(svg_text, fill_color, stroke_color)


def render_svg(
    svg_path: Path,
    fill_color: str,
    stroke_color: str,
    height: int = RENDER_HEIGHT,
    name: str = "",
    crop_human: bool = True,
) -> Image.Image:
    """Recolor SVG and render to PIL Image via rsvg-convert.

    If crop_human is True, adjusts the SVG viewBox to crop out
    the leftmost portion containing the human scale figure.
    The human occupies roughly the left 15-20% of each SVG.
    """
    svg_text = svg_path.read_text(encoding="utf-8")

    # Check if this species needs special handling
    special = {
        "orca",
        "blue_whale",
        "sperm_whale",
        "bottlenose_dolphin",
        "humpback_whale",
        "common_dolphin",
        "rissos_dolphin",
    }
    if name in special:
        svg_text = recolor_svg_special(name, svg_text, fill_color, stroke_color)
    else:
        svg_text = recolor_svg(svg_text, fill_color, stroke_color)

    # No cropping — render full SVG as-is

    # Write to temp file and render
    with tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False) as f:
        f.write(svg_text)
        tmp_svg = f.name

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_png = f.name

    subprocess.run(
        [
            RSVG,
            "-h",
            str(height * 2),
            "--dpi-x",
            str(DPI),
            "--dpi-y",
            str(DPI),
            "-o",
            tmp_png,
            tmp_svg,
        ],
        check=True,
        capture_output=True,
    )

    img = Image.open(tmp_png).convert("RGBA")
    Path(tmp_svg).unlink()
    Path(tmp_png).unlink()
    return img


def _crop_svg_viewbox(svg_text: str, crop_left: float = 0.12) -> str:
    """Adjust SVG viewBox to crop the left portion (human).

    Works by:
    1. Finding or computing the SVG coordinate space
    2. Adding/modifying a viewBox that starts crop_left
       fraction into the width
    """
    # Extract width and height from SVG tag
    w_match = re.search(r'width="([^"]+)"', svg_text)
    h_match = re.search(r'height="([^"]+)"', svg_text)
    vb_match = re.search(r'viewBox="([^"]+)"', svg_text)

    if vb_match:
        # Has viewBox — parse and adjust
        parts = vb_match.group(1).split()
        vb_x = float(parts[0])
        vb_y = float(parts[1])
        vb_w = float(parts[2])
        vb_h = float(parts[3])
        new_x = vb_x + vb_w * crop_left
        new_w = vb_w * (1 - crop_left)
        new_vb = f"{new_x} {vb_y} {new_w} {vb_h}"
        svg_text = svg_text.replace(vb_match.group(0), f'viewBox="{new_vb}"')
    elif w_match and h_match:
        # No viewBox — create one from width/height
        w_str = w_match.group(1)
        h_str = h_match.group(1)
        # Handle mm units (orca)
        if "mm" in w_str:
            w_val = float(w_str.replace("mm", ""))
            h_val = float(h_str.replace("mm", ""))
        else:
            w_val = float(w_str)
            h_val = float(h_str)
        new_x = w_val * crop_left
        new_w = w_val * (1 - crop_left)
        new_vb = f"{new_x} 0 {new_w} {h_val}"
        # Insert viewBox after height attribute
        svg_text = svg_text.replace(
            h_match.group(0),
            f'{h_match.group(0)}\n   viewBox="{new_vb}"',
        )

    return svg_text


def crop_to_content(img: Image.Image, padding: int = 8) -> Image.Image:
    """Crop image to non-transparent content with padding."""
    bbox = img.getbbox()
    if bbox is None:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - padding)
    y0 = max(0, y0 - padding)
    x1 = min(img.width, x1 + padding)
    y1 = min(img.height, y1 + padding)
    return img.crop((x0, y0, x1, y1))


def crop_animal_only(img: Image.Image) -> Image.Image:
    """Crop to keep the animal body, strip human scale figure.

    Strategy: scan columns left-to-right. The human silhouette is a
    narrow vertical figure on the far left. The animal body is much
    wider and taller. We find the column where the "mass" of visible
    pixels first exceeds a threshold, then crop a small margin before
    that point to remove the human while keeping the full animal.

    Falls back to keeping rightmost 85% if detection fails.
    """
    import numpy as np

    arr = np.array(img)
    alpha = arr[:, :, 3]

    col_has = alpha.max(axis=0) > 10
    if not col_has.any():
        return img

    cols = np.where(col_has)[0]
    left = cols[0]
    right = cols[-1]
    content_w = right - left
    if content_w < 20:
        return crop_to_content(img)

    # Compute vertical span (height of content) per column
    spans = np.zeros(img.width, dtype=int)
    for c in range(left, right + 1):
        rows = np.where(alpha[:, c] > 10)[0]
        if len(rows) > 0:
            spans[c] = rows[-1] - rows[0]

    # The animal body will have a much larger vertical span
    # than the human figure. Find where span exceeds 60% of
    # the maximum span — that's the animal body start.
    max_span = spans.max()
    if max_span < 10:
        return crop_to_content(img)

    threshold = max_span * 0.5
    # Scan from left — find the first column with big span
    animal_start = left
    for c in range(left, right + 1):
        if spans[c] >= threshold:
            animal_start = c
            break

    # Add a small margin before animal_start to not clip it
    margin = max(8, int(content_w * 0.01))
    crop_x = max(0, animal_start - margin)

    # Only crop if the human takes meaningful space (>3% width)
    human_fraction = (animal_start - left) / content_w
    if human_fraction < 0.03:
        return crop_to_content(img)

    cropped = img.crop((crop_x, 0, img.width, img.height))
    return crop_to_content(cropped)


def draw_annotation(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    cx: int,
    cy: int,
    text: str,
    color: str,
    anchor: str = "left",
) -> None:
    """Draw annotation line + label from (cx,cy) to (x,y)."""
    # Leader line
    draw.line([(cx, cy), (x, y)], fill=color, width=1)
    # Circle at feature point
    r = 4
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=1)
    # Text
    offset = 8 if anchor == "left" else -8
    a = "la" if anchor == "left" else "ra"
    draw.text((x + offset, y), text, fill=color, font=FONT_ANN, anchor=a)


# ── Stage composers ───────────────────────────────────────────


def compose_stage(
    species_list: list[dict], title: str | None = None, canvas_height: int = 380
) -> Image.Image:
    """Compose a row of species images with labels.

    Animals are scaled to fit their column width — never wider.
    Canvas height shrinks to the tallest species + labels so
    there is no wasted vertical space.

    Each dict: {name, file, fill, stroke, label, sublabel?,
                ann_color}
    """
    n = len(species_list)

    # Render each species
    rendered = []
    for sp in species_list:
        svg_path = WIKIMEDIA / sp["file"]
        if not svg_path.exists():
            print(f"  WARNING: {svg_path} not found, skipping")
            continue
        img = render_svg(
            svg_path,
            sp["fill"],
            sp["stroke"],
            height=RENDER_HEIGHT,
            name=sp.get("name", ""),
        )
        img = crop_to_content(img)
        rendered.append((sp, img))

    if not rendered:
        return Image.new(
            "RGBA",
            (CANVAS_WIDTH, canvas_height),
            (0, 0, 0, 0),
        )

    # Layout constants
    col_width = CANVAS_WIDTH // n
    padding = 16
    label_zone = 80  # bottom area for labels
    title_zone = 40 if title else 0
    top_pad = 8

    # First pass: scale each animal to fit strictly within
    # its column width — never overflow
    max_h = 0
    scaled = []
    for sp, img in rendered:
        avail_w = col_width - padding * 2
        scale = avail_w / img.width
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        max_h = max(max_h, new_h)
        scaled.append((sp, img, new_w, new_h))

    # Dynamic canvas: shrink to tallest species + labels
    animal_zone = min(
        max_h + 16,
        canvas_height - label_zone - title_zone - top_pad,
    )
    actual_h = title_zone + top_pad + animal_zone + label_zone

    canvas = Image.new(
        "RGBA",
        (CANVAS_WIDTH, actual_h),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(canvas)

    # Title
    if title:
        draw.text(
            (CANVAS_WIDTH // 2, 8),
            title,
            fill=LABEL_COLOR,
            font=FONT_TITLE,
            anchor="mt",
        )

    for i, (sp, img, new_w, new_h) in enumerate(scaled):
        cx = col_width * i + col_width // 2

        # Cap at animal zone if needed
        if new_h > animal_zone:
            ratio = animal_zone / new_h
            new_w = int(new_w * ratio)
            new_h = animal_zone

        resized = img.resize((new_w, new_h), Image.LANCZOS)

        # Center horizontally, bottom-align in animal zone
        ax = cx - new_w // 2
        ay = title_zone + top_pad + animal_zone - new_h
        canvas.paste(resized, (ax, ay), resized)

        # Separator line (except after last)
        if i < n - 1:
            sep_x = col_width * (i + 1)
            draw.line(
                [(sep_x, title_zone + 10), (sep_x, actual_h - 20)],
                fill="#475569",
                width=1,
            )

        # Species label
        label_y = actual_h - label_zone + 8
        draw.text(
            (cx, label_y),
            sp["label"],
            fill=sp.get("label_color", LABEL_COLOR),
            font=FONT_LABEL,
            anchor="mt",
        )

        # Sub-label
        if "sublabel" in sp:
            draw.text(
                (cx, label_y + 30),
                sp["sublabel"],
                fill=sp.get("ann_color", SUBLABEL),
                font=FONT_SUB,
                anchor="mt",
            )

    return canvas


# ── Stage definitions ─────────────────────────────────────────


def make_stage_start():
    """Stage 1: Whale vs Dolphin vs Porpoise comparison."""
    species = [
        {
            "name": "blue_whale",
            "file": "blue_whale.svg",
            "fill": BLUE_FILL,
            "stroke": BLUE,
            "label": "Whale",
            "sublabel": "4–30 m",
            "label_color": BLUE,
            "ann_color": ANN_BLUE,
        },
        {
            "name": "bottlenose_dolphin",
            "file": "bottlenose_dolphin.svg",
            "fill": TEAL_FILL,
            "stroke": TEAL,
            "label": "Dolphin",
            "sublabel": "1.5–9 m",
            "label_color": TEAL,
            "ann_color": ANN_TEAL,
        },
        {
            "name": "harbour_porpoise",
            "file": "harbour_porpoise.svg",
            "fill": PURPLE_FILL,
            "stroke": PURPLE,
            "label": "Porpoise",
            "sublabel": "1.2–2.5 m",
            "label_color": PURPLE,
            "ann_color": ANN_PURPLE,
        },
    ]
    return compose_stage(species, canvas_height=360)


def make_stage_whale_kind():
    """Stage 2: Baleen vs Toothed whale comparison."""
    species = [
        {
            "name": "right_whale",
            "file": "right_whale.svg",
            "fill": TEAL_FILL,
            "stroke": TEAL,
            "label": "Baleen Whale",
            "sublabel": "Filter feeders · 2 blowholes",
            "label_color": TEAL,
            "ann_color": ANN_TEAL,
        },
        {
            "name": "sperm_whale",
            "file": "sperm_whale.svg",
            "fill": PURPLE_FILL,
            "stroke": PURPLE,
            "label": "Toothed Whale",
            "sublabel": "Active hunters · 1 blowhole",
            "label_color": PURPLE,
            "ann_color": ANN_PURPLE,
        },
    ]
    return compose_stage(species, canvas_height=360)


def make_stage_baleen():
    """Stage 3: Baleen species — Right, Humpback, Fin, Blue."""
    species = [
        {
            "name": "right_whale",
            "file": "right_whale.svg",
            "fill": TEAL_FILL,
            "stroke": TEAL,
            "label": "Right Whale",
            "sublabel": "Callosities · No dorsal",
            "label_color": TEAL,
            "ann_color": ANN_TEAL,
        },
        {
            "name": "humpback_whale",
            "file": "humpback_whale.svg",
            "fill": TEAL_FILL,
            "stroke": TEAL,
            "label": "Humpback",
            "sublabel": "Long pectoral fins",
            "label_color": TEAL,
            "ann_color": ANN_TEAL,
        },
        {
            "name": "fin_whale",
            "file": "fin_whale.svg",
            "fill": TEAL_FILL,
            "stroke": TEAL,
            "label": "Fin Whale",
            "sublabel": "Tall sickle dorsal",
            "label_color": TEAL,
            "ann_color": ANN_TEAL,
        },
        {
            "name": "blue_whale",
            "file": "blue_whale.svg",
            "fill": TEAL_FILL,
            "stroke": TEAL,
            "label": "Blue Whale",
            "sublabel": "Mottled blue-grey",
            "label_color": TEAL,
            "ann_color": ANN_TEAL,
        },
    ]
    return compose_stage(species, canvas_height=360)


def make_stage_toothed():
    """Stage 4: Toothed species — Sperm, Beaked, Beluga, Narwhal."""
    species = [
        {
            "name": "sperm_whale",
            "file": "sperm_whale.svg",
            "fill": PURPLE_FILL,
            "stroke": PURPLE,
            "label": "Sperm Whale",
            "sublabel": "Massive squared head",
            "label_color": PURPLE,
            "ann_color": ANN_PURPLE,
        },
        {
            "name": "cuviers_beaked_whale",
            "file": "cuviers_beaked_whale.svg",
            "fill": PURPLE_FILL,
            "stroke": PURPLE,
            "label": "Beaked Whale",
            "sublabel": "Elongated beak · Scars",
            "label_color": PURPLE,
            "ann_color": ANN_PURPLE,
        },
        {
            "name": "beluga",
            "file": "beluga.svg",
            "fill": "#b8c9e0",
            "stroke": "#e2e8f0",
            "label": "Beluga",
            "sublabel": "All white · No dorsal",
            "label_color": "#e2e8f0",
            "ann_color": "#e2e8f0",
        },
        {
            "name": "narwhal",
            "file": "narwhal.svg",
            "fill": PURPLE_FILL,
            "stroke": PURPLE,
            "label": "Narwhal",
            "sublabel": "Spiral tusk",
            "label_color": PURPLE,
            "ann_color": ANN_PURPLE,
        },
    ]
    return compose_stage(species, canvas_height=360)


def make_stage_dolphin():
    """Stage 5: Dolphin species — Orca, Bottlenose, Common, Pilot, Risso's."""
    species = [
        {
            "name": "orca",
            "file": "orca.svg",
            "fill": TEAL_FILL,
            "stroke": TEAL,
            "label": "Orca",
            "sublabel": "Tall dorsal · Eye patch",
            "label_color": TEAL,
            "ann_color": ANN_TEAL,
        },
        {
            "name": "bottlenose_dolphin",
            "file": "bottlenose_dolphin.svg",
            "fill": TEAL_FILL,
            "stroke": TEAL,
            "label": "Bottlenose",
            "sublabel": "Short beak · Curved fin",
            "label_color": TEAL,
            "ann_color": ANN_TEAL,
        },
        {
            "name": "common_dolphin",
            "file": "common_dolphin.svg",
            "fill": TEAL_FILL,
            "stroke": TEAL,
            "label": "Common",
            "sublabel": "Hourglass pattern",
            "label_color": TEAL,
            "ann_color": ANN_TEAL,
        },
        {
            "name": "pilot_whale",
            "file": "pilot_whale.svg",
            "fill": TEAL_FILL,
            "stroke": TEAL,
            "label": "Pilot Whale",
            "sublabel": "Bulbous melon",
            "label_color": TEAL,
            "ann_color": ANN_TEAL,
        },
        {
            "name": "rissos_dolphin",
            "file": "rissos_dolphin.svg",
            "fill": TEAL_FILL,
            "stroke": TEAL,
            "label": "Risso's",
            "sublabel": "No beak · Scarred",
            "label_color": TEAL,
            "ann_color": ANN_TEAL,
        },
    ]
    return compose_stage(species, canvas_height=360)


def make_stage_porpoise():
    """Stage 6: Porpoise species — Harbour, Dall's, Vaquita."""
    species = [
        {
            "name": "harbour_porpoise",
            "file": "harbour_porpoise.svg",
            "fill": PURPLE_FILL,
            "stroke": PURPLE,
            "label": "Harbour Porpoise",
            "sublabel": "Triangular fin · 1.5 m",
            "label_color": PURPLE,
            "ann_color": ANN_PURPLE,
        },
        {
            "name": "dalls_porpoise",
            "file": "dalls_porpoise.svg",
            "fill": PURPLE_FILL,
            "stroke": PURPLE,
            "label": "Dall's Porpoise",
            "sublabel": "White flanks · Rooster tail",
            "label_color": PURPLE,
            "ann_color": ANN_PURPLE,
        },
        {
            "name": "vaquita",
            "file": "vaquita.svg",
            "fill": PURPLE_FILL,
            "stroke": PURPLE,
            "label": "Vaquita",
            "sublabel": "Dark eye rings · < 10 left",
            "label_color": PURPLE,
            "ann_color": ANN_PURPLE,
        },
    ]
    return compose_stage(species, canvas_height=360)


STAGES = [
    ("stage_start_comparison", make_stage_start),
    ("stage_whale_kind_comparison", make_stage_whale_kind),
    ("stage_baleen_species", make_stage_baleen),
    ("stage_toothed_species", make_stage_toothed),
    ("stage_dolphin_species", make_stage_dolphin),
    ("stage_porpoise_species", make_stage_porpoise),
]


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    for name, fn in STAGES:
        print(f"Generating {name}...")
        img = fn()
        out_path = OUTPUT / f"{name}.png"
        img.save(str(out_path), "PNG", optimize=True)
        print(f"  → {out_path.name}  {img.size[0]}×{img.size[1]}")

    print("\nDone! All 6 stage images generated.")


if __name__ == "__main__":
    main()

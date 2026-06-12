"""
Generate stylised whale identification wizard graphics via DALL-E 3 API.

Usage::

    export OPENAI_API_KEY="sk-..."
    uv run python docs/generate/\
        generate_wizard_graphics.py [--stages] [--all]

Outputs PNG images to frontend/public/wizard/{stages,species}/.
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import shutil
import sys
import time
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("openai package required: uv add openai")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont

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
STAGE_DIR = ROOT / "frontend" / "public" / "wizard" / "stages"
SPECIES_DIR = ROOT / "frontend" / "public" / "wizard" / "species"

# ── Shared style preamble ──────────────────────────────────────────
# Every prompt starts with this to lock a consistent visual style.
STYLE = (
    "Scientific field-guide illustration style. "
    "Clean, elegant line art with soft watercolour washes on a very dark "
    "navy-black background, almost black with a hint of deep blue. "
    "Muted teal, cyan, and indigo accent colours. "
    "CRITICAL: absolutely no text, no labels, no words, no letters, "
    "no numbers, no writing of any kind anywhere in the image. "
    "No photo-realism — stylised, educational, and beautiful. "
    "No borders or frames. Horizontal landscape composition. "
    "Each animal must be clearly separated with visible gaps between them."
)

# ── Stage guidance graphics ────────────────────────────────────────
STAGE_PROMPTS: dict[str, str] = {
    "stage_start_comparison": (
        f"{STYLE} "
        "Size comparison of three marine mammals aligned at bottom, viewed "
        "from the side. The whale dominates the frame — it is ENORMOUS, "
        "filling 80 percent of the image height. The dolphin is tiny beside "
        "it, only about one-eighth the whale's length. The porpoise is even "
        "tinier, about half the dolphin's size. The massive scale difference "
        "is the whole point of the image. The whale is teal-toned with a "
        "visible blow spout, the dolphin is indigo with a curved dorsal fin "
        "and beak, the porpoise is orange with a small triangular fin and "
        "blunt head. All three aligned along the same baseline to emphasise "
        "the extreme size contrast."
    ),
    "stage_whale_kind_comparison": (
        f"{STYLE} "
        "Exactly two whales, side by side in profile. "
        "Left half: a baleen whale in teal tones with its mouth open "
        "showing curtains of baleen plates hanging from the upper jaw, "
        "a wide rounded body. "
        "Right half: a toothed whale in purple tones with its jaw open "
        "showing rows of conical teeth, a more streamlined body. "
        "A thin vertical dashed line separates the two halves. "
        "Strong colour contrast between the two sides."
    ),
    "stage_baleen_species": (
        f"{STYLE} "
        "Exactly four whale silhouettes in profile, swimming right, "
        "evenly spaced with clear gaps between them. Teal colour palette. "
        "First whale: black body, NO dorsal fin at all, rough white "
        "patches on its head. "
        "Second whale: dark with a small hump on its back, extremely "
        "long pectoral fins extending below. "
        "Third whale: very large and sleek, tall curved dorsal fin, "
        "one side of the jaw is white. "
        "Fourth whale: enormous mottled blue-grey body, a tiny dorsal "
        "fin set very far back near the tail."
    ),
    "stage_toothed_species": (
        f"{STYLE} "
        "Exactly four whale silhouettes in profile, evenly spaced with "
        "clear gaps. Purple and lavender colour palette. "
        "First: a massive whale with a huge rectangular head that takes "
        "up a third of its body, wrinkled greyish skin. "
        "Second: a slender whale with a long pointed snout like a beak, "
        "small fin near the tail, thin scratches across its body. "
        "Third: a completely white whale with a smooth rounded bulging "
        "forehead, no dorsal fin at all, plump body. "
        "Fourth: a grey spotted whale with a very long straight spiral "
        "horn projecting from its head, no dorsal fin."
    ),
    "stage_dolphin_species": (
        f"{STYLE} "
        "Exactly five dolphins in profile, evenly spaced with clear gaps "
        "between each one. Indigo and blue-violet colour palette. "
        "First: a large black-and-white dolphin with a very tall straight "
        "dorsal fin and a white oval patch near the eye. "
        "Second: a plain grey dolphin with a short snout and a gently "
        "curved dorsal fin. "
        "Third: a slender dolphin with a striking yellow and grey "
        "hourglass pattern on its side. "
        "Fourth: a dark nearly-black dolphin with a rounded bulging "
        "forehead and a low wide dorsal fin. "
        "Fifth: a pale whitish-grey dolphin covered in scratches, with "
        "a blunt rounded head and no snout."
    ),
    "stage_porpoise_species": (
        f"{STYLE} "
        "Exactly three small porpoises in profile, evenly spaced with "
        "clear gaps. Orange and warm amber colour palette. "
        "First: a small grey-brown porpoise with a small triangular "
        "dorsal fin and a blunt rounded head, no beak at all. "
        "Second: a stocky black porpoise with a bold white patch on "
        "its flank, kicking up a rooster-tail spray of water behind it. "
        "Third: a very small pale grey porpoise with distinctive dark "
        "circles around its eyes and dark markings on its lips."
    ),
}

# Column labels for Pillow overlay.  column[0] = title, rest = features.
STAGE_LABELS: dict[str, list[list[str]]] = {
    "stage_start_comparison": [
        ["Whale", "~25 m"],
        ["Dolphin", "~3 m"],
        ["Porpoise", "~1.5 m"],
    ],
    "stage_whale_kind_comparison": [
        ["Baleen Whales", "Filter feeders", "2 blowholes \u00b7 V-blow"],
        ["Toothed Whales", "Active hunters", "1 blowhole \u00b7 Teeth"],
    ],
    "stage_baleen_species": [
        ["Right Whale", "No dorsal fin", "Callosities"],
        ["Humpback", "Long pectoral fins", "Knobby head"],
        ["Fin Whale", "Asymmetric jaw", "Tall sickle dorsal"],
        ["Blue Whale", "Tiny dorsal far back", "Mottled blue-grey"],
    ],
    "stage_toothed_species": [
        ["Sperm Whale", "Squared head", "Forward-left blow"],
        ["Beaked Whale", "Elongated beak", "Linear scars"],
        ["Beluga", "All white", "Rounded melon"],
        ["Narwhal", "Spiral tusk", "No dorsal fin"],
    ],
    "stage_dolphin_species": [
        ["Orca", "Black & white", "Tall dorsal"],
        ["Bottlenose", "Curved dorsal", "Short beak"],
        ["Common", "Hourglass pattern", "Slender"],
        ["Pilot Whale", "Bulbous head", "Low dorsal"],
        ["Risso's", "Scarred body", "No beak"],
    ],
    "stage_porpoise_species": [
        ["Harbour", "Triangular dorsal", "Blunt head"],
        ["Dall's", "Rooster-tail spray", "Black & white"],
        ["Vaquita", "Dark eye rings", "Lip patches"],
    ],
}

# ── Species graphics ───────────────────────────────────────────────
# Each species gets a stylised portrait with key ID features highlighted.
_SPECIES_STYLE = (
    "Scientific field-guide portrait illustration. Stylised, elegant "
    "watercolour-and-ink on a very dark navy-black background, almost "
    "black with a hint of deep blue. "
    "The animal is shown in a natural swimming pose from a slightly "
    "angled side view. Only ONE single animal in the image, centred. "
    "CRITICAL: absolutely no text, no labels, no words, no letters, "
    "no numbers, no writing of any kind anywhere in the image. "
    "Muted oceanic colour palette. Beautiful, educational, "
    "not photorealistic. Square composition."
)

SPECIES_PROMPTS: dict[str, str] = {
    # Baleen whales
    "right_whale": (
        f"{_SPECIES_STYLE} North Atlantic right whale. Black body, no dorsal "
        "fin, rough white callosities on head and jaw. V-shaped blow."
    ),
    "southern_right_whale": (
        f"{_SPECIES_STYLE} Southern right whale. Dark body, prominent white "
        "callosities on head, no dorsal fin. Seen near coast."
    ),
    "humpback": (
        f"{_SPECIES_STYLE} Humpback whale breaching or diving with flukes "
        "raised. Very long white pectoral fins, knobby tubercles on head, "
        "black-and-white fluke pattern."
    ),
    "fin_whale": (
        f"{_SPECIES_STYLE} Fin whale in profile. Very large, sleek body. "
        "Asymmetric jaw colouring — right side white, left side dark. "
        "Tall sickle-shaped dorsal fin."
    ),
    "blue_whale": (
        f"{_SPECIES_STYLE} Blue whale surfacing. Enormous mottled blue-grey "
        "body. Tiny dorsal fin positioned far back. Broad flat U-shaped "
        "head."
    ),
    "minke_whale": (
        f"{_SPECIES_STYLE} Minke whale. Small rorqual with pointed snout. "
        "White bands on dark flippers. Curved dorsal fin."
    ),
    "sei_whale": (
        f"{_SPECIES_STYLE} Sei whale in profile. Dark grey uniform body. "
        "Single central ridge on head. Tall sickle-shaped dorsal fin."
    ),
    "gray_whale": (
        f"{_SPECIES_STYLE} Gray whale. Mottled grey body covered with "
        "barnacles and orange whale lice. No dorsal fin — low hump and "
        "knuckle ridges along tail stock. Heart-shaped blow."
    ),
    "bowhead": (
        f"{_SPECIES_STYLE} Bowhead whale. Massive triangular head, strongly "
        "bowed lower jaw with white chin patch. No dorsal fin. Arctic "
        "setting with ice."
    ),
    "brydes_whale": (
        f"{_SPECIES_STYLE} Bryde's whale. Three parallel ridges on top of "
        "head. Tropical waters. Sleek body with curved dorsal fin."
    ),
    "rices_whale": (
        f"{_SPECIES_STYLE} Rice's whale. Similar to Bryde's whale with "
        "three head ridges. Warm Gulf of Mexico waters. Extremely rare."
    ),
    "omuras_whale": (
        f"{_SPECIES_STYLE} Omura's whale. Asymmetric jaw colouring like fin "
        "whale but smaller. Tropical waters."
    ),
    "pygmy_right_whale": (
        f"{_SPECIES_STYLE} Pygmy right whale. Smallest baleen whale. "
        "Arched jawline, small hooked dorsal fin."
    ),
    # Toothed whales
    "sperm_whale": (
        f"{_SPECIES_STYLE} Sperm whale diving with flukes raised. Massive "
        "squared head taking one-third of body length. Wrinkled skin. "
        "Blow angled forward-left."
    ),
    "beaked_whale": (
        f"{_SPECIES_STYLE} Beaked whale (Cuvier's or Blainville's). "
        "Elongated beak, small dorsal fin far back, linear scars on body."
    ),
    "narwhal": (
        f"{_SPECIES_STYLE} Narwhal. Mottled grey-brown body, no dorsal fin. "
        "Male with long spiral tusk extending from head. Arctic ice setting."
    ),
    "beluga": (
        f"{_SPECIES_STYLE} Beluga whale. All-white adult, rounded bulbous "
        "melon forehead, no dorsal fin. Flexible neck."
    ),
    "dwarf_sperm_whale": (
        f"{_SPECIES_STYLE} Dwarf sperm whale. Very small, shark-like "
        "profile. Bracket-shaped pale mark behind eye resembling a false "
        "gill slit."
    ),
    "pygmy_sperm_whale": (
        f"{_SPECIES_STYLE} Pygmy sperm whale. Small, shark-like. False gill "
        "mark behind eye. Lower dorsal fin than dwarf sperm whale. "
        "Floating motionless at the surface."
    ),
    # Dolphins
    "orca": (
        f"{_SPECIES_STYLE} Orca (killer whale). Striking black and white "
        "pattern. Tall erect dorsal fin. White eye patch. Grey saddle patch "
        "behind dorsal fin."
    ),
    "bottlenose_dolphin": (
        f"{_SPECIES_STYLE} Bottlenose dolphin. Robust grey body, short "
        "stubby beak, curved dorsal fin. Friendly expression."
    ),
    "common_dolphin": (
        f"{_SPECIES_STYLE} Common dolphin leaping. Distinctive hourglass "
        "colour pattern — yellow-tan forward, grey behind. Slender build."
    ),
    "spotted_dolphin": (
        f"{_SPECIES_STYLE} Atlantic spotted dolphin. Slender body covered "
        "with spots. Long beak."
    ),
    "striped_dolphin": (
        f"{_SPECIES_STYLE} Striped dolphin leaping acrobatically. Dark "
        "stripe from eye to flipper, second stripe from eye to flank."
    ),
    "whitesided_dolphin": (
        f"{_SPECIES_STYLE} Atlantic white-sided dolphin. White and yellow "
        "patches on flanks. Robust body."
    ),
    "rissos_dolphin": (
        f"{_SPECIES_STYLE} Risso's dolphin. Blunt rounded head with no beak. "
        "Heavily scarred grey body — older animals nearly white. Tall dorsal "
        "fin."
    ),
    "pilot_whale": (
        f"{_SPECIES_STYLE} Long-finned pilot whale. Dark body, bulbous "
        "rounded melon forehead, long low sickle dorsal fin. Shown in a "
        "social group of several individuals."
    ),
    "hectors_dolphin": (
        f"{_SPECIES_STYLE} Hector's dolphin. Very small. Distinctive "
        "rounded black dorsal fin. Grey body with white belly."
    ),
    # Porpoises
    "harbor_porpoise": (
        f"{_SPECIES_STYLE} Harbour porpoise. Small, dark grey-brown back, "
        "lighter flanks. Small triangular dorsal fin. Rounded head, no beak."
    ),
    "dalls_porpoise": (
        f"{_SPECIES_STYLE} Dall's porpoise swimming fast with distinctive "
        "rooster-tail spray. Stocky black body with bold white flank "
        "patches."
    ),
    "vaquita": (
        f"{_SPECIES_STYLE} Vaquita porpoise. Small grey body with dark "
        "rings around eyes and dark lip patches. Shy, barely surfacing."
    ),
}

# Display names for Pillow label overlay on species portraits.
SPECIES_DISPLAY_NAMES: dict[str, str] = {
    "right_whale": "North Atlantic Right Whale",
    "southern_right_whale": "Southern Right Whale",
    "humpback": "Humpback Whale",
    "fin_whale": "Fin Whale",
    "blue_whale": "Blue Whale",
    "minke_whale": "Minke Whale",
    "sei_whale": "Sei Whale",
    "gray_whale": "Gray Whale",
    "bowhead": "Bowhead Whale",
    "brydes_whale": "Bryde\u2019s Whale",
    "rices_whale": "Rice\u2019s Whale",
    "omuras_whale": "Omura\u2019s Whale",
    "pygmy_right_whale": "Pygmy Right Whale",
    "sperm_whale": "Sperm Whale",
    "beaked_whale": "Beaked Whale",
    "narwhal": "Narwhal",
    "beluga": "Beluga",
    "dwarf_sperm_whale": "Dwarf Sperm Whale",
    "pygmy_sperm_whale": "Pygmy Sperm Whale",
    "orca": "Orca (Killer Whale)",
    "bottlenose_dolphin": "Bottlenose Dolphin",
    "common_dolphin": "Common Dolphin",
    "spotted_dolphin": "Atlantic Spotted Dolphin",
    "striped_dolphin": "Striped Dolphin",
    "whitesided_dolphin": "White-sided Dolphin",
    "rissos_dolphin": "Risso\u2019s Dolphin",
    "pilot_whale": "Pilot Whale",
    "hectors_dolphin": "Hector\u2019s Dolphin",
    "harbor_porpoise": "Harbour Porpoise",
    "dalls_porpoise": "Dall\u2019s Porpoise",
    "vaquita": "Vaquita",
}

# ── Per-species annotation data ────────────────────────────────────
# Each entry: list of (x_pct, y_pct, label, anchor_direction).
# Coordinates are percentages of the 1024×1024 image.
# Anchor: "tl"=top-left, "tr"=top-right, "bl"=bottom-left,
#         "br"=bottom-right, "t"=top, "b"=bottom, "l"=left, "r"=right
#
# Animal is centred, side-view facing right.  Head ≈ left 20-30 %,
# dorsal ≈ 45-55 % from left, tail ≈ 75-85 % from left.

SPECIES_ANNOTATIONS: dict[str, list[tuple[int, int, str, str]]] = {
    # ── Baleen whales ──────────────────────────────────
    "right_whale": [
        (24, 32, "White callosities", "tl"),
        (54, 22, "No dorsal fin", "tr"),
        (16, 12, "V-shaped blow", "tl"),
        (80, 40, "Broad black flukes", "tr"),
    ],
    "southern_right_whale": [
        (24, 32, "Callosities on head", "tl"),
        (54, 22, "No dorsal fin", "tr"),
        (48, 60, "Southern Hemisphere", "br"),
    ],
    "humpback": [
        (22, 34, "Knobby tubercles", "tl"),
        (36, 62, "Long white pectoral fins", "bl"),
        (78, 34, "Unique fluke pattern", "tr"),
        (52, 22, "Dorsal hump", "tr"),
    ],
    "fin_whale": [
        (20, 48, "Asymmetric jaw colour", "l"),
        (55, 20, "Tall sickle dorsal", "tr"),
        (42, 40, "Very long, sleek body", "br"),
    ],
    "blue_whale": [
        (68, 24, "Tiny dorsal far back", "tr"),
        (22, 36, "Flat U-shaped head", "tl"),
        (44, 44, "Mottled blue-grey", "br"),
    ],
    "minke_whale": [
        (34, 58, "White flipper bands", "bl"),
        (18, 38, "Pointed triangular snout", "tl"),
        (52, 20, "Curved dorsal fin", "tr"),
    ],
    "sei_whale": [
        (22, 32, "Single head ridge", "tl"),
        (55, 18, "Tall sickle dorsal", "tr"),
        (44, 48, "Uniform dark grey", "br"),
    ],
    "gray_whale": [
        (40, 40, "Barnacles & whale lice", "tr"),
        (64, 26, "Knuckle ridges", "tr"),
        (16, 12, "Heart-shaped blow", "tl"),
    ],
    "bowhead": [
        (26, 36, "Massive triangular head", "tl"),
        (22, 56, "White chin patch", "bl"),
        (56, 24, "No dorsal fin", "tr"),
    ],
    "brydes_whale": [
        (22, 30, "Three head ridges", "tl"),
        (55, 20, "Curved dorsal fin", "tr"),
    ],
    "rices_whale": [
        (22, 30, "Three head ridges", "tl"),
        (55, 20, "Dorsal fin", "tr"),
        (46, 66, "Gulf of Mexico only", "b"),
    ],
    "omuras_whale": [
        (20, 48, "Asymmetric jaw colour", "l"),
        (44, 42, "Smaller than fin whale", "br"),
    ],
    "pygmy_right_whale": [
        (22, 46, "Arched jawline", "l"),
        (55, 20, "Small hooked dorsal", "tr"),
    ],
    # ── Toothed whales ─────────────────────────────────
    "sperm_whale": [
        (26, 36, "Massive squared head", "tl"),
        (18, 12, "Forward-left blow", "tl"),
        (44, 44, "Wrinkled skin", "br"),
        (80, 34, "Broad triangular flukes", "tr"),
    ],
    "beaked_whale": [
        (16, 38, "Elongated beak", "tl"),
        (66, 24, "Small dorsal far back", "tr"),
        (42, 46, "Linear body scars", "br"),
    ],
    "narwhal": [
        (10, 34, "Spiral tusk", "tl"),
        (56, 26, "No dorsal fin", "tr"),
        (42, 44, "Mottled grey body", "br"),
    ],
    "beluga": [
        (44, 44, "All-white body", "br"),
        (24, 30, "Rounded melon", "tl"),
        (56, 26, "No dorsal fin", "tr"),
    ],
    "dwarf_sperm_whale": [
        (30, 40, "False gill mark", "l"),
        (55, 20, "Taller dorsal fin", "tr"),
        (40, 50, "Shark-like profile", "br"),
    ],
    "pygmy_sperm_whale": [
        (30, 40, "False gill mark", "l"),
        (55, 24, "Low dorsal fin", "tr"),
        (48, 56, "Floats motionless", "br"),
    ],
    # ── Dolphins ───────────────────────────────────────
    "orca": [
        (50, 12, "Tall dorsal fin (1.8 m)", "t"),
        (24, 34, "White eye patch", "tl"),
        (58, 38, "Grey saddle patch", "tr"),
        (40, 58, "Black & white body", "bl"),
    ],
    "bottlenose_dolphin": [
        (16, 38, "Short stubby beak", "tl"),
        (50, 18, "Curved dorsal fin", "tr"),
        (42, 50, "Robust grey body", "br"),
    ],
    "common_dolphin": [
        (38, 44, "Hourglass pattern", "bl"),
        (50, 18, "Curved dorsal fin", "tr"),
        (48, 50, "Yellow-tan forward, grey behind", "r"),
    ],
    "spotted_dolphin": [
        (42, 44, "Spots increase with age", "br"),
        (14, 38, "Long beak", "tl"),
    ],
    "striped_dolphin": [
        (32, 42, "Eye-to-flipper stripe", "bl"),
        (40, 52, "Eye-to-flank stripe", "br"),
    ],
    "whitesided_dolphin": [
        (44, 48, "White & yellow patches", "br"),
        (50, 18, "Dorsal fin", "tr"),
    ],
    "rissos_dolphin": [
        (20, 34, "Blunt head, no beak", "tl"),
        (42, 44, "Heavily scarred body", "br"),
        (50, 16, "Tall dorsal fin", "t"),
    ],
    "pilot_whale": [
        (22, 30, "Bulbous melon head", "tl"),
        (50, 20, "Low sickle dorsal", "tr"),
        (42, 54, "Dark body", "br"),
    ],
    "hectors_dolphin": [
        (50, 18, "Rounded black dorsal", "tr"),
        (42, 56, "Very small (\u223c1.4 m)", "br"),
    ],
    # ── Porpoises ──────────────────────────────────────
    "harbor_porpoise": [
        (50, 18, "Triangular dorsal fin", "tr"),
        (18, 36, "Blunt head, no beak", "tl"),
        (42, 54, "Small (1.5 m)", "br"),
    ],
    "dalls_porpoise": [
        (44, 48, "White flank patches", "bl"),
        (76, 22, "Rooster-tail spray", "tr"),
        (35, 38, "Stocky black body", "tl"),
    ],
    "vaquita": [
        (22, 34, "Dark eye rings", "tl"),
        (18, 50, "Dark lip patches", "bl"),
        (46, 58, "< 10 remaining", "br"),
    ],
}


# ── Pillow annotation + overlay helpers ────────────────────────────

# System font search: (file_path, ttc_face_index).
_FONT_PATHS: list[tuple[str, int]] = [
    (  # macOS Avenir Next Demi Bold
        "/System/Library/Fonts/Avenir Next.ttc",
        2,
    ),
    (  # macOS Supplemental (older macOS)
        "/System/Library/Fonts/Supplemental/Avenir Next.ttc",
        4,
    ),
    (  # macOS Helvetica
        "/System/Library/Fonts/Helvetica.ttc",
        0,
    ),
    (  # Linux DejaVu Sans
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        0,
    ),
]


def _find_font(
    size: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Find a clean system sans-serif font."""
    for fpath, idx in _FONT_PATHS:
        if Path(fpath).exists():
            try:
                return ImageFont.truetype(fpath, size, index=idx)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _add_bottom_gradient(
    img: Image.Image,
    height_frac: float = 0.28,
    max_alpha: int = 210,
) -> None:
    """Composite a transparent-to-dark gradient at the bottom."""
    w, h = img.size
    gh = int(h * height_frac)
    overlay = Image.new("RGBA", (w, gh), (0, 0, 0, 0))
    drw = ImageDraw.Draw(overlay)
    for y in range(gh):
        t = (y / gh) ** 1.5  # ease-in curve
        a = int(max_alpha * t)
        drw.line([(0, y), (w, y)], fill=(8, 12, 28, a))
    img.paste(overlay, (0, h - gh), overlay)


def _text_with_shadow(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, ...] = (255, 255, 255, 245),
    anchor: str = "mt",
) -> None:
    """Draw text with a soft outline shadow."""
    x, y = xy
    shadow = (0, 0, 0, 160)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                draw.text(
                    (x + dx, y + dy),
                    text,
                    font=font,
                    fill=shadow,
                    anchor=anchor,
                )
    draw.text(
        (x + 1, y + 2),
        text,
        font=font,
        fill=(0, 0, 0, 120),
        anchor=anchor,
    )
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def overlay_stage_labels(
    img_path: Path,
    columns: list[list[str]],
) -> None:
    """Overlay evenly-spaced column labels on a stage image."""
    if not _HAS_PIL:
        log.warning("Pillow not installed \u2014 skipping labels")
        return
    img = Image.open(img_path).convert("RGBA")
    w, h = img.size
    _add_bottom_gradient(img, height_frac=0.30)
    draw = ImageDraw.Draw(img)

    title_font = _find_font(36)
    feat_font = _find_font(24)
    ncols = len(columns)
    col_w = w // ncols

    for i, col in enumerate(columns):
        cx = col_w * i + col_w // 2
        y_title = h - int(h * 0.22)
        _text_with_shadow(
            draw,
            (cx, y_title),
            col[0],
            title_font,
            fill=(255, 255, 255, 250),
        )
        for j, feat in enumerate(col[1:], start=1):
            fy = y_title + j * 34
            _text_with_shadow(
                draw,
                (cx, fy),
                feat,
                feat_font,
                fill=(176, 196, 210, 220),
            )

    img.convert("RGB").save(img_path)
    log.info("  \U0001f3f7  Labels overlaid: %s", img_path.name)


def overlay_species_label(
    img_path: Path,
    display_name: str,
) -> None:
    """Overlay species common name on a species portrait (legacy)."""
    if not _HAS_PIL:
        log.warning("Pillow not installed — skipping labels")
        return
    img = Image.open(img_path).convert("RGBA")
    w, h = img.size
    _add_bottom_gradient(img, height_frac=0.18, max_alpha=200)
    draw = ImageDraw.Draw(img)
    name_font = _find_font(44)
    _text_with_shadow(
        draw,
        (w // 2, h - int(h * 0.07)),
        display_name,
        name_font,
        fill=(255, 255, 255, 245),
    )
    img.convert("RGB").save(img_path)
    log.info("  🏷  Label overlaid: %s", img_path.name)


# ── Annotation anchor geometry ─────────────────────────────────────
# Maps anchor direction → (angle_deg, text_pillow_anchor).
# angle_deg: direction from circle centre to text, 0 = right, CCW.
_ANCHOR_MAP: dict[str, tuple[float, str]] = {
    "tl": (135.0, "rm"),  # text right-middle aligned
    "tr": (45.0, "lm"),
    "bl": (225.0, "rm"),
    "br": (315.0, "lm"),
    "t": (90.0, "ms"),  # text middle-baseline-ish
    "b": (270.0, "mt"),
    "l": (180.0, "rm"),
    "r": (0.0, "lm"),
}


def overlay_species_annotations(
    img_path: Path,
    display_name: str,
    annotations: list[tuple[int, int, str, str]],
) -> None:
    """Draw field-guide annotations on a species portrait.

    For each annotation: a teal circle at the feature location,
    a leader line with an elbow, and a text label on a dark pill.
    The species common name is rendered at the bottom.
    """
    if not _HAS_PIL:
        log.warning("Pillow not installed — skipping")
        return

    img = Image.open(img_path).convert("RGBA")
    w, h = img.size

    # Scale all fixed-pixel constants relative to image size.
    # Annotations were designed for 1024×1024; for smaller images
    # (e.g. 800×534 NOAA) everything shrinks proportionally.
    s = min(w, h) / 1024

    # Create a transparent overlay for annotations so they
    # composite cleanly over the base image.
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    label_font = _find_font(max(12, int(22 * s)))
    name_font = _find_font(max(18, int(42 * s)))

    # Annotation styling constants — scaled
    circle_r = max(6, int(16 * s))
    circle_colour = (0, 210, 210, 180)  # teal
    line_colour = (0, 210, 210, 140)
    line_width = max(1, int(2 * s))
    diag_len = max(20, int(50 * s))  # diagonal segment length
    horiz_len = max(14, int(35 * s))  # horizontal segment length
    pill_pad = max(3, int(6 * s))
    pill_fill = (8, 14, 30, 190)
    pill_radius = max(3, int(5 * s))
    text_fill = (240, 250, 255, 240)

    for x_pct, y_pct, label, anchor in annotations:
        cx = int(w * x_pct / 100)
        cy = int(h * y_pct / 100)

        angle_deg, text_anchor = _ANCHOR_MAP.get(anchor, (45.0, "lm"))
        rad = math.radians(angle_deg)
        dx = math.cos(rad)
        dy = -math.sin(rad)  # SVG/Pillow y-axis inverted

        # Circle ring (unfilled)
        draw.ellipse(
            [
                cx - circle_r,
                cy - circle_r,
                cx + circle_r,
                cy + circle_r,
            ],
            outline=circle_colour,
            width=2,
        )
        # Small filled centre dot
        dot_r = max(2, int(3 * s))
        draw.ellipse(
            [cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
            fill=circle_colour,
        )

        # Leader line: diagonal from circle edge → elbow
        gap = max(1, int(2 * s))
        start_x = cx + int(dx * (circle_r + gap))
        start_y = cy + int(dy * (circle_r + gap))
        elbow_x = cx + int(dx * (circle_r + diag_len))
        elbow_y = cy + int(dy * (circle_r + diag_len))

        # Horizontal tail from elbow
        # Direction: left if text anchor is "rm", right if "lm",
        # centre if "ms"/"mt"
        if text_anchor.startswith("r"):
            end_x = elbow_x - horiz_len
        elif text_anchor.startswith("l"):
            end_x = elbow_x + horiz_len
        else:
            end_x = elbow_x  # centred (no horiz segment)
        end_y = elbow_y

        # Draw leader line segments
        draw.line(
            [(start_x, start_y), (elbow_x, elbow_y)],
            fill=line_colour,
            width=line_width,
        )
        if end_x != elbow_x:
            draw.line(
                [(elbow_x, elbow_y), (end_x, end_y)],
                fill=line_colour,
                width=line_width,
            )

        # Text label on a dark pill background
        # Pillow textbbox needs the text position + anchor
        tx = end_x
        ty = end_y
        # Adjust for centred anchors
        nudge = max(2, int(4 * s))
        if text_anchor in ("ms", "mt"):
            ty = end_y - nudge if angle_deg == 90.0 else end_y + nudge

        bbox = draw.textbbox(
            (tx, ty),
            label,
            font=label_font,
            anchor=text_anchor,
        )
        draw.rounded_rectangle(
            [
                bbox[0] - pill_pad,
                bbox[1] - pill_pad,
                bbox[2] + pill_pad,
                bbox[3] + pill_pad,
            ],
            radius=pill_radius,
            fill=pill_fill,
        )
        draw.text(
            (tx, ty),
            label,
            font=label_font,
            fill=text_fill,
            anchor=text_anchor,
        )

    # Composite annotation overlay onto base image
    img = Image.alpha_composite(img, overlay)

    # Species name at bottom with gradient
    _add_bottom_gradient(img, height_frac=0.14, max_alpha=190)
    draw = ImageDraw.Draw(img)
    _text_with_shadow(
        draw,
        (w // 2, h - int(h * 0.055)),
        display_name,
        name_font,
        fill=(255, 255, 255, 245),
    )

    img.convert("RGB").save(img_path)
    log.info(
        "  🏷  Annotations overlaid: %s (%d features)",
        img_path.name,
        len(annotations),
    )


def generate_image(
    client: OpenAI,
    prompt: str,
    output_path: Path,
    size: str = "1792x1024",
    max_retries: int = 5,
) -> bool:
    """Generate a single image via DALL-E 3 and save to disk."""
    if output_path.exists():
        log.info("  ⏭  Already exists: %s", output_path.name)
        return True

    import urllib.request

    for attempt in range(1, max_retries + 1):
        try:
            log.info(
                "  ⏳ Generating %s (attempt %d/%d)…",
                output_path.name,
                attempt,
                max_retries,
            )
            resp = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size=size,
                quality="hd",
                response_format="url",
            )
            url = resp.data[0].url
            if not url:
                log.error(
                    "  ✗  No URL returned for %s",
                    output_path.name,
                )
                return False

            urllib.request.urlretrieve(url, str(output_path))
            log.info("  ✓  Saved %s", output_path.name)
            return True

        except Exception as e:
            err = str(e)
            if "500" in err or "server" in err.lower():
                wait = min(2**attempt, 60)
                log.warning(
                    "  ⚠  Server error on %s (attempt %d/%d), retrying in %ds: %s",
                    output_path.name,
                    attempt,
                    max_retries,
                    wait,
                    err[:120],
                )
                time.sleep(wait)
                continue
            elif "rate" in err.lower() or "429" in err:
                wait = min(2**attempt * 5, 120)
                log.warning(
                    "  ⚠  Rate limited on %s, waiting %ds…",
                    output_path.name,
                    wait,
                )
                time.sleep(wait)
                continue
            elif "content_policy" in err.lower():
                log.error(
                    "  ✗  Content policy rejection for %s: %s",
                    output_path.name,
                    err[:200],
                )
                return False
            else:
                log.error(
                    "  ✗  Failed %s: %s",
                    output_path.name,
                    err[:200],
                )
                if attempt < max_retries:
                    time.sleep(5)
                    continue
                return False

    log.error("  ✗  Exhausted retries for %s", output_path.name)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate wizard graphics via DALL-E 3"
    )
    parser.add_argument("--stages", action="store_true", help="Generate stage graphics")
    parser.add_argument(
        "--species", action="store_true", help="Generate species graphics"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all graphics",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Only generate a single key (e.g. 'humpback' or 'stage_start_comparison')",
    )
    parser.add_argument(
        "--reoverlay",
        action="store_true",
        help="Re-apply Pillow text overlays from saved raw "
        "images without calling DALL-E (free, instant)",
    )
    args = parser.parse_args()

    if not any(
        [
            args.stages,
            args.species,
            args.all,
            args.only,
            args.reoverlay,
        ]
    ):
        args.all = True

    if args.reoverlay:
        api_key = None
        client = None  # type: ignore[assignment]
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            log.error(
                "Set OPENAI_API_KEY environment variable.\n"
                "  export OPENAI_API_KEY='sk-...'"
            )
            sys.exit(1)
        client = OpenAI(api_key=api_key)

    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    SPECIES_DIR.mkdir(parents=True, exist_ok=True)
    stage_raw = STAGE_DIR / "raw"
    species_raw = SPECIES_DIR / "raw"
    stage_raw.mkdir(exist_ok=True)
    species_raw.mkdir(exist_ok=True)

    total = 0
    success = 0

    # Stage graphics (landscape 1792x1024)
    if args.all or args.stages or args.only or args.reoverlay:
        log.info("── Stage guidance graphics ──")
        for key, prompt in STAGE_PROMPTS.items():
            if args.only and args.only != key:
                continue
            raw_path = stage_raw / f"{key}.png"
            out = STAGE_DIR / f"{key}.png"

            if args.reoverlay:
                # Re-apply labels from saved raw image
                if raw_path.exists() and key in STAGE_LABELS:
                    shutil.copy2(raw_path, out)
                    overlay_stage_labels(out, STAGE_LABELS[key])
                continue

            total += 1
            if generate_image(client, prompt, raw_path, size="1792x1024"):
                success += 1
                # Copy raw → final, then overlay
                shutil.copy2(raw_path, out)
                if key in STAGE_LABELS:
                    overlay_stage_labels(out, STAGE_LABELS[key])
            # Rate limit: 5 images/min for DALL-E 3
            time.sleep(13)

    # Species graphics (square 1024x1024)
    if args.all or args.species or args.only or args.reoverlay:
        log.info("── Species identification graphics ──")
        for key, prompt in SPECIES_PROMPTS.items():
            if args.only and args.only != key:
                continue
            raw_path = species_raw / f"{key}.png"
            out = SPECIES_DIR / f"{key}.png"

            if args.reoverlay:
                if raw_path.exists():
                    name = SPECIES_DISPLAY_NAMES.get(key)
                    annot = SPECIES_ANNOTATIONS.get(key)
                    if name:
                        shutil.copy2(raw_path, out)
                        if annot:
                            overlay_species_annotations(out, name, annot)
                        else:
                            overlay_species_label(out, name)
                continue

            total += 1
            if generate_image(client, prompt, raw_path, size="1024x1024"):
                success += 1
                shutil.copy2(raw_path, out)
                name = SPECIES_DISPLAY_NAMES.get(key)
                annot = SPECIES_ANNOTATIONS.get(key)
                if name and annot:
                    overlay_species_annotations(out, name, annot)
                elif name:
                    overlay_species_label(out, name)
            time.sleep(13)

    log.info("Done: %d/%d generated successfully.", success, total)

    # Cost estimate
    stage_count = sum(1 for k in STAGE_PROMPTS if (STAGE_DIR / f"{k}.png").exists())
    species_count = sum(
        1 for k in SPECIES_PROMPTS if (SPECIES_DIR / f"{k}.png").exists()
    )
    cost = stage_count * 0.08 + species_count * 0.08  # HD DALL-E 3
    log.info(
        "Estimated cost: $%.2f (%d stage + %d species @ $0.08/image HD)",
        cost,
        stage_count,
        species_count,
    )


if __name__ == "__main__":
    main()

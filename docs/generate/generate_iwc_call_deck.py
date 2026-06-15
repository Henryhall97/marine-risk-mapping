"""Generate the IWC Modelling Briefing -- the call-deck PDF.

A single, self-contained briefing for the modelling review call
(Alice / Russell / Ellen). It pulls the whole story together:

  1. What the platform models today (current implementation).
  2. The modelling decisions behind each component and WHY.
  3. The tests / validation evidence that the models behave.
  4. Direct answers to the reviewer's (Russell's) four points.
  5. Where we are going -- the IWC-conformity roadmap (Tranches 2-3).
  6. How every component maps onto the two IWC standards.

Every major stage carries BOTH a plain-language "In plain terms" box
and the technical detail, so the document reads for a mixed audience.

Source of truth for the plan: /memories/repo/iwc-migration-plan.md and
the Tranche-1 execution log in /memories/repo/context.md.

Output: docs/pdfs/modelling/iwc_modelling_briefing.pdf
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from fpdf import FPDF  # noqa: E402

# ── Paths ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs" / "modelling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "iwc_modelling_briefing.pdf"

FIG_DIR = Path(__file__).resolve().parent.parent / "diagrams" / "call_deck"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Existing validation figures we embed (produced by validate_traffic_risk.py).
VAL_DIR = ROOT / "data" / "processed" / "ml" / "artifacts" / "validation"

# ── Palette (matches the navy/teal house style) ──────────────────────
NAVY = "#0F2041"
TEAL = "#009688"
AMBER = "#F39C12"
GREEN = "#2ECC71"
RED = "#D64045"
BLUE = "#3498DB"
PURPLE = "#8E44AD"
LIGHT = "#F0F5FA"
GREY = "#505050"


# ═══════════════════════════════════════════════════════════════════
# Figures (matplotlib) -- generated fresh each run
# ═══════════════════════════════════════════════════════════════════


def _save(fig, name):
    path = FIG_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def fig_architecture():
    """Data -> models -> two risk products schematic."""
    fig, ax = plt.subplots(figsize=(10, 5.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 56)
    ax.axis("off")

    def box(x, y, w, h, label, color, tc="white", fs=8.5):
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="round,pad=0.4,rounding_size=1.2",
                facecolor=color,
                edgecolor="none",
            )
        )
        ax.text(
            x + w / 2,
            y + h / 2,
            label,
            ha="center",
            va="center",
            fontsize=fs,
            color=tc,
            weight="bold",
        )

    # Column headers
    for cx, t in [
        (11, "DATA SOURCES"),
        (37, "AGGREGATION"),
        (62, "MODELS"),
        (87, "RISK PRODUCTS"),
    ]:
        ax.text(cx, 53, t, ha="center", fontsize=9.5, color=NAVY, weight="bold")

    # Data sources
    srcs = [
        "AIS vessel\ntraffic (3.1B)",
        "OBIS cetacean\nsightings (~1M)",
        "NOAA ship\nstrikes",
        "Bathymetry +\nocean covars",
        "Regulatory\nzones",
    ]
    for i, s in enumerate(srcs):
        box(2, 44 - i * 9, 18, 7, s, BLUE, fs=7.5)

    # Aggregation
    box(28, 30, 18, 9, "H3 res-7\nhex grid\n(1.9M cells)", GREY, fs=8)
    box(28, 17, 18, 9, "VTD strata\n(type x size\nx speed)", TEAL, fs=7.5)

    # Models
    box(54, 38, 18, 8, "SDM / ISDM\nensemble\n(6 species)", TEAL, fs=7.5)
    box(54, 27, 18, 8, "Traffic +\nGarrison Pleth", TEAL, fs=8)
    box(54, 16, 18, 8, "Proximity /\nhabitat /\nprotection", GREY, fs=7.5)

    # Products
    box(80, 33, 18, 9, "PRODUCT A\nScreening\ncomposite\n(7 sub-scores)", NAVY, fs=7.5)
    box(
        80,
        18,
        18,
        9,
        "PRODUCT B\nEncounter chain\nR = Dw x VTD x w\n(planned)",
        AMBER,
        fs=7,
    )

    # Arrows
    arrow = {"arrowstyle": "-|>", "color": "#888888", "lw": 1.4}
    for i in range(5):
        ax.annotate("", xy=(28, 34), xytext=(20, 47 - i * 9), arrowprops=arrow)
    ax.annotate("", xy=(54, 41), xytext=(46, 35), arrowprops=arrow)
    ax.annotate("", xy=(54, 31), xytext=(46, 22), arrowprops=arrow)
    ax.annotate("", xy=(54, 20), xytext=(46, 33), arrowprops=arrow)
    ax.annotate("", xy=(80, 37), xytext=(72, 41), arrowprops=arrow)
    ax.annotate("", xy=(80, 37), xytext=(72, 31), arrowprops=arrow)
    ax.annotate("", xy=(80, 23), xytext=(72, 30), arrowprops=arrow)
    ax.annotate("", xy=(80, 23), xytext=(72, 20), arrowprops=arrow)

    fig.tight_layout()
    return _save(fig, "architecture.png")


def fig_subscore_weights():
    """Standard vs ML composite sub-score weights."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))

    std = [
        ("Traffic intensity", 25),
        ("Cetacean presence", 25),
        ("Proximity blend", 15),
        ("Strike history", 10),
        ("Habitat suitability", 10),
        ("Protection gap", 10),
        ("Reference (Nisi)", 5),
    ]
    ml = [
        ("Whale x traffic", 30),
        ("Traffic intensity", 15),
        ("Whale ML exposure", 15),
        ("Proximity blend", 15),
        ("Strike history", 10),
        ("Protection gap", 10),
        ("Reference (Nisi)", 5),
    ]
    for ax, data, title in [
        (axes[0], std, "Product A -- Standard composite"),
        (axes[1], ml, "Product A -- ML-enhanced variant"),
    ]:
        labels = [d[0] for d in data][::-1]
        vals = [d[1] for d in data][::-1]
        colors = [TEAL if v >= 15 else GREY for v in vals]
        ax.barh(labels, vals, color=colors)
        for i, v in enumerate(vals):
            ax.text(v + 0.5, i, f"{v}%", va="center", fontsize=8, color=NAVY)
        ax.set_xlim(0, 36)
        ax.set_title(title, fontsize=10, color=NAVY, weight="bold")
        ax.tick_params(labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return _save(fig, "subscore_weights.png")


def fig_exposure_layering():
    """Exposure-first: base co-occurrence, then optional weighting."""
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 24)
    ax.axis("off")
    tiers = [
        (
            2,
            "BASE LAYER\nWhale x Vessel co-occurrence\n(no lethality assumption)",
            GREEN,
            "Reported first -- reviewer's request",
        ),
        (
            35,
            "OVERLAY 1\n+ Garrison speed-lethality\nP(lethal | speed, size, taxon)",
            TEAL,
            "Optional weighting",
        ),
        (
            68,
            "OVERLAY 2\n+ Encounter & avoidance\n(Phase 4-5, speed pathways)",
            AMBER,
            "Full speed-risk picture",
        ),
    ]
    for x, label, color, sub in tiers:
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (x, 7),
                28,
                12,
                boxstyle="round,pad=0.4,rounding_size=1.5",
                facecolor=color,
                edgecolor="none",
            )
        )
        ax.text(
            x + 14,
            13,
            label,
            ha="center",
            va="center",
            fontsize=8,
            color="white",
            weight="bold",
        )
        ax.text(
            x + 14,
            4.5,
            sub,
            ha="center",
            va="center",
            fontsize=7.5,
            color=GREY,
            style="italic",
        )
    arrow = {"arrowstyle": "-|>", "color": "#888888", "lw": 1.6}
    ax.annotate("", xy=(35, 13), xytext=(30, 13), arrowprops=arrow)
    ax.annotate("", xy=(68, 13), xytext=(63, 13), arrowprops=arrow)
    fig.tight_layout()
    return _save(fig, "exposure_layering.png")


def fig_lethality_curves():
    """V&T 2007 vs Garrison 2025 generic vs Garrison humpback."""
    v = np.linspace(2, 30, 200)

    def logistic(b0, b1):
        return 1.0 / (1.0 + np.exp(-(b0 + b1 * v)))

    vt = logistic(-4.89, 0.41)
    g_generic = logistic(-1.127, 0.129)
    g_hump = logistic(-1.266, 0.026)

    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(v, vt, color=RED, lw=2.4, label="V&T 2007 (b1=0.41/kn)")
    ax.plot(
        v, g_generic, color=TEAL, lw=2.4, label="Garrison 2025 generic (b1=0.129/kn)"
    )
    ax.plot(
        v,
        g_hump,
        color=BLUE,
        lw=2.4,
        ls="--",
        label="Garrison 2025 humpback (b1=0.026/kn)",
    )
    ax.axvline(10, color=GREY, ls=":", lw=1)
    ax.text(10.2, 0.04, "10 kn\nslow zone", fontsize=7.5, color=GREY)
    ax.set_xlabel("Vessel speed (knots)", fontsize=9)
    ax.set_ylabel("P(strike is lethal)", fontsize=9)
    ax.set_title(
        "Speed-lethality curves -- Garrison is shallower (lethality is only "
        "ONE speed pathway)",
        fontsize=9.5,
        color=NAVY,
        weight="bold",
    )
    ax.set_ylim(0, 1)
    ax.legend(fontsize=8.5, loc="center right")
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return _save(fig, "lethality_curves.png")


def fig_vtd_concept():
    """Ping counts vs true transit distance inside one cell."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    for ax in axes:
        ax.add_patch(
            mpatches.RegularPolygon(
                (0.5, 0.5),
                6,
                radius=0.46,
                orientation=0,
                facecolor=LIGHT,
                edgecolor=NAVY,
                lw=1.5,
            )
        )
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

    # Left: ping counts -- dwell bias
    rng = np.random.default_rng(3)
    px = 0.5 + (rng.random(14) - 0.5) * 0.5
    py = 0.5 + (rng.random(14) - 0.5) * 0.5
    axes[0].scatter(px, py, s=22, color=RED, zorder=3)
    axes[0].set_title(
        "OLD: ping COUNT\n(biased by dwell + AIS rate)",
        fontsize=9,
        color=RED,
        weight="bold",
    )

    # Right: transit distance -- track length
    axes[1].plot(
        [0.18, 0.45, 0.62, 0.85],
        [0.30, 0.55, 0.42, 0.72],
        color=TEAL,
        lw=3,
        zorder=3,
        marker="o",
        ms=4,
    )
    axes[1].set_title(
        "NEW: transit DISTANCE\n(track-km / km^2 = VTD)",
        fontsize=9,
        color=TEAL,
        weight="bold",
    )
    fig.tight_layout()
    return _save(fig, "vtd_concept.png")


def fig_sdm_auc():
    """Per-species spatial-CV AUC (Phase 1b retrain)."""
    data = [
        ("Right", 0.972),
        ("Gray", 0.947),
        ("Humpback", 0.919),
        ("Any whale", 0.901),
        ("Minke", 0.878),
        ("Fin", 0.775),
        ("Blue", 0.684),
        ("Sperm", 0.628),
    ]
    labels = [d[0] for d in data]
    vals = [d[1] for d in data]
    colors = [GREEN if v >= 0.85 else (AMBER if v >= 0.7 else RED) for v in vals]
    fig, ax = plt.subplots(figsize=(10, 3.8))
    bars = ax.bar(labels, vals, color=colors)
    for b, v in zip(bars, vals, strict=False):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v + 0.01,
            f"{v:.3f}",
            ha="center",
            fontsize=8,
            color=NAVY,
        )
    ax.axhline(0.7, color=GREY, ls=":", lw=1)
    ax.text(7.4, 0.71, "0.70", fontsize=7.5, color=GREY)
    ax.set_ylim(0.5, 1.02)
    ax.set_ylabel("Spatial-CV AUC", fontsize=9)
    ax.set_title(
        "Per-species SDM discrimination (spatial block CV, post Phase-1b "
        "bias correction)",
        fontsize=9.5,
        color=NAVY,
        weight="bold",
    )
    ax.tick_params(labelsize=8.5)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return _save(fig, "sdm_auc.png")


def fig_roadmap():
    """Tranche / phase roadmap with status."""
    fig, ax = plt.subplots(figsize=(10, 4.8))
    rows = [
        ("Survey-data sourcing (parallel)", 0, 4, AMBER, "IN PROGRESS"),
        ("P6 Integrated SDM (optional)", 9, 2, GREY, "LATER"),
        ("P5 Monte-Carlo uncertainty", 7.5, 1.5, GREY, "LATER"),
        ("P4 Encounter-rate chain", 6, 1.5, BLUE, "NEXT"),
        ("P3 Survey + R DSM density", 4.2, 1.8, BLUE, "NEXT"),
        ("P2 Traffic + Garrison Pleth", 3, 1.2, GREEN, "DONE"),
        ("P1b Model corrections (A-H)", 1.8, 1.2, GREEN, "DONE"),
        ("P1 Uncertainty layers", 0.9, 0.9, GREEN, "DONE"),
        ("P0 Framing + model cards", 0, 0.9, GREEN, "DONE"),
    ]
    for i, (_label, start, dur, color, tag) in enumerate(rows):
        ax.barh(i, dur, left=start, height=0.62, color=color)
        ax.text(
            start + dur + 0.15,
            i,
            tag,
            va="center",
            fontsize=7.5,
            color=color,
            weight="bold",
        )
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=8.5)
    ax.set_xlim(0, 13)
    ax.set_xlabel(
        "Relative sequence  (Tranche 1 done | Tranche 2 next | Tranche 3 later)",
        fontsize=8.5,
    )
    ax.axvline(3.3, color=NAVY, ls="--", lw=1)
    ax.text(3.4, 8.6, "we are here", fontsize=8, color=NAVY, style="italic")
    ax.set_title("IWC-conformity roadmap", fontsize=10, color=NAVY, weight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return _save(fig, "roadmap.png")


def fig_encounter_chain():
    """Encounter-rate -> interactions -> mortality module chain."""
    fig, ax = plt.subplots(figsize=(10, 3.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 20)
    ax.axis("off")
    steps = [
        ("Density\nDw (animals/km^2)\nfrom DSM", TEAL),
        ("Transit density\nVTD (track-km/km^2)\nfrom AIS", TEAL),
        ("Contact width\nw = BS + 0.64 x WL", BLUE),
        ("Encounter rate\nR = Dw x VTD x w", AMBER),
        ("Mortality index\nI = N x P_leth\n(Garrison taxon)", RED),
    ]
    w = 17
    for i, (label, color) in enumerate(steps):
        x = 1 + i * 19.6
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (x, 6),
                w,
                9,
                boxstyle="round,pad=0.4,rounding_size=1.2",
                facecolor=color,
                edgecolor="none",
            )
        )
        ax.text(
            x + w / 2,
            10.5,
            label,
            ha="center",
            va="center",
            fontsize=7.5,
            color="white",
            weight="bold",
        )
        if i < len(steps) - 1:
            ax.annotate(
                "",
                xy=(x + 19.6, 10.5),
                xytext=(x + w, 10.5),
                arrowprops={"arrowstyle": "-|>", "color": "#888888", "lw": 1.6},
            )
    fig.tight_layout()
    return _save(fig, "encounter_chain.png")


# ═══════════════════════════════════════════════════════════════════
# ReportPDF -- navy / teal theme (matches all earlier reports)
# ═══════════════════════════════════════════════════════════════════


class ReportPDF(FPDF):
    NAVY = (15, 32, 65)
    TEAL = (0, 150, 136)
    LIGHT_BG = (240, 245, 250)
    WHITE = (255, 255, 255)
    DARK_TEXT = (30, 30, 30)
    MID_TEXT = (80, 80, 80)
    ACCENT_GREEN = (46, 204, 113)
    ACCENT_AMBER = (243, 156, 18)
    ACCENT_BLUE = (52, 152, 219)
    ACCENT_RED = (214, 64, 69)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(
                0,
                10,
                "Marine Risk Mapping -- IWC Modelling Briefing",
                align="C",
            )
            self.ln(4)
            self.set_draw_color(*self.TEAL)
            self.set_line_width(0.3)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*self.MID_TEXT)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    # ── Layout helpers ────────────────────────────────────────────

    def section_title(self, title):
        if self.get_y() > 250:
            self.add_page()
        self.ln(4)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*self.NAVY)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.TEAL)
        self.set_line_width(0.6)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(4)

    def subsection_title(self, title):
        if self.get_y() > 258:
            self.add_page()
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*self.TEAL)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def small_text(self, text):
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*self.MID_TEXT)
        self.multi_cell(0, 4.5, text)
        self.ln(1)

    def bullet(self, text, indent=15):
        if self.get_y() > 265:
            self.add_page()
        x = self.get_x()
        self.set_x(x + indent - 5)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.TEAL)
        self.cell(5, 5.5, "-")
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def numbered_item(self, number, text, indent=15):
        if self.get_y() > 265:
            self.add_page()
        x = self.get_x()
        self.set_x(x + indent - 5)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.TEAL)
        self.cell(8, 5.5, f"{number}.")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def stat_boxes(self, stats, y=None):
        if y is None:
            y = self.get_y()
        n = len(stats)
        box_w = 42
        gap = 4
        x_start = 10 + (190 - (box_w * n + gap * (n - 1))) / 2
        for i, (value, label) in enumerate(stats):
            x = x_start + i * (box_w + gap)
            self.set_fill_color(*self.LIGHT_BG)
            self.rect(x, y, box_w, 22, style="F")
            self.set_xy(x, y + 3)
            self.set_font("Helvetica", "B", 15)
            self.set_text_color(*self.TEAL)
            self.cell(box_w, 8, str(value), align="C")
            self.set_xy(x, y + 12)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(box_w, 6, label, align="C")
        self.set_y(y + 26)

    def metric_table(self, headers, rows, col_widths=None, body_font=9):
        if col_widths is None:
            col_widths = [190 // len(headers)] * len(headers)
        self.set_fill_color(*self.NAVY)
        self.set_text_color(*self.WHITE)
        self.set_font("Helvetica", "B", 9)
        for w, h_text in zip(col_widths, headers, strict=False):
            self.cell(w, 7, f"  {h_text}", fill=True)
        self.ln()
        self.set_font("Helvetica", "", body_font)
        for i, row in enumerate(rows):
            if self.get_y() > 270:
                self.add_page()
                self.set_fill_color(*self.NAVY)
                self.set_text_color(*self.WHITE)
                self.set_font("Helvetica", "B", 9)
                for w, h_text in zip(col_widths, headers, strict=False):
                    self.cell(w, 7, f"  {h_text}", fill=True)
                self.ln()
                self.set_font("Helvetica", "", body_font)
            line_h = 5
            n_lines = 1
            for w, cell_val in zip(col_widths, row, strict=False):
                txt = str(cell_val)
                approx = max(1, int(len(txt) / max(1, (w - 3) / 1.8)) + 1)
                n_lines = max(n_lines, approx)
            row_h = line_h * n_lines
            bg = self.LIGHT_BG if i % 2 == 0 else self.WHITE
            self.set_fill_color(*bg)
            x0 = self.get_x()
            y0 = self.get_y()
            for j, (w, cell_val) in enumerate(zip(col_widths, row, strict=False)):
                self.rect(x0, y0, w, row_h, style="F")
                if j == 0:
                    self.set_text_color(*self.NAVY)
                    self.set_font("Helvetica", "B", body_font)
                else:
                    self.set_text_color(*self.DARK_TEXT)
                    self.set_font("Helvetica", "", body_font)
                self.set_xy(x0 + 1.5, y0 + 1)
                self.multi_cell(w - 3, line_h, str(cell_val))
                x0 += w
                self.set_xy(x0, y0)
            self.set_y(y0 + row_h)
        self.ln(3)

    def equation_box(self, title, equation, note=None):
        self.set_font("Helvetica", "", 9.5)
        box_h = 22 if note else 16
        if self.get_y() + box_h > 278:
            self.add_page()
        y_start = self.get_y()
        self.set_fill_color(*self.NAVY)
        self.rect(10, y_start, 190, box_h, style="F")
        self.set_xy(14, y_start + 2)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.TEAL)
        self.cell(0, 5, title)
        self.set_xy(14, y_start + 7.5)
        self.set_font("Courier", "B", 11)
        self.set_text_color(*self.WHITE)
        self.cell(0, 6, equation)
        if note:
            self.set_xy(14, y_start + 15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(210, 220, 230)
            self.multi_cell(180, 4, note)
        self.set_y(y_start + box_h + 4)

    def callout_box(self, title, text, colour=None):
        if colour is None:
            colour = self.ACCENT_BLUE
        self.set_font("Helvetica", "", 9.5)
        n_lines = max(1, len(text) // 84 + text.count("\n") + 1)
        box_h = 12 + n_lines * 5
        if self.get_y() + box_h > 278:
            self.add_page()
        y_start = self.get_y()
        self.set_fill_color(*self.LIGHT_BG)
        self.rect(10, y_start, 190, box_h, style="F")
        self.set_fill_color(*colour)
        self.rect(10, y_start, 3, box_h, style="F")
        self.set_xy(16, y_start + 2)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*colour)
        self.cell(0, 6, title)
        self.set_xy(16, y_start + 9)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(180, 5, text)
        self.set_y(y_start + box_h + 4)

    def plain(self, text):
        """Plain-language callout (green)."""
        self.callout_box("In plain terms", text, self.ACCENT_GREEN)

    def add_image_safe(self, path, w=None, caption=None):
        p = Path(path)
        if not p.exists():
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.ACCENT_AMBER)
            self.cell(
                0, 5, f"[Image not found: {p.name}]", new_x="LMARGIN", new_y="NEXT"
            )
            return
        if w is None:
            w = 190
        if self.get_y() + w * 0.5 > 277:
            self.add_page()
        x = 10 + (190 - w) / 2
        self.image(str(p), x=x, w=w)
        if caption:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.ln(1)
            self.multi_cell(0, 4.5, caption, align="C")
            self.ln(2)


# ═══════════════════════════════════════════════════════════════════
# Report content
# ═══════════════════════════════════════════════════════════════════


def build_report():  # noqa: C901 PLR0915
    # Generate figures first.
    f_arch = fig_architecture()
    f_weights = fig_subscore_weights()
    f_expose = fig_exposure_layering()
    f_leth = fig_lethality_curves()
    f_vtd = fig_vtd_concept()
    f_auc = fig_sdm_auc()
    f_road = fig_roadmap()
    f_chain = fig_encounter_chain()

    pdf = ReportPDF("P", "mm", "A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Title page ────────────────────────────────────────────────
    pdf.add_page()
    pdf.ln(26)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(
        0,
        13,
        "Whale-Vessel Risk & SDM Modelling",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(0, 13, "Briefing for Review", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        9,
        "Current modelling, tests, and the path to IWC conformity",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5.5,
        (
            "This briefing summarises what the marine-risk platform models "
            "today, the reasoning and tests behind each modelling choice, and "
            "the staged programme that brings the platform into line with two "
            "IWC standards: the ship-strike reporting standard (Leaper et al. "
            "2026, SC/70/HIM/13, with R. Leaper's review feedback) and the "
            "model-based abundance / SDM guidance (Miller & Kelly 2023, "
            "SC/69A/ASI/20). Each section carries a plain-language summary "
            "alongside the technical detail. The reviewer's four points are "
            "answered directly in Section 2."
        ),
        align="C",
    )
    pdf.ln(8)
    pdf.stat_boxes(
        [
            ("Tranche 1", "LANDED"),
            ("4 phases", "P0-P2 done"),
            ("9/9", "Validation PASS"),
            ("6 species", "SDM ensemble"),
        ]
    )
    pdf.ln(4)
    pdf.stat_boxes(
        [
            ("Garrison", "2025 Pleth"),
            ("VTD", "track-km/km^2"),
            ("214.7x", "Strike enrich."),
            ("Tranche 2-3", "Roadmap"),
        ]
    )
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9.5)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5,
        "Prepared 2026-06-16. Status: Tranche 1 complete and validated; "
        "Tranche 2 (survey density + encounter chain) is the next step.",
        align="C",
    )

    # ── 1. Executive summary ──────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1. Executive summary")
    pdf.body_text(
        "The platform fuses AIS vessel traffic, cetacean sightings, ship-strike "
        "records, bathymetry, ocean covariates and regulatory zones onto a "
        "1.9-million-cell H3 hex grid (study area 2S-52N, US waters incl. "
        "Alaska, Hawaii, Caribbean). From this it produces a relative "
        "collision-risk SCREENING product today, and is being extended into a "
        "quantitative ENCOUNTER-RATE product aligned with the IWC standards."
    )
    pdf.plain(
        "Today we can say WHERE whales and ships overlap and rank which cells "
        "are most dangerous. We are now adding HOW MANY animals are there "
        "(absolute density with error bars) so we can estimate expected "
        "encounters and mortality, not just a ranking."
    )
    pdf.subsection_title("Two products, deliberately separated")
    pdf.bullet(
        "Product A -- a screening composite risk index (retained, refreshed). "
        "Seven percentile-ranked sub-scores. Good for triage and mapping; it "
        "is a RELATIVE ranking, not a probability."
    )
    pdf.bullet(
        "Product B -- a quantitative encounter chain R = Dw x VTD x w feeding a "
        "mortality index I = N x P_leth (in build, Tranche 2). This is the "
        "IWC-standard quantity and carries explicit uncertainty."
    )
    pdf.add_image_safe(
        f_arch,
        w=185,
        caption="Figure 1. Data -> aggregation -> models -> two "
        "risk products. Product A ships today; Product B is the "
        "Tranche-2 encounter chain.",
    )

    # ── 2. Reviewer points ────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("2. Reviewer points addressed (R. Leaper)")
    pdf.body_text(
        "The four points raised in review are already designed into the "
        "programme. Each is answered below with what is built now and what is "
        "scheduled."
    )

    pdf.subsection_title("2.1  Report exposure BEFORE speed-lethality weighting")
    pdf.body_text(
        "Implemented (Phase 1). We expose raw whale x vessel co-occurrence as "
        "the BASE layer, with no lethality assumption baked in. Speed-lethality "
        "weighting is an optional overlay, not the default. The dedicated mart "
        "fct_whale_vessel_exposure (Phase 1b) carries the unweighted exposure "
        "so reviewers can see overlap independent of any Pleth curve."
    )
    pdf.plain(
        "You asked to see where whales and ships simply coincide, before we "
        "assume anything about how deadly a strike is. That unweighted layer is "
        "now the starting point; the lethality weighting sits on top and can be "
        "switched off."
    )
    pdf.add_image_safe(
        f_expose,
        w=185,
        caption="Figure 2. Exposure-first layering: unweighted "
        "co-occurrence is reported first; lethality and the wider "
        "speed pathways are overlays.",
    )

    pdf.subsection_title("2.2  Garrison et al. (2025) as the updated curve")
    pdf.body_text(
        "Implemented (Phase 2). We sourced the real Garrison (2025) Table-3 "
        "coefficients (Front. Mar. Sci. 11:1467387) and replaced the "
        "Vanderlaan & Taggart (2007) speed-lethality covariate in the traffic "
        "score. Garrison enters at two touchpoints: (A) a taxon-agnostic "
        "generic curve in the screening index now, and (B) the full "
        "speed x size x taxon curve in the Phase-4 mortality module. V&T 2007 "
        "is retained only as a back-comparison diagnostic. The Garrison slope "
        "is markedly shallower (generic b1 = 0.129/kn vs V&T 0.41/kn), and is "
        "taxon-specific (humpback b1 = 0.026/kn)."
    )
    pdf.add_image_safe(
        f_leth,
        w=185,
        caption="Figure 3. Garrison 2025 (teal/blue) vs V&T 2007 "
        "(red). Garrison's larger dataset gives a shallower, "
        "taxon-specific lethality response.",
    )

    pdf.subsection_title("2.3  Lethality is only a small part of speed-risk")
    pdf.body_text(
        "Agreed and built in. We treat vessel speed as a THREE-pathway lever: "
        "(i) it raises the ENCOUNTER rate, (ii) it lowers the chance of "
        "successful AVOIDANCE, and (iii) it raises the LETHALITY of a strike. "
        "The Pleth curve (Garrison/V&T) captures only pathway (iii), so it is a "
        "LOWER BOUND on the value of slowing down. The Phase-4 encounter chain "
        "(R = Dw x VTD x w) makes pathway (i) explicit, and avoidance (ii) is a "
        "Phase-5 Monte-Carlo scenario fork. This is exactly why the Garrison "
        "lethality curve looks shallow: most of the speed benefit lives in the "
        "other two pathways."
    )
    pdf.plain(
        "Slowing ships down helps in three ways: fewer encounters, more chance "
        "the whale gets out of the way, and less deadly hits. The lethality "
        "curve is only the third of these -- so we never present it as the "
        "whole speed story."
    )

    pdf.subsection_title("2.4  The IWC strike database is a small US sample")
    pdf.body_text(
        "Agreed. For a US-waters project the IWC global ship-strike database "
        "adds little, so we treat it as supplementary context only. Our "
        "quantitative backbone rests on US sources: NOAA/NMFS strike records "
        "for the strike layer, and US designed-survey programmes (AMAPPS, "
        "NARWSS, GoMMAPPS, SWFSC, AFSC, PIFSC HICEAS) for density/abundance. "
        "None of the headline numbers depend on the IWC database."
    )
    pdf.callout_box(
        "Net effect",
        "All four review points are either already implemented (2.1, 2.2) or "
        "are explicit design principles carried through the roadmap (2.3, 2.4). "
        "Nothing here requires re-opening a settled decision.",
        ReportPDF.TEAL,
    )

    # ── 3. What we have now -- Tranche 1 ───────────────────────────
    pdf.add_page()
    pdf.section_title("3. What we model today (Tranche 1 -- landed)")
    pdf.body_text(
        "Tranche 1 delivered four phases. Each was built, validated against a "
        "gate (tests + dbt build + lint), and stopped before the next."
    )
    pdf.metric_table(
        ["Phase", "What it delivered", "Status"],
        [
            [
                "P0",
                "IWC framing, model cards, terminology crosswalk, "
                "AIS-required traffic flag",
                "Done",
            ],
            [
                "P1",
                "Bootstrap uncertainty on SDMs, spatial residual "
                "diagnostics, extrapolation flag, exposure-first base layer",
                "Done",
            ],
            [
                "P1b",
                "Eight model corrections (A-H): NULL-deflation bugfix, "
                "calibration, target-group background, skill-weighted ensemble, "
                "CV block size, strike-weighted exposure, protection-gap refresh",
                "Done",
            ],
            [
                "P2",
                "True VTD traffic metric, joint (type x size x speed) "
                "strata, Garrison 2025 Pleth, Product-A rebase",
                "Done",
            ],
        ],
        col_widths=[16, 150, 24],
    )

    pdf.subsection_title("3.1  The screening composite (Product A)")
    pdf.body_text(
        "Product A blends seven percentile-ranked sub-scores into one "
        "collision-risk index per cell. The weights are expert-elicited (V&T "
        "2007, Rockwood 2021, Nisi 2024), not data-fitted, and act on RANKS so "
        "they were invariant to the Phase-2 count->VTD rebasing."
    )
    pdf.add_image_safe(
        f_weights,
        w=185,
        caption="Figure 4. Sub-score weights for the standard "
        "composite and its ML-enhanced variant. Teal bars are "
        "the dominant terms.",
    )
    pdf.plain(
        "We score every 1.2 km hex on seven ingredients -- how much traffic, "
        "how many whales, how close to known hotspots, past strikes, habitat, "
        "protection gaps, and an external reference -- then combine them into "
        "one 0-1 danger score for mapping."
    )

    pdf.subsection_title("3.2  The traffic backbone -- VTD, not ping counts")
    pdf.body_text(
        "Phase 2 retired ping/vessel COUNTS (biased by AIS broadcast rate and "
        "how long a vessel dwells in a cell) in favour of true Vessel Transit "
        "Density: the track-km a vessel actually travels through each cell per "
        "km^2, from consecutive AIS positions with exact great-circle "
        "segment-to-cell clipping. Traffic is stratified on the IWC standard's "
        "joint (vessel type x size class x speed bin) grain -- 11.58M strata "
        "rows."
    )
    pdf.add_image_safe(
        f_vtd,
        w=150,
        caption="Figure 5. Why VTD matters: ping counts reward "
        "dwell time and dense AIS; transit distance measures the "
        "actual exposure path through the cell.",
    )

    pdf.subsection_title("3.3  Species distribution models (the whale layer)")
    pdf.body_text(
        "Six species are modelled with an ISDM + SDM ensemble. The SDMs are "
        "gradient-boosted presence/background models trained on OBIS sightings "
        "with environmental covariates (SST, MLD, SLA, productivity, depth). "
        "Phase-1b corrections materially improved their honesty:"
    )
    pdf.bullet(
        "Probability CALIBRATION (isotonic, per species) so outputs are "
        "real probabilities, not just rankings -- essential before they "
        "feed an absolute encounter equation."
    )
    pdf.bullet(
        "TARGET-GROUP background + spatial thinning to cancel OBIS "
        "survey-effort bias (where people looked, not where whales are)."
    )
    pdf.bullet(
        "SKILL-WEIGHTED ensemble (AUC-weighted ISDM:SDM blend) instead of a flat 50/50."
    )
    pdf.bullet(
        "BOOTSTRAP ensemble (~50 refits) giving a per-cell uncertainty "
        "band, plus a MESS/ExDet extrapolation flag for low-confidence "
        "cells."
    )
    pdf.add_image_safe(
        f_auc,
        w=180,
        caption="Figure 6. Per-species spatial-CV AUC after the "
        "Phase-1b bias correction. Lower than naive in-sample "
        "numbers by design -- effort-bias inflation was removed.",
    )
    pdf.plain(
        "These models predict how likely each whale species is to be in a "
        "given patch of sea by season. We corrected them so they report honest "
        "probabilities and aren't fooled by the fact that surveys cluster near "
        "ports and shipping lanes."
    )
    pdf.callout_box(
        "Honest labelling (Phase 0)",
        "SDM outputs are labelled throughout as 'relative occurrence "
        "probability / habitat suitability', NOT density or abundance. Turning "
        "suitability into absolute animals/km^2 is exactly the job of the "
        "Tranche-2 survey-based density engine.",
        ReportPDF.ACCENT_AMBER,
    )

    # ── 4. Tests & validation ─────────────────────────────────────
    pdf.add_page()
    pdf.section_title("4. Tests & validation evidence")
    pdf.body_text(
        "The risk model is validated by an automated suite (9 checks, all "
        "PASS) spanning internal consistency, external benchmarks and "
        "sensitivity. Key figures below are produced by "
        "validate_traffic_risk.py and refreshed each run."
    )
    pdf.metric_table(
        ["Check", "Result", "Reading"],
        [
            ["Weight sums", "9/9 = 1.000", "All sub-score weights normalise"],
            [
                "Jensen (binned vs collapsed)",
                "rho = 0.9975",
                "Per-bin Garrison "
                "aggregation keeps the estimate bounded (mean |bias| 0.0027)",
            ],
            [
                "Strike enrichment",
                "214.7x critical",
                "Historic strike cells land overwhelmingly in the top risk bands",
            ],
            [
                "Nisi (2024) correlation",
                "rho = 0.585",
                "Independent published risk grid agrees with the composite",
            ],
            [
                "SMA protection check",
                "PASS",
                "Active speed zones score lower protection-gap than unprotected cells",
            ],
            [
                "Weight perturbation",
                "Jaccard 0.71-0.90",
                "Top-1% cells are stable under +/-50% weight shifts",
            ],
        ],
        col_widths=[48, 36, 106],
    )
    pdf.add_image_safe(
        VAL_DIR / "strike_overlap.png",
        w=170,
        caption="Figure 7. Historic ship-strike sites vs risk "
        "category -- 214.7x enrichment in the 'critical' band.",
    )
    pdf.add_image_safe(
        VAL_DIR / "jensens_inequality_check.png",
        w=170,
        caption="Figure 8. Applying Garrison lethality per narrow "
        "speed bin vs on the cell-mean speed -- binning avoids "
        "Jensen's-inequality bias (rho = 0.9975).",
    )
    pdf.add_image_safe(
        VAL_DIR / "nisi_correlation.png",
        w=170,
        caption="Figure 9. Composite risk vs the Nisi et al. "
        "(2024) reference grid (Spearman rho = 0.585).",
    )
    pdf.plain(
        "We don't just trust the model -- we test it. Past strikes fall in our "
        "high-risk cells far more than chance, an independent published risk "
        "map agrees with ours, protected areas score as protected, and the "
        "ranking barely moves when we wiggle the weights."
    )

    # ── 5. Roadmap to IWC conformity ──────────────────────────────
    pdf.add_page()
    pdf.section_title("5. Where we are going -- IWC conformity")
    pdf.body_text(
        "Tranche 1 made the existing models honest and standard-compatible. "
        "Tranches 2-3 add the quantitative backbone the IWC standards expect: "
        "absolute density with error bars, an explicit encounter chain, and "
        "end-to-end uncertainty."
    )
    pdf.add_image_safe(
        f_road,
        w=185,
        caption="Figure 10. The staged roadmap. Tranche 1 (green) "
        "is complete; Tranche 2 (blue) is next; Tranche 3 (grey) "
        "follows. Survey-data sourcing runs in parallel.",
    )

    pdf.subsection_title("5.1  Phase 3 -- survey density engine (the big lift)")
    pdf.body_text(
        "Distance-sampling + density-surface modelling (DSM) in R (Distance, "
        "mrds, dsm/mgcv) turns designed-survey observations into ABSOLUTE "
        "density (animals/km^2) with confidence intervals. It corrects for "
        "whales missed with distance and missed on the trackline (perception + "
        "availability bias via dive-tag data), then spreads density across the "
        "map with a spatial GAM. Predictions are tiered for honesty: inside "
        "survey footprint (trust), inside the environmental envelope "
        "(extrapolation, caveated), outside the envelope (masked)."
    )
    pdf.plain(
        "Right now the whale layer is a relative likelihood. Phase 3 converts "
        "it into an actual headcount per square kilometre, with error bars, "
        "using rigorous survey statistics -- the quantity the IWC standard "
        "needs and the one ship-strike estimates multiply against."
    )
    pdf.callout_box(
        "Survey-data sourcing (parallel workstream)",
        "Running now, ahead of Phase 3. NARW US-Atlantic is already cleared to "
        "GO (AMAPPS full DSM); SWFSC and PIFSC HICEAS GO; GoMMAPPS/AFSC "
        "go-caveated; Roberts/Duke density retained as an independent "
        "validation benchmark only.",
        ReportPDF.ACCENT_BLUE,
    )

    pdf.subsection_title("5.2  Phase 4 -- the encounter-rate chain (Product B)")
    pdf.body_text(
        "With absolute density in hand, the IWC encounter equation becomes "
        "computable per cell and species. Contact width w = BS + 0.64 x WL "
        "combines vessel beam and whale length; the encounter rate R = Dw x "
        "VTD x w (no separate speed term -- speed cancels between encounter "
        "rate and transit time, a literature-confirmed result); and the "
        "mortality index I = N x P_leth applies the full Garrison "
        "speed x size x taxon curve."
    )
    pdf.add_image_safe(
        f_chain,
        w=185,
        caption="Figure 11. The encounter chain: density and "
        "transit density combine through contact width into an "
        "encounter rate, then a mortality index.",
    )

    pdf.subsection_title("5.3  Phase 5-6 -- uncertainty & integration")
    pdf.bullet(
        "Phase 5: a ~1000-draw Monte-Carlo propagates every input "
        "uncertainty (density CV, Garrison coefficient intervals, "
        "availability) into credible intervals; avoidance is an OUTER "
        "scenario fork, never blended into the error bars."
    )
    pdf.bullet(
        "Phase 6 (optional): a single integrated point-process SDM "
        "(inlabru/INLA) fusing surveys + thinned OBIS + tag "
        "availability, validated against the Phase-3 DSM."
    )

    # ── 6. Standards mapping ──────────────────────────────────────
    pdf.add_page()
    pdf.section_title("6. Mapping to the IWC standards")
    pdf.body_text(
        "How each component lines up with the strike-risk reporting standard "
        "(Leaper et al. 2026) and the SDM/abundance guidance (Miller & Kelly "
        "2023)."
    )
    pdf.metric_table(
        ["IWC expectation", "Our component", "Status"],
        [
            [
                "Exposure reported with and without weighting",
                "fct_whale_vessel_exposure base layer + optional Pleth overlay",
                "Done",
            ],
            [
                "Up-to-date speed-lethality curve",
                "Garrison 2025 Table-3 coeffs, two touchpoints",
                "Done",
            ],
            [
                "Traffic as transit density, stratified",
                "VTD on (type x size x speed) joint grain",
                "Done",
            ],
            [
                "Model cards / documented assumptions",
                "docs/model_cards vs Miller & Kelly checklist",
                "Done",
            ],
            [
                "Calibrated, bias-corrected SDMs",
                "Isotonic calibration + target-group background",
                "Done",
            ],
            [
                "Absolute density with uncertainty",
                "Phase-3 R DSM (Distance/mrds/dsm) + CV",
                "Next",
            ],
            [
                "g(0) availability + perception correction",
                "MRDS + dive-tag availability multipliers",
                "Next",
            ],
            [
                "Encounter-rate / mortality estimate",
                "Phase-4 R = Dw x VTD x w -> I = N x P_leth",
                "Next",
            ],
            [
                "End-to-end uncertainty",
                "Phase-5 Monte-Carlo with avoidance fork",
                "Later",
            ],
        ],
        col_widths=[66, 100, 24],
    )

    pdf.subsection_title("Key takeaways")
    pdf.numbered_item(
        1,
        "Tranche 1 is complete and validated: the existing "
        "models are now honest, calibrated and standard-compatible.",
    )
    pdf.numbered_item(
        2,
        "All four reviewer points are implemented or are "
        "explicit roadmap principles -- exposure-first, Garrison "
        "2025, speed-as-three-pathways, US-data-first.",
    )
    pdf.numbered_item(
        3,
        "Product A (screening) ships today; Product B "
        "(quantitative encounter chain) is the Tranche-2 goal.",
    )
    pdf.numbered_item(
        4,
        "The whale layer moves from relative suitability to "
        "absolute density (animals/km^2 with error bars) via a "
        "rigorous R distance-sampling engine, NARW-first.",
    )
    pdf.numbered_item(
        5,
        "Survey-data sourcing is already underway in parallel; "
        "NARW US-Atlantic is cleared, so Phase 3 can start without "
        "delay.",
    )

    pdf.ln(2)
    pdf.callout_box(
        "References",
        "Leaper et al. 2026 (SC/70/HIM/13); Miller & Kelly 2023 "
        "(SC/69A/ASI/20); Garrison et al. 2025 (Front. Mar. Sci. 11:1467387); "
        "Vanderlaan & Taggart 2007; Rockwood et al. 2017, 2021; Nisi et al. "
        "2024; Buckland et al. (Distance Sampling); Miller et al. (dsm/mgcv). "
        "Full methodology in the companion modelling PDFs in this folder.",
        ReportPDF.NAVY,
    )

    pdf.output(str(OUTPUT_FILE))
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    build_report()

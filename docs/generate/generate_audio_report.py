"""Generate Audio Classification Pipeline PDF report.

Comprehensive report covering the whale audio species classification system:
data sources, preprocessing pipeline, balancing strategy, XGBoost and CNN
model results, and comparative analysis.

Follows the same ReportPDF navy/teal theme as earlier phase reports.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from fpdf import FPDF

# ── Paths ────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = ROOT / "docs" / "pdfs"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "audio_classification.pdf"

ARTIFACT_DIR = ROOT / "data" / "processed" / "ml" / "artifacts" / "audio_classifier"
MODEL_DIR = ROOT / "data" / "processed" / "ml" / "audio_classifier"
AUDIO_RAW = ROOT / "data" / "raw" / "whale_audio"
DIAGRAM_DIR = ARTIFACT_DIR / "diagrams"

# ── Data Sources ─────────────────────────────────────────────

DATA_SOURCES = [
    {
        "name": "Watkins Marine Mammal Sound Database",
        "species": "8 species (right, humpback, fin, blue, sperm, minke, sei, killer)",
        "format": "WAV / AIF bundles per species",
        "url": "whalesound.wordpress.com",
    },
    {
        "name": "Zenodo 3624145",
        "species": "Blue whale (D/Z calls)",
        "format": "WAV",
        "url": "doi.org/10.5281/zenodo.3624145",
    },
    {
        "name": "Zenodo 4293955",
        "species": "Humpback whale song units",
        "format": "WAV",
        "url": "doi.org/10.5281/zenodo.4293955",
    },
    {
        "name": "Zenodo 8147524",
        "species": "Fin whale 20 Hz pulses",
        "format": "WAV",
        "url": "doi.org/10.5281/zenodo.8147524",
    },
]

# ── Per-species file counts ──────────────────────────────────

FILE_COUNTS = {
    "blue_whale": 4,
    "fin_whale": 51,
    "humpback_whale": 65,
    "killer_whale": 179,
    "minke_whale": 19,
    "right_whale": 58,
    "sei_whale": 1,
    "sperm_whale": 75,
}
TOTAL_FILES = sum(FILE_COUNTS.values())

# ── Segment counts (after preprocessing pipeline) ───────────

SEGMENT_COUNTS = {
    "blue_whale": {"raw": 2000, "augmented": 0, "total": 2000},
    "fin_whale": {"raw": 1249, "augmented": 0, "total": 1249},
    "humpback_whale": {"raw": 1599, "augmented": 0, "total": 1599},
    "killer_whale": {"raw": 190, "augmented": 310, "total": 500},
    "minke_whale": {"raw": 43, "augmented": 457, "total": 500},
    "right_whale": {"raw": 1837, "augmented": 0, "total": 1837},
    "sei_whale": {"raw": 18, "augmented": 482, "total": 500},
    "sperm_whale": {"raw": 2000, "augmented": 0, "total": 2000},
}
TOTAL_SEGMENTS = sum(v["total"] for v in SEGMENT_COUNTS.values())

# ── Class weights ────────────────────────────────────────────

CLASS_WEIGHTS = {
    "blue_whale": 0.637,
    "fin_whale": 1.019,
    "humpback_whale": 0.796,
    "killer_whale": 2.546,
    "minke_whale": 2.546,
    "right_whale": 0.693,
    "sei_whale": 2.546,
    "sperm_whale": 0.637,
}

# ── XGBoost results ─────────────────────────────────────────

XGBOOST_RESULTS = {
    "accuracy": 0.979,
    "macro_f1": 0.982,
    "weighted_f1": 0.979,
    "cv_folds": 5,
    "n_segments": 10185,
    "n_features": 64,
    "training_time": "213.7 s",
    "per_class": {
        "blue_whale": {"precision": 1.00, "recall": 0.91, "f1": 0.95, "support": 2000},
        "fin_whale": {"precision": 0.89, "recall": 1.00, "f1": 0.94, "support": 1249},
        "humpback_whale": {
            "precision": 1.00,
            "recall": 1.00,
            "f1": 1.00,
            "support": 1599,
        },
        "killer_whale": {"precision": 0.98, "recall": 1.00, "f1": 0.99, "support": 500},
        "minke_whale": {"precision": 1.00, "recall": 1.00, "f1": 1.00, "support": 500},
        "right_whale": {"precision": 0.98, "recall": 0.99, "f1": 0.99, "support": 1837},
        "sei_whale": {"precision": 0.99, "recall": 1.00, "f1": 1.00, "support": 500},
        "sperm_whale": {"precision": 1.00, "recall": 1.00, "f1": 1.00, "support": 2000},
    },
}

# ── CNN results ──────────────────────────────────────────────

CNN_RESULTS = {
    "accuracy": 0.993,
    "macro_f1": 0.994,
    "weighted_f1": 0.993,
    "best_val_f1": 0.9943,
    "best_epoch": 5,
    "stopped_epoch": 12,
    "total_epochs": 30,
    "early_stop_patience": 7,
    "n_train": 8148,
    "n_val": 2037,
    "batch_size": 32,
    "lr": 0.001,
    "training_time": "279.7 s",
    "device": "Apple MPS (M-series GPU)",
    "architecture": "ResNet18 (pretrained, final FC adapted)",
    "per_class": {
        "blue_whale": {"precision": 1.00, "recall": 1.00, "f1": 1.00, "support": 400},
        "fin_whale": {"precision": 1.00, "recall": 0.98, "f1": 0.99, "support": 250},
        "humpback_whale": {
            "precision": 1.00,
            "recall": 0.99,
            "f1": 0.99,
            "support": 320,
        },
        "killer_whale": {"precision": 0.96, "recall": 0.99, "f1": 0.98, "support": 100},
        "minke_whale": {"precision": 0.99, "recall": 1.00, "f1": 1.00, "support": 100},
        "right_whale": {"precision": 1.00, "recall": 0.99, "f1": 1.00, "support": 367},
        "sei_whale": {"precision": 0.95, "recall": 1.00, "f1": 0.98, "support": 100},
        "sperm_whale": {"precision": 1.00, "recall": 1.00, "f1": 1.00, "support": 400},
    },
    "epoch_log": [
        {"epoch": 1, "train_loss": 0.3334, "val_acc": 0.9755, "val_f1": 0.9606},
        {"epoch": 5, "train_loss": 0.0365, "val_acc": 0.9961, "val_f1": 0.9943},
        {"epoch": 10, "train_loss": 0.0405, "val_acc": 0.9082, "val_f1": 0.8870},
        {"epoch": 12, "train_loss": 0.0265, "val_acc": 0.9561, "val_f1": 0.9409},
    ],
}

# ── Acoustic features (64 total) ────────────────────────────

FEATURE_GROUPS = [
    (
        "MFCCs",
        "20 coefficients x (mean + std) = 40",
        "Timbral fingerprint of each species' vocalisation",
    ),
    (
        "Spectral shape",
        "centroid, bandwidth, rolloff, flatness (mean + std) = 8",
        "Frequency distribution characteristics",
    ),
    (
        "Spectral contrast",
        "7 bands (mean) = 7",
        "Peak-to-valley differences across frequency bands",
    ),
    (
        "Zero-crossing rate",
        "mean + std = 2",
        "Signal noisiness / periodicity indicator",
    ),
    ("RMS energy", "mean, std, max = 3", "Signal loudness and dynamic range"),
    ("Dominant frequency", "1 feature", "Peak frequency (Hz) -- species-diagnostic"),
    (
        "Temporal envelope",
        "mean, std, skew, kurtosis = 4",
        "Amplitude modulation shape",
    ),
]

# ── Top features from XGBoost ───────────────────────────────

TOP_FEATURES = [
    ("spectral_rolloff_mean", 300.3),
    ("spectral_flatness_mean", 148.8),
    ("mfcc_18_std", 143.9),
    ("mfcc_4_mean", 123.0),
    ("mfcc_5_mean", 95.3),
    ("spectral_bandwidth_mean", 79.4),
    ("dominant_freq_hz", 77.9),
    ("rms_mean", 77.2),
    ("mfcc_7_mean", 62.5),
    ("mfcc_14_mean", 59.2),
]


# ── Whale frequency bands ───────────────────────────────────

FREQ_BANDS = {
    "blue_whale": "10 -- 100 Hz  (infrasonic D/Z calls)",
    "fin_whale": "15 -- 30 Hz   (20 Hz pulse trains)",
    "right_whale": "50 -- 500 Hz  (up-calls, gunshots)",
    "humpback_whale": "100 -- 4000 Hz (complex songs)",
    "minke_whale": "50 -- 500 Hz  (pulse trains, boings)",
    "sei_whale": "20 -- 100 Hz  (low-frequency downsweeps)",
    "sperm_whale": "2000 -- 8000 Hz (clicks, codas)",
    "killer_whale": "500 -- 8000 Hz (whistles, pulsed calls)",
}


# ═══════════════════════════════════════════════════════════════
# PDF Class -- same theme as Phase 7 report
# ═══════════════════════════════════════════════════════════════


class ReportPDF(FPDF):
    """Navy / teal themed report matching earlier phase PDFs."""

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
                0, 10, "Marine Risk Mapping -- Audio Classification Pipeline", align="C"
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

    # ── helpers ──────────────────────────────────────────────

    def section_title(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*self.NAVY)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.TEAL)
        self.set_line_width(0.6)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(4)

    def subsection_title(self, title: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*self.TEAL)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def small_text(self, text: str):
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*self.MID_TEXT)
        self.multi_cell(0, 4.5, text)
        self.ln(1)

    def bullet(self, text: str, indent: int = 15):
        x = self.get_x()
        self.set_x(x + indent - 5)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.TEAL)
        self.cell(5, 5.5, "-")
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def stat_boxes(self, stats: list[tuple], y: float | None = None):
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
            self.set_font("Helvetica", "B", 16)
            self.set_text_color(*self.TEAL)
            self.cell(box_w, 8, str(value), align="C")
            self.set_xy(x, y + 12)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(box_w, 6, label, align="C")
        self.set_y(y + 26)

    def metric_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        col_widths: list[int] | None = None,
    ):
        if col_widths is None:
            col_widths = [190 // len(headers)] * len(headers)
        self.set_fill_color(*self.NAVY)
        self.set_text_color(*self.WHITE)
        self.set_font("Helvetica", "B", 9)
        for w, h_text in zip(col_widths, headers):
            self.cell(w, 7, f"  {h_text}", fill=True)
        self.ln()
        self.set_font("Helvetica", "", 9)
        for i, row in enumerate(rows):
            bg = self.LIGHT_BG if i % 2 == 0 else self.WHITE
            self.set_fill_color(*bg)
            for j, (w, cell_val) in enumerate(zip(col_widths, row)):
                if j == 0:
                    self.set_text_color(*self.DARK_TEXT)
                else:
                    self.set_text_color(*self.TEAL)
                self.cell(w, 7, f"  {cell_val}", fill=True)
            self.ln()
        self.ln(3)

    def tech_card(self, name: str, category: str, purpose: str, details: str):
        card_w = 190
        x_start = self.get_x()
        y_start = self.get_y()
        if y_start > 250:
            self.add_page()
            y_start = self.get_y()
        self.set_fill_color(*self.LIGHT_BG)
        self.rect(x_start, y_start, card_w, 28, style="F")
        cat_colours = {
            "ML": self.TEAL,
            "Data": self.ACCENT_BLUE,
            "Audio": self.ACCENT_AMBER,
            "Infra": self.ACCENT_GREEN,
        }
        colour = cat_colours.get(category, self.TEAL)
        self.set_fill_color(*colour)
        self.rect(x_start, y_start, 3, 28, style="F")
        self.set_xy(x_start + 6, y_start + 2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*self.NAVY)
        self.cell(80, 6, name)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*colour)
        self.cell(40, 6, f"[{category}]")
        self.set_xy(x_start + 6, y_start + 9)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.DARK_TEXT)
        self.cell(180, 5, purpose)
        self.set_xy(x_start + 6, y_start + 16)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*self.MID_TEXT)
        self.multi_cell(178, 4, details)
        self.set_y(y_start + 31)

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
        if self.get_y() + 60 > 277:
            self.add_page()
        self.image(str(p), x=10, w=w)
        if caption:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(0, 5, caption, new_x="LMARGIN", new_y="NEXT")
            self.ln(2)


# ═══════════════════════════════════════════════════════════════
# Diagram generation
# ═══════════════════════════════════════════════════════════════


def _generate_diagrams():
    """Generate all diagrams needed for the report."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    DIAGRAM_DIR.mkdir(parents=True, exist_ok=True)

    species = list(SEGMENT_COUNTS.keys())
    species_short = [s.replace("_whale", "").replace("_", " ").title() for s in species]

    # ── 1. Segment distribution (raw vs augmented) ──────────
    fig, ax = plt.subplots(figsize=(12, 6))
    raw = [SEGMENT_COUNTS[s]["raw"] for s in species]
    aug = [SEGMENT_COUNTS[s]["augmented"] for s in species]
    x = np.arange(len(species))
    w = 0.5
    ax.bar(x, raw, w, color="#00968A", label="Raw segments")
    ax.bar(x, aug, w, bottom=raw, color="#F39C12", label="Augmented segments")
    ax.axhline(
        y=500,
        color="#E74C3C",
        linestyle="--",
        linewidth=1,
        label="Augmentation target (500)",
    )
    ax.axhline(
        y=2000,
        color="#3498DB",
        linestyle="--",
        linewidth=1,
        label="Segment cap (2,000)",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(species_short, rotation=30, ha="right")
    ax.set_ylabel("Number of segments")
    ax.set_title("Training Segments per Species (After Balancing)")
    ax.legend(loc="upper right")
    for i, (r, a) in enumerate(zip(raw, aug)):
        ax.text(
            i,
            r + a + 20,
            str(r + a),
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )
    plt.tight_layout()
    fig.savefig(DIAGRAM_DIR / "segment_distribution.png", dpi=150)
    plt.close(fig)

    # ── 2. Model comparison (XGBoost vs CNN) ────────────────
    comparison_species = list(XGBOOST_RESULTS["per_class"].keys())
    comp_short = [
        s.replace("_whale", "").replace("_", " ").title() for s in comparison_species
    ]
    xgb_f1 = [XGBOOST_RESULTS["per_class"][s]["f1"] for s in comparison_species]
    cnn_f1 = [CNN_RESULTS["per_class"][s]["f1"] for s in comparison_species]

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(comparison_species))
    w = 0.35
    ax.bar(x - w / 2, xgb_f1, w, color="#3498DB", label="XGBoost", alpha=0.85)
    ax.bar(x + w / 2, cnn_f1, w, color="#00968A", label="CNN (ResNet18)", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(comp_short, rotation=30, ha="right")
    ax.set_ylabel("F1 Score")
    ax.set_ylim(0.90, 1.02)
    ax.set_title("Per-Species F1: XGBoost vs CNN")
    ax.legend()
    ax.axhline(y=1.0, color="grey", linestyle=":", linewidth=0.5)
    for i in range(len(comparison_species)):
        ax.text(
            i - w / 2,
            xgb_f1[i] + 0.003,
            f"{xgb_f1[i]:.2f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#2C3E50",
        )
        ax.text(
            i + w / 2,
            cnn_f1[i] + 0.003,
            f"{cnn_f1[i]:.2f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#2C3E50",
        )
    plt.tight_layout()
    fig.savefig(DIAGRAM_DIR / "model_comparison.png", dpi=150)
    plt.close(fig)

    # ── 3. CNN training curve ───────────────────────────────
    # Use epoch log from CNN_RESULTS
    epochs_log = CNN_RESULTS["epoch_log"]
    ep_nums = [e["epoch"] for e in epochs_log]
    train_losses = [e["train_loss"] for e in epochs_log]
    val_f1s = [e["val_f1"] for e in epochs_log]
    val_accs = [e["val_acc"] for e in epochs_log]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Loss curve
    ax1.plot(
        ep_nums, train_losses, "o-", color="#E74C3C", label="Train loss", markersize=6
    )
    ax1.axvline(
        x=CNN_RESULTS["best_epoch"],
        color="#00968A",
        linestyle="--",
        label=f"Best epoch ({CNN_RESULTS['best_epoch']})",
    )
    ax1.axvline(
        x=CNN_RESULTS["stopped_epoch"],
        color="#F39C12",
        linestyle="--",
        label=f"Early stop ({CNN_RESULTS['stopped_epoch']})",
    )
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Training Loss")
    ax1.set_title("CNN Training Loss")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # F1 / accuracy curve
    ax2.plot(
        ep_nums, val_f1s, "s-", color="#00968A", label="Val macro F1", markersize=6
    )
    ax2.plot(
        ep_nums, val_accs, "^-", color="#3498DB", label="Val accuracy", markersize=6
    )
    ax2.axvline(x=CNN_RESULTS["best_epoch"], color="#00968A", linestyle="--", alpha=0.5)
    ax2.axvline(
        x=CNN_RESULTS["stopped_epoch"], color="#F39C12", linestyle="--", alpha=0.5
    )
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Score")
    ax2.set_title("CNN Validation Metrics")
    ax2.set_ylim(0.85, 1.02)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(DIAGRAM_DIR / "cnn_training_curves.png", dpi=150)
    plt.close(fig)

    # ── 4. File count per species ───────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    fc_species = list(FILE_COUNTS.keys())
    fc_short = [s.replace("_whale", "").replace("_", " ").title() for s in fc_species]
    fc_vals = list(FILE_COUNTS.values())
    colors = [
        "#00968A" if v >= 50 else "#F39C12" if v >= 10 else "#E74C3C" for v in fc_vals
    ]
    bars = ax.bar(fc_short, fc_vals, color=colors)
    ax.set_ylabel("Audio Files")
    ax.set_title("Training Audio Files per Species")
    ax.set_xticklabels(fc_short, rotation=30, ha="right")
    for bar, val in zip(bars, fc_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 2,
            str(val),
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )
    plt.tight_layout()
    fig.savefig(DIAGRAM_DIR / "file_counts.png", dpi=150)
    plt.close(fig)

    # ── 5. Pipeline architecture diagram ────────────────────
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title(
        "Audio Classification Pipeline Architecture",
        fontsize=16,
        fontweight="bold",
        color="#0F2041",
        pad=20,
    )

    box_style = dict(
        boxstyle="round,pad=0.4", facecolor="#E8F5E9", edgecolor="#00968A", linewidth=2
    )
    arrow_style = dict(arrowstyle="->", color="#0F2041", linewidth=2)
    box_ml = dict(
        boxstyle="round,pad=0.4", facecolor="#E3F2FD", edgecolor="#3498DB", linewidth=2
    )
    box_out = dict(
        boxstyle="round,pad=0.4", facecolor="#FFF3E0", edgecolor="#F39C12", linewidth=2
    )

    # Row 1: Data sources
    ax.text(
        2, 7, "Watkins\nDatabase", ha="center", va="center", fontsize=9, bbox=box_style
    )
    ax.text(
        5,
        7,
        "Zenodo\nDatasets (3)",
        ha="center",
        va="center",
        fontsize=9,
        bbox=box_style,
    )
    ax.text(
        8,
        7,
        "SanctSound\n(Optional)",
        ha="center",
        va="center",
        fontsize=9,
        bbox=box_style,
    )

    # Row 2: Download + organize
    ax.annotate("", xy=(5, 5.8), xytext=(2, 6.5), arrowprops=arrow_style)
    ax.annotate("", xy=(5, 5.8), xytext=(5, 6.5), arrowprops=arrow_style)
    ax.annotate("", xy=(5, 5.8), xytext=(8, 6.5), arrowprops=arrow_style)
    ax.text(
        5,
        5.5,
        "download_whale_audio.py\n452 files -> 8 species folders",
        ha="center",
        va="center",
        fontsize=9,
        bbox=box_style,
    )

    # Row 3: Preprocessing
    ax.annotate("", xy=(5, 4.3), xytext=(5, 5.0), arrowprops=arrow_style)
    ax.text(
        5,
        4.0,
        "preprocess.py\nResample 16kHz | Segment 4s/2s hop\n64 acoustic features | Mel spectrograms",
        ha="center",
        va="center",
        fontsize=9,
        bbox=box_style,
    )

    # Row 4: Balancing
    ax.annotate("", xy=(5, 2.8), xytext=(5, 3.4), arrowprops=arrow_style)
    ax.text(
        5,
        2.5,
        "3-Stage Balancing\nCap 2,000 | Augment to 500 | Class weights",
        ha="center",
        va="center",
        fontsize=9,
        bbox=box_style,
    )

    # Row 5: Two model paths
    ax.annotate("", xy=(3, 1.3), xytext=(4, 2.0), arrowprops=arrow_style)
    ax.annotate("", xy=(8, 1.3), xytext=(6, 2.0), arrowprops=arrow_style)
    ax.text(
        3,
        1.0,
        "XGBoost\n5-fold CV\n64 features",
        ha="center",
        va="center",
        fontsize=9,
        bbox=box_ml,
    )
    ax.text(
        8,
        1.0,
        "CNN (ResNet18)\nMel spectrograms\nMPS accelerated",
        ha="center",
        va="center",
        fontsize=9,
        bbox=box_ml,
    )

    # Outputs
    ax.text(
        11.5,
        4.0,
        "MLflow\nTracking",
        ha="center",
        va="center",
        fontsize=9,
        bbox=box_out,
    )
    ax.text(
        11.5,
        2.5,
        "Artifacts\nPlots, Reports",
        ha="center",
        va="center",
        fontsize=9,
        bbox=box_out,
    )
    ax.text(
        11.5,
        1.0,
        "H3 Risk\nEnrichment",
        ha="center",
        va="center",
        fontsize=9,
        bbox=box_out,
    )

    ax.annotate(
        "",
        xy=(10.5, 4.0),
        xytext=(9.2, 1.5),
        arrowprops=dict(
            arrowstyle="->", color="#F39C12", linewidth=1.5, linestyle="--"
        ),
    )
    ax.annotate(
        "",
        xy=(10.5, 2.5),
        xytext=(9.2, 1.0),
        arrowprops=dict(
            arrowstyle="->", color="#F39C12", linewidth=1.5, linestyle="--"
        ),
    )

    plt.tight_layout()
    fig.savefig(DIAGRAM_DIR / "pipeline_architecture.png", dpi=150)
    plt.close(fig)

    # ── 6. Frequency band chart ─────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 6))
    fb_species = list(FREQ_BANDS.keys())
    fb_short = [s.replace("_whale", "").replace("_", " ").title() for s in fb_species]
    # Parse approximate ranges for the chart
    freq_ranges = {
        "blue_whale": (10, 100),
        "fin_whale": (15, 30),
        "right_whale": (50, 500),
        "humpback_whale": (100, 4000),
        "minke_whale": (50, 500),
        "sei_whale": (20, 100),
        "sperm_whale": (2000, 8000),
        "killer_whale": (500, 8000),
    }
    # Sort by low frequency
    sorted_species = sorted(freq_ranges.keys(), key=lambda s: freq_ranges[s][0])
    y_pos = np.arange(len(sorted_species))
    colours = [
        "#00968A",
        "#3498DB",
        "#E74C3C",
        "#F39C12",
        "#9B59B6",
        "#1ABC9C",
        "#E67E22",
        "#2C3E50",
    ]

    for i, sp in enumerate(sorted_species):
        lo, hi = freq_ranges[sp]
        label = sp.replace("_whale", "").replace("_", " ").title()
        ax.barh(
            i, hi - lo, left=lo, height=0.6, color=colours[i], alpha=0.8, label=label
        )
        ax.text(hi + 50, i, f"{lo}--{hi} Hz", va="center", fontsize=8)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(
        [s.replace("_whale", "").replace("_", " ").title() for s in sorted_species]
    )
    ax.set_xscale("log")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_title("Species-Specific Frequency Bands")
    ax.set_xlim(5, 15000)
    ax.grid(True, alpha=0.3, axis="x")
    plt.tight_layout()
    fig.savefig(DIAGRAM_DIR / "frequency_bands.png", dpi=150)
    plt.close(fig)

    # ── 7. Class weight visualisation ───────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    cw_species = list(CLASS_WEIGHTS.keys())
    cw_short = [s.replace("_whale", "").replace("_", " ").title() for s in cw_species]
    cw_vals = list(CLASS_WEIGHTS.values())
    colors = [
        "#E74C3C" if v > 2 else "#F39C12" if v > 1 else "#00968A" for v in cw_vals
    ]
    bars = ax.bar(cw_short, cw_vals, color=colors)
    ax.axhline(y=1.0, color="grey", linestyle="--", linewidth=1, label="Balanced (1.0)")
    ax.set_ylabel("Class Weight")
    ax.set_title("Inverse-Frequency Class Weights")
    ax.set_xticklabels(cw_short, rotation=30, ha="right")
    ax.legend()
    for bar, val in zip(bars, cw_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.03,
            f"{val:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    plt.tight_layout()
    fig.savefig(DIAGRAM_DIR / "class_weights.png", dpi=150)
    plt.close(fig)

    print(f"Generated {len(list(DIAGRAM_DIR.glob('*.png')))} diagrams in {DIAGRAM_DIR}")


# ═══════════════════════════════════════════════════════════════
# Report builder
# ═══════════════════════════════════════════════════════════════


def build_report():  # noqa: C901 PLR0915
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ════════════════════════════════════════════════════════
    # COVER PAGE
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.ln(40)
    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.rect(0, 30, 210, 65, style="F")

    pdf.set_xy(10, 38)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.cell(0, 14, "Audio Classification", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "Whale Species Identification from Underwater Audio",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "I", 11)
    pdf.set_text_color(180, 200, 220)
    pdf.cell(
        0,
        10,
        "Marine Risk Mapping  |  March 2026",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(30)
    pdf.stat_boxes(
        [
            ("8", "Species"),
            (str(TOTAL_FILES), "Audio Files"),
            (f"{TOTAL_SEGMENTS:,}", "Segments"),
            ("99.3%", "Best Accuracy"),
        ]
    )

    pdf.ln(10)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5.5,
        (
            "This report describes the whale audio species classification system "
            "built for the Marine Risk Mapping platform. The pipeline downloads "
            "training audio from four public databases, extracts acoustic features "
            "and mel spectrograms, applies a three-stage class balancing strategy, "
            "and trains two complementary classifiers: XGBoost on 64 acoustic "
            "features and a ResNet18 CNN on mel-spectrogram images. Both models "
            "achieve > 97% accuracy across 8 cetacean species, with the CNN "
            "reaching 99.3% accuracy and 99.4% macro F1."
        ),
        align="C",
    )

    # ════════════════════════════════════════════════════════
    # PAGE 2: Pipeline Architecture
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("1. Pipeline Architecture")

    pdf.body_text(
        "The audio classification pipeline follows the project's established "
        "pattern: ingestion scripts in pipeline/ingestion/, domain-specific "
        "library code in pipeline/audio/, and training scripts in "
        "pipeline/analysis/. All constants are centralised in pipeline/config.py."
    )

    pdf.add_image_safe(
        DIAGRAM_DIR / "pipeline_architecture.png",
        caption="Figure 1: End-to-end audio classification pipeline architecture.",
    )

    pdf.subsection_title("Key Design Decisions")
    pdf.bullet(
        "Two-backend architecture: XGBoost for fast, interpretable results; "
        "CNN for maximum accuracy on mel spectrograms."
    )
    pdf.bullet(
        "Consistent 3-stage balancing across both backends: segment cap (2,000), "
        "augmentation to minimum floor (500), inverse-frequency class weights."
    )
    pdf.bullet(
        "All audio constants centralised in pipeline/config.py (22 constants) -- "
        "sample rate, segment duration, mel parameters, augmentation ranges, etc."
    )
    pdf.bullet(
        "CNN trained on Apple MPS (M-series GPU) with early stopping (patience=7) "
        "to prevent overfitting."
    )

    # ════════════════════════════════════════════════════════
    # PAGE 3: Training Data
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("2. Training Data")

    pdf.body_text(
        f"The pipeline downloads {TOTAL_FILES} audio files across 8 cetacean species "
        "from 4 public databases. Files range from short individual call "
        "recordings (<10 s) to extended continuous monitoring sessions. "
        "The download script (download_whale_audio.py) handles format "
        "conversion, deduplication, and organisation into species folders."
    )

    pdf.subsection_title("Data Sources")
    headers = ["Source", "Species", "Format"]
    rows = [[d["name"], d["species"], d["format"]] for d in DATA_SOURCES]
    pdf.metric_table(headers, rows, col_widths=[60, 90, 40])

    pdf.add_image_safe(
        DIAGRAM_DIR / "file_counts.png",
        w=170,
        caption="Figure 2: Raw audio file counts per species. Colour indicates data abundance.",
    )

    pdf.subsection_title("Class Imbalance Challenge")
    pdf.body_text(
        "The raw file distribution is severely imbalanced: killer whale has 179 files "
        "while sei whale has only 1. However, because files vary enormously in duration "
        "(a single blue whale file can contain hundreds of 4-second segments), the "
        "segment-level distribution after segmentation is less extreme but still "
        "requires intervention."
    )

    # ════════════════════════════════════════════════════════
    # PAGE 4: Preprocessing Pipeline
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("3. Preprocessing Pipeline")

    pdf.body_text(
        "Audio preprocessing is implemented in pipeline/audio/preprocess.py and "
        "produces two parallel representations from each recording: a vector of "
        "64 acoustic features (for XGBoost) and a mel spectrogram image "
        "(for the CNN)."
    )

    pdf.subsection_title("A. Loading & Resampling")
    pdf.body_text(
        "All audio is loaded via librosa and resampled to 16 kHz mono. A "
        "max_duration_sec parameter prevents loading entire 24-hour continuous "
        "monitoring files -- only enough audio to fill the species segment cap "
        "is loaded per file."
    )

    pdf.subsection_title("B. Segmentation")
    pdf.body_text(
        "Recordings are split into 4-second windows with a 2-second hop (50% "
        "overlap). This generates overlapping segments that capture temporal "
        "context while increasing the effective training set size. Configuration: "
        "AUDIO_SEGMENT_DURATION=4.0, AUDIO_SEGMENT_HOP=2.0."
    )

    pdf.subsection_title("C. Acoustic Feature Extraction (64 features)")
    pdf.body_text(
        "For the XGBoost backend, each segment is summarised into 64 numerical "
        "descriptors computed via librosa:"
    )

    headers = ["Feature Group", "Count", "Purpose"]
    rows = [[g[0], g[1], g[2]] for g in FEATURE_GROUPS]
    pdf.metric_table(headers, rows, col_widths=[40, 70, 80])

    pdf.subsection_title("D. Mel Spectrogram Generation")
    pdf.body_text(
        "For the CNN backend, each segment produces a 128-bin mel spectrogram "
        "(n_fft=2048, hop_length=512, fmin=10 Hz, fmax=8000 Hz). Spectrograms "
        "are converted to dB scale and padded to uniform time dimension before "
        "being fed to ResNet18 as 3-channel pseudo-RGB images."
    )

    # ════════════════════════════════════════════════════════
    # PAGE: Species Frequency Bands
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.subsection_title("E. Species-Specific Frequency Bands")
    pdf.body_text(
        "Each whale species vocalises in a characteristic frequency range. "
        "These bands are configured in pipeline/config.py (WHALE_FREQ_BANDS) "
        "and used for optional bandpass pre-filtering before feature extraction. "
        "The wide separation between species (e.g. blue whale at 10-100 Hz vs "
        "sperm whale at 2-8 kHz) is the fundamental signal that makes acoustic "
        "species identification feasible."
    )

    pdf.add_image_safe(
        DIAGRAM_DIR / "frequency_bands.png",
        w=170,
        caption="Figure 3: Species-specific vocalisation frequency bands (log scale).",
    )

    headers = ["Species", "Frequency Band"]
    rows = [
        [s.replace("_whale", "").replace("_", " ").title(), b]
        for s, b in FREQ_BANDS.items()
    ]
    pdf.metric_table(headers, rows, col_widths=[50, 140])

    # ════════════════════════════════════════════════════════
    # PAGE: Class Balancing
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("4. Three-Stage Class Balancing")

    pdf.body_text(
        "Both XGBoost and CNN training paths use an identical three-stage "
        "balancing strategy to handle the 40:1 class imbalance between "
        "the most and least represented species:"
    )

    pdf.subsection_title(
        "Stage 1: Segment Cap (AUDIO_MAX_SEGMENTS_PER_SPECIES = 2,000)"
    )
    pdf.body_text(
        "Species with very long recordings (blue whale, sperm whale) can produce "
        "thousands of segments from just a few files. We cap each species at "
        "2,000 segments via random subsampling to prevent the largest classes "
        "from dominating training."
    )

    pdf.subsection_title("Stage 2: Augmentation (AUDIO_AUGMENT_TARGET = 500)")
    pdf.body_text(
        "Species below 500 segments are augmented using three random "
        "transformations applied jointly: time stretching (0.9-1.1x), pitch "
        "shifting (+/-2 semitones), and additive Gaussian noise (15-30 dB SNR). "
        "A 25% random time shift is also applied. This brings killer whale, "
        "minke whale, and sei whale up to 500 segments each."
    )

    pdf.subsection_title("Stage 3: Inverse-Frequency Class Weights")
    pdf.body_text(
        "After segmentation and augmentation, we compute inverse-frequency "
        "weights: w_c = N / (C * n_c). These weights scale the loss function "
        "so that errors on rare species are penalised more heavily. Applied "
        "as sample_weight in XGBoost and as CrossEntropyLoss(weight=...) in "
        "the CNN."
    )

    pdf.add_image_safe(
        DIAGRAM_DIR / "segment_distribution.png",
        w=170,
        caption="Figure 4: Segment distribution after balancing. Orange = augmented synthetic segments.",
    )

    pdf.add_image_safe(
        DIAGRAM_DIR / "class_weights.png",
        w=160,
        caption="Figure 5: Inverse-frequency class weights. Red bars indicate > 2x upweighting.",
    )

    # ════════════════════════════════════════════════════════
    # PAGE: XGBoost Results
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("5. XGBoost Results")

    pdf.stat_boxes(
        [
            ("97.9%", "CV Accuracy"),
            ("98.2%", "Macro F1"),
            ("10,185", "Segments"),
            ("213.7 s", "Training Time"),
        ]
    )

    pdf.ln(4)
    pdf.body_text(
        "The XGBoost classifier operates on the 64-dimensional acoustic feature "
        "vectors. Evaluation uses 5-fold stratified cross-validation (all folds "
        "contribute to the final classification report). The model achieves "
        "near-perfect performance on most species, with the main weakness "
        "being blue/fin whale confusion."
    )

    pdf.subsection_title("Per-Class Performance")
    headers = ["Species", "Precision", "Recall", "F1", "Support"]
    rows = []
    for sp, m in XGBOOST_RESULTS["per_class"].items():
        rows.append(
            [
                sp.replace("_whale", "").replace("_", " ").title(),
                f"{m['precision']:.2f}",
                f"{m['recall']:.2f}",
                f"{m['f1']:.2f}",
                str(m["support"]),
            ]
        )
    rows.append(
        [
            "Overall",
            f"{XGBOOST_RESULTS['accuracy']:.3f}",
            "--",
            f"{XGBOOST_RESULTS['macro_f1']:.3f}",
            str(XGBOOST_RESULTS["n_segments"]),
        ]
    )
    pdf.metric_table(headers, rows, col_widths=[45, 30, 30, 30, 30])

    pdf.subsection_title("Confusion Matrix")
    pdf.add_image_safe(
        ARTIFACT_DIR / "confusion_matrix.png",
        w=150,
        caption="Figure 6: XGBoost confusion matrix (5-fold aggregated).",
    )

    # ════════════════════════════════════════════════════════
    # PAGE: XGBoost Feature Importance
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.subsection_title("Feature Importance Analysis")

    pdf.body_text(
        "Spectral rolloff (the frequency below which 85% of spectral energy "
        "concentrates) is the most discriminative feature by a wide margin. "
        "This makes ecological sense: low-frequency baleen whale calls (blue, "
        "fin: <100 Hz) have dramatically different spectral rolloff than "
        "high-frequency odontocete clicks (sperm whale: 2-8 kHz). Spectral "
        "flatness (tonal vs noisy signal) ranks second, distinguishing tonal "
        "whale song from broadband clicks."
    )

    pdf.add_image_safe(
        ARTIFACT_DIR / "feature_importance.png",
        w=170,
        caption="Figure 7: Top 30 XGBoost feature importances (gain).",
    )

    pdf.subsection_title("Top 10 Features")
    headers = ["Rank", "Feature", "Gain"]
    rows = [[str(i + 1), f[0], f"{f[1]:.1f}"] for i, f in enumerate(TOP_FEATURES)]
    pdf.metric_table(headers, rows, col_widths=[15, 110, 65])

    pdf.subsection_title("Interpretation")
    pdf.bullet(
        "Spectral shape features (rolloff, flatness, bandwidth) dominate -- these "
        "capture the fundamental frequency range differences between species."
    )
    pdf.bullet(
        "MFCCs provide timbral detail -- coefficients 4, 5, 7, 14, 18 each contribute "
        "meaningfully, covering different aspects of vocal tract shape."
    )
    pdf.bullet("RMS energy and dominant frequency add amplitude and pitch information.")
    pdf.bullet(
        "The spread across many feature types (spectral, cepstral, temporal) "
        "suggests the model uses multiple complementary cues -- good for robustness."
    )

    # ════════════════════════════════════════════════════════
    # PAGE: CNN Results
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("6. CNN Results (ResNet18)")

    pdf.stat_boxes(
        [
            ("99.3%", "Val Accuracy"),
            ("99.4%", "Best Val F1"),
            ("Ep. 5/12", "Best / Stopped"),
            ("279.7 s", "Training Time"),
        ]
    )

    pdf.ln(4)
    pdf.body_text(
        "The CNN fine-tunes a pretrained ResNet18 on 128-bin mel spectrograms. "
        "Training uses an 80/20 stratified split with inverse-frequency class "
        "weights in the CrossEntropyLoss. Adam optimiser (lr=0.001) with "
        "ReduceLROnPlateau scheduler. Early stopping (patience=7 epochs) "
        "triggered at epoch 12 after the best validation F1 (0.9943) was "
        "achieved at epoch 5."
    )

    pdf.subsection_title("Per-Class Performance")
    headers = ["Species", "Precision", "Recall", "F1", "Support"]
    rows = []
    for sp, m in CNN_RESULTS["per_class"].items():
        rows.append(
            [
                sp.replace("_whale", "").replace("_", " ").title(),
                f"{m['precision']:.2f}",
                f"{m['recall']:.2f}",
                f"{m['f1']:.2f}",
                str(m["support"]),
            ]
        )
    rows.append(
        [
            "Overall",
            f"{CNN_RESULTS['accuracy']:.3f}",
            "--",
            f"{CNN_RESULTS['macro_f1']:.3f}",
            str(CNN_RESULTS["n_val"]),
        ]
    )
    pdf.metric_table(headers, rows, col_widths=[45, 30, 30, 30, 30])

    pdf.subsection_title("Training Dynamics")
    pdf.body_text(
        "The CNN converges very quickly (val F1 = 0.9943 by epoch 5), then shows "
        "signs of overfitting at epoch 10 where validation accuracy drops to "
        "90.8%. Early stopping correctly catches this and halts training at "
        "epoch 12, restoring the best model weights from epoch 5. The entire "
        "training run takes under 5 minutes on Apple MPS."
    )

    pdf.add_image_safe(
        DIAGRAM_DIR / "cnn_training_curves.png",
        w=170,
        caption="Figure 8: CNN training loss and validation metrics. Vertical lines mark best epoch (green) and early stop (orange).",
    )

    # ════════════════════════════════════════════════════════
    # PAGE: Model Comparison
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("7. Model Comparison")

    pdf.body_text(
        "Both models achieve excellent classification performance. The CNN "
        "has a consistent edge, particularly on the most challenging species "
        "(fin whale and blue whale), likely because mel spectrograms preserve "
        "fine temporal-spectral patterns that the 64-feature summary cannot "
        "fully capture."
    )

    pdf.subsection_title("Head-to-Head Metrics")
    headers = ["Metric", "XGBoost", "CNN", "Delta"]
    rows = [
        [
            "Accuracy",
            f"{XGBOOST_RESULTS['accuracy']:.3f}",
            f"{CNN_RESULTS['accuracy']:.3f}",
            f"+{CNN_RESULTS['accuracy'] - XGBOOST_RESULTS['accuracy']:.3f}",
        ],
        [
            "Macro F1",
            f"{XGBOOST_RESULTS['macro_f1']:.3f}",
            f"{CNN_RESULTS['macro_f1']:.3f}",
            f"+{CNN_RESULTS['macro_f1'] - XGBOOST_RESULTS['macro_f1']:.3f}",
        ],
        [
            "Weighted F1",
            f"{XGBOOST_RESULTS['weighted_f1']:.3f}",
            f"{CNN_RESULTS['weighted_f1']:.3f}",
            f"+{CNN_RESULTS['weighted_f1'] - XGBOOST_RESULTS['weighted_f1']:.3f}",
        ],
        [
            "Training Time",
            XGBOOST_RESULTS["training_time"],
            CNN_RESULTS["training_time"],
            "--",
        ],
        ["Interpretability", "High (feature imp.)", "Low (black box)", "--"],
        ["GPU Required", "No", "Recommended", "--"],
    ]
    pdf.metric_table(headers, rows, col_widths=[40, 45, 45, 35])

    pdf.add_image_safe(
        DIAGRAM_DIR / "model_comparison.png",
        w=170,
        caption="Figure 9: Per-species F1 comparison between XGBoost and CNN.",
    )

    pdf.subsection_title("Per-Species Delta Analysis")
    headers = ["Species", "XGBoost F1", "CNN F1", "Delta"]
    rows = []
    for sp in XGBOOST_RESULTS["per_class"]:
        xf1 = XGBOOST_RESULTS["per_class"][sp]["f1"]
        cf1 = CNN_RESULTS["per_class"][sp]["f1"]
        delta = cf1 - xf1
        sign = "+" if delta > 0 else ""
        rows.append(
            [
                sp.replace("_whale", "").replace("_", " ").title(),
                f"{xf1:.2f}",
                f"{cf1:.2f}",
                f"{sign}{delta:.2f}",
            ]
        )
    pdf.metric_table(headers, rows, col_widths=[45, 40, 40, 40])

    pdf.body_text(
        "The CNN's biggest improvements are on fin whale (+0.05 F1) and blue "
        "whale (+0.05 F1) -- the two species most commonly confused with each "
        "other. The mel spectrogram representation preserves the fine harmonic "
        "structure that distinguishes blue whale D/Z calls from fin whale "
        "20 Hz pulses. For already well-separated species (humpback, sperm), "
        "both models perform near-perfectly."
    )

    # ════════════════════════════════════════════════════════
    # PAGE: Technical Stack
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("8. Technical Stack")

    pdf.tech_card(
        "librosa 0.11.0",
        "Audio",
        "Audio loading, resampling, feature extraction, spectrogram computation",
        "Core audio processing library. Used for MFCC, mel spectrogram, spectral features, PCEN.",
    )
    pdf.tech_card(
        "soundfile 0.13.1",
        "Audio",
        "High-performance audio I/O backend",
        "Backend for librosa.load(). Handles WAV, FLAC, AIF formats.",
    )
    pdf.tech_card(
        "XGBoost 3.2.0",
        "ML",
        "Gradient-boosted tree classifier on acoustic features",
        "5-fold stratified CV, multi:softprob objective, sample_weight balancing.",
    )
    pdf.tech_card(
        "PyTorch 2.10 + torchvision",
        "ML",
        "CNN training on mel spectrograms (ResNet18)",
        "Fine-tuned pretrained ResNet18. Apple MPS acceleration. Adam + ReduceLROnPlateau.",
    )
    pdf.tech_card(
        "MLflow",
        "Infra",
        "Experiment tracking and model registry",
        "Logs params, metrics per epoch, artifacts (plots, reports, models).",
    )
    pdf.tech_card(
        "pipeline/audio/classify.py",
        "ML",
        "WhaleAudioClassifier ABC with XGBoost + CNN backends",
        "Uniform API: classify(audio_path) -> species. classify_and_enrich() adds H3 risk context.",
    )

    # ════════════════════════════════════════════════════════
    # PAGE: Key Takeaways
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("9. Key Takeaways")

    takeaways = [
        "Both models exceed 97% accuracy on 8 cetacean species from underwater audio, "
        "validating the acoustic approach for species identification.",
        "The CNN (ResNet18) achieves 99.3% accuracy and 99.4% macro F1, outperforming "
        "XGBoost by +1.4% accuracy -- particularly on the challenging blue/fin distinction.",
        "Three-stage class balancing (cap + augment + weights) is critical: the raw "
        "segment distribution spans 18 to 2,000 segments per species (111:1 ratio).",
        "Spectral rolloff is the single most discriminative acoustic feature, reflecting "
        "the fundamental frequency-range separation between species.",
        "Early stopping (patience=7) correctly prevented CNN overfitting -- the model "
        "peaked at epoch 5 but would have continued degrading through epoch 30.",
        "Training is fast: XGBoost takes 3.5 minutes, CNN takes 4.7 minutes on Apple "
        "MPS. Both fit comfortably in interactive development loops.",
        "The classify_and_enrich() API connects audio classification to the spatial "
        "risk model by joining predictions to fct_collision_risk via H3 cells.",
        "452 training files from 4 public databases provide a solid foundation, but "
        "adding NOAA SanctSound continuous monitoring data would improve real-world "
        "robustness (different noise conditions, recording equipment).",
        "All 22 audio configuration constants are centralised in pipeline/config.py, "
        "ensuring consistency between preprocessing, XGBoost, and CNN paths.",
        "The pipeline follows established project conventions: ingestion in pipeline/ingestion/, "
        "domain logic in pipeline/audio/, training in pipeline/analysis/, with MLflow tracking.",
    ]

    for i, t in enumerate(takeaways, 1):
        pdf.bullet(f"{i}. {t}")

    # ════════════════════════════════════════════════════════
    # PAGE: Challenges & Solutions
    # ════════════════════════════════════════════════════════
    if pdf.get_y() > 200:
        pdf.add_page()
    else:
        pdf.ln(6)

    pdf.section_title("10. Challenges & Solutions")

    challenges = [
        (
            "Severe class imbalance (1 sei whale file vs 179 killer whale files)",
            "Three-stage balancing: segment cap (2,000) prevents large-class dominance, "
            "augmentation lifts small classes to 500, inverse-frequency weights handle "
            "remaining imbalance in the loss function.",
        ),
        (
            "24-hour continuous recordings loading into memory",
            "Added max_duration_sec parameter to load_audio() -- calculates exactly "
            "how many seconds to load based on remaining segment cap, preventing "
            "multi-GB memory consumption.",
        ),
        (
            "CNN overfitting after epoch 5 (val accuracy dropped to 90.8%)",
            "Implemented early stopping with patience=7. The model now correctly "
            "stops at epoch 12 and restores the best weights from epoch 5.",
        ),
        (
            "Blue/fin whale confusion in XGBoost (F1: 0.95/0.94)",
            "CNN resolves this (+0.05 F1 for both species) because mel spectrograms "
            "preserve temporal-spectral patterns that the 64-feature summary compresses.",
        ),
        (
            "Inconsistent balancing between XGBoost and CNN paths",
            "Refactored both paths to use identical cap + augment + weight strategy "
            "with the same random seeds, ensuring fair model comparison.",
        ),
    ]

    for title, solution in challenges:
        pdf.subsection_title(title)
        pdf.body_text(solution)

    # ════════════════════════════════════════════════════════
    # DONE
    # ════════════════════════════════════════════════════════
    pdf.output(str(OUTPUT_FILE))
    print(f"Report saved to {OUTPUT_FILE}")
    print(f"  Total pages: {pdf.page_no()}")


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    _generate_diagrams()
    build_report()

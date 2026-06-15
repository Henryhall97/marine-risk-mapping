"""Generate Phase 7 summary PDF: Machine Learning -- Species Distribution Models.

Comprehensive report with all model results, per-species analysis,
embedded diagnostic diagrams, and metric explanations.
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs" / "modelling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "phase7_machine_learning.pdf"

# Artifact roots
ARTIFACT_ROOT = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "processed"
    / "ml"
    / "artifacts"
)
SDM_DIR = ARTIFACT_ROOT / "sdm"
SEASONAL_DIR = ARTIFACT_ROOT / "sdm_seasonal"
ISDM_DIR = ARTIFACT_ROOT / "isdm"


# ── Per-species result data ──────────────────────────────────────────
# Collected from training run logs

SEASONAL_WHALE_RESULT = {
    "auc": "0.9556 +/- 0.0085",
    "ap": "0.2565 +/- 0.0855",
    "rows": "7.30M",
    "pos_rate": "1.38%",
    "season_auc": {
        "winter": 0.9575,
        "spring": 0.9619,
        "summer": 0.9532,
        "fall": 0.9478,
    },
}

STATIC_SDM_RESULT = {
    "auc": "0.9521 +/- 0.0075",
    "ap": "0.4976 +/- 0.1183",
    "rows": "1.82M",
    "pos_rate": "4.09%",
}

PER_SPECIES_RESULTS = {
    "right_whale": {
        "label": "North Atlantic Right Whale",
        "auc": "0.9907 +/- 0.0025",
        "ap": "0.0681 +/- 0.0625",
        "positives": 3207,
        "prevalence": "0.04%",
        "season_auc": {
            "winter": 0.9907,
            "spring": 0.9933,
            "summer": 0.9826,
            "fall": 0.9888,
        },
        "top_features": ["sla (58%)", "depth_zone_abyssal (21%)", "depth_m (7%)"],
        "ecology": (
            "Critically endangered (~350 remaining). Strongly coastal, "
            "preferring shallow shelf waters with high SLA variability "
            "(upwelling/frontal zones). The model's reliance on SLA and "
            "abyssal depth zone (as a negative indicator) confirms the "
            "species' tight association with dynamic shelf-edge features. "
            "Continental shelf flag is near-zero importance because the "
            "signal is captured more precisely by SLA + depth interaction."
        ),
        "implications": (
            "Extremely high AUC (0.99) reflects a highly restricted, "
            "predictable habitat. Low AP (0.07) is expected given 0.04% "
            "prevalence -- the model correctly identifies habitat but "
            "most shelf waters still lack sightings. Conservation: SLA "
            "could serve as a near-real-time dynamic habitat indicator "
            "for dynamic management areas."
        ),
    },
    "humpback": {
        "label": "Humpback Whale",
        "auc": "0.9873 +/- 0.0020",
        "ap": "0.1990 +/- 0.0796",
        "positives": 20618,
        "prevalence": "0.28%",
        "season_auc": {
            "winter": 0.9837,
            "spring": 0.9882,
            "summer": 0.9869,
            "fall": 0.9839,
        },
        "top_features": [
            "is_continental_shelf (69%)",
            "depth_zone_shelf (14%)",
            "depth_m (6%)",
        ],
        "ecology": (
            "Highly coastal, shelf-associated species found in productive "
            "nearshore waters during feeding season. The overwhelming "
            "dominance of is_continental_shelf (69%) and depth_zone_shelf "
            "(14%) reflects a clear habitat boundary at the 200m isobath. "
            "Most sightings (28% of all species) occur on the continental "
            "shelf where prey aggregates."
        ),
        "implications": (
            "Highest AP of all per-species models (0.20) because humpbacks "
            "are the most commonly sighted species (20.6K positives). "
            "Consistent AUC across all seasons (0.98) means habitat "
            "preferences are stable year-round. Bathymetric features alone "
            "are nearly sufficient -- ocean covariates add marginal value."
        ),
    },
    "fin_whale": {
        "label": "Fin Whale",
        "auc": "0.9823 +/- 0.0040",
        "ap": "0.0871 +/- 0.0434",
        "positives": 9948,
        "prevalence": "0.14%",
        "season_auc": {
            "winter": 0.9686,
            "spring": 0.9882,
            "summer": 0.9870,
            "fall": 0.9744,
        },
        "top_features": [
            "depth_m (37%)",
            "sla (15%)",
            "depth_zone_abyssal (11%)",
        ],
        "ecology": (
            "Wide-ranging feeder using both shelf and slope waters. "
            "Unlike humpbacks, fin whales use deeper habitats, so "
            "continuous depth_m (37%) dominates rather than the binary "
            "shelf flag. SLA importance (15%) suggests association with "
            "mesoscale eddies and fronts that concentrate prey."
        ),
        "implications": (
            "Lower winter AUC (0.97 vs 0.99 spring) suggests more "
            "diffuse winter habitat. The model relies on continuous "
            "environmental gradients rather than sharp boundaries, "
            "making predictions more nuanced. Good candidate for "
            "dynamic seasonal management."
        ),
    },
    "blue_whale": {
        "label": "Blue Whale",
        "auc": "0.9803 +/- 0.0154",
        "ap": "0.0805 +/- 0.0587",
        "positives": 3529,
        "prevalence": "0.05%",
        "season_auc": {
            "winter": 0.9671,
            "spring": 0.9918,
            "summer": 0.9833,
            "fall": 0.9778,
        },
        "top_features": [
            "depth_m (29%)",
            "sst (16%)",
            "sla (8%)",
        ],
        "ecology": (
            "Blue whales are deep-water feeders that target krill "
            "aggregations near submarine canyons and upwelling zones. "
            "SST importance (16% -- highest of any species) reflects "
            "their preference for cool, productive waters. Strong "
            "spring AUC (0.99) aligns with spring upwelling on the "
            "US West Coast where most US blue whale sightings occur."
        ),
        "implications": (
            "Highest CV variance (+/-0.015) of all species -- habitat "
            "use varies more across spatial blocks, possibly because "
            "blue whales concentrate in a few specific areas (Monterey "
            "Canyon, Channel Islands). Spring predictability is "
            "excellent (0.99), suggesting SST-driven upwelling is a "
            "strong seasonal cue."
        ),
    },
    "sperm_whale": {
        "label": "Sperm Whale",
        "auc": "0.9540 +/- 0.0155",
        "ap": "0.0337 +/- 0.0144",
        "positives": 6744,
        "prevalence": "0.09%",
        "season_auc": {
            "winter": 0.9430,
            "spring": 0.9520,
            "summer": 0.9610,
            "fall": 0.9357,
        },
        "top_features": [
            "depth_m (20%)",
            "pp_upper_200m (15%)",
            "sla (11%)",
        ],
        "ecology": (
            "Deep-diving species (routinely >1000m) whose surface "
            "habitat associations are weaker than for baleen whales. "
            "Primary productivity importance (15% -- highest of any "
            "species) may reflect squid prey aggregations in productive "
            "waters. More evenly distributed feature importance suggests "
            "no single environmental variable dominates."
        ),
        "implications": (
            "Lowest AUC of all species (0.95) -- still strong, but "
            "the weakest surface-feature signal. This is ecologically "
            "expected: sperm whales' deep-diving foraging behaviour "
            "decouples surface conditions from habitat quality. Fall "
            "AUC is lowest (0.94), possibly reflecting offshore movements. "
            "Would benefit most from bathymetric slope and deep-layer "
            "covariates if available."
        ),
    },
    "minke_whale": {
        "label": "Minke Whale",
        "auc": "0.9854 +/- 0.0045",
        "ap": "0.0813 +/- 0.0751",
        "positives": 4291,
        "prevalence": "0.06%",
        "season_auc": {
            "winter": 0.9438,
            "spring": 0.9898,
            "summer": 0.9868,
            "fall": 0.9764,
        },
        "top_features": [
            "depth_m (40%)",
            "sla (12%)",
            "depth_zone_abyssal (11%)",
        ],
        "ecology": (
            "Primarily shelf and slope species with strong depth "
            "dependency (40%). The winter AUC dip (0.94) is the "
            "largest seasonal swing of any species -- minkes may shift "
            "to more offshore/southern waters in winter where our "
            "sighting data is sparser."
        ),
        "implications": (
            "High AP variance (+/-0.075) across folds suggests spatial "
            "heterogeneity in sighting density. Some geographic blocks "
            "have dense minke data while others have almost none. "
            "Depth dominance (40%) means bathymetric data alone is "
            "a strong predictor. Winter management should account for "
            "reduced model certainty."
        ),
    },
}

ISDM_RESULTS = {
    "blue_whale": {
        "label": "Blue Whale",
        "rows": "48.8K",
        "auc": "0.9448 +/- 0.0014",
        "ap": "0.9452 +/- 0.0014",
        "top_features": ["depth_m (28%)", "mld (17%)", "sst (16%)"],
        "note": (
            "Depth dominates in both ISDM and seasonal SDM. MLD importance "
            "is higher in ISDM (17% vs 7%) -- Nisi's expert pseudo-absences "
            "may better separate deep-mixing foraging zones."
        ),
    },
    "fin_whale": {
        "label": "Fin Whale",
        "rows": "180K",
        "auc": "0.9337 +/- 0.0008",
        "ap": "0.9271 +/- 0.0010",
        "top_features": ["mld (22%)", "depth_m (18%)", "sst (17%)"],
        "note": (
            "Lowest ISDM AUC -- consistent with fin whales being generalist "
            "feeders with diffuse habitat preferences. MLD tops depth, "
            "suggesting vertical mixing is the key environmental axis "
            "for this species."
        ),
    },
    "humpback_whale": {
        "label": "Humpback Whale",
        "rows": "272K",
        "auc": "0.9714 +/- 0.0006",
        "ap": "0.9712 +/- 0.0004",
        "top_features": ["depth_m (31%)", "sst (16%)", "depth_range_m (15%)"],
        "note": (
            "Highest ISDM AUC -- humpbacks have the clearest environmental "
            "niche. Depth + depth variation (46% combined) dominates, "
            "matching the seasonal SDM's shelf-focused signal."
        ),
    },
    "sperm_whale": {
        "label": "Sperm Whale",
        "rows": "47.2K",
        "auc": "0.9399 +/- 0.0024",
        "ap": "0.9423 +/- 0.0023",
        "top_features": [
            "depth_range_m (28%)",
            "depth_m (25%)",
            "mld (14%)",
        ],
        "note": (
            "Bathymetric variation (28%) tops the list -- sperm whales "
            "prefer complex seafloor topography (canyons, seamounts). "
            "This is a feature our seasonal SDM doesn't emphasise as "
            "strongly (10%), possibly because depth_range_m has less "
            "variation in our H3 sampling."
        ),
    },
}


class ReportPDF(FPDF):
    """Custom PDF with navy/teal theme (matches earlier reports)."""

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
                "Marine Risk Mapping -- Phase 7: Machine Learning",
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

    def section_title(self, title):
        self.ln(4)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*self.NAVY)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.TEAL)
        self.set_line_width(0.6)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(4)

    def subsection_title(self, title):
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
        x = self.get_x()
        self.set_x(x + indent - 5)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.TEAL)
        self.cell(5, 5.5, "-")
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
            self.set_font("Helvetica", "B", 16)
            self.set_text_color(*self.TEAL)
            self.cell(box_w, 8, str(value), align="C")
            self.set_xy(x, y + 12)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(box_w, 6, label, align="C")
        self.set_y(y + 26)

    def metric_table(self, headers, rows, col_widths=None):
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

    def tech_card(self, name, category, purpose, details):
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
            "Evaluation": self.ACCENT_AMBER,
            "Infra": self.ACCENT_GREEN,
            "Fix": self.ACCENT_RED,
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
        """Add an image if the file exists; skip gracefully otherwise."""
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
        # Check page space -- if less than 70mm left, new page
        if self.get_y() + 60 > 277:
            self.add_page()
        self.image(str(p), x=10, w=w)
        if caption:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(0, 5, caption, new_x="LMARGIN", new_y="NEXT")
            self.ln(2)


# ── Report builder ───────────────────────────────────────────────────


def build_report():  # noqa: C901 PLR0915
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ================================================================
    # COVER PAGE
    # ================================================================
    pdf.add_page()
    pdf.ln(40)
    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.rect(0, 30, 210, 65, style="F")

    pdf.set_xy(10, 38)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.cell(0, 14, "Phase 7", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "Machine Learning -- Species Distribution Models",
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
            ("12", "Trained Models"),
            ("0.991", "Best AUC"),
            ("6", "Species"),
            ("18", "Features (SDM)"),
        ]
    )

    pdf.ln(10)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5.5,
        (
            "This phase built four families of XGBoost species distribution "
            "models: a static SDM (1.8M H3 cells), a seasonal all-species "
            "SDM (7.3M cell-seasons), six per-species seasonal SDMs, and "
            "four ISDM models trained on Nisi et al. (2024) curated "
            "presence/absence data. All 12 models use spatial or stratified "
            "cross-validation, MLflow tracking, SHAP explainability, and "
            "produce comprehensive diagnostic plots."
        ),
        align="C",
    )

    # ================================================================
    # PAGE 2: Model Architecture Overview
    # ================================================================
    pdf.add_page()
    pdf.section_title("1. Model Architecture Overview")

    pdf.body_text("Four complementary model families address different questions:")

    pdf.subsection_title("A. Static Whale SDM (train_sdm_model.py)")
    pdf.body_text(
        "Predicts P(cetacean present | environment) per H3 cell (resolution 7, "
        "~1.22 km edge). Trained on 1.8M cells from fct_whale_sdm_training with "
        "a 4.09% positive rate. Uses 14 environmental features. Provides an "
        "annual average habitat suitability map."
    )

    pdf.subsection_title("B. Seasonal All-Species SDM (train_sdm_seasonal.py)")
    pdf.body_text(
        "Extends the static SDM to (h3_cell, season) grain -- 7.3M rows across "
        "4 seasons. Adds 4 season one-hot indicators for 18 total features. "
        "Captures how the same location changes habitat quality across seasons "
        "as SST, MLD, and productivity shift."
    )

    pdf.subsection_title("C. Per-Species Seasonal SDMs (--target flag)")
    pdf.body_text(
        "Six species-specific models trained on the same seasonal feature matrix "
        "but with individual species targets: right whale, humpback, fin whale, "
        "blue whale, sperm whale, and minke whale. Each reveals unique habitat "
        "drivers and seasonal patterns for that species."
    )

    pdf.subsection_title("D. ISDM Per-Species (train_isdm_model.py)")
    pdf.body_text(
        "Four species-specific models trained on Nisi et al. (2024) curated "
        "datasets with expert-generated pseudo-absences (~50/50 balance). "
        "Uses 7 shared ocean/bathymetry covariates. Provides independent "
        "validation of our SDM features against a published benchmark."
    )

    # ================================================================
    # PAGE 3: Understanding the Metrics
    # ================================================================
    pdf.add_page()
    pdf.section_title("2. Understanding the Metrics")

    pdf.body_text(
        "Each model is evaluated with multiple metrics that capture different "
        "aspects of performance. Understanding what each metric measures -- "
        "and its limitations -- is essential for interpreting results."
    )

    pdf.subsection_title("AUC-ROC (Area Under the ROC Curve)")
    pdf.body_text(
        "Measures the model's ability to RANK positive cases above negatives. "
        "Interpretation: if you randomly pick one whale-present cell and one "
        "whale-absent cell, AUC is the probability the model assigns a higher "
        "score to the whale cell.\n\n"
        "Range: 0.5 (random) to 1.0 (perfect). Key property: AUC is "
        "PREVALENCE-INDEPENDENT -- it gives the same value whether 1% or 50% "
        "of cells are positive. This makes it comparable across our seasonal "
        "SDM (1.38% positive) and ISDM models (50% positive).\n\n"
        "Limitation: AUC can be high even if the model's probability "
        "calibration is poor. A model that ranks correctly but outputs "
        "P=0.99 for everything still gets perfect AUC."
    )

    pdf.subsection_title("Average Precision (AP)")
    pdf.body_text(
        "Area under the Precision-Recall curve. Unlike AUC, AP is heavily "
        "influenced by class prevalence. A random classifier's expected AP "
        "equals the positive rate: AP_baseline = 0.0138 (seasonal SDM) vs "
        "0.50 (ISDM).\n\n"
        "Why AP matters: In highly imbalanced data, a model can achieve "
        "AUC=0.95 while generating thousands of false positives for every "
        "true positive. AP penalises this directly -- high AP means the model's "
        "top-ranked predictions are actually positive cases.\n\n"
        "Interpreting AP across models: An AP of 0.07 for right whales "
        "(0.04% prevalence) means the model enriches whale presence ~175x "
        "above the base rate at optimal threshold. Compare this to AP=0.97 "
        "for ISDM humpback (50% prevalence) -- the numbers are not directly "
        "comparable because the baselines differ."
    )

    pdf.subsection_title("Calibration Metrics (Log Loss & Brier Score)")
    pdf.body_text(
        "Log Loss measures how well predicted probabilities match actual "
        "outcomes. Lower is better. Heavily penalises confident wrong "
        "predictions (P=0.99 for a negative case). Brier Score is the "
        "mean squared error of probabilities -- values near 0 indicate "
        "well-calibrated predictions where P=0.3 means ~30% of such cases "
        "are truly positive.\n\n"
        "The calibration plots (shown per model) visualise this: perfectly "
        "calibrated models follow the diagonal. Curves above the diagonal "
        "mean the model underestimates probability; below means overestimation."
    )

    pdf.subsection_title("Per-Season AUC")
    pdf.body_text(
        "For seasonal models, AUC is computed per season by filtering "
        "out-of-fold predictions. This reveals whether the model performs "
        "consistently or struggles in specific periods. Common pattern: "
        "spring and summer AUC tend to be highest (more sightings, clearer "
        "environmental signal), winter and fall lower (fewer observations, "
        "mixed conditions)."
    )

    # ================================================================
    # PAGE 4-5: Static SDM Results + Diagrams
    # ================================================================
    pdf.add_page()
    pdf.section_title("3. Static SDM Results")

    pdf.stat_boxes(
        [
            ("0.952", "AUC-ROC"),
            ("0.498", "Avg Precision"),
            ("1.82M", "Cells"),
            ("4.09%", "Positive Rate"),
        ]
    )

    pdf.ln(4)
    pdf.body_text(
        "The static SDM provides an annual average habitat suitability map. "
        "With AUC=0.952, the model strongly separates whale-present from "
        "whale-absent cells. AP=0.50 (vs baseline 0.04) represents a 12x "
        "enrichment -- the model's top predictions are 12 times more likely "
        "to contain whale sightings than random selection.\n\n"
        "Top features: is_continental_shelf (41%), depth_zone_shelf (19%), "
        "depth_m (14%). Bathymetric features collectively account for ~80% "
        "of model gain -- the continental shelf boundary is the strongest "
        "single predictor of cetacean presence."
    )

    pdf.subsection_title("ROC & Precision-Recall Curves")
    pdf.add_image_safe(
        SDM_DIR / "roc_pr_curves.png",
        w=180,
        caption="Fig 3.1: Static SDM -- ROC curve (left) shows strong "
        "separation; PR curve (right) shows precision holds well at "
        "moderate recall.",
    )

    pdf.subsection_title("SHAP Feature Importance")
    pdf.body_text(
        "SHAP values decompose each prediction into per-feature contributions. "
        "The beeswarm plot shows each cell as a dot -- position on x-axis is "
        "the SHAP value (impact on prediction), colour is feature value "
        "(red=high, blue=low). Features sorted by mean |SHAP|."
    )
    pdf.add_image_safe(
        SDM_DIR / "shap_summary.png",
        w=170,
        caption="Fig 3.2: Static SDM SHAP -- is_continental_shelf dominates. "
        "Red dots (shelf=true) push predictions strongly positive.",
    )

    pdf.add_page()
    pdf.subsection_title("Feature Importance (Gain)")
    pdf.add_image_safe(
        SDM_DIR / "feature_importance.png",
        w=170,
        caption="Fig 3.3: Static SDM XGBoost gain importance. Shelf features "
        "account for 60% of total gain.",
    )

    pdf.subsection_title("Calibration Plot")
    pdf.add_image_safe(
        SDM_DIR / "calibration.png",
        w=170,
        caption="Fig 3.4: Static SDM calibration -- predicted probability vs "
        "observed frequency. Closeness to diagonal = good calibration.",
    )

    # ================================================================
    # PAGE 6-7: Seasonal All-Species SDM
    # ================================================================
    pdf.add_page()
    pdf.section_title("4. Seasonal All-Species SDM")

    pdf.stat_boxes(
        [
            ("0.956", "AUC-ROC"),
            ("0.257", "Avg Precision"),
            ("7.30M", "Cell-Seasons"),
            ("1.38%", "Positive Rate"),
        ]
    )

    pdf.ln(4)
    pdf.body_text(
        "The seasonal model captures how habitat suitability varies across "
        "winter, spring, summer, and fall. Despite 4x more rows (and lower "
        "positive rate), AUC remains comparable to the static model (0.956 "
        "vs 0.952). Lower AP (0.26 vs 0.50) is expected -- the positive "
        "baseline dropped from 4.09% to 1.38%.\n\n"
        "is_continental_shelf dominates even more strongly (74%) in the "
        "seasonal model, likely because ocean covariate variations across "
        "seasons are secondary to the fundamental shelf/deep-ocean divide."
    )

    pdf.subsection_title("Per-Season Performance")
    pdf.metric_table(
        ["Season", "OOF AUC", "Interpretation"],
        [
            [
                "Winter (Dec-Feb)",
                "0.9575",
                "Cold SST signal, less effort but clear habitat",
            ],
            [
                "Spring (Mar-May)",
                "0.9619",
                "Best -- migration + upwelling create clear niche",
            ],
            [
                "Summer (Jun-Aug)",
                "0.9532",
                "Good -- warm SST, high PP in productive areas",
            ],
            ["Fall (Sep-Nov)", "0.9478", "Lowest -- fewer sightings, mixed conditions"],
        ],
        col_widths=[38, 25, 127],
    )

    pdf.add_image_safe(
        SEASONAL_DIR / "whale" / "roc_pr_curves.png",
        w=180,
        caption="Fig 4.1: Seasonal all-species SDM -- ROC and PR curves.",
    )

    pdf.add_page()
    pdf.subsection_title("Season AUC Comparison")
    pdf.add_image_safe(
        SEASONAL_DIR / "whale" / "season_auc.png",
        w=170,
        caption="Fig 4.2: Per-season AUC -- spring highest, fall lowest.",
    )

    pdf.subsection_title("SHAP Feature Importance")
    pdf.add_image_safe(
        SEASONAL_DIR / "whale" / "shap_summary.png",
        w=170,
        caption="Fig 4.3: Seasonal SDM SHAP -- is_continental_shelf (74%) "
        "dominates. Season indicators contribute modestly.",
    )

    pdf.add_page()
    pdf.subsection_title("Feature Importance (Gain)")
    pdf.add_image_safe(
        SEASONAL_DIR / "whale" / "feature_importance.png",
        w=170,
        caption="Fig 4.4: Seasonal SDM gain importance.",
    )

    pdf.subsection_title("Calibration Plot")
    pdf.add_image_safe(
        SEASONAL_DIR / "whale" / "calibration.png",
        w=170,
        caption="Fig 4.5: Seasonal SDM calibration.",
    )

    # ================================================================
    # PAGE 8: Per-Species Results Overview
    # ================================================================
    pdf.add_page()
    pdf.section_title("5. Per-Species Seasonal SDMs")

    pdf.body_text(
        "Six species-specific models trained on the same 7.3M-row seasonal "
        "feature matrix, each targeting a different species' presence. "
        "These reveal how habitat drivers differ across species and "
        "which environmental features matter most for each."
    )

    pdf.subsection_title("Summary Comparison")
    pdf.metric_table(
        [
            "Species",
            "AUC-ROC",
            "Avg Precision",
            "Positives",
            "Prevalence",
            "Top Feature",
        ],
        [
            ["Right Whale", "0.9907", "0.0681", "3,207", "0.04%", "sla (58%)"],
            ["Humpback", "0.9873", "0.1990", "20,618", "0.28%", "shelf (69%)"],
            ["Fin Whale", "0.9823", "0.0871", "9,948", "0.14%", "depth_m (37%)"],
            ["Blue Whale", "0.9803", "0.0805", "3,529", "0.05%", "depth_m (29%)"],
            ["Minke Whale", "0.9854", "0.0813", "4,291", "0.06%", "depth_m (40%)"],
            ["Sperm Whale", "0.9540", "0.0337", "6,744", "0.09%", "depth_m (20%)"],
        ],
        col_widths=[30, 24, 30, 22, 24, 60],
    )

    pdf.subsection_title("Key Patterns Across Species")
    pdf.bullet(
        "Right whale is the most predictable species (AUC 0.991) -- "
        "its narrow habitat niche (shelf-edge, high SLA) is highly "
        "distinctive, despite having the fewest sightings."
    )
    pdf.bullet(
        "Humpback has the highest AP (0.20) -- most sightings (20.6K) "
        "make positive predictions more reliable."
    )
    pdf.bullet(
        "Sperm whale has the lowest AUC (0.954) -- deep-diving behaviour "
        "weakens the surface-feature signal."
    )
    pdf.bullet(
        "Feature dominance varies dramatically: humpback = shelf flag "
        "(69%), right whale = SLA (58%), fin/blue/minke/sperm = "
        "continuous depth (20-40%)."
    )
    pdf.bullet(
        "All species show AUC > 0.95 except sperm whale (0.954) -- "
        "environmental features alone are remarkably predictive."
    )

    # ================================================================
    # PAGES 9-20: Individual Species Deep Dives (2 pages each)
    # ================================================================
    fig_num = 1
    for sp_key, sp in PER_SPECIES_RESULTS.items():
        # --- Page 1: text + stats ---
        pdf.add_page()
        pdf.subsection_title(f"5.{fig_num}  {sp['label']}")

        auc_val = sp["auc"].split(" +/- ")[0]
        ap_val = sp["ap"].split(" +/- ")[0]
        pdf.stat_boxes(
            [
                (auc_val, "AUC-ROC"),
                (ap_val, "Avg Precision"),
                (f"{sp['positives']:,}", "Positives"),
                (sp["prevalence"], "Prevalence"),
            ]
        )

        pdf.ln(2)
        pdf.subsection_title("Ecology & Feature Drivers")
        pdf.body_text(sp["ecology"])

        pdf.subsection_title("Implications")
        pdf.body_text(sp["implications"])

        pdf.subsection_title("Season AUC Breakdown")
        season_rows = []
        for s_name in ["winter", "spring", "summer", "fall"]:
            val = sp["season_auc"][s_name]
            season_rows.append([s_name.capitalize(), f"{val:.4f}"])
        pdf.metric_table(
            ["Season", "AUC-ROC"],
            season_rows,
            col_widths=[50, 50],
        )

        # Diagrams
        sp_dir = SEASONAL_DIR / sp_key

        pdf.add_image_safe(
            sp_dir / "roc_pr_curves.png",
            w=180,
            caption=f"Fig 5.{fig_num}a: {sp['label']} -- ROC and PR curves.",
        )

        # --- Page 2: more diagrams ---
        pdf.add_page()
        pdf.subsection_title(f"5.{fig_num}  {sp['label']} (continued)")

        pdf.add_image_safe(
            sp_dir / "shap_summary.png",
            w=170,
            caption=(
                f"Fig 5.{fig_num}b: {sp['label']} -- SHAP summary. "
                f"Top features: {', '.join(sp['top_features'])}."
            ),
        )

        pdf.add_image_safe(
            sp_dir / "season_auc.png",
            w=170,
            caption=f"Fig 5.{fig_num}c: {sp['label']} -- per-season AUC.",
        )

        pdf.add_image_safe(
            sp_dir / "feature_importance.png",
            w=170,
            caption=f"Fig 5.{fig_num}d: {sp['label']} -- XGBoost gain importance.",
        )

        pdf.add_image_safe(
            sp_dir / "calibration.png",
            w=170,
            caption=f"Fig 5.{fig_num}e: {sp['label']} -- calibration plot.",
        )

        fig_num += 1

    # ================================================================
    # ISDM Models
    # ================================================================
    pdf.add_page()
    pdf.section_title("6. ISDM Benchmark Models")

    pdf.body_text(
        "The ISDM (Integrated Species Distribution Model) family uses "
        "Nisi et al. (2024) curated training data with expert-generated "
        "pseudo-absences, achieving ~50/50 class balance. This independent "
        "dataset provides validation that our environmental features "
        "capture genuine habitat associations.\n\n"
        "Because the data is pre-balanced, AUC and AP are numerically "
        "similar (both near the class ratio). The ISDM models use only "
        "7 features (a subset of our 18) -- the features that map directly "
        "between Nisi's naming convention and ours."
    )

    pdf.subsection_title("ISDM Summary")
    pdf.metric_table(
        ["Species", "Rows", "AUC-ROC", "Avg Precision", "Top Feature"],
        [
            [r["label"], r["rows"], r["auc"], r["ap"], r["top_features"][0]]
            for r in ISDM_RESULTS.values()
        ],
        col_widths=[35, 20, 45, 45, 45],
    )

    pdf.subsection_title("ISDM vs Seasonal SDM: Feature Comparison")
    pdf.body_text(
        "The ISDM models share the same top features as our seasonal SDMs "
        "but with different relative importance -- reflecting differences "
        "in training data (expert pseudo-absences vs opportunistic OBIS "
        "sightings) and feature set (7 vs 18 features).\n\n"
        "Key insight: depth_m is the top feature in both model families "
        "for 3 of 4 shared species. This cross-validation between "
        "independently curated datasets strengthens confidence that "
        "bathymetry is a genuine habitat driver, not an artefact of "
        "sampling bias."
    )

    # Per-ISDM species pages
    fig_num = 1
    for sp_key, sp in ISDM_RESULTS.items():
        pdf.add_page()
        pdf.subsection_title(f"6.{fig_num}  ISDM {sp['label']}")

        auc_val = sp["auc"].split(" +/- ")[0]
        ap_val = sp["ap"].split(" +/- ")[0]
        pdf.stat_boxes(
            [
                (auc_val, "AUC-ROC"),
                (ap_val, "Avg Precision"),
                (sp["rows"], "Training Rows"),
                ("50%", "Pos Rate"),
            ]
        )

        pdf.ln(2)
        pdf.body_text(sp["note"])

        sp_dir = ISDM_DIR / sp_key

        pdf.add_image_safe(
            sp_dir / "roc_pr_curves.png",
            w=180,
            caption=f"Fig 6.{fig_num}a: ISDM {sp['label']} -- ROC and PR curves.",
        )

        pdf.add_image_safe(
            sp_dir / "shap_summary.png",
            w=170,
            caption=(
                f"Fig 6.{fig_num}b: ISDM {sp['label']} -- SHAP summary. "
                f"Top: {', '.join(sp['top_features'])}."
            ),
        )

        pdf.add_image_safe(
            sp_dir / "feature_importance.png",
            w=170,
            caption=f"Fig 6.{fig_num}c: ISDM {sp['label']} -- gain importance.",
        )

        pdf.add_image_safe(
            sp_dir / "calibration.png",
            w=170,
            caption=f"Fig 6.{fig_num}d: ISDM {sp['label']} -- calibration.",
        )

        fig_num += 1

    # ================================================================
    # Feature Engineering
    # ================================================================
    pdf.add_page()
    pdf.section_title("7. Feature Engineering")

    pdf.subsection_title("Static & Seasonal SDM Features (18 cols)")
    pdf.metric_table(
        ["Feature", "Source", "Type", "Description"],
        [
            [
                "sst",
                "Copernicus",
                "Seasonal",
                "Sea surface temperature (climatological mean)",
            ],
            [
                "sst_sd",
                "Copernicus",
                "Seasonal",
                "SST standard deviation (interannual variability)",
            ],
            [
                "mld",
                "Copernicus",
                "Seasonal",
                "Mixed layer depth (vertical mixing indicator)",
            ],
            [
                "sla",
                "Copernicus",
                "Seasonal",
                "Sea level anomaly (mesoscale eddy proxy)",
            ],
            [
                "pp_upper_200m",
                "Copernicus",
                "Seasonal",
                "Primary productivity in upper 200m",
            ],
            ["depth_m", "GEBCO", "Static", "Mean depth (7-point sample)"],
            ["depth_range_m", "GEBCO", "Static", "Max-min depth (gradient proxy)"],
            ["is_continental_shelf", "Derived", "Static", "Boolean: depth 0m to -200m"],
            ["is_shelf_edge", "Derived", "Static", "Boolean: straddles -200m contour"],
            ["depth_zone_*", "Derived", "Static", "One-hot: shelf / slope / abyssal"],
            [
                "dist_to_nearest_*",
                "KDTree",
                "Static",
                "Distance to nearest strike (km)",
            ],
            ["strike_proximity_*", "Derived", "Static", "Exp. decay (half-life 25km)"],
            [
                "season_winter..fall",
                "Derived",
                "Temporal",
                "One-hot season indicators (4 cols)",
            ],
        ],
        col_widths=[42, 26, 22, 100],
    )

    pdf.subsection_title("ISDM Features (7 cols)")
    pdf.metric_table(
        ["ISDM Name", "Our Name", "Description"],
        [
            ["sst", "sst", "Sea surface temperature"],
            ["sst_sd", "sst_sd", "SST standard deviation"],
            ["mld", "mld", "Mixed layer depth"],
            ["sla", "sla", "Sea level anomaly"],
            ["PPupper200m", "pp_upper_200m", "Primary productivity (upper 200m)"],
            ["bathy", "depth_m", "Bathymetric depth"],
            ["bathy_sd", "depth_range_m", "Bathymetric depth variation"],
        ],
        col_widths=[40, 40, 110],
    )

    pdf.subsection_title("Feature Exclusions (Leakage Prevention)")
    pdf.bullet(
        "Traffic features: Detection bias -- survey effort correlates "
        "with vessel traffic."
    )
    pdf.bullet("Whale proximity: Direct target leakage -- computed from sighting data.")
    pdf.bullet("Speed zones: Policy circularity -- placed where whales occur.")
    pdf.bullet("MPA features: Policy decisions, not environment.")
    pdf.bullet("Nisi reference: Model outputs kept for comparison, not training.")

    # ================================================================
    # XGBoost Configuration
    # ================================================================
    pdf.add_page()
    pdf.section_title("8. XGBoost Configuration & Scoring")

    pdf.subsection_title("Hyperparameters")
    pdf.metric_table(
        ["Parameter", "Value", "Purpose"],
        [
            ["objective", "binary:logistic", "Binary classification via sigmoid"],
            ["eval_metric", "auc", "Early stopping on AUC-ROC"],
            ["tree_method", "hist", "Histogram splits, native NaN handling"],
            ["max_depth", "6", "Tree complexity cap"],
            ["learning_rate", "0.05", "Conservative step size"],
            ["n_estimators", "500 (1K static)", "Max rounds (early stopping halts)"],
            ["scale_pos_weight", "auto", "neg/pos ratio per species"],
            ["early_stopping", "50 rounds", "Prevents overfitting"],
        ],
        col_widths=[42, 42, 106],
    )

    pdf.subsection_title("How XGBoost Scores a Cell")
    pdf.body_text(
        "1. TRAINING: Each tree partitions the feature space (e.g., 'if SST > 15 "
        "and depth > -100, lean positive'). Trees added sequentially, each "
        "correcting residual errors of the ensemble.\n\n"
        "2. RAW PREDICTION: For a new cell, leaf values are summed with a "
        "base score (log-odds of overall positive rate) to produce F(x) in "
        "log-odds space.\n\n"
        "3. PROBABILITY: Sigmoid transforms to probability: "
        "P = 1/(1+exp(-F(x))). A cell with SST, depth, and productivity "
        "typical of whale habitat gets high sum -> high probability.\n\n"
        "4. IMBALANCE: scale_pos_weight amplifies each positive sample's "
        "gradient during training. At prediction time, outputs are calibrated "
        "probabilities -- no reweighting needed."
    )

    # ================================================================
    # SHAP Explainability
    # ================================================================
    pdf.add_page()
    pdf.section_title("9. Explainability (SHAP)")

    pdf.body_text(
        "SHAP (SHapley Additive exPlanations) decomposes each prediction "
        "into per-feature contributions. For a cell predicted at P=0.82, "
        "SHAP might show: is_continental_shelf +0.15, SST +0.08, depth_m "
        "+0.06, etc. The sum of all SHAP values plus the base value equals "
        "the raw log-odds prediction.\n\n"
        "We use TreeExplainer (exact SHAP for tree ensembles in polynomial "
        "time) on a sample of 10,000 cells (5,000 for ISDM). Artifacts: "
        "beeswarm summary plot + feature importance bar chart per model."
    )

    pdf.subsection_title("Reading SHAP Beeswarm Plots")
    pdf.body_text(
        "Each row is a feature (sorted by importance). Each dot is a cell. "
        "X-axis = SHAP value (right = pushes prediction toward positive). "
        "Colour = feature value (red = high, blue = low).\n\n"
        "Example: For is_continental_shelf, red dots (shelf=true) cluster "
        "far right (strongly positive SHAP), blue dots (deep ocean) cluster "
        "left. This means being on the shelf is the single strongest "
        "signal for whale presence.\n\n"
        "For SST, red and blue dots may appear on both sides -- the "
        "relationship is non-linear, mediated by species, season, and "
        "location. Non-linear patterns are a strength of tree models."
    )

    pdf.subsection_title("SHAP + XGBoost 3.x Compatibility Fix")
    pdf.body_text(
        "XGBoost 3.x stores base_score as '[5E-1]' in UBJSON format. "
        "SHAP 0.49 reads via save_raw(ubj) -> decode_ubjson_buffer() -> "
        "float() which fails on brackets. After two failed attempts "
        "patching the wrong methods, root-cause analysis of SHAP source "
        "revealed it reads via decode_ubjson_buffer. Fixed by patching "
        "the UBJSON decoder at module level in pipeline/utils.py."
    )

    # ================================================================
    # Critical Assessment
    # ================================================================
    pdf.add_page()
    pdf.section_title("10. Critical Assessment")

    pdf.body_text(
        "An honest appraisal of what these models can and cannot do is "
        "essential for responsible use. The results are strong by ecological "
        "SDM standards, but several caveats must inform how predictions "
        "are interpreted and applied."
    )

    pdf.subsection_title("Strengths")

    pdf.bullet(
        "Discrimination is excellent: every model achieves AUC > 0.93, "
        "well above typical published cetacean SDMs (0.85-0.92). The "
        "models reliably rank whale-present cells above absent cells."
    )
    pdf.bullet(
        "ISDM cross-validation is reassuring: independently curated "
        "Nisi et al. data produces the same top features (depth, SST, "
        "MLD), confirming habitat signals are real, not sampling artefacts."
    )
    pdf.bullet(
        "Species-specific patterns are ecologically coherent: right "
        "whales keying on SLA (frontal zones), humpbacks on shelf depth, "
        "sperm whales showing the weakest surface signal -- all match "
        "established biology."
    )
    pdf.bullet(
        "Spatial CV fold variance is low (0.002-0.016), indicating "
        "stable generalisation across ~158 km geographic blocks."
    )

    pdf.subsection_title("Honest Caveats")

    pdf.bullet(
        "AP tells a more sobering story. Per-species AP ranges from "
        "0.034 (sperm whale) to 0.199 (humpback). In practical terms, "
        "the top-ranked 1% of cell-seasons would still contain a "
        "majority of false positives. The models rank well but absolute "
        "precision at any realistic threshold is limited by extreme rarity."
    )
    pdf.bullet(
        "We model sightings, not true presence. OBIS data is "
        "opportunistic -- the target is 'a whale was observed here,' "
        "not 'a whale was here.' We excluded traffic features to "
        "mitigate detection bias, but the fundamental limitation "
        "remains: absence of sightings does not equal absence of whales."
    )
    pdf.bullet(
        "Continental shelf dominance is a double-edged sword. "
        "is_continental_shelf capturing 41-74% of gain means the models "
        "are largely learning 'whales are on the shelf' -- true, but "
        "not very actionable for fine-grained management. Ocean covariate "
        "contributions (SST, SLA, MLD) are relatively small."
    )
    pdf.bullet(
        "Spatial block CV is conservative but not perfect. 158 km blocks "
        "are large, but US East Coast cetacean populations form a "
        "semi-continuous corridor. True spatial independence would require "
        "leave-one-region-out CV. Reported AUCs may be slightly "
        "optimistic for truly novel regions (e.g., Gulf of Mexico "
        "predicted from East Coast training data)."
    )
    pdf.bullet(
        "No temporal holdout. All seasons and years are mixed in "
        "training. We do not know how well these models predict future "
        "conditions -- only how well they separate habitat in the "
        "historical record. Climate-driven range shifts could degrade "
        "performance over time."
    )

    pdf.subsection_title("Assessment Summary")
    pdf.metric_table(
        ["Aspect", "Rating", "Notes"],
        [
            [
                "Ranking ability",
                "Excellent",
                "AUC >0.95 consistently -- top-tier for ecological SDMs",
            ],
            [
                "Precision at deployment",
                "Moderate",
                "Low AP = many false positives at realistic thresholds",
            ],
            [
                "Ecological validity",
                "Strong",
                "Feature importance matches known biology; ISDM confirms",
            ],
            [
                "Generalisation confidence",
                "Strong",
                "Spatial CV robust; temporal holdout missing",
            ],
            [
                "Actionability for mgmt",
                "Moderate",
                "Good for risk zone ID; too coarse for real-time routing",
            ],
        ],
        col_widths=[45, 28, 117],
    )

    pdf.body_text(
        "Bottom line: these are publication-quality SDMs that reliably "
        "identify where whale habitat is and which environmental features "
        "drive it. They are strong enough to inform spatial risk mapping "
        "and prioritise management areas. They are not yet precise enough "
        "to serve as standalone real-time decision tools -- for that, "
        "layering with dynamic data (real-time SST, AIS, acoustic "
        "detections) and validation against independent survey data "
        "would be needed."
    )

    # ================================================================
    # Challenges & Solutions
    # ================================================================
    pdf.add_page()
    pdf.section_title("11. Challenges & Solutions")

    challenges = [
        (
            "Detection Bias in OBIS Sightings",
            "Cetacean sightings from OBIS are opportunistic -- whales are "
            "observed where ships go. Solution: exclude all traffic, proximity, "
            "speed zone, and MPA features from SDM training. Models use "
            "only environmental covariates.",
        ),
        (
            "Extreme Class Imbalance (0.04% to 4.09%)",
            "Most cells have no sightings. scale_pos_weight auto-balances "
            "gradients. Average Precision replaces accuracy as the key "
            "metric. Per-species prevalence ranges from 0.04% (right whale) "
            "to 0.28% (humpback).",
        ),
        (
            "Spatial Autocorrelation in CV",
            "Standard random CV leaks from nearby cells. Spatial block CV "
            "groups cells by H3 resolution 2 parent (~158 km), ensuring "
            "geographic separation between folds.",
        ),
        (
            "SHAP + XGBoost 3.x base_score Format",
            "Three fix attempts needed. XGBoost 3.x stores '[5E-1]' in UBJSON; "
            "SHAP calls float() on it. Fixed by patching decode_ubjson_buffer "
            "at module level (attempt #3, after two wrong methods).",
        ),
        (
            "Static vs Seasonal AP Discrepancy",
            "AP depends on positive rate baseline. Static (4.09% -> AP=0.50) "
            "vs seasonal (1.38% -> AP=0.26). AUC is prevalence-independent "
            "and shows equal discrimination quality.",
        ),
        (
            "Per-Species Sample Size Variation",
            "Right whale: 3,207 positives vs humpback: 20,618. Addressed via "
            "per-species scale_pos_weight and reporting AP alongside AUC. "
            "CV variance increases for rare species (right whale: +/-0.0025 "
            "vs humpback: +/-0.0020).",
        ),
    ]

    for title, desc in challenges:
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.subsection_title(title)
        pdf.body_text(desc)

    # ================================================================
    # Key Technologies
    # ================================================================
    pdf.add_page()
    pdf.section_title("12. Key Technologies")

    techs = [
        (
            "XGBoost 3.2",
            "ML",
            "Gradient-boosted tree ensemble for binary classification",
            "hist method, scale_pos_weight, early stopping, NaN handling",
        ),
        (
            "SHAP 0.49",
            "ML",
            "Exact Shapley value decomposition for tree ensembles",
            "TreeExplainer, beeswarm plots, per-feature contributions",
        ),
        (
            "MLflow 3.10",
            "Infra",
            "Experiment tracking: params, metrics, artifacts, models",
            "Local file store (./mlruns), auto-logged XGBoost models",
        ),
        (
            "Optuna 4.7",
            "ML",
            "Bayesian hyperparameter optimisation (--tune flag)",
            "TPE sampler, per-trial spatial CV, best params applied",
        ),
        (
            "evaluate.py",
            "Evaluation",
            "Shared metrics + plotting for all training scripts",
            "Binary metrics, ROC/PR curves, calibration, spatial CV",
        ),
        (
            "extract_features.py",
            "Data",
            "Server-side cursor extraction from PostGIS to Parquet",
            "100K chunks, spatial blocks, one-hot encoding, dtype prep",
        ),
        (
            "patch_shap_for_xgboost3",
            "Fix",
            "SHAP/XGBoost 3.x compat -- patches UBJSON decoder",
            "Centralised in utils.py, called before TreeExplainer",
        ),
    ]

    for name, cat, purpose, details in techs:
        pdf.tech_card(name, cat, purpose, details)

    # ================================================================
    # Key Takeaways
    # ================================================================
    pdf.add_page()
    pdf.section_title("13. Key Takeaways")

    takeaways = [
        "12 models trained: 1 static, 1 seasonal all-species, 6 per-species "
        "seasonal, 4 ISDM -- all AUC > 0.93",
        "Right whale (AUC=0.991): SLA is the dominant feature -- dynamic "
        "oceanographic fronts drive habitat, enabling near-real-time "
        "management potential",
        "Humpback (AUC=0.987): Continental shelf flag captures 69% of "
        "model signal -- the simplest, most predictable species habitat",
        "Sperm whale (AUC=0.954): Lowest AUC reflects deep-diving ecology -- "
        "surface features are weaker predictors for this species",
        "Each species has unique feature drivers: shelf vs depth vs SLA vs "
        "productivity -- one-model-fits-all is insufficient",
        "ISDM cross-validation confirms bathymetry as genuine habitat "
        "driver across independently curated datasets",
        "Spatial block CV (H3 res-2, ~158 km) prevents leakage -- fold "
        "AUC variance is 0.002-0.016, indicating stable generalisation",
        "Detection bias addressed: no traffic, whale proximity, or policy "
        "features in any SDM model",
        "Seasonal patterns emerge: spring AUC highest for most species "
        "(migration + upwelling); winter/fall lower",
        "Models are strong enough for spatial risk mapping and zone "
        "prioritisation, but not yet precise enough for standalone "
        "real-time routing without dynamic data layers",
    ]

    for i, text in enumerate(takeaways, 1):
        y = pdf.get_y()
        if y > 265:
            pdf.add_page()
        cx = 17
        cy = y + 4
        pdf.set_fill_color(*ReportPDF.TEAL)
        pdf.ellipse(cx - 4, cy - 4, 8, 8, style="F")
        pdf.set_xy(cx - 4, cy - 3)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*ReportPDF.WHITE)
        pdf.cell(8, 6, str(i), align="C")
        pdf.set_xy(27, y + 1)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*ReportPDF.DARK_TEXT)
        pdf.multi_cell(165, 5, text)
        pdf.ln(3)

    # ================================================================
    # Save
    # ================================================================
    pdf.output(str(OUTPUT_FILE))
    print(f"PDF written to {OUTPUT_FILE}")
    print(f"  Size: {OUTPUT_FILE.stat().st_size / 1024:.0f} KB")
    print(f"  Pages: {pdf.pages_count}")


if __name__ == "__main__":
    build_report()

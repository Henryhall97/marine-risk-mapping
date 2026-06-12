"""Generate Climate Projections & ISDM+SDM Ensemble Methodology PDF.

Describes the ISDM+SDM ensemble approach used for both current and
climate-projected collision risk, the removal of the proximity sub-score
from projected risk, weight renormalisation, and the full CMIP6
projection pipeline from SSP scenarios through to the
fct_collision_risk_ml_projected mart.

Usage:
    uv run python docs/generate/generate_projections_report.py
"""

from pathlib import Path

from fpdf import FPDF

# ── Paths ─────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "climate_projections_ensemble.pdf"


# ═══════════════════════════════════════════════════════════════
# ReportPDF — navy / teal theme (matches all project reports)
# ═══════════════════════════════════════════════════════════════


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
                ("Marine Risk Mapping -- Climate Projections & Ensemble Methodology"),
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

    # ── Layout helpers ────────────────────────────────────────

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

    def numbered_item(self, number, text, indent=15):
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
        for w, h_text in zip(col_widths, headers, strict=True):
            self.cell(w, 7, f"  {h_text}", fill=True)
        self.ln()
        self.set_font("Helvetica", "", 9)
        for i, row in enumerate(rows):
            bg = self.LIGHT_BG if i % 2 == 0 else self.WHITE
            self.set_fill_color(*bg)
            for j, (w, cell_val) in enumerate(zip(col_widths, row, strict=True)):
                if j == 0:
                    self.set_text_color(*self.DARK_TEXT)
                else:
                    self.set_text_color(*self.TEAL)
                self.cell(w, 7, f"  {cell_val}", fill=True)
            self.ln()
        self.ln(3)

    def callout_box(self, title, text, colour=None):
        if colour is None:
            colour = self.ACCENT_BLUE
        if self.get_y() > 245:
            self.add_page()
        y_start = self.get_y()
        self.set_fill_color(*self.LIGHT_BG)
        self.set_font("Helvetica", "", 9.5)
        n_lines = max(1, len(text) // 80 + 1)
        box_h = 12 + n_lines * 5
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

    def equation_box(self, label, equation, note=None):
        if self.get_y() > 255:
            self.add_page()
        y = self.get_y()
        box_h = 22 if note is None else 30
        self.set_fill_color(*self.LIGHT_BG)
        self.rect(20, y, 170, box_h, style="F")
        self.set_draw_color(*self.TEAL)
        self.set_line_width(0.4)
        self.rect(20, y, 170, box_h, style="D")
        self.set_xy(25, y + 2)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*self.MID_TEXT)
        self.cell(0, 5, label)
        self.set_xy(25, y + 8)
        self.set_font("Courier", "B", 11)
        self.set_text_color(*self.NAVY)
        self.cell(0, 7, equation)
        if note:
            self.set_xy(25, y + 18)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.multi_cell(160, 4.5, note)
        self.set_y(y + box_h + 4)


# ═══════════════════════════════════════════════════════════════
# Report content
# ═══════════════════════════════════════════════════════════════


def build_report():  # noqa: C901 PLR0915
    pdf = ReportPDF("P", "mm", "A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Title page ────────────────────────────────────────────
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(
        0,
        14,
        "Climate Projections &",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        14,
        "Ensemble Methodology",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "ISDM+SDM Ensemble for Current & Projected Risk",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.cell(
        0,
        8,
        "Marine Risk Mapping Project",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        8,
        "March 2026",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(20)

    pdf.stat_boxes(
        [
            ("6", "Ensembled species"),
            ("58M", "Projected rows"),
            ("2", "CMIP6 scenarios"),
            ("4", "Future decades"),
        ]
    )

    pdf.ln(12)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        6,
        (
            "This report describes the ISDM+SDM ensemble methodology "
            "used for both current and climate-projected whale-vessel "
            "collision risk.  It covers the rationale for combining two "
            "complementary model families, the species-specific ensemble "
            "strategy, weight renormalisation for projected risk "
            "(6 sub-scores, no proximity), and the full CMIP6 projection "
            "pipeline from SSP scenarios through to the "
            "fct_collision_risk_ml_projected mart."
        ),
        align="C",
    )

    # ══════════════════════════════════════════════════════════
    # 1. Motivation
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("1. Motivation: Why Ensemble?")

    pdf.body_text(
        "Our initial ML-enhanced risk mart (fct_collision_risk_ml) "
        "used only ISDM (Integrated Species Distribution Model) "
        "predictions derived from the Nisi et al. 2024 expert dataset.  "
        "While ISDM provides high-quality habitat suitability estimates "
        "for four species (blue, fin, humpback, sperm whale), it has "
        "two critical limitations:"
    )

    pdf.numbered_item(
        1,
        "Species coverage: ISDM covers only 4 species.  Right whale "
        "and minke whale -- both of conservation concern and present "
        "in the study area -- are entirely absent from the Nisi et al. "
        "training data.",
    )
    pdf.numbered_item(
        2,
        "Data complementarity: ISDM is trained on expert-curated "
        "presence/absence records (548K observations), while our SDM "
        "(Species Distribution Model) is trained on OBIS citizen-science "
        "sightings (~1M records).  The two data sources capture different "
        "aspects of species distribution -- expert surveys tend to cover "
        "known hotspots systematically, while OBIS provides broader "
        "opportunistic coverage.",
    )

    pdf.body_text(
        "To address both limitations, we ensemble ISDM and SDM "
        "predictions using a species-aware strategy that leverages "
        "the strengths of each model family."
    )

    pdf.callout_box(
        "Key insight",
        "Both current and projected risk must use the same ensemble "
        "methodology.  If current risk used ISDM-only but projected "
        "risk used ISDM+SDM, the delta (projected - current) would "
        "conflate model differences with climate signal, making "
        "attribution of risk changes impossible.",
        colour=ReportPDF.ACCENT_AMBER,
    )

    # ══════════════════════════════════════════════════════════
    # 2. Ensemble strategy
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("2. Ensemble Strategy (6 Species)")

    pdf.subsection_title("2.1 Species coverage")

    pdf.metric_table(
        ["Species", "ISDM", "SDM", "Ensemble method"],
        [
            ["Blue whale", "Yes", "Yes", "avg(ISDM, SDM)"],
            ["Fin whale", "Yes", "Yes", "avg(ISDM, SDM)"],
            ["Humpback whale", "Yes", "Yes", "avg(ISDM, SDM)"],
            ["Sperm whale", "Yes", "Yes", "avg(ISDM, SDM)"],
            ["Right whale", "No", "Yes", "SDM only"],
            ["Minke whale", "No", "Yes", "SDM only"],
        ],
        col_widths=[50, 30, 30, 80],
    )

    pdf.body_text(
        "For the four shared species, simple averaging produces a "
        "robust ensemble: ISDM contributes expert-data signal while "
        "SDM contributes observation-based coverage.  For right whale "
        "and minke, SDM predictions are used directly since ISDM has "
        "no training data for these species."
    )

    pdf.subsection_title("2.2 Composite probabilities")

    pdf.body_text(
        "From the 6 ensembled per-species probabilities, we compute "
        "three composite metrics used for risk scoring:"
    )

    pdf.equation_box(
        "Union probability (any whale present)",
        "any_whale = 1 - prod(1 - P_i)  for i in 6 species",
        note=(
            "Assumes species independence.  "
            "Conservative upper bound on true co-occurrence."
        ),
    )

    pdf.equation_box(
        "Maximum species probability",
        "max_whale = max(P_blue, P_fin, ..., P_minke)",
        note="Captures the single most likely species at each cell.",
    )

    pdf.equation_box(
        "Mean species probability",
        "mean_whale = avg(P_blue, P_fin, ..., P_minke)",
        note="Smoothed community-level presence indicator.",
    )

    pdf.subsection_title("2.3 Implementation in SQL")

    pdf.body_text(
        "The ensemble is computed in fct_collision_risk_ml.sql in the "
        "'features' CTE.  The mart LEFT JOINs both int_ml_whale_predictions "
        "(ISDM) and int_sdm_whale_predictions (SDM) on (h3_cell, season).  "
        "For each species, the ensemble column is computed with COALESCE:"
    )

    pdf.callout_box(
        "SQL pattern (shared species)",
        "CASE WHEN isdm.blue_whale IS NOT NULL "
        "AND sdm.sdm_blue_whale IS NOT NULL "
        "THEN (isdm.blue_whale + sdm.sdm_blue_whale) / 2.0 "
        "WHEN isdm.blue_whale IS NOT NULL THEN isdm.blue_whale "
        "ELSE sdm.sdm_blue_whale END AS blue_whale_prob",
        colour=ReportPDF.TEAL,
    )

    pdf.callout_box(
        "SQL pattern (SDM-only species)",
        "sdm.sdm_right_whale AS right_whale_prob  -- no ISDM available",
        colour=ReportPDF.TEAL,
    )

    pdf.body_text(
        "The has_ml_predictions boolean is TRUE when either ISDM or SDM "
        "data exists for the cell-season combination.  Raw per-source "
        "columns (isdm_*, sdm_*) are retained alongside ensembled "
        "species columns for diagnostic comparison."
    )

    # ══════════════════════════════════════════════════════════
    # 3. Current ML risk mart
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("3. Current ML Risk (fct_collision_risk_ml)")

    pdf.body_text(
        "The current ML-enhanced risk mart uses the ISDM+SDM ensemble "
        "at the (h3_cell, season) grain, producing ~7.3M rows.  "
        "It replaces the standard mart's cetacean presence and habitat "
        "suitability sub-scores with ML-derived whale probabilities."
    )

    pdf.subsection_title("3.1 Sub-score architecture (7 sub-scores)")

    pdf.metric_table(
        ["Sub-score", "Weight", "Source"],
        [
            [
                "Whale x traffic interaction",
                "30%",
                "P(any whale) x traffic_score",
            ],
            [
                "Traffic intensity",
                "15%",
                "Same as standard mart",
            ],
            [
                "Whale ML exposure",
                "15%",
                "ISDM+SDM ensemble percentiles",
            ],
            [
                "Proximity blend",
                "15%",
                "Whale/ship/strike/protection decay",
            ],
            [
                "Strike history",
                "10%",
                "67 geocoded strike cells",
            ],
            [
                "Protection gap",
                "10%",
                "MPA + speed zone tiered scoring",
            ],
            [
                "Reference risk",
                "5%",
                "Nisi et al. 1-degree grid",
            ],
        ],
        col_widths=[58, 20, 112],
    )

    pdf.callout_box(
        "No habitat sub-score",
        "Both ISDM and SDM models were trained on environmental "
        "covariates (SST, MLD, SLA, PP, depth, depth_range).  "
        "Habitat suitability is already encoded in P(whale).  "
        "Including a separate habitat sub-score would double-count "
        "these features.  The standard mart uses expert-elicited "
        "habitat; the ML mart delegates habitat to learned "
        "species distributions.",
    )

    pdf.subsection_title("3.2 Output columns")

    pdf.body_text(
        "The mart outputs 6 ensembled species columns "
        "(blue_whale_prob through minke_whale_prob), 3 composite "
        "columns (any_whale_prob, max_whale_prob, mean_whale_prob), "
        "and 10 raw diagnostic columns (4 isdm_* + 6 sdm_*) "
        "for model comparison.  Plus the 7 sub-scores, composite "
        "risk score, and risk category."
    )

    # ══════════════════════════════════════════════════════════
    # 4. What is CMIP6?
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("4. What is CMIP6?")

    pdf.body_text(
        "CMIP6 (Coupled Model Intercomparison Project, Phase 6) is "
        "the latest generation of coordinated global climate model "
        "experiments organised by the World Climate Research Programme "
        "(WCRP).  Over 100 climate models from ~50 institutions "
        "worldwide run standardised experiments under identical "
        "forcing scenarios, producing a multi-model ensemble that "
        "captures both the consensus signal and the structural "
        "uncertainty across modelling approaches."
    )

    pdf.body_text(
        "CMIP6 is the scientific backbone of the IPCC Sixth "
        "Assessment Report (AR6, 2021-2023).  Its ocean outputs "
        "-- including sea surface temperature (SST), mixed layer "
        "depth (MLD), sea surface height (SLA), and primary "
        "productivity (PP) -- are the standard reference for "
        "projecting marine ecosystem changes under climate change."
    )

    pdf.callout_box(
        "Why CMIP6 matters for whale risk",
        "Whale habitat is fundamentally driven by ocean conditions: "
        "SST controls thermal tolerance, MLD governs prey "
        "aggregation depth, SLA indicates mesoscale eddy activity "
        "that concentrates plankton, and PP determines the base "
        "of the food chain.  Our SDM and ISDM models were trained "
        "on exactly these covariates.  Projecting them forward "
        "under CMIP6 scenarios lets us ask: where will whale "
        "habitat shift, and how does that change collision risk?",
        colour=ReportPDF.ACCENT_BLUE,
    )

    pdf.subsection_title("4.1 Shared Socioeconomic Pathways (SSPs)")

    pdf.body_text(
        "CMIP6 replaces the older RCP (Representative Concentration "
        "Pathway) framework with SSPs -- narratives that combine "
        "socioeconomic development trajectories with radiative "
        "forcing levels.  The SSP label encodes both: SSP2-4.5 means "
        "'SSP2 socioeconomic pathway at 4.5 W/m2 forcing by 2100'.  "
        "We use two scenarios that bracket the plausible range:"
    )

    pdf.metric_table(
        ["Scenario", "Narrative", "Forcing", "Warming by 2100"],
        [
            [
                "SSP2-4.5",
                "Middle of the road",
                "4.5 W/m2",
                "~2.7C",
            ],
            [
                "SSP5-8.5",
                "Fossil-fuelled development",
                "8.5 W/m2",
                "~4.4C",
            ],
        ],
        col_widths=[30, 55, 35, 70],
    )

    pdf.body_text(
        "SSP2-4.5 represents a world where emissions peak around "
        "2040 and decline -- roughly consistent with current "
        "policies.  SSP5-8.5 represents continued fossil fuel "
        "expansion and is increasingly viewed as an upper bound "
        "rather than a likely outcome.  Together, they define a "
        "risk envelope: the moderate scenario shows the expected "
        "trajectory while the high scenario stress-tests resilience."
    )

    pdf.subsection_title("4.2 Multi-model ensemble")

    pdf.body_text(
        "We draw projections from a 5-model ensemble to capture "
        "inter-model structural uncertainty:"
    )

    pdf.metric_table(
        ["Model", "Institution", "Resolution"],
        [
            ["IPSL-CM6A-LR", "Institut Pierre-Simon Laplace", "~1deg ocean"],
            ["MPI-ESM1-2-LR", "Max Planck Institute", "~1deg ocean"],
            ["UKESM1-0-LL", "UK Met Office / NERC", "~1deg ocean"],
            ["GFDL-ESM4", "NOAA GFDL", "~0.5deg ocean"],
            ["NorESM2-LM", "Norwegian Earth System", "~1deg ocean"],
        ],
        col_widths=[50, 80, 60],
    )

    pdf.body_text(
        "These models span different continents, ocean model "
        "architectures, and parameterisation choices.  Using "
        "the ensemble mean (rather than any single model) "
        "reduces the influence of model-specific biases and "
        "provides a more robust central estimate."
    )

    pdf.subsection_title("4.3 Projection decades")

    pdf.metric_table(
        ["Decade", "Year range", "Planning context"],
        [
            ["2030s", "2025-2034", "Near-term: current vessel fleet lifespan"],
            ["2040s", "2035-2044", "Medium-term: shipping policy cycles"],
            ["2060s", "2055-2064", "Long-term: MPA designation horizons"],
            ["2080s", "2075-2084", "End-of-century: strategic envelope"],
        ],
        col_widths=[25, 45, 120],
    )

    pdf.body_text(
        "Decadal means (averaging over a 10-year window) smooth "
        "out interannual variability and isolate the climate trend "
        "signal.  This matches the standard IPCC reporting convention."
    )

    # ══════════════════════════════════════════════════════════
    # 5. Our covariate projection methodology
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("5. Covariate Projection Methodology")

    pdf.body_text(
        "We construct projected ocean covariates using a delta "
        "method: literature-derived CMIP6 ensemble-mean changes "
        "are applied to our observed 2019-2024 climatological "
        "baseline.  This preserves the fine-grained spatial "
        "structure of our baseline data (0.25-degree Copernicus "
        "grid) while incorporating the large-scale climate signal "
        "from the CMIP6 ensemble."
    )

    pdf.equation_box(
        "Delta method",
        "X_projected = X_baseline + delta(scenario, decade)",
        note=(
            "Additive for SST, MLD, SLA.  Multiplicative (fractional) "
            "for PP.  Baseline is the 2019-2024 seasonal climatology."
        ),
    )

    pdf.callout_box(
        "Why delta rather than raw CMIP6?",
        "Raw CMIP6 model outputs have systematic biases relative "
        "to observations (e.g. SST offsets of 1-3C in some regions). "
        "The delta method uses only the change signal from the models "
        "and applies it to the observational baseline, avoiding the "
        "need for complex bias correction.  This is the standard "
        "approach in ecological projection studies (e.g. Hazen et al. "
        "2013, Becker et al. 2019).",
        colour=ReportPDF.ACCENT_BLUE,
    )

    pdf.subsection_title("5.1 Sea surface temperature (SST)")

    pdf.body_text(
        "SST is the primary driver of whale habitat suitability "
        "in our SDM and ISDM models.  We apply latitude-dependent "
        "warming to capture polar amplification -- the well-documented "
        "phenomenon where higher latitudes warm faster than the tropics "
        "due to ice-albedo feedback and poleward heat transport."
    )

    pdf.metric_table(
        ["Latitude band", "Region", "Amplification factor"],
        [
            ["3S - 20N", "Tropical", "0.8x (less warming)"],
            ["20N - 40N", "Mid-latitude", "1.0x (baseline)"],
            ["40N - 53N", "Subpolar", "1.3x (polar amplification)"],
        ],
        col_widths=[40, 60, 90],
    )

    pdf.body_text(
        "SST deltas from IPCC AR6 WG1 Chapter 9 (Ocean, Cryosphere "
        "and Sea Level Change):"
    )

    pdf.metric_table(
        ["Decade", "SSP2-4.5", "SSP5-8.5"],
        [
            ["2030s", "+0.5C", "+0.6C"],
            ["2040s", "+0.8C", "+1.2C"],
            ["2060s", "+1.4C", "+2.5C"],
            ["2080s", "+1.8C", "+3.8C"],
        ],
        col_widths=[40, 75, 75],
    )

    pdf.small_text(
        "Deltas shown are mid-latitude baseline values before "
        "latitude amplification.  At 50N (Gulf of Maine / Alaska), "
        "multiply by 1.3x.  SST variability (sst_sd) also increases: "
        "+15% per degree C of warming, reflecting stronger thermal "
        "gradients under a warming ocean."
    )

    pdf.callout_box(
        "Ecological implication",
        "A +1.8C warming (SSP2-4.5 by 2080s) pushes isotherms "
        "poleward by roughly 200-400 km.  Species like right whale "
        "and minke -- already at the warm edge of their thermal "
        "range in the Gulf of Maine -- may see significant habitat "
        "contraction.  Conversely, species like blue whale may expand "
        "into newly suitable subpolar waters.",
        colour=ReportPDF.ACCENT_AMBER,
    )

    pdf.subsection_title("5.2 Mixed layer depth (MLD)")

    pdf.body_text(
        "MLD controls the vertical extent of the surface mixed layer "
        "where phytoplankton grow and where prey species aggregate.  "
        "Under warming, increased surface stratification leads to a "
        "shallower mixed layer, concentrating prey in a thinner "
        "layer -- potentially beneficial for lunge-feeding baleen "
        "whales in the short term, but reducing total productivity "
        "in the long term."
    )

    pdf.metric_table(
        ["Decade", "SSP2-4.5", "SSP5-8.5"],
        [
            ["2030s", "-1.0 m", "-1.5 m"],
            ["2040s", "-2.0 m", "-3.0 m"],
            ["2060s", "-4.0 m", "-6.5 m"],
            ["2080s", "-5.5 m", "-10.0 m"],
        ],
        col_widths=[40, 75, 75],
    )

    pdf.small_text(
        "Negative values = shallower MLD (more stratified).  "
        "Clamped to a minimum of 1 m.  Source: IPCC AR6 WG1 Ch9."
    )

    pdf.subsection_title("5.3 Sea level anomaly (SLA)")

    pdf.body_text(
        "SLA (sea surface height above the geoid) captures both "
        "thermal expansion and dynamic ocean circulation changes.  "
        "Mesoscale SLA variability (eddies) is a key predictor of "
        "prey concentration and whale foraging habitat."
    )

    pdf.metric_table(
        ["Decade", "SSP2-4.5", "SSP5-8.5"],
        [
            ["2030s", "+0.03 m", "+0.04 m"],
            ["2040s", "+0.06 m", "+0.08 m"],
            ["2060s", "+0.12 m", "+0.18 m"],
            ["2080s", "+0.20 m", "+0.32 m"],
        ],
        col_widths=[40, 75, 75],
    )

    pdf.small_text(
        "Additive deltas in metres.  These are dynamic sea level "
        "changes (excluding land ice contribution).  Source: IPCC "
        "AR6 WG1 Ch9."
    )

    if pdf.get_y() > 200:
        pdf.add_page()

    pdf.subsection_title("5.4 Primary productivity (PP)")

    pdf.body_text(
        "PP (depth-integrated primary production, mgC/m2/day) is "
        "the base of the marine food web.  Under warming, increased "
        "stratification reduces nutrient supply from depth, leading "
        "to a global decline in primary productivity.  We apply a "
        "fractional change (multiplicative delta) rather than an "
        "additive one because PP scales differently across regions."
    )

    pdf.metric_table(
        ["Decade", "SSP2-4.5", "SSP5-8.5"],
        [
            ["2030s", "-2%", "-3%"],
            ["2040s", "-3%", "-5%"],
            ["2060s", "-5%", "-10%"],
            ["2080s", "-7%", "-16%"],
        ],
        col_widths=[40, 75, 75],
    )

    pdf.small_text(
        "Fractional change relative to baseline.  Clamped to "
        "minimum of zero.  Source: Kwiatkowski et al. (2020) and "
        "IPCC AR6 WG1 Ch5."
    )

    pdf.callout_box(
        "Cascading food-web effects",
        "A 16% decline in PP (SSP5-8.5 by 2080s) propagates up "
        "the food web with roughly 10:1 trophic transfer ratios.  "
        "This could substantially reduce prey availability for "
        "baleen whales, even in regions where thermal conditions "
        "remain suitable.  Our SDMs capture this indirectly via "
        "the PP input feature.",
        colour=ReportPDF.ACCENT_RED,
    )

    # ══════════════════════════════════════════════════════════
    # 6. Pipeline architecture
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("6. Projection Pipeline Architecture")

    pdf.body_text(
        "The end-to-end projection pipeline has four stages, "
        "each implemented as a separate script following the "
        "project's ingestion/analysis/database conventions:"
    )

    pdf.subsection_title("Stage 1: Covariate generation")

    pdf.body_text(
        "download_cmip6_projections.py first attempts to download "
        "raw CMIP6 monthly data from the Copernicus Climate Data "
        "Store (CDS) via the cdsapi Python client.  If CDS access "
        "is unavailable, it falls back to the delta method described "
        "above, applying published ensemble-mean deltas to the "
        "observational 2019-2024 baseline."
    )

    pdf.body_text(
        "For CDS downloads, the pipeline requests monthly fields "
        "for 5 CMIP6 models, computes ensemble means, regrids to "
        "the observational 0.25-degree grid using nearest-neighbour "
        "interpolation, and computes climatological seasonal means "
        "(same as the existing ocean covariates pipeline).  Output: "
        "~2.9M rows in cmip6_projections.parquet."
    )

    pdf.subsection_title("Stage 2: SDM scoring")

    pdf.body_text(
        "score_future_sdm.py loads the trained seasonal XGBoost "
        "SDMs from the MLflow file store and scores them on the "
        "projected covariates.  For each (scenario, decade):"
    )

    pdf.numbered_item(
        1,
        "Load projected ocean covariates (SST, MLD, SLA, PP, sst_sd) "
        "for the target scenario and decade.",
    )
    pdf.numbered_item(
        2,
        "Spatial-join projected covariates to H3 cells using a "
        "cKDTree nearest-neighbour lookup (same pattern as the "
        "existing ocean covariate intermediate model).",
    )
    pdf.numbered_item(
        3,
        "Merge with static features (bathymetry, proximity, "
        "season indicators) that don't change under projection.",
    )
    pdf.numbered_item(
        4,
        "Score all 7 target columns (any, blue, fin, humpback, "
        "sperm, right, minke) using predict_proba.",
    )
    pdf.numbered_item(
        5,
        "Save per-species parquets to sdm_projections/ directory.  "
        "load_sdm_projections.py merges them into the "
        "whale_sdm_projections PostGIS table (58.1M rows).",
    )

    pdf.body_text(
        "About 49% of H3 cells lack projected ocean covariate "
        "data (deep ocean or grid-edge cells).  These are filled "
        "with median values -- the same approach used for current "
        "covariates, documented as a known pipeline characteristic."
    )

    pdf.subsection_title("Stage 3: ISDM scoring")

    pdf.body_text(
        "train_isdm_model.py with --score-grid scores the 4 ISDM "
        "models (blue, fin, humpback, sperm) on the same projected "
        "covariates.  Output: 4-species probability surfaces stored "
        "in whale_isdm_projections table (58.1M rows).  ISDM uses "
        "only 7 environmental covariates (no bathymetry or proximity), "
        "so the feature matrix construction is simpler."
    )

    pdf.subsection_title("Stage 4: Risk assembly (dbt)")

    pdf.body_text(
        "fct_collision_risk_ml_projected.sql INNER JOINs the ISDM "
        "and SDM projection tables on (h3_cell, season, scenario, "
        "decade), computes the 6-species ensemble, calculates 6 "
        "sub-scores via weighted_risk_score('ml_projected'), and "
        "assigns risk categories.  The INNER JOIN ensures cells only "
        "appear if they have at least one whale prediction -- cells "
        "with no projected whale presence have near-zero interaction "
        "risk and can be safely excluded."
    )

    pdf.subsection_title("6.1 Scale")

    pdf.body_text(
        "The full projection matrix is: 1.8M H3 cells x 4 seasons "
        "x 2 scenarios x 4 decades = ~58M rows.  Each row contains "
        "6 ensembled species probabilities, 3 composites, 7 raw "
        "model columns, and 6 sub-scores plus the composite risk "
        "score and category."
    )

    # ══════════════════════════════════════════════════════════
    # 7. Projected risk scoring
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("7. Projected Risk Scoring (fct_collision_risk_ml_projected)")

    pdf.subsection_title("7.1 Why no proximity sub-score?")

    pdf.body_text(
        "The proximity sub-score in the current risk mart is derived "
        "from spatial distances to observed whale sightings, ship "
        "strike locations, and protection boundaries.  Under future "
        "projections, whale sighting and strike locations do not exist "
        "-- we cannot know where future sightings will occur.  "
        "Including the current proximity field would anchor projected "
        "risk to today's observation pattern, defeating the purpose "
        "of projection."
    )

    pdf.callout_box(
        "Design decision",
        "Proximity is dropped from projected risk.  The remaining "
        "6 sub-score weights are renormalised by dividing by "
        "(1 - 0.15) = 0.85 so that relative proportions among "
        "the remaining sub-scores are preserved.",
        colour=ReportPDF.ACCENT_GREEN,
    )

    pdf.subsection_title("7.2 Weight renormalisation")

    pdf.body_text(
        "Current ML mart weights sum to 1.0 across 7 sub-scores "
        "(proximity = 0.15).  For the projected mart, we divide each "
        "remaining weight by 0.85:"
    )

    pdf.metric_table(
        ["Sub-score", "Current wt", "Projected wt", "Formula"],
        [
            [
                "Whale x traffic",
                "0.30",
                "0.3529",
                "0.30 / 0.85",
            ],
            [
                "Traffic intensity",
                "0.15",
                "0.1765",
                "0.15 / 0.85",
            ],
            [
                "Whale ML exposure",
                "0.15",
                "0.1765",
                "0.15 / 0.85",
            ],
            [
                "Strike history",
                "0.10",
                "0.1176",
                "0.10 / 0.85",
            ],
            [
                "Protection gap",
                "0.10",
                "0.1176",
                "0.10 / 0.85",
            ],
            [
                "Reference risk",
                "0.05",
                "0.0588",
                "0.05 / 0.85",
            ],
        ],
        col_widths=[50, 30, 35, 75],
    )

    pdf.equation_box(
        "Weight renormalisation",
        "w_projected_i = w_current_i / (1 - w_proximity)",
        note=(
            "Preserves the relative ranking of all non-proximity "
            "sub-scores.  Sum of projected weights = 1.0."
        ),
    )

    pdf.subsection_title("7.3 Static inputs under projection")

    pdf.body_text(
        "Several sub-scores use inputs that are inherently "
        "present-day: strike history (67 observed incidents), "
        "protection gap (current MPA/SMA boundaries), reference "
        "risk (Nisi 2024 grid), and traffic intensity (observed AIS).  "
        "These are held constant across all projected decades."
    )

    pdf.callout_box(
        "Assumption",
        "Traffic patterns, regulatory zones, and strike history are "
        "assumed static under projection.  Only whale habitat "
        "probabilities vary with climate scenario.  This is a "
        "conservative modelling choice -- in reality, both shipping "
        "routes and MPA boundaries may change.  Future work could "
        "incorporate projected shipping growth scenarios.",
        colour=ReportPDF.ACCENT_AMBER,
    )

    # ══════════════════════════════════════════════════════════
    # 8. SQL architecture
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("8. SQL Architecture")

    pdf.subsection_title("8.1 fct_collision_risk_ml (current)")

    pdf.body_text(
        "The current ML mart follows the standard seasonal pattern: "
        "seasons CTE generates the 4 season names, grid_seasons "
        "cross-joins with int_hex_grid to produce 7.3M rows, then "
        "features CTE LEFT JOINs 14 intermediate models.  "
        "The key addition is the dual join to both "
        "int_ml_whale_predictions (ISDM) and "
        "int_sdm_whale_predictions (SDM), with CASE expressions "
        "computing per-species ensemble values."
    )

    pdf.body_text(
        "Sub-scores are computed via the weighted_risk_score('ml') "
        "macro, which reads the 7 risk_ml_weight_* vars from "
        "dbt_project.yml.  Percentile ranking uses "
        "PARTITION BY season for season-relative scores."
    )

    pdf.subsection_title("8.2 fct_collision_risk_ml_projected")

    pdf.body_text(
        "The projected mart has a different structure because its "
        "grain includes (scenario, decade) in addition to "
        "(h3_cell, season).  It INNER JOINs whale_isdm_projections "
        "and whale_sdm_projections directly (not via intermediate "
        "models), then LEFT JOINs the static current-period "
        "intermediate models for traffic, strike, protection gap, "
        "and reference risk."
    )

    pdf.body_text(
        "The INNER JOIN means cells only appear in the projected "
        "mart if they have at least one whale habitat prediction.  "
        "This is appropriate because cells with no projected whale "
        "presence have near-zero interaction risk."
    )

    pdf.body_text(
        "Sub-scores use weighted_risk_score('ml_projected'), "
        "which reads the 6 risk_ml_projected_weight_* vars.  "
        "Percentile ranking uses PARTITION BY season, scenario, "
        "decade so scores are relative within each projection slice."
    )

    pdf.subsection_title("8.3 weighted_risk_score macro")

    pdf.body_text(
        "The macro accepts a mode parameter ('standard', 'ml', or "
        "'ml_projected') and generates the weighted sum expression.  "
        "This ensures weight changes in dbt_project.yml automatically "
        "propagate to all three mart variants without manual SQL edits."
    )

    # ══════════════════════════════════════════════════════════
    # 9. API & frontend integration
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("9. API & Frontend Integration")

    pdf.subsection_title("9.1 Backend endpoints")

    pdf.body_text(
        "The projected risk data is served by three API endpoints "
        "in the layers route module:"
    )

    pdf.metric_table(
        ["Endpoint", "Description"],
        [
            [
                "GET /layers/sdm-projections",
                "Projected whale habitat (scenario + decade filter)",
            ],
            [
                "GET /layers/sdm-projections/summary",
                "Summary stats across scenarios/decades",
            ],
            [
                "GET /risk/ml",
                "Current ML risk with ensemble species",
            ],
            [
                "GET /risk/ml/{h3_cell}",
                "Cell detail with 6 ensembled + 10 raw cols",
            ],
            [
                "GET /risk/compare",
                "Standard vs ML side-by-side comparison",
            ],
        ],
        col_widths=[65, 125],
    )

    pdf.subsection_title("9.2 Frontend layers")

    pdf.body_text("The frontend dashboard supports two projection-related layers:")

    pdf.bullet(
        "sdm_projections: Renders CMIP6-projected whale habitat "
        "probabilities with amber color ramp.  Users select scenario "
        "(SSP2-4.5 or SSP5-8.5) and decade (2030s-2080s) via sidebar "
        "controls.  Uses the same dual-resolution rendering as other "
        "layers (heatmap zoomed out, H3 hexagons zoomed in)."
    )
    pdf.bullet(
        "risk_ml: Renders the ML-enhanced collision risk with "
        "ISDM+SDM ensemble species probabilities.  Cell detail panel "
        "shows all 6 ensembled species, 3 composites, and 10 raw "
        "diagnostic columns for ISDM/SDM comparison."
    )

    # ══════════════════════════════════════════════════════════
    # 10. Data inventory
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("10. Data Inventory")

    pdf.subsection_title("10.1 Source tables")

    pdf.metric_table(
        ["Table", "Rows", "Description"],
        [
            [
                "whale_isdm_projections",
                "58.1M",
                "ISDM projected (4 species)",
            ],
            [
                "whale_sdm_projections",
                "58.1M",
                "SDM projected (7 species)",
            ],
            [
                "ml_whale_predictions",
                "7.3M",
                "ISDM current (4 species)",
            ],
            [
                "ml_sdm_predictions",
                "7.3M",
                "SDM current (7 species, OOF)",
            ],
        ],
        col_widths=[55, 25, 110],
    )

    pdf.subsection_title("10.2 Output marts")

    pdf.metric_table(
        ["Mart", "Rows", "Grain", "Sub-scores"],
        [
            [
                "fct_collision_risk_ml",
                "7.3M",
                "(h3_cell, season)",
                "7",
            ],
            [
                "fct_collision_risk_ml_projected",
                "58M",
                "(h3_cell, season, scenario, decade)",
                "6",
            ],
        ],
        col_widths=[60, 20, 75, 35],
    )

    pdf.subsection_title("10.3 Key artefacts")

    pdf.metric_table(
        ["Path", "Content"],
        [
            [
                "data/raw/cmip6/",
                "CMIP6 projected covariates (parquet)",
            ],
            [
                "data/processed/ml/isdm_predictions/",
                "4 ISDM grid-scored parquets (~53 MB each)",
            ],
            [
                "data/processed/ml/sdm_projections/",
                "Per-species x scenario x decade parquets",
            ],
        ],
        col_widths=[70, 120],
    )

    # ══════════════════════════════════════════════════════════
    # 11. Challenges & solutions
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("11. Challenges & Solutions")

    challenges = [
        (
            "Delta interpretability",
            "Using ISDM-only for current risk but ISDM+SDM for projected "
            "risk would make the delta uninterpretable -- model "
            "differences would be conflated with climate signal.  "
            "Solution: ensemble both marts consistently.",
        ),
        (
            "Proximity under projection",
            "Proximity decay scores are derived from observed sighting "
            "and strike locations.  These locations don't exist for "
            "future decades.  Solution: drop proximity from projected "
            "risk and renormalise weights.",
        ),
        (
            "Right whale & minke coverage",
            "ISDM (Nisi et al.) only covers 4 species, missing right "
            "whale and minke.  Solution: SDM-only predictions for "
            "these two species within the ensemble framework.",
        ),
        (
            "58M row scale",
            "The projected mart (1.8M cells x 4 seasons x 2 scenarios "
            "x 4 decades) produces ~58M rows.  Percentile ranking with "
            "PARTITION BY season, scenario, decade must process large "
            "windows.  Solution: max_parallel_workers_per_gather = 0 "
            "and work_mem = 128MB to avoid Docker OOM.",
        ),
        (
            "COALESCE vs CASE for ensemble",
            "Simple avg(ISDM, SDM) returns NULL if either is NULL.  "
            "For shared species where one model has predictions but "
            "the other doesn't for a given cell, we need graceful "
            "fallback.  Solution: CASE WHEN ... pattern that averages "
            "when both exist, falls back to whichever is available.",
        ),
    ]

    for title, detail in challenges:
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.subsection_title(title)
        pdf.body_text(detail)

    # ══════════════════════════════════════════════════════════
    # 12. Key takeaways
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("12. Key Takeaways")

    takeaways = [
        (
            "Consistent methodology enables clean deltas.",
            "Both current and projected risk use ISDM+SDM ensemble, "
            "so risk changes between decades can be cleanly attributed "
            "to climate signal rather than model choice differences.",
        ),
        (
            "6-species ensemble broadens coverage.",
            "Adding right whale and minke (SDM-only) to the 4 ISDM "
            "species provides comprehensive whale hazard coverage.  "
            "The any_whale composite over 6 species better captures "
            "true collision risk than the previous 4-species version.",
        ),
        (
            "Proximity is correctly excluded from projections.",
            "Sighting/strike proximity is inherently observational.  "
            "Projecting it forward would anchor future risk to current "
            "observation patterns, defeating climate projection.",
        ),
        (
            "Weight renormalisation preserves relative importance.",
            "Dividing by (1 - w_proximity) ensures the 6 projected "
            "sub-scores maintain the same relative ranking as the 7 "
            "current sub-scores, just without proximity.",
        ),
        (
            "Static inputs are a conservative choice.",
            "Traffic patterns, protection zones, and strike history "
            "are held constant under projection.  Only whale habitat "
            "varies with climate.  This isolates the climate signal "
            "but understates total future risk change.",
        ),
        (
            "CASE-based ensemble handles missing data gracefully.",
            "Where ISDM or SDM predictions are unavailable for a "
            "specific cell-season, the ensemble falls back to "
            "whichever source is available rather than returning NULL.",
        ),
        (
            "58M rows require careful PostGIS tuning.",
            "max_parallel_workers_per_gather = 0 and work_mem = 128MB "
            "prevent Docker shared memory OOM during the large "
            "window functions in the projected mart.",
        ),
        (
            "Raw diagnostic columns enable model comparison.",
            "Both isdm_* and sdm_* raw columns are retained alongside "
            "the ensembled species columns, allowing comparison of "
            "the two model families at any cell-season.",
        ),
    ]

    for i, (title, detail) in enumerate(takeaways, 1):
        if pdf.get_y() > 248:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*ReportPDF.TEAL)
        pdf.cell(8, 6, f"{i}.")
        pdf.set_text_color(*ReportPDF.NAVY)
        pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(18)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*ReportPDF.DARK_TEXT)
        pdf.multi_cell(172, 5, detail)
        pdf.ln(3)

    # ── Output ────────────────────────────────────────────────
    pdf.output(str(OUTPUT_FILE))
    print(f"PDF saved to {OUTPUT_FILE}")
    print(f"  Pages: {pdf.page_no()}")


if __name__ == "__main__":
    build_report()

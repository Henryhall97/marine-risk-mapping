"""Generate IWC SDM / Abundance-Estimation Alignment PDF.

Assesses how the Marine Risk Mapping species-distribution-modelling (SDM)
stack fits alongside (and differs from) the IWC Scientific Committee
guidance on model-based abundance estimation:

    Miller, D.L. & Kelly, N. (2023). "Guidelines for model-based
    estimation." SC/69A/ASI/20, IWC Scientific Committee, Bled, May 2023.

    Kelly, N. (2023). "History of work towards updating the IWC's
    'Requirements and Guidelines for Conducting Surveys and Analysing
    Data within the Revised Management Scheme'." SC/69A/ASI/21.

This report is the deliberate companion to ``iwc_strike_risk_alignment``
and reuses its visual language. It covers:
  1. OVERLAP    - where our SDM stack already aligns with the guidance.
  2. ISSUES     - where our approach diverges or falls short.
  3. MIGRATION  - a concrete path to guidance-compatible reporting.
  4. IMPROVEMENT- a prioritised, phased work plan.
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs" / "modelling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "iwc_sdm_alignment.pdf"


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
                "Marine Risk Mapping -- IWC SDM & Abundance-Estimation Alignment",
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
            self.set_font("Helvetica", "B", 16)
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
            # Page-break guard
            if self.get_y() > 270:
                self.add_page()
                self.set_fill_color(*self.NAVY)
                self.set_text_color(*self.WHITE)
                self.set_font("Helvetica", "B", 9)
                for w, h_text in zip(col_widths, headers, strict=False):
                    self.cell(w, 7, f"  {h_text}", fill=True)
                self.ln()
                self.set_font("Helvetica", "", body_font)
            # Compute wrapped row height
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

    def callout_box(self, title, text, colour=None):
        if colour is None:
            colour = self.ACCENT_BLUE
        self.set_font("Helvetica", "", 9.5)
        n_lines = max(1, len(text) // 88 + text.count("\n") + 1)
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

    def equation_box(self, label, equation, note=None):
        box_h = 22 if note is None else 30
        if self.get_y() + box_h > 278:
            self.add_page()
        y = self.get_y()
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


# ═══════════════════════════════════════════════════════════════════
# Report content
# ═══════════════════════════════════════════════════════════════════


def build_report():  # noqa: C901 PLR0915
    pdf = ReportPDF("P", "mm", "A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Title page ────────────────────────────────────────────────
    pdf.add_page()
    pdf.ln(32)
    pdf.set_font("Helvetica", "B", 25)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(
        0,
        13,
        "Aligning With the IWC",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        13,
        "Abundance & SDM Guidance",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        9,
        "Overlap, Gaps, Migration & Improvement Plan",
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
            "An assessment of how the Marine Risk Mapping species-"
            "distribution-modelling (SDM) stack fits alongside the IWC "
            "Scientific Committee guidance on model-based abundance "
            "estimation -- Miller & Kelly (2023), 'Guidelines for model-"
            "based estimation' (SC/69A/ASI/20), and its history paper "
            "SC/69A/ASI/21. Companion to the strike-risk alignment report."
        ),
        align="C",
    )
    pdf.ln(10)
    pdf.stat_boxes(
        [
            ("10", "Overlaps found"),
            ("11", "Gaps identified"),
            ("4", "Migration phases"),
        ]
    )
    pdf.ln(2)
    pdf.stat_boxes(
        [
            ("12", "SDM models"),
            ("6", "Species modelled"),
            ("47", "Env. features"),
        ]
    )
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5,
        (
            "Prepared by the Marine Risk Mapping project. This document "
            "reads as a pair with 'Aligning With the IWC Strike-Risk "
            "Reporting Standard': abundance/SDM is the exposure layer that "
            "feeds the strike-risk encounter-rate chain, so the two "
            "migration plans are designed to dovetail."
        ),
        align="C",
    )

    # ── 1. Executive summary ──────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1.  Executive Summary")
    pdf.body_text(
        "The IWC guidance describes how to obtain defensible, absolute "
        "abundance and density estimates (with rigorous uncertainty) from "
        "designed distance-sampling line-transect surveys, using model-"
        "based 'density surface models' (DSMs) as a generalisation of the "
        "classical design-based Horvitz-Thompson estimator. Its purpose is "
        "management-grade abundance for the Revised Management Procedure: "
        "every modelling decision must be documented so the Committee can "
        "judge an estimate's 'acceptability'."
    )
    pdf.body_text(
        "Marine Risk Mapping builds species-distribution models with a "
        "different purpose: fine-grained, coast-wide RELATIVE habitat "
        "suitability and occurrence probability, used to drive a collision-"
        "risk screening and public-engagement product. We use gradient-"
        "boosted trees (XGBoost) on opportunistic OBIS presence data, an "
        "integrated SDM (ISDM) trained on the Nisi et al. (2024) expert "
        "dataset, spatial block cross-validation, a two-source ensemble, "
        "and CMIP6 climate projections -- on a ~1.2 km H3 grid."
    )
    pdf.callout_box(
        "Bottom line",
        "The two efforts are complementary, not competing. The guidance is "
        "an abundance-estimation standard for designed surveys; we are a "
        "relative-suitability screening layer built from opportunistic and "
        "expert data. We already honour several of its principles (spatial "
        "validation, covariate-driven prediction, explicit detection-bias "
        "handling, full decision documentation). The main gaps are absolute "
        "density, calibrated uncertainty (CV) maps, and effort/detection "
        "correction. A four-phase plan closes them where it adds value "
        "without abandoning coast-wide coverage.",
        ReportPDF.TEAL,
    )

    # ── 2. The IWC guidance in brief ──────────────────────────────
    pdf.section_title("2.  The IWC Guidance in Brief")
    pdf.body_text(
        "The guidance modernises the RMP survey 'Requirements and "
        "Guidelines' to admit model-based estimation alongside design-"
        "based analysis. The recommended vehicle is the density surface "
        "model (DSM), a two-stage workflow."
    )
    pdf.subsection_title("Stage 1 -- Detection function (detectability)")
    pdf.body_text(
        "Distance sampling fits a detection function g(y) to perpendicular "
        "distances, giving the probability p that an animal within the "
        "truncation half-width w is detected. This corrects counts for "
        "imperfect detectability (and, with mark-recapture distance "
        "sampling, for availability and perception bias / g(0))."
    )
    pdf.equation_box(
        "Effective effort-corrected count per segment i",
        "n_i / (p * a_i),   a_i = 2 * w * L_i",
        "n_i = animals seen on segment i; a_i = covered area (transect "
        "length L_i x effective strip 2w); p from the detection function.",
    )
    pdf.subsection_title("Stage 2 -- Spatial density surface (GAM)")
    pdf.body_text(
        "A generalised additive model (the 'dsm' / 'mgcv' R stack) relates "
        "the effort-corrected counts to environmental and spatial smooth "
        "terms, with the covered area as an offset; integrating the fitted "
        "density surface over a prediction grid yields abundance."
    )
    pdf.equation_box(
        "Density surface and abundance",
        "E[n_i] = A_i * exp( b0 + Sum_k f_k(z_ik) + s(x_i, y_i) )",
        "f_k = smooth functions of covariates z (SST, depth, ...); "
        "s(x,y) = spatial smooth; N_hat = Sum_g A_g * D_hat_g over grid "
        "cells g.",
    )
    pdf.subsection_title("Cross-cutting requirements")
    pdf.bullet(
        "Uncertainty is mandatory: a coefficient of variation (CV) must "
        "accompany every estimate, propagating both detection-function and "
        "GAM variance (delta method or bootstrap)."
    )
    pdf.bullet(
        "Coverage probability and randomisation underpin design-based "
        "validity; model-based methods can reduce bias from uneven "
        "coverage but must be assessed, not assumed."
    )
    pdf.bullet(
        "Extrapolation beyond the surveyed area or the covariate envelope "
        "is a named pitfall -- predictions there must be flagged."
    )
    pdf.bullet(
        "Diagnostics: residual checks, basis-dimension / smoothness checks, "
        "spatial autocorrelation, and the 'ltdesigntester' tool for judging "
        "whether a simple design-based estimate is even appropriate."
    )
    pdf.bullet(
        "'Acceptability' = thorough documentation of every design and "
        "analysis decision and its rationale, so reviewers can reproduce "
        "and judge the estimate."
    )

    # ── 3. Our current SDM approach ───────────────────────────────
    pdf.section_title("3.  Our Current SDM Approach")
    pdf.body_text("For context, our stack (summarised before the gap analysis):")
    pdf.bullet(
        "OBIS SDM: XGBoost binary classifier, presence = 'has this H3 cell "
        "ever recorded a cetacean sighting', background = all other cells. "
        "~47 environmental + spatial features; ~4% positive rate handled "
        "via scale_pos_weight."
    )
    pdf.bullet(
        "ISDM: per-species XGBoost trained on Nisi et al. (2024) curated "
        "presence / expert pseudo-absence (blue, fin, humpback, sperm) on "
        "seven ocean covariates (SST, SST sd, MLD, SLA, PP, depth, depth "
        "range)."
    )
    pdf.bullet(
        "Ensemble: avg(ISDM, SDM) for the four shared species; SDM-only "
        "for right and minke whales (not in Nisi). Composites: "
        "P(any whale) = 1 - prod(1 - P_i)."
    )
    pdf.bullet(
        "Validation: spatial block CV (H3 res-2 parents, ~158 km blocks, "
        "5 folds) so all seasons of a cell share a fold -- honest out-of-"
        "sample AUC / AP, with calibration and SHAP diagnostics."
    )
    pdf.bullet(
        "Detection-bias controls: traffic features and whale-proximity "
        "features are deliberately EXCLUDED from whale SDMs (survey effort "
        "correlates with shipping lanes; proximity leaks the target)."
    )
    pdf.bullet(
        "Seasonal SDMs and CMIP6-projected SDMs (SSP2-4.5 / SSP5-8.5, "
        "2030s-2080s) extend the surface in time."
    )

    # ── 4. Overlap ────────────────────────────────────────────────
    pdf.section_title("4.  Overlap -- Where We Already Align")
    pdf.body_text(
        "Ten places where our SDM stack already embodies the spirit (and "
        "often the letter) of the guidance."
    )
    overlap_rows = [
        (
            "Model-based spatial prediction",
            "Guidance promotes model-based density surfaces over a grid; we "
            "produce a model-based suitability surface over an H3 grid.",
        ),
        (
            "Environmental covariates",
            "DSMs use SST, depth, productivity etc.; our SDM/ISDM use the "
            "same Copernicus + GEBCO covariates (SST, MLD, SLA, PP, depth).",
        ),
        (
            "Honest spatial validation",
            "Guidance warns against optimistic in-sample fit; we use spatial "
            "block CV (res-2 blocks) so neighbouring cells never leak across "
            "train/test.",
        ),
        (
            "Detection / effort-bias awareness",
            "Detectability is central to the guidance; we explicitly drop "
            "traffic + proximity features to avoid encoding survey effort "
            "into the whale signal.",
        ),
        (
            "Extrapolation caution",
            "Guidance names extrapolation as a pitfall; we restrict to the "
            "US study bbox and log/median-fill cells lacking covariates "
            "rather than predict blindly.",
        ),
        (
            "Multiple data sources",
            "Guidance values combining survey, tagging and sightings; our "
            "ISDM is built on Nisi's integrated sighting+tag+whaling+survey "
            "dataset, blended with OBIS.",
        ),
        (
            "Model averaging / ensemble",
            "Miller's DSM work supports multiple detection functions / model "
            "averaging; we ensemble ISDM + OBIS SDM per species.",
        ),
        (
            "Temporal stratification",
            "Guidance supports stratifying by period; we fit season-varying "
            "SDMs (winter/spring/summer/fall) on a seasonal grid.",
        ),
        (
            "Per-species modelling",
            "Abundance is estimated per stock/species; we train per-species "
            "targets (right, humpback, fin, blue, sperm, minke).",
        ),
        (
            "Decision documentation",
            "'Acceptability' = documenting every choice; our repo "
            "instructions, model cards and PDF reports record feature "
            "exclusions, CV design and rationale.",
        ),
    ]
    pdf.metric_table(
        ["Guidance principle", "How Marine Risk Mapping already meets it"],
        overlap_rows,
        col_widths=[58, 132],
        body_font=8.5,
    )

    # ── 5. Issues / gaps ──────────────────────────────────────────
    pdf.section_title("5.  Gaps -- Where We Diverge")
    pdf.body_text(
        "Eleven divergences. Most stem from a single root cause: our inputs "
        "are opportunistic presence data, not designed distance-sampling "
        "surveys -- so the absolute-abundance machinery the guidance "
        "assumes is not directly available to us."
    )
    gap_rows = [
        (
            "No detection function",
            "We treat a sighting as presence with no g(y), no g(0), no "
            "availability/perception correction. Detectability is "
            "unmodelled.",
            "High",
        ),
        (
            "Relative, not absolute",
            "Output is a 0-1 suitability/occurrence score, not animals per "
            "km^2 or an abundance N. Cannot feed RMP/CLA directly.",
            "High",
        ),
        (
            "No uncertainty / CV maps",
            "Guidance mandates a CV per estimate; we report AUC/AP but no "
            "per-cell prediction variance or CV surface.",
            "High",
        ),
        (
            "No design-based foundation",
            "OBIS lacks randomised trackline placement and estimable "
            "coverage probability -- the statistical basis for unbiased "
            "density is absent.",
            "High",
        ),
        (
            "Naive pseudo-absence",
            "'Cell with no sighting = absence' conflates true absence with "
            "unsurveyed area -- exactly the coverage problem the guidance "
            "targets.",
            "High",
        ),
        (
            "No effort layer",
            "We have no survey-effort surface to offset by; presence "
            "probability is confounded with observation intensity.",
            "Med",
        ),
        (
            "Tree model vs GAM",
            "XGBoost gives no explicit, inspectable smooth terms, no spatial "
            "smooth s(x,y), and no basis-dimension diagnostics as in mgcv.",
            "Med",
        ),
        (
            "No spatial residual checks",
            "We lack variograms / Moran's I on residuals to confirm spatial "
            "autocorrelation is captured.",
            "Med",
        ),
        (
            "No formal extrapolation metric",
            "Bbox + median-fill is ad hoc; no ExDet / MESS-style covariate-"
            "envelope flag travels with each prediction.",
            "Med",
        ),
        (
            "No group size / availability",
            "Group-size estimation and availability bias (dive cycles) are "
            "not modelled; relevant for deep divers (sperm whale).",
            "Med",
        ),
        (
            "Terminology mismatch",
            "We say 'SDM probability'; the guidance speaks in density, "
            "abundance, CV, coverage, detection -- needs an explicit "
            "crosswalk for reviewers.",
            "Low",
        ),
    ]
    pdf.metric_table(
        ["Gap", "Description", "Sev."],
        gap_rows,
        col_widths=[42, 130, 18],
        body_font=8.5,
    )

    # ── 6. Terminology crosswalk ──────────────────────────────────
    pdf.section_title("6.  Terminology & Method Crosswalk")
    pdf.body_text(
        "A reviewer fluent in the guidance can map our components onto "
        "theirs with this table."
    )
    cross_rows = [
        ("Density surface D(s)", "SDM suitability / P(occurrence) per cell"),
        ("Abundance N_hat", "(not produced) -- relative exposure only"),
        ("Detection function g(y)", "(none) -- presence taken at face value"),
        (
            "g(0) / availability",
            "(none) -- partially proxied by excluding effort-correlated features",
        ),
        ("Effort offset A_i", "(none) -- no survey-effort surface"),
        ("Coverage probability", "(n/a) -- opportunistic, non-randomised"),
        ("CV(N_hat)", "(none) -- AUC/AP + calibration instead"),
        ("Spatial smooth s(x,y)", "Lat/lon features + spatial block CV"),
        ("GAM smooths f_k(z)", "XGBoost trees + SHAP partial effects"),
        ("Prediction grid", "H3 res-7 (~1.2 km) cells, US study area"),
        ("Extrapolation flag", "Bbox clip + median-fill of missing covars"),
        ("Integrated estimation", "ISDM on Nisi multi-source dataset"),
    ]
    pdf.metric_table(
        ["IWC guidance term", "Marine Risk Mapping equivalent"],
        cross_rows,
        col_widths=[70, 120],
        body_font=8.5,
    )

    # ── 7. Migration & improvement plan ───────────────────────────
    pdf.section_title("7.  Migration & Improvement Plan")
    pdf.body_text(
        "Four phases, ordered by effort-to-value and designed to interlock "
        "with the strike-risk migration plan (the SDM surface is its "
        "exposure term)."
    )

    pdf.subsection_title("Phase 1 -- Framing & documentation (low effort)")
    pdf.numbered_item(
        1,
        "Re-label outputs unambiguously as 'relative occurrence "
        "probability / habitat suitability', NOT density or abundance, in "
        "the API, frontend legend and reports.",
    )
    pdf.numbered_item(
        2,
        "Publish a model card / acceptability-style report for each SDM "
        "against the Miller & Kelly checklist (data, covariates, CV, "
        "assumptions, known biases, intended use).",
    )
    pdf.numbered_item(
        3,
        "Attach an extrapolation flag to every prediction: an ExDet / "
        "MESS-style covariate-envelope distance, surfaced as a 'low-"
        "confidence / extrapolated' overlay.",
    )

    pdf.subsection_title("Phase 2 -- Calibrated uncertainty (medium effort)")
    pdf.numbered_item(
        1,
        "Produce per-cell uncertainty: quantile / bootstrap ensembles of "
        "the XGBoost SDM to emit a prediction interval and a CV-analogue "
        "surface alongside the point estimate.",
    )
    pdf.numbered_item(
        2,
        "Add spatial residual diagnostics to evaluate.py: variograms and "
        "Moran's I on out-of-fold residuals to confirm spatial structure "
        "is captured.",
    )
    pdf.numbered_item(
        3,
        "Expose the uncertainty layer in the map UI so risk consumers see "
        "where the SDM is and is not trustworthy -- mirrors the strike "
        "plan's Monte-Carlo CV maps.",
    )

    pdf.subsection_title("Phase 3 -- Toward density (higher effort)")
    pdf.numbered_item(
        1,
        "Where designed line-transect data exist (NARWSS, AMAPPS, SEFSC "
        "shipboard/aerial surveys), fit a proper DSM: mrds detection "
        "function + mgcv spatial GAM, as a parallel 'effort-corrected "
        "density' product.",
    )
    pdf.numbered_item(
        2,
        "Calibrate the ML suitability surface against DSM density in "
        "overlapping regions, so the relative score has a defensible link "
        "to animals per km^2.",
    )
    pdf.numbered_item(
        3,
        "Clearly separate the two layers in the platform: opportunistic "
        "suitability (coast-wide) vs effort-corrected density (survey "
        "footprints), each labelled with its provenance.",
    )

    pdf.subsection_title("Phase 4 -- Integrated, RMP-grade (research)")
    pdf.numbered_item(
        1,
        "Move to a true integrated SDM / point-process model that jointly "
        "uses presence-only OBIS, designed surveys and tagging -- the Nisi "
        "et al. (2024) paradigm -- to estimate absolute density with CV.",
    )
    pdf.numbered_item(
        2,
        "Model availability (dive-cycle) bias for deep divers and group "
        "size where data allow, closing the perception/availability gap.",
    )
    pdf.numbered_item(
        3,
        "Propagate the resulting density + CV through the strike-risk "
        "encounter-rate chain by Monte Carlo, so collision-risk maps carry "
        "honest uncertainty end-to-end (joins Phase 4 of the strike plan).",
    )

    # ── 8. Key takeaways ──────────────────────────────────────────
    pdf.section_title("8.  Key Takeaways")
    takeaways = [
        "The guidance is an absolute-abundance standard for designed "
        "surveys; we are a relative-suitability screening layer from "
        "opportunistic + expert data. Different jobs, compatible methods.",
        "We already satisfy several core principles: spatial validation, "
        "covariate-driven prediction, explicit detection-bias handling, "
        "multi-source integration, and full decision documentation.",
        "Our biggest, honest gaps are absolute density, calibrated CV "
        "maps, and effort/detection correction -- all traceable to "
        "opportunistic, non-randomised input data.",
        "The cheapest, highest-value moves are Phase 1-2: precise framing, "
        "model cards, extrapolation flags, and per-cell uncertainty.",
        "Density-grade products (Phase 3-4) are best pursued only inside "
        "designed-survey footprints, kept distinct from the coast-wide "
        "suitability layer.",
        "ISDM is our bridge: the Nisi et al. (2024) integrated framework is "
        "exactly the route the guidance and the strike standard both point "
        "toward (and Nisi co-authors the strike standard).",
        "Uncertainty is the connective tissue: SDM CV feeds the strike "
        "Monte-Carlo, so Phase 2 here unlocks Phase 4 of the strike plan.",
        "Nothing here requires abandoning XGBoost or H3; it requires "
        "adding uncertainty, calibration and, where data permit, a "
        "parallel effort-corrected density layer.",
    ]
    for i, t in enumerate(takeaways, 1):
        pdf.numbered_item(i, t)

    pdf.ln(3)
    pdf.callout_box(
        "Relationship to the strike-risk report",
        "This SDM plan is deliberately the upstream half of the strike-risk "
        "plan. Strike risk = whale exposure x vessel threat x lethality; "
        "the SDM surface IS the whale-exposure term. Improving its density "
        "calibration and uncertainty (Phases 2-4 here) is what lets the "
        "strike chain become quantitative and uncertainty-aware.",
        ReportPDF.ACCENT_BLUE,
    )

    pdf.subsection_title("References")
    pdf.small_text(
        "Miller, D.L. & Kelly, N. (2023). Guidelines for model-based "
        "estimation. SC/69A/ASI/20, IWC Scientific Committee, Bled, May "
        "2023."
    )
    pdf.small_text(
        "Kelly, N. (2023). History of work towards updating the IWC's "
        "'Requirements and Guidelines for Conducting Surveys and Analysing "
        "Data within the Revised Management Scheme'. SC/69A/ASI/21."
    )
    pdf.small_text(
        "Miller, D.L., Burt, M.L., Rexstad, E.A. & Thomas, L. (2013). "
        "Spatial models for distance sampling data: recent developments "
        "and future directions. Methods Ecol. Evol. 4: 1001-1010 (dsm)."
    )
    pdf.small_text(
        "Buckland, S.T., Anderson, D.R., Burnham, K.P., Borchers, D.L. & "
        "Thomas, L. (2001). Introduction to Distance Sampling. OUP."
    )
    pdf.small_text(
        "Hedley, S. & Bravington, M. (2014). Comments on design-based and "
        "model-based abundance estimates for the RMP. SC/65b/RMP11."
    )
    pdf.small_text(
        "Nisi, A.C. et al. (2024). Ship collision risk for whales "
        "(integrated SDM dataset used to train our ISDM models)."
    )

    pdf.output(str(OUTPUT_FILE))
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    build_report()

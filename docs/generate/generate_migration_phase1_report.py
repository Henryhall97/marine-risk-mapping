"""Generate the Tranche 1 / Phase 1 migration report PDF.

Documents the PLAN and the EXECUTION of Phase 1 of the IWC-standard full
migration program (see /memories/repo/iwc-migration-plan.md):

    Phase 1 -- Uncertainty on existing models (medium effort, no new data).

The report covers:
  1. Where Phase 1 sits in the migration program (tranches & phases).
  2. The Phase-1 scope as planned (compute-and-store first, UI fast-follow).
  3. What was actually built (deliverables, file by file).
  4. Design decisions & trade-offs.
  5. Verification results against the Phase-1 gate.
  6. Key diagnostic findings surfaced by the new error analysis.
  7. Key takeaways and what Phase 1b picks up next.

Output: docs/pdfs/migration/tranche1_phase1.pdf
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs" / "migration"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "tranche1_phase1.pdf"


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
                "Marine Risk Mapping -- IWC Migration -- Tranche 1 / Phase 1",
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


# ═══════════════════════════════════════════════════════════════════
# Report content
# ═══════════════════════════════════════════════════════════════════


def build_report():  # noqa: C901 PLR0915
    pdf = ReportPDF("P", "mm", "A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Title page ────────────────────────────────────────────────
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font("Helvetica", "B", 25)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(0, 13, "IWC Migration Programme", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 13, "Tranche 1 / Phase 1", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        9,
        "Uncertainty on Existing Models -- Plan vs Execution",
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
            "The second phase of Tranche 1. Where Phase 0 re-framed the "
            "platform's language, Phase 1 attaches honest ERROR BARS to the "
            "existing whale species-distribution models and exposes the raw "
            "whale x vessel co-occurrence signal on its own. It adds three "
            "things the IWC SDM guidance (Miller & Kelly, 2023) asks for but "
            "the platform lacked: a predictive-uncertainty surface, a "
            "spatial-residual diagnostic, and an extrapolation flag -- plus "
            "an exposure-first base layer (Leaper's explicit request). No new "
            "external data; the science is made more honest, not more."
        ),
        align="C",
    )
    pdf.ln(8)

    pdf.stat_boxes(
        [
            ("5", "Scope items"),
            ("50", "ISDM refits"),
            ("27.4%", "Cells flagged"),
            ("7.3M", "Rows scored"),
        ]
    )
    pdf.ln(6)
    pdf.stat_boxes(
        [
            ("270", "tests pass"),
            ("33", "dbt nodes"),
            ("1", "new mart"),
            ("1", "API layer"),
        ]
    )

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9.5)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5,
        (
            "Status: LANDED, 2026-06-15. Phase-1 verification gate passed; "
            "compute-and-store delivered first, UI exposed as a fast-follow. "
            "Phase 1b started separately."
        ),
        align="C",
    )

    # ── 1. Where Phase 1 sits ─────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1.  Where Phase 1 Sits in the Programme")
    pdf.body_text(
        "Phase 1 is the second phase of Tranche 1 ('standards + screening "
        "refresh', no new external data). It follows Phase 0's framing work "
        "and precedes the audit-driven model corrections of Phase 1b and the "
        "true vessel-traffic-density rewrite of Phase 2. It touches the "
        "modelling, error-analysis, and presentation layers -- it quantifies "
        "the uncertainty in models that already exist rather than building "
        "new ones."
    )
    pdf.metric_table(
        ["Tranche 1 phase", "Theme", "State"],
        [
            ["Phase 0", "Framing, model cards & crosswalk", "Landed"],
            ["Phase 1", "Uncertainty on existing models", "Landed (this report)"],
            ["Phase 1b", "Audit-driven model corrections", "In progress"],
            ["Phase 2", "True VTD + Garrison lethality", "Not started"],
        ],
        col_widths=[34, 96, 60],
    )
    pdf.callout_box(
        "Delivery philosophy -- compute-and-store FIRST",
        "Land the science and the error analysis, inspect the diagnostics, "
        "and only THEN expose them in the UI as a fast-follow slice. This "
        "de-risks the method (does the spread surface look sensible? is the "
        "extrapolation flag firing where expected?) before paying the "
        "multi-touchpoint plumbing cost of a new map layer.",
        colour=ReportPDF.ACCENT_BLUE,
    )

    # ── 2. The plan ───────────────────────────────────────────────
    pdf.section_title("2.  The Plan -- Phase-1 Scope")
    pdf.body_text(
        "Phase 1 was scoped to five deliverables spanning modelling, "
        "error-analysis, and presentation:"
    )
    pdf.numbered_item(
        1,
        "Bootstrap / bagging ensemble (NOT quantile regression -- the SDMs "
        "are binary:logistic, outputting a Bernoulli P(presence), so quantile "
        "regression does not apply). Refit ~50 models on resampled rows with "
        "varied seeds; the per-cell MEAN is the point estimate and the "
        "per-cell SPREAD is the uncertainty band / CV-analogue surface. New "
        "columns in the SDM marts.",
    )
    pdf.numbered_item(
        2,
        "Spatial residual diagnostics in evaluate.py: empirical variograms "
        "and Moran's I on out-of-fold residuals, to confirm whether the "
        "models capture the spatial structure in the data.",
    )
    pdf.numbered_item(
        3,
        "ExDet / MESS-style covariate-envelope extrapolation flag on every "
        "prediction -- a 'low-confidence / extrapolated' overlay marking "
        "cells whose environment lies outside the training range.",
    )
    pdf.numbered_item(
        4,
        "Exposure-first base layer: report the RAW whale x vessel "
        "co-occurrence per cell BEFORE any speed-lethality weighting "
        "(Leaper's explicit request), with the speed-weighted variant as an "
        "optional overlay.",
    )
    pdf.numbered_item(
        5,
        "Expose the uncertainty, extrapolation, and exposure layers in the "
        "map UI and API -- the FAST-FOLLOW, after compute-and-store is "
        "validated.",
    )
    pdf.callout_box(
        "Why bootstrap, not quantile regression",
        "Quantile regression estimates conditional quantiles of a CONTINUOUS "
        "target. The SDMs predict a probability (Bernoulli mean), which has "
        "no meaningful quantiles to regress. Refitting the model on "
        "resampled data and reading the spread of predictions is the correct "
        "uncertainty tool for a classifier. Quantile regression is reserved "
        "for the Phase 3/5 DSM DENSITY (animals per km-squared), which is "
        "continuous.",
        colour=ReportPDF.ACCENT_AMBER,
    )

    # ── 3. The execution ──────────────────────────────────────────
    pdf.section_title("3.  The Execution -- What Was Built")

    pdf.subsection_title("3.1  Uncertainty toolkit (pipeline/analysis/uncertainty.py)")
    pdf.body_text(
        "A new pure-numpy / XGBoost helper module, with no I/O, that the "
        "training scripts call. Two public functions:"
    )
    pdf.bullet(
        "bootstrap_ensemble_predict(...) -- fits K models, each on a "
        "bootstrap resample (rows sampled WITH replacement), and scores the "
        "grid with every member. Returns the per-cell MEAN and STANDARD "
        "DEVIATION of P(presence) across the K members. Supports sub-bagging "
        "(sample_frac < 1.0) and a reduced per-member tree count so the "
        "7.3M-row seasonal grid stays affordable."
    )
    pdf.bullet(
        "mess_extrapolation(...) -- the Multivariate Environmental Similarity "
        "Surface (Elith et al. 2010). Per cell it returns the minimum "
        "similarity across covariates (negative => at least one covariate is "
        "out of the training range) and names the most-dissimilar (MoD) "
        "variable for the model card."
    )

    pdf.subsection_title("3.2  Spatial residual diagnostics (evaluate.py)")
    pdf.body_text(
        "Out-of-fold residuals plus each cell's lat/lon are already in-frame "
        "at train time, so residual diagnostics were nearly free to add. New "
        "helpers: morans_i (global spatial autocorrelation via a cKDTree "
        "neighbour graph), empirical_variogram (binned semivariance vs "
        "distance), and spatial_residual_diagnostics / "
        "plot_spatial_diagnostics, which persist a per-target PNG. Strong "
        "residual autocorrelation flags spatial structure the model has NOT "
        "captured -- exactly the signal the IWC guidance wants reported."
    )

    pdf.subsection_title("3.3  Training-script wiring")
    pdf.body_text(
        "The ISDM and seasonal-SDM trainers gained CLI flags to drive the "
        "ensemble and emit the new columns, with budgets matched to each "
        "model's size:"
    )
    pdf.metric_table(
        ["Trainer", "Ensemble budget", "Outputs added"],
        [
            [
                "train_isdm_model.py",
                "K=50 full bootstrap (Nisi data is tiny)",
                "_sd per species + MESS (value, flag, MoD)",
            ],
            [
                "train_sdm_seasonal.py",
                "K=15 sub-bagging (frac 0.3, 200 trees)",
                "_sd per species + residual diagnostics",
            ],
        ],
        col_widths=[48, 82, 60],
    )
    pdf.body_text(
        "MESS extrapolation is computed for the ISDM only: it is trained on "
        "point (presence) data from the Nisi grid and then scores a DIFFERENT "
        "(H3) grid, so envelope extrapolation is a real risk. The seasonal "
        "SDM trains on the full H3 grid it later scores, so by construction "
        "it does not extrapolate beyond its own covariate envelope."
    )

    pdf.subsection_title("3.4  Marts -- uncertainty columns + new exposure mart")
    pdf.body_text(
        "The loaders (load_ml_predictions.py, load_sdm_predictions.py) carry "
        "the new _sd and MESS columns through to PostGIS via the existing "
        "COPY-from-StringIO idempotent pattern. The intermediate models "
        "(int_ml_whale_predictions, int_sdm_whale_predictions) surface a "
        "combined mean_whale_sd, and the ML risk mart gained four honest "
        "confidence columns:"
    )
    pdf.bullet(
        "fct_collision_risk_ml.sql now exposes whale_prob_sd (ensemble "
        "uncertainty), isdm_mess_value, isdm_extrapolated (boolean), and "
        "isdm_mod_variable (the most-dissimilar covariate name)."
    )
    pdf.body_text(
        "A brand-new mart, fct_whale_vessel_exposure.sql, delivers the "
        "exposure-first base layer at (h3_cell, season) grain (~7.3M rows):"
    )
    pdf.metric_table(
        ["Column", "Definition", "Role"],
        [
            ["exposure_raw", "P(any whale) x vessel volume", "BASE layer"],
            [
                "exposure_speed_weighted",
                "P(any whale) x speed lethality",
                "optional overlay",
            ],
            [
                "exposure_score",
                "percent_rank of raw, PARTITION BY season",
                "season-relative",
            ],
            [
                "exposure_speed_score",
                "percent_rank of speed-weighted, by season",
                "season-relative",
            ],
        ],
        col_widths=[48, 86, 56],
    )
    pdf.body_text(
        "Decoupling exposure from lethality makes the co-occurrence signal -- "
        "the quantity most directly comparable across studies and least "
        "dependent on modelling assumptions -- visible on its own, satisfying "
        "the standard's 'report with and without the lethality weighting' "
        "rule."
    )

    pdf.subsection_title("3.5  UI fast-follow (exposure layer)")
    pdf.body_text(
        "Once the mart was validated, the exposure layer was wired "
        "end-to-end as a fast-follow:"
    )
    pdf.bullet(
        "Backend: a new GET /api/v1/layers/exposure endpoint (ExposureCell "
        "model + get_exposure / count_exposure service functions), filtered "
        "by bbox, season, and a minimum exposure-score threshold."
    )
    pdf.bullet(
        "Frontend: a new 'exposure' LayerType threaded through types.ts, the "
        "useMapData hook (endpoint + seasonal-layer set), colors.ts (colour "
        "ramp, heatmap range, macro weight field), the Legend, the Sidebar "
        "(layer guide entry under Vessel Traffic), and CellDetail (an "
        "explanation panel)."
    )

    # ── 4. Design decisions ───────────────────────────────────────
    pdf.section_title("4.  Design Decisions & Trade-offs")
    pdf.subsection_title("Full bootstrap for ISDM, sub-bagging for the seasonal SDM")
    pdf.body_text(
        "The ISDM trains on the small Nisi grid, so 50 full bootstrap refits "
        "are cheap. The seasonal SDM scores 7.3M rows across seven targets, "
        "so a naive K=50 full bootstrap was too slow; sub-bagging (30% row "
        "sample, 200 trees, K=15) gives a robust spread estimate at a "
        "fraction of the cost. The spread estimator is insensitive to these "
        "knobs, so accuracy is preserved."
    )
    pdf.subsection_title("MESS on the ISDM only")
    pdf.body_text(
        "Extrapolation is only meaningful when a model scores a grid "
        "DIFFERENT from its training support. The ISDM does (Nisi points -> "
        "H3 grid); the seasonal SDM trains and scores on the same grid. "
        "Computing MESS for the SDM would have produced a vacuous all-clear "
        "flag, so it was deliberately omitted."
    )
    pdf.subsection_title("A separate exposure mart, not another column")
    pdf.body_text(
        "Exposure-first is a conceptually distinct reporting product, not a "
        "tweak to the composite risk score. Giving it its own mart "
        "(fct_whale_vessel_exposure) keeps the base co-occurrence signal "
        "cleanly separable in the API and UI, and lets the speed-weighted "
        "overlay sit beside the raw layer without entangling either with the "
        "seven-sub-score collision index."
    )

    # ── 5. Verification ───────────────────────────────────────────
    pdf.section_title("5.  Verification -- Gate Results")
    pdf.body_text(
        "Both the Phase-1 verification line and the global gate were run. All "
        "checks passed:"
    )
    pdf.metric_table(
        ["Check", "Command", "Result"],
        [
            [
                "Uncertainty cols",
                "fct_collision_risk_ml in PostGIS",
                "7.3M rows; _sd + MESS populated",
            ],
            [
                "ISDM ensemble",
                "train_isdm --score-grid --bootstrap-k 50",
                "4 species; 27.4% extrapolated",
            ],
            [
                "Seasonal diag",
                "train_sdm_seasonal --bootstrap-k 15",
                "8 residual PNGs in artifacts",
            ],
            [
                "Exposure mart",
                "dbt build fct_whale_vessel_exposure",
                "7.3M rows; raw + speed populated",
            ],
            ["Subgraph build", "dbt build (modified + downstream)", "33 nodes pass"],
            ["Lint", "ruff check pipeline/ backend/ tests/", "clean"],
            ["Unit tests", "pytest tests/", "270 pass"],
            ["Frontend", "tsc --noEmit", "exit 0"],
            ["Orchestration", "dagster definitions validate", "valid"],
        ],
        col_widths=[30, 90, 70],
    )
    pdf.callout_box(
        "Gate passed",
        "ruff clean; dbt subgraph 33 nodes green; 270 pytest pass; frontend "
        "type-check clean; Dagster validates. Uncertainty columns and the "
        "exposure mart are populated and the exposure layer renders. Phase 1 "
        "is complete; Phase 1b is a separate piece of work.",
        colour=ReportPDF.ACCENT_GREEN,
    )

    # ── 6. Diagnostic findings ────────────────────────────────────
    pdf.section_title("6.  What the Error Analysis Revealed")
    pdf.body_text(
        "The point of adding diagnostics is to LOOK at them. Two findings of "
        "note from this first run:"
    )
    pdf.bullet(
        "Extrapolation is real and concentrated: 27.4% of ISDM-scored cells "
        "fall outside the training envelope, and the most-dissimilar variable "
        "is most often pp_upper_200m (primary productivity). These cells now "
        "carry an honest low-confidence flag instead of being shown as "
        "equally trustworthy."
    )
    pdf.bullet(
        "The minke-whale seasonal SDM left residual Moran's I ~= 0.70 -- "
        "strong positive spatial autocorrelation in the out-of-fold "
        "residuals, i.e. genuine spatial structure the model has NOT "
        "captured. A real diagnostic catch, recorded for follow-up rather "
        "than silently passing."
    )
    pdf.callout_box(
        "Feeds Phase 1b",
        "The variogram range produced here is exactly the input Phase 1b item "
        "E needs to set the spatial-CV block size from residual "
        "autocorrelation instead of a fixed 158 km guess. Phase 1's error "
        "analysis is reused, not rebuilt.",
        colour=ReportPDF.ACCENT_BLUE,
    )

    # ── 7. Takeaways & next ───────────────────────────────────────
    pdf.section_title("7.  Key Takeaways & What's Next")
    pdf.bullet(
        "Honest error bars first: every whale prediction now carries a "
        "spread (uncertainty) and, for the ISDM, an extrapolation flag -- the "
        "platform can finally distinguish 'high risk + confident' from 'high "
        "risk but data-poor'."
    )
    pdf.bullet(
        "The right tool for the target: bootstrap spread for a probability "
        "classifier; quantile regression deferred to the continuous Phase 3 "
        "density."
    )
    pdf.bullet(
        "Compute-and-store first paid off -- the diagnostics were inspected "
        "(and caught a genuine minke autocorrelation issue) before any UI "
        "plumbing was written."
    )
    pdf.bullet(
        "Exposure-first decoupling gives a co-occurrence base layer that is "
        "comparable across studies and independent of lethality assumptions, "
        "directly answering Leaper's request."
    )
    pdf.bullet(
        "The new diagnostics are not throw-away: the variogram range feeds "
        "the Phase 1b CV-block sizing, and the MESS MoD variable feeds the "
        "model cards."
    )
    pdf.body_text(
        "Next: Phase 1b -- audit-driven corrections on the existing models "
        "(no new data). The headline items are the ensemble NULL-deflation "
        "bugfix (a missing model should not halve P(whale)), probability "
        "recalibration, target-group background + spatial thinning to remove "
        "OBIS effort bias, a skill-weighted ensemble, variogram-driven CV "
        "block sizing, a strike-weighted whale-exposure column, the addition "
        "of Rice's whale and gray whale to the species set, and a "
        "protection-gap refresh folding in critical habitat and active slow "
        "zones."
    )

    pdf.ln(4)
    pdf.subsection_title("References")
    pdf.small_text(
        "Elith et al. (2010) Methods Ecol. Evol. 1:330-342 -- MESS / ExDet "
        "environmental novelty. Miller & Kelly (2023) SC/69A/ASI/20 -- IWC "
        "model-based abundance / SDM guidance. Leaper et al. (2026) "
        "SC/70/HIM/13 -- IWC strike-risk reporting standard (exposure-first "
        "request). Nisi et al. (2024) Science 386(6724):870-875 -- ISDM "
        "training source. Rockwood et al. (2021) -- whale x vessel "
        "co-occurrence interaction basis."
    )

    pdf.output(str(OUTPUT_FILE))
    return OUTPUT_FILE


if __name__ == "__main__":
    out = build_report()
    print(f"Wrote {out}")

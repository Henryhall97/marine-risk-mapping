"""Generate the Tranche 1 / Phase 1b migration report PDF.

Documents the PLAN and the EXECUTION of Phase 1b of the IWC-standard full
migration program (see /memories/repo/iwc-migration-plan.md):

    Phase 1b -- Existing-model corrections (no new data, audit-driven).

Phase 1b is the audit-driven correction pass over the existing SDM ensemble,
scoring macros, and protection-gap sub-score. Eight items (A-H) found in a code
audit; none block Phase 3, several make the Phase-3 density land on a sounder
base. The report covers:
  1. Where Phase 1b sits in the migration program.
  2. The Phase-1b scope as planned (items A-H).
  3. What was actually built, item by item.
  4. Two scoring bugs found and fixed during execution.
  5. Design decisions & trade-offs.
  6. Verification results against the Phase-1b gate.
  7. Key takeaways and what Phase 2 picks up next.

Output: docs/pdfs/migration/tranche1_phase1b.pdf
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs" / "migration"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "tranche1_phase1b.pdf"


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
                "Marine Risk Mapping -- IWC Migration -- Tranche 1 / Phase 1b",
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
    pdf.cell(0, 13, "Tranche 1 / Phase 1b", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        9,
        "Existing-Model Corrections -- Plan vs Execution",
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
            "The audit-driven correction pass of Tranche 1. Phase 1b fixes eight "
            "issues (A-H) found in a code audit of the whale-prediction ensemble, "
            "the SDM training pipeline, and the composite-risk scoring macros -- "
            "with no new external data. None of the items block the downstream "
            "density work (Phase 3), but several make it land on a sounder, "
            "honestly-calibrated base. The headline fixes: a probability "
            "NULL-deflation bug, isotonic calibration of every SDM, target-group "
            "background to cancel survey effort bias, a strike-weighted whale "
            "exposure metric, and an enforceable-protection refresh of the "
            "protection-gap sub-score."
        ),
        align="C",
    )
    pdf.ln(10)

    pdf.stat_boxes(
        [
            ("8", "Items A-H"),
            ("8", "SDMs recalibrated"),
            ("2", "Bugs fixed"),
            ("2", "New species"),
        ]
    )
    pdf.ln(6)
    pdf.stat_boxes(
        [
            ("9/9", "Validation PASS"),
            ("270", "tests pass"),
            ("58.1M", "Proj. rows"),
            ("4", "New dbt files"),
        ]
    )

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9.5)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5,
        (
            "Status: LANDED, 2026-06-15. Phase-1b verification gate passed; "
            "Phase 2 not yet started (one chat per phase, stop at the gate)."
        ),
        align="C",
    )

    # ── 1. Where Phase 1b sits ────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1.  Where Phase 1b Sits in the Programme")
    pdf.body_text(
        "Phase 1b is the third phase of Tranche 1, after the framing work "
        "(Phase 0) and the uncertainty layer (Phase 1), and before the true "
        "vessel-traffic-density rewrite (Phase 2). Where Phase 1 ADDED an "
        "uncertainty surface, Phase 1b CORRECTS the existing point estimates -- "
        "it is a debt-paydown pass scoped entirely to models and macros that "
        "already exist, with no new external data."
    )
    pdf.metric_table(
        ["Phase", "Theme", "Relationship to 1b"],
        [
            ["0", "Framing, model cards, crosswalk", "Pre-registered the 1b bugs"],
            ["1", "Uncertainty on existing models", "Variogram feeds item E"],
            ["1b", "Existing-model corrections (A-H)", "THIS REPORT"],
            ["2", "True VTD + Garrison Pleth upgrade", "Rebuilds these marts next"],
        ],
        col_widths=[18, 86, 86],
    )
    pdf.body_text(
        "The Phase-0 model cards deliberately pre-registered the known issues "
        "that Phase 1b now closes (uncalibrated probabilities, OBIS effort "
        "bias, the ensemble NULL-deflation bug, the fixed CV block size, the "
        "any-whale independence assumption). Phase 1b is where that backlog is "
        "paid down rather than merely documented."
    )
    pdf.callout_box(
        "Why correct now, before Phase 2 rebuilds these marts anyway",
        "Phase 2 rebases the SAME collision-risk marts onto true VTD + the "
        "Garrison lethality curve. Doing 1b first means the rebase inherits "
        "calibrated probabilities, the NULL-aware ensemble, and the refreshed "
        "protection ladder -- so Phase 2 changes only the traffic basis, never "
        "re-litigating the whale-probability or protection science. Each phase "
        "is its own commit/verification gate per the migration plan.",
        colour=ReportPDF.ACCENT_BLUE,
    )

    # ── 2. The plan ───────────────────────────────────────────────
    pdf.section_title("2.  The Plan -- Phase-1b Scope (Items A-H)")
    pdf.body_text(
        "Eight audit-driven items, ordered roughly by correctness impact. "
        "Item A is a hard correctness bug; B and C are the biggest accuracy "
        "levers; D-F are validation / documentation; G and H extend the "
        "species set and the protection ladder."
    )
    pdf.metric_table(
        ["Item", "Title", "Severity"],
        [
            ["A", "Ensemble NULL-deflation bugfix", "HIGH / bugfix"],
            ["B", "Probability calibration", "HIGH"],
            ["C", "Target-group background + spatial thinning", "MED-HIGH"],
            ["D", "Skill-weighted ensemble", "MEDIUM"],
            ["E", "Variogram-driven CV block size", "MEDIUM"],
            ["F", "any_whale independence (document)", "LOW"],
            ["G", "Strike-weighted exposure + Rice's + gray", "MED-HIGH"],
            ["H", "Protection-gap refresh (crit. hab + slow zones)", "MEDIUM"],
        ],
        col_widths=[16, 124, 50],
    )

    # ── 3. The execution ──────────────────────────────────────────
    pdf.section_title("3.  The Execution -- What Was Built")

    pdf.subsection_title("A.  Ensemble NULL-deflation bugfix")
    pdf.body_text(
        "The ML mart ensembled four shared species as "
        "(coalesce(isdm,0) + coalesce(sdm,0)) / 2.0. When ISDM coverage was "
        "narrower than SDM, the missing model was treated as a hard ZERO and "
        "the sum still divided by two -- halving the whale probability for a "
        "coverage reason, not a biological one. That deflated value then "
        "propagated into any/max/mean_whale_prob AND the Rockwood "
        "P(whale)xtraffic interaction. The fix is a NULL-aware mean: average "
        "only over the models actually present (ISDM null -> use SDM directly, "
        "never SDM/2). Extracted into a reusable ensemble_prob.sql macro and "
        "applied identically in the current and the projected ML marts."
    )

    pdf.subsection_title("B.  Probability calibration")
    pdf.body_text(
        "The SDMs train with scale_pos_weight = n_neg/n_pos, which is fine for "
        "AUC/ranking but inflates the predicted probability scale. The ML mart "
        "then MULTIPLIES P(whale) x traffic as if the values were calibrated, "
        "biasing every downstream product -- and far worse once Phase 4 uses "
        "P(whale) in an absolute encounter equation. The fix fits a per-species "
        "isotonic regression on out-of-fold predictions and persists it to "
        "artifacts/sdm_seasonal/<species>/calibrator.joblib. The calibrator is "
        "applied at three points so the scale stays consistent end to end: SDM "
        "training, current-grid scoring, and the CMIP6 projection scoring."
    )

    pdf.subsection_title("C.  Target-group background + spatial thinning")
    pdf.body_text(
        "The OBIS presence-background SDM already excludes traffic features, "
        "but feature exclusion alone cannot remove 'where people looked' -- "
        "effort clusters near ports, coastlines, and survey transects. Phase "
        "1b adds target-group background (Phillips et al. 2009: draw background "
        "points from the pooled cetacean-sighting distribution so the shared "
        "effort bias cancels between presence and background) plus spatial "
        "thinning of presences (Aiello-Lammens et al. 2015) in the feature "
        "extraction and training path. This is the single biggest SDM accuracy "
        "lever in the phase."
    )
    pdf.callout_box(
        "Lower AUCs are the point, not a regression",
        "After item C the retrained AUCs sit below the March pre-correction "
        "numbers (e.g. blue 0.684, sperm 0.628). That is expected: removing "
        "effort-bias inflation removes 'easy' separability that was really "
        "just survey geography. The new scores reflect genuine habitat signal, "
        "not where boats happened to sample.",
        colour=ReportPDF.ACCENT_AMBER,
    )

    pdf.subsection_title("D.  Skill-weighted ensemble")
    pdf.body_text(
        "The ISDM:SDM blend was a flat, unjustified 50/50 despite the two "
        "models having very different per-species reliability. Phase 1b weights "
        "the blend by each model's spatial-CV skill (Araujo & New 2007) for the "
        "four shared species, falling back to the SDM alone for the two "
        "SDM-only species (right whale, minke). The two-species SDM-only path "
        "is unchanged; the four-species shared path is now skill-weighted."
    )

    pdf.subsection_title("E.  Variogram-driven CV block size")
    pdf.body_text(
        "Spatial cross-validation previously used a fixed H3 res-2 (~158 km) "
        "block, a guess. Best practice (Valavi et al. 2019; Roberts et al. "
        "2017) sets the block size from the residual autocorrelation range -- "
        "which is exactly the variogram that Phase 1 added. Phase 1b feeds that "
        "empirical range back into the spatial-CV block sizing, closing the "
        "loop between the two phases instead of hard-coding 158 km."
    )

    pdf.subsection_title("F.  any_whale independence assumption (documented)")
    pdf.body_text(
        "The composite any_whale_prob = 1 - product(1 - P_i) assumes species "
        "independence. In reality whales co-occur (shared prey and habitat), so "
        "the formula OVERESTIMATES P(any whale). This is a low-severity, "
        "document-only item: the assumption is now explicitly recorded as a "
        "known simplification alongside the ensemble macro so it is not quietly "
        "forgotten when the value is consumed downstream."
    )

    pdf.subsection_title("G.  Strike-weighted exposure + Rice's + gray whale")
    pdf.body_text(
        "Two changes. First, any_whale_prob is a blunt instrument for STRIKE "
        "risk because it equal-weights a minke and a right whale. It is kept as "
        "a diagnostic, but a new strike-weighted whale exposure -- "
        "sum(P_i x vulnerability_i) -- is promoted to feed the interaction "
        "score, with right/fin/humpback carrying high weight and minke/sperm "
        "low (strike_weighted_exposure.sql macro + strike_vuln_* vars). Second, "
        "the species set gains the two biggest omissions for a Gulf+Pacific "
        "strike platform:"
    )
    pdf.bullet(
        "Rice's whale (Gulf of Mexico Bryde's, ~50 animals, ship strike is THE "
        "primary threat) -- wired end-to-end but DORMANT: only 8 positives, "
        "below the 50-positive training floor, so its column stays NULL and is "
        "coalesced away until survey data (GoMMAPPS) supports a model."
    )
    pdf.bullet(
        "Gray whale (coastal eastern-Pacific migration, regularly struck) -- "
        "fully trained and scored end-to-end (extract -> train -> score -> "
        "load -> marts), CV AUC 0.947."
    )
    pdf.body_text(
        "A new fct_whale_vessel_exposure mart surfaces the exposure-first "
        "(raw co-occurrence) and strike-weighted views side by side, satisfying "
        "Leaper's with/without-lethality reporting rule."
    )

    pdf.subsection_title("H.  Protection-gap refresh")
    pdf.body_text(
        "The protection-gap sub-score previously tiered only MPAs + speed "
        "zones, even though critical habitat and active slow zones / DMAs had "
        "since been ingested into PostGIS. Phase 1b folds the ENFORCEABLE ones "
        "into the tier ladder via two new intermediate models "
        "(int_critical_habitat_coverage, int_slow_zone_coverage), wired into "
        "both fct_collision_risk and fct_collision_risk_seasonal with new "
        "protection_* tier vars and an updated protection_gap macro."
    )
    pdf.callout_box(
        "Why BIA stays OUT",
        "A Biologically Important Area flags WHERE WHALES ARE, not where they "
        "are PROTECTED. Folding it into a protection score would invert the "
        "signal exactly as the proposed (non-binding) speed zones once did -- "
        "a high-whale-use area would read as 'well protected'. Only "
        "enforceable designations (critical habitat, active DMAs) enter the "
        "ladder; BIA is deliberately excluded.",
        colour=ReportPDF.ACCENT_BLUE,
    )

    # ── 4. Bugs found during execution ────────────────────────────
    pdf.section_title("4.  Two Scoring Bugs Found & Fixed in Execution")
    pdf.body_text(
        "Beyond the planned items A-H, materialising the projections surfaced "
        "two latent bugs in the climate-projection scoring path. Both corrupted "
        "the projected-minus-current delta -- the headline range-shift signal -- "
        "and both were fixed before the projection reload."
    )
    pdf.subsection_title("Bug 4 -- calibration not applied to projections")
    pdf.body_text(
        "score_future_sdm.py applied the raw predict_proba (~0.27) while the "
        "current out-of-fold predictions were isotonic-calibrated (~0.019). The "
        "two scales were therefore incomparable, poisoning every "
        "projected-current delta. Fixed by loading and applying the same "
        "per-species item-B calibrator at projection-scoring time."
    )
    pdf.subsection_title("Bug 5 -- projections scored with stale March models")
    pdf.body_text(
        "The model loader scanned a hard-coded MLflow file-store directory that "
        "held only the March pre-item-C models -- and was missing gray whale "
        "entirely. Today's item B+C runs are SQLite-backed (no file-based "
        "params), so the directory scan silently fell back to stale weights. "
        "Rewrote the loader to query the MLflow API against the SQLite store and "
        "pick the most-recent FINISHED run per species, so the projections now "
        "use exactly the models that produced the current-grid predictions."
    )
    pdf.callout_box(
        "Result: clean, monotonic climate signal",
        "After both fixes, projected any-whale exposure rose monotonically with "
        "warming -- SSP2-4.5: 0.0361 -> 0.0473 across decades; SSP5-8.5: 0.0378 "
        "-> 0.0631 (steeper, as the higher-emissions path should be) against a "
        "0.0191 current baseline. The deltas are now modest and interpretable, "
        "not the broken ~0.27.",
        colour=ReportPDF.ACCENT_GREEN,
    )

    # ── 5. Design decisions ───────────────────────────────────────
    pdf.section_title("5.  Design Decisions & Trade-offs")
    pdf.subsection_title("Calibrate the SAME way in all three scoring paths")
    pdf.body_text(
        "The isotonic calibrator is applied at training, current-grid scoring, "
        "AND projection scoring. Using calibrated current but raw projected "
        "values (the Bug-4 state) makes the climate delta uninterpretable -- it "
        "conflates a model-scale artefact with the climate signal. Consistency "
        "of method across current and future is what makes the delta a clean "
        "attribution."
    )
    pdf.subsection_title("Ensemble both current AND projected the same way")
    pdf.body_text(
        "The NULL-aware mean and skill weighting are applied to both the "
        "current and the projected ensembles. Mixing methods (e.g. ISDM-only "
        "current vs ISDM+SDM projected) would again corrupt the delta, so the "
        "correction is symmetric across the time axis."
    )
    pdf.subsection_title("Rice's whale wired-but-dormant rather than dropped")
    pdf.body_text(
        "Rice's whale is the single biggest omission for a Gulf strike "
        "platform, but only 8 positive records exist -- below the 50-positive "
        "training floor. Rather than fabricate a model or omit the species, the "
        "full plumbing (crosswalk, seed, target column, mart coalesce) is in "
        "place and inert, so the day GoMMAPPS survey data lands the model drops "
        "in with no schema change."
    )

    # ── 6. Verification ───────────────────────────────────────────
    pdf.section_title("6.  Verification -- Gate Results")
    pdf.body_text(
        "Both the Phase-1b exit criteria and the global gate were run. All "
        "checks passed:"
    )
    pdf.metric_table(
        ["Check", "Command / Scope", "Result"],
        [
            ["Scoring validation", "validate_traffic_risk --section all", "9/9 PASS"],
            ["dbt build", "11 table models + 93 data tests", "PASS=104, 0 ERR"],
            ["Projection reload", "load_sdm_projections.py", "58.1M rows OK"],
            ["Planner stats", "ANALYZE on 5 rebuilt tables", "OK"],
            ["Unit tests", "pytest tests/", "270 pass"],
            ["Lint", "ruff check pipeline/ backend/ tests/", "clean"],
            ["Orchestration", "dagster definitions validate", "valid"],
            ["PDF", "regen transformation report", "16 pp OK"],
        ],
        col_widths=[36, 102, 52],
    )
    pdf.callout_box(
        "Gate passed",
        "Scoring validation 9 PASS / 0 WARN; scoped dbt build PASS=104 (0 "
        "errors); 270 pytest pass; ruff clean; Dagster validates; transformation "
        "PDF regenerated. Phase 1b is complete and Phase 2 was deliberately NOT "
        "started.",
        colour=ReportPDF.ACCENT_GREEN,
    )

    # ── 7. Takeaways & next ───────────────────────────────────────
    pdf.section_title("7.  Key Takeaways & What's Next")
    pdf.bullet(
        "Correctness before sophistication: a one-line NULL-handling bug (item "
        "A) was silently halving whale probabilities for coverage reasons -- "
        "fixing it matters more than any model tuning."
    )
    pdf.bullet(
        "Calibration is end-to-end or it is nothing: the value of item B was "
        "almost lost to Bug 4 because one of three scoring paths skipped it. "
        "Probability scale must be consistent everywhere it is consumed."
    )
    pdf.bullet(
        "Effort bias cannot be feature-engineered away: target-group background "
        "(item C) addresses 'where people looked', which excluding traffic "
        "features alone never could -- at the honest cost of lower AUCs."
    )
    pdf.bullet(
        "Strike risk is taxon-weighted: equal-weighting a minke and a right "
        "whale (the old any_whale view) understates the species that actually "
        "die -- item G's strike-weighted exposure fixes the signal feeding the "
        "interaction score."
    )
    pdf.bullet(
        "Only enforceable designations are protection: critical habitat and "
        "active DMAs enter the ladder; BIA (a presence flag) is kept out to "
        "avoid inverting the protection-gap signal."
    )
    pdf.bullet(
        "The MLflow file-store vs SQLite-store split is a latent trap (Bug 5) -- "
        "always load models via the MLflow API, never a directory scan."
    )
    pdf.body_text(
        "Next: Phase 2 -- Standard-compatible traffic metric & Pleth upgrade. A "
        "true vessel-traffic-density rewrite (track-km per km^2, not ping "
        "counts) in aggregate_ais.py, a joint type x size x speed strata grain, "
        "the Garrison et al. (2025) lethality curve at two touchpoints, and a "
        "Product-A rebase of fct_collision_risk onto VTD -- inheriting the "
        "calibrated, NULL-aware, refreshed base that Phase 1b just established."
    )

    pdf.ln(4)
    pdf.subsection_title("References")
    pdf.small_text(
        "Leaper et al. (2026) SC/70/HIM/13 -- IWC strike-risk reporting "
        "standard. Miller & Kelly (2023) SC/69A/ASI/20 -- IWC model-based "
        "abundance / SDM guidance. Phillips et al. (2009) Ecol. Appl. "
        "19:181-197 -- target-group background. Aiello-Lammens et al. (2015) "
        "Ecography 38:541-545 -- spatial thinning (spThin). Araujo & New (2007) "
        "Trends Ecol. Evol. 22:42-47 -- ensemble forecasting. Valavi et al. "
        "(2019) Methods Ecol. Evol. 10:225-232 -- blockCV. Roberts et al. "
        "(2017) -- spatial block sizing. Rockwood et al. (2021) -- co-occurrence "
        "interaction basis. Garrison et al. (2025) Front. Mar. Sci. 11:1467387 "
        "-- Pleth upgrade (Phase 2)."
    )

    pdf.output(str(OUTPUT_FILE))
    return OUTPUT_FILE


if __name__ == "__main__":
    out = build_report()
    print(f"Wrote {out}")

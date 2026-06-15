"""Generate the Tranche 1 / Phase 0 migration report PDF.

Documents the PLAN and the EXECUTION of Phase 0 of the IWC-standard full
migration program (see /memories/repo/iwc-migration-plan.md):

    Phase 0 -- Framing, model cards & crosswalk (low effort, no new data).

The report covers:
  1. Where Phase 0 sits in the migration program (tranches & phases).
  2. The Phase-0 scope as planned.
  3. What was actually built (deliverables, file by file).
  4. Design decisions & trade-offs.
  5. Verification results against the Phase-0 gate.
  6. An incidental data-quality fix surfaced during the full build.
  7. Key takeaways and what Phase 1 picks up next.

Output: docs/pdfs/migration/tranche1_phase0.pdf
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs" / "migration"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "tranche1_phase0.pdf"


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
                "Marine Risk Mapping -- IWC Migration -- Tranche 1 / Phase 0",
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
    pdf.cell(0, 13, "Tranche 1 / Phase 0", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        9,
        "Framing, Model Cards & Crosswalk -- Plan vs Execution",
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
            "The first, lowest-effort phase of a full migration of the Marine "
            "Risk Mapping platform towards two IWC Scientific Committee "
            "standards: the vessel-strike reporting standard (Leaper et al., "
            "2026, SC/70/HIM/13) and the model-based abundance / SDM guidance "
            "(Miller & Kelly, 2023, SC/69A/ASI/20). Phase 0 introduces NO new "
            "external data -- it re-frames, documents, and labels the existing "
            "platform so later phases land on honest foundations."
        ),
        align="C",
    )
    pdf.ln(10)

    pdf.stat_boxes(
        [
            ("6", "Scope items"),
            ("4", "Model cards"),
            ("18", "Crosswalk terms"),
            ("0", "Col renames"),
        ]
    )
    pdf.ln(6)
    pdf.stat_boxes(
        [
            ("270", "dbt nodes pass"),
            ("270", "tests pass"),
            ("1", "API endpoint"),
            ("2", "PDFs regen"),
        ]
    )

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9.5)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5,
        (
            "Status: LANDED, 2026-06-14. Phase-0 verification gate passed; "
            "Phase 1 not yet started (one chat per phase, stop at the gate)."
        ),
        align="C",
    )

    # ── 1. Where Phase 0 sits ─────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1.  Where Phase 0 Sits in the Programme")
    pdf.body_text(
        "The migration is staged into three independently shippable tranches. "
        "Each tranche lands, commits, and passes a global verification gate "
        "before the next begins. Phase 0 is the very first phase of Tranche 1 "
        "and is deliberately the cheapest: it ships standalone value to the "
        "existing product with no new external survey data."
    )
    pdf.metric_table(
        ["Tranche", "Theme", "Phases"],
        [
            ["1", "Standards + screening refresh (no new data)", "0, 1, 1b, 2"],
            ["2", "Quantitative density + encounter (survey-gated)", "3, 4"],
            ["3", "Uncertainty + research (downstream of T2)", "5, 6"],
        ],
        col_widths=[20, 115, 55],
    )
    pdf.body_text(
        "Within Tranche 1, Phase 0 precedes the SDM uncertainty work (Phase "
        "1), the audit-driven model corrections (Phase 1b), and the true "
        "vessel-traffic-density rewrite plus Garrison lethality upgrade "
        "(Phase 2). Phase 0 touches only the presentation and documentation "
        "layers; it changes no science."
    )
    pdf.callout_box(
        "Working rule",
        "One chat per phase. Implement the scoped items, run the phase "
        "verification line, then STOP -- do not roll into the next phase. "
        "The progress log in repo memory is updated when a phase lands.",
        colour=ReportPDF.ACCENT_BLUE,
    )

    # ── 2. The plan ───────────────────────────────────────────────
    pdf.section_title("2.  The Plan -- Phase-0 Scope")
    pdf.body_text(
        "Phase 0 (Framing, model cards & crosswalk) was scoped to six "
        "concrete, low-effort items spanning presentation and "
        "error-analysis documentation:"
    )
    pdf.numbered_item(
        1,
        "Re-label all SDM/ISDM outputs as 'relative occurrence probability / "
        "habitat suitability', NOT density or abundance. Scope confirmed to "
        "legends, report prose, and API field DESCRIPTIONS only -- the field "
        "NAMES (isdm_*, sdm_*, *_whale_prob) are already honest, so this is "
        "NOT a column-rename cascade.",
    )
    pdf.numbered_item(
        2,
        "Publish a model card per SDM/ISDM against the Miller & Kelly "
        "checklist (data, covariates, CV, assumptions, biases, intended "
        "use). New docs/model_cards/ directory.",
    )
    pdf.numbered_item(
        3,
        "Ship the IWC terminology crosswalk as machine-readable metadata: a "
        "dbt seed (iwc_crosswalk.csv) plus an API mapping our terms to the "
        "standard's Table-1 terms.",
    )
    pdf.numbered_item(
        4,
        "Emit an AIS-required-only traffic layer alongside the best-estimate "
        "all-traffic. Add a NEW constant AIS_REQUIRED_LENGTH_M ~= 20 m (the "
        "practical SOLAS Class-A proxy) plus all passenger types -- the "
        "existing LARGE_VESSEL / WIDE_VESSEL / DEEP_DRAFT constants are "
        "risk-flagging thresholds, NOT the AIS carriage line.",
    )
    pdf.numbered_item(
        5,
        "Document the modular structure: surface speed_lethality (Pleth-like) "
        "and draft_risk (Pstrikedepth-like) as labelled, toggleable layers.",
    )
    pdf.numbered_item(
        6,
        "Verification line: dbt seed loads iwc_crosswalk; API returns "
        "crosswalk; ruff clean; regenerate both IWC PDFs. Plus the global "
        "gate (pytest, dbt build, ruff, Dagster validate).",
    )

    # ── 3. The execution ──────────────────────────────────────────
    pdf.section_title("3.  The Execution -- What Was Built")
    pdf.subsection_title("3.1  SDM relabelling (no column renames)")
    pdf.body_text(
        "Honest labelling was delivered through three surfaces that reach the "
        "user without touching the database schema:"
    )
    pdf.bullet(
        "Backend Pydantic model docstrings (backend/models/layers.py): the "
        "WhalePredictionCell, SdmPredictionCell, SdmProjectionCell and "
        "IsdmProjectionCell classes now state values are relative occurrence "
        "probability / habitat suitability (0-1), NOT density or abundance."
    )
    pdf.bullet(
        "API route docstrings (backend/api/layers.py): the whale-predictions "
        "(ISDM) and sdm-predictions endpoints carry the same note, which "
        "surfaces in the OpenAPI / Swagger documentation."
    )
    pdf.bullet(
        "Frontend layer-info bodies (frontend/src/components/Sidebar.tsx): "
        "the 'Whale Habitat (Expert)' and 'Whale Habitat (Observed)' panels "
        "now explain the values are a relative ranking of where whales are "
        "more likely to occur, not animals per km-squared."
    )

    pdf.subsection_title("3.2  Model cards (docs/model_cards/)")
    pdf.body_text(
        "Four cards, each answering the same six Miller & Kelly questions, "
        "plus an index README that restates the critical labelling note:"
    )
    pdf.metric_table(
        ["Card", "Model", "Backend"],
        [
            ["whale_sdm_static.md", "Static any-cetacean SDM", "XGBoost"],
            ["whale_sdm_seasonal.md", "Seasonal per-species SDM", "XGBoost"],
            ["isdm_nisi.md", "ISDM per-species (Nisi data)", "XGBoost"],
            [
                "traffic_lethality_layers.md",
                "Speed-lethality + draft-risk layers",
                "dbt / SQL",
            ],
        ],
        col_widths=[58, 92, 40],
    )
    pdf.body_text(
        "The cards do double duty: they document each model honestly today, "
        "and they pre-register the known issues that Phase 1 / 1b will fix "
        "(uncalibrated probabilities, OBIS effort bias, the ensemble "
        "NULL-deflation bug, fixed CV block size, the any-whale independence "
        "assumption) so nothing is quietly forgotten."
    )

    pdf.subsection_title("3.3  IWC terminology crosswalk")
    pdf.body_text(
        "An 18-row dbt seed (transform/seeds/iwc_crosswalk.csv) maps our "
        "internal terms to the IWC Table-1 vocabulary across seven "
        "categories (exposure, encounter, mortality, vessel, whale, "
        "uncertainty, output) and two standards (strike, sdm). Documented and "
        "tested in seeds.yml (term_id unique + not_null; category and "
        "standard accepted_values)."
    )
    pdf.body_text(
        "It is served read-only at GET /api/v1/species/iwc-crosswalk via a "
        "new service function (list_iwc_crosswalk), two Pydantic schemas "
        "(IwcCrosswalkEntry / IwcCrosswalkResponse), and a route on the "
        "existing species router -- no new router. A backend test "
        "(TestSpecies.test_iwc_crosswalk) mocks the service and asserts the "
        "response shape."
    )

    pdf.subsection_title("3.4  AIS-required traffic groundwork")
    pdf.body_text(
        "A new constant AIS_REQUIRED_LENGTH_M = 20 was added to "
        "pipeline/config.py with a comment block clarifying it is a SOLAS "
        "Class-A length proxy (legally mandated to broadcast AIS), NOT a "
        "risk-flagging threshold. The AIS aggregation query "
        "(aggregate_ais.py) gained two cell-level columns, "
        "ais_required_vessels and ais_required_pings, filtering on length >= "
        "20 m OR a passenger vessel type."
    )
    pdf.callout_box(
        "Deliberately dormant",
        "The two new aggregate columns are NOT wired into any dbt model and "
        "were NOT re-materialised -- re-running the 3.1B-ping aggregation "
        "takes hours and belongs to the Phase 2 VTD rewrite. They are inert "
        "groundwork, so the dbt build stays green with zero new data work in "
        "Phase 0.",
        colour=ReportPDF.ACCENT_AMBER,
    )

    pdf.subsection_title("3.5  Modular lethality layers documented")
    pdf.body_text(
        "The traffic_lethality_layers.md card describes speed_lethality "
        "(IWC Pleth) and draft_risk (IWC Pstrikedepth) as independent, "
        "toggleable map layers -- mirroring the standard's separation of "
        "exposure from conditional mortality. The frontend already exposes "
        "both as TrafficMetric toggles; the card formalises why they are kept "
        "modular and flags the Phase 2 Garrison (2025) Pleth upgrade."
    )

    # ── 4. Design decisions ───────────────────────────────────────
    pdf.section_title("4.  Design Decisions & Trade-offs")
    pdf.subsection_title("Why docstrings, not column renames")
    pdf.body_text(
        "The API field names were already free of density/abundance language, "
        "so a rename cascade would have been pure churn with downstream "
        "breakage risk across dbt models, Python queries, and the frontend. "
        "Relabelling via docstrings and Field descriptions (which surface in "
        "OpenAPI) achieves the honesty goal at a fraction of the risk."
    )
    pdf.subsection_title("Why the crosswalk lives under the species router")
    pdf.body_text(
        "Placing GET /api/v1/species/iwc-crosswalk alongside the existing "
        "/api/v1/species/crosswalk avoids a new router and keeps reference "
        "metadata endpoints together, consistent with the established "
        "service-returns-dicts / route-builds-Pydantic pattern."
    )
    pdf.subsection_title("Why the AIS columns are dormant")
    pdf.body_text(
        "Phase 0's contract is 'no new data, low effort'. Adding the SQL now "
        "(but not running it) front-loads the schema decision and keeps the "
        "constant and query in one reviewable change, while deferring the "
        "expensive recomputation to Phase 2 where the full VTD track-km "
        "rewrite re-runs aggregation anyway."
    )

    # ── 5. Verification ───────────────────────────────────────────
    pdf.section_title("5.  Verification -- Gate Results")
    pdf.body_text(
        "Both the Phase-0 verification line and the global gate were run. All "
        "checks passed:"
    )
    pdf.metric_table(
        ["Check", "Command", "Result"],
        [
            ["Seed loads", "dbt seed --select iwc_crosswalk", "OK -- 18 rows"],
            ["Full build", "dbt build --profiles-dir .", "270 nodes pass"],
            ["API crosswalk", "GET /api/v1/species/iwc-crosswalk", "200 + test"],
            ["Lint", "ruff check pipeline/ backend/ tests/", "clean"],
            ["Unit tests", "pytest tests/", "270 pass"],
            ["Orchestration", "dagster definitions validate", "valid"],
            ["IWC PDFs", "regenerate both alignment reports", "regen OK"],
        ],
        col_widths=[34, 96, 60],
    )
    pdf.callout_box(
        "Gate passed",
        "ruff clean; dbt build 270 nodes green; 270 pytest pass; Dagster "
        "validates; both IWC alignment PDFs regenerated. Phase 0 is complete "
        "and Phase 1 was deliberately NOT started.",
        colour=ReportPDF.ACCENT_GREEN,
    )

    # ── 6. Incidental fix ─────────────────────────────────────────
    pdf.section_title("6.  Incidental Fix -- CMIP6 Dedup")
    pdf.body_text(
        "The full dbt build surfaced a PRE-EXISTING failure unrelated to the "
        "Phase-0 seed work: the uniqueness test on "
        "int_ocean_covariates_projected (grain h3_cell, season, scenario, "
        "decade) returned ~59M duplicate keys."
    )
    pdf.body_text(
        "Root cause: a handful of CMIP6 climate-model grid cells round to the "
        "same 0.5-degree (lat, lon) within a (scenario, decade, season). The "
        "model's optimised Step-2 equi-join on (lat, lon) then doubled those "
        "cells. The fix added a deterministic distinct-on "
        "(scenario, decade, season, lat, lon) dedup CTE in "
        "stg_cmip6_ocean_covariates.sql, restoring one row per coordinate. A "
        "targeted rebuild of that subtree passed (19 nodes, uniqueness test "
        "green)."
    )
    pdf.callout_box(
        "Scope note",
        "This was a data-quality fix incidental to running the Phase-0 gate, "
        "not part of the Phase-0 scope. It is recorded in the migration "
        "progress log so the provenance is clear.",
        colour=ReportPDF.ACCENT_BLUE,
    )

    # ── 7. Takeaways & next ───────────────────────────────────────
    pdf.section_title("7.  Key Takeaways & What's Next")
    pdf.bullet(
        "Honest framing first: every later phase rests on outputs being "
        "labelled as relative suitability, not density -- Phase 0 makes that "
        "true everywhere a user looks."
    )
    pdf.bullet(
        "Low effort, high leverage: no new data, no science change, no column "
        "renames -- yet model cards, a machine-readable crosswalk, and an API "
        "endpoint are now in place."
    )
    pdf.bullet(
        "Pre-registering known issues in the model cards keeps the Phase 1 / "
        "1b backlog visible and honest."
    )
    pdf.bullet(
        "Dormant groundwork (AIS-required columns, lethality-layer docs) "
        "de-risks Phase 2 without paying its compute cost now."
    )
    pdf.bullet(
        "The verification gate caught and forced a fix for a latent CMIP6 "
        "data-quality bug -- a free win from running the full build."
    )
    pdf.body_text(
        "Next: Phase 1 -- Uncertainty on existing models. Bootstrap / bagging "
        "ensembles for per-cell mean P(presence) + spread (a CV-analogue "
        "surface), spatial residual diagnostics (variograms, Moran's I), an "
        "ExDet / MESS extrapolation flag, and an exposure-first co-occurrence "
        "base layer. Compute-and-store first, expose in the UI as a "
        "fast-follow."
    )

    pdf.ln(4)
    pdf.subsection_title("References")
    pdf.small_text(
        "Leaper et al. (2026) SC/70/HIM/13 -- IWC strike-risk reporting "
        "standard. Miller & Kelly (2023) SC/69A/ASI/20 -- IWC model-based "
        "abundance / SDM guidance. Nisi et al. (2024) Science "
        "386(6724):870-875 -- ISDM training source. Rockwood et al. (2021) "
        "-- co-occurrence interaction basis. Garrison et al. (2025) Front. "
        "Mar. Sci. 11:1467387 -- recommended Pleth upgrade (Phase 2)."
    )

    pdf.output(str(OUTPUT_FILE))
    return OUTPUT_FILE


if __name__ == "__main__":
    out = build_report()
    print(f"Wrote {out}")

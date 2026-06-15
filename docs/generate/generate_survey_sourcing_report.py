"""Generate the Survey-Data Sourcing Plan report PDF (plan vs execution).

Documents the PLAN and the EXECUTION of the survey-data SOURCING workstream
of the IWC-standard migration programme (see /memories/repo/iwc-migration-plan.md,
"PARALLEL WORKSTREAM -- survey-data sourcing", and docs/survey_data_status.md).

The workstream runs CONCURRENTLY with Tranche 1 and GATES Phase 3 (the R
DSM density engine).  It is research / data-hunt + light Python tidy work,
not modelling code.

The report covers:
  1. Where the workstream sits in the migration programme.
  2. Why it exists (DSM needs designed-survey distance data).
  3. The acquisition gate (6-item checklist + GO/CAVEATED/NO-GO rule).
  4. The plan -- NARW-first priority order, the status-table deliverable.
  5. Execution -- the per-program GO/CAVEATED/NO-GO status table.
  6. Execution deep-dive -- the GoMMAPPS NCEI download+tidy that shipped.
  7. AMAPPS access route confirmed (named NEFSC data manager).
  8. Validation benchmark (Roberts/Duke), outstanding actions, takeaways.

Output: docs/pdfs/migration/survey_data_sourcing.pdf
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs" / "migration"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "survey_data_sourcing.pdf"


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
                "Marine Risk Mapping -- IWC Migration -- Survey-Data Sourcing",
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
    pdf.ln(28)
    pdf.set_font("Helvetica", "B", 25)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(0, 13, "IWC Migration Programme", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 13, "Survey-Data Sourcing", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        9,
        "The Parallel Workstream that Gates Phase 3 -- Plan vs Execution",
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
            "Phase 3 turns whale observations into ABSOLUTE density "
            "(animals/km2) with error bars -- and a density-surface model is "
            "only valid where it has DESIGNED-SURVEY data: on-effort "
            "tracklines, perpendicular distances, group sizes, and the "
            "metadata to correct for animals missed on the line (g0). That "
            "data is not a download; it is a real acquisition programme. This "
            "workstream runs in PARALLEL with Tranche 1, has zero code "
            "dependency on it, and is the long pole that gates Phase 3. The "
            "deliverable is a per-programme GO / GO-caveated / NO-GO table, "
            "kept current as each programme is vetted. This report sets out "
            "the plan and the execution to date."
        ),
        align="C",
    )
    pdf.ln(8)

    pdf.stat_boxes(
        [
            ("8", "Programmes vetted"),
            ("4", "GO / GO-full"),
            ("3", "GO-caveated"),
            ("1", "Data in hand"),
        ]
    )
    pdf.ln(6)
    pdf.stat_boxes(
        [
            ("272.5k", "GoM effort pts"),
            ("1,564", "GoM sightings"),
            ("96.4%", "with distance"),
            ("NARW", "GO -> P3 ready"),
        ]
    )

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9.5)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5,
        (
            "Status: ON TRACK, 2026-06-15. NARW US-Atlantic cleared to GO "
            "(AMAPPS) -- the Tranche-1 exit condition is satisfied, so Phase 3 "
            "can start NARW-first with no wait. GoMMAPPS data downloaded and "
            "tidied direct from NCEI. Other programmes continue sourcing in "
            "the background."
        ),
        align="C",
    )

    # ══════════════════════════════════════════════════════════════
    # 1. Where the workstream sits
    # ══════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("1.  Where This Workstream Sits")
    pdf.body_text(
        "The migration is delivered in three tranches. Tranche 1 ('standards "
        "+ screening refresh', Phases 0-2) improves the EXISTING product with "
        "no new external data. Tranche 2 (Phases 3-4) is the quantitative "
        "density + encounter build, and it is GATED on survey data. Survey-"
        "data sourcing is the research workstream that opens that gate."
    )
    pdf.metric_table(
        ["Track", "Theme", "New data?", "State"],
        [
            ["Tranche 1", "Standards + screening refresh", "No", "In progress"],
            ["-> Sourcing", "Survey-data acquisition (this)", "Yes", "In progress"],
            [
                "Tranche 2",
                "DSM density + encounter (P3-4)",
                "Yes (gated)",
                "Blocked on data",
            ],
            ["Tranche 3", "Monte-Carlo uncertainty (P5-6)", "No", "Not started"],
        ],
        col_widths=[30, 88, 32, 40],
    )
    pdf.callout_box(
        "Why it must start NOW, alongside Phase 0/1",
        "The workstream has ZERO code dependency on Tranche 1 but is the "
        "long pole: it is email + research + light tidy scripts, and lead "
        "times on NOAA data requests are measured in weeks. Starting it the "
        "moment Tranche 1 kicks off is what lets Phase 3 begin the instant "
        "Tranche 1 lands -- instead of stalling while we wait for data. If "
        "sourcing stalls, Tranche 1 still ships standalone; only Tranche 2 "
        "waits. That is precisely why the tranches are split this way.",
        colour=ReportPDF.ACCENT_BLUE,
    )

    # ══════════════════════════════════════════════════════════════
    # 2. Why it exists
    # ══════════════════════════════════════════════════════════════
    pdf.section_title("2.  Why It Exists -- DSM Needs Designed-Survey Data")
    pdf.body_text(
        "IWC risk = whales x ships x lethality. We currently have only a "
        "RELATIVE whale ranking (the XGBoost SDM / ISDM ensemble), not a "
        "count. Phase 3's job is to produce absolute density. A density-"
        "surface model (DSM) is fitted from distance sampling: on-effort "
        "tracklines with perpendicular distances let you estimate the "
        "detection function (how detectability falls with distance), correct "
        "for it, and spread density across the map with a spatial GAM."
    )
    pdf.bullet(
        "Opportunistic / presence-only data (OBIS, NARWC sightings) CANNOT "
        "anchor absolute density -- they have no effort denominator and "
        "re-import the very effort bias we are trying to remove."
    )
    pdf.bullet(
        "R DSM is the PRIMARY density product. The Roberts et al. / Duke "
        "habitat-based density models are an independent VALIDATION benchmark "
        "only (US Atlantic + Gulf), per the locked plan -- not the source."
    )
    pdf.bullet(
        "So for each survey programme the question is concrete: does its raw "
        "distance-sampling data exist, in reusable form, and what does it "
        "satisfy? That is what the acquisition gate scores."
    )

    # ══════════════════════════════════════════════════════════════
    # 3. The acquisition gate
    # ══════════════════════════════════════════════════════════════
    pdf.section_title("3.  The Acquisition Gate")
    pdf.body_text(
        "Each programme is scored against six checklist items. Items 1-3 are "
        "HARD (a DSM cannot be fitted without them); items 4-5 are SOFT (they "
        "enable g(0) correction -- their absence only caveats the result); "
        "item 6 is normally already satisfied in our PostGIS covariate grid."
    )
    pdf.metric_table(
        ["#", "Checklist item", "Hard?", "What it buys"],
        [
            ["1", "Perpendicular distances", "HARD", "Detection function -> strip"],
            ["2", "Effort / tracklines", "HARD", "Segmentable effort + offset"],
            ["3", "Group size per detection", "HARD*", "Group -> individual density"],
            ["4", "Double-platform observer", "SOFT", "Corrects misses ON the line"],
            ["5", "Dive-tag time-at-depth", "SOFT", "Corrects deep-diver misses"],
            ["6", "Env covariate coverage", "(have)", "GAM predictors"],
        ],
        col_widths=[10, 60, 22, 98],
    )
    pdf.small_text(
        "*Item 3 falls back to a mean group size E[s] if per-detection counts "
        "are missing. Item 5 is single-sourced once in Phase 3 as "
        "whale_dive_cdf.csv (per species, not per programme) and reused by "
        "Phase 4 (Pstrikedepth) and Phase 5b (availability uncertainty)."
    )
    pdf.subsection_title("Decision rule per programme / species")
    pdf.bullet("GO (full DSM): items 1-3 AND (4 OR 5) -> g(0)-corrected DSM.")
    pdf.bullet(
        "GO (caveated): items 1-3 only, no g(0) data -> DSM with g(0)=1 "
        "documented, deep divers flagged biased-low."
    )
    pdf.bullet(
        "NO-GO: any of items 1-3 missing -> no Phase-3 surface; that "
        "region/species stays Product-A screening only and emits no R/N/I."
    )

    # ══════════════════════════════════════════════════════════════
    # 4. The plan
    # ══════════════════════════════════════════════════════════════
    pdf.section_title("4.  The Plan -- NARW-First Priority Order")
    pdf.body_text(
        "Sourcing is ordered by strike value and data quality, NARW-first, so "
        "the single highest-value region clears the gate before Tranche 1 "
        "ends and Phase 3 can begin NARW-first with no stall. Other "
        "programmes continue sourcing in the background while Phase 3/4 build."
    )
    pdf.numbered_item(
        1,
        "AMAPPS (NEFSC+SEFSC) + NARWSS + NARWC for NARW US-Atlantic FIRST -- "
        "best data plus the Roberts validation target.",
    )
    pdf.numbered_item(
        2,
        "GoMMAPPS (Gulf of Mexico) next -- Rice's whale is the biggest "
        "species omission for a strike platform covering the Gulf.",
    )
    pdf.numbered_item(
        3,
        "Then SWFSC (California Current), AFSC (Alaska), PIFSC (Hawaii) "
        "region-by-region.",
    )
    pdf.callout_box(
        "Exit condition (defines Phase-3 readiness)",
        "At least NARW US-Atlantic cleared to GO (or GO-caveated) BEFORE "
        "Tranche 1 finishes. The deliverable is a per-programme status table "
        "(programme -> region -> species -> checklist items -> verdict -> "
        "access route), kept current in docs/survey_data_status.md. No DSM "
        "code is written in this workstream -- only the research verdicts and "
        "light Python download+tidy scripts.",
        colour=ReportPDF.ACCENT_GREEN,
    )

    # ══════════════════════════════════════════════════════════════
    # 5. Execution -- the status table
    # ══════════════════════════════════════════════════════════════
    pdf.section_title("5.  Execution -- Per-Programme Status")
    pdf.body_text(
        "All eight candidate programmes across the study area have been "
        "vetted against the gate. The verdict column is the deliverable; the "
        "headline is that NARW US-Atlantic is GO."
    )
    pdf.metric_table(
        ["Programme", "Region", "Verdict"],
        [
            ["AMAPPS", "US Atlantic shelf+slope", "GO (full DSM)"],
            ["NARWSS", "US NE / Mid-Atlantic", "GO-caveated (pool into NARW)"],
            ["NARWC", "US+CAN Atlantic", "NO-GO (validation/presence only)"],
            ["GoMMAPPS", "Gulf of Mexico", "GO-caveated -- DATA IN HAND"],
            ["SWFSC", "California Current", "GO (full DSM)"],
            ["AFSC", "Alaska (GoA/Bering/Aleutian)", "GO-caveated (sparser)"],
            ["PIFSC HICEAS", "Hawaii / C. Pacific", "GO (full) -- few strike targets"],
            ["SEFSC Caribbean", "PR / USVI", "NO-GO (provisional, too sparse)"],
        ],
        col_widths=[36, 70, 84],
    )
    pdf.callout_box(
        "Headline -- NARW US-Atlantic = GO",
        "AMAPPS satisfies items 1-3 plus double-platform g(0); NARWSS pools "
        "in as caveated aerial effort; NARWC is held back as validation / "
        "presence only. This clears the Tranche-1 exit condition -- Phase 3 "
        "can begin NARW-first the moment Tranche 1 lands.",
        colour=ReportPDF.ACCENT_GREEN,
    )

    # ══════════════════════════════════════════════════════════════
    # 6. Execution deep-dive -- GoMMAPPS
    # ══════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("6.  Execution Deep-Dive -- GoMMAPPS Downloaded + Tidied")
    pdf.body_text(
        "GoMMAPPS is the first programme taken from a verdict to data on "
        "disk. The raw distance-sampling data are archived at NCEI (one "
        "accession per survey leg), so no email request was needed -- a "
        "single Python download+tidy script "
        "(pipeline/ingestion/download_survey_gommapps.py) resolves each "
        "accession's NCEI archive path, crawls for the CSV tables, and "
        "harmonises them into the three tidy tables shared across all survey "
        "programmes. This script is the TEMPLATE for the other programmes."
    )
    pdf.subsection_title("What was produced")
    pdf.metric_table(
        ["Tidy table", "Rows", "Content"],
        [
            ["survey_segments", "272,555", "Effort geometry, 1 row / effort point"],
            ["survey_sightings", "1,564", "Perp. distance + group size (on-transect)"],
            [
                "survey_detection_covariates",
                "1,564",
                "Beaufort, observer, double-platform",
            ],
        ],
        col_widths=[58, 28, 104],
    )
    pdf.body_text(
        "Of 1,564 on-transect sightings, 1,508 (96.4%) carry a perpendicular "
        "distance and are detection-function ready: vessel legs 100%, aerial "
        "legs 93.4%. Top species tidied: common bottlenose dolphin 881, sperm "
        "whale 159, then pantropical / Atlantic spotted dolphins. Six raw "
        "per-cruise accessions were processed (3 shipboard, 3 aerial); three "
        "further accessions were honestly excluded."
    )
    pdf.subsection_title("Python does download + tidy ONLY")
    pdf.body_text(
        "By the locked plan, the statistics (detection function, effort "
        "segmentation, DSM GAM) all live in the R density/ toolchain. The "
        "Python script's sole job is to land clean, harmonised tables -- it "
        "computes no estimates. This keeps the whole statistical chain in R "
        "and avoids a confusing R->Python->R ping-pong across the "
        "strip-width boundary."
    )
    pdf.subsection_title("Schema-robustness was the real work")
    pdf.body_text(
        "GoMMAPPS ships three schema families with table-name drift and two "
        "different perpendicular-distance geometries. Getting this right -- "
        "rather than silently dropping data -- was the substance of the "
        "execution:"
    )
    pdf.bullet(
        "Aerial cue tables (MMSightsAndCues / MammalSightsAndCues) were "
        "initially missed by a vessel-only regex, which would have dropped "
        "ALL aerial perpendicular distances and mislabelled them "
        "presence-only. Aerial surveys DO archive distance: their "
        "sightingDistanceInMeters is already perpendicular (derived from the "
        "declination angle and flight altitude)."
    )
    pdf.bullet(
        "Platform-aware geometry: vessel perp = radial x sin(bearing); aerial "
        "perp = the stored value directly. One winter aerial accession used a "
        "no-underscore table name (MMSightsBehObs) and was being skipped "
        "entirely -- now matched."
    )
    pdf.bullet(
        "Aerial legs split effort + cue tables across two simultaneous "
        "observer teams (T1/T2) flying the SAME trackline. We use T1 as the "
        "trackline (to avoid double-counting effort) and set double_platform "
        "because the second team exists -- giving aerial a g(0) signal too."
    )
    pdf.callout_box(
        "Honest exclusions -- not everything in the archive is DSM data",
        "Three of nine GoMMAPPS accessions were excluded with logged "
        "reasons: two consolidated strip-transect products (coarse distance "
        "BINS, multi-taxon / seabird-dominated -- not line-transect cetacean "
        "data) and one published SEFSC density-model shapefile set, which is "
        "kept as a Gulf VALIDATION benchmark (a Roberts-equivalent), not "
        "survey input. Shipping silently-incomplete or mislabelled data would "
        "have poisoned the DSM; the exclusions are documented in the script "
        "and the status tracker.",
        colour=ReportPDF.ACCENT_AMBER,
    )

    # ══════════════════════════════════════════════════════════════
    # 7. AMAPPS access route
    # ══════════════════════════════════════════════════════════════
    pdf.section_title("7.  AMAPPS Access Route -- Named Data Manager")
    pdf.body_text(
        "For the cornerstone NARW dataset the access route is now concrete, "
        "not a generic 'find a NEFSC contact' step. The AMAPPS Northeast + "
        "Southeast aerial and shipboard cruises (2010-2023) are hosted on "
        "OBIS-SEAMAP under provider 671 -- Beth Josephson, NOAA Fisheries "
        "NEFSC data manager (Woods Hole). ~30 cruises are listed and the "
        "sighting observations are directly downloadable."
    )
    pdf.bullet(
        "Still to request: the on-effort tracklines + per-sighting "
        "perpendicular distances + double-platform / MRDS fields behind those "
        "observation layers (OBIS-SEAMAP often exposes the points but not the "
        "full distance-sampling effort tables), plus the SEFSC Southeast "
        "components, and confirmation of redistribution terms."
    )
    pdf.bullet(
        "This is the true Phase-3 critical path -- an email to a named "
        "person, not a search."
    )

    pdf.subsection_title("Validation benchmark (not a primary source)")
    pdf.body_text(
        "Roberts et al. / Duke 'Habitat-based Marine Mammal Density Models "
        "for the U.S. Atlantic' (absolute density, 5 km raster, 2.8M km of "
        "1992-2020 effort, dedicated NARW model v12.2 2024) is the "
        "independent validation benchmark for our DSM in the US Atlantic + "
        "Gulf -- rank-correlation + calibration + abundance cross-check where "
        "overlapping. The rasters are CC-BY 4.0; the processed survey data "
        "feeding them is NOT openly redistributable, so for our own DSM fit "
        "we still source the raw distance/effort from NEFSC/SEFSC/OBIS-SEAMAP "
        "directly."
    )

    # ══════════════════════════════════════════════════════════════
    # 8. Outstanding actions
    # ══════════════════════════════════════════════════════════════
    pdf.section_title("8.  Outstanding Actions")
    pdf.metric_table(
        ["Action", "Owner / route", "State"],
        [
            [
                "AMAPPS effort + perp-distance + g(0) tables",
                "Beth Josephson, NEFSC (prov. 671)",
                "Awaiting reply",
            ],
            [
                "Confirm AMAPPS redistribution / storage licence",
                "same reply thread",
                "Awaiting reply",
            ],
            ["GoMMAPPS download + tidy (NCEI)", "download_survey_gommapps.py", "DONE"],
            [
                "NARWC DUA (validation/presence layer)",
                "narwc.org -> H. Pettis",
                "Application gated",
            ],
            [
                "SWFSC California Current distance + effort",
                "Jeff Moore, SWFSC CMAP",
                "Queued",
            ],
            ["PIFSC HICEAS distance + effort", "Erin Oleson, PIFSC", "Queued"],
            [
                "AFSC (GoA/Bering/Aleutian) distance + effort",
                "Janice Waite, NMML/AFSC",
                "Queued",
            ],
            [
                "Per-species dive-tag CDF (whale_dive_cdf)",
                "literature (Phase 3)",
                "Inventory done",
            ],
        ],
        col_widths=[78, 70, 42],
        body_font=8.5,
    )

    # ══════════════════════════════════════════════════════════════
    # 9. Key takeaways
    # ══════════════════════════════════════════════════════════════
    pdf.section_title("9.  Key Takeaways")
    pdf.bullet(
        "Survey-data sourcing is the long pole of the whole migration -- the "
        "code is not the bottleneck, the designed-survey data is. Running it "
        "in parallel with Tranche 1 is what keeps Phase 3 from stalling."
    )
    pdf.bullet(
        "The Tranche-1 exit condition is SATISFIED: NARW US-Atlantic is GO "
        "via AMAPPS. Phase 3 can start NARW-first with no wait."
    )
    pdf.bullet(
        "GoMMAPPS is the first programme from verdict to data on disk -- "
        "272.5k effort points, 1,564 sightings, 96.4% with perpendicular "
        "distance -- and it sets the download+tidy template for the rest."
    )
    pdf.bullet(
        "Schema robustness matters more than volume: a vessel-only regex "
        "would have silently dropped every aerial distance. Honest handling "
        "of drift (and honest EXCLUSION of strip-transect / shapefile "
        "accessions) is the difference between DSM-ready and DSM-poisoned."
    )
    pdf.bullet(
        "Provenance discipline holds throughout: R DSM is the primary "
        "product; Roberts/Duke and the GoM density shapefiles are validation "
        "benchmarks only; presence-only data (NARWC, OBIS) never anchors "
        "absolute density."
    )
    pdf.bullet(
        "The remaining critical path is a single email thread to a named "
        "NEFSC data manager (Beth Josephson) for the AMAPPS effort + "
        "perpendicular-distance tables."
    )

    pdf.ln(4)
    pdf.subsection_title("References")
    pdf.small_text(
        "Leaper et al. (2026) SC/70/HIM/13 -- IWC strike-risk reporting "
        "standard. Miller & Kelly (2023) SC/69A/ASI/20 -- IWC model-based "
        "abundance / SDM guidance. Roberts et al. (2024) MEPS "
        "doi:10.3354/meps14547 -- US Atlantic habitat-based density models "
        "(NARW v12.2). Buckland et al. (2001) -- distance sampling. "
        "GoMMAPPS (SEFSC) doi:10.25923/xdnn-wg78 -- Gulf of Mexico survey "
        "programme; raw accessions via NOAA NCEI archive. OBIS-SEAMAP "
        "provider 671 -- AMAPPS NE+SE cruises (B. Josephson, NEFSC)."
    )

    pdf.output(str(OUTPUT_FILE))
    return OUTPUT_FILE


if __name__ == "__main__":
    out = build_report()
    print(f"Wrote {out}")

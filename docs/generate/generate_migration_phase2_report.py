"""Generate the Tranche 1 / Phase 2 migration report PDF.

Documents the PLAN and the EXECUTION of Phase 2 of the IWC-standard full
migration program (see /memories/repo/iwc-migration-plan.md):

    Phase 2 -- Standard-compatible traffic metric & Pleth upgrade.

Phase 2 rebuilds the vessel-traffic backbone onto the IWC ship-strike
reporting standard (Leaper et al. 2026, SC/70/HIM/13). It replaces ping/
vessel COUNTS with true Vessel Transit Density (VTD, track-km per km^2),
stratifies traffic on the standard's joint (type x size x speed-bin) grain,
and upgrades the speed-lethality curve from Vanderlaan & Taggart (2007) to
Garrison et al. (2025). The standard mart's traffic score is rebased onto
these IWC-aligned quantities (Product-A rebase). The report covers:
  1. Where Phase 2 sits in the migration program.
  2. The Phase-2 scope as planned.
  3. What was actually built, component by component.
  4. The Garrison (2025) coefficient sourcing + size-class remap.
  5. Jensen's-inequality correctness and the validation evidence.
  6. Challenges hit during execution and how they were solved.
  7. Documented caveats (2024-only AIS, non-AIS small craft).
  8. Verification against the Phase-2 gate, takeaways, technologies.

Output: docs/pdfs/migration/tranche1_phase2.pdf
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs" / "migration"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "tranche1_phase2.pdf"


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
                "Marine Risk Mapping -- IWC Migration -- Tranche 1 / Phase 2",
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
    pdf.cell(0, 13, "Tranche 1 / Phase 2", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        9,
        "Traffic Metric & Pleth Upgrade -- Plan vs Execution",
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
            "The traffic-backbone rebuild of Tranche 1. Phase 2 retires "
            "ping/vessel COUNTS -- which are biased by AIS broadcast rate and "
            "dwell time -- in favour of true Vessel Transit Density (VTD, "
            "track-km per km^2), computed from consecutive AIS positions with "
            "exact great-circle segment-to-cell apportionment. Traffic is "
            "re-stratified on the IWC standard's joint (vessel type x size "
            "class x speed bin) grain, and the speed-lethality curve is "
            "upgraded from Vanderlaan & Taggart (2007) to Garrison et al. "
            "(2025). The standard collision-risk mart is rebased onto these "
            "IWC-aligned quantities (Product-A rebase), with the V&T "
            "formulation retained as a diagnostic surface."
        ),
        align="C",
    )
    pdf.ln(10)

    pdf.stat_boxes(
        [
            ("VTD", "track-km / km^2"),
            ("11.58M", "Joint strata"),
            ("0.129", "Garrison B1 / kn"),
            ("Product-A", "Rebased"),
        ]
    )
    pdf.ln(6)
    pdf.stat_boxes(
        [
            ("9/9", "Validation PASS"),
            ("0.9975", "Jensen rho"),
            ("0.0027", "Mean |bias|"),
            ("3", "PDFs regen"),
        ]
    )

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9.5)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5,
        (
            "Status: LANDED, 2026-06-16. Phase-2 verification gate passed; "
            "Phase 3 not yet started (one chat per phase, stop at the gate)."
        ),
        align="C",
    )

    # ── 1. Where Phase 2 sits ─────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1.  Where Phase 2 Sits in the Programme")
    pdf.body_text(
        "Phase 2 is the fourth phase of Tranche 1, after the framing work "
        "(Phase 0), the uncertainty layer (Phase 1), and the existing-model "
        "corrections (Phase 1b). It is the first phase to rebuild a core "
        "data product rather than patch the existing one: the entire vessel-"
        "traffic magnitude is recomputed from raw AIS positions. Every "
        "downstream traffic mart, the standard composite risk score, and the "
        "Phase 4 mortality module rest on the aggregate_ais.py output that "
        "Phase 2 rewrites."
    )
    pdf.metric_table(
        ["Phase", "Theme", "Relationship to Phase 2"],
        [
            ["0", "Framing, model cards, crosswalk", "Pre-registered the metric"],
            ["1", "Uncertainty on existing models", "Independent layer"],
            ["1b", "Existing-model corrections", "Cleaned the scoring base"],
            ["2", "True VTD + Garrison Pleth", "THIS REPORT"],
            ["3", "Survey ingestion + DSM density", "Consumes VTD strata next"],
            ["4", "Mortality module (N x P_leth)", "Garrison touchpoint B"],
        ],
        col_widths=[18, 78, 94],
    )
    pdf.body_text(
        "The IWC standard (Leaper et al. 2026, SC/70/HIM/13) decomposes "
        "ship-strike risk into a chain of modular products. Phase 2 delivers "
        "the traffic backbone of that chain: an unbiased exposure surface "
        "(VTD) stratified so the downstream lethality and encounter-geometry "
        "terms can each draw the axis they need."
    )

    pdf.equation_box(
        "IWC standard encounter / mortality chain",
        "R = Dw x VTD x w ;  N = R x Pstrikedepth ;  I = N x Pleth",
        "Dw = whale density (Phase 3); VTD = vessel transit density (THIS "
        "PHASE); w = contact-zone width; Pleth = Garrison lethality (Phase 4 "
        "touchpoint B). Phase 2 builds VTD and the joint strata the rest "
        "consume.",
    )

    # ── 2. Phase 2 scope as planned ───────────────────────────────
    pdf.add_page()
    pdf.section_title("2.  Phase 2 Scope -- As Planned")
    pdf.body_text(
        "The migration plan scoped Phase 2 as five interlocking workstreams. "
        "They are listed here as planned; Section 3 reports what was actually "
        "built and where execution diverged."
    )

    pdf.subsection_title("2.1  True VTD from consecutive AIS positions")
    pdf.bullet(
        "Order pings by timestamp per MMSI per month; form consecutive "
        "segments; compute per-segment gap, haversine distance, implied speed."
    )
    pdf.bullet(
        "Teleport / outlier filter on implied speed, PER vessel class, to "
        "drop impossible segments (GPS error, MMSI collision)."
    )
    pdf.bullet(
        "Apportion each segment's length to the H3 cells it crosses via a "
        "hybrid same-cell fast path + exact ST_Intersection clip for the few "
        "boundary-spanning segments (Rockwood Track Builder approach)."
    )
    pdf.bullet(
        "Sum valid segment-km per (cell, month); divide by actual per-cell "
        "H3 res-7 area (varies with latitude) to get VTD in km^-1."
    )

    pdf.subsection_title("2.2  Joint strata grain")
    pdf.bullet(
        "Emit VTD on the cross-product key (h3_cell, month, vessel_type, "
        "size_class, speed_bin) -- a single GROUP BY, not a nested drill-down."
    )
    pdf.bullet(
        "Bin speed on the SEGMENT's own implied speed (<=10, 10-12, 12-15, "
        ">15 kn), so a decelerating ship deposits km into multiple bins."
    )
    pdf.bullet(
        "This full cross-product must exist before any lethality is applied: "
        "Phase 4 sums over (type, size, speed) and each axis feeds a "
        "different term (beam -> width; speed -> Garrison; size -> Garrison)."
    )

    pdf.subsection_title("2.3  Garrison (2025) Pleth upgrade")
    pdf.bullet(
        "Replace the V&T 2007 logistic with Garrison et al. (2025): speed x "
        "size class x whale taxon, with the speed x taxon interaction."
    )
    pdf.bullet(
        "Two touchpoints: (A) a taxon-agnostic generic curve in the Phase 2 "
        "traffic screen; (B) the full taxon-specific curve in Phase 4 "
        "mortality, where the interaction actually bites."
    )
    pdf.bullet(
        "Mechanics: a garrison_lethality_coeffs seed (whale_taxon x size "
        "class -> beta params) read by a garrison_lethality() macro; V&T "
        "scalars retained for the back-compat sensitivity diff."
    )

    pdf.subsection_title("2.4  Product-A rebase + Mayette mass")
    pdf.bullet(
        "Rebase the standard mart traffic score: pctl_vessels on VTD track-"
        "km, pctl_speed_lethality on the Garrison generic curve. Weights need "
        "NO re-elicitation -- they are proportions over percentile ranks, "
        "invariant to the count -> VTD rebasing."
    )
    pdf.bullet(
        "Adopt Mayette & Brillant (2026) vessel-mass-from-length for draft "
        "imputation, a Garrison size covariate, and an OLS cross-check."
    )

    pdf.subsection_title("2.5  Documented caveats")
    pdf.bullet(
        "2024-only AIS: VTD is a single annual snapshot; interannual "
        "variability is not captured (within-2024 seasonality still valid)."
    )
    pdf.bullet(
        "Non-AIS small craft: a known blind spot, documented -- no fabricated "
        "correction factor, no phantom-traffic Monte-Carlo."
    )

    # ── 3. What was built ─────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("3.  What Was Built -- Execution")

    pdf.subsection_title("3.1  aggregate_ais.py -- the VTD rewrite")
    pdf.body_text(
        "The aggregation was rebuilt around track segments rather than "
        "independent pings. Pings are ordered per (MMSI, month); consecutive "
        "pairs form segments; each segment carries a haversine length, a time "
        "gap, and an implied speed. A per-class implied-speed ceiling drops "
        "teleports. Same-cell segments (the dense-AIS common case, 95%+) take "
        "a zero-geometry fast path; the few boundary-spanning segments are "
        "clipped exactly against their candidate cells with ST_Intersection "
        "so track-km is conserved along the great circle. Segment-km is summed "
        "per cell-month and divided by the true latitude-varying H3 res-7 "
        "cell area to yield VTD (km per km^2)."
    )

    pdf.subsection_title("3.2  ais_vtd_strata -- joint cross-product")
    pdf.body_text(
        "The aggregation emits on the joint (h3_cell, month, vessel_type, "
        "size_class, speed_bin) key -- 11,578,420 strata rows loaded into "
        "PostGIS. Speed is binned on each segment's own implied speed, so a "
        "ship that slows on approach correctly splits its track-km across "
        "speed bins of the same type x size stratum. This grain is the "
        "contract for Phase 4: no axis is averaged away before lethality."
    )

    pdf.subsection_title("3.3  int_vtd.sql -- cell-month rollup + Garrison")
    pdf.body_text(
        "int_vtd rolls the strata up to (h3_cell, month), joining "
        "garrison_lethality_coeffs (whale_taxon = 'generic') on size_class "
        "and applying the garrison_lethality() macro per stratum before the "
        "track-km-weighted average. Outputs include total_track_km, "
        "vtd_km_per_km2, garrison_leth_generic (track-km-weighted), and the "
        "Mayette mean vessel mass. 11.58M strata -> the cell-month grain the "
        "marts join on."
    )

    pdf.equation_box(
        "garrison_lethality() macro",
        "P = 1.0 / (1.0 + exp(-(beta0 + beta1 * speed_kn)))",
        "beta0/beta1 from the seed per (whale_taxon, size_class). Applied per "
        "narrow speed bin so the nonlinearity is honoured (see Section 5).",
    )

    pdf.subsection_title("3.4  Product-A rebase of fct_collision_risk")
    pdf.body_text(
        "The standard mart's traffic score now derives its two dominant "
        "components from IWC-aligned quantities: pctl_vessels = "
        "percent_rank(avg_vtd_km_per_km2) and pctl_speed_lethality = "
        "percent_rank(avg_garrison_lethality). The remaining six V&T "
        "components (high-speed fraction, large-vessel, draft, deep-draft, "
        "commercial, night) are unchanged. The full V&T per-vessel lethality "
        "columns survive in ais_h3_summary and int_vessel_traffic as "
        "diagnostics but no longer drive the composite. The seasonal mart was "
        "rebased identically."
    )

    pdf.subsection_title("3.5  config.py mirror + Mayette mass")
    pdf.body_text(
        "GARRISON_GENERIC_BETA mirrors the seed's touchpoint-A 'generic' rows "
        "so the DuckDB VTD aggregation evaluates the same curve in-pipeline "
        "without a DB round-trip. The Mayette & Brillant mass-from-length "
        "relation feeds draft imputation (displacement solve when AIS draft "
        "is null), a Garrison size covariate, and an OLS cross-check."
    )

    # ── 4. Garrison coefficient sourcing ──────────────────────────
    pdf.add_page()
    pdf.section_title("4.  Garrison (2025): Real Coefficients + Size Remap")
    pdf.small_text(
        "Garrison, L.P. et al. (2025). Vessel speed and the lethality of "
        "large whale ship strikes. Frontiers in Marine Science, 11:1467387. "
        "Open access (CC-BY, US Gov work). n = 192 strike events (79 lethal / "
        "113 non-lethal); pseudo-R^2 = 0.291."
    )
    pdf.ln(1)
    pdf.body_text(
        "The plan flagged 'extract the Garrison coefficient table before "
        "coding' as an open sourcing task. During execution the paper's "
        "Table 3 best logit model was retrieved and the provisional seed "
        "(V&T-anchored, beta1 = 0.42 for all taxa) was replaced with the real "
        "coefficients. The provisional slope was ~3x too steep: Garrison's "
        "real speed effect is far gentler (beta1 = 0.129/kn for non-humpback) "
        "and probabilities are much higher at low speed."
    )

    pdf.equation_box(
        "Garrison et al. (2025) Table 3 -- best logit model",
        "logit(P) = -1.744 + 0.129*v + size - 0.139*HB - 0.103*v*HB",
        "v = speed (kn); HB = 1 for humpback. Size offsets added to the "
        "intercept: Small 0, Medium +0.113, Large +0.617, XL +2.498.",
    )

    pdf.body_text(
        "We reconstructed per-(size, taxon) (beta0, beta1) pairs and validated "
        "them exactly against the paper's Table 4 predicted probabilities at "
        "5/10/15/20/25/30 kn. The seed stores eight rows (non-humpback x4 + "
        "humpback x4); touchpoint A uses only the generic (non-humpback) rows."
    )
    pdf.metric_table(
        ["Garrison size", "Non-humpback (beta0, beta1)", "Humpback (beta0, beta1)"],
        [
            ["Small (<12.1 m)", "(-1.744, 0.129)", "(-1.883, 0.026)"],
            ["Medium (12.2-19.7 m)", "(-1.631, 0.129)", "(-1.770, 0.026)"],
            ["Large (19.8-108 m)", "(-1.127, 0.129)", "(-1.266, 0.026)"],
            ["XL (>=108 m)", "(+0.754, 0.129)", "(+0.615, 0.026)"],
        ],
        col_widths=[55, 68, 67],
    )

    pdf.subsection_title("Size-class remap (the one real approximation)")
    pdf.body_text(
        "Garrison's size bins are defined on vessel LENGTH with its only "
        "material edge at 108 m. AIS transponder carriage begins around 20 m, "
        "so essentially every vessel in our data falls in Garrison Large "
        "(19.8-108 m) or XL (>=108 m); Garrison Small/Medium sit below the AIS "
        "line. Our VTD length bins (small <50, medium 50-100, large 100-200, "
        "vlarge >=200 m) therefore map onto the 108 m seam: small/medium -> "
        "Garrison Large (beta0 = -1.127), large/vlarge -> Garrison XL (beta0 = "
        "+0.754). The sole approximation is the narrow 100-108 m band "
        "receiving the XL curve -- negligible traffic."
    )
    pdf.ln(2)
    pdf.callout_box(
        "Why generic-only at touchpoint A",
        "The traffic SCREEN must stay a single lethality column. Garrison's "
        "taxon split (humpback vs other) and the full taxon x size grid are "
        "reserved for Phase 4 mortality, where N is per-species from the DSM "
        "density and the speed x taxon interaction genuinely changes the "
        "answer. Mixing taxa into the screen would imply a whale composition "
        "we do not yet have. Leaper's caveat stands: speed is a 3-pathway "
        "lever (encounter, avoidance, lethality), so Pleth is a lower bound "
        "on the value of slowing -- speed-risk > lethality.",
        ReportPDF.ACCENT_BLUE,
    )

    # ── 5. Jensen correctness + validation ────────────────────────
    pdf.add_page()
    pdf.section_title("5.  Jensen-Correctness and Validation Evidence")
    pdf.body_text(
        "Because P(lethal | speed) is nonlinear, averaging speed before "
        "applying the logistic biases the estimate (Jensen's inequality). The "
        "joint strata are already binned by narrow speed bins, so the Garrison "
        "logistic is applied per bin and the residual within-bin spread is "
        "tiny. The scoring-validation script was rewritten to test exactly "
        "this: it compares the binned estimate (what the pipeline uses) "
        "against a speed-collapsed counterfactual (bins collapsed to one "
        "track-km-weighted mean speed per size class, Garrison applied once)."
    )

    pdf.metric_table(
        ["Validation check", "Result", "Verdict"],
        [
            ["Jensen inequality (binned vs collapsed)", "rho=0.9975", "PASS"],
            ["  mean |bias| over 11.58M cell-months", "0.0027", "PASS"],
            ["Jensen spatial (|bias| vs speed-spread)", "rho=0.8897", "PASS"],
            ["Draft imputation coverage", "100% (6% OLS)", "PASS"],
            ["Composite vs Nisi all_risk", "rho=0.5853", "PASS"],
            ["Traffic vs Nisi shipping_index", "rho=0.3600", "PASS"],
            ["Strike enrichment (critical cells)", "214.7x", "PASS"],
            ["Weight perturbation (rank stability)", "rho=0.9964", "PASS"],
            ["Composite sensitivity (rank stability)", "rho=0.9938", "PASS"],
        ],
        col_widths=[100, 45, 45],
    )

    pdf.ln(1)
    pdf.callout_box(
        "High rho + tiny bias is the ideal, not a contradiction",
        "Binning + Garrison is SUPPOSED to change the lethality value vs a "
        "naive speed-average -- that is the accuracy gain. But because the "
        "traffic score consumes a percentile RANK, what matters downstream is "
        "that cells keep their relative order. The Jensen check confirms both: "
        "the lethality estimate is essentially unbiased (|bias| = 0.0027) AND "
        "the ranking is near-perfectly preserved (rho = 0.9975). Accuracy from "
        "the correction; robustness from rank stability.",
        ReportPDF.ACCENT_GREEN,
    )

    pdf.body_text(
        "One benign internal note remains in the SMA-overlap check: traffic "
        "score inside Seasonal Management Areas (median 0.38) is BELOW the "
        "all-cell median (0.46). This is expected and informative, not a "
        "defect -- SMAs are sited on whale density, not traffic, and the "
        "VTD/Garrison rebasing de-emphasises exactly the high-speed lethality "
        "that SMAs suppress. The protection-gap check passes overall."
    )

    # ── 6. Challenges & solutions ─────────────────────────────────
    pdf.add_page()
    pdf.section_title("6.  Challenges & Solutions")

    pdf.subsection_title("6.1  DuckDB out-of-memory on the segment join")
    pdf.body_text(
        "Forming consecutive segments and clipping boundary-spanning legs "
        "across 3.1 billion pings exceeded memory when run as a single query. "
        "Solution: chunk the aggregation by month (and spatial tile where "
        "needed) so each pass holds only one slice of tracks, with the "
        "same-cell fast path keeping geometry cost off the hot path. The "
        "exact ST_Intersection clip only ever touches the small minority of "
        "boundary-spanning segments."
    )

    pdf.subsection_title("6.2  True VTD vs the easy ping-count proxy")
    pdf.body_text(
        "The tempting shortcut -- counting pings per cell -- conflates AIS "
        "broadcast rate (Class A every 2-10 s vs Class B every 30 s) and "
        "dwell time with actual transit. A slow ship loitering in a cell would "
        "dominate a fast transiting one. True VTD apportions great-circle "
        "track-km and conserves distance, giving an exposure surface that "
        "reflects how much vessel travel actually passes through each cell."
    )

    pdf.subsection_title("6.3  Joint strata vs sequential drill-down")
    pdf.body_text(
        "An early instinct was to aggregate type, then size, then speed in "
        "nested steps. That collapses axes by averaging before lethality, "
        "breaking either the Jensen nonlinearity (speed) or the geometry "
        "contrast (a container vs a tug at equal speed). The fix was a single "
        "GROUP BY on the full cross-product so every (type, size, speed) "
        "combination survives intact for Phase 4."
    )

    pdf.subsection_title("6.4  Provisional Garrison coefficients were wrong")
    pdf.body_text(
        "The seed was first stubbed with V&T-anchored placeholders (beta1 = "
        "0.42 all taxa). Retrieving the real Table 3 revealed the slope was "
        "~3x too steep and the taxon structure collapses to just two levels "
        "(humpback vs other). The seed was rewritten with the eight real rows "
        "and validated exactly against Table 4, and config.py was re-mirrored."
    )

    pdf.subsection_title("6.5  datetime month crash in validation")
    pdf.body_text(
        "The rewritten Jensen check crashed with 'int() argument must be a "
        "real number, not datetime.date'. ais_vtd_strata.month is a date, not "
        "an integer; the top-bias display loop was casting it. Fixed by "
        "formatting month as %s with the raw value. Validation logging was "
        "also redirected to logs/phase2_validation.log because the "
        "interactive terminal buffered the output."
    )

    # ── 7. Caveats ────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("7.  Documented Caveats")
    pdf.body_text(
        "Two limitations are deliberately documented rather than papered over "
        "with fabricated corrections. Honesty about scope is part of the IWC "
        "standard's reporting discipline."
    )
    pdf.callout_box(
        "2024-only AIS (temporal representativeness)",
        "VTD is built from a single annual AIS snapshot. Interannual "
        "variability (traffic growth, route shifts, regulatory changes) is "
        "NOT captured; the surface should be read as 'traffic = 2024'. "
        "Within-2024 seasonality remains valid and is preserved in the "
        "monthly grain. The metric is expandable when more years are ingested "
        "-- no code change, a documented limitation.",
        ReportPDF.ACCENT_AMBER,
    )
    pdf.callout_box(
        "Non-AIS small craft (coverage blind spot)",
        "VTD is scoped to AIS-required vessels (the Rockwood convention: large "
        "commercial traffic). Recreational and small fishing craft below the "
        "AIS carriage line are a known blind spot. We deliberately add NO "
        "fabricated correction factor and NO phantom-traffic scenario -- the "
        "AIS-required surface is the primary, defensible output, and the gap "
        "is stated in the model card and reports.",
        ReportPDF.ACCENT_RED,
    )

    # ── 8. Verification gate ──────────────────────────────────────
    pdf.add_page()
    pdf.section_title("8.  Phase-2 Verification Gate")
    pdf.body_text(
        "The gate was scoped to avoid a needless cold dbt rebuild (the "
        "int_vtd model alone takes ~27 min single-threaded, and everything "
        "Garrison-affected had just been rebuilt). Verification focused on "
        "the surfaces actually touched."
    )
    pdf.metric_table(
        ["Gate item", "Outcome"],
        [
            ["Scoring validation (9 checks)", "9 PASS, 0 WARN"],
            ["pytest suite", "PASS"],
            ["ruff check (pipeline/backend/tests)", "Clean"],
            ["Dagster definitions validate", "Valid"],
            ["Traffic + transformation + IWC PDFs", "Regenerated"],
            ["Garrison seed vs Table 4", "Exact match"],
        ],
        col_widths=[110, 80],
    )

    pdf.subsection_title("8.1  Key takeaways")
    pdf.numbered_item(
        1,
        "VTD (track-km/km^2) replaces count-based exposure -- an unbiased, "
        "IWC-standard traffic magnitude built from consecutive AIS positions.",
    )
    pdf.numbered_item(
        2,
        "The joint (type x size x speed-bin) grain is a contract, not a "
        "convenience: every axis must survive intact for the Phase 4 chain.",
    )
    pdf.numbered_item(
        3,
        "Garrison (2025) real Table 3 coefficients replace V&T -- gentler "
        "slope (0.129 vs 0.41 /kn), higher low-speed lethality, validated "
        "exactly against Table 4.",
    )
    pdf.numbered_item(
        4,
        "Touchpoint A (traffic screen) uses the generic curve; the "
        "taxon-specific curve waits for Phase 4 where per-species N exists.",
    )
    pdf.numbered_item(
        5,
        "Product-A rebase needed NO weight re-elicitation -- percentile ranks "
        "are invariant to the count -> VTD rebasing; only the magnitude "
        "becomes unbiased.",
    )
    pdf.numbered_item(
        6,
        "Jensen-correctness is preserved by per-bin application: rho = 0.9975, "
        "mean |bias| = 0.0027 over 11.58M cell-months.",
    )
    pdf.numbered_item(
        7,
        "V&T is retained as a diagnostic, not deleted -- it remains the "
        "back-compat sensitivity reference.",
    )
    pdf.numbered_item(
        8,
        "Caveats (2024-only AIS, non-AIS small craft) are documented honestly "
        "with no fabricated corrections.",
    )

    pdf.subsection_title("8.2  Key technologies")
    pdf.body_text(
        "DuckDB spatial (segment-to-cell ST_Intersection apportionment); H3 "
        "res-7 latitude-aware cell areas; PostGIS (11.58M strata); dbt "
        "(int_vtd rollup, garrison_lethality macro, seed); Garrison et al. "
        "(2025) logistic; Mayette & Brillant (2026) mass-from-length; "
        "percent_rank composite scoring; Spearman/Jensen validation; fpdf2 "
        "reporting."
    )

    pdf.ln(2)
    pdf.callout_box(
        "What Phase 3 picks up next",
        "Phase 3 turns whale observations into ABSOLUTE density (animals/km^2) "
        "with error bars via distance-sampling + density-surface modelling in "
        "R (Distance, mrds, dsm). That density Dw multiplies the VTD strata "
        "this phase built, and Phase 4 then applies the full taxon-specific "
        "Garrison curve at I = N x Pleth. The traffic backbone is now ready "
        "for both.",
        ReportPDF.TEAL,
    )

    pdf.output(str(OUTPUT_FILE))
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    build_report()

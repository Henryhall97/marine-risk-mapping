"""Generate IWC Strike-Risk Standardisation Alignment PDF.

Assesses how the Marine Risk Mapping platform fits alongside (and
differs from) the IWC Scientific Committee guidance paper:

    Leaper, R., Bedrinana-Romano, L., Bouchard, A., Collins, T., Hines, E.,
    Hague, E., Keen, E., Livermore, S., Nisi, A., Reisinger, R. & Rhodes, R.
    (2026). "Considerations for standardising reporting of vessel strike
    risk assessments." SC/70/HIM/13, IWC Scientific Committee.

The report covers four things the project owner asked for:
  1. OVERLAP    - where our pipeline already aligns with the standard.
  2. ISSUES     - where our approach diverges or falls short.
  3. MIGRATION  - a concrete path to standard-compatible reporting.
  4. IMPROVEMENT- a prioritised, phased work plan.
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs" / "modelling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "iwc_strike_risk_alignment.pdf"


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
                "Marine Risk Mapping -- IWC Strike-Risk Standardisation Alignment",
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
    pdf.ln(34)
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
        "Strike-Risk Reporting Standard",
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
            "An assessment of how the Marine Risk Mapping platform fits "
            "alongside the IWC Scientific Committee guidance paper "
            "SC/70/HIM/13 (Leaper et al., 2026): 'Considerations for "
            "standardising reporting of vessel strike risk assessments', "
            "developed at the IMO / Benioff Ocean Science Laboratory "
            "workshop, London, January 2026."
        ),
        align="C",
    )
    pdf.ln(10)

    pdf.stat_boxes(
        [
            ("5", "Standard modules"),
            ("10", "Overlaps found"),
            ("12", "Gaps identified"),
            ("4", "Migration phases"),
        ]
    )

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9.5)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5,
        (
            "Prepared by the Marine Risk Mapping project in response to "
            "feedback from vessel-strike modelling specialists. Section 6 "
            "is the action plan. Note: A. Nisi is both a co-author of the "
            "IWC paper and the source of the ISDM training data already "
            "embedded in our ML pipeline."
        ),
        align="C",
    )

    # ── 1. Executive summary ──────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1. Executive Summary")

    pdf.body_text(
        "The IWC paper is not a model -- it is a reporting standard. It "
        "asks the strike-risk community to express assessments through a "
        "common, modular, multiplicative chain so that results can be "
        "compared between studies, areas, and over time. Its reference "
        "structure (Figure 1 of the paper) is a five-module encounter-rate "
        "model that builds from raw co-occurrence up to estimated annual "
        "mortality, reporting an output at each stage."
    )

    pdf.body_text(
        "Our platform is a different class of tool. It is a high-resolution, "
        "multi-species, relative risk screening and engagement system: an "
        "H3 grid covering CONUS, Alaska, Hawaii and the Caribbean; a "
        "seven-sub-score composite; an ISDM+SDM machine-learning ensemble; "
        "CMIP6 climate projections; and a public-facing dashboard with "
        "citizen-science photo/audio classification. The IWC framework is a "
        "mortality-estimation standard; ours is a relative-risk visualisation "
        "and prioritisation platform. They are complementary, not competing."
    )

    pdf.callout_box(
        "Bottom line",
        (
            "We already share the standard's scientific foundations (AIS "
            "traffic, V&T speed-lethality, draft / strike-zone reasoning, a "
            "~1 km grid, relative-density indices, and Nisi et al. 2024). "
            "The principal gap is structural: we collapse everything into one "
            "additive 0-1 index, whereas the standard wants a multiplicative "
            "chain with a reported output at each module. The recommended "
            "path is to add a standard-compatible REPORTING LAYER on top of "
            "the existing pipeline -- not to replace the composite."
        ),
        colour=ReportPDF.ACCENT_GREEN,
    )

    pdf.subsection_title("1.1  How to read this document")
    pdf.bullet("Section 2 summarises the standard's five-module reference model.")
    pdf.bullet("Section 3 maps OVERLAP -- ten places we already align.")
    pdf.bullet("Section 4 lists ISSUES -- eleven divergences and shortfalls.")
    pdf.bullet("Section 5 gives a side-by-side terminology and module crosswalk.")
    pdf.bullet("Section 6 is the phased migration and improvement plan (the ask).")
    pdf.subsection_title("1.2  Direct feedback from the standard's lead author")
    pdf.body_text(
        "R. Leaper (lead author of SC/70/HIM/13) shared four points by "
        "email that this revision now incorporates. They sharpen, rather "
        "than change, the migration plan:"
    )
    pdf.bullet(
        "Report exposure per cell BEFORE applying the Vanderlaan & Taggart "
        "(2007) speed-lethality weighting -- raw whale x vessel co-occurrence "
        "is the base output; speed-weighting is an optional overlay on top "
        "(now Phase 1, and the standard's with/without rule)."
    )
    pdf.bullet(
        "Prefer Garrison et al. (2025) over V&T (2007): a more recent "
        "re-estimation of the speed-lethality relationship on a much larger "
        "dataset (now the headline Phase 2 upgrade)."
    )
    pdf.bullet(
        "Lethality-given-strike (Pleth) is only a relatively SMALL part of "
        "the overall speed-risk relationship -- speed also drives encounter "
        "rate and avoidance ability. Our single speed_lethality term "
        "therefore under-represents how speed shapes risk (new Issue 12)."
    )
    pdf.bullet(
        "The IWC ship-strike database holds only a small sample of the US "
        "strike record; for a US-focused platform it adds little beyond the "
        "NOAA / US sources we already use (see the data-source note in "
        "Section 6)."
    )
    # ── 2. The standard in brief ──────────────────────────────────
    pdf.add_page()
    pdf.section_title("2. The IWC Standard in Brief")

    pdf.body_text(
        "The paper recommends a modular, multiplicative encounter-rate "
        "framework with results reported as each module is added from left "
        "to right. The two anchor equations are the encounter rate R and "
        "the annual mortality M:"
    )

    pdf.equation_box(
        "Encounter rate (per grid square)",
        "R  =  Dw  x  VTD  x  w",
        note=(
            "Dw = whale density; VTD = Vessel Travelled Density (distance "
            "travelled per unit area, km^-1); w = contact-zone width = "
            "vessel beam + whale dimension term."
        ),
    )

    pdf.equation_box(
        "Annual mortality",
        "M  =  N  x  (1 - Pavoid)  x  (1 - Pmanoeuvre)  x  Pleth",
        note=(
            "N = R x Pstrikedepth = expected interactions; Pavoid = whale "
            "avoidance; Pmanoeuvre = vessel avoidance; Pleth = lethality "
            "given contact. Each factor is a discrete, optional module."
        ),
    )

    pdf.subsection_title("2.1  The five reported outputs")
    pdf.numbered_item(
        1,
        "Co-occurrence / overlap of whale density and vessel traffic "
        "(simplest relative index).",
    )
    pdf.numbered_item(
        2,
        "Encounter rate R = Dw x VTD x w (adds the contact-zone geometry).",
    )
    pdf.numbered_item(
        3,
        "Interactions N = R x Pstrikedepth (adds vertical strike zone from "
        "whale dive behaviour and vessel draft).",
    )
    pdf.numbered_item(
        4,
        "Mortality Index I = N x Pleth (adds speed-lethality, e.g. Garrison "
        "et al. 2025), still without avoidance.",
    )
    pdf.numbered_item(
        5,
        "Mortality M (adds Pavoid and Pmanoeuvre -- the most influential and "
        "most uncertain factors).",
    )

    pdf.callout_box(
        "The cardinal rule of the standard",
        (
            "Each probability adjustment (Pstrikedepth, Pleth, Pavoid, "
            "Pmanoeuvre) must be a DISCRETE, OPTIONAL module, and results "
            "must ALSO be presented WITHOUT that adjustment. This is what "
            "makes assessments with very different data richness comparable. "
            "Comparability -- not a single 'correct' model -- is the goal."
        ),
        colour=ReportPDF.ACCENT_BLUE,
    )

    pdf.subsection_title("2.2  Recommended data conventions")
    pdf.bullet("Grid: ~1 km, EASE-Grid 2 preferred, or 1/100 degree lat/long.")
    pdf.bullet(
        "Traffic metric: VTD = distance travelled per km^2 (km^-1 yr^-1), "
        "monthly when seasonal."
    )
    pdf.bullet(
        "Speed: retain fine detail -- 1-knot bins where possible; report "
        "categories <=10, 10-12, 12-15, >15 knots."
    )
    pdf.bullet(
        "Size: Small craft (<19.8 m); Small ship (>19.8 m, <500 GT); "
        "Medium (500-10,000 GT); Large (>10,000 GT)."
    )
    pdf.bullet(
        "Type: 12 AIS categories (bulk, container, cruise, ferry, fishing, "
        "gov/research, passenger, pleasure, sailing, tanker, tug, other)."
    )
    pdf.bullet(
        "Density: report whether absolute or relative; if relative, give "
        "the proportion of the population within the study area."
    )
    pdf.bullet(
        "Uncertainty: propagate via Monte Carlo; map coefficients of "
        "variation; run sensitivity analyses on Pavoid / Pmanoeuvre."
    )
    pdf.bullet(
        "Non-AIS traffic: correct for it, or present AIS-required vessels "
        "separately from best-estimate all-traffic."
    )
    pdf.bullet(
        "Exposure first: report the raw exposure / co-occurrence per cell "
        "BEFORE any speed-lethality weighting, then add the weighted layer "
        "as a separate, optional output (reinforced by the lead author)."
    )

    pdf.callout_box(
        "Speed is more than lethality",
        (
            "The lead author stresses that the probability of a strike being "
            "LETHAL (Pleth) is only one, relatively small, component of the "
            "overall speed-risk relationship. Vessel speed also raises the "
            "encounter rate and erodes both whale and vessel avoidance "
            "(Pavoid, Pmanoeuvre). A speed-risk story told through Pleth "
            "alone -- as our single speed_lethality term does -- understates "
            "the true effect of slowing down."
        ),
        colour=ReportPDF.ACCENT_AMBER,
    )

    # ── 3. Overlap ────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("3. Overlap -- Where We Already Align")

    pdf.body_text(
        "Encouragingly, the platform was built on much of the same "
        "literature the standard codifies. The following ten alignments "
        "mean we are already speaking the same scientific language; the "
        "work in Section 6 is mostly about re-packaging, not rebuilding."
    )

    overlap_rows = [
        (
            "AIS traffic core",
            "VTD from AIS is the backbone of risk",
            "9.7 M cell-months from MarineCadastre AIS; aggregate_ais.py "
            "rolls 3.1 B pings into the H3 grid",
        ),
        (
            "V&T speed-lethality",
            "Pleth via Vanderlaan & Taggart (2007) logistic",
            "Already implemented as the speed_lethality traffic component "
            "(vessel-weighted, debiased) -- the single highest traffic "
            "weight (20%)",
        ),
        (
            "Strike-zone reasoning",
            "Pstrikedepth via Sz = WH + D x Prop (draft)",
            "draft_risk and draft_risk_fraction components encode the "
            "vertical strike zone from vessel draft (OLS-imputed where "
            "missing)",
        ),
        (
            "Fine grid ~1 km",
            "EASE-Grid 2 / 1/100 deg, ~1 km",
            "H3 resolution 7 (~1.22 km edge) -- same order, fine enough "
            "for ship-routeing detail",
        ),
        (
            "Relative density OK",
            "Relative indices explicitly permitted",
            "Our percentile-rank composite is a relative index; the paper "
            "cites Bedrinana-Romano and Nisi as valid relative-density "
            "examples",
        ),
        (
            "Nisi et al. 2024",
            "Cited as a global strike-risk benchmark",
            "nisi_risk_grid is a reference sub-score; the ISDM ensemble is "
            "trained on Nisi's data (a co-author of the standard)",
        ),
        (
            "Seasonality",
            "Monthly aggregation when seasonal",
            "Seasonal marts at (h3_cell, season) grain; monthly traffic "
            "table (9.2 M rows)",
        ),
        (
            "Vessel type & size",
            "Stratify by type and size category",
            "Vessel-type codes, large_vessels and commercial components; "
            "macro grid carries 6 traffic sub-metrics",
        ),
        (
            "Co-occurrence logic",
            "Whale x traffic overlap is the base index",
            "ML mart's interaction_score = P(any whale) x traffic_score "
            "is exactly Rockwood et al. (2021) co-occurrence",
        ),
        (
            "Night-time risk",
            "Diel dive shifts raise night strike risk",
            "night_traffic component up-weights night transits "
            "(Calambokidis et al. 2019 blue-whale finding)",
        ),
    ]
    pdf.metric_table(
        ["Theme", "Standard says", "Our pipeline"],
        overlap_rows,
        col_widths=[34, 56, 100],
        body_font=8,
    )

    pdf.callout_box(
        "Strongest credibility anchors",
        (
            "(1) We already run the V&T 2007 speed-lethality logistic -- the "
            "exact Pleth lineage the standard endorses. (2) Nisi et al. 2024 "
            "is both a standard reference AND the training source for our "
            "ISDM models, so our whale layer is methodologically inside the "
            "standard's accepted set."
        ),
        colour=ReportPDF.ACCENT_GREEN,
    )

    # ── 4. Issues ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("4. Issues -- Where We Diverge or Fall Short")

    pdf.body_text(
        "These are the gaps between our current outputs and a "
        "standard-compatible assessment. They are ordered roughly by how "
        "much they affect comparability. None invalidate the platform; "
        "they define the migration scope in Section 6."
    )

    issue_rows = [
        (
            "1",
            "Additive, not multiplicative",
            "Weighted SUM of 7 percentile sub-scores vs the standard's "
            "multiplicative module chain (R, N, I, M). Our index is neither "
            "an encounter rate nor a mortality estimate.",
            "High",
        ),
        (
            "2",
            "No modular stage outputs",
            "We emit one 0-1 number; the standard wants R, N, I and M "
            "reported separately so each adjustment can be added/removed.",
            "High",
        ),
        (
            "3",
            "No absolute density",
            "Relative density only -> cannot estimate interactions or "
            "mortality. Standard accepts this but asks for proportion of "
            "population within the area; we do not report it.",
            "High",
        ),
        (
            "4",
            "No Pavoid / Pmanoeuvre",
            "We model no whale or vessel avoidance. The paper flags Pavoid "
            "as the single most influential (and most uncertain) factor.",
            "Med",
        ),
        (
            "5",
            "No explicit contact width w",
            "We never compute w = BS + 0.64*WL (or BS + WL). Traffic threat "
            "is a percentile blend, not a strip-transect encounter rate.",
            "Med",
        ),
        (
            "6",
            "Pstrikedepth is a proxy",
            "draft_risk approximates the strike zone but lacks "
            "species-specific dive-time-at-depth telemetry and the "
            "propeller-suction coefficient.",
            "Med",
        ),
        (
            "7",
            "Traffic units differ",
            "We count vessels / pings; the standard's preferred metric is "
            "distance travelled per km^2 (VTD, km^-1).",
            "Med",
        ),
        (
            "8",
            "No uncertainty propagation",
            "No Monte Carlo, no CV maps. Percentile ranking hides the "
            "density and lethality uncertainty the standard wants surfaced.",
            "Med",
        ),
        (
            "9",
            "Terminology mismatch",
            "Our names (traffic threat, exposure, proximity blend) do not "
            "map cleanly to the standard's Table 1 (Encounter, Interaction, "
            "VTD, Pleth, Sz, w).",
            "Low",
        ),
        (
            "10",
            "Non-AIS vessels",
            "AIS-only; small craft under-represented. Standard asks for a "
            "correction factor or an explicit AIS-required-only output.",
            "Low",
        ),
        (
            "11",
            "Grid system interop",
            "H3 hexagons vs EASE-Grid 2 / 1/100 deg squares -- a re-binning "
            "step is needed to exchange data with other studies.",
            "Low",
        ),
        (
            "12",
            "Speed-risk reduced to lethality",
            "We express vessel speed mainly through the V&T Pleth term. The "
            "lead author notes lethality is only a small part of the "
            "speed-risk relationship -- speed also drives encounter rate and "
            "avoidance -- so our single speed_lethality weight "
            "under-represents the benefit of slowing down.",
            "Med",
        ),
    ]
    pdf.metric_table(
        ["#", "Gap", "Detail", "Impact"],
        issue_rows,
        col_widths=[8, 40, 116, 16],
        body_font=8,
    )

    pdf.callout_box(
        "Framing for the experts",
        (
            "The composite index was designed for VISUALISATION and "
            "PRIORITISATION across many species and a continental domain, "
            "not for population-mortality estimation in one area. The gaps "
            "above are therefore expected: they are the price of breadth. "
            "The fix is additive -- a parallel module-chain output for any "
            "area/species where density and dive data support it."
        ),
        colour=ReportPDF.ACCENT_AMBER,
    )

    # ── 5. Crosswalk ──────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("5. Terminology & Module Crosswalk")

    pdf.body_text(
        "A direct mapping between the standard's terms (Table 1 / Figure 1 "
        "of the paper) and our pipeline artefacts. This table is itself the "
        "first migration deliverable -- shipping it as metadata makes our "
        "outputs legible to anyone working to the standard."
    )

    crosswalk_rows = [
        (
            "Dw (whale density)",
            "Relative",
            "int_cetacean_density; ISDM+SDM ensemble P(whale) in fct_collision_risk_ml",
        ),
        (
            "VTD (travelled density)",
            "Partial",
            "int_vessel_traffic (counts/pings today; distance-travelled "
            "is the migration target)",
        ),
        (
            "w (contact-zone width)",
            "Missing",
            "Not computed -- needs vessel beam + species whale length",
        ),
        (
            "Encounter rate R",
            "Missing",
            "Not emitted as a discrete output",
        ),
        (
            "Pstrikedepth",
            "Proxy",
            "draft_risk / draft_risk_fraction (no dive telemetry yet)",
        ),
        (
            "Sz (strike zone)",
            "Proxy",
            "Implicit in draft components; not the explicit WH + D x Prop",
        ),
        (
            "Interactions N",
            "Missing",
            "Not emitted (would be R x Pstrikedepth)",
        ),
        (
            "Pleth (lethality)",
            "Yes",
            "speed_lethality (V&T 2007); upgrade path = Garrison et al. 2025",
        ),
        (
            "Mortality Index I",
            "Partial",
            "Speed-weighted traffic exists but not as a standalone I = N x "
            "Pleth output",
        ),
        (
            "Pavoid / Pmanoeuvre",
            "Missing",
            "Not modelled",
        ),
        (
            "Mortality M",
            "Missing",
            "Out of scope for a relative-index platform (today)",
        ),
        (
            "Proportion of population",
            "Missing",
            "Not reported; cheap to add where abundance estimates exist",
        ),
    ]
    pdf.metric_table(
        ["Standard term", "Status", "Where it lives (or would) in our stack"],
        crosswalk_rows,
        col_widths=[48, 22, 120],
        body_font=8,
    )

    pdf.small_text(
        "Status legend: Yes = implemented to the standard's intent; "
        "Partial = present but in a different form/units; Proxy = an "
        "approximation stands in; Missing = not currently produced."
    )

    # ── 6. Migration & improvement plan ───────────────────────────
    pdf.add_page()
    pdf.section_title("6. Migration & Improvement Plan")

    pdf.body_text(
        "A four-phase plan, ordered by value-to-effort. Phases 1-2 deliver "
        "most of the comparability benefit at low cost and keep the "
        "existing composite untouched. Phases 3-4 add genuine "
        "encounter-rate and mortality capability for focused study areas."
    )

    pdf.subsection_title("Phase 1 -- Re-package what we already have (low effort)")
    pdf.bullet(
        "Publish the Section 5 crosswalk as machine-readable metadata "
        "(a seed table + an API field) so our terms map to the standard."
    )
    pdf.bullet(
        "Emit an AIS-required-only traffic layer alongside best-estimate "
        "all-traffic (filter by SOLAS size thresholds already in the data)."
    )
    pdf.bullet(
        "Document the modular structure explicitly: surface speed_lethality "
        "(Pleth-like) and draft_risk (Pstrikedepth-like) as labelled, "
        "toggleable layers in the dashboard and API."
    )
    pdf.bullet(
        "Report raw exposure (whale x vessel co-occurrence) per cell as the "
        "BASE layer BEFORE any V&T speed-lethality weighting, then expose the "
        "speed-weighted layer as an optional overlay (explicit request from "
        "the standard's lead author; satisfies the with/without rule)."
    )

    pdf.subsection_title("Phase 2 -- Standard-compatible traffic metric (medium)")
    pdf.bullet(
        "Compute true VTD (distance travelled per km^2) in aggregate_ais.py "
        "from consecutive AIS positions, not just ping counts."
    )
    pdf.bullet(
        "Bin speed into the standard's categories (<=10, 10-12, 12-15, >15 "
        "kn) and retain 1-knot resolution upstream."
    )
    pdf.bullet(
        "Adopt the standard's 4 size classes and 12 type classes as "
        "first-class stratifiers in the traffic mart."
    )
    pdf.bullet(
        "Upgrade Pleth from V&T 2007 to Garrison et al. (2025) -- the lead "
        "author's recommended update, re-estimated on a much larger dataset; "
        "adds vessel size category, whale taxon, and the speed x taxon "
        "interaction (humpbacks significantly less lethal)."
    )
    pdf.bullet(
        "Treat speed as a multi-pathway driver, not just a lethality knob: "
        "document that speed also affects encounter rate and avoidance, so "
        "the speed_lethality term is a lower bound on the value of slowing."
    )

    pdf.ln(2)
    pdf.callout_box(
        "Implementation status (2026): Phases 1b + 2 are LIVE",
        "True VTD (track-km/km^2) is now computed in aggregate_ais.py via "
        "great-circle segment apportionment (11.58M joint strata), and the "
        "speed-lethality term has been upgraded from V&T (2007) to Garrison "
        "et al. (2025) using the real Table 3 coefficients (generic B1 = "
        "0.129/kn; humpback B1 = 0.026/kn). The traffic score is rebased on "
        "VTD exposure + Garrison lethality percentiles; V&T is retained as a "
        "diagnostic. Jensen bias is negligible (rho = 0.9975, mean |bias| = "
        "0.0027 over 11.58M cell-months). See the Tranche 1 Phase 2 "
        "migration report for the full treatment.",
        ReportPDF.ACCENT_GREEN,
    )

    pdf.subsection_title("Phase 3 -- A real encounter-rate module (higher)")
    pdf.bullet(
        "Add an optional R = Dw x VTD x w output for a chosen study area "
        "and species, with w = BS + 0.64*WL from vessel beam and published "
        "whale lengths."
    )
    pdf.bullet(
        "Build Pstrikedepth from species dive-time-at-depth distributions "
        "(literature where local telemetry is absent) and Sz = WH + D x Prop."
    )
    pdf.bullet(
        "Emit N = R x Pstrikedepth and I = N x Pleth as discrete, stackable "
        "layers -- the standard's reported outputs 2-4."
    )
    pdf.bullet(
        "Where an abundance estimate exists, report the proportion of the "
        "population predicted to interact annually (the standard's "
        "preferred comparable metric for relative-density studies)."
    )

    pdf.subsection_title("Phase 4 -- Uncertainty & avoidance (research)")
    pdf.bullet(
        "Monte Carlo propagation over density, Pleth and draft parameters; "
        "publish coefficient-of-variation maps alongside risk."
    )
    pdf.bullet(
        "Sensitivity analysis on Pavoid / Pmanoeuvre across plausible bounds "
        "(the factors the standard flags as most influential)."
    )
    pdf.bullet(
        "Optional Pavoid / Pmanoeuvre modules for areas with detection or "
        "behavioural-response data, always reported with and without."
    )
    pdf.bullet(
        "Evaluate the Global Fishing Watch global AIS data product spec "
        "(paper Appendix) for international-domain expansion."
    )

    pdf.subsection_title("Data-source note -- the IWC strike database")
    pdf.body_text(
        "The lead author cautions that the IWC global ship-strike database "
        "contains only a small sample of the US strike record. For a "
        "platform focused on US waters, integrating it would add little "
        "beyond the NOAA / US sources already in the pipeline (our 261 "
        "NOAA-parsed strike records, plus the US AIS and OBIS feeds). We "
        "therefore treat the IWC database as a cross-check and an "
        "international-expansion asset, not a primary US data source -- and "
        "prioritise effort accordingly."
    )

    pdf.ln(2)
    pdf.callout_box(
        "Recommended immediate next step",
        (
            "Do Phase 1 now -- it is mostly metadata and labelling, needs no "
            "new science, and instantly makes our outputs legible to the IWC "
            "community. Two specifics from the lead author: (1) report raw "
            "exposure per cell BEFORE the V&T speed-weighting, and (2) pair "
            "it with the Phase 2 Garrison et al. (2025) Pleth upgrade -- a "
            "clean, larger-dataset swap for our V&T 2007 curve."
        ),
        colour=ReportPDF.ACCENT_GREEN,
    )

    # ── 7. Key takeaways ──────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("7. Key Takeaways")

    takeaways = [
        "The IWC paper is a REPORTING STANDARD for comparability, not a "
        "prescribed model -- our job is to make outputs legible to it, not "
        "to abandon the composite.",
        "We already share its foundations: AIS/VTD, V&T speed-lethality, "
        "draft strike-zone logic, a ~1 km grid, relative-density indices, "
        "and Nisi et al. 2024 (a co-author).",
        "The core divergence is structural -- additive composite vs "
        "multiplicative module chain (R -> N -> I -> M).",
        "Report exposure FIRST: raw whale x vessel co-occurrence per cell is "
        "the base output; the V&T speed-lethality weighting is an optional "
        "overlay on top (explicit request from the standard's lead author).",
        "The cheapest, highest-value work is Phase 1 (terminology "
        "crosswalk, AIS-required-only layer, labelled modular outputs, "
        "with/without toggles).",
        "Upgrading Pleth from V&T 2007 to Garrison et al. 2025 -- a larger, "
        "more recent dataset -- is a clean, high-impact swap that improves "
        "every traffic score.",
        "Speed is more than lethality: it also drives encounter rate and "
        "avoidance, so our single speed_lethality term is a lower bound on "
        "the true benefit of slowing vessels down.",
        "A true encounter-rate module (R = Dw x VTD x w) and Pstrikedepth "
        "from dive telemetry are the medium-term scientific upgrades.",
        "Pavoid / Pmanoeuvre and absolute mortality remain research-grade "
        "and area-specific -- best added as optional modules, never forced.",
        "The IWC strike database is only a small sample of the US record; "
        "for US waters it is a cross-check and an international-expansion "
        "asset, not a primary data source.",
        "Our platform's distinctive strengths (multi-species ML ensemble, "
        "CMIP6 projections, citizen science, fine H3 grid, live dashboard) "
        "sit ABOVE the standard and are fully retained throughout.",
    ]
    for i, t in enumerate(takeaways, 1):
        pdf.numbered_item(i, t)

    pdf.ln(3)
    pdf.subsection_title("Key references (from the standard, relevant to us)")
    pdf.small_text(
        "Leaper et al. (2026) SC/70/HIM/13 -- the standard itself. "
        "Vanderlaan & Taggart (2007) Mar. Mamm. Sci. 23(1):144-156 -- our "
        "current Pleth. Garrison et al. (2025) Front. Mar. Sci. 11:1467387 "
        "-- the recommended Pleth upgrade (size x taxon). Nisi et al. (2024) "
        "Science 386(6724):870-875 -- our ISDM training source. Rockwood et "
        "al. (2021) -- the co-occurrence interaction basis of our ML mart. "
        "Glennie et al. (2015) -- whale-movement bias. Silber et al. (2010) "
        "-- propeller suction / hydrodynamics. Blondin et al. (2025) -- "
        "2D Pstrikedepth and right-whale avoidance. Calambokidis et al. "
        "(2019) -- diel (night) strike vulnerability."
    )

    pdf.output(str(OUTPUT_FILE))
    return OUTPUT_FILE


if __name__ == "__main__":
    out = build_report()
    print(f"Wrote {out}")

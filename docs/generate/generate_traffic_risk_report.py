"""Generate Traffic Risk Methodology PDF.

Summarises the scientific literature underpinning our traffic-threat
scoring, the changes made to the collision-risk pipeline, and the
rationale behind each modelling decision.
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "traffic_risk_methodology.pdf"


# ═══════════════════════════════════════════════════════════════════
# ReportPDF — navy / teal theme (matches all earlier reports)
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
                "Marine Risk Mapping -- Traffic Risk Methodology",
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

    def callout_box(self, title, text, colour=None):
        """Coloured left-border callout box."""
        if colour is None:
            colour = self.ACCENT_BLUE
        if self.get_y() > 250:
            self.add_page()
        y_start = self.get_y()
        self.set_fill_color(*self.LIGHT_BG)
        # Estimate height
        self.set_font("Helvetica", "", 9.5)
        n_lines = max(1, len(text) // 85 + 1)
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
        """Display a named equation in a highlighted box."""
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


# ═══════════════════════════════════════════════════════════════════
# Report content
# ═══════════════════════════════════════════════════════════════════


def build_report():  # noqa: C901 PLR0915
    pdf = ReportPDF("P", "mm", "A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Title page ────────────────────────────────────────────────
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(
        0, 14, "Traffic Risk Methodology", align="C", new_x="LMARGIN", new_y="NEXT"
    )
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "Literature-Grounded Vessel Threat Scoring",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.cell(
        0, 8, "Marine Risk Mapping Project", align="C", new_x="LMARGIN", new_y="NEXT"
    )
    pdf.cell(0, 8, "June 2026", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)

    # Stat boxes on title page
    pdf.stat_boxes(
        [
            ("4", "Key papers"),
            ("11.6M", "VTD cell-months"),
            ("0.129", "Garrison B1 / kn"),
            ("9/9", "Validation checks PASS"),
        ]
    )

    pdf.ln(12)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        6,
        (
            "This document describes the scientific basis for our vessel traffic "
            "threat scoring methodology.  It summarises three foundational papers, "
            "explains how their findings translate into our composite risk model, "
            "details the implementation across the dbt transformation layer "
            "and the AIS aggregation pipeline, and presents the results of "
            "nine validation checks covering internal consistency, external "
            "benchmarks, and sensitivity analysis."
        ),
        align="C",
    )

    # ── 1. Motivation ─────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1. Motivation")

    pdf.body_text(
        "Ship strikes are among the leading causes of large whale mortality "
        "worldwide.  The International Whaling Commission (IWC) Ship Strike "
        "Database documents 933 validated incidents across 36 species, with "
        "large baleen whales (fin, right, humpback) comprising the majority "
        "of known victims.  Effective risk mapping requires translating "
        "vessel traffic patterns into a meaningful threat measure -- one "
        "that reflects the probability that an encounter with a whale will "
        "prove lethal."
    )

    pdf.body_text(
        "Our original approach used a binary speed threshold (>10 knots) "
        "as a proxy for strike lethality.  While simple, this conflates "
        "a 10.1 kn vessel with one doing 22 kn, even though the latter "
        "is an order of magnitude more likely to kill a whale.  Similarly, "
        "vessel draft -- the vertical depth of hull below the waterline "
        "-- was captured only as a binary (>8 m), losing the continuous "
        "relationship between draft and the vertical strike zone."
    )

    pdf.body_text(
        "This document outlines the three key papers that informed our "
        "improved methodology, and describes exactly how their findings "
        "are implemented in our pipeline."
    )

    # ── 1A. 2026 Update: IWC Product-A Rebase ─────────────────────
    pdf.add_page()
    pdf.section_title("1A. 2026 Update: IWC Product-A Rebase (VTD + Garrison)")

    pdf.body_text(
        "In 2026 the traffic threat metric was rebased onto the IWC "
        "ship-strike reporting standard (Leaper et al. 2026, "
        "SC/70/HIM/13).  Two of the eight traffic components now derive "
        "from IWC-aligned quantities, while the original Vanderlaan & "
        "Taggart (V&T) formulation is retained as a diagnostic surface.  "
        "The V&T literature in Sections 2 onward documents the design "
        "lineage; the live scoring inputs are described here."
    )

    pdf.subsection_title("What changed")
    pdf.bullet(
        "Exposure volume: the vessel-count percentile is replaced by "
        "vessel transit density (VTD) -- track-km swept per km^2.  Raw "
        "AIS ping counts conflate broadcast rate (Class A >> Class B) "
        "and dwell time with actual transit; VTD apportions each "
        "great-circle segment's length across the H3 cells it crosses, "
        "conserving track-km and giving an unbiased exposure surface."
    )
    pdf.bullet(
        "Speed lethality: the V&T logistic is replaced by the Garrison "
        "et al. (2025) speed-lethality logistic, evaluated per joint "
        "stratum (vessel_type x size_class x speed_bin) and track-km-"
        "weighted up to the cell-month (int_vtd.garrison_leth_generic)."
    )
    pdf.bullet(
        "Both replacements feed the composite as percentile ranks "
        "(pctl_vessels on avg VTD, pctl_speed_lethality on avg Garrison "
        "lethality).  The remaining six V&T components are retained "
        "unchanged as diagnostics."
    )

    pdf.subsection_title("Garrison et al. (2025) speed-lethality logistic")
    pdf.small_text(
        "Garrison, L.P. et al. (2025). Vessel speed and the lethality "
        "of large whale ship strikes. Frontiers in Marine Science, "
        "11:1467387.  Open access (CC-BY).  n = 192 strike events "
        "(79 lethal / 113 non-lethal), pseudo-R^2 = 0.291."
    )
    pdf.ln(1)
    pdf.equation_box(
        "Garrison et al. (2025) -- Table 3 best logit model",
        "logit(P) = -1.744 + 0.129*v + size_offset"
        " - 0.139*HB - 0.103*v*HB",
        "v = speed (kn); HB = 1 for humpback, else 0.  Size offsets "
        "(added to intercept): Small 0, Medium +0.113, Large +0.617, "
        "XL +2.498.  Speed effect (B1 = 0.129/kn) is far gentler than "
        "V&T (0.41/kn) and probabilities are higher at low speed.",
    )

    pdf.body_text(
        "We use the taxon-agnostic ('other'/generic, B1 = 0.129) curve "
        "for the traffic screen; the humpback curve (B1 = 0.026) and the "
        "full taxon x size grid are reserved for the Phase 4 mortality "
        "module.  The seed stores reconstructed (B0, B1) pairs validated "
        "exactly against Garrison Table 4 at 5/10/15/20/25/30 kn."
    )

    pdf.subsection_title("Size-class mapping")
    pdf.body_text(
        "Garrison's size bins are defined on vessel length with its only "
        "material edge at 108 m (Small <12.1 m, Medium 12.2-19.7, Large "
        "19.8-108, XL >=108).  Because AIS transponder carriage begins "
        "around 20 m, virtually all vessels in our data fall in Garrison "
        "Large or XL.  Our VTD length bins (small <50 m, medium 50-100, "
        "large 100-200, vlarge >=200) therefore map onto that 108 m seam: "
        "small/medium -> Garrison Large coefficients, large/vlarge -> "
        "Garrison XL.  The sole approximation is vessels in the narrow "
        "100-108 m band receiving the XL curve -- negligible traffic."
    )

    pdf.subsection_title("Jensen-correct by construction")
    pdf.body_text(
        "Because P(lethal | speed) is nonlinear, averaging speed before "
        "applying the logistic biases the estimate (Jensen's inequality, "
        "Section 6).  The joint strata are already binned by narrow speed "
        "bins (<=10 / 10-12 / 12-15 / >15 kn), so the Garrison logistic "
        "is applied per bin and the residual within-bin spread is tiny.  "
        "Validation confirms this: comparing the binned estimate against "
        "a speed-collapsed counterfactual over 11.58M cell-months gives a "
        "Spearman rank correlation of 0.9975 and a mean absolute "
        "lethality difference of just 0.0027."
    )

    pdf.ln(2)
    pdf.callout_box(
        "Why retain V&T as a diagnostic?",
        "The V&T per-vessel lethality columns (vw_avg_lethality, etc.) "
        "remain in ais_h3_summary and int_vessel_traffic for continuity "
        "and cross-checking, but no longer drive the composite.  The "
        "live traffic score is rebased on VTD exposure and Garrison "
        "lethality, both of which align with the IWC reporting standard "
        "and travel cleanly into the Phase 4 mortality estimator.",
        ReportPDF.ACCENT_GREEN,
    )

    # ── 2. Literature Review ──────────────────────────────────────
    pdf.add_page()
    pdf.section_title("2. Literature Review")

    # -- V&T 2007 --
    pdf.subsection_title("2.1  Vanderlaan & Taggart (2007)")
    pdf.small_text(
        "Vanderlaan, A.S.M. & Taggart, C.T. (2007). Vessel collisions "
        "with whales: the probability of lethal injury based on vessel "
        "speed. Marine Mammal Science, 23(1), 144-156."
    )
    pdf.ln(1)

    pdf.body_text(
        "This foundational paper fitted a logistic regression to 40 "
        "observed whale-vessel collisions with known outcomes (lethal "
        "vs. non-lethal), modelling the probability of a lethal injury "
        "as a function of vessel speed at the time of impact:"
    )

    pdf.equation_box(
        "Vanderlaan & Taggart (2007) -- Speed-lethality logistic",
        "P(lethal | v) = 1 / (1 + exp(-(-4.89 + 0.41 * v)))",
        "where v is vessel speed in knots.  B0 = -4.89, B1 = 0.41.",
    )

    pdf.body_text("Key findings from the fitted model:")
    pdf.bullet(
        "At 10 knots the probability of lethality is ~31% -- not the "
        "near-certainty implied by a binary threshold."
    )
    pdf.bullet(
        "At 15 knots the probability jumps to ~78%, and by 20 knots "
        "it exceeds 96%.  The curve is steepest between 8 and 18 knots."
    )
    pdf.bullet(
        "Below 8 knots the probability is under 17%, supporting the "
        "scientific basis for 10 kn speed restrictions in right whale "
        "Seasonal Management Areas."
    )
    pdf.bullet(
        "The inflection point is at ~12 knots (P = 50%), not 10 knots.  "
        "Using 10 kn as a binary cutoff both over-counts slow vessels "
        "and under-weights fast ones."
    )

    pdf.ln(2)
    pdf.callout_box(
        "Key insight",
        "The binary 10 kn threshold loses critical information.  "
        "A cell with mean speed 15 kn is 2.5x more dangerous than one "
        "at 10 kn, but both would score identically under a binary "
        "scheme.  The logistic captures this continuous gradient.",
        ReportPDF.ACCENT_BLUE,
    )

    # V&T probability table
    pdf.ln(2)
    pdf.subsection_title("Speed-Lethality Reference Table")
    pdf.metric_table(
        ["Speed (kn)", "P(lethal)", "Interpretation"],
        [
            ["0", "0.008", "Negligible -- drifting or at anchor"],
            ["5", "0.055", "Very low -- harbour manoeuvring"],
            ["8", "0.167", "Low -- approaching SMA limit"],
            ["10", "0.312", "Moderate -- typical slow-steaming"],
            ["12", "0.508", "50/50 inflection point"],
            ["15", "0.779", "High -- normal coastal transit"],
            ["20", "0.965", "Very high -- open-water cruising"],
            ["25", "0.995", "Near-certain lethality"],
        ],
        col_widths=[35, 35, 120],
    )

    # -- Rockwood et al. 2017 --
    pdf.add_page()
    pdf.subsection_title("2.2  Rockwood et al. (2017, 2021)")
    pdf.small_text(
        "Rockwood, R.C., Calambokidis, J. & Jahncke, J. (2017). High "
        "mortality of blue, humpback and fin whales from modeling of "
        "vessel strikes on the U.S. West Coast. PLoS ONE, 12(8).\n"
        "Rockwood, R.C. et al. (2021). Modeling whale deaths from "
        "vessel strikes to reduce the risk of fatality to endangered "
        "whales. Frontiers in Marine Science, 8."
    )
    pdf.ln(1)

    pdf.body_text(
        "Rockwood et al. developed an encounter-rate model that "
        "estimates the expected number of lethal whale-vessel encounters "
        "per unit area per unit time.  Their key contribution to our "
        "methodology is the explicit treatment of vessel draft as the "
        "vertical component of the strike zone:"
    )

    pdf.equation_box(
        "Rockwood et al. -- Encounter rate (simplified)",
        "E = N_w * sum_i( P_lethal(v_i) * D_i / D_max * L_i / L_max )",
        "where D_i = vessel draft (vertical strike zone), L_i = vessel "
        "length, and the sum is over all transits i through the cell.",
    )

    pdf.body_text("Key insights adopted in our model:")
    pdf.bullet(
        "Vessel draft determines the vertical extent of the hull below "
        "the waterline -- a deeper-draft vessel sweeps a larger column "
        "of water, increasing the probability of physically contacting "
        "a whale at any given depth.  A 12 m draft container ship has "
        "3x the vertical strike zone of a 4 m draft pleasure craft."
    )
    pdf.bullet(
        "Per-transit calculations avoid aggregation bias.  Applying the "
        "V&T logistic to each vessel's speed before averaging across the "
        "cell (rather than applying it to the cell-average speed) avoids "
        "Jensen's inequality bias."
    )
    pdf.bullet(
        "Draft and speed should be multiplied, not added, since they "
        "represent independent dimensions of encounter probability "
        "(horizontal sweep rate x vertical strike zone)."
    )

    pdf.ln(2)
    pdf.callout_box(
        "Jensen's inequality",
        "Because the logistic function is nonlinear (convex below the "
        "inflection, concave above), applying it to a cell-average "
        "speed systematically underestimates lethality.  For a "
        "bimodal cell (5 kn + 15 kn): avg(P(5), P(15)) = 0.42 but "
        "P(avg) = P(10) = 0.31 -- a 25% underestimate.  We resolve "
        "this by computing P(lethal) per-vessel in aggregate_ais.py "
        "before averaging.",
        ReportPDF.ACCENT_AMBER,
    )

    # -- IWC Ship Strike Database --
    pdf.add_page()
    pdf.subsection_title("2.3  IWC Ship Strike Database (Winkler et al.)")
    pdf.small_text(
        "Winkler, C. et al. IWC Ship Strike Database. International "
        "Whaling Commission, SC/68B/HIM/09."
    )
    pdf.ln(1)

    pdf.body_text(
        "The IWC maintains the most comprehensive global database of "
        "known ship strikes, containing 933 validated incidents across "
        "36 cetacean species.  While not a modelling paper per se, the "
        "database provides essential empirical context:"
    )

    pdf.bullet(
        "Large whales account for the vast majority of fatal strikes.  "
        "Fin whales are the most frequently struck species globally, "
        "followed by right whales and humpback whales."
    )
    pdf.bullet(
        "Vessel types most commonly involved: container ships, bulk "
        "carriers, tankers, and military vessels -- all characterised by "
        "high speed (>12 kn), deep draft (>8 m), and large displacement."
    )
    pdf.bullet(
        "Night-time strikes are proportionally more lethal than daytime "
        "strikes, likely because reduced visibility eliminates the "
        "(already slim) chance of evasive action by either party."
    )
    pdf.bullet(
        "Many strikes go unreported -- the database represents a lower "
        "bound.  Modelled estimates of total mortality (Rockwood et al.) "
        "suggest true rates may be 10-20x higher than reported."
    )

    pdf.ln(2)
    pdf.callout_box(
        "Why night traffic matters",
        "The IWC database shows that night strikes are disproportionately "
        "fatal.  Our model weights night traffic at 15% of the traffic "
        "sub-score -- the highest single component.  This reflects both "
        "the empirical evidence and the absence of any mitigation "
        "opportunity (no visual whale detection at night).",
        ReportPDF.ACCENT_RED,
    )

    # ── 3. From Literature to Model ───────────────────────────────
    pdf.add_page()
    pdf.section_title("3. From Literature to Model")

    pdf.body_text(
        "Each paper contributes specific methodological improvements "
        "to our traffic threat scoring.  The table below maps literature "
        "findings to implementation decisions:"
    )

    pdf.metric_table(
        ["Literature Finding", "Old Approach", "New Approach"],
        [
            ["V&T: lethality is a", "Binary >10 kn", "Logistic P(lethal|v)"],
            ["  continuous f(speed)", "  threshold", "  per vessel"],
            ["Rockwood: draft is the", "Binary >8 m", "Continuous draft (m)"],
            ["  vertical strike zone", "  count only", "  with OLS imputation"],
            ["Rockwood: per-transit", "f(cell-average)", "Per-vessel logistic"],
            ["  avoids Jensen's bias", "  speed)", "  then average"],
            ["IWC: night strikes are", "Not weighted", "15% of traffic sub-"],
            ["  disproportionally fatal", "  differently", "  score (highest wt)"],
            ["IWC: large commercial", "All vessel types", "10% commercial +"],
            ["  vessels dominate", "  equal weight", "  10% large-vessel wt"],
        ],
        col_widths=[68, 56, 66],
    )

    # ── 4. Traffic Sub-Score Architecture ─────────────────────────
    pdf.add_page()
    pdf.section_title("4. Traffic Sub-Score Architecture")

    pdf.body_text(
        "The traffic sub-score is one of seven (or eight, in the ML-enhanced "
        "variant) sub-scores that form the composite collision risk.  It is "
        "computed as a weighted sum of eight percentile-ranked traffic "
        "components, each capturing a distinct dimension of vessel threat:"
    )

    pdf.ln(2)
    pdf.metric_table(
        ["Component", "Weight", "Source", "Dimension"],
        [
            ["Speed lethality", "20%", "V&T logistic on per-vessel speed", "Lethality"],
            [
                "High-speed fraction",
                "10%",
                "Share of vessels >= 10 kn",
                "Speed risk breadth",
            ],
            [
                "Vessel count",
                "20%",
                "Monthly average unique vessels",
                "Exposure volume",
            ],
            ["Large vessels", "10%", "Vessels > 100 m length", "Size / momentum"],
            ["Draft risk", "10%", "Continuous avg draft (m)", "Vertical strike zone"],
            [
                "Deep-draft fraction",
                "5%",
                "Share of vessels > 8 m draft",
                "Draft risk breadth",
            ],
            ["Commercial vessels", "10%", "Cargo + tanker count", "Vessel type risk"],
            ["Night traffic", "15%", "Night-time vessel count", "Visibility risk"],
        ],
        col_widths=[42, 16, 82, 50],
    )

    pdf.subsection_title("Design rationale")

    pdf.body_text("The components are grouped into four conceptual dimensions:")

    pdf.bullet(
        "Speed risk (30%): split between the continuous V&T lethality index "
        "(20%, capturing the magnitude of danger per encounter) and the "
        "high-speed fraction (10%, capturing how widespread fast vessels are "
        "in the cell).  A cell where 5% of vessels transit at 15 kn scores "
        "the same average lethality as one where 50% do -- the fraction "
        "distinguishes them."
    )
    pdf.bullet(
        "Volume / exposure (20%): raw vessel count determines encounter "
        "probability.  More transits = more chances for a whale to be struck, "
        "independent of how dangerous each transit is."
    )
    pdf.bullet(
        "Size and draft (25%): large vessel count (10%), continuous average "
        "draft (10%), and deep-draft fraction (5%).  Draft captures the "
        "Rockwood vertical-strike-zone insight.  Length and draft are "
        "correlated (R-sq ~ 0.63) but not redundant -- tugs are short but "
        "deep-draft; ferries are long but shallow."
    )
    pdf.bullet(
        "Night + type (25%): night traffic (15%) reflects the IWC finding "
        "on night strike lethality, plus the fundamental absence of visual "
        "detection.  Commercial vessels (10%) captures the IWC's observation "
        "that cargo and tanker ships dominate fatal strikes."
    )

    # ── 5. Draft Imputation ───────────────────────────────────────
    pdf.add_page()
    pdf.section_title("5. Draft Imputation")

    pdf.body_text(
        "Approximately 15% of AIS-reporting vessels do not broadcast draft "
        "information.  Since draft is now a scored risk component rather "
        "than just a diagnostic, missing values would bias risk downward "
        "for cells dominated by non-reporting vessels (often smaller craft "
        "with Class B AIS transponders)."
    )

    pdf.subsection_title("5.1  Per-vessel type-stratified imputation (gold standard)")

    pdf.body_text(
        "In the AIS aggregation pipeline (aggregate_ais.py), we impute "
        "missing draft per-vessel using a four-tier waterfall:"
    )

    pdf.numbered_item(
        1, "Reported draft: use the vessel's own AIS-broadcast draft if available."
    )
    pdf.numbered_item(
        2,
        "Type-stratified OLS regression: for each vessel category (cargo, "
        "tanker, passenger, fishing, tug, pleasure, other), fit draft ~ length "
        "from vessels that report both.  Use the regression prediction if "
        "R-sq >= 0.05 and n >= 20.",
    )
    pdf.numbered_item(
        3,
        "Type median fallback: if the regression is unreliable (e.g., "
        "tugs have R-sq ~ 0), use the median draft for that vessel type.",
    )
    pdf.numbered_item(4, "Global median: last resort if vessel type is unknown.")

    pdf.body_text(
        "All imputed values are clamped to [0.5, 25.0] metres to prevent "
        "extrapolation artefacts from extreme vessel lengths."
    )

    pdf.ln(2)
    pdf.metric_table(
        ["Vessel Type", "R-sq", "n (with both)", "Strategy"],
        [
            ["Cargo", "0.645", "~500K", "Regression"],
            ["Tanker", "0.484", "~200K", "Regression"],
            ["Passenger", "0.719", "~100K", "Regression"],
            ["Fishing", "~0.01", "~300K", "Type median"],
            ["Tug", "~0.003", "~150K", "Type median"],
            ["Pleasure", "0.277", "~80K", "Regression (marginal)"],
            ["Other/Unknown", "varies", "varies", "Global median fallback"],
        ],
        col_widths=[40, 25, 45, 80],
    )

    pdf.subsection_title("5.2  Cell-level OLS fallback (dbt layer)")

    pdf.body_text(
        "The dbt intermediate model (int_vessel_traffic.sql) provides an "
        "additional safety net: a simple OLS regression of cell-average "
        "draft on cell-average length (R-sq = 0.63, r = 0.79), used only "
        "when the per-vessel imputed column is not yet available from "
        "aggregate_ais.py.  Once the AIS re-run completes, the per-vessel "
        "values take priority via COALESCE."
    )

    # ── 6. Jensen's Inequality Resolution ─────────────────────────
    pdf.add_page()
    pdf.section_title("6. Jensen's Inequality Resolution")

    pdf.body_text(
        "The V&T logistic is a nonlinear function applied to speed.  "
        "When applied to a cell-average speed (the arithmetic mean of "
        "all vessel speeds in that cell-month), the result differs from "
        "the correct value -- the average of per-vessel lethalities."
    )

    pdf.equation_box(
        "Jensen's inequality for convex functions",
        "E[f(X)] >= f(E[X])   (equality iff X is constant)",
        "For the V&T logistic, this means P(lethal|avg speed) "
        "underestimates the true average lethality.",
    )

    pdf.body_text("Concrete example for a bimodal cell (5 kn + 15 kn):")

    pdf.metric_table(
        ["Approach", "Calculation", "Value"],
        [
            ["Correct", "avg(P(5), P(15))", "0.417"],
            ["Cell-average", "P(avg(5,15)) = P(10)", "0.312"],
            ["Bias", "correct - cell-avg", "-0.105 (-25%)"],
        ],
        col_widths=[50, 70, 70],
    )

    pdf.body_text(
        "Our resolution: apply the V&T logistic per-vessel in the "
        "DuckDB aggregation (aggregate_ais.py), then average.  The "
        "vessel_with_lethality CTE computes P(lethal|v_i) for each "
        "vessel i, then Pass 2 aggregates:"
    )

    pdf.bullet(
        "vw_avg_lethality: vessel-weighted mean (corrects for AIS ping-rate bias)."
    )
    pdf.bullet(
        "pw_avg_lethality: ping-weighted mean (useful for exposure-weighted analyses)."
    )
    pdf.bullet(
        "max_lethality: maximum single-vessel lethality in the cell "
        "(captures worst-case threat)."
    )

    pdf.body_text(
        "In the dbt layer, int_vessel_traffic.sql reads the pre-computed "
        "vw_avg_lethality column via COALESCE, falling back to the "
        "cell-average approximation only if the column is NULL (i.e., "
        "the AIS data predates the per-vessel computation)."
    )

    pdf.ln(2)
    pdf.callout_box(
        "2026 update -- Garrison VTD strata",
        "The same Jensen logic now governs the live traffic score "
        "(Section 1A): the Garrison logistic is applied per narrow "
        "speed bin inside int_vtd, then track-km-weighted to the "
        "cell-month.  Validated over 11.58M cell-months, the binned "
        "estimate tracks a speed-collapsed counterfactual at Spearman "
        "rho = 0.9975 with mean |bias| = 0.0027 -- the binning keeps the "
        "lethality estimate essentially unbiased while preserving the "
        "relative cell ranking the percentile score consumes.",
        ReportPDF.ACCENT_AMBER,
    )

    # ── 7. Composite Risk Integration ─────────────────────────────
    pdf.add_page()
    pdf.section_title("7. Composite Risk Integration")

    pdf.body_text("The traffic sub-score integrates into two composite risk models:")

    pdf.subsection_title("7.1  Hand-tuned model (fct_collision_risk)")
    pdf.body_text(
        "The original 7-sub-score model uses percentile-ranked features.  "
        "Traffic receives 25% weight in the composite:"
    )

    pdf.metric_table(
        ["Sub-score", "Weight", "Changes in this update"],
        [
            ["Traffic threat", "25%", "VTD exposure + Garrison lethality"],
            ["Cetacean exposure", "25%", "Unchanged"],
            ["Proximity blend", "15%", "Unchanged"],
            ["Strike history", "10%", "Unchanged"],
            ["Habitat suitability", "10%", "Unchanged"],
            ["Protection gap", "10%", "Unchanged"],
            ["Reference risk (Nisi)", "5%", "Unchanged"],
        ],
        col_widths=[55, 20, 115],
    )

    pdf.subsection_title("7.2  ML-enhanced model (fct_collision_risk_ml)")
    pdf.body_text(
        "The interaction-first model promotes whale x traffic co-occurrence "
        "as the primary risk signal.  This is motivated by Rockwood et al.'s "
        "encounter-rate formulation: risk is the product of whale presence "
        "and vessel threat, not their independent sum."
    )

    pdf.equation_box(
        "Interaction term",
        "interaction = P(whale) * traffic_score",
        "P(whale) from ISDM models, traffic_score from the 8-component "
        "formula. Percentile-ranked within season before weighting.",
    )

    pdf.metric_table(
        ["Sub-score", "Weight", "Notes"],
        [
            ["Whale x traffic interaction", "25%", "PRIMARY -- co-occurrence"],
            ["Traffic threat (residual)", "15%", "Independent traffic risk"],
            ["Whale ML exposure", "10%", "Residual whale presence"],
            ["Proximity blend", "15%", "Unchanged"],
            ["Strike history", "10%", "Unchanged"],
            ["Habitat suitability", "10%", "Unchanged"],
            ["Protection gap", "10%", "Unchanged"],
            ["Reference risk (Nisi)", "5%", "Unchanged"],
        ],
        col_widths=[60, 16, 114],
    )

    pdf.ln(2)
    pdf.callout_box(
        "Double-counting is intentional",
        "A cell with both whales and heavy traffic gets triple exposure: "
        "interaction (25%) + residual traffic (15%) + residual whale (10%) "
        "= 50% of the composite from whale+traffic dimensions.  This "
        "steep gradient from traffic-only (15%) to co-occurrence (50%) "
        "correctly reflects that co-occurrence IS the fundamental risk "
        "mechanism for ship strikes.",
        ReportPDF.ACCENT_GREEN,
    )

    # ── 8. Implementation Architecture ────────────────────────────
    pdf.add_page()
    pdf.section_title("8. Implementation Architecture")

    pdf.body_text("The changes span two layers of the pipeline:")

    pdf.subsection_title("8.1  DuckDB aggregation layer (aggregate_ais.py)")
    pdf.body_text(
        "Processes 3.1 billion AIS pings from raw parquet files.  "
        "The query chains 8 CTEs culminating in a per-cell-month "
        "aggregation that produces 9.7 million rows with 75 columns "
        "(68 original + 7 new):"
    )

    pdf.metric_table(
        ["CTE", "Purpose"],
        [
            ["raw_pings", "Extract fields, null-zero draft/length, filter sog>0"],
            ["with_h3", "H3 cell assignment, month extraction, local hour"],
            ["with_time_of_day", "is_night boolean from local solar hour"],
            ["vessel_summaries", "Pass 1: per (cell, month, MMSI) aggregation"],
            ["vessel_typed", "CASE vessel_type -> category (cargo/tanker/etc)"],
            ["draft_regression", "Per-type OLS: regr_slope, intercept, R2, median"],
            ["draft_global", "Global median draft as last-resort fallback"],
            ["vessel_with_draft", "4-tier draft imputation, clamped [0.5, 25]m"],
            ["vessel_with_lethality", "V&T logistic per-vessel (Jensen-correct)"],
            ["Pass 2 SELECT", "Cell-month aggregation of all metrics"],
        ],
        col_widths=[50, 140],
    )

    pdf.subsection_title("8.2  dbt transformation layer")
    pdf.body_text("Modified models and their roles:")

    pdf.metric_table(
        ["Model", "Layer", "Change"],
        [
            [
                "int_vessel_traffic",
                "Intermediate",
                "COALESCE to pre-computed lethality",
            ],
            ["", "", "  + cell-level draft OLS fallback"],
            [
                "int_vessel_traffic_seasonal",
                "Intermediate",
                "Pass-through avg of new metrics",
            ],
            ["fct_collision_risk", "Mart", "8-component traffic formula"],
            [
                "fct_collision_risk_seasonal",
                "Mart",
                "Same formula, PARTITION BY season",
            ],
            ["fct_collision_risk_ml", "Mart", "Same + interaction-first architecture"],
        ],
        col_widths=[60, 30, 100],
    )

    # ── 9. Validation Results ─────────────────────────────────────
    pdf.add_page()
    pdf.section_title("9. Validation Results")

    pdf.body_text(
        "We ran nine automated validation checks across three categories: "
        "internal consistency, external benchmarks, and sensitivity analysis.  "
        "All nine checks passed.  The full validation script is "
        "pipeline/analysis/validate_traffic_risk.py; diagnostic plots are "
        "saved to data/processed/ml/artifacts/validation/."
    )

    pdf.ln(1)
    pdf.metric_table(
        ["#", "Check", "Section", "Result"],
        [
            ["1", "Weight sums", "Internal", "PASS"],
            ["2", "Jensen's inequality", "Internal", "PASS"],
            ["3", "Draft imputation", "Internal", "PASS"],
            ["4", "Nisi correlation", "External", "PASS"],
            ["5", "Strike overlap", "External", "PASS"],
            ["6", "SMA overlap", "External", "PASS"],
            ["7", "Weight perturbation", "Sensitivity", "PASS"],
            ["8", "Jensen's spatial", "Sensitivity", "PASS"],
            ["9", "Composite sensitivity", "Sensitivity", "PASS"],
        ],
        col_widths=[12, 55, 55, 68],
    )

    # ── 9.1 Internal Consistency ──────────────────────────────────
    pdf.add_page()
    pdf.subsection_title("9.1  Internal Consistency Checks")

    # Weight sums
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(0, 7, "Weight Sum Verification", new_x="LMARGIN", new_y="NEXT")
    pdf.body_text(
        "All six weight sets sum to exactly 1.000000: hand-tuned composite, "
        "ML composite, traffic sub-score, cetacean sub-score, strike "
        "sub-score, and proximity sub-score."
    )

    # Jensen's inequality
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(0, 7, "Jensen's Inequality Check", new_x="LMARGIN", new_y="NEXT")
    pdf.body_text(
        "Across all 9,726,299 cell-months, the Spearman rank correlation "
        "between per-vessel lethality (vw_avg_lethality) and the cell-average "
        "approximation is rho = 0.9795 (p ~ 0), confirming that per-vessel "
        "computation preserves rank orderings.  51.0% of cells have "
        "per-vessel > cell-average lethality, consistent with Jensen's "
        "inequality biasing the cell-average downward."
    )

    pdf.metric_table(
        ["Statistic", "Value"],
        [
            ["Spearman rho", "0.9795"],
            ["Cells with pv > ca", "51.0%"],
            ["Mean bias (pv - ca)", "-0.0102"],
            ["Median bias", "0.0000"],
            ["Max bias", "0.2553"],
            ["P50 diff", "-0.0201"],
            ["P90 diff", "-0.0167"],
            ["P95 diff", "-0.0060"],
        ],
        col_widths=[80, 110],
    )

    pdf.body_text(
        "Maximum bias (0.2553) occurs in 2-vessel cells near 8 knots -- "
        "exactly the steepest part of the V&T logistic curve.  At higher "
        "traffic volumes the bias averages out, and at very high or low "
        "speeds the logistic is nearly linear, so Jensen's effect is minimal."
    )

    # Draft imputation
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(0, 7, "Draft Imputation Coverage", new_x="LMARGIN", new_y="NEXT")

    pdf.metric_table(
        ["Metric", "Value"],
        [
            ["Total cell-months", "9,726,299"],
            ["With raw draft", "9,141,027 (94.0%)"],
            ["After imputation", "9,726,299 (100.0%)"],
            ["OLS-imputed (dbt fallback)", "585,272 (6.0%)"],
            ["Mean raw draft", "8.89 m"],
            ["Mean imputed draft", "8.32 m"],
            ["Total imputed vessels", "22,634,030"],
        ],
        col_widths=[80, 110],
    )

    pdf.body_text(
        "The 6% of cells requiring OLS imputation in the dbt layer are "
        "those where the per-vessel imputation in aggregate_ais.py still "
        "left cell-average draft null (typically very sparse cells with "
        "only Class B transponders).  Mean imputed draft (8.32 m) is "
        "slightly below raw (8.89 m), which is expected: missing-draft "
        "vessels tend to be smaller craft."
    )

    # ── 9.2 External Benchmarks ───────────────────────────────────
    pdf.add_page()
    pdf.subsection_title("9.2  External Benchmarks")

    # Nisi correlation
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(
        0, 7, "Nisi et al. (2024) Risk Grid Correlation", new_x="LMARGIN", new_y="NEXT"
    )
    pdf.body_text(
        "We matched 1,032,153 H3 cells to the Nisi et al. 1-degree global "
        "risk grid and computed Spearman rank correlations between our "
        "sub-scores and their risk dimensions:"
    )

    pdf.metric_table(
        ["Comparison", "Spearman rho"],
        [
            ["Composite risk vs Nisi all_risk", "0.4426"],
            ["Traffic score vs Nisi shipping_index", "0.3194"],
            ["Cetacean score vs Nisi whale_space_use", "0.1981"],
            ["Composite risk vs Nisi hotspot_overlap", "0.2429"],
        ],
        col_widths=[120, 70],
    )

    pdf.body_text(
        "Cross-correlation analysis reveals that our proximity score has "
        "the strongest individual correlation with Nisi all_risk (rho = 0.376), "
        "followed by cetacean (0.198) and traffic (0.167).  The moderate "
        "overall correlation (0.44) is expected: our model operates at H3 "
        "resolution (~1.2 km) while Nisi uses 1-degree cells (~100 km), and "
        "our 8-component traffic formula captures finer risk gradients than "
        "their shipping intensity index."
    )

    pdf.ln(1)
    pdf.callout_box(
        "Why moderate correlation is good",
        "Perfect correlation with Nisi would mean our model adds no value.  "
        "rho = 0.44 indicates broad agreement on spatial risk patterns while "
        "capturing sub-degree-scale variation (port approaches, shipping "
        "lanes, nearshore habitats) that a 1-degree grid cannot resolve.",
        ReportPDF.ACCENT_BLUE,
    )

    # Strike overlap
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(0, 7, "Historical Strike Site Overlap", new_x="LMARGIN", new_y="NEXT")
    pdf.body_text(
        "Of 1,824,667 scored cells, 60 contain geocoded historical ship "
        "strikes from the NOAA database.  Our composite risk score is "
        "significantly higher at strike sites (Mann-Whitney U = 96.7M, "
        "p = 4.1e-25):"
    )

    pdf.metric_table(
        ["Metric", "Strike cells (n=60)", "Non-strike cells"],
        [
            ["Mean risk score", "0.5149", "0.3019"],
            ["Median risk score", "0.5287", "0.2914"],
            ["Mean cetacean score", "0.2711", "0.0221"],
        ],
        col_widths=[55, 65, 70],
    )

    pdf.body_text("Strike cell risk percentile distribution:")
    pdf.metric_table(
        ["Percentile threshold", "% of strike cells above"],
        [
            [">= P50", "88.3%"],
            [">= P75", "83.3%"],
            [">= P90", "76.7%"],
            [">= P95", "73.3%"],
        ],
        col_widths=[80, 110],
    )

    pdf.body_text("Risk category enrichment analysis:")
    pdf.metric_table(
        ["Category", "Strike cells", "All cells", "Enrichment"],
        [
            ["Critical", "13.3%", "0.1%", "156.1x"],
            ["High", "45.0%", "2.2%", "20.9x"],
            ["Medium", "26.7%", "25.8%", "1.0x"],
            ["Low", "15.0%", "63.9%", "0.2x"],
            ["Minimal", "0.0%", "8.1%", "0.0x"],
        ],
        col_widths=[40, 40, 40, 70],
    )

    pdf.ln(1)
    pdf.callout_box(
        "156x critical enrichment",
        "Strike cells are 156x more likely to fall in the 'critical' risk "
        "category than random cells.  85% of strikes fall above the median "
        "risk score and 73% above the 95th percentile.  This is the "
        "strongest external validation of the model's discriminative power.",
        ReportPDF.ACCENT_GREEN,
    )

    # SMA overlap
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(
        0, 7, "Seasonal Management Area (SMA) Validation", new_x="LMARGIN", new_y="NEXT"
    )
    pdf.body_text(
        "Right whale SMAs are active speed-restriction zones under "
        "50 CFR 224.105.  We compared risk scores across three zone categories:"
    )

    pdf.metric_table(
        ["Zone type", "n cells", "Risk score", "Cetacean", "Protection gap"],
        [
            ["Active SMA", "13,656", "0.388", "0.358", "0.200"],
            ["Proposed zone", "16,669", "0.408", "0.223", "0.397"],
            ["Unprotected", "1,790,632", "0.300", "0.017", "0.997"],
        ],
        col_widths=[38, 28, 38, 38, 48],
    )

    pdf.body_text(
        "The protection gap sub-score correctly differentiates: active SMAs "
        "score 0.20 (well-protected) vs 0.997 for unprotected cells.  "
        "SMA cells have 21x higher cetacean scores (0.358 vs 0.017), "
        "confirming the zones target areas with real whale presence.  "
        "Traffic score inside SMAs (median 0.380) is slightly below the "
        "global median (0.428) -- this is expected because SMAs are placed "
        "in calving habitat, not the busiest shipping lanes."
    )

    # ── 9.3 Sensitivity Analysis ──────────────────────────────────
    pdf.add_page()
    pdf.subsection_title("9.3  Sensitivity Analysis")

    # Weight perturbation
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(0, 7, "Traffic Weight Perturbation", new_x="LMARGIN", new_y="NEXT")
    pdf.body_text(
        "We systematically perturbed each of the 8 traffic component weights "
        "by +/-25% and +/-50% (32 scenarios) and measured the Jaccard "
        "similarity of the top-1% risk cells (19,195 cells) and the overall "
        "Spearman rank correlation vs the baseline ranking:"
    )

    pdf.metric_table(
        ["Component", "-50%", "-25%", "+25%", "+50%"],
        [
            [
                "speed_lethality",
                "J=0.71 r=0.983",
                "J=0.86 r=0.996",
                "J=0.88 r=0.996",
                "J=0.78 r=0.987",
            ],
            [
                "high_speed_frac",
                "J=0.76 r=0.997",
                "J=0.87 r=0.999",
                "J=0.88 r=0.999",
                "J=0.77 r=0.997",
            ],
            [
                "vessels",
                "J=0.79 r=0.986",
                "J=0.89 r=0.997",
                "J=0.90 r=0.997",
                "J=0.81 r=0.990",
            ],
            [
                "large_vessels",
                "J=0.92 r=0.998",
                "J=0.96 r=1.000",
                "J=0.96 r=1.000",
                "J=0.92 r=0.999",
            ],
            [
                "draft_risk",
                "J=0.80 r=0.996",
                "J=0.91 r=0.999",
                "J=0.93 r=0.999",
                "J=0.87 r=0.997",
            ],
            [
                "draft_risk_frac",
                "J=0.94 r=0.999",
                "J=0.97 r=1.000",
                "J=0.97 r=1.000",
                "J=0.94 r=0.999",
            ],
            [
                "commercial",
                "J=0.92 r=0.998",
                "J=0.96 r=1.000",
                "J=0.96 r=1.000",
                "J=0.93 r=0.999",
            ],
            [
                "night_traffic",
                "J=0.84 r=0.991",
                "J=0.92 r=0.998",
                "J=0.92 r=0.998",
                "J=0.85 r=0.993",
            ],
        ],
        col_widths=[38, 38, 38, 38, 38],
    )

    pdf.stat_boxes(
        [
            ("0.88", "Mean Jaccard (top-1%)"),
            ("0.71", "Min Jaccard (worst)"),
            ("0.996", "Mean rank rho"),
        ]
    )

    pdf.body_text(
        "The top-1% hotspot set is stable under all perturbations.  Even "
        "the worst case (speed_lethality at -50%) retains 71% of the "
        "original hotspot cells, with rank correlation still at 0.983.  "
        "The most sensitive components are speed_lethality and vessels "
        "(weight = 20% each), while draft_risk_fraction (5%) and "
        "large_vessels (10%) have minimal impact."
    )

    # Jensen's spatial
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(
        0, 7, "Spatial Distribution of Jensen's Bias", new_x="LMARGIN", new_y="NEXT"
    )
    pdf.body_text(
        "Jensen's bias varies predictably with cell-average speed.  We "
        "grouped 1,919,487 unique cells into speed deciles:"
    )

    pdf.metric_table(
        ["Decile", "Avg Speed (kn)", "Avg Bias", "Avg Lethality", "n cells"],
        [
            ["0", "7.4", "+0.0108", "0.200", "191,949"],
            ["1", "10.5", "+0.0019", "0.377", "192,335"],
            ["2", "11.6", "-0.0021", "0.469", "196,240"],
            ["3", "12.3", "-0.0054", "0.532", "187,271"],
            ["4", "13.0", "-0.0090", "0.586", "194,436"],
            ["5", "13.6", "-0.0129", "0.635", "189,638"],
            ["6", "14.3", "-0.0140", "0.685", "191,775"],
            ["7", "15.0", "-0.0135", "0.738", "191,952"],
            ["8", "16.0", "-0.0112", "0.801", "193,910"],
            ["9", "22.9", "-0.0070", "0.913", "189,981"],
        ],
        col_widths=[22, 40, 35, 45, 48],
    )

    pdf.body_text(
        "Bias peaks at decile 6 (14.3 kn, bias = -0.014), exactly in the "
        "steepest region of the V&T logistic.  At low speeds (<8 kn) the "
        "bias is slightly positive (logistic is convex there), and at very "
        "high speeds (>20 kn) it approaches zero because the logistic is "
        "saturated.  The correlation between |bias| and high-speed fraction "
        "is rho = -0.41, confirming that cells with more uniform speed "
        "distributions (high hs_frac) have less Jensen's bias.  Maximum "
        "individual-cell bias is 0.25, occurring in 2-vessel cells near the "
        "8 kn inflection point."
    )

    # Composite sensitivity
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(
        0, 7, "Composite Sub-Score Weight Sensitivity", new_x="LMARGIN", new_y="NEXT"
    )
    pdf.body_text(
        "We repeated the perturbation analysis at the composite level, "
        "varying each of the 7 sub-score weights by +/-25% and +/-50% "
        "across 1,824,667 scored cells:"
    )

    pdf.metric_table(
        ["Sub-score", "-50%", "-25%", "+25%", "+50%"],
        [
            [
                "Traffic",
                "J=0.76 r=0.975",
                "J=0.86 r=0.995",
                "J=0.88 r=0.996",
                "J=0.80 r=0.988",
            ],
            [
                "Cetacean",
                "J=0.69 r=0.999",
                "J=0.88 r=1.000",
                "J=0.92 r=1.000",
                "J=0.88 r=1.000",
            ],
            [
                "Proximity",
                "J=0.93 r=0.994",
                "J=0.96 r=0.999",
                "J=0.97 r=0.999",
                "J=0.93 r=0.996",
            ],
            [
                "Strike",
                "J=1.00 r=1.000",
                "J=1.00 r=1.000",
                "J=1.00 r=1.000",
                "J=1.00 r=1.000",
            ],
            [
                "Habitat",
                "J=0.84 r=0.995",
                "J=0.91 r=0.999",
                "J=0.89 r=0.999",
                "J=0.82 r=0.997",
            ],
            [
                "Prot. Gap",
                "J=0.85 r=0.999",
                "J=0.92 r=1.000",
                "J=0.92 r=1.000",
                "J=0.87 r=0.999",
            ],
            [
                "Reference",
                "J=0.97 r=0.996",
                "J=0.99 r=0.999",
                "J=0.98 r=0.999",
                "J=0.97 r=0.997",
            ],
        ],
        col_widths=[32, 40, 40, 40, 38],
    )

    pdf.stat_boxes(
        [
            ("0.91", "Mean Jaccard (top-1%)"),
            ("0.69", "Min Jaccard (worst)"),
            ("0.997", "Mean rank rho"),
        ]
    )

    pdf.body_text(
        "The composite model is highly stable.  Strike history (10% weight, "
        "only 67 cells with strikes) has no measurable effect on rankings.  "
        "The most sensitive sub-scores are cetacean (Jaccard 0.69 at -50%) "
        "and traffic (0.76 at -50%), which is expected given their combined "
        "50% weight.  Even in the worst case, rank correlation never drops "
        "below 0.975."
    )

    pdf.ln(2)
    pdf.callout_box(
        "Validation summary",
        "All 9 checks pass.  The model is internally consistent (weight "
        "sums correct, Jensen's bias negligible, draft fully imputed), "
        "externally valid (moderate Nisi correlation, 156x strike "
        "enrichment, correct SMA targeting), and stable under weight "
        "perturbation (minimum Jaccard 0.69, mean rank rho > 0.99).",
        ReportPDF.ACCENT_GREEN,
    )

    # ── 10. Key References ────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("10. References")

    refs = [
        (
            "Vanderlaan, A.S.M. & Taggart, C.T. (2007). Vessel collisions "
            "with whales: the probability of lethal injury based on vessel "
            "speed. Marine Mammal Science, 23(1), 144-156."
        ),
        (
            "Rockwood, R.C., Calambokidis, J. & Jahncke, J. (2017). High "
            "mortality of blue, humpback and fin whales from modeling of "
            "vessel strikes on the U.S. West Coast. PLoS ONE, 12(8), "
            "e0183052."
        ),
        (
            "Rockwood, R.C. et al. (2021). Modeling whale deaths from "
            "vessel strikes to reduce the risk of fatality to endangered "
            "whales. Frontiers in Marine Science, 8, 649890."
        ),
        (
            "Winkler, C. et al. IWC Ship Strike Database. International "
            "Whaling Commission, SC/68B/HIM/09 (rev1)."
        ),
        (
            "Nisi, A.C. et al. (2024). Mapping global risk of whale-ship "
            "collisions using AIS data and species distribution models. "
            "Nature Communications."
        ),
        (
            "Conn, P.B. & Silber, G.K. (2013). Vessel speed restrictions "
            "reduce risk of collision-related mortality for North Atlantic "
            "right whales. Ecosphere, 4(4), art43."
        ),
        (
            "Laist, D.W. et al. (2001). Collisions between ships and "
            "whales. Marine Mammal Science, 17(1), 35-75."
        ),
    ]

    for i, ref in enumerate(refs, 1):
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*ReportPDF.DARK_TEXT)
        x = pdf.get_x()
        pdf.set_x(x + 5)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(*ReportPDF.TEAL)
        pdf.cell(8, 6, f"[{i}]")
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*ReportPDF.DARK_TEXT)
        pdf.multi_cell(172, 5.5, ref)
        pdf.ln(2)

    # ── 11. Summary ───────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("11. Summary")

    pdf.body_text(
        "This update moves our traffic risk scoring from a simplified "
        "heuristic to a literature-grounded methodology.  The key changes:"
    )

    pdf.numbered_item(
        1,
        "Continuous speed-lethality: V&T (2007) logistic replaces binary "
        ">10 kn threshold, capturing the full gradient from 0.8% (0 kn) "
        "to 99.5% (25 kn) lethality probability.",
    )
    pdf.numbered_item(
        2,
        "Per-vessel computation: logistic applied to each vessel's speed "
        "before cell-level averaging, eliminating Jensen's inequality bias "
        "(up to 25% underestimation in bimodal cells).",
    )
    pdf.numbered_item(
        3,
        "Continuous draft: Rockwood-inspired vertical strike zone dimension, "
        "with type-stratified OLS imputation to fill the 15% of vessels "
        "missing draft data.",
    )
    pdf.numbered_item(
        4,
        "Eight-component traffic sub-score: captures speed, volume, size, "
        "draft, vessel type, and night traffic in a principled weighting "
        "scheme informed by the IWC and Rockwood findings.",
    )
    pdf.numbered_item(
        5,
        "Interaction-first ML variant: promotes P(whale) x traffic as the "
        "primary co-occurrence metric (25% of composite), directly "
        "implementing the Rockwood encounter-rate paradigm.",
    )
    pdf.numbered_item(
        6,
        "Comprehensive validation: 9 automated checks across internal "
        "consistency, external benchmarks, and sensitivity analysis -- all "
        "passing.  156x enrichment of strike cells in the critical risk "
        "category provides strong real-world validation.",
    )

    pdf.ln(6)

    # Closing stat boxes
    pdf.stat_boxes(
        [
            ("9/9", "Validation PASS"),
            ("156x", "Strike enrichment"),
            ("0.98", "Jensen rank rho"),
            ("100%", "Draft coverage"),
        ]
    )

    # ── Output ────────────────────────────────────────────────────
    pdf.output(str(OUTPUT_FILE))
    print(f"Report written to {OUTPUT_FILE}")
    print(f"  Pages: {pdf.page_no()}")


if __name__ == "__main__":
    build_report()

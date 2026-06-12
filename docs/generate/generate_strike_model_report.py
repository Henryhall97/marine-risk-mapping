"""Generate Strike Model Methodology PDF.

Documents the planned transition from the current sparse-strike risk
pipeline (NMFS Atlantic, 67 geocoded records) to a properly
conditional strike-probability model fit on the extended IWC vessel
strike database. Covers the conceptual shift from "spatial prior"
to "likelihood", the point-process / use-availability fitting
machinery, the construction of P(vessel | cell, season) from AIS,
the background-sampling algorithm, and the data we need to make it
viable.

Run:
    uv run python docs/generate/generate_strike_model_report.py
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "strike_model_with_iwc_data.pdf"


# ═══════════════════════════════════════════════════════════════════
# ReportPDF — same navy / teal theme as the other phase reports
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
                "Marine Risk Mapping -- Strike Model with IWC Data",
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
        for w, h_text in zip(col_widths, headers, strict=False):
            self.cell(w, 7, f"  {h_text}", fill=True)
        self.ln()
        self.set_font("Helvetica", "", 9)
        for i, row in enumerate(rows):
            bg = self.LIGHT_BG if i % 2 == 0 else self.WHITE
            self.set_fill_color(*bg)
            for j, (w, cell_val) in enumerate(zip(col_widths, row, strict=False)):
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
        if self.get_y() > 250:
            self.add_page()
        y = self.get_y()
        box_h = 22 if note is None else 32
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

    def code_block(self, code):
        if self.get_y() > 240:
            self.add_page()
        y = self.get_y()
        lines = code.strip("\n").split("\n")
        box_h = len(lines) * 4.2 + 4
        self.set_fill_color(248, 249, 250)
        self.rect(10, y, 190, box_h, style="F")
        self.set_draw_color(220, 220, 220)
        self.rect(10, y, 190, box_h, style="D")
        self.set_xy(13, y + 2)
        self.set_font("Courier", "", 8.5)
        self.set_text_color(*self.DARK_TEXT)
        for line in lines:
            self.cell(0, 4.2, line, new_x="LMARGIN", new_y="NEXT")
            self.set_x(13)
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
    pdf.ln(36)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(
        0,
        13,
        "From Prior to Likelihood",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "A Conditional Strike-Probability Model",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        10,
        "Powered by Extended IWC Strike Records",
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
    pdf.ln(16)

    pdf.stat_boxes(
        [
            ("67", "Geocoded strikes today"),
            ("1.8M", "H3 cells"),
            ("9.7M", "AIS cell-months"),
            ("6", "Whale species modelled"),
        ]
    )

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        6,
        (
            "This document describes how an extended ship-strike record set "
            "(of the kind held by the IWC Vessel Strikes Database) would "
            "change the modelling pipeline. The current architecture treats "
            "strike history as a sparse spatial prior. With several hundred "
            "to several thousand additional positives, the same data becomes "
            "the response variable of a conditional point-process model that "
            "estimates the probability of a strike given a whale-ship "
            "encounter -- the term that conservation actually needs."
        ),
        align="C",
    )

    # ── 1. Where we are today ─────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1. Where the model is today")

    pdf.body_text(
        "The current Marine Risk Mapping pipeline computes a 7-sub-score "
        "composite collision-risk index over a 1.8M-cell H3 resolution-7 "
        "grid (~1.2 km edge length) covering CONUS, Alaska, Hawaii, and "
        "the Caribbean. The three layers that feed it are vessel traffic, "
        "whale presence, and strike history."
    )

    pdf.subsection_title("1.1 Vessel traffic")
    pdf.body_text(
        "AIS pings (~3.1 billion observations) are condensed into ~9.7 "
        "million cell-month rows in ais_h3_summary, with per-cell speed "
        "distributions, vessel type breakdowns, draft averages, "
        "night-traffic fractions, and a Vanderlaan & Taggart (2007) "
        "lethality-weighted exposure rate."
    )

    pdf.subsection_title("1.2 Whale presence")
    pdf.body_text(
        "Two complementary models per species, ensembled to reduce single-source bias:"
    )
    pdf.bullet(
        "An integrated species distribution model (ISDM) fit on the Nisi "
        "et al. (2024) expert-curated presence-absence dataset, covering "
        "blue, fin, humpback and sperm whales."
    )
    pdf.bullet(
        "A standard XGBoost SDM trained on OBIS sighting data with "
        "spatial block CV at H3 resolution 2 (~158 km blocks, 5 folds), "
        "extending to right whale and minke. Traffic features are "
        "deliberately excluded -- they correlate with survey effort, not "
        "with biological presence."
    )
    pdf.body_text(
        "Per cell-season we compute per-species probabilities P(species_i) "
        "and a joint P(any_whale) = 1 - product_i(1 - P_i) over the six "
        "target species."
    )

    pdf.subsection_title("1.3 Strike history -- the weak link")
    pdf.body_text(
        "Strike records currently come from a single source: the NOAA "
        "NMFS Atlantic large-whale strike database. 261 records are "
        "parsed, of which only 67 have usable geocoordinates. In a 1.8M "
        "cell grid, this means just 67 cells carry a positive strike "
        "signal."
    )

    pdf.callout_box(
        "Current treatment",
        "Strike data enters the composite risk score as a spatial "
        "prior: a kernel-decayed proximity-to-historical-strike feature "
        "(half-life 25 km) and a binary 'any strike in cell' indicator. "
        "These are smoothed presence maps, not models -- they describe "
        "where strikes have clustered, not why.",
        colour=ReportPDF.ACCENT_AMBER,
    )

    pdf.body_text(
        "We have built a feature matrix (fct_strike_risk_training, 1.8M "
        "rows, 10 features) ready for a strike-probability classifier, "
        "but with 67 positives the model is statistically unidentifiable: "
        "the events-per-predictor ratio is well below the conventional 10:1 "
        "threshold (Peduzzi et al. 1996), and positives are concentrated "
        "almost entirely in a single regional + species + season stratum "
        "(North Atlantic right whale, US East Coast, winter)."
    )

    # ── 2. Two regimes ────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("2. Two regimes: prior vs likelihood")

    pdf.body_text(
        "Evidence about where strikes happen can enter a model in two "
        "fundamentally different ways. The distinction matters because "
        "it changes what you can ask the model afterwards."
    )

    pdf.subsection_title("2.1 As a prior (current state)")
    pdf.body_text(
        "'Strikes have happened here in the past, so cells near past "
        "strikes are a-priori more risky.' Strike locations are a fixed "
        "smoothed spatial input. No model is fit; you never ask why the "
        "strikes clustered where they did. This is informative for "
        "ranking cells, but it does not generalise to new cells where "
        "no historical strike has occurred, and it cannot answer "
        "counterfactual questions."
    )

    pdf.subsection_title("2.2 As a likelihood (target state)")
    pdf.body_text(
        "'Given this cell has whales present, vessels present, and these "
        "environmental conditions, what is the probability that a strike "
        "occurs?' Strike records become observations of a process; the "
        "model parameters describe how strike probability scales with "
        "covariates."
    )

    pdf.body_text("Three practical advantages:")
    pdf.bullet(
        "Interpretable coefficients: 'for every 1 knot increase in mean "
        "vessel speed, the log-odds of a strike rise by X (+/- s.e.)'."
    )
    pdf.bullet(
        "Generalisation: predicts strike probability in cells where no "
        "historical strike has occurred but conditions match."
    )
    pdf.bullet(
        "Counterfactuals: 'if vessels slowed to 10 knots in this cell, "
        "P(strike) would drop by Y%' -- the policy-relevant unit."
    )

    pdf.subsection_title("2.3 Why 'conditional' is non-negotiable")
    pdf.body_text(
        "A strike requires three things to be jointly true at the same "
        "place and time: a whale is present, a vessel is present, and "
        "they collide given the whale's surfacing behaviour and the "
        "vessel's speed/size. A naive P(strike | env) model just learns "
        "the geometry of encounters -- the places where shipping lanes "
        "cross whale habitat -- but not the physics of collisions. A "
        "1-knot harbour skiff in dense whale habitat almost never kills "
        "anything; a 22-knot container ship in a sparse area can."
    )

    pdf.equation_box(
        "Strike target",
        "P(strike | whale present, vessel present, env, speed, draft, ...)",
        note=(
            "Conditioning on the first two terms isolates the third -- "
            "the part of the process that the model can actually learn "
            "something useful about. P(whale) and P(vessel) come from the "
            "existing SDM ensemble and AIS aggregation."
        ),
    )

    # ── 3. P(vessel | cell, season) ───────────────────────────────
    pdf.add_page()
    pdf.section_title("3. Computing P(vessel | cell, season)")

    pdf.body_text(
        "The strike model needs vessel presence as a probability, not a "
        "raw transit count. The conversion is a modelling choice: we "
        "treat each cell-season as a homogeneous Poisson arrival process "
        "with rate lambda (transits per hour), and convert to a "
        "presence probability over a strike-relevant time window."
    )

    pdf.equation_box(
        "Poisson presence",
        "P(vessel in dt) = 1 - exp(-lambda * dt)",
        note=(
            "lambda = transit_count / hours_in_season. dt is the "
            "strike-relevant time window; a whale spends 10-30 minutes "
            "at the surface per dive cycle so dt = 1 hour is sensible. "
            "Choice of dt rescales the column but leaves model slopes "
            "unchanged -- only the intercept shifts."
        ),
    )

    pdf.subsection_title("3.1 Worked numeric examples")
    pdf.body_text("Assuming a 90-day season (2,160 hours) and dt = 1 hour:")

    pdf.metric_table(
        headers=[
            "Cell type",
            "Transits/season",
            "lambda /h",
            "P(1h)",
            "P(10min)",
        ],
        rows=[
            ("Deep open ocean", "1", "0.00046", "0.05%", "0.008%"),
            ("Quiet shelf, occasional fishing", "10", "0.0046", "0.46%", "0.08%"),
            ("Coastal, regular small vessel", "50", "0.023", "2.29%", "0.39%"),
            ("Moderate fishing ground", "200", "0.093", "8.85%", "1.53%"),
            ("Approach to regional port", "1,000", "0.46", "37.1%", "7.45%"),
            ("Edge of major shipping lane", "5,000", "2.31", "90.1%", "31.8%"),
            ("Inside Boston/NY TSS", "20,000", "9.26", "99.99%", "78.8%"),
            ("Inside SF Bay TSS", "50,000", "23.1", "~100%", "97.9%"),
        ],
        col_widths=[60, 32, 25, 30, 30],
    )

    pdf.subsection_title("3.2 Why the non-linearity matters")
    pdf.body_text(
        "Doubling traffic from 5 to 10 transits per season barely changes "
        "P (0.23% -> 0.46%); doubling from 1,000 to 2,000 takes you from "
        "37% to 60%; doubling from 20,000 to 40,000 changes essentially "
        "nothing because both saturate. This is physical: two ships in "
        "the same hour cannot both be the one that hits the whale, so "
        "the marginal vessel matters less as traffic grows. The Poisson "
        "form encodes this correctly; raw transit counts do not."
    )

    pdf.callout_box(
        "Why this beats raw transit counts",
        "A linear traffic covariate forces the strike model to learn the "
        "saturation curve from data -- which it cannot do with 67 "
        "positives. Pre-computing P(vessel) as a Poisson presence "
        "probability bakes the physics in and lets the model spend its "
        "limited statistical power on the species, speed, depth, and "
        "interaction effects that actually require fitting.",
        colour=ReportPDF.ACCENT_BLUE,
    )

    pdf.code_block(
        """
SEASON_HOURS = 90 * 24      # 2160
DT_HOURS = 1.0

vessel_rate = ais_seasonal["transit_count"] / SEASON_HOURS  # per h
p_vessel = 1.0 - np.exp(-vessel_rate * DT_HOURS)            # 0..1
"""
    )

    # ── 4. Use-availability design ────────────────────────────────
    pdf.add_page()
    pdf.section_title("4. The use-availability point-process design")

    pdf.body_text(
        "Use-availability (Manly et al. 2002) is the ecology-flavoured "
        "framing of an inhomogeneous Poisson point-process model "
        "(Warton & Shepherd 2010). It lets us fit a strike model when "
        "positives are rare and negatives are everywhere."
    )

    pdf.subsection_title("4.1 The construction")
    pdf.bullet("'Used' points are the K geocoded strike records (the positives).")
    pdf.bullet(
        "'Available' points are samples from the distribution of where "
        "the event could have occurred -- locations where a whale and "
        "vessel were both plausibly present at the same time of year."
    )
    pdf.bullet(
        "Fit a logistic regression (or boosted trees) with the "
        "use/available indicator as the binary target. Coefficients "
        "describe how the probability of use, relative to availability, "
        "varies with the covariates -- mathematically equivalent to a "
        "Poisson point-process MLE."
    )

    pdf.subsection_title("4.2 The sampling weight is the crux")
    pdf.body_text(
        "How you sample the available points determines what the model "
        "actually learns. Sample uniformly across the map and you "
        "contaminate the negative set with vast areas where no strike "
        "was ever possible -- the model relearns 'whales + ships' and "
        "nothing else. Instead we sample weighted by the joint hazard "
        "surface:"
    )

    pdf.equation_box(
        "Background sampling weight",
        "w[c] proportional to  P_whale[c, s, sp] * P_vessel[c, s]",
        note=(
            "Computed per (cell c, season s, species sp) -- so each "
            "strike's background is drawn from the conditions plausibly "
            "applicable to that strike. The model is forced to learn the "
            "residual signal: what additional conditions tip an "
            "encounter into a strike."
        ),
    )

    pdf.subsection_title("4.3 The algorithm")
    pdf.code_block(
        """
for k in strikes:
    s_k, sp_k = strike.season, strike.species

    # 1. Compute per-cell sampling weight
    w[c] = P_whale[c, s_k, sp_k] * P_vessel[c, s_k]
    w = w / w.sum()

    # 2. Draw N cells from that distribution (with replacement)
    bg_cells = np.random.choice(cells, size=N, p=w)

    # 3. For each, sample a "fake vessel" from the empirical
    #    AIS distribution in that (cell, season)
    for c_prime in bg_cells:
        env = covariates[c_prime, s_k]
        vessel_attrs = sample_from_ais(c_prime, s_k)
        rows.append((c_prime, s_k, sp_k, env, vessel_attrs, label=0))

    # 4. Add the positive record
    rows.append((strike.cell, s_k, sp_k,
                 strike.env, strike.vessel_attrs, label=1))
"""
    )

    pdf.subsection_title("4.4 What 'N' does")
    pdf.body_text(
        "N is the ratio of background to positives. With a case-control "
        "design like this, logistic-regression slopes are unbiased -- "
        "only the intercept carries a known log(N * pi / (1-pi)) bias "
        "that a Platt-style recalibration corrects. N = 10 sacrifices "
        "almost no efficiency vs the full background; N = 100 is "
        "overkill but cheap. We would sensitivity-test 10 / 50 / 100 to "
        "confirm slopes are stable."
    )

    # ── 5. Numeric impact of more positives ───────────────────────
    pdf.add_page()
    pdf.section_title("5. What more positives actually buy")

    pdf.body_text(
        "Statistical power for logistic regression scales with the "
        "number of events, not the total sample size. The Peduzzi "
        "et al. (1996) rule of thumb is 10 events per predictor variable. "
        "Below this, coefficient confidence intervals are so wide the "
        "model is effectively useless for inference."
    )

    pdf.metric_table(
        headers=[
            "Positives K",
            "Predictor budget",
            "Realistic model spec",
            "Generalises?",
        ],
        rows=[
            (
                "67 (today)",
                "6-7",
                "Main effects only, single region",
                "No",
            ),
            (
                "200",
                "20",
                "+ species random effect",
                "Limited",
            ),
            (
                "500",
                "50",
                "+ species x speed interactions",
                "Within ocean basin",
            ),
            (
                "1,000",
                "100",
                "+ regional intercepts",
                "Across basins",
            ),
            (
                "5,000+",
                "500",
                "Full hierarchical Bayesian GLM, non-linear smooths on speed",
                "Global, generalisable",
            ),
        ],
        col_widths=[28, 30, 92, 40],
    )

    pdf.callout_box(
        "Spatial coverage scales with positives",
        "The current 67 positives are almost all NARW + Mid-Atlantic + "
        "winter. A model fit on them learns that single stratum and has "
        "nothing to say about humpbacks in Alaska, blue whales off "
        "California, or sperm whales in the Caribbean. Scaling positives "
        "by 5-10x implicitly scales geographic and species diversity, "
        "which is what makes coefficients generalise.",
        colour=ReportPDF.ACCENT_GREEN,
    )

    pdf.subsection_title("5.1 Why slope estimates need so many events")
    pdf.body_text(
        "Each covariate adds a parameter that must be estimated from the "
        "positive class. With binary outcomes, the standard error on a "
        "log-odds coefficient scales roughly as 1 / sqrt(K_min * p * "
        "(1-p)), where K_min is the minor-class count and p is the "
        "covariate prevalence among positives. At K_min = 67 the SEs are "
        "wide enough that even strong physical effects (V&T-style speed "
        "dependence) cannot be distinguished from zero at conventional "
        "significance. At K_min = 500 the same effect would be detected "
        "comfortably."
    )

    # ── 6. End-to-end pipeline ────────────────────────────────────
    pdf.add_page()
    pdf.section_title("6. End-to-end pipeline with IWC data")

    pdf.body_text(
        "Combining everything above, the full strike-modelling pipeline "
        "looks like this:"
    )

    pdf.numbered_item(
        1,
        "Score the SDM ensemble on every (cell, season, species) tuple. "
        "Output: P_whale[c, s, sp], already materialised as "
        "ml_whale_predictions and ml_sdm_predictions.",
    )
    pdf.numbered_item(
        2,
        "Convert AIS to P_vessel[c, s] via the Poisson formula in S3. "
        "New dbt model: int_vessel_presence_seasonal.",
    )
    pdf.numbered_item(
        3,
        "Geocode and standardise the IWC strike records. Match each to "
        "an H3 cell, season, and species. New ingestion script: "
        "ingest_iwc_strikes.py.",
    )
    pdf.numbered_item(
        4,
        "Build the use-availability training table: for each positive "
        "strike, draw N=50 background cells weighted by P_whale x "
        "P_vessel matched on (season, species). New script: "
        "build_strike_use_availability.py.",
    )
    pdf.numbered_item(
        5,
        "Fit the strike model. Two candidates worth comparing: "
        "(a) a hierarchical Bayesian GLM with species random effects "
        "and weakly-informative priors on speed/draft (interpretable, "
        "calibrated, handles small samples gracefully); "
        "(b) gradient-boosted trees with sample-weighted background "
        "(captures interactions, less interpretable).",
    )
    pdf.numbered_item(
        6,
        "Validate with spatial holdout (fit on East Coast, predict "
        "West Coast and vice versa) to confirm coefficients generalise "
        "rather than memorising regional patterns.",
    )
    pdf.numbered_item(
        7,
        "Score per (cell, season): P_strike[c, s] = model.predict_proba "
        "with P_whale, P_vessel, env, and average vessel attrs as inputs.",
    )
    pdf.numbered_item(
        8,
        "Compose to expected strikes per unit time: "
        "E[strikes/season] = P_whale x P_vessel x P_strike x "
        "season_hours. This is the policy-actionable unit.",
    )

    pdf.subsection_title("6.1 What changes in the composite risk score")
    pdf.body_text(
        "In the current pipeline the strike sub-score is one of seven "
        "percentile-ranked sub-scores entering a weighted sum. With the "
        "new model we have two cleaner options:"
    )
    pdf.bullet(
        "Replace the strike sub-score with P_strike, percentile-ranked "
        "as before. Maintains the existing user interface."
    )
    pdf.bullet(
        "Replace the whole composite score with the expected-strikes-per-"
        "season prediction. This breaks the relative-risk framing but "
        "gives an absolute unit -- the strike rate you can multiply by "
        "management interventions to get expected lives saved."
    )

    # ── 7. Climate projections ────────────────────────────────────
    pdf.add_page()
    pdf.section_title("7. Climate-projected strike risk")

    pdf.body_text(
        "We already re-score the SDM ensemble on CMIP6 SSP2-4.5 and "
        "SSP5-8.5 ocean covariates out to the 2080s. With the conditional "
        "strike model in place, the same projection mechanics propagate "
        "forward:"
    )

    pdf.equation_box(
        "Projected expected strikes",
        "E[strikes | year, scenario] = P_whale(future) * P_vessel(today) * "
        "P_strike(future env)",
        note=(
            "Traffic is held at present-day -- we have no credible "
            "shipping projections. The output is interpretable as 'if "
            "today's traffic patterns persisted, where would whales move "
            "into them as oceans warm'. This is exactly the question that "
            "drives dynamic management zone proposals."
        ),
    )

    pdf.body_text(
        "The combined output supports two policy-relevant outputs that "
        "are not possible today:"
    )
    pdf.bullet(
        "Identifying future emerging hotspots -- cells with low strike "
        "rates today but high projected rates under warming. These are "
        "the priority candidates for proactive DMA-style management."
    )
    pdf.bullet(
        "Quantifying intervention benefit -- 'a 10-knot seasonal speed "
        "restriction in cell X reduces expected strikes by Y per year "
        "under the 2050 SSP2-4.5 scenario'."
    )

    # ── 8. Data we need from IWC ──────────────────────────────────
    pdf.add_page()
    pdf.section_title("8. Data we need from IWC")

    pdf.body_text(
        "The pipeline above is robust to a wide range of input "
        "completeness. The minimum useful per-record fields are:"
    )

    pdf.metric_table(
        headers=["Field", "Required?", "Why"],
        rows=[
            (
                "Latitude / longitude",
                "Required",
                "Maps strike to H3 cell + env covariates",
            ),
            (
                "Date (or year + month)",
                "Required",
                "Assigns season for matched background",
            ),
            (
                "Species (or genus)",
                "Required",
                "Species-stratified sampling and per-species priors",
            ),
            (
                "Vessel length / GT class",
                "Strongly desired",
                "Vessel-size effect; can impute from typical AIS dist",
            ),
            (
                "Estimated vessel speed",
                "Desired",
                "V&T-style lethality coefficient",
            ),
            (
                "Vessel type",
                "Desired",
                "Cargo/fishing/passenger covariates",
            ),
            (
                "Outcome severity",
                "Optional",
                "Lets us model lethal vs sub-lethal as ordinal target",
            ),
            (
                "Coordinate uncertainty",
                "Optional",
                "Down-weights coarse positions; supports uncertain h3 spread",
            ),
        ],
        col_widths=[42, 32, 116],
    )

    pdf.subsection_title("8.1 Geographic coverage")
    pdf.body_text(
        "The current study area is the US EEZ (lat 2S-52N, lon "
        "180W-59W). However, the modelling machinery is global -- "
        "the constraint is which study area we have AIS and SDM "
        "coverage for. North Atlantic, North Pacific and Mediterranean "
        "records are immediately usable; Southern Hemisphere records "
        "would let us extend the framework as we add traffic and "
        "presence data for those basins."
    )

    pdf.subsection_title("8.2 Temporal coverage")
    pdf.body_text(
        "Full historical record is ideal. Pre-AIS strikes (before "
        "~2002) are still valuable -- they inform the spatial "
        "distribution of where strikes have historically occurred even "
        "in the absence of contemporaneous vessel tracking. We would "
        "model them with a flag indicating reduced vessel-attribute "
        "fidelity, but they still contribute positive cases to the "
        "use-availability fit."
    )

    # ── 9. Summary ────────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("9. Summary")

    pdf.subsection_title("9.1 The one-line version")
    pdf.callout_box(
        "Headline",
        "Right now strike records are a smoothed input map. With an "
        "extended IWC dataset they become the response variable of a "
        "real model -- and that is the difference between ranking cells "
        "by relative risk and predicting absolute strike rates you can "
        "do policy with.",
        colour=ReportPDF.TEAL,
    )

    pdf.subsection_title("9.2 What changes, end-to-end")
    pdf.metric_table(
        headers=["Layer", "Today", "With extended IWC data"],
        rows=[
            (
                "Whale presence",
                "ISDM + SDM ensemble (unchanged)",
                "Unchanged -- becomes a covariate in the strike model",
            ),
            (
                "Vessel exposure",
                "V&T-weighted transit count (rank-only)",
                "Poisson P(vessel in dt) + per-transit attrs",
            ),
            (
                "Strike data",
                "Spatial prior: proximity + binary indicator",
                "Likelihood: response variable of conditional model",
            ),
            (
                "Composite score",
                "7-sub-score percentile-rank sum",
                "Replaceable with expected-strikes-per-season unit",
            ),
            (
                "Climate projection",
                "Risk percentile vs current decade",
                "Absolute projected strike rate under SSPs",
            ),
            (
                "Policy questions",
                "'Which cells rank highest?'",
                "'How many strikes does a 10-knot zone prevent?'",
            ),
        ],
        col_widths=[42, 72, 76],
    )

    pdf.subsection_title("9.3 What we are asking for")
    pdf.body_text(
        "The IWC Vessel Strikes Database extract, as broad in time and "
        "geography as it is feasible to share. Minimum useful fields: "
        "lat, lon, date, species. Anything beyond that improves the "
        "model. Even partial coverage (a few hundred geocoded records) "
        "would move us from 'statistically unidentifiable' to "
        "'meaningfully fittable' -- a step change that the current "
        "pipeline cannot achieve from any other source."
    )

    pdf.subsection_title("9.4 References")
    pdf.small_text(
        "Manly, B.F.J., McDonald, L.L., Thomas, D.L., McDonald, T.L. & "
        "Erickson, W.P. (2002). Resource Selection by Animals: "
        "Statistical Design and Analysis for Field Studies. 2nd ed. "
        "Kluwer Academic."
    )
    pdf.small_text(
        "Nisi, A.C., Welch, H., Brodie, S., et al. (2024). 'Ship "
        "collision risk threatens whales across the world's oceans.' "
        "Science 386(6724): 870-875."
    )
    pdf.small_text(
        "Peduzzi, P., Concato, J., Kemper, E., Holford, T.R. & Feinstein, "
        "A.R. (1996). 'A simulation study of the number of events per "
        "variable in logistic regression analysis.' J. Clin. Epidemiol. "
        "49(12): 1373-1379."
    )
    pdf.small_text(
        "Rockwood, R.C., Adams, J.D., Hastings, S., Morten, J. & "
        "Jahncke, J. (2021). 'Modeling whale deaths from vessel strikes "
        "to reduce the risk of fatality to endangered whales.' Front. "
        "Mar. Sci. 8: 649890."
    )
    pdf.small_text(
        "Vanderlaan, A.S.M. & Taggart, C.T. (2007). 'Vessel collisions "
        "with whales: the probability of lethal injury based on vessel "
        "speed.' Mar. Mamm. Sci. 23(1): 144-156."
    )
    pdf.small_text(
        "Warton, D.I. & Shepherd, L.C. (2010). 'Poisson point process "
        "models solve the pseudo-absence problem for presence-only data "
        "in ecology.' Ann. Appl. Stat. 4(3): 1383-1402."
    )

    # ── Save ──────────────────────────────────────────────────────
    pdf.output(str(OUTPUT_FILE))
    return OUTPUT_FILE


if __name__ == "__main__":
    out = build_report()
    print(f"Wrote: {out}")
    print(f"Size: {out.stat().st_size / 1024:.1f} KB")

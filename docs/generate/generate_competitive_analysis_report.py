"""Generate Competitive Analysis PDF.

Compares the Marine Risk Mapping community / citizen science
features against iNaturalist, Happywhale, Zooniverse, and OBIS.

Usage:
    uv run python docs/generate/generate_competitive_analysis_report.py
"""

from pathlib import Path

from fpdf import FPDF

# -- Paths --------------------------------------------------------
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "competitive_analysis.pdf"


# =================================================================
# ReportPDF - navy / teal theme (matches all project reports)
# =================================================================


class ReportPDF(FPDF):
    NAVY = (15, 32, 65)
    TEAL = (0, 150, 136)
    LIGHT_BG = (240, 245, 250)
    WHITE = (255, 255, 255)
    DARK_TEXT = (30, 30, 30)
    MID_TEXT = (80, 80, 80)
    ACCENT_GREEN = (46, 204, 113)
    ACCENT_AMBER = (243, 156, 18)
    ACCENT_RED = (214, 64, 69)
    ACCENT_BLUE = (52, 152, 219)
    ACCENT_PURPLE = (142, 68, 173)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(
                0,
                10,
                "Marine Risk Mapping -- Competitive Analysis",
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

    # -- Layout helpers -------------------------------------------

    def section_title(self, title: str) -> None:
        self.ln(4)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*self.NAVY)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.TEAL)
        self.set_line_width(0.6)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(4)

    def subsection_title(self, title: str) -> None:
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*self.TEAL)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def small_text(self, text: str) -> None:
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*self.MID_TEXT)
        self.multi_cell(0, 4.5, text)
        self.ln(1)

    def bullet(self, text: str, indent: int = 15) -> None:
        x = self.get_x()
        self.set_x(x + indent - 5)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.TEAL)
        self.cell(5, 5.5, "-")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def numbered_item(self, number: str, text: str, indent: int = 15) -> None:
        x = self.get_x()
        self.set_x(x + indent - 5)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.TEAL)
        self.cell(8, 5.5, number)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def stat_boxes(self, stats: list, y: float | None = None) -> None:
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

    def metric_table(
        self,
        headers: list,
        rows: list,
        col_widths: list | None = None,
    ) -> None:
        if col_widths is None:
            col_widths = [190 // len(headers)] * len(headers)
        self.set_fill_color(*self.NAVY)
        self.set_text_color(*self.WHITE)
        self.set_font("Helvetica", "B", 8)
        for w, h_text in zip(col_widths, headers, strict=False):
            self.cell(w, 7, f"  {h_text}", fill=True)
        self.ln()
        self.set_font("Helvetica", "", 8)
        for i, row in enumerate(rows):
            if self.get_y() > 265:
                self.add_page()
                # Re-draw header row on new page
                self.set_fill_color(*self.NAVY)
                self.set_text_color(*self.WHITE)
                self.set_font("Helvetica", "B", 8)
                for w, h_text in zip(col_widths, headers, strict=False):
                    self.cell(w, 7, f"  {h_text}", fill=True)
                self.ln()
                self.set_font("Helvetica", "", 8)
            bg = self.LIGHT_BG if i % 2 == 0 else self.WHITE
            self.set_fill_color(*bg)
            for j, (w, cell_val) in enumerate(zip(col_widths, row, strict=False)):
                if j == 0:
                    self.set_text_color(*self.DARK_TEXT)
                else:
                    self.set_text_color(*self.TEAL)
                self.cell(w, 6, f"  {cell_val}", fill=True)
            self.ln()
        self.ln(3)

    def callout_box(
        self,
        title: str,
        text: str,
        colour: tuple | None = None,
    ) -> None:
        if colour is None:
            colour = self.ACCENT_BLUE
        if self.get_y() > 240:
            self.add_page()
        y_start = self.get_y()
        self.set_font("Helvetica", "", 9.5)
        n_lines = max(1, len(text) // 75 + 1)
        box_h = 12 + n_lines * 5
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

    def verdict_badge(
        self,
        label: str,
        verdict: str,
        colour: tuple | None = None,
    ) -> None:
        if colour is None:
            colour = self.TEAL
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*colour)
        self.cell(24, 6, verdict)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.DARK_TEXT)
        self.cell(0, 6, label, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def platform_card(
        self,
        name: str,
        tagline: str,
        facts: list[tuple[str, str]],
        colour: tuple | None = None,
    ) -> None:
        """Render a coloured platform summary card."""
        if colour is None:
            colour = self.TEAL
        if self.get_y() > 230:
            self.add_page()
        y_start = self.get_y()
        card_h = 14 + len(facts) * 6
        # Background
        self.set_fill_color(*self.LIGHT_BG)
        self.rect(10, y_start, 190, card_h, style="F")
        # Colour bar
        self.set_fill_color(*colour)
        self.rect(10, y_start, 3, card_h, style="F")
        # Name
        self.set_xy(16, y_start + 2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*colour)
        self.cell(60, 6, name)
        # Tagline
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(*self.MID_TEXT)
        self.cell(0, 6, tagline)
        # Fact rows
        for idx, (key, val) in enumerate(facts):
            self.set_xy(18, y_start + 10 + idx * 6)
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(*self.DARK_TEXT)
            self.cell(40, 5, key)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(0, 5, val)
        self.set_y(y_start + card_h + 4)


# =================================================================
# Build report content
# =================================================================


def build_report() -> None:  # noqa: C901 PLR0915
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Cover page ──────────────────────────────────────────
    pdf.add_page()
    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.rect(0, 0, 210, 297, style="F")
    pdf.set_y(70)
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.cell(0, 15, "Competitive Analysis", align="C")
    pdf.ln(12)
    pdf.set_font("Helvetica", "", 15)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "Citizen Science & Cetacean Platforms",
        align="C",
    )
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 13)
    pdf.cell(
        0,
        10,
        "Marine Risk Mapping Platform",
        align="C",
    )
    pdf.ln(20)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(180, 200, 220)
    pdf.cell(
        0,
        8,
        "iNaturalist | Happywhale | Zooniverse | OBIS",
        align="C",
    )
    pdf.ln(8)
    pdf.cell(0, 8, "March 2026", align="C")
    pdf.ln(30)

    # Cover stat boxes
    box_data = [
        ("5", "Platforms Compared"),
        ("30+", "Features Audited"),
        ("7", "Unique Advantages"),
        ("4", "Key Gaps"),
    ]
    box_w, gap = 38, 8
    x_start = (210 - (box_w * 4 + gap * 3)) / 2
    y_box = pdf.get_y()
    for i, (val, label) in enumerate(box_data):
        x = x_start + i * (box_w + gap)
        pdf.set_fill_color(25, 50, 85)
        pdf.rect(x, y_box, box_w, 28, style="F")
        pdf.set_draw_color(*ReportPDF.TEAL)
        pdf.set_line_width(0.5)
        pdf.rect(x, y_box, box_w, 28, style="D")
        pdf.set_xy(x, y_box + 4)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(*ReportPDF.TEAL)
        pdf.cell(box_w, 10, val, align="C")
        pdf.set_xy(x, y_box + 16)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(180, 200, 220)
        pdf.cell(box_w, 6, label, align="C")

    # ── 1. Executive Summary ────────────────────────────────
    pdf.add_page()
    pdf.section_title("1. Executive Summary")
    pdf.body_text(
        "This report compares the Marine Risk Mapping platform's "
        "citizen science features against four established platforms "
        "in the marine / biodiversity space: iNaturalist, Happywhale, "
        "Zooniverse, and OBIS. The analysis concludes that our platform "
        "occupies a unique niche -- risk-aware citizen observation -- "
        "that none of the incumbents fill. We are not duplicating "
        "iNaturalist. The overlap is thin and the divergence is "
        "fundamental."
    )
    pdf.callout_box(
        "Core Finding",
        "iNaturalist answers 'what did you see?' -- we answer "
        "'what did you see, how dangerous is it here for that animal, "
        "and who should you call?' No existing platform combines "
        "real-time collision risk enrichment with citizen science "
        "observation.",
        ReportPDF.TEAL,
    )
    pdf.ln(2)
    pdf.stat_boxes(
        [
            ("96", "API Endpoints"),
            ("8", "ML Species"),
            ("7", "Risk Sub-scores"),
            ("138", "Crosswalk Taxa"),
        ]
    )
    pdf.ln(2)
    pdf.body_text(
        "Our platform's unique value proposition centres on three "
        "pillars: (1) dual photo+audio ML classification with "
        "consensus reconciliation, (2) real-time H3 collision risk "
        "enrichment with 7 sub-scores on every sighting, and "
        "(3) actionable NOAA-routed advisories. These capabilities "
        "transform passive biodiversity observation into operational "
        "risk reduction."
    )

    # ── 2. Platform Profiles ────────────────────────────────
    pdf.add_page()
    pdf.section_title("2. Platform Profiles")
    pdf.body_text(
        "Brief profiles of each platform in the competitive "
        "landscape, highlighting their core mission and scale."
    )

    pdf.platform_card(
        "iNaturalist",
        "All-taxa global biodiversity observation",
        [
            ("Scale:", "~10M users, ~200M observations, 490K+ species"),
            ("Founded:", "2008 (UC Berkeley), independent nonprofit 2023"),
            ("Core:", "Photo-based species ID with community consensus"),
            ("Export:", "Auto-syncs Research Grade to GBIF"),
            ("Mobile:", "iOS + Android + Seek (AR camera)"),
        ],
        ReportPDF.ACCENT_GREEN,
    )
    pdf.platform_card(
        "Happywhale",
        "Individual marine mammal re-identification",
        [
            ("Scale:", "1.4M photos, 137K individuals, 449K encounters"),
            ("Founded:", "2015, with ~90 marine mammal species"),
            ("Core:", "Fluke/fin pattern matching for individual tracking"),
            ("Data use:", "Research partnerships (Cascadia Research, etc.)"),
            ("Mobile:", "iOS + Android"),
        ],
        ReportPDF.ACCENT_BLUE,
    )
    pdf.platform_card(
        "Zooniverse",
        "Crowdsourced research classification platform",
        [
            ("Scale:", "2.7M volunteers, 100+ active projects"),
            ("Founded:", "2009 (Citizen Science Alliance)"),
            ("Core:", "Task-based classification workflows for researchers"),
            ("Marine:", "Cetalingua (marine mammal communication decoding)"),
            ("Mobile:", "iOS + Android"),
        ],
        ReportPDF.ACCENT_PURPLE,
    )
    pdf.platform_card(
        "OBIS",
        "Ocean Biodiversity Information System",
        [
            ("Scale:", "168M records, 204K species, 7K datasets"),
            ("Founded:", "2000 (IOC-UNESCO)"),
            ("Core:", "Data aggregation + interoperability layer"),
            ("Standard:", "Darwin Core, WoRMS taxonomy backbone"),
            ("Role:", "Does not collect observations; aggregates them"),
        ],
        ReportPDF.ACCENT_AMBER,
    )
    pdf.platform_card(
        "Marine Risk Mapping (Ours)",
        "Risk-aware whale observation + collision risk reduction",
        [
            ("Endpoints:", "96 API endpoints, 14 frontend pages"),
            ("ML:", "EfficientNet-B4 photo + XGBoost/CNN audio (8 spp.)"),
            ("Risk:", "7-sub-score H3 composite risk on every sighting"),
            ("Export:", "OBIS Darwin Core Archive (WoRMS LSIDs, NERC vocabs)"),
            ("Mobile:", "Responsive web only (no native app)"),
        ],
        ReportPDF.TEAL,
    )

    # ── 3. Feature Comparison Matrix ────────────────────────
    pdf.add_page()
    pdf.section_title("3. Feature Comparison Matrix")
    pdf.body_text(
        "Head-to-head capability comparison across all five platforms. "
        "Y = present, N = absent, P = partial."
    )

    headers = [
        "Capability",
        "Us",
        "iNaturalist",
        "Happywhale",
        "Zooniverse",
        "OBIS",
    ]
    widths = [58, 22, 30, 28, 28, 24]
    rows = [
        ["Photo species ID", "Y (auto)", "Y (CV)", "Y (indiv.)", "P", "N"],
        ["Audio species ID", "Y (auto)", "P (attach)", "N", "N", "N"],
        ["Server-side ML", "Y (dual)", "Y (70K taxa)", "Y (re-ID)", "P", "N"],
        ["Individual re-ID", "N", "N", "Y", "N", "N"],
        ["Collision risk context", "Y (7 scores)", "N", "N", "N", "N"],
        ["Risk advisory routing", "Y (7 regions)", "N", "N", "N", "N"],
        ["Climate projections", "Y (CMIP6)", "N", "N", "N", "N"],
        ["Vessel traffic data", "Y (3.1B AIS)", "N", "N", "N", "N"],
        ["Location pre-check", "Y (GEBCO)", "N (post-hoc)", "N", "N", "N"],
        ["Community verification", "Y (weighted)", "Y (2/3 vote)", "N", "N", "N"],
        ["Reputation system", "Y (5 tiers)", "N", "N", "N", "N"],
        ["Group events", "Y (full CRUD)", "Y (Projects)", "N", "N", "N"],
        ["OBIS DwC-A export", "Y", "N (GBIF)", "N", "N", "Is OBIS"],
        ["Biological metadata", "Y (12+ fields)", "P (5 fields)", "N", "N", "Y"],
        ["Mobile app", "N", "Y", "Y", "Y", "N"],
        ["Offline capability", "N", "Y (Seek)", "P", "N", "N"],
        ["Vessel profiles", "Y", "N", "N", "N", "N"],
        ["Taxonomic crosswalk", "Y (138 taxa)", "Y (full tree)", "P", "N", "Y"],
    ]
    pdf.metric_table(headers, rows, widths)

    # ── 4. The iNaturalist Question ─────────────────────────
    pdf.add_page()
    pdf.section_title("4. Are We Duplicating iNaturalist?")

    pdf.callout_box(
        "Verdict: No",
        "The overlap is thin and the divergence is fundamental. "
        "iNaturalist is a horizontal biodiversity network covering "
        "490K+ species across all kingdoms. We are a vertical, "
        "domain-specific platform for cetacean-vessel collision "
        "risk reduction with operational outputs.",
        ReportPDF.ACCENT_GREEN,
    )
    pdf.ln(2)

    pdf.subsection_title("What iNaturalist Does That We Do Not")
    pdf.bullet(
        "All-taxa, global biodiversity -- 490K+ species from lichen "
        "to leopards. We are cetaceans-only by design (8 target species)."
    )
    pdf.bullet(
        "Massive community flywheel -- 10M users and 200M+ observations "
        "built over 18 years. That scale cannot be replicated."
    )
    pdf.bullet(
        "Mobile-first experience -- dedicated iOS/Android apps with "
        "offline capability via Seek. We are responsive web only."
    )
    pdf.bullet(
        "GBIF auto-sync -- Research Grade observations flow directly "
        "into GBIF, the terrestrial+marine global biodiversity facility."
    )
    pdf.bullet(
        "Broad taxonomic CV model covering ~70,000 taxa. Ours is "
        "laser-focused on 8 whale species but goes deeper per species."
    )

    pdf.subsection_title("What We Do That iNaturalist Cannot")

    pdf.numbered_item(
        "1.",
        "Real-time collision risk enrichment -- every sighting returns "
        "a 7-sub-score composite collision risk breakdown from "
        "fct_collision_risk (traffic, cetacean density, strike history, "
        "habitat, proximity, protection gap, reference risk). No "
        "biodiversity platform does this.",
    )
    pdf.numbered_item(
        "2.",
        "Dual ML classifier pipeline -- both photo (EfficientNet-B4) "
        "and audio (XGBoost/CNN) classifiers run on every upload, with "
        "intelligent consensus reconciliation. iNat has photo-only CV.",
    )
    pdf.numbered_item(
        "3.",
        "Actionable advisories -- plain-language risk advisories routed "
        "to the correct NOAA regional office (7 regions) with phone, "
        "email, and stranding hotline. Escalated for ESA-protected "
        "species or strike/entanglement events.",
    )
    pdf.numbered_item(
        "4.",
        "Vessel traffic integration -- risk model incorporates 3.1 "
        "billion AIS pings of real vessel traffic. Sightings exist "
        "within a traffic context. iNat has no anthropogenic layers.",
    )
    pdf.numbered_item(
        "5.",
        "Climate-projected risk -- CMIP6 scenarios (SSP2-4.5, "
        "SSP5-8.5, 2030s-2080s) project risk forward. No citizen "
        "science platform does future risk assessment.",
    )
    pdf.numbered_item(
        "6.",
        "OBIS-specific DwC-A export with WoRMS LSIDs and NERC/BODC "
        "measurement vocabularies. iNat feeds GBIF; we feed OBIS. "
        "Different destination, complementary coverage.",
    )
    pdf.numbered_item(
        "7.",
        "Location pre-validation via GEBCO bathymetry -- checks "
        "land/ocean and risk coverage before submission. iNat relies "
        "on post-hoc community voting to flag bad locations.",
    )

    # ── 5. Overlap Analysis ─────────────────────────────────
    pdf.add_page()
    pdf.section_title("5. Genuine Overlap & Differentiation")

    pdf.body_text(
        "Some feature categories do overlap with existing platforms. "
        "Here we examine each area of overlap and how our "
        "implementation diverges."
    )

    overlap_headers = [
        "Feature",
        "iNaturalist",
        "Our Approach",
        "Differentiation",
    ]
    overlap_widths = [30, 45, 50, 65]
    overlap_rows = [
        [
            "Photo species ID",
            "CV 'Visually Similar'",
            "Server-side EfficientNet",
            "Ours is automatic + confidence",
        ],
        [
            "Verification",
            "2/3 majority vote",
            "Reputation-weighted",
            "Expert votes count 4x more",
        ],
        [
            "Events",
            "Collection Projects",
            "Full event lifecycle",
            "Invite codes, sighting linking",
        ],
        [
            "Leaderboards",
            "Obs count, species",
            "Submissions + rep + boats",
            "Vessel profiles are unique",
        ],
        [
            "Data export",
            "CSV, DwC to GBIF",
            "DwC-A ZIP to OBIS",
            "Different target network",
        ],
    ]
    pdf.metric_table(overlap_headers, overlap_rows, overlap_widths)

    pdf.subsection_title("Overlap with Happywhale")
    pdf.body_text(
        "Happywhale is closer to our domain than iNaturalist, but "
        "still divergent. Their core feature is individual "
        "re-identification -- tracking 137,847 individual whales by "
        "fluke and fin patterns across 449,351 encounters. We do "
        "not do individual re-ID; we do species-level classification."
    )
    pdf.bullet(
        "Happywhale has no risk model, no traffic data, no collision "
        "risk scores, and no advisories."
    )
    pdf.bullet("Happywhale has no audio classification -- it is photo-only.")
    pdf.bullet(
        "Happywhale's community model is researcher-centric (photos "
        "flow to Cascadia Research Collective, etc.). Ours is "
        "risk-reduction-centric."
    )
    pdf.bullet(
        "The two platforms are complementary: a user could submit "
        "to Happywhale for individual tracking AND to our platform "
        "for risk context. There is no reason they cannot coexist."
    )

    # ── 6. Our Unique Advantages ────────────────────────────
    pdf.add_page()
    pdf.section_title("6. Our Unique Advantages")
    pdf.body_text(
        "Features that no competing platform offers, forming our "
        "core defensible differentiation."
    )

    advantages = [
        (
            "Dual ML Classifier Pipeline",
            "Both photo (CNN) and audio (XGBoost/CNN) classifiers run on "
            "every upload with intelligent consensus reconciliation. Most "
            "citizen science apps have no server-side ML or only photo. "
            "Audio classification of underwater recordings is unique.",
        ),
        (
            "Real-Time Collision Risk Enrichment",
            "Every sighting is geocoded to an H3 cell and returned with "
            "a 7-sub-score composite collision risk breakdown -- not just "
            "species classification. This couples conservation monitoring "
            "to operational risk assessment.",
        ),
        (
            "NOAA Regional Authority Routing",
            "Advisories include the correct NOAA regional office phone, "
            "email, and stranding hotline based on the sighting's "
            "coordinates (7 geographic regions). Strike, entanglement, "
            "and stranding events escalate to immediate-contact urgency.",
        ),
        (
            "Reputation-Weighted Verification",
            "Community votes are weighted by the voter's reputation tier "
            "(Newcomer 1x through Authority 4x). Credentials can be "
            "verified by administrators for +20 reputation points. This "
            "is more sophisticated than iNaturalist's flat majority rule.",
        ),
        (
            "OBIS-Ready DwC-A Export",
            "Verified sightings export as Darwin Core Archives with "
            "WoRMS LSID species identifiers, NERC/BODC vocabulary URIs "
            "for measurement terms, and EML metadata -- purpose-built "
            "for the Ocean Biodiversity Information System.",
        ),
        (
            "Location Pre-Validation",
            "Real-time GEBCO bathymetry check before submission tells "
            "the user if coordinates are on land or outside risk model "
            "coverage. Prevents junk GPS data at the source rather "
            "than relying on post-hoc community flagging.",
        ),
        (
            "Climate-Projected Risk Assessment",
            "CMIP6 projections (SSP2-4.5, SSP5-8.5, 2030s-2080s) using "
            "ISDM+SDM ensemble whale predictions to forecast how "
            "collision risk will shift under climate change. No citizen "
            "science platform offers future-state risk modelling.",
        ),
    ]
    for title, text in advantages:
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.callout_box(title, text, ReportPDF.TEAL)

    # ── 7. Honest Gaps ──────────────────────────────────────
    pdf.add_page()
    pdf.section_title("7. Honest Gaps")
    pdf.body_text(
        "An honest assessment of areas where competing platforms "
        "have clear advantages over our current implementation."
    )

    gaps = [
        (
            "No Mobile App",
            "CRITICAL",
            "Every competitor has a native mobile app. This is the "
            "single biggest adoption barrier for field-based citizen "
            "science. A whale watcher on a boat is not opening a "
            "browser. A progressive web app (PWA) or React Native "
            "wrapper would address this.",
        ),
        (
            "No Individual Re-Identification",
            "MEDIUM",
            "Happywhale's fluke-matching is compelling for repeat "
            "engagement ('your whale was seen again in Baja!'). Our "
            "photo classifier architecture supports a future metric "
            "learning extension (ArcFace loss on embeddings) for "
            "individual re-ID, but it is not yet implemented.",
        ),
        (
            "Community Scale = Zero",
            "HIGH",
            "Features do not matter without users. iNaturalist has "
            "10M users; Happywhale has 1.4M photos submitted. Our "
            "verification system is well-designed but untested at "
            "scale. Community building, partnerships with whale watch "
            "operators, and research institution outreach are needed.",
        ),
        (
            "No Offline Capability",
            "MEDIUM",
            "Whale watching often happens in low-connectivity "
            "environments (open ocean, remote coastlines). iNaturalist's "
            "Seek app works fully offline. A PWA with service worker "
            "caching and deferred upload would close this gap.",
        ),
    ]

    for title, severity, text in gaps:
        if pdf.get_y() > 235:
            pdf.add_page()
        colour_map = {
            "CRITICAL": ReportPDF.ACCENT_RED,
            "HIGH": ReportPDF.ACCENT_AMBER,
            "MEDIUM": ReportPDF.ACCENT_BLUE,
            "LOW": ReportPDF.ACCENT_GREEN,
        }
        colour = colour_map.get(severity, ReportPDF.MID_TEXT)
        pdf.callout_box(f"[{severity}] {title}", text, colour)

    # ── 8. Strategic Positioning ────────────────────────────
    pdf.add_page()
    pdf.section_title("8. Strategic Positioning")
    pdf.body_text(
        "Our platform occupies a unique niche that none of the "
        "existing platforms fill: risk-aware citizen observation. "
        "The competitive landscape segments into four quadrants."
    )

    pdf.subsection_title("Market Segmentation")
    segment_headers = [
        "Segment",
        "Platform",
        "Mission",
    ]
    segment_widths = [50, 45, 95]
    segment_rows = [
        [
            "Pure Observation",
            "iNaturalist",
            "Record what you see (all taxa, global)",
        ],
        [
            "Individual Tracking",
            "Happywhale",
            "Re-ID individuals for population science",
        ],
        [
            "Research Tasks",
            "Zooniverse",
            "Crowdsource classification for researchers",
        ],
        [
            "Data Aggregation",
            "OBIS / GBIF",
            "Interoperability layer for science",
        ],
        [
            "Risk-Aware Obs.",
            "Ours",
            "Collision risk context + advisories + ML ID",
        ],
    ]
    pdf.metric_table(segment_headers, segment_rows, segment_widths)

    pdf.subsection_title("Complementary, Not Competitive")
    pdf.body_text(
        "Our platform is designed to complement rather than replace "
        "existing platforms. The data flows are additive:"
    )
    pdf.bullet("A user photographs a humpback fluke from a whale-watch boat.")
    pdf.bullet(
        "They submit to Happywhale for individual re-identification "
        "and population tracking."
    )
    pdf.bullet(
        "They submit to our platform for collision risk context, "
        "species classification, and a NOAA advisory."
    )
    pdf.bullet("Our verified sighting exports to OBIS via Darwin Core Archive.")
    pdf.bullet(
        "OBIS aggregates it alongside iNaturalist data (via GBIF) "
        "into the global marine biodiversity record."
    )

    pdf.ln(4)
    pdf.body_text(
        "Each platform serves a different purpose in this chain. "
        "We fill the 'risk-aware observation' gap that currently has "
        "no dedicated platform."
    )

    # ── 9. Recommendations ──────────────────────────────────
    pdf.add_page()
    pdf.section_title("9. Recommendations")
    pdf.body_text(
        "Based on this analysis, the following priorities would "
        "maximise the platform's competitive positioning."
    )

    pdf.subsection_title("Near-Term (0-3 months)")
    pdf.numbered_item(
        "1.",
        "Progressive Web App (PWA) -- add a service worker, app "
        "manifest, and offline queue for deferred sighting upload. "
        "This closes the mobile gap without building native apps.",
    )
    pdf.numbered_item(
        "2.",
        "Whale-watch operator partnerships -- onboard 3-5 commercial "
        "whale-watch companies as beta users. Their guides submit "
        "sightings on every trip, seeding the community flywheel.",
    )
    pdf.numbered_item(
        "3.",
        "iNaturalist cross-posting -- allow users to optionally "
        "cross-post verified sightings to iNaturalist (via their API), "
        "reaching the 10M-user community while keeping the risk "
        "context unique to our platform.",
    )

    pdf.subsection_title("Medium-Term (3-6 months)")
    pdf.numbered_item(
        "4.",
        "Individual re-identification -- add metric learning (ArcFace "
        "loss) on the EfficientNet-B4 penultimate layer for fluke/fin "
        "embedding matching. This adds the Happywhale engagement "
        "pattern ('your whale was seen again!').",
    )
    pdf.numbered_item(
        "5.",
        "Happywhale data integration -- ingest Happywhale's public "
        "encounter data to enrich our risk model with individual "
        "movement patterns and population estimates.",
    )
    pdf.numbered_item(
        "6.",
        "Research institution API access -- tiered API keys for "
        "universities and NGOs to query risk data programmatically, "
        "positioning the platform as research infrastructure.",
    )

    pdf.subsection_title("Long-Term (6-12 months)")
    pdf.numbered_item(
        "7.",
        "Native mobile apps (iOS/Android) -- if the PWA proves "
        "insufficient for field use, build native apps with camera "
        "integration, offline-first architecture, and push "
        "notifications for nearby whale alerts.",
    )
    pdf.numbered_item(
        "8.",
        "Real-time vessel alerting -- combine AIS live feeds with "
        "sighting reports to alert vessels entering high-risk areas "
        "where whales were recently observed. This transforms "
        "citizen science into active collision prevention.",
    )
    pdf.numbered_item(
        "9.",
        "Multi-region expansion -- extend beyond the US study area "
        "(CONUS, Alaska, Hawaii, Caribbean) to global shipping lanes "
        "(Mediterranean, Strait of Malacca, Great Barrier Reef) "
        "using regional AIS and sighting data.",
    )

    # ── 10. Conclusion ──────────────────────────────────────
    if pdf.get_y() > 200:
        pdf.add_page()
    pdf.section_title("10. Conclusion")
    pdf.body_text(
        "The Marine Risk Mapping platform is not a duplication of "
        "iNaturalist, Happywhale, or any existing citizen science "
        "platform. It occupies a genuinely novel niche: risk-aware "
        "observation that couples species identification with "
        "real-time collision risk assessment and actionable "
        "regulatory routing."
    )
    pdf.body_text(
        "The competitive landscape is complementary rather than "
        "adversarial. Our platform fills the missing risk layer "
        "that existing observation platforms do not provide. The "
        "primary challenges are adoption (no mobile app, no community "
        "at scale) rather than feature differentiation. "
        "Addressing the mobile gap via a PWA, seeding the community "
        "through whale-watch operator partnerships, and building "
        "cross-platform data bridges (iNaturalist cross-posting, "
        "Happywhale integration, OBIS export) will position the "
        "platform as a unique and essential piece of the marine "
        "conservation technology ecosystem."
    )

    pdf.callout_box(
        "Bottom Line",
        "We are building the missing 'risk layer' on top of the "
        "citizen science observation pattern. iNaturalist answers "
        "'what did you see?' -- we answer 'what did you see, how "
        "dangerous is it here for that animal, and who should you "
        "call?'",
        ReportPDF.TEAL,
    )

    # ── Write ───────────────────────────────────────────────
    pdf.output(str(OUTPUT_FILE))
    print(f"Report generated: {OUTPUT_FILE}")
    print(f"  Pages: {pdf.page_no()}")


if __name__ == "__main__":
    build_report()

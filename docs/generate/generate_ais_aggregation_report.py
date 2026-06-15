"""Generate a styled PDF documenting the AIS H3 aggregation design.

Covers:
  - Why we aggregate (the problem)
  - How the two-pass pipeline works
  - Ping-rate bias and the debiasing approach
  - Full output schema with weighting annotations
  - Design decisions and thresholds

Run with:
    uv run python docs/generate_ais_aggregation_report.py
"""

from fpdf import FPDF


class ReportPDF(FPDF):
    """Custom PDF with header/footer styling matching project reports."""

    NAVY = (15, 32, 65)
    TEAL = (0, 150, 136)
    LIGHT_BG = (240, 245, 250)
    WHITE = (255, 255, 255)
    DARK_TEXT = (30, 30, 30)
    MID_TEXT = (80, 80, 80)
    ACCENT_GREEN = (46, 204, 113)
    ACCENT_AMBER = (243, 156, 18)
    ACCENT_RED = (231, 76, 60)
    ACCENT_BLUE = (52, 152, 219)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(
                0,
                10,
                "Marine Risk Mapping - AIS Aggregation Design",
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

    def callout_box(self, title, text, colour):
        """Draw a coloured callout box with a left accent bar."""
        y_start = self.get_y()
        if y_start > 250:
            self.add_page()
            y_start = self.get_y()

        # Measure height needed
        self.set_font("Helvetica", "", 9)
        line_count = len(text) / 85 + 1  # rough estimate
        box_h = max(20, 10 + line_count * 4.5)

        self.set_fill_color(*self.LIGHT_BG)
        self.rect(10, y_start, 190, box_h, style="F")
        self.set_fill_color(*colour)
        self.rect(10, y_start, 3, box_h, style="F")

        self.set_xy(16, y_start + 3)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.NAVY)
        self.cell(180, 5, title)

        self.set_xy(16, y_start + 9)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(178, 4.5, text)

        self.set_y(y_start + box_h + 3)

    def column_table(self, title, columns, col_widths=None):
        """Draw a styled table of output columns.

        columns: list of (name, weighting, description) tuples
        """
        if col_widths is None:
            col_widths = [58, 20, 112]

        y = self.get_y()
        if y > 240:
            self.add_page()

        self.subsection_title(title)

        # Header row
        self.set_fill_color(*self.NAVY)
        self.set_text_color(*self.WHITE)
        self.set_font("Helvetica", "B", 8)
        headers = ["Column", "Weight", "Description"]
        for w, h in zip(col_widths, headers):
            self.cell(w, 7, h, border=1, fill=True, align="C")
        self.ln()

        # Data rows
        self.set_font("Helvetica", "", 7.5)
        for i, (name, weight, desc) in enumerate(columns):
            y = self.get_y()
            if y > 272:
                self.add_page()
                # Re-draw header on new page
                self.set_fill_color(*self.NAVY)
                self.set_text_color(*self.WHITE)
                self.set_font("Helvetica", "B", 8)
                for w, h in zip(col_widths, headers):
                    self.cell(w, 7, h, border=1, fill=True, align="C")
                self.ln()
                self.set_font("Helvetica", "", 7.5)

            fill = i % 2 == 0
            if fill:
                self.set_fill_color(*self.LIGHT_BG)

            # Weight colour coding
            self.set_text_color(*self.DARK_TEXT)
            self.set_font("Helvetica", "", 7.5)
            self.cell(col_widths[0], 6, name, border=1, fill=fill)

            # Colour the weight indicator
            if weight == "Ping":
                self.set_text_color(*self.ACCENT_BLUE)
            elif weight == "Vessel":
                self.set_text_color(*self.ACCENT_GREEN)
            else:
                self.set_text_color(*self.MID_TEXT)
            self.set_font("Helvetica", "B", 7.5)
            self.cell(col_widths[1], 6, weight, border=1, fill=fill, align="C")

            self.set_text_color(*self.DARK_TEXT)
            self.set_font("Helvetica", "", 7.5)
            self.cell(col_widths[2], 6, desc, border=1, fill=fill)
            self.ln()

        self.ln(3)

    def decision_card(self, number, title, description):
        """Draw a numbered design decision card."""
        card_w = 190
        y_start = self.get_y()

        if y_start > 245:
            self.add_page()
            y_start = self.get_y()

        # Measure needed height
        self.set_font("Helvetica", "", 8.5)
        n_lines = max(2, len(description) // 80 + 1)
        card_h = max(20, 10 + n_lines * 4.5)

        self.set_fill_color(*self.LIGHT_BG)
        self.rect(10, y_start, card_w, card_h, style="F")

        # Number circle
        self.set_fill_color(*self.TEAL)
        cx = 20
        cy = y_start + card_h / 2
        self.ellipse(cx - 5, cy - 5, 10, 10, style="F")
        self.set_xy(cx - 5, cy - 3.5)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.WHITE)
        self.cell(10, 7, str(number), align="C")

        # Title
        self.set_xy(28, y_start + 3)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.NAVY)
        self.cell(168, 6, title)

        # Description
        self.set_xy(28, y_start + 10)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(168, 4.5, description)

        self.set_y(y_start + card_h + 3)


def build_report():
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── COVER PAGE ──────────────────────────────────
    pdf.add_page()
    pdf.ln(40)

    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.rect(0, 30, 210, 65, style="F")

    pdf.set_xy(10, 35)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.cell(
        0,
        14,
        "AIS Aggregation Design",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "From 3.1 Billion Pings to Risk-Ready Features",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "I", 11)
    pdf.set_text_color(180, 200, 220)
    pdf.cell(
        0,
        10,
        "Marine Risk Mapping Project  |  February 2026",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(28)

    # Stats boxes
    stats = [
        ("3.1B", "Raw AIS Pings"),
        ("~15M", "Output Rows"),
        ("66", "Feature Columns"),
        ("H3 Res 7", "~1.2km Cells"),
    ]
    box_w = 42
    gap = 4
    x_start = 10 + (190 - (box_w * 4 + gap * 3)) / 2
    y_stat = pdf.get_y()

    for i, (value, label) in enumerate(stats):
        x = x_start + i * (box_w + gap)
        pdf.set_fill_color(*ReportPDF.LIGHT_BG)
        pdf.rect(x, y_stat, box_w, 22, style="F")

        pdf.set_xy(x, y_stat + 3)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*ReportPDF.TEAL)
        pdf.cell(box_w, 8, value, align="C")

        pdf.set_xy(x, y_stat + 12)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*ReportPDF.MID_TEXT)
        pdf.cell(box_w, 6, label, align="C")

    pdf.set_y(y_stat + 30)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*ReportPDF.DARK_TEXT)
    pdf.multi_cell(
        0,
        5.5,
        (
            "This document describes how raw AIS (Automatic Identification System) "
            "vessel position data is aggregated into H3 hexagonal grid cells for "
            "use in whale-vessel collision risk modelling. It covers the pipeline "
            "architecture, the ping-rate debiasing strategy, the full output "
            "schema with 66 feature columns, execution and PostGIS loading, "
            "and the CLI interface for running the pipeline."
        ),
        align="C",
    )

    # ── THE PROBLEM ─────────────────────────────────
    pdf.add_page()
    pdf.section_title("1. The Problem")

    pdf.body_text(
        "The US Coast Guard collects AIS broadcasts from every vessel in US "
        "waters. MarineCadastre publishes this as daily parquet files - one "
        "year of data contains approximately 3.1 billion position reports "
        "across 365 files."
    )

    pdf.body_text(
        "This raw data cannot be used directly for risk modelling. It is too "
        "large for spatial joins (3.1B rows x cetacean sightings x MPA "
        "polygons), the point data has no spatial aggregation unit, and each "
        "raw ping carries minimal context about the traffic pattern in its "
        "vicinity."
    )

    pdf.body_text(
        "We need to compress 3.1 billion pings into a manageable set of "
        "spatially-aggregated features that capture traffic intensity, vessel "
        "characteristics, speed risk, and temporal patterns - all at a "
        "resolution fine enough to distinguish shipping lanes from quiet waters."
    )

    pdf.callout_box(
        "Goal",
        "Transform 3.1B raw AIS pings into ~15M rows of cell-level monthly "
        "traffic features, suitable for spatial joins with cetacean sightings "
        "and MPA boundaries in PostGIS.",
        ReportPDF.TEAL,
    )

    # ── SPATIAL GRID ────────────────────────────────
    pdf.section_title("2. Spatial Grid: H3 Hexagons")

    pdf.body_text(
        "H3 (developed by Uber) is a hierarchical hexagonal grid system that "
        "tiles the Earth's surface. Unlike square grids, hexagons have uniform "
        "adjacency (every neighbour is equidistant) and avoid edge/corner "
        "ambiguity. This makes them ideal for spatial aggregation and "
        "neighbourhood analysis."
    )

    pdf.subsection_title("Resolution choice: Level 7")

    # Resolution comparison table
    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.set_font("Helvetica", "B", 9)
    col_w = [30, 40, 40, 80]
    for w, h in zip(col_w, ["Resolution", "Edge Length", "Cell Area", "Use Case"]):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*ReportPDF.DARK_TEXT)
    res_rows = [
        ("4", "~22 km", "~1,770 km2", "Coarse rollup, regional dashboards"),
        ("5", "~8 km", "~253 km2", "Moderate, shipping corridor level"),
        ("6", "~3.2 km", "~36 km2", "Fine, port approach level"),
        ("7", "~1.2 km", "~5.2 km2", "Very fine - our base resolution"),
        ("8", "~0.5 km", "~0.74 km2", "Harbour-level (too granular for open ocean)"),
    ]
    for i, row in enumerate(res_rows):
        fill = i % 2 == 0
        if fill:
            pdf.set_fill_color(*ReportPDF.LIGHT_BG)
        bold = row[0] == "7"
        if bold:
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(*ReportPDF.TEAL)
        for w, val in zip(col_w, row):
            pdf.cell(w, 7, val, border=1, fill=fill, align="C")
        pdf.ln()
        if bold:
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(*ReportPDF.DARK_TEXT)

    pdf.ln(3)
    pdf.body_text(
        "Resolution 7 (~1.2km edge, ~5.2 km2 area) is fine enough to "
        "distinguish individual shipping lanes and port approaches, while "
        "coarse enough to produce a manageable ~15M output rows for a full "
        "year of study-area data. Resolution 4 rollup can be derived later "
        "by truncating H3 indices for regional dashboards."
    )

    # ── THE PING-RATE BIAS PROBLEM ──────────────────
    pdf.add_page()
    pdf.section_title("3. The Ping-Rate Bias Problem")

    pdf.body_text(
        "AIS transponders broadcast at different rates depending on vessel "
        "class and dynamic conditions:"
    )

    # Broadcast rate table
    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.set_font("Helvetica", "B", 9)
    bcast_w = [45, 45, 45, 55]
    for w, h in zip(bcast_w, ["Transponder", "Condition", "Interval", "Pings/Hour"]):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*ReportPDF.DARK_TEXT)
    bcast_rows = [
        ("Class A", "Moving > 23 kn", "2 seconds", "1,800"),
        ("Class A", "Moving 0-14 kn", "10 seconds", "360"),
        ("Class A", "At anchor", "3 minutes", "20"),
        ("Class B", "Moving > 2 kn", "30 seconds", "120"),
        ("Class B", "Stationary", "3 minutes", "20"),
    ]
    for i, row in enumerate(bcast_rows):
        fill = i % 2 == 0
        if fill:
            pdf.set_fill_color(*ReportPDF.LIGHT_BG)
        for w, val in zip(bcast_w, row):
            pdf.cell(w, 7, val, border=1, fill=fill, align="C")
        pdf.ln()

    pdf.ln(3)

    pdf.callout_box(
        "The bias",
        "A single Class A cargo ship moving slowly through a cell can generate "
        "15x more pings per hour than a Class B pleasure craft. In a naive "
        "aggregation, that one ship would dominate every average (speed, size, "
        "type distribution) in the cell - making it look like the cell is full "
        "of slow cargo ships when the reality is 1 cargo + 15 sailboats.",
        ReportPDF.ACCENT_RED,
    )

    pdf.callout_box(
        "The solution: two-pass aggregation",
        "Pass 1 collapses all pings for the same (cell, month, vessel) into a "
        "single summary row. Each vessel gets one vote regardless of how often "
        "it pinged. Pass 2 aggregates vessel summaries to cell level, producing "
        "both ping-weighted (exposure) and vessel-weighted (debiased) metrics.",
        ReportPDF.ACCENT_GREEN,
    )

    # ── PIPELINE ARCHITECTURE ───────────────────────
    pdf.add_page()
    pdf.section_title("4. Pipeline Architecture")

    pdf.body_text(
        "The aggregation is a single DuckDB SQL query with five CTEs, executed "
        "as a streaming pipeline. DuckDB never loads all 3.1B rows into memory "
        "- it processes parquet files in batches using columnar execution."
    )

    # Pipeline stages
    stages = [
        (
            "CTE 1: raw_pings",
            "Read all 365 parquet files via glob pattern. Extract lat/lon from "
            "GeoParquet geometry column using ST_Y/ST_X. Filter to moving "
            "vessels only (SOG > 0) - stationary vessels are not a collision "
            "risk. Convert zero-sentinel values in length/width/draft to NULL "
            "using NULLIF (0 means 'not reported' in AIS, not 'zero metres').",
        ),
        (
            "CTE 2: with_h3",
            "Assign each ping to an H3 resolution-7 cell via h3_latlng_to_cell(). "
            "Extract month for temporal grouping. Compute approximate local solar "
            "hour from longitude: local_hour = (UTC_hour + lon/15) mod 24. Uses "
            "double-mod to handle negative longitudes on the US coast.",
        ),
        (
            "CTE 3: with_time_of_day",
            "Add a boolean is_night flag. Night is defined as local solar hour "
            "< 06:00 or >= 20:00. This is approximate but more than adequate at "
            "monthly/cell granularity. Whale spotting is essentially impossible "
            "at night, making nighttime traffic higher risk.",
        ),
        (
            "CTE 4: vessel_summaries (PASS 1)",
            "Group by (h3_cell, month, mmsi) - one row per vessel per cell per "
            "month. Computes: ping count, static attributes via MAX (type, length, "
            "width, draft), median speed (robust to outliers), high-speed ping "
            "counts (overall + day/night), nav status counts, day/night ping "
            "splits and speeds, COG sin/cos components for circular statistics.",
        ),
        (
            "Final SELECT (PASS 2)",
            "Group by (h3_cell, month). Aggregates vessel summaries into ~66 "
            "output columns spanning traffic volume, speed, vessel size (length/"
            "width/draft), course diversity, navigational status, day/night "
            "splits, and vessel type breakdowns. Each metric category has both "
            "ping-weighted and vessel-weighted variants.",
        ),
        (
            "run_aggregation()",
            "Wraps the SQL query in a COPY ... TO statement that streams results "
            "directly to a ZSTD-compressed parquet file. DuckDB writes to disk "
            "without materialising the full result set in Python memory. Logs "
            "elapsed time, row count, and compressed file size.",
        ),
        (
            "load_to_postgis()",
            "Creates the ais_h3_summary table in PostGIS with all 66 columns "
            "correctly typed. Bulk-loads data via psycopg2 execute_values in "
            "10K-row batches. Creates indexes on h3_cell, month, and the "
            "composite (h3_cell, month) for efficient dbt spatial joins. "
            "Table is DROP + CREATE for full idempotency.",
        ),
    ]

    for stage_title, stage_desc in stages:
        y = pdf.get_y()
        if y > 248:
            pdf.add_page()

        pdf.set_fill_color(*ReportPDF.LIGHT_BG)
        # Estimate box height
        n_lines = len(stage_desc) // 80 + 2
        box_h = max(18, 10 + n_lines * 4.5)
        pdf.rect(10, pdf.get_y(), 190, box_h, style="F")
        pdf.set_fill_color(*ReportPDF.TEAL)
        pdf.rect(10, pdf.get_y(), 3, box_h, style="F")

        y_box = pdf.get_y()
        pdf.set_xy(16, y_box + 2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*ReportPDF.NAVY)
        pdf.cell(180, 5, stage_title)

        pdf.set_xy(16, y_box + 8)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*ReportPDF.DARK_TEXT)
        pdf.multi_cell(178, 4.5, stage_desc)

        pdf.set_y(y_box + box_h + 3)

    # ── WEIGHTING EXPLAINED ─────────────────────────
    pdf.add_page()
    pdf.section_title("5. Ping-Weighted vs Vessel-Weighted")

    pdf.body_text(
        "The output schema deliberately provides two views of the same "
        "underlying traffic. Each serves a different analytical purpose:"
    )

    pdf.callout_box(
        "Ping-Weighted (pw_) - Temporal Exposure",
        "A vessel lingering in a cell for 4 hours genuinely creates more "
        "collision risk than one passing through in 2 minutes. Ping-weighted "
        "metrics capture this exposure. Use these for: total collision "
        "opportunity, time-in-cell risk estimation, and exposure-based models "
        "where duration matters. Prefixed with pw_ or expressed as _pings.",
        ReportPDF.ACCENT_BLUE,
    )

    pdf.callout_box(
        "Vessel-Weighted (vw_) - Debiased Composition",
        "Each vessel gets one vote regardless of ping rate. A Class B sailboat "
        "and a Class A supertanker each count once. Use these for: vessel size "
        "distributions, type composition analysis, speed profiling across "
        "vessel classes, and any analysis where broadcast frequency should not "
        "influence the result. Prefixed with vw_ or expressed as _vessels.",
        ReportPDF.ACCENT_GREEN,
    )

    pdf.body_text(
        "For risk modelling, both perspectives matter. The model will likely "
        "consume both: vessel-weighted for 'what kind of traffic', and "
        "ping-weighted for 'how much exposure time'."
    )

    pdf.subsection_title("Example: Speed in a cell/month")

    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.set_font("Helvetica", "B", 8)
    ex_w = [48, 22, 120]
    for w, h in zip(ex_w, ["Column", "Weight", "Interpretation"]):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*ReportPDF.DARK_TEXT)
    speed_ex = [
        (
            "pw_avg_speed_knots",
            "Ping",
            "Weighted avg: slow lingering ships pull it down (exposure bias)",
        ),
        (
            "vw_avg_speed_knots",
            "Vessel",
            "Mean of per-vessel medians: each ship counts once",
        ),
        (
            "vw_median_speed_knots",
            "Vessel",
            "Median of per-vessel medians: robust to outlier vessels",
        ),
        (
            "high_speed_pings",
            "Ping",
            "Total pings > 10 kn: how much dangerous-speed time",
        ),
        (
            "high_speed_vessel_count",
            "Vessel",
            "How many vessels ever exceeded 10 kn in this cell",
        ),
    ]
    for i, (name, weight, desc) in enumerate(speed_ex):
        fill = i % 2 == 0
        if fill:
            pdf.set_fill_color(*ReportPDF.LIGHT_BG)
        pdf.cell(ex_w[0], 6, name, border=1, fill=fill)
        if weight == "Ping":
            pdf.set_text_color(*ReportPDF.ACCENT_BLUE)
        else:
            pdf.set_text_color(*ReportPDF.ACCENT_GREEN)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(ex_w[1], 6, weight, border=1, fill=fill, align="C")
        pdf.set_text_color(*ReportPDF.DARK_TEXT)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(ex_w[2], 6, desc, border=1, fill=fill)
        pdf.ln()

    # ── OUTPUT SCHEMA ───────────────────────────────
    pdf.add_page()
    pdf.section_title("6. Output Schema (66 Columns)")

    pdf.body_text(
        "Below is the complete output schema, grouped by feature category. "
        "Weight column is colour-coded: blue = ping-weighted, "
        "green = vessel-weighted, grey = unweighted (max, centroid, etc)."
    )

    # Key columns
    pdf.column_table(
        "Key + Spatial (4 columns)",
        [
            ("h3_cell", "--", "H3 resolution-7 cell identifier"),
            ("month", "--", "First day of month (date_trunc)"),
            ("cell_lat", "--", "Cell centroid latitude (from H3)"),
            ("cell_lon", "--", "Cell centroid longitude (from H3)"),
        ],
    )

    # Traffic volume
    pdf.column_table(
        "Traffic Volume (2 columns)",
        [
            ("ping_count", "Ping", "Total AIS broadcasts in cell/month"),
            ("unique_vessels", "Vessel", "Distinct MMSI count"),
        ],
    )

    # Speed
    pdf.column_table(
        "Speed (7 columns)",
        [
            ("pw_avg_speed_knots", "Ping", "Weighted avg of vessel median speeds"),
            ("max_speed_knots", "--", "Fastest single ping observed"),
            (
                "high_speed_pings",
                "Ping",
                "Total pings exceeding 10 kn (NOAA threshold)",
            ),
            (
                "high_speed_vessel_count",
                "Vessel",
                "Vessels that exceeded 10 kn at least once",
            ),
            ("vw_avg_speed_knots", "Vessel", "Mean of per-vessel median speeds"),
            ("vw_median_speed_knots", "Vessel", "Median of per-vessel median speeds"),
        ],
    )

    # Length
    pdf.column_table(
        "Vessel Length (6 columns)",
        [
            (
                "pw_avg_length_m",
                "Ping",
                "Ping-weighted avg (lingering ships weigh more)",
            ),
            ("vw_avg_length_m", "Vessel", "Simple mean of per-vessel max length"),
            ("max_length_m", "--", "Longest vessel to transit the cell"),
            ("p95_length_m", "Vessel", "95th percentile vessel length"),
            ("length_report_count", "Vessel", "How many vessels reported length"),
            ("large_vessel_count", "Vessel", "Vessels with length > 100m"),
        ],
    )

    # Width
    pdf.column_table(
        "Vessel Width (6 columns)",
        [
            ("pw_avg_width_m", "Ping", "Ping-weighted avg"),
            ("vw_avg_width_m", "Vessel", "Simple mean of per-vessel max width"),
            ("max_width_m", "--", "Widest vessel to transit the cell"),
            ("p95_width_m", "Vessel", "95th percentile vessel width"),
            ("width_report_count", "Vessel", "How many vessels reported width"),
            ("wide_vessel_count", "Vessel", "Vessels with width > 20m"),
        ],
    )

    # Draft
    pdf.column_table(
        "Vessel Draft (6 columns)",
        [
            ("pw_avg_draft_m", "Ping", "Ping-weighted avg"),
            ("vw_avg_draft_m", "Vessel", "Simple mean of per-vessel max draft"),
            ("max_draft_m", "--", "Deepest draft to transit the cell"),
            ("p95_draft_m", "Vessel", "95th percentile vessel draft"),
            (
                "draft_report_count",
                "Vessel",
                "How many vessels reported draft (~58% complete)",
            ),
            ("deep_draft_count", "Vessel", "Vessels with draft > 8m"),
        ],
    )

    # COG
    pdf.column_table(
        "Course Diversity (4 columns)",
        [
            (
                "avg_circ_cog_stddev",
                "Vessel",
                "Maneuvering signal: avg per-vessel circular COG stddev (degrees)",
            ),
            (
                "cross_vessel_circ_cog_stddev",
                "Vessel",
                "Crossing-traffic signal: circular stddev of vessel heading vectors",
            ),
            (
                "cog_vessel_count",
                "Vessel",
                "Vessels with COG data (confidence measure)",
            ),
            ("cog_report_count", "Ping", "Total COG observations"),
        ],
    )

    # Nav status
    pdf.column_table(
        "Navigational Status (4 columns)",
        [
            ("underway_engine_pings", "Ping", "Time in status 0 (primary risk)"),
            (
                "restricted_maneuver_pings",
                "Ping",
                "Time in status 2 or 3 (cannot avoid whales)",
            ),
            (
                "status_report_count",
                "Ping",
                "Total status observations (~65% complete)",
            ),
            ("restricted_vessel_count", "Vessel", "Vessels with any restricted status"),
        ],
    )

    # Day/Night
    pdf.column_table(
        "Day/Night Split (12 columns)",
        [
            ("day_ping_count", "Ping", "Daytime pings (06:00-20:00 local solar)"),
            ("night_ping_count", "Ping", "Nighttime pings (20:00-06:00 local solar)"),
            ("day_unique_vessels", "Vessel", "Vessels active during day"),
            ("night_unique_vessels", "Vessel", "Vessels active at night"),
            ("vw_day_avg_speed_knots", "Vessel", "Debiased daytime avg speed"),
            ("vw_night_avg_speed_knots", "Vessel", "Debiased nighttime avg speed"),
            ("day_high_speed_pings", "Ping", "Daytime pings > 10 kn"),
            ("night_high_speed_pings", "Ping", "Nighttime pings > 10 kn"),
            ("day_high_speed_vessel_count", "Vessel", "Vessels > 10 kn during day"),
            ("night_high_speed_vessel_count", "Vessel", "Vessels > 10 kn at night"),
        ],
    )

    # Vessel types
    pdf.column_table(
        "Vessel Type - Debiased (7 columns)",
        [
            ("fishing_vessels", "Vessel", "Type 30, 1001, 1002"),
            ("tug_vessels", "Vessel", "Type 31, 32, 52, 1023, 1025"),
            ("passenger_vessels", "Vessel", "Type 60-69, 1012-1015"),
            ("cargo_vessels", "Vessel", "Type 70-79, 1003, 1004, 1016"),
            ("tanker_vessels", "Vessel", "Type 80-89, 1017, 1024"),
            ("pleasure_vessels", "Vessel", "Type 36, 37, 1019"),
            ("military_vessels", "Vessel", "Type 35, 1021"),
        ],
    )

    pdf.column_table(
        "Vessel Type - Exposure (7 columns)",
        [
            ("fishing_pings", "Ping", "Time-in-cell for fishing vessels"),
            ("tug_pings", "Ping", "Time-in-cell for tugs/towing"),
            ("passenger_pings", "Ping", "Time-in-cell for passenger vessels"),
            ("cargo_pings", "Ping", "Time-in-cell for cargo vessels"),
            ("tanker_pings", "Ping", "Time-in-cell for tankers"),
            ("pleasure_pings", "Ping", "Time-in-cell for pleasure craft"),
            ("military_pings", "Ping", "Time-in-cell for military vessels"),
        ],
    )

    # ── DESIGN DECISIONS ────────────────────────────
    pdf.add_page()
    pdf.section_title("7. Design Decisions")

    decisions = [
        (
            "SOG > 0 filter",
            "Stationary vessels (65.7% of all pings) are excluded. A moored "
            "ship cannot collide with a whale. This dramatically reduces data "
            "volume and focuses the features on actual collision-risk traffic.",
        ),
        (
            "NULLIF(length/width/draft, 0)",
            "AIS uses 0 as a sentinel for 'not reported'. Without this, "
            "averages and percentiles would include fake zeros, dragging "
            "values down. count() would overstate reporting completeness.",
        ),
        (
            "Two-pass vessel debiasing",
            "Class A transponders broadcast 2-10x per second; Class B every "
            "30 seconds. Without debiasing, a single slow cargo ship could "
            "generate 15x more pings than nearby pleasure craft, dominating "
            "every average. Pass 1 gives each vessel one row; Pass 2 gives "
            "each vessel one vote.",
        ),
        (
            "10-knot lethal speed threshold",
            "NOAA research shows that vessel strikes above 10 knots are "
            "significantly more likely to be lethal to large whales. This is "
            "the basis for Seasonal Management Areas (SMAs) and Dynamic "
            "Management Areas (DMAs). We count pings and vessels above this.",
        ),
        (
            "Circular statistics for COG",
            "Standard stddev fails at the 360/0 degree boundary: vessels "
            "heading 355 and 005 degrees appear 350 apart instead of 10. "
            "We use Yamartino method (sin/cos decomposition) for proper "
            "circular standard deviation.",
        ),
        (
            "Dual COG measures (maneuvering + crossing)",
            "avg_circ_cog_stddev measures per-vessel heading variability "
            "(maneuvering signal - port approaches, channels). "
            "cross_vessel_circ_cog_stddev measures heading diversity across "
            "vessels (crossing-traffic signal - intersections, TSS crossings). "
            "Both are collision-relevant but for different reasons.",
        ),
        (
            "Local solar time for day/night",
            "UTC-based hours would misclassify: midnight UTC is 7pm ET. "
            "We approximate local solar time from longitude: "
            "local_hour = (UTC_hour + lon/15) mod 24. Accurate to ~30min, "
            "more than sufficient for monthly aggregation.",
        ),
        (
            "max() for static vessel attributes",
            "Length, width, draft, and vessel_type do not change between pings "
            "for the same MMSI. max() picks the highest non-null value, which "
            "handles the rare case of inconsistent reporting across pings.",
        ),
        (
            "Percentile_cont(0.5) for vessel speed",
            "Each vessel's speed is summarised as its median (50th percentile) "
            "rather than mean. This is robust to outlier pings caused by GPS "
            "glitches or transient speed changes.",
        ),
        (
            "Report counts alongside every sparse metric",
            "AIS field completeness varies: heading ~48%, draft ~58%, status "
            "~65%, width ~97%. Every metric from a sparse field includes a "
            "count column so downstream consumers can filter unreliable cells.",
        ),
    ]

    for i, (title, desc) in enumerate(decisions, 1):
        pdf.decision_card(i, title, desc)

    # ── VESSEL TYPE CODES ───────────────────────────
    pdf.add_page()
    pdf.section_title("8. Vessel Type Code Reference")

    pdf.body_text(
        "Vessel type codes combine standard AIS codes (ITU-R M.1371) with "
        "MarineCadastre extended codes (1001+). The extended codes provide "
        "finer-grained classification than the AIS standard allows."
    )

    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.set_font("Helvetica", "B", 9)
    vt_w = [40, 50, 100]
    for w, h in zip(vt_w, ["Category", "AIS Standard", "MarineCadastre Extended"]):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*ReportPDF.DARK_TEXT)
    vtype_rows = [
        ("Fishing", "30", "1001, 1002"),
        ("Tug/Tow", "31, 32, 52", "1023, 1025"),
        ("Military", "35", "1021"),
        ("Pleasure", "36, 37", "1019"),
        ("Passenger", "60-69", "1012-1015"),
        ("Cargo", "70-79", "1003, 1004, 1016"),
        ("Tanker", "80-89", "1017, 1024"),
    ]
    for i, row in enumerate(vtype_rows):
        fill = i % 2 == 0
        if fill:
            pdf.set_fill_color(*ReportPDF.LIGHT_BG)
        for w, val in zip(vt_w, row):
            pdf.cell(w, 7, val, border=1, fill=fill, align="C")
        pdf.ln()

    pdf.ln(4)
    pdf.body_text(
        "Source: NOAA Office of Coast Survey, 2018 AIS Vessel Type reference. "
        "MarineCadastre codes (1001+) are assigned during post-processing of "
        "AIS data and provide more specific vessel classifications than the "
        "standard AIS type field."
    )

    # ── DOWNSTREAM USAGE ────────────────────────────
    pdf.ln(2)
    pdf.section_title("9. Downstream Usage")

    pdf.body_text(
        "The output parquet file (data/processed/ais_h3_res7.parquet) feeds "
        "two downstream systems:"
    )

    pdf.callout_box(
        "PostGIS via dbt",
        "The aggregated data is loaded into PostGIS and joined with cetacean "
        "sightings and MPA boundaries using H3 spatial indexing. dbt "
        "intermediate models (int_vessel_traffic, int_cetacean_density, "
        "int_mpa_coverage) perform these joins. Mart models compute final "
        "risk scores per cell.",
        ReportPDF.ACCENT_BLUE,
    )

    pdf.callout_box(
        "Risk Model",
        "The 66 feature columns serve as input features for the collision "
        "risk model. Vessel-weighted columns provide fair type/size "
        "distributions. Ping-weighted columns quantify temporal exposure. "
        "Day/night splits capture visibility-dependent risk. Large-vessel "
        "thresholds (>100m, >20m, >8m) provide direct lethality indicators.",
        ReportPDF.ACCENT_GREEN,
    )

    # ── RUNNING THE SCRIPT ──────────────────────────
    pdf.add_page()
    pdf.section_title("10. Running the Pipeline")

    pdf.body_text(
        "The aggregation script is a standalone Python module that can be run "
        "from the project root. It supports three execution modes via CLI flags:"
    )

    # CLI table
    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.set_font("Helvetica", "B", 8)
    cli_w = [90, 100]
    for w, h in zip(cli_w, ["Command", "Description"]):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*ReportPDF.DARK_TEXT)
    cli_rows = [
        (
            "uv run python -m pipeline.aggregation.aggregate_ais",
            "Run aggregation only, write parquet",
        ),
        ("... --load-postgis", "Aggregate + load into PostGIS"),
        ("... --postgis-only", "Skip aggregation, load existing parquet"),
    ]
    for i, (cmd, desc) in enumerate(cli_rows):
        fill = i % 2 == 0
        if fill:
            pdf.set_fill_color(*ReportPDF.LIGHT_BG)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.cell(cli_w[0], 7, cmd, border=1, fill=fill)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(cli_w[1], 7, desc, border=1, fill=fill)
        pdf.ln()

    pdf.ln(4)

    pdf.subsection_title("Execution Flow")
    pdf.body_text(
        "1. DuckDB opens an in-memory connection and loads spatial + H3 extensions.\n"
        "2. The two-pass SQL query streams through all 365 parquet files.\n"
        "3. COPY ... TO writes results directly to ZSTD-compressed parquet.\n"
        "4. Row count and file size are logged for verification.\n"
        "5. If --load-postgis: reads the parquet, creates ais_h3_summary table, "
        "bulk-inserts in 10K batches, and creates three indexes."
    )

    pdf.subsection_title("PostGIS Table: ais_h3_summary")
    pdf.body_text(
        "The PostGIS table mirrors the full 66-column parquet schema with "
        "appropriate PostgreSQL types (BIGINT for ping counts, DOUBLE PRECISION "
        "for averages, INTEGER for vessel counts). Primary key is (h3_cell, month). "
        "Three indexes are created: h3_cell (cell lookups), month (temporal queries), "
        "and the composite (h3_cell, month) for dbt joins. The table is fully "
        "dropped and recreated on each load for idempotency."
    )

    pdf.subsection_title("Expected Performance")
    pdf.body_text(
        "The DuckDB aggregation processes ~3.1B rows using columnar streaming. "
        "Expected runtime is 30-90 minutes depending on hardware (CPU cores, "
        "disk speed, available RAM). The output parquet is typically 200-500MB "
        "ZSTD-compressed. PostGIS loading of ~15M rows takes an additional "
        "5-15 minutes via batched inserts."
    )

    # Save
    output_path = "docs/pdfs/modelling/ais_aggregation_design.pdf"
    pdf.output(output_path)
    print(f"Report saved to {output_path}")


if __name__ == "__main__":
    build_report()

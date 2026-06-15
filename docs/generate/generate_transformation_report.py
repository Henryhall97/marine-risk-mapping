"""Generate a styled PDF documenting the data transformation pipeline.

Covers:
  - Python pre-computation scripts (AIS, cetacean, bathymetry, proximity)
  - dbt model architecture (staging, intermediate, marts)
  - Risk scoring methodology and sub-score design
  - Technical challenges and solutions
  - Key packages and technology decisions

Run with:
    uv run python docs/generate_transformation_report.py
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
                "Marine Risk Mapping - Data Transformation & Risk Model",
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
        if y_start > 245:
            self.add_page()
            y_start = self.get_y()

        self.set_font("Helvetica", "", 9)
        line_count = len(text) / 80 + 1
        box_h = max(20, 12 + line_count * 4.5)

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

    def stage_box(self, title, desc):
        """Draw a pipeline stage box with accent bar."""
        y = self.get_y()
        if y > 248:
            self.add_page()

        n_lines = len(desc) // 75 + 2
        box_h = max(18, 10 + n_lines * 4.5)
        self.set_fill_color(*self.LIGHT_BG)
        self.rect(10, self.get_y(), 190, box_h, style="F")
        self.set_fill_color(*self.TEAL)
        self.rect(10, self.get_y(), 3, box_h, style="F")

        y_box = self.get_y()
        self.set_xy(16, y_box + 2)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.NAVY)
        self.cell(180, 5, title)

        self.set_xy(16, y_box + 8)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(178, 4.5, desc)

        self.set_y(y_box + box_h + 3)

    def decision_card(self, number, title, description):
        """Draw a numbered design decision card."""
        card_w = 190
        y_start = self.get_y()
        if y_start > 240:
            self.add_page()
            y_start = self.get_y()

        self.set_font("Helvetica", "", 8.5)
        n_lines = max(2, len(description) // 75 + 1)
        card_h = max(22, 10 + n_lines * 4.5)

        self.set_fill_color(*self.LIGHT_BG)
        self.rect(10, y_start, card_w, card_h, style="F")

        self.set_fill_color(*self.TEAL)
        cx = 20
        cy = y_start + card_h / 2
        self.ellipse(cx - 5, cy - 5, 10, 10, style="F")
        self.set_xy(cx - 5, cy - 3.5)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.WHITE)
        self.cell(10, 7, str(number), align="C")

        self.set_xy(28, y_start + 3)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.NAVY)
        self.cell(168, 6, title)

        self.set_xy(28, y_start + 10)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(168, 4.5, description)

        self.set_y(y_start + card_h + 3)

    def issue_card(self, number, problem, solution, colour):
        """Draw a problem/solution card for the issues section."""
        y_start = self.get_y()
        if y_start > 230:
            self.add_page()
            y_start = self.get_y()

        n_lines = (len(problem) + len(solution)) // 75 + 3
        card_h = max(30, 14 + n_lines * 4.5)

        self.set_fill_color(*self.LIGHT_BG)
        self.rect(10, y_start, 190, card_h, style="F")
        self.set_fill_color(*colour)
        self.rect(10, y_start, 3, card_h, style="F")

        # Number badge
        self.set_fill_color(*colour)
        self.ellipse(17, y_start + 3, 8, 8, style="F")
        self.set_xy(17, y_start + 4)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.WHITE)
        self.cell(8, 6, str(number), align="C")

        # Problem
        self.set_xy(28, y_start + 3)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.ACCENT_RED)
        self.cell(30, 5, "Problem: ")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(150, 4.5, problem)

        # Solution
        y_mid = self.get_y() + 1
        self.set_xy(28, y_mid)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.ACCENT_GREEN)
        self.cell(30, 5, "Solution: ")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(150, 4.5, solution)

        self.set_y(y_start + card_h + 3)

    def simple_table(self, headers, rows, col_widths=None):
        """Draw a styled table."""
        if col_widths is None:
            col_widths = [190 // len(headers)] * len(headers)

        y = self.get_y()
        if y > 245:
            self.add_page()

        # Header row
        self.set_fill_color(*self.NAVY)
        self.set_text_color(*self.WHITE)
        self.set_font("Helvetica", "B", 8)
        for w, h in zip(col_widths, headers, strict=True):
            self.cell(w, 7, h, border=1, fill=True, align="C")
        self.ln()

        # Data rows
        self.set_font("Helvetica", "", 8)
        for i, row in enumerate(rows):
            y = self.get_y()
            if y > 272:
                self.add_page()
                self.set_fill_color(*self.NAVY)
                self.set_text_color(*self.WHITE)
                self.set_font("Helvetica", "B", 8)
                for w, h in zip(col_widths, headers, strict=True):
                    self.cell(w, 7, h, border=1, fill=True, align="C")
                self.ln()
                self.set_font("Helvetica", "", 8)

            fill = i % 2 == 0
            if fill:
                self.set_fill_color(*self.LIGHT_BG)
            self.set_text_color(*self.DARK_TEXT)
            for w, val in zip(col_widths, row, strict=True):
                self.cell(w, 6, val, border=1, fill=fill)
            self.ln()
        self.ln(3)


# ── REPORT CONTENT ──────────────────────────────────────


def build_report():
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ================================================================
    # COVER PAGE
    # ================================================================
    pdf.add_page()
    pdf.ln(40)

    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.rect(0, 30, 210, 70, style="F")

    pdf.set_xy(10, 35)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.cell(
        0,
        14,
        "Data Transformation & Risk Model",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "From Raw Data to Whale-Vessel Collision Risk Scores",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "I", 11)
    pdf.set_text_color(180, 200, 220)
    pdf.cell(
        0,
        10,
        "Marine Risk Mapping Project  |  March 2026",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(30)

    # Stats boxes
    stats = [
        ("1.9M", "H3 Grid Cells"),
        ("9.7M", "Traffic Rows"),
        ("1M", "Whale Sightings"),
        ("7", "Risk Sub-Scores"),
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
            "This document describes how raw data from 16+ sources (AIS vessel "
            "traffic, OBIS cetacean sightings, GEBCO bathymetry, NOAA MPAs, "
            "ship strikes, Nisi reference risk, ocean covariates, speed zones, "
            "and more) is transformed into a unified risk model through Python "
            "pre-computation scripts and a dbt transformation pipeline. It covers "
            "the architecture, the 7-sub-score composite risk methodology, "
            "seasonal and ML-enhanced variants, and technical challenges."
        ),
        align="C",
    )

    # ================================================================
    # 1. OVERVIEW
    # ================================================================
    pdf.add_page()
    pdf.section_title("1. Architecture Overview")

    pdf.body_text(
        "The transformation pipeline converts 16+ heterogeneous data sources "
        "into composite collision risk scores per H3 hexagonal grid cell. The "
        "architecture cleanly separates pre-computation (Python) from "
        "transformation (dbt SQL), with PostGIS as the shared handoff layer. "
        "The pipeline produces 9 mart tables including standard, seasonal, "
        "ML-enhanced, and climate-projected risk variants."
    )

    pdf.subsection_title("Two-layer design")

    pdf.body_text(
        "Layer 1: Python pre-computation scripts handle operations that are "
        "computationally expensive or impossible in SQL. These scripts read "
        "from source tables, perform the heavy lifting (H3 cell assignment, "
        "raster sampling, KDTree nearest-neighbour), and write results back to "
        "PostGIS as source tables."
    )

    pdf.body_text(
        "Layer 2: dbt handles all SQL transformations - cleaning, joining, "
        "aggregating, and scoring. dbt manages the DAG (directed acyclic "
        "graph) of model dependencies, runs tests, and documents every column. "
        "This layer is fully idempotent: dbt run rebuilds all tables "
        "deterministically from sources."
    )

    pdf.callout_box(
        "Key design principle: no circular dependencies",
        "All Python scripts read ONLY from source tables (loaded outside dbt). "
        "dbt models read from sources and other dbt models, never from scripts "
        "mid-execution. This means the Python scripts can run before dbt, and "
        "dbt can run its full DAG in a single pass. This pattern is directly "
        "compatible with Dagster orchestration: Python tasks feed source "
        "tables, then dbt runs downstream.",
        ReportPDF.TEAL,
    )

    # ================================================================
    # 2. PYTHON PRE-COMPUTATION
    # ================================================================
    pdf.add_page()
    pdf.section_title("2. Python Pre-Computation Scripts")

    pdf.body_text(
        "Six core Python scripts handle operations that PostGIS/SQL cannot "
        "perform efficiently. Each reads from source tables, performs its "
        "computation, and writes a new source table to PostGIS."
    )

    # ── 2a. AIS Aggregation ─────────────────────────
    pdf.subsection_title("2a. AIS H3 Aggregation (aggregate_ais.py)")

    pdf.body_text(
        "The largest pre-computation. Compresses 3.1 billion raw AIS pings "
        "into ~9.7 million cell-month feature rows using DuckDB's columnar "
        "execution engine with H3 and spatial extensions."
    )

    pdf.simple_table(
        ["Aspect", "Detail"],
        [
            ("Input", "365 daily parquet files from MarineCadastre (~3.1B pings)"),
            ("Output", "ais_h3_summary table: 9,726,299 rows x 66 columns"),
            ("Engine", "DuckDB with spatial + H3 extensions (in-process, zero setup)"),
            ("Method", "Two-pass: per-vessel summaries, then cell-level agg"),
            ("Key fix", "Ping-rate debiasing via vessel-weighted (vw_) metrics"),
            ("CLI flags", "--test (Jan only), --threads (default 4), --memory (8GB)"),
            ("Runtime", "~17 minutes for full year, 8GB RAM"),
        ],
        col_widths=[40, 150],
    )

    pdf.body_text(
        "The two-pass approach is critical: Class A transponders broadcast up "
        "to 15x more frequently than Class B. Without debiasing, a single "
        "cargo ship would dominate every average in a cell. Pass 1 gives each "
        "vessel one vote; Pass 2 aggregates those votes into 66 features "
        "spanning traffic volume, speed, vessel size, course diversity, "
        "day/night splits, vessel type mix, and navigational status."
    )

    # ── 2b. Cetacean H3 Assignment ──────────────────
    pdf.subsection_title("2b. Cetacean H3 Assignment (assign_cetacean_h3.py)")

    pdf.body_text(
        "Assigns each cetacean sighting to its exact H3 resolution-7 cell "
        "using the Python h3 library. This replaces what would be an extremely "
        "expensive PostGIS spatial join (ST_Contains with 460K points against "
        "1.9M hexagon polygons)."
    )

    pdf.simple_table(
        ["Aspect", "Detail"],
        [
            ("Input", "cetacean_sightings table (OBIS data, 460K rows)"),
            ("Output", "cetacean_sighting_h3 table: sighting_id, h3_cell, lat, lon"),
            ("Method", "h3.latlng_to_cell() - exact hexagonal cell assignment"),
            ("Runtime", "~5 seconds for 460K sightings"),
            ("Key point", "Whale cells extend beyond AIS grid (whale-only areas)"),
        ],
        col_widths=[40, 150],
    )

    pdf.callout_box(
        "Why Python h3 instead of PostGIS?",
        "PostGIS ST_Contains spatial join between 460K points and 1.9M "
        "hexagon polygons was cancelled after 59 minutes with no result. "
        "Even a KNN lateral join approach was rejected because it would snap "
        "whale sightings to the nearest vessel cell, losing whales in areas "
        "with no shipping. Python h3.latlng_to_cell() computes the exact cell "
        "in O(1) per point - the entire assignment runs in under 5 seconds.",
        ReportPDF.ACCENT_GREEN,
    )

    # ── 2c. Bathymetry Sampling ─────────────────────
    pdf.add_page()
    pdf.subsection_title("2c. Bathymetry Sampling (sample_bathymetry.py)")

    pdf.body_text(
        "Samples ocean depth from the GEBCO 2025 GeoTIFF at each H3 cell "
        "centroid and its 6 hexagon vertices (7 points per cell). The "
        "multi-point sampling captures shelf-edge gradients that a single "
        "centroid sample would miss."
    )

    pdf.simple_table(
        ["Aspect", "Detail"],
        [
            ("Input", "GEBCO 2025 GeoTIFF (187MB, 6000x15600px, ~450m resolution)"),
            ("Output", "bathymetry_h3 table: 1,043,639 cells with depth features"),
            ("Method", "rasterio pixel lookup at 7 sample points per cell"),
            ("Features", "depth_m (mean), min_depth_m, max_depth_m, depth_range_m"),
            ("Convention", "GEBCO: negative = ocean, positive = land"),
            ("Edge case", "880K cells outside raster bounds get NULL depth"),
        ],
        col_widths=[40, 150],
    )

    # ── 2d. Proximity Computation ───────────────────
    pdf.subsection_title("2d. Proximity Computation (compute_proximity.py)")

    pdf.body_text(
        "Computes the distance from every grid cell to the nearest cetacean "
        "sighting cell and nearest vessel traffic cell. This captures the "
        "spatial co-location signal that is critical for risk scoring: a whale "
        "cell next to a shipping lane is much higher risk than one in the "
        "open ocean."
    )

    pdf.simple_table(
        ["Aspect", "Detail"],
        [
            ("Input", "ais_h3_summary + cetacean_sighting_h3 (source tables)"),
            ("Output", "cell_proximity: 1.9M cells with 2 distance features"),
            ("Method", "scipy cKDTree nearest-neighbour with haversine correction"),
            ("Projection", "Approx Cartesian (km) for KDTree, haversine output"),
            ("Features", "dist_to_nearest_whale_km, dist_to_nearest_ship_km"),
            ("Runtime", "~10 seconds for 1.9M cells"),
        ],
        col_widths=[40, 150],
    )

    pdf.callout_box(
        "Why scipy KDTree instead of PostGIS ST_DWithin / KNN?",
        "PostGIS KNN (<->) requires a GiST index, but CTEs and intermediate "
        "tables in dbt don't carry indexes during execution. A cross-lateral "
        "join of 1.9M grid cells x 76K whale cells would scan billions of "
        "pairs. scipy cKDTree performs the same operation in O(n log m) with "
        "sub-second query time after a one-time tree build.",
        ReportPDF.ACCENT_GREEN,
    )

    # ================================================================
    # 3. DBT MODEL ARCHITECTURE
    # ================================================================
    pdf.add_page()
    pdf.section_title("3. dbt Model Architecture")

    pdf.body_text(
        "The dbt project follows the standard three-layer convention: staging "
        "(clean raw data), intermediate (domain-specific joins and "
        "enrichment), and marts (final business-facing tables). All models "
        "are materialized as views (staging) or tables (intermediate, marts) "
        "in PostGIS. The project currently contains 6 staging views, 16 "
        "intermediate tables, 9 mart tables, and 1 seed."
    )

    pdf.subsection_title("Model DAG")

    pdf.body_text(
        "The transformation flows from 16+ source tables through 6 staging "
        "views, 16 intermediate tables, and 9 mart tables:"
    )

    # Source tables
    pdf.simple_table(
        ["Source Table", "Loader", "Rows", "Description"],
        [
            (
                "ais_h3_summary",
                "aggregate_ais.py",
                "9.7M",
                "Vessel traffic per cell/month (66 cols)",
            ),
            (
                "cetacean_sightings",
                "load_data.py",
                "~1M",
                "Raw OBIS whale sighting records",
            ),
            (
                "cetacean_sighting_h3",
                "assign_cetacean_h3.py",
                "120K",
                "Sighting-to-H3 cell mapping",
            ),
            ("ship_strikes", "load_data.py", "261", "NOAA ship strike incidents"),
            (
                "ship_strike_h3",
                "assign_strike_h3.py",
                "67",
                "Strike-to-H3 cell mapping",
            ),
            ("marine_protected_areas", "load_data.py", "926", "NOAA MPA polygons"),
            ("right_whale_speed_zones", "load_data.py", "5", "Proposed speed zones"),
            (
                "seasonal_management_areas",
                "load_data.py",
                "10",
                "Active SMAs (50 CFR 224.105)",
            ),
            ("nisi_risk_grid", "load_data.py", "47K", "Nisi et al. 2024 global risk"),
            ("ocean_covariates", "load_data.py", "437K", "Copernicus SST/MLD/SLA/PP"),
            (
                "bathymetry_h3",
                "sample_bathymetry.py",
                "1.9M",
                "GEBCO depth (7-point avg)",
            ),
            (
                "cell_proximity",
                "compute_proximity.py",
                "2.0M",
                "4 nearest-neighbour distances",
            ),
            (
                "ml_whale_predictions",
                "load_data.py",
                "7.3M",
                "ISDM scored grid (4 species)",
            ),
            (
                "ml_sdm_predictions",
                "load_sdm.py",
                "7.3M",
                "SDM OOF predictions (7 species)",
            ),
        ],
        col_widths=[46, 38, 16, 90],
    )

    # Staging models
    pdf.subsection_title("Staging Layer (6 views)")

    pdf.simple_table(
        ["Model", "Source", "Purpose"],
        [
            (
                "stg_cetacean_sightings",
                "cetacean_sightings",
                "nullif NaN strings, species backfill",
            ),
            (
                "stg_ship_strikes",
                "ship_strikes + crosswalk",
                "Join species_crosswalk seed",
            ),
            (
                "stg_marine_protected_areas",
                "marine_protected_areas",
                "ST_MakeValid, filter marine areas",
            ),
            ("stg_speed_zones", "speed_zones + SMAs", "UNION proposed + active zones"),
            (
                "stg_ocean_covariates",
                "ocean_covariates",
                "Seasonal ocean data cleaning",
            ),
            ("stg_nisi_risk_grid", "nisi_risk_grid", "US bbox filter, column rename"),
        ],
        col_widths=[55, 50, 85],
    )

    # Intermediate models
    pdf.add_page()
    pdf.subsection_title("Intermediate Layer (16 tables)")

    pdf.body_text(
        "10 static intermediates (joined at h3_cell grain), 4 seasonal "
        "intermediates (h3_cell x season grain), and 2 ML intermediates "
        "(h3_cell x season grain)."
    )

    pdf.simple_table(
        ["Model", "Rows", "Grain", "Purpose"],
        [
            (
                "int_hex_grid",
                "1.9M",
                "h3_cell",
                "Spatial spine: UNION of AIS + cetacean + strike",
            ),
            (
                "int_vessel_traffic",
                "9.7M",
                "cell x month",
                "~75 traffic features from AIS",
            ),
            (
                "int_cetacean_density",
                "76K",
                "h3_cell",
                "Sighting counts: total, baleen, recent",
            ),
            (
                "int_ship_strike_density",
                "67",
                "h3_cell",
                "Strike counts: total, fatal, baleen",
            ),
            ("int_bathymetry", "1M", "h3_cell", "Depth + shelf/edge/depth_zone flags"),
            (
                "int_proximity",
                "1.9M",
                "h3_cell",
                "4 distances + 4 exponential decay scores",
            ),
            (
                "int_mpa_coverage",
                "21K",
                "h3_cell",
                "MPA overlap, protection level, no-take",
            ),
            (
                "int_speed_zone_coverage",
                "30K",
                "h3_cell",
                "Speed zone flags (proposed + active)",
            ),
            ("int_ocean_covariates", "1.1M", "h3_cell", "Annual mean SST/MLD/SLA/PP"),
            (
                "int_nisi_reference_risk",
                "1.1M",
                "h3_cell",
                "Nisi et al. risk grid joined to H3",
            ),
            (
                "int_vessel_traffic_seasonal",
                "4.9M",
                "cell x season",
                "Monthly AIS aggregated to seasons",
            ),
            (
                "int_cetacean_density_seasonal",
                "104K",
                "cell x season",
                "Seasonal sighting density",
            ),
            (
                "int_speed_zone_seasonal",
                "87K",
                "cell x season",
                "Active zones per season",
            ),
            (
                "int_ocean_covariates_seasonal",
                "4.4M",
                "cell x season",
                "Seasonal SST/MLD/SLA/PP",
            ),
            (
                "int_ml_whale_predictions",
                "7.3M",
                "cell x season",
                "ISDM whale probabilities (4 spp)",
            ),
            (
                "int_sdm_whale_predictions",
                "7.3M",
                "cell x season",
                "SDM whale probabilities (7 spp)",
            ),
        ],
        col_widths=[52, 14, 28, 96],
    )

    # Mart models
    pdf.subsection_title("Mart Layer (9 tables)")

    pdf.simple_table(
        ["Model", "Rows", "Grain", "Purpose"],
        [
            (
                "fct_collision_risk",
                "1.8M",
                "h3_cell",
                "Standard 7-sub-score composite risk",
            ),
            (
                "fct_collision_risk_seasonal",
                "7.3M",
                "cell x season",
                "Seasonal variant (4 seasons)",
            ),
            (
                "fct_collision_risk_ml",
                "7.3M",
                "cell x season",
                "ML-enhanced: ISDM+SDM ensemble",
            ),
            (
                "fct_collision_risk_ml_projected",
                "58M",
                "cell x scen x dec",
                "Climate-projected ML risk",
            ),
            ("fct_whale_sdm_training", "1.8M", "h3_cell", "Static SDM feature matrix"),
            (
                "fct_whale_sdm_seasonal",
                "7.3M",
                "cell x season",
                "Seasonal SDM training data",
            ),
            (
                "fct_strike_risk_training",
                "1.8M",
                "h3_cell",
                "Strike probability features",
            ),
            (
                "fct_species_risk",
                "98K",
                "species x cell",
                "Per-species risk aggregation",
            ),
            (
                "fct_monthly_traffic",
                "9.2M",
                "cell x month",
                "Enriched monthly traffic stats",
            ),
        ],
        col_widths=[55, 14, 34, 87],
    )

    # ================================================================
    # 4. RISK SCORING
    # ================================================================
    pdf.add_page()
    pdf.section_title("4. Risk Scoring Methodology")

    pdf.body_text(
        "The collision risk score quantifies danger to whales at each H3 "
        "cell on a 0-1 scale (higher = more dangerous). The standard model "
        "decomposes risk into 7 sub-scores, each capturing a different "
        "dimension. This makes the model interpretable: the API can show "
        "not just 'high risk' but explain WHY (e.g. heavy night traffic near "
        "baleen whale feeding grounds on an unprotected continental shelf)."
    )

    pdf.subsection_title("Composite formula (standard: fct_collision_risk)")

    pdf.callout_box(
        "Risk = 0.25 Traffic + 0.25 Cetacean + 0.15 Proximity + "
        "0.10 Strike + 0.10 Habitat + 0.10 Protection Gap + "
        "0.05 Reference",
        "All sub-scores are on a 0-1 scale via percentile ranking.  "
        "Weights are expert-elicited from the literature (Vanderlaan & "
        "Taggart 2007, Garrison et al. 2025, Rockwood et al. 2021, Nisi "
        "et al. 2024), not data-fitted.  All weight values are defined as "
        "dbt vars in dbt_project.yml and read by macros at build time.",
        ReportPDF.TEAL,
    )

    pdf.simple_table(
        ["Sub-score", "Weight", "Source intermediate"],
        [
            ("Traffic intensity", "25%", "int_vessel_traffic"),
            ("Cetacean presence", "25%", "int_cetacean_density"),
            ("Proximity blend", "15%", "int_proximity"),
            ("Strike history", "10%", "int_ship_strike_density"),
            ("Habitat suitability", "10%", "int_bathymetry + int_ocean_covariates"),
            ("Protection gap", "10%", "int_mpa_coverage + int_speed_zone_coverage"),
            ("Reference risk", "5%", "int_nisi_reference_risk"),
        ],
        col_widths=[42, 18, 130],
    )

    # Sub-score 1: Traffic
    pdf.subsection_title("Sub-score 1: Traffic Intensity (25%)")

    pdf.body_text(
        "Captures vessel activity threat using 8 component features, each "
        "percentile-ranked.  Following the 2026 IWC Product-A rebase, two "
        "components are IWC-aligned: the speed-lethality component now uses "
        "the Garrison et al. (2025) per-stratum logistic, and the exposure "
        "component now uses vessel transit density (VTD, track-km/km^2) "
        "instead of raw vessel counts.  The V&T logistic (Vanderlaan & "
        "Taggart 2007) is retained as a diagnostic surface."
    )

    pdf.simple_table(
        ["Feature", "Weight", "Rationale"],
        [
            (
                "speed_lethality_pctl",
                "20%",
                "Garrison (2025) per-stratum lethality percentile",
            ),
            ("high_speed_fraction_pctl", "10%", "Fraction of vessels exceeding 10 kn"),
            ("vessels_pctl (VTD)", "20%", "Vessel transit density, track-km/km^2"),
            ("large_vessel_pctl", "10%", "Vessels > threshold LOA (high inertia)"),
            ("draft_risk_pctl", "10%", "Mean draft risk score (keel depth hazard)"),
            ("draft_risk_fraction_pctl", "5%", "Fraction of deep-draft vessels"),
            (
                "commercial_pctl",
                "10%",
                "Cargo + tanker count (deep draft, high inertia)",
            ),
            (
                "night_traffic_pctl",
                "15%",
                "Night traffic fraction (zero visual detection)",
            ),
        ],
        col_widths=[50, 18, 122],
    )

    # Sub-score 2: Cetacean
    pdf.subsection_title("Sub-score 2: Cetacean Presence (25%)")

    pdf.body_text(
        "Captures whale presence and vulnerability.  The equal weight with "
        "traffic reflects the core insight: risk requires BOTH ships AND "
        "whales.  A cell with intense traffic but no whales is not a "
        "collision risk."
    )

    pdf.simple_table(
        ["Feature", "Weight", "Rationale"],
        [
            ("total_sightings", "35%", "Overall whale density signal"),
            (
                "baleen_whale_sightings",
                "35%",
                "Baleen whales are most strike-vulnerable",
            ),
            (
                "recent_sightings",
                "30%",
                "Recent data (2019+) reflects current populations",
            ),
        ],
        col_widths=[50, 18, 122],
    )

    # Sub-score 3: Proximity
    pdf.add_page()
    pdf.subsection_title("Sub-score 3: Proximity Blend (15%)")

    pdf.body_text(
        "Captures spatial co-location of whales, ships, strikes, and "
        "protection gaps.  Uses exponential decay with species-specific "
        "half-lives.  The blend combines three proximity signals:"
    )

    pdf.simple_table(
        ["Component", "Weight", "Half-life", "Captures"],
        [
            (
                "Whale x ship geometric mean",
                "45%",
                "10 km",
                "Where whales and ships converge",
            ),
            ("Strike proximity", "30%", "25 km", "Decay from known strike locations"),
            (
                "Protection proximity",
                "25%",
                "50 km",
                "Decay from protection boundaries",
            ),
        ],
        col_widths=[50, 18, 22, 100],
    )

    pdf.callout_box(
        "Geometric mean as the co-location operator",
        "Using sqrt(whale_score x ship_score) ensures BOTH must be high "
        "for proximity to register.  A cell on a shipping lane but far "
        "from whales (1.0 x 0.01 = 0.1) scores low.  Only cells where "
        "ships and whales converge score high.",
        ReportPDF.ACCENT_BLUE,
    )

    # Sub-score 4: Strike history
    pdf.subsection_title("Sub-score 4: Strike History (10%)")

    pdf.body_text(
        "Captures known ship strike incidents.  Only 67 of 261 NOAA "
        "records are geocoded, making this effectively binary for most "
        "cells.  Three components weight total, fatal, and baleen strikes."
    )

    pdf.simple_table(
        ["Feature", "Weight", "Rationale"],
        [
            ("total_strikes_pctl", "40%", "All documented strike incidents"),
            ("fatal_strikes_pctl", "35%", "Lethal strikes (strongest signal)"),
            ("baleen_strikes_pctl", "25%", "Strikes on most vulnerable taxa"),
        ],
        col_widths=[50, 18, 122],
    )

    # Sub-score 5: Habitat
    pdf.subsection_title("Sub-score 5: Habitat Suitability (10%)")

    pdf.body_text(
        "Captures ocean environment favourability.  Split 80% bathymetry, "
        "20% ocean productivity (PP).  Acts as a prior: even without "
        "sighting data, shelf cells with high productivity are more likely "
        "to host whales."
    )

    pdf.simple_table(
        ["Feature", "Weight", "Value"],
        [
            (
                "Bathymetry (inner blend)",
                "80%",
                "shelf 50% + edge 30% + depth_zone 20%",
            ),
            ("Ocean PP (percentile)", "20%", "Primary productivity from Copernicus"),
        ],
        col_widths=[50, 18, 122],
    )

    # Sub-score 6: Protection gap
    pdf.subsection_title("Sub-score 6: Protection Gap (10%)")

    pdf.body_text(
        "Captures the absence of regulatory protection.  Uses an 8-tier "
        "system that accounts for MPA type, SMA presence, and their "
        "combinations.  Higher values = less protection = more risk."
    )

    pdf.simple_table(
        ["Protection Status", "Score", "Rationale"],
        [
            (
                "No-take + SMA overlap",
                "0.10",
                "Strongest: vessel exclusion + speed limit",
            ),
            ("No-take zone only", "0.15", "Strong: minimal vessel access"),
            ("Strict MPA + SMA", "0.25", "Strong regulation + speed limit"),
            ("Strict MPA only", "0.35", "Regulation but no speed limit"),
            ("Any MPA + SMA", "0.50", "Some protection + speed limit"),
            ("Any MPA only", "0.60", "Some protection, often advisory"),
            ("SMA only (voluntary)", "0.80", "Speed advisory, no vessel limits"),
            ("No protection", "1.00", "No regulatory protection at all"),
        ],
        col_widths=[50, 18, 122],
    )

    # Sub-score 7: Reference risk
    pdf.subsection_title("Sub-score 7: Reference Risk (5%)")

    pdf.body_text(
        "Nisi et al. 2024 global ship strike risk grid (1-degree cells, "
        "47K rows) provides an independent external benchmark.  "
        "Percentile-ranked and included at 5% weight as a cross-check "
        "against our bottom-up model."
    )

    # Risk categories
    pdf.subsection_title("Risk categories")

    pdf.simple_table(
        ["Category", "Score Range", "Interpretation"],
        [
            ("Critical", ">= 0.70", "Immediate danger: multiple elevated risk factors"),
            ("High", ">= 0.50", "Significant risk: several risk factors present"),
            ("Medium", ">= 0.35", "Moderate risk: some risk factors present"),
            ("Low", ">= 0.20", "Low risk: minimal overlap of risk factors"),
            ("Minimal", "< 0.20", "Very low risk: little traffic or whale presence"),
        ],
        col_widths=[30, 30, 130],
    )

    # ================================================================
    # 5. SEASONAL & ML VARIANTS
    # ================================================================
    pdf.add_page()
    pdf.section_title("5. Risk Model Variants")

    pdf.body_text(
        "The standard risk model has three variants that extend the "
        "7-sub-score framework to capture temporal patterns, machine "
        "learning predictions, and climate projections."
    )

    pdf.subsection_title("5a. Seasonal variant (fct_collision_risk_seasonal)")

    pdf.body_text(
        "Same 7-sub-score architecture at (h3_cell, season) grain -- "
        "4x the static row count (7.3M rows).  Four inputs vary by season: "
        "traffic intensity, cetacean presence, speed zone coverage, and "
        "ocean covariates (habitat).  Static inputs (bathymetry, proximity, "
        "strike history, Nisi, MPA) are joined without season key."
    )

    pdf.callout_box(
        "Season-relative scoring",
        "percent_rank() uses PARTITION BY season so a cell at the 90th "
        "percentile in summer is scored relative to other summer values. "
        "This prevents summer's higher absolute traffic from dominating "
        "all other seasons.",
        ReportPDF.ACCENT_GREEN,
    )

    pdf.subsection_title("5b. ML-enhanced variant (fct_collision_risk_ml)")

    pdf.body_text(
        "Replaces cetacean + habitat sub-scores with ISDM+SDM ensemble "
        "whale predictions.  Still 7 sub-scores but with different "
        "content and weights:"
    )

    pdf.simple_table(
        ["Sub-score", "Weight", "Source"],
        [
            ("Whale x traffic interaction", "30%", "P(any whale) x traffic_score"),
            ("Traffic intensity", "15%", "Same as standard"),
            ("Whale ML exposure", "15%", "ISDM+SDM ensemble probabilities"),
            ("Proximity blend", "15%", "Same as standard"),
            ("Strike history", "10%", "Same as standard"),
            ("Protection gap", "10%", "Same as standard"),
            ("Reference risk", "5%", "Same as standard"),
        ],
        col_widths=[52, 18, 120],
    )

    pdf.body_text(
        "No habitat sub-score in the ML variant: both ISDM and SDM models "
        "were trained on environmental covariates (SST, MLD, SLA, PP, depth), "
        "so habitat is already encoded in P(whale).  This avoids "
        "double-counting."
    )

    pdf.subsection_title(
        "5c. Climate-projected variant (fct_collision_risk_ml_projected)"
    )

    pdf.body_text(
        "Projects ML-enhanced risk under CMIP6 SSP2-4.5 and SSP5-8.5 "
        "scenarios for 4 future decades (2030s-2080s).  Uses only 6 "
        "sub-scores -- proximity is dropped because observed sighting/"
        "strike locations don't exist for future decades.  Weights are "
        "renormalised by dividing by (1 - 0.15) = 0.85."
    )

    pdf.simple_table(
        ["Sub-score", "Projected wt", "Formula"],
        [
            ("Whale x traffic interaction", "35.29%", "0.30 / 0.85"),
            ("Traffic intensity", "17.65%", "0.15 / 0.85"),
            ("Whale ML exposure", "17.65%", "0.15 / 0.85"),
            ("Strike history", "11.76%", "0.10 / 0.85"),
            ("Protection gap", "11.76%", "0.10 / 0.85"),
            ("Reference risk", "5.88%", "0.05 / 0.85"),
        ],
        col_widths=[52, 28, 110],
    )

    pdf.body_text(
        "Grain: (h3_cell, season, scenario, decade) = ~58M rows.  "
        "Traffic, strikes, protection, and reference risk are held "
        "constant -- only whale habitat varies with climate."
    )

    # ================================================================
    # 6. TECHNICAL CHALLENGES
    # ================================================================
    pdf.add_page()
    pdf.section_title("6. Technical Challenges & Solutions")

    pdf.body_text(
        "Building the pipeline surfaced several non-obvious technical issues. "
        "This section documents each problem and its solution, useful both as "
        "a reference and as interview talking points."
    )

    issues = [
        (
            "ln(0) in Yamartino circular statistics",
            "The Yamartino method for circular standard deviation of vessel "
            "course-over-ground computes ln(R) where R is the resultant "
            "length. When all pings have identical heading (common for vessels "
            "in a straight shipping lane), R = 1.0 and the argument to "
            "sqrt(ln(R)) becomes exactly zero - but floating-point rounding "
            "can produce R slightly > 1.0, making ln(R) positive and "
            "sqrt(-negative) = NaN.",
            "Clamped R to greatest(epsilon, 1 - R) with epsilon = 1e-10. "
            "This floors the angular spread at ~0 degrees rather than "
            "producing NaN, which is physically correct (zero spread means "
            "all vessels heading the same direction).",
        ),
        (
            "numpy types not adaptable by psycopg2",
            "When loading data from Python (numpy arrays) to PostGIS via "
            "psycopg2, numpy.int32 and numpy.float64 types are not "
            "recognized by psycopg2's type adaptation system. The INSERT "
            "fails with 'can't adapt type numpy.int32'.",
            "Convert all numpy scalars to native Python types before "
            "insertion using .item() for integers and float() for floats. "
            "Applied in both the AIS loading and bathymetry sampling scripts. "
            "Lesson: always convert numpy types at the boundary between "
            "numpy and database code.",
        ),
        (
            "Cetacean spatial join: 59 minutes and counting",
            "The initial approach used PostGIS ST_Intersects to join 460K "
            "cetacean sightings against H3 hexagon polygons. This required "
            "either generating hex polygons in SQL (expensive) or a "
            "point-in-polygon join against 1.9M cells. After 59 minutes "
            "with no result, the query was cancelled.",
            "Replaced with Python h3.latlng_to_cell() - an O(1) function "
            "that directly computes the containing H3 cell for any lat/lon. "
            "460K sightings processed in ~5 seconds. The KNN lateral join "
            "alternative was rejected because it would snap whale sightings "
            "to the nearest vessel cell, losing sightings in whale-only areas.",
        ),
        (
            "dbt post-hook {{ this }} rendered empty",
            "Index creation using dbt's post-hook config with {{ this }} "
            "macro produced empty table names during rendering. The CREATE "
            "INDEX statement referenced a blank table name.",
            "Switched from post-hook to dbt's native indexes config: "
            "config(indexes=[{'columns': ['geom'], 'type': 'gist'}]). "
            "This is cleaner, more portable, and handled natively by "
            "dbt-postgres without macro rendering issues.",
        ),
        (
            "GEBCO land values confused with ocean depth",
            "GEBCO bathymetry uses positive values for land elevation and "
            "negative for ocean depth. The initial is_continental_shelf flag "
            "used depth_m >= -200, which is TRUE for all 98,992 land cells "
            "(e.g. 214m elevation >= -200m). This inflated the shelf count "
            "and would have contaminated the risk model with inland cells.",
            "Added an is_land flag (depth_m >= 0), changed "
            "is_continental_shelf to require depth_m BETWEEN -200 AND 0 "
            "(excluding land), and filtered land cells from both mart "
            "models. The depth_zone classifier correctly separates "
            "land / shelf / slope / abyssal.",
        ),
        (
            "exp() underflow in PostgreSQL proximity scores",
            "The exponential decay function exp(-0.0693 * distance_km) "
            "underflows for very large distances (e.g. 5000km from any "
            "whale). PostgreSQL's exp() cannot represent the result and "
            "throws 'value out of range: underflow'.",
            "Added a CASE guard: when distance > 700km, return 0.0 "
            "directly instead of computing exp(). At 700km the true value "
            "is ~1e-21, which is effectively zero. This is both "
            "mathematically correct and avoids the PostgreSQL limitation.",
        ),
        (
            "Python scripts reading dbt-managed tables",
            "sample_bathymetry.py and compute_proximity.py initially read "
            "from int_hex_grid, a dbt-managed intermediate table. This "
            "created a hidden circular dependency: dbt would rebuild "
            "int_hex_grid, then int_proximity would read stale data from "
            "the Python-written cell_proximity table.",
            "Rewrote both scripts to derive the grid directly from source "
            "tables using UNION of ais_h3_summary and cetacean_sighting_h3. "
            "Now all Python scripts read ONLY from source tables, making "
            "them completely independent of dbt execution order. This is "
            "the correct pattern for Dagster orchestration.",
        ),
    ]

    for i, (_title, problem, solution) in enumerate(issues, 1):
        pdf.issue_card(i, problem, solution, ReportPDF.ACCENT_AMBER)

    # ================================================================
    # 7. KEY PACKAGES
    # ================================================================
    pdf.add_page()
    pdf.section_title("7. Key Packages & Technologies")

    pdf.simple_table(
        ["Package", "Version", "Role"],
        [
            ("DuckDB", "0.10+", "In-process OLAP engine for 3.1B row AIS aggregation"),
            ("duckdb spatial", "-", "ST_X/ST_Y for GeoParquet geometry extraction"),
            ("duckdb h3", "-", "h3_latlng_to_cell() for in-query H3 assignment"),
            ("dbt-postgres", "1.10.0", "SQL transformation framework with DAG/testing"),
            ("dbt-core", "1.11.6", "Model compilation, YAML docs, test runner"),
            ("PostGIS", "3.4+", "Spatial DB: ST_Intersects, ST_MakeValid, GiST"),
            ("psycopg2", "2.9+", "Python-PostgreSQL adapter for bulk loading"),
            ("h3 (Python)", "4.4.2", "Exact H3 cell assignment (hex/int conversion)"),
            ("rasterio", "1.5.0", "GEBCO GeoTIFF reading, pixel coordinate transforms"),
            ("scipy", "1.11+", "cKDTree for O(n log m) nearest-neighbour search"),
            ("numpy", "1.26+", "Array ops for raster sampling and distance calc"),
        ],
        col_widths=[35, 20, 135],
    )

    # ================================================================
    # 7. DATA QUALITY
    # ================================================================
    pdf.section_title("8. Data Quality & Testing")

    pdf.body_text(
        "The dbt project includes comprehensive testing across all three "
        "layers. Tests are defined in YAML schema files alongside model "
        "documentation, running automatically with dbt test."
    )

    pdf.simple_table(
        ["Test Type", "Count", "Examples"],
        [
            ("unique", "8", "h3_cell in every grid/intermediate/mart model"),
            ("not_null", "25+", "All join keys, risk scores, sub-scores"),
            ("accepted_values", "2", "depth_zone, risk_category enums"),
            ("Column docs", "100+", "Every column in every model has a description"),
        ],
        col_widths=[40, 20, 130],
    )

    pdf.callout_box(
        "Documentation as a first-class artifact",
        "Every column in every model has a human-readable description in the "
        "YAML schema files. This serves three purposes: (1) it acts as a "
        "data dictionary for anyone querying the tables, (2) it generates "
        "dbt docs (a browsable website), and (3) it forces the developer "
        "to think about what each column actually means. The YAML files are "
        "often longer than the SQL they document.",
        ReportPDF.ACCENT_BLUE,
    )

    # ================================================================
    # 9. SUMMARY
    # ================================================================
    pdf.add_page()
    pdf.section_title("9. Summary & Key Takeaways")

    takeaways = [
        (
            "Separation of concerns: Python for compute, SQL for transform",
            "Heavy computation (H3 assignment, raster sampling, KDTree "
            "nearest-neighbour) runs in Python where specialized libraries "
            "excel. All joining, aggregation, and business logic runs in "
            "dbt SQL where it is testable, documented, and DAG-managed. "
            "The boundary is PostGIS source tables.",
        ),
        (
            "7-sub-score decomposition enables interpretability",
            "Traffic, cetacean, proximity, strike, habitat, protection gap, "
            "and reference risk each capture a distinct dimension.  The API "
            "can explain WHY a cell is high-risk, not just that it is.  "
            "Expert-elicited weights from the V&T, Rockwood, and Nisi "
            "literature ground the model in peer-reviewed science.",
        ),
        (
            "Three model variants cover different questions",
            "Standard (static, 7 sub-scores), seasonal (h3_cell x season, "
            "season-relative percentiles), ML-enhanced (ISDM+SDM ensemble "
            "replacing cetacean + habitat), and climate-projected (6 sub-scores, "
            "CMIP6 SSP2-4.5/SSP5-8.5, 2030s-2080s).  Each variant is a "
            "separate mart table built from the same intermediate layer.",
        ),
        (
            "Spatial operations at scale need the right tool",
            "PostGIS spatial joins work beautifully for indexed polygons "
            "(MPA overlay: 12 seconds) but fail catastrophically for "
            "point-to-cell matching without indexes (cetacean join: 59+ "
            "minutes). Matching the operation to the tool (Python h3 for "
            "cell assignment, scipy KDTree for proximity) reduced runtimes "
            "from hours to seconds.",
        ),
        (
            "8-tier protection gap reflects regulatory reality",
            "The protection gap sub-score accounts for MPA type, SMA "
            "presence, and their combinations.  Proposed speed zones are "
            "excluded (not real protection).  SMAs are voluntary and "
            "downgraded accordingly.  This nuanced scoring replaced the "
            "earlier binary MPA/no-MPA approach.",
        ),
        (
            "Debiasing matters: vessel-weighted metrics",
            "AIS ping-rate bias (Class A = 15x Class B) would dominate "
            "every naive average. The two-pass aggregation produces both "
            "ping-weighted (exposure) and vessel-weighted (composition) "
            "metrics, giving the risk model both perspectives.",
        ),
        (
            "Dependency hygiene: no circular references",
            "All Python scripts read only from source tables. dbt models "
            "read from sources and other dbt models. This clean DAG "
            "means the full pipeline can be orchestrated as: "
            "(1) Python pre-computation, then (2) dbt run. No mid-pipeline "
            "pauses or manual intervention required.",
        ),
    ]

    for i, (title, desc) in enumerate(takeaways, 1):
        pdf.decision_card(i, title, desc)

    # ── Save ────────────────────────────────────────
    output_path = "docs/pdfs/modelling/transformation_and_risk_model.pdf"
    pdf.output(output_path)
    print(f"Report saved to {output_path}")
    print(f"  Pages: {pdf.page_no()}")


if __name__ == "__main__":
    build_report()

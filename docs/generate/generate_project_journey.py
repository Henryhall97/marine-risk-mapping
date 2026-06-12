"""Generate a comprehensive Project Journey PDF for Whale Watch.

Covers the full development arc: data acquisition, database, dbt transforms,
ML pipeline, Dagster orchestration, FastAPI backend, Next.js frontend, and
community features.

Usage:
    uv run python docs/generate/generate_project_journey.py
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "project_journey.pdf"


# ═══════════════════════════════════════════════════════════════
# ReportPDF — navy / teal theme (matches all project reports)
# ═══════════════════════════════════════════════════════════════


class ReportPDF(FPDF):
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
    ACCENT_PURPLE = (142, 68, 173)
    OCEAN_BLUE = (41, 128, 185)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(
                0,
                10,
                "Whale Watch -- Project Journey & Architecture",
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

    # ── Layout helpers ────────────────────────────────────────

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
        self.set_text_color(*self.DARK_TEXT)
        self.cell(5, 5.5, "-")
        self.multi_cell(0, 5.5, text)
        self.ln(0.5)

    def bold_bullet(self, label, text, indent=15):
        x = self.get_x()
        self.set_x(x + indent - 5)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.DARK_TEXT)
        self.cell(5, 5.5, "-")
        self.set_font("Helvetica", "B", 10)
        self.cell(self.get_string_width(label) + 1, 5.5, label)
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.5, text)
        self.ln(0.5)

    def stat_boxes(self, stats, y_pos=None):
        """Draw a row of stat boxes. stats = [(value, label), ...]."""
        n = len(stats)
        box_w = min(42, (190 - (n - 1) * 4) / n)
        gap = 4
        x_start = 10 + (190 - (box_w * n + gap * (n - 1))) / 2
        y = y_pos if y_pos else self.get_y()

        for i, (value, label) in enumerate(stats):
            x = x_start + i * (box_w + gap)
            self.set_fill_color(*self.LIGHT_BG)
            self.rect(x, y, box_w, 22, style="F")
            self.set_xy(x, y + 3)
            self.set_font("Helvetica", "B", 16)
            self.set_text_color(*self.TEAL)
            self.cell(box_w, 8, str(value), align="C")
            self.set_xy(x, y + 12)
            self.set_font("Helvetica", "", 7.5)
            self.set_text_color(*self.MID_TEXT)
            self.cell(box_w, 6, label, align="C")

        self.set_y(y + 27)

    def phase_banner(self, phase_num, title, colour):
        """Full-width phase header banner."""
        self._check_page_break(18)
        y = self.get_y()
        self.set_fill_color(*colour)
        self.rect(10, y, 190, 14, style="F")

        # Phase number circle
        cx, cy = 22, y + 7
        self.set_fill_color(*self.WHITE)
        self.ellipse(cx - 5, cy - 5, 10, 10, style="F")
        self.set_xy(cx - 5, cy - 3.5)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*colour)
        self.cell(10, 7, str(phase_num), align="C")

        # Title
        self.set_xy(32, y + 2)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*self.WHITE)
        self.cell(160, 10, title)
        self.set_y(y + 18)

    def table(self, headers, rows, col_widths=None):
        """Draw a styled data table."""
        self._check_page_break(10 + len(rows) * 7)
        if col_widths is None:
            col_widths = [190 / len(headers)] * len(headers)

        # Header row
        self.set_fill_color(*self.NAVY)
        self.set_text_color(*self.WHITE)
        self.set_font("Helvetica", "B", 8.5)
        for w, h in zip(col_widths, headers):
            self.cell(w, 8, h, border=1, fill=True, align="C")
        self.ln()

        # Data rows
        self.set_text_color(*self.DARK_TEXT)
        self.set_font("Helvetica", "", 8)
        for idx, row in enumerate(rows):
            fill = idx % 2 == 0
            if fill:
                self.set_fill_color(*self.LIGHT_BG)
            for w, val in zip(col_widths, row):
                self.cell(w, 7, str(val), border=1, fill=fill, align="C")
            self.ln()
        self.ln(3)

    def key_value_card(self, items, colour=None):
        """Draw a coloured card with key-value pairs."""
        colour = colour or self.LIGHT_BG
        self._check_page_break(8 + len(items) * 6)
        y_start = self.get_y()
        card_h = 6 + len(items) * 6
        self.set_fill_color(*colour)
        self.rect(10, y_start, 190, card_h, style="F")

        for i, (key, val) in enumerate(items):
            self.set_xy(14, y_start + 3 + i * 6)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*self.NAVY)
            self.cell(50, 5, key)
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*self.DARK_TEXT)
            self.cell(130, 5, val)

        self.set_y(y_start + card_h + 3)

    def challenge_card(self, title, problem, solution):
        """Styled problem/solution card."""
        self._check_page_break(30)
        y = self.get_y()
        # Background
        self.set_fill_color(*self.LIGHT_BG)
        self.rect(10, y, 190, 28, style="F")
        # Red left accent
        self.set_fill_color(*self.ACCENT_RED)
        self.rect(10, y, 3, 14, style="F")
        # Green left accent (solution)
        self.set_fill_color(*self.ACCENT_GREEN)
        self.rect(10, y + 14, 3, 14, style="F")
        # Title
        self.set_xy(16, y + 1)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.NAVY)
        self.cell(180, 5, title)
        # Problem
        self.set_xy(16, y + 7)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*self.ACCENT_RED)
        self.cell(6, 4, "X")
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(168, 4, problem)
        # Solution
        self.set_xy(16, y + 15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*self.ACCENT_GREEN)
        self.cell(6, 4, ">")
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(168, 4, solution)
        self.set_y(y + 31)

    def _check_page_break(self, height):
        if self.get_y() + height > 275:
            self.add_page()


# ═══════════════════════════════════════════════════════════════
# Build the report
# ═══════════════════════════════════════════════════════════════


def build_report():  # noqa: C901 PLR0915
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── COVER PAGE ────────────────────────────────────────────
    pdf.add_page()
    pdf.ln(30)

    # Navy title block
    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.rect(0, 25, 210, 75, style="F")

    pdf.set_xy(10, 30)
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.cell(
        0,
        16,
        "Whale Watch",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "", 15)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "Marine Risk Mapping Platform",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(180, 200, 220)
    pdf.cell(
        0,
        8,
        "Whale-Vessel Collision Risk — CONUS, Alaska, Hawaii & Caribbean",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(150, 170, 190)
    pdf.cell(
        0,
        10,
        "Project Journey & Architecture  |  March 2026",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(30)

    # Stats row
    pdf.stat_boxes(
        [
            ("3.1B", "AIS Pings"),
            ("1M", "Whale Sightings"),
            ("1.9M", "H3 Cells"),
            ("46", "API Endpoints"),
            ("226", "Tests"),
        ]
    )

    pdf.ln(6)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*ReportPDF.DARK_TEXT)
    pdf.multi_cell(
        0,
        5.5,
        (
            "This document traces the full development arc of Whale Watch "
            "-- from raw data acquisition through PostGIS, dbt transforms, "
            "machine learning, Dagster orchestration, a FastAPI backend, and "
            "a Next.js + deck.gl interactive frontend with community features."
        ),
        align="C",
    )

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5,
        (
            "62,000+ lines of code across Python, SQL, and TypeScript  |  "
            "45 backend modules  |  35 frontend components & pages  |  "
            "30 dbt models + 4 macros  |  16 database migrations"
        ),
        align="C",
    )

    # ── TABLE OF CONTENTS ─────────────────────────────────────
    pdf.add_page()
    pdf.section_title("Table of Contents")
    pdf.ln(2)

    toc = [
        ("1", "Project Overview & Architecture", "3"),
        ("2", "Phase 1-2: Data Acquisition & Ingestion", "5"),
        ("3", "Phase 3: Database & Spatial Infrastructure", "7"),
        ("4", "Phase 4: Data Validation & Quality", "9"),
        ("5", "Phase 5: dbt Transformation Layer", "10"),
        ("6", "Phase 6: Dagster Orchestration", "13"),
        ("7", "Phase 7: Machine Learning Pipeline", "14"),
        ("8", "Phase 8: FastAPI Backend", "18"),
        ("9", "Phase 9: Next.js Frontend & Dashboard", "21"),
        ("10", "Community Features & Auth", "24"),
        ("11", "Challenges & Lessons Learned", "26"),
        ("12", "Technology Stack Summary", "28"),
        ("13", "Codebase Statistics", "30"),
    ]
    for num, title, page in toc:
        pdf.set_font("Helvetica", "B" if num.isdigit() else "", 10)
        pdf.set_text_color(*ReportPDF.NAVY)
        w_num = 12
        pdf.cell(w_num, 7, num + ".")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*ReportPDF.DARK_TEXT)
        title_w = 155
        pdf.cell(title_w, 7, title)
        pdf.set_text_color(*ReportPDF.TEAL)
        pdf.cell(20, 7, page, align="R")
        pdf.ln(7)

    # ══════════════════════════════════════════════════════════
    # SECTION 1: PROJECT OVERVIEW
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("1. Project Overview & Architecture")

    pdf.body_text(
        "Whale Watch is a marine risk mapping platform that combines "
        "AIS vessel traffic data, cetacean sighting records, ship "
        "strike history, bathymetry, ocean covariates, and regulatory "
        "zones to predict whale-vessel collision risk across the study "
        "area (lat 2\u00b0S\u201352\u00b0N, lon 180\u00b0W\u201359\u00b0W)."
    )

    pdf.body_text(
        "The platform ingests data from 8+ public sources, aggregates "
        "it onto a 1.9-million cell H3 hexagonal grid (resolution 7, "
        "~1.22 km edge length), computes a 7-sub-score composite risk "
        "model, and serves the results through an interactive map "
        "dashboard with species classification and community features."
    )

    pdf.subsection_title("System Architecture")
    pdf.body_text(
        "The architecture follows a layered approach with clear separation of concerns:"
    )
    pdf.bold_bullet(
        "Data Layer: ",
        "Python ingestion scripts download from MarineCadastre "
        "(AIS), OBIS (cetaceans), NOAA (MPAs, SMAs, strikes), "
        "Copernicus (ocean covariates), and GEBCO (bathymetry).",
    )
    pdf.bold_bullet(
        "Storage Layer: ",
        "PostGIS 16 + PostGIS 3.4 in Docker for spatial data. "
        "DuckDB for ad-hoc analytics over raw Parquet files.",
    )
    pdf.bold_bullet(
        "Transform Layer: ",
        "dbt (dbt-postgres) with 30 SQL models across staging, "
        "intermediate, and mart layers. 4 custom macros.",
    )
    pdf.bold_bullet(
        "ML Layer: ",
        "XGBoost species distribution models (SDM, ISDM, seasonal), "
        "audio classifier (XGBoost + CNN), photo classifier "
        "(EfficientNet-B4). All with spatial block CV.",
    )
    pdf.bold_bullet(
        "Orchestration: ",
        "Dagster with 72 assets, 6 targeted refresh jobs.",
    )
    pdf.bold_bullet(
        "API Layer: ",
        "FastAPI with 46 endpoints, JWT auth, Pydantic v2, connection pooling.",
    )
    pdf.bold_bullet(
        "Frontend: ",
        "Next.js 15 + React 19 + deck.gl 9 + MapLibre GL. "
        "Dual-resolution map (H3 res-4 heatmap + res-7 hex detail).",
    )

    pdf.subsection_title("Data Flow")
    pdf.body_text(
        "Raw sources -> Python ingestion -> Parquet files -> "
        "PostGIS tables -> dbt staging (views) -> dbt intermediate "
        "(tables) -> dbt marts (tables) -> FastAPI services -> "
        "Next.js frontend. ML models are trained on dbt mart "
        "features and predictions are loaded back into PostGIS "
        "for the ML-enhanced risk mart."
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 2: DATA ACQUISITION
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("2. Phase 1-2: Data Acquisition & Ingestion")

    pdf.body_text(
        "The foundation of the platform is 8 diverse marine "
        "datasets, each requiring custom download and parsing logic."
    )

    pdf.subsection_title("Data Sources")
    pdf.table(
        ["Source", "Records", "Format", "Script"],
        [
            ("AIS Vessel Traffic", "3.1B pings", "Parquet", "download_ais.py"),
            ("OBIS Cetaceans", "~1M sightings", "Parquet", "download_cetaceans.py"),
            ("NOAA Ship Strikes", "261 records", "PDF-parsed", "parse_ship_strikes.py"),
            ("GEBCO Bathymetry", "93.6M pixels", "GeoTIFF", "sample_bathymetry.py"),
            ("Copernicus Ocean", "437K rows", "NetCDF", "download_ocean_cov.py"),
            ("NOAA MPAs", "926 polygons", "GeoParquet", "download_mpa.py"),
            ("NARW SMAs", "10 zones", "GeoJSON", "download_sma.py"),
            ("Nisi Risk Grid", "47K cells", "CSV", "download_nisi_2024.py"),
        ],
        [42, 30, 28, 90],
    )

    pdf.subsection_title("AIS Data Pipeline")
    pdf.body_text(
        "The largest dataset: 3.1 billion AIS position reports from "
        "MarineCadastre for 2024 (365 daily CSV files, ~80 GB as "
        "Parquet). Rather than loading all rows into PostGIS, we "
        "aggregate to H3 cells in Python using DuckDB, producing "
        "9.7M monthly traffic summary rows with ~75 metrics per cell "
        "including vessel counts, speed distributions, V&T lethality "
        "scores, draft risk, and night traffic ratios."
    )

    pdf.subsection_title("Aggregation Pipeline")
    pdf.body_text(
        "Six Python aggregation scripts transform raw data into the "
        "H3 grid representation:"
    )
    pdf.bold_bullet(
        "aggregate_ais.py: ",
        "3.1B pings -> 9.7M monthly H3 rows (V&T lethality, "
        "draft risk, night traffic, vessel type mix).",
    )
    pdf.bold_bullet(
        "assign_cetacean_h3.py: ",
        "~1M sightings -> 120K H3 assignments.",
    )
    pdf.bold_bullet(
        "assign_ship_strike_h3.py: ",
        "67 geocoded strikes -> H3 cells.",
    )
    pdf.bold_bullet(
        "sample_bathymetry.py: ",
        "GEBCO raster sampled at H3 centroids + vertices -> 1.9M depth/slope records.",
    )
    pdf.bold_bullet(
        "compute_proximity.py: ",
        "scipy KDTree nearest-neighbour for 4 distance features "
        "(whale sightings, ship strikes, MPAs, speed zones) with "
        "exponential decay scoring.",
    )
    pdf.bold_bullet(
        "aggregate_macro_grid.py: ",
        "H3 res-7 -> res-4 pre-aggregation for coast-wide overview "
        "(70,880 rows = 14,176 cells x 5 seasons).",
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 3: DATABASE
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("3. Phase 3: Database & Spatial Infrastructure")

    pdf.subsection_title("PostGIS Configuration")
    pdf.key_value_card(
        [
            ("Engine", "PostgreSQL 16 + PostGIS 3.4"),
            ("Container", "postgis/postgis:16-3.4 (Docker)"),
            ("Port", "5433 (avoids conflict with local PostgreSQL)"),
            ("Database", "marine_risk (user: marine)"),
            ("H3 Resolution", "7 (~1.22 km edge, BIGINT type)"),
            ("Coordinate System", "WGS-84 (SRID 4326)"),
            ("Tuning", "max_parallel_workers_per_gather=0, work_mem=128MB"),
        ]
    )

    pdf.subsection_title("Schema Design")
    pdf.body_text(
        "The schema separates raw loaded tables (managed by Python "
        "load scripts) from dbt-managed transformation outputs. "
        "All spatial joins use h3_cell (BIGINT) as the universal "
        "join key. Geometry columns are named 'geom' consistently."
    )

    pdf.table(
        ["Table", "Rows", "Key Columns"],
        [
            ("ais_h3_summary", "9.7M", "h3_cell, year_month, 75 metrics"),
            ("cetacean_sightings", "~1M", "id, species, lat, lon, event_date"),
            ("cetacean_sighting_h3", "120K", "sighting_id (FK), h3_cell"),
            ("ship_strikes", "261", "id, species, lat, lon, vessel_speed"),
            ("ship_strike_h3", "67", "strike_id (FK), h3_cell"),
            ("bathymetry_h3", "1.9M", "h3_cell, depth_m, depth_range_m"),
            ("ocean_covariates", "437K", "h3_cell, season, sst, mld, sla, pp"),
            ("marine_protected_areas", "926", "id, name, geom (polygon)"),
            ("cell_proximity", "2.0M", "h3_cell, 4 distances + 4 decays"),
            ("macro_risk_overview", "70K", "h3_cell_r4, season, agg metrics"),
        ],
        [48, 22, 120],
    )

    pdf.subsection_title("Database Migrations")
    pdf.body_text(
        "16 sequential migrations managed by backend/migrations.py. "
        "These create community tables (users, sighting_submissions, "
        "submission_comments), add indexes, and extend schemas for "
        "auth, verification, and user avatars. All migrations are "
        "idempotent (IF NOT EXISTS / IF EXISTS guards)."
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 4: VALIDATION
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("4. Phase 4: Data Validation & Quality")

    pdf.body_text(
        "Two-boundary validation strategy: Pandera schemas guard data "
        "before it enters PostGIS, dbt tests validate after SQL "
        "transformations. This catches issues whether they originate "
        "in source data or in transformation logic."
    )

    pdf.subsection_title("Pandera Schema Validation")
    pdf.body_text(
        "Python-side validation with typed DataFrame schemas that "
        "enforce column types, ranges, nullability, and custom checks. "
        "lazy=True collects all failures in a single pass for "
        "comprehensive quality reports."
    )

    pdf.subsection_title("Key Quality Findings")
    pdf.bold_bullet(
        "Pandas NaN strings: ",
        "cetacean_sightings.species contains literal 'NaN' strings "
        "(not SQL NULL). Fixed with nullif(column, 'NaN') in staging.",
    )
    pdf.bold_bullet(
        "55 invalid MPA geometries: ",
        "6.5% of MPA polygons have self-intersections. Fixed with "
        "ST_MakeValid() in dbt staging.",
    )
    pdf.bold_bullet(
        "Sentinel values: ",
        "MPA Estab_Yr=0 for 'unknown' (not NULL). Fixed with NULLIF(estab_yr, 0).",
    )
    pdf.bold_bullet(
        "Ship strike species: ",
        "Lowercase short names ('right', 'finback') not full names. "
        "species_crosswalk seed bridges 3 naming systems.",
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 5: DBT TRANSFORMS
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("5. Phase 5: dbt Transformation Layer")

    pdf.body_text(
        "30 SQL models in a staging -> intermediate -> mart layered "
        "architecture. dbt_project.yml is the single source of truth "
        "for ~70 shared variables (weights, thresholds, seasons). "
        "pipeline/config.py reads the same file via yaml.safe_load() "
        "-- no manual sync needed."
    )

    pdf.subsection_title("Layer Architecture")
    pdf.table(
        ["Layer", "Count", "Materialisation", "Purpose"],
        [
            ("Staging", "6", "view", "Light cleaning, renaming, type casting"),
            ("Intermediate", "16", "table", "Feature engineering, spatial joins"),
            ("Marts", "8", "table", "Final analytical outputs"),
            ("Macros", "4", "--", "Reusable SQL logic"),
            ("Seeds", "1", "table", "Species crosswalk (77 rows)"),
        ],
        [35, 18, 38, 99],
    )

    pdf.subsection_title("Staging Models (6 views)")
    pdf.body_text(
        "One model per source table. No cross-source joins (exception: "
        "stg_ship_strikes joins species_crosswalk seed). Handle pandas "
        "'NaN' strings with nullif(). Expose species_raw alongside "
        "cleaned columns."
    )

    pdf.subsection_title("Intermediate Models (16 tables)")
    pdf.body_text(
        "Feature engineering at the H3 cell level. int_hex_grid is "
        "the master grid (UNION of AIS + cetacean + strike cells = "
        "1.9M cells). All other intermediate models join via h3_cell."
    )

    pdf.table(
        ["Model", "Rows", "Key Features"],
        [
            ("int_hex_grid", "1.9M", "Master grid (UNION of all sources)"),
            ("int_vessel_traffic", "9.7M", "8 traffic components per cell-month"),
            ("int_cetacean_density", "76K", "Sighting counts, baleen, recent"),
            ("int_ship_strike_density", "67", "Effectively binary (67 cells)"),
            ("int_bathymetry", "1M", "Depth, slope, shelf/edge classification"),
            ("int_proximity", "1.9M", "4 distances + exponential decay scores"),
            ("int_mpa_coverage", "21K", "MPA intersections with hex grid"),
            ("int_speed_zone_coverage", "30K", "SMA/proposed zone overlaps"),
            ("int_ocean_covariates", "1.1M", "SST, MLD, SLA, PP (annual)"),
            ("int_nisi_reference_risk", "1.1M", "External benchmark risk"),
            ("int_ml_whale_predictions", "7.3M", "ISDM-scored per species"),
            ("int_sdm_whale_predictions", "7.3M", "SDM OOF predictions"),
            ("+ 4 seasonal variants", "--", "Traffic, cetacean, zones, ocean"),
        ],
        [52, 20, 118],
    )

    pdf.subsection_title("Mart Models (8 tables)")
    pdf.body_text(
        "Final analytical outputs joining intermediate models. The "
        "core mart (fct_collision_risk) joins all 10 static "
        "intermediate models into a 7-sub-score composite risk score."
    )

    pdf.table(
        ["Mart", "Rows", "Purpose"],
        [
            ("fct_collision_risk", "1.8M", "7-sub-score composite risk"),
            ("fct_collision_risk_seasonal", "7.3M", "Seasonal variant (x4)"),
            ("fct_collision_risk_ml", "7.3M", "ML-enhanced (ISDM replaces habitat)"),
            ("fct_whale_sdm_training", "1.8M", "Static SDM feature matrix"),
            ("fct_whale_sdm_seasonal", "7.3M", "Seasonal SDM (no traffic bias)"),
            ("fct_strike_risk_training", "1.8M", "Strike risk features"),
            ("fct_species_risk", "98K", "Per-species aggregation"),
            ("fct_monthly_traffic", "9.2M", "Monthly vessel traffic stats"),
        ],
        [58, 22, 110],
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 5 (cont): RISK MODEL
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.subsection_title("Composite Risk Model")
    pdf.body_text(
        "The core risk model computes a weighted composite from 7 "
        "sub-scores. All scores are percentile-ranked (0-1), not "
        "probabilities. Weights are expert-elicited from published "
        "research (Vanderlaan & Taggart 2007, Rockwood 2021, "
        "Nisi 2024)."
    )

    pdf.table(
        ["Sub-Score", "Weight", "Source"],
        [
            (
                "Traffic intensity",
                "25%",
                "8-component: V&T lethality, draft, volume...",
            ),
            ("Cetacean presence", "25%", "Sighting counts, baleen fraction, recency"),
            ("Proximity blend", "15%", "Geometric mean whale x ship, strike, gap"),
            ("Strike history", "10%", "Binary: 67 of 1.8M cells non-zero"),
            ("Habitat suitability", "10%", "Bathymetry 80% + ocean productivity 20%"),
            ("Protection gap", "10%", "Tiered MPA + SMA coverage"),
            ("Reference risk", "5%", "Nisi et al. 2024 global risk grid"),
        ],
        [40, 20, 130],
    )

    pdf.subsection_title("ML-Enhanced Mart")
    pdf.body_text(
        "The ML mart (fct_collision_risk_ml) replaces cetacean + "
        "habitat sub-scores with ISDM-based whale predictions. "
        "Top sub-score: whale x traffic interaction (30%). No "
        "habitat sub-score since ISDM was trained on all 7 "
        "environmental covariates -- avoids double-counting."
    )

    pdf.subsection_title("Seasonal Variant")
    pdf.body_text(
        "Same 7-sub-score architecture at (h3_cell, season) grain. "
        "Four inputs vary by season: traffic, cetacean density, "
        "speed zones, and ocean covariates. Static inputs (bathymetry, "
        "proximity, etc.) join without season key. percent_rank() "
        "uses PARTITION BY season for season-relative scores."
    )

    pdf.subsection_title("Custom dbt Macros")
    pdf.table(
        ["Macro", "Purpose"],
        [
            ("season_from_month.sql", "CASE expression: month integer -> season name"),
            ("sub_scores.sql", "7 sub-score calculation macros"),
            ("weighted_risk_score.sql", "Composite score (standard + ML variants)"),
            ("risk_category.sql", "Score -> category label mapping"),
        ],
        [60, 130],
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 6: ORCHESTRATION
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("6. Phase 6: Dagster Orchestration")

    pdf.body_text(
        "Dagster orchestrates the full pipeline with 72 software-"
        "defined assets across 5 asset groups: ingestion (10), "
        "database (3), aggregation (6), ML (11), and dbt (42 auto-"
        "generated from the dbt manifest)."
    )

    pdf.subsection_title("Asset Groups")
    pdf.table(
        ["Group", "Assets", "Purpose"],
        [
            ("Ingestion", "10", "Raw data downloads (AIS, OBIS, NOAA, etc.)"),
            ("Database", "3", "Schema creation, data loading, migrations"),
            ("Aggregation", "6", "H3 assignment, proximity, macro grid"),
            ("ML", "11", "Feature extraction, SDM, ISDM, audio, photo"),
            ("dbt", "42", "Auto-generated from dbt manifest"),
        ],
        [35, 20, 135],
    )

    pdf.subsection_title("Targeted Refresh Jobs")
    pdf.body_text(
        "5 targeted refresh jobs (+ 1 full pipeline) enable "
        "surgical data updates without reprocessing everything:"
    )
    pdf.bold_bullet(
        "refresh_ais: ",
        "AIS -> H3 aggregation -> downstream dbt models.",
    )
    pdf.bold_bullet(
        "refresh_sightings: ",
        "Cetaceans -> H3 -> proximity -> dbt.",
    )
    pdf.bold_bullet(
        "refresh_covariates: ",
        "Ocean covariates -> DB load -> dbt.",
    )
    pdf.bold_bullet(
        "refresh_zones: ",
        "MPA + SMA + speed zones -> DB -> dbt.",
    )
    pdf.bold_bullet(
        "refresh_all_ingestion: ",
        "All ingestion + full downstream cascade.",
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 7: MACHINE LEARNING
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("7. Phase 7: Machine Learning Pipeline")

    pdf.body_text(
        "12 XGBoost binary classifiers trained with spatial block "
        "cross-validation (H3 res-2, ~158 km blocks, 5 folds). "
        "All experiments logged to MLflow. Feature extraction pulls "
        "from dbt mart tables -> Parquet -> train."
    )

    pdf.subsection_title("Model Families")
    pdf.table(
        ["Family", "Script", "Key Config"],
        [
            ("Static Whale SDM", "train_sdm_model.py", "47 features, 1.8M rows"),
            ("Seasonal SDM", "train_sdm_seasonal.py", "7.3M rows, per-species targets"),
            (
                "ISDM (Nisi data)",
                "train_isdm_model.py",
                "7 env covariates, grid scoring",
            ),
            ("Strike Risk", "train_strike_model.py", "67/1.8M imbalance (parked)"),
            ("Audio Classifier", "train_audio_classifier.py", "XGBoost + CNN backends"),
            ("Photo Classifier", "train_photo_classifier.py", "EfficientNet-B4"),
        ],
        [38, 52, 100],
    )

    pdf.subsection_title("Spatial Block Cross-Validation")
    pdf.body_text(
        "evaluate.py implements spatial_cv_split() which assigns "
        "H3 cells to parent cells at resolution 2 and distributes "
        "blocks across 5 folds. For seasonal data, all 4 seasons for "
        "a given cell always land in the same fold (spatial grouping, "
        "not temporal). This prevents spatial leakage between train "
        "and validation sets."
    )

    pdf.subsection_title("Species Distribution Models (SDM)")
    pdf.body_text(
        "Trained on dbt mart features to predict whale presence "
        "per H3 cell. Static SDM uses 47 features across 1.8M cells. "
        "Seasonal SDM uses 7.3M rows with per-species targets "
        "(right whale, humpback, fin, blue, sperm, minke). Both "
        "deliberately exclude traffic features (detection bias: "
        "surveys correlate with shipping lanes) and whale proximity "
        "(target leakage)."
    )

    pdf.subsection_title("ISDM Models")
    pdf.body_text(
        "Integrated Species Distribution Models trained on the "
        "Nisi et al. 2024 global risk grid with 7 environmental "
        "covariates (SST, MLD, SLA, PP, depth, depth_range). "
        "Predictions scored across the full H3 grid and loaded "
        "back into PostGIS for the ML-enhanced risk mart. "
        "any_whale_prob = 1 - product(1 - Pi) treats all 4 species "
        "equally."
    )

    pdf.add_page()
    pdf.subsection_title("Audio Classification Pipeline")
    pdf.body_text(
        "Two-stage system: preprocessing (resample to 16 kHz, "
        "4s windows with 2s hop, 64 acoustic features including "
        "20 MFCCs, spectral shape, temporal envelope) followed by "
        "classification (XGBoost on features or CNN/ResNet18 on "
        "mel spectrograms). 8 target species trained on 452 audio "
        "files from Watkins + Zenodo databases."
    )

    pdf.table(
        ["Model", "Accuracy", "Macro F1", "Key Detail"],
        [
            ("XGBoost", "97.9%", "98.2%", "5-fold stratified CV, 64 features"),
            ("CNN (ResNet18)", "99.3%", "99.4%", "Early stop epoch 5, Apple MPS"),
        ],
        [30, 25, 25, 110],
    )

    pdf.subsection_title("Photo Classification Pipeline")
    pdf.body_text(
        "Single-stage EfficientNet-B4 fine-tuned from ImageNet weights "
        "on Happywhale Kaggle dataset (~20K images, 8 classes). "
        "7 target species + 'other_cetacean' rejection class. "
        "Differential learning rates (1e-4 head, 1e-5 backbone), "
        "label smoothing (0.1), weighted random sampler for class "
        "balance. Input: 380x380 images with training augmentations "
        "(flip, rotation, color jitter, resized crop)."
    )

    pdf.subsection_title("Three-Stage Class Balancing")
    pdf.body_text(
        "Consistent across audio and photo pipelines: (1) segment/ "
        "image cap per species prevents dominant classes from "
        "overwhelming, (2) augmentation for under-represented "
        "species, (3) inverse-frequency class weights in loss "
        "function."
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 8: BACKEND
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("8. Phase 8: FastAPI Backend")

    pdf.body_text(
        "FastAPI REST API with 46 endpoints serving collision risk "
        "data, species distributions, vessel traffic, ML predictions, "
        "photo/audio classification, community sightings, and "
        "regulatory zone geometries."
    )

    pdf.subsection_title("Architecture")
    pdf.key_value_card(
        [
            ("Framework", "FastAPI + Pydantic v2 + uvicorn"),
            ("DB Pool", "psycopg2 ThreadedConnectionPool (4-30 connections)"),
            ("Auth", "JWT tokens + bcrypt password hashing"),
            ("File Upload", "Multipart (photos max 10MB, audio max 100MB)"),
            ("CORS", "localhost:3000 (Next.js) + localhost:5173 (Vite)"),
            ("Migrations", "16 sequential SQL scripts (idempotent)"),
        ]
    )

    pdf.ln(2)
    pdf.subsection_title("Module Organisation")
    pdf.table(
        ["Layer", "Modules", "Purpose"],
        [
            ("api/", "14 route modules", "Thin handlers: validation + response"),
            ("models/", "13 schema modules", "Pydantic v2 request/response schemas"),
            ("services/", "14 service modules", "Business logic + DB queries"),
        ],
        [30, 40, 120],
    )

    pdf.subsection_title("Endpoint Groups (46 total)")
    pdf.table(
        ["Group", "Count", "Key Endpoints"],
        [
            ("Risk & Data", "10", "zones, stats, detail, seasonal, ML risk"),
            ("Spatial Layers", "11", "bathymetry, ocean, whale predictions, MPA..."),
            ("ML Comparison", "5", "ML stats, breakdown, standard vs ML compare"),
            ("Species & Traffic", "5", "List, per-species risk, seasonal, monthly"),
            ("Classification", "2", "Photo + audio multipart upload"),
            ("Sighting Report", "1", "Combined photo + audio + GPS + species"),
            ("Zone Geometries", "3", "Current SMAs, proposed zones, MPAs (GeoJSON)"),
            ("Authentication", "6", "Register, login, profile, reputation"),
            ("Community", "6", "Submissions CRUD, verify, public feed"),
            ("Macro Overview", "2", "Coast-wide res-4 grid + contours"),
        ],
        [35, 18, 137],
    )

    pdf.add_page()
    pdf.subsection_title("Key Backend Patterns")
    pdf.bold_bullet(
        "Bbox validation: ",
        "All spatial endpoints enforce lat_min < lat_max, "
        "lon_min < lon_max, area <= 100 deg sq. Prevents "
        "accidental full-table scans.",
    )
    pdf.bold_bullet(
        "Service layer returns dicts: ",
        "Route handlers construct Pydantic models from dicts. "
        "Keeps services independent of Pydantic and testable "
        "in isolation.",
    )
    pdf.bold_bullet(
        "Lazy-loaded classifiers: ",
        "Photo (EfficientNet-B4) and audio (XGBoost/CNN) models "
        "loaded as singletons on first request. Avoids slow "
        "startup when classifiers aren't needed.",
    )
    pdf.bold_bullet(
        "H3 risk enrichment: ",
        "Both classifiers convert GPS coords to H3 cell and "
        "join fct_collision_risk for spatial risk context "
        "alongside species predictions.",
    )
    pdf.bold_bullet(
        "Media serving: ",
        "Dedicated /api/v1/media/ endpoints for submission "
        "photos, audio files, and user avatars. Files stored "
        "in data/uploads/ (git-ignored).",
    )
    pdf.bold_bullet(
        "Reputation system: ",
        "Event-based scoring with tier progression (newcomer -> "
        "expert). Rewards verified sightings, successful "
        "classifications, and community engagement.",
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 9: FRONTEND
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("9. Phase 9: Next.js Frontend & Dashboard")

    pdf.body_text(
        "Interactive geospatial dashboard built with Next.js 15 "
        "(App Router), React 19, deck.gl 9, and MapLibre GL. "
        "Features a dual-resolution map, 14 switchable data layers, "
        "species classification tools, and a community sighting "
        "platform."
    )

    pdf.subsection_title("Technology Stack")
    pdf.key_value_card(
        [
            ("Framework", "Next.js 15.2 (App Router) + React 19"),
            ("Map Engine", "deck.gl ~9.1.0 + MapLibre GL 4.7"),
            ("Hex Grid", "h3-js 4.2 (H3HexagonLayer)"),
            ("Styling", "Tailwind CSS 3.4"),
            ("Charts", "Recharts"),
            ("Auth", "JWT via AuthContext (token management)"),
            ("Base Map", "CARTO Dark Matter GL style"),
        ]
    )

    pdf.ln(2)
    pdf.subsection_title("Page Routes (9)")
    pdf.table(
        ["Route", "Purpose"],
        [
            ("/", "Landing page: animated stats, feature cards, sub-score breakdown"),
            ("/map", "Main interactive map (heatmap + hex detail + cell inspect)"),
            ("/report", "Sighting report form (photo + audio + GPS + live map)"),
            ("/classify", "Standalone photo/audio classification tools"),
            ("/community", "Public feed of verified sightings"),
            ("/auth", "Login / registration"),
            ("/profile", "User profile + submission history + avatar upload"),
            ("/submissions/[id]", "Submission detail with hero image + comments"),
            ("/users/[id]", "Public user profile + contributions"),
        ],
        [40, 150],
    )

    pdf.subsection_title("Dual-Resolution Map Architecture")
    pdf.body_text("The map uses two rendering strategies depending on zoom:")
    pdf.bold_bullet(
        "Overview (zoomed out): ",
        "HeatmapLayer renders pre-aggregated H3 res-4 macro data "
        "(70,880 rows). Cached per-season. Weight and color range "
        "vary by active layer and selected metric.",
    )
    pdf.bold_bullet(
        "Detail (zoomed in): ",
        "H3HexagonLayer renders individual H3 res-7 cells from "
        "full-detail API endpoints. Fetched on viewport change "
        "with debouncing.",
    )
    pdf.body_text(
        "Zoom threshold is configured per-layer. This approach "
        "avoids loading 1.8M res-7 cells at overview zoom levels "
        "while providing full-fidelity data when inspecting areas."
    )

    pdf.add_page()
    pdf.subsection_title("14 Switchable Layers")
    pdf.table(
        ["Layer", "Source", "Detail"],
        [
            ("Collision Risk", "fct_collision_risk", "7-sub-score composite"),
            ("ML Risk", "fct_collision_risk_ml", "ISDM-enhanced composite"),
            ("Cetacean Density", "int_cetacean_density", "Sighting counts"),
            ("Strike Density", "int_ship_strike_density", "Historical strikes"),
            ("ISDM Predictions", "int_ml_whale_predictions", "ISDM per-species"),
            ("SDM Predictions", "int_sdm_whale_predictions", "OBIS SDM OOF"),
            ("Bathymetry", "int_bathymetry", "Depth + shelf/edge zones"),
            ("Ocean Covariates", "int_ocean_covariates", "SST, MLD, SLA, PP"),
            ("MPA Coverage", "int_mpa_coverage", "Protected area overlaps"),
            ("Speed Zones", "int_speed_zone_coverage", "SMA + proposed zones"),
            ("Proximity", "int_proximity", "4 decay distances"),
            ("Nisi Reference", "int_nisi_reference_risk", "External benchmark"),
            ("Traffic Density", "int_vessel_traffic", "6 sub-metrics"),
            ("Protection Gap", "derived", "MPA + speed zone gap score"),
        ],
        [40, 55, 95],
    )

    pdf.subsection_title("Traffic Density Sub-Metrics")
    pdf.body_text(
        "6 switchable metrics within the traffic layer, each with "
        "distinct colour ramps: vessel_density, speed_lethality, "
        "high_speed, draft_risk, night_traffic, commercial."
    )

    pdf.subsection_title("Components (17)")
    pdf.body_text(
        "MapView (main map + layer rendering), Sidebar (layer/"
        "season/metric controls), Legend (dynamic per-layer), "
        "CellDetail (click-to-inspect panel), Nav (navigation + "
        "auth state), SightingForm (multi-step report wizard), "
        "PhotoClassifier, AudioClassifier, AudioWaveform, "
        "LocationPin (GPS with zoom + region label), SubmissionMap "
        "(live preview), CoverageMap, CommentSection, UserAvatar "
        "(gradient-initials fallback), plus 3 decorative icons."
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 10: COMMUNITY FEATURES
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("10. Community Features & Authentication")

    pdf.subsection_title("Authentication System")
    pdf.body_text(
        "JWT-based auth with bcrypt password hashing. Users register "
        "with email, display name, and password. Tokens issued on "
        "login, verified via Authorization: Bearer header. Frontend "
        "AuthContext manages token storage, user state, and "
        "refreshUser() for profile updates."
    )

    pdf.subsection_title("Sighting Report Flow")
    pdf.body_text(
        "Multi-step form on /report page: (1) Upload photo and/or "
        "audio, (2) Set GPS location via interactive map with "
        "LocationPin, (3) Select species guess and interaction type, "
        "(4) Submit. Backend orchestrates photo + audio classifiers, "
        "risk lookup, and generates an advisory. The submission is "
        "stored with all classification results."
    )

    pdf.subsection_title("Community Feed")
    pdf.body_text(
        "Public feed at /community shows verified sightings with "
        "species badges, confidence indicators, photo/audio media "
        "icons, verification status, and submitter avatars. Cards "
        "link to full submission detail pages."
    )

    pdf.subsection_title("Submission Detail")
    pdf.body_text(
        "Hero image display with interaction-specific guidance. "
        "Species classification results with confidence bars. "
        "Risk summary with 7 sub-scores. Interactive map showing "
        "the sighting location. Comment section for community "
        "discussion. Verification agree/disagree buttons."
    )

    pdf.subsection_title("User Profiles & Avatars")
    pdf.body_text(
        "Full avatar system: upload via profile page, stored in "
        "data/uploads/avatars/{user_id}/, served via media endpoint. "
        "UserAvatar component displays image or falls back to "
        "gradient-initials (6 deterministic colour pairs). Avatars "
        "shown across community cards, comments, submission detail, "
        "and public profiles."
    )

    pdf.subsection_title("Reputation System")
    pdf.body_text(
        "Event-based scoring engine with tier progression "
        "(newcomer -> contributor -> trusted -> expert). Rewards "
        "verified sightings, accurate classifications, community "
        "verification votes, and consistent engagement. Reputation "
        "history visible on user profiles."
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 11: CHALLENGES
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("11. Challenges & Lessons Learned")

    pdf.subsection_title("Data Challenges")
    pdf.challenge_card(
        "3.1B AIS rows won't fit in PostGIS",
        "Initial plan was bulk-load all AIS pings. Each file took ~4 min.",
        "Aggregate to H3 cells in Python/DuckDB first, load only 9.7M summary rows.",
    )
    pdf.challenge_card(
        "Pandas NaN strings pollute SQL",
        "pandas writes literal 'NaN' strings, not SQL NULL. Joins silently fail.",
        "nullif(column, 'NaN') in every staging model. Added to pitfalls list.",
    )
    pdf.challenge_card(
        "Ship strike species naming mismatch",
        "Strike data has 'right', 'finback' -- not 'right whale' or scientific names.",
        "Created species_crosswalk seed (77 rows) bridging 3 naming systems.",
    )

    pdf.subsection_title("Infrastructure Challenges")
    pdf.challenge_card(
        "Docker shared memory OOM",
        "Large window functions with parallel workers exceeded Docker shm.",
        "Set max_parallel_workers_per_gather=0, work_mem=128MB via ALTER SYSTEM.",
    )
    pdf.challenge_card(
        "Apple Silicon + PostGIS Docker",
        "postgis/postgis has no ARM64 builds. platform: linux/arm64 crashed.",
        "Remove platform setting. Docker Desktop uses Rosetta 2 to emulate amd64.",
    )
    pdf.challenge_card(
        "Spatial joins on CTEs are catastrophic",
        "ST_DWithin cross-lateral on 1.9M rows via CTE = hours (no GiST index).",
        "Use Python KDTree for proximity. Join indexed source tables, never CTEs.",
    )

    pdf.add_page()
    pdf.subsection_title("ML Challenges")
    pdf.challenge_card(
        "SHAP + XGBoost 3.x incompatibility",
        "SHAP 0.49.1 crashes with XGBoost >= 3.0 (removed save_raw parameter).",
        "patch_shap_for_xgboost3() utility function in pipeline/utils.py.",
    )
    pdf.challenge_card(
        "49% missing ocean covariates in scoring",
        "When scoring the full grid, ~49% of cells lack Copernicus data.",
        "Fill with median values. Expected for deep ocean/edge cells. Log warning.",
    )
    pdf.challenge_card(
        "Detection bias in whale SDMs",
        "Survey effort correlates with shipping lanes -- traffic features leak.",
        "Exclude all traffic features from SDM training. Exclude whale proximity too.",
    )

    pdf.subsection_title("Frontend Challenges")
    pdf.challenge_card(
        "deck.gl 9 peer dependency conflicts",
        "deck.gl 9.x conflicts with React 19 and luma.gl during npm install.",
        "Committed .npmrc with legacy-peer-deps=true. Documented in instructions.",
    )
    pdf.challenge_card(
        "1.8M hexagons won't render at overview zoom",
        "Rendering all H3 res-7 cells on initial load would be unusably slow.",
        "Dual-resolution: HeatmapLayer (res-4 macro) overview + H3HexagonLayer detail.",
    )
    pdf.challenge_card(
        "Photo form field name mismatch",
        "Frontend sent 'image', backend expected 'file'. Upload silently failed.",
        "Aligned field names. Added explicit error alerts in frontend handlers.",
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 12: TECH STACK
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("12. Technology Stack Summary")

    pdf.subsection_title("Core Platform")
    pdf.table(
        ["Technology", "Version", "Role"],
        [
            ("Python", "3.12", "Core language for pipeline, ML, backend"),
            ("TypeScript", "5.7", "Frontend type-safe development"),
            ("PostgreSQL", "16", "Primary data store"),
            ("PostGIS", "3.4", "Spatial extension for geometry ops"),
            ("Docker", "--", "Container runtime for PostGIS"),
        ],
        [50, 30, 110],
    )

    pdf.subsection_title("Data & Transform")
    pdf.table(
        ["Technology", "Version", "Role"],
        [
            ("dbt-postgres", "1.10.0", "SQL transformation framework"),
            ("DuckDB", "--", "Ad-hoc analytics over Parquet files"),
            ("Pandera", "--", "DataFrame schema validation"),
            ("H3", "Resolution 7", "Hexagonal spatial indexing"),
            ("Apache Parquet", "--", "Columnar storage for all raw data"),
            ("scipy KDTree", "--", "Proximity distance computation"),
        ],
        [50, 30, 110],
    )

    pdf.subsection_title("Machine Learning")
    pdf.table(
        ["Technology", "Version", "Role"],
        [
            ("XGBoost", "3.2.0", "SDM, ISDM, strike, audio classifiers"),
            ("SHAP", "0.49.1", "Feature importance explanations"),
            ("Optuna", "4.7.0", "Hyperparameter optimization"),
            ("MLflow", "3.10.0", "Experiment tracking + model registry"),
            ("PyTorch", "--", "CNN audio + photo classifiers"),
            ("torchvision", "--", "EfficientNet-B4, ResNet18"),
            ("librosa", "0.11.0", "Audio feature extraction"),
        ],
        [50, 30, 110],
    )

    pdf.add_page()
    pdf.subsection_title("Backend")
    pdf.table(
        ["Technology", "Version", "Role"],
        [
            ("FastAPI", "0.115+", "REST API framework"),
            ("Pydantic", "v2", "Request/response validation"),
            ("uvicorn", "--", "ASGI server"),
            ("psycopg2", "--", "PostgreSQL driver + connection pool"),
            ("bcrypt", "--", "Password hashing"),
            ("PyJWT", "--", "JWT token auth"),
        ],
        [50, 30, 110],
    )

    pdf.subsection_title("Frontend")
    pdf.table(
        ["Technology", "Version", "Role"],
        [
            ("Next.js", "15.2", "React framework (App Router)"),
            ("React", "19", "UI component library"),
            ("deck.gl", "~9.1.0", "WebGL geospatial rendering"),
            ("MapLibre GL", "4.7", "Vector tile base map"),
            ("h3-js", "4.2", "H3 hex boundary computation"),
            ("Tailwind CSS", "3.4", "Utility-first styling"),
            ("Recharts", "--", "Data visualization charts"),
        ],
        [50, 30, 110],
    )

    pdf.subsection_title("Orchestration & Tooling")
    pdf.table(
        ["Technology", "Version", "Role"],
        [
            ("Dagster", "1.12.15", "Pipeline orchestration (72 assets)"),
            ("dagster-dbt", "0.28.15", "dbt integration (42 auto-assets)"),
            ("uv", "--", "Python package manager"),
            ("Ruff", "--", "Linter + formatter"),
            ("pytest", "--", "Test framework (226 tests)"),
            ("fpdf2", "--", "PDF report generation"),
        ],
        [50, 30, 110],
    )

    # ══════════════════════════════════════════════════════════
    # SECTION 13: CODEBASE STATS
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("13. Codebase Statistics")

    pdf.stat_boxes(
        [
            ("62K+", "Lines of Code"),
            ("226", "Tests"),
            ("46", "API Endpoints"),
            ("72", "Dagster Assets"),
        ]
    )

    pdf.ln(4)
    pdf.subsection_title("Lines of Code by Area")
    pdf.table(
        ["Area", "Files", "Lines", "Language"],
        [
            ("Transform (dbt)", "~30 SQL + 16 YML", "22,293", "SQL / YAML"),
            ("Pipeline", "49 .py", "16,631", "Python"),
            ("Frontend", "35 .ts/.tsx", "10,059", "TypeScript"),
            ("Backend", "45 .py", "8,334", "Python"),
            ("Tests", "9 .py", "3,774", "Python"),
            ("Orchestration", "9 .py", "1,270", "Python"),
            ("Total", "~193 files", "62,361", "Python / SQL / TS"),
        ],
        [45, 45, 30, 70],
    )

    pdf.subsection_title("Database Scale")
    pdf.table(
        ["Metric", "Value"],
        [
            ("Raw AIS data", "3.1 billion pings (~80 GB Parquet)"),
            ("PostGIS tables", "~15 raw + 30 dbt-managed"),
            ("H3 grid cells", "1.9 million (res-7)"),
            ("Macro grid cells", "14,176 (res-4) x 5 seasons"),
            ("dbt test count", "186 data tests"),
            ("Migrations", "16 sequential (idempotent)"),
        ],
        [50, 140],
    )

    pdf.subsection_title("ML Artefacts")
    pdf.table(
        ["Artefact", "Size / Count"],
        [
            ("ISDM grid predictions", "4 parquet files, ~53 MB each"),
            ("SDM seasonal features", "7.3M rows parquet"),
            ("Audio training data", "452 files, 8 species, 10K segments"),
            ("Photo training data", "~20K images (Happywhale)"),
            ("MLflow experiments", "5 experiment families"),
            ("Generated reports", "10 PDFs in docs/pdfs/"),
        ],
        [55, 135],
    )

    pdf.ln(6)
    pdf.subsection_title("Test Coverage")
    pdf.table(
        ["Test Module", "Tests", "Coverage Area"],
        [
            ("test_backend.py", "96", "FastAPI routes, services, layers, auth"),
            ("test_config.py", "44", "Weights, thresholds, seasons, audio config"),
            ("test_utils.py", "20", "to_python, bulk_insert, DB connection"),
            ("test_audio.py", "19", "Audio preprocessing + feature extraction"),
            ("test_validation.py", "17", "Pandera schemas + quality reports"),
            ("test_analysis.py", "16", "Binary metrics, spatial CV, plots"),
            ("test_aggregation.py", "14", "Haversine, H3, proximity decay"),
            ("Total", "226", "Pipeline + backend + ML"),
        ],
        [42, 18, 130],
    )

    # ── CLOSING ───────────────────────────────────────────────
    pdf.add_page()
    pdf.ln(20)
    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.rect(0, 40, 210, 55, style="F")

    pdf.set_xy(10, 48)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.cell(
        0,
        12,
        "Thank You",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        8,
        "Whale Watch - Marine Risk Mapping Platform",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(180, 200, 220)
    pdf.cell(
        0,
        10,
        "Protecting whales through data-driven collision risk assessment",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(25)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5.5,
        (
            "This platform demonstrates end-to-end data engineering: "
            "from ingesting 3.1 billion raw AIS pings to serving "
            "interactive risk maps through a modern web application. "
            "The combination of spatial analysis (H3 + PostGIS), "
            "expert-elicited risk scoring, machine learning (XGBoost "
            "SDMs + deep learning classifiers), and community-driven "
            "sighting reports creates a comprehensive tool for marine "
            "conservation and vessel traffic management."
        ),
        align="C",
    )

    pdf.ln(10)
    pdf.stat_boxes(
        [
            ("9", "Development Phases"),
            ("40", "Git Commits"),
            ("10", "Generated PDFs"),
            ("1", "Platform"),
        ]
    )

    # ── SAVE ──────────────────────────────────────────────────
    pdf.output(str(OUTPUT_FILE))
    print(f"PDF saved to {OUTPUT_FILE}")
    print(f"  Pages: {pdf.page_no()}")


if __name__ == "__main__":
    build_report()

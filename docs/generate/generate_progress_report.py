"""Generate a styled PDF progress report for the Marine Risk Mapping project."""

from fpdf import FPDF


class ReportPDF(FPDF):
    """Custom PDF with header/footer styling."""

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
                "Marine Risk Mapping - Project Progress Report",
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

    def tech_card(self, name, category, purpose, details):
        """Draw a styled card for a technology."""
        card_w = 190
        x_start = self.get_x()
        y_start = self.get_y()

        if y_start > 250:
            self.add_page()
            y_start = self.get_y()

        # Card background
        self.set_fill_color(*self.LIGHT_BG)
        self.rect(x_start, y_start, card_w, 28, style="F")

        # Left accent bar
        cat_colours = {
            "Storage": self.ACCENT_BLUE,
            "Transform": self.TEAL,
            "Quality": self.ACCENT_GREEN,
            "Infra": self.ACCENT_AMBER,
            "Language": self.NAVY,
            "Tooling": self.ACCENT_RED,
        }
        colour = cat_colours.get(category, self.TEAL)
        self.set_fill_color(*colour)
        self.rect(x_start, y_start, 3, 28, style="F")

        # Name + category
        self.set_xy(x_start + 6, y_start + 2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*self.NAVY)
        self.cell(80, 6, name)

        self.set_font("Helvetica", "", 8)
        self.set_text_color(*colour)
        self.cell(40, 6, f"[{category}]")

        # Purpose
        self.set_xy(x_start + 6, y_start + 9)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.DARK_TEXT)
        self.cell(180, 5, purpose)

        # Details
        self.set_xy(x_start + 6, y_start + 16)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*self.MID_TEXT)
        self.multi_cell(178, 4, details)

        self.set_y(y_start + 31)

    def lesson_card(self, number, title, description):
        """Draw a styled lesson-learned card."""
        card_w = 190
        y_start = self.get_y()

        if y_start > 245:
            self.add_page()
            y_start = self.get_y()

        # Background
        self.set_fill_color(*self.LIGHT_BG)
        self.rect(10, y_start, card_w, 24, style="F")

        # Number circle
        self.set_fill_color(*self.TEAL)
        self.set_draw_color(*self.TEAL)
        cx = 20
        cy = y_start + 12
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
        self.set_xy(28, y_start + 11)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(168, 4, description)

        self.set_y(y_start + 27)

    def phase_row(self, phase, status, description):
        """Draw a phase status row."""
        y = self.get_y()
        if y > 270:
            self.add_page()
            y = self.get_y()

        # Status indicator
        if status == "complete":
            self.set_fill_color(*self.ACCENT_GREEN)
            label = "DONE"
        elif status == "partial":
            self.set_fill_color(*self.ACCENT_AMBER)
            label = "WIP"
        else:
            self.set_fill_color(200, 200, 200)
            label = "TODO"

        self.set_xy(10, y)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.WHITE)
        self.cell(18, 7, label, fill=True, align="C")

        self.set_xy(30, y)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.NAVY)
        self.cell(45, 7, phase)

        self.set_xy(75, y)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.DARK_TEXT)
        self.cell(125, 7, description)

        self.ln(9)


def build_report():
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # -- COVER PAGE ----------------------------------
    pdf.add_page()
    pdf.ln(40)

    # Title block
    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.rect(0, 30, 210, 65, style="F")

    pdf.set_xy(10, 38)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.cell(0, 14, "Marine Risk Mapping", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "Whale-Vessel Collision Risk Platform",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "I", 11)
    pdf.set_text_color(180, 200, 220)
    pdf.cell(
        0,
        10,
        "Project Progress Report  |  February 2026",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(30)

    # Stats boxes
    stats = [
        ("3.1B", "AIS Records"),
        ("460K", "Whale Sightings"),
        ("843", "Protected Areas"),
        ("12/12", "dbt Tests Pass"),
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
            "This report summarises the technologies adopted, architectural "
            "decisions made, and lessons learned while building the marine risk "
            "mapping platform through Phases 1-5."
        ),
        align="C",
    )

    # -- PHASE PROGRESS ------------------------------
    pdf.add_page()
    pdf.section_title("Phase Progress")

    phases = [
        ("Phase 1", "complete", "Project Setup - uv, git, ruff, pre-commit"),
        (
            "Phase 2",
            "complete",
            "Data Acquisition - AIS, cetaceans, bathymetry, MPA, S3",
        ),
        (
            "Phase 3",
            "complete",
            "Database Setup - PostGIS Docker, schema, DuckDB views",
        ),
        ("Phase 4", "complete", "Data Quality - Pandera schemas, validation, reports"),
        (
            "Phase 5",
            "partial",
            "dbt Transforms - staging models built, spatial joins next",
        ),
        ("Phase 6", "todo", "Orchestration - Dagster assets, schedules, monitoring"),
        ("Phase 7", "todo", "Risk Model - spatial analysis, scoring, validation"),
        ("Phase 8", "todo", "Backend API - FastAPI endpoints"),
        ("Phase 9", "todo", "Frontend - Next.js + Deck.gl dashboard"),
        ("Phase 10", "todo", "Testing - pytest, Vitest, E2E"),
        ("Phase 11", "todo", "Containerisation - Dockerfiles, CI/CD"),
        ("Phase 12", "todo", "Cloud Deployment - AWS ECS, RDS, S3"),
    ]
    for phase, status, desc in phases:
        pdf.phase_row(phase, status, desc)

    # -- TECHNOLOGIES --------------------------------
    pdf.add_page()
    pdf.section_title("Technologies Used")
    pdf.body_text(
        "Each technology was chosen for a specific reason. "
        "Below is every tool adopted so far, grouped by role."
    )

    technologies = [
        (
            "Python 3.12",
            "Language",
            "Core language for all pipeline, validation, and analysis code.",
            "Chosen for its data ecosystem (pandas, geopandas, duckdb). "
            "3.12 for performance improvements and better error messages.",
        ),
        (
            "uv",
            "Tooling",
            "Python package manager and virtual environment tool.",
            "10-100x faster than pip. Manages lockfile (uv.lock) for reproducible "
            "installs. Single tool replaces pip, pip-tools, and virtualenv.",
        ),
        (
            "Ruff",
            "Tooling",
            "Linter and formatter for Python code.",
            "Replaces flake8, black, and isort in one tool. Written in Rust - "
            "lints the entire codebase in under a second. Configured in pyproject.toml.",
        ),
        (
            "DuckDB",
            "Storage",
            "Analytical query engine over raw Parquet files.",
            "Queries 3.1B AIS rows directly from parquet without loading into a database. "
            "Uses columnar storage for fast aggregations. Spatial extension for geometry.",
        ),
        (
            "PostGIS (Docker)",
            "Storage",
            "Spatial database for serving cleaned, pre-aggregated data.",
            "PostgreSQL + PostGIS extension for spatial queries (ST_Intersects, "
            "ST_Distance). Runs in Docker on port 5433. Stores cetacean and MPA data.",
        ),
        (
            "AWS S3",
            "Storage",
            "Cloud storage for raw data backup and sharing.",
            "Parquet files uploaded to s3://marine-risk-mapping-hh (eu-west-2). "
            "Cheap, durable storage. boto3 for Python integration.",
        ),
        (
            "Apache Parquet",
            "Storage",
            "Columnar file format for all raw datasets.",
            "80-90% smaller than CSV. Preserves data types and schemas. "
            "Natively supported by DuckDB, pandas, and geopandas.",
        ),
        (
            "Pandera",
            "Quality",
            "Schema validation and data contracts for DataFrames.",
            "Defines expected columns, types, and constraints. lazy=True collects "
            "all failures in one pass. Guards data before it enters PostGIS.",
        ),
        (
            "dbt (dbt-postgres)",
            "Transform",
            "SQL transformation framework with built-in testing.",
            "Manages staging/intermediate/mart SQL models as version-controlled files. "
            "Runs against PostGIS. 12 tests passing on staging layer.",
        ),
        (
            "Docker + Docker Compose",
            "Infra",
            "Container runtime for local PostGIS database.",
            "postgis/postgis:16-3.4 image (amd64 emulated via Rosetta 2 on Apple Silicon). "
            "docker-compose.yml with health checks and persistent volumes.",
        ),
        (
            "GeoPandas",
            "Language",
            "Spatial data manipulation in Python.",
            "Extends pandas with geometry columns. Used for reading GeoParquet, "
            "exploring MPA polygons, and spatial operations in Python.",
        ),
        (
            "Rasterio",
            "Language",
            "Raster data reading and analysis.",
            "Reads bathymetry GeoTIFF (15600x6000 pixels, ~15 arc-second resolution). "
            "GEBCO depth data from -6233m to +4336m elevation.",
        ),
        (
            "httpx",
            "Language",
            "HTTP client for downloading data from APIs.",
            "Async-capable, modern replacement for requests. Used for OBIS API "
            "and MarineCadastre file downloads.",
        ),
        (
            "Matplotlib",
            "Language",
            "Visualisation library for data quality charts.",
            "Completeness bar charts, species distributions, geometry health pie charts. "
            "Used in quality report notebook.",
        ),
    ]

    for name, cat, purpose, details in technologies:
        pdf.tech_card(name, cat, purpose, details)

    # -- ARCHITECTURE DECISIONS ----------------------
    pdf.add_page()
    pdf.section_title("Key Architecture Decisions")

    pdf.subsection_title("1. DuckDB for analytics, PostGIS for serving")
    pdf.body_text(
        "Raw AIS data (3.1 billion rows, ~80GB parquet) stays in parquet files "
        "and is queried via DuckDB views. PostGIS only stores smaller datasets "
        "(cetacean sightings, MPAs) and will receive pre-aggregated results from "
        "dbt. This avoids a 24+ hour bulk load and keeps the spatial database "
        "focused on what it does best - serving spatial queries to the API."
    )

    pdf.subsection_title("2. Layered dbt transformation")
    pdf.body_text(
        "SQL transformations follow the staging -> intermediate -> mart pattern. "
        "Staging cleans raw data (fix invalid geometries, backfill nulls, rename "
        "columns). Intermediate performs spatial joins. Marts produce the final "
        "risk scores. Each layer is independently testable."
    )

    pdf.subsection_title("3. Validation at two boundaries")
    pdf.body_text(
        "Pandera validates raw data before it enters PostGIS (structural checks). "
        "dbt tests validate transformed data after SQL runs (transformation logic "
        "checks). This belt-and-braces approach catches issues whether they "
        "originate in source data or in our own SQL."
    )

    pdf.subsection_title("4. Docker PostGIS on port 5433")
    pdf.body_text(
        "The development machine runs a local PostgreSQL on port 5432. Rather "
        "than stopping it, Docker PostGIS maps to 5433. All connection configs "
        "(load_data.py, profiles.yml) reference this port explicitly."
    )

    # -- LESSONS LEARNED -----------------------------
    pdf.add_page()
    pdf.section_title("Lessons Learned")

    lessons = [
        (
            "Don't load everything into the database",
            "Initial plan was to bulk-load 3.1B AIS rows into PostGIS. After "
            "three optimisation attempts (iterrows -> vectorized -> COPY protocol), "
            "each file still took ~4 minutes. The real lesson: analytical workloads "
            "belong in DuckDB/parquet, PostGIS is for serving pre-aggregated results.",
        ),
        (
            "Apple Silicon needs Rosetta for PostGIS",
            "The postgis/postgis Docker image has no ARM64 builds. Setting "
            "'platform: linux/arm64' in docker-compose.yml caused a crash. "
            "Removing it lets Docker Desktop use Rosetta 2 to emulate amd64 - "
            "slower but works transparently.",
        ),
        (
            "Sentinel values are not null",
            "MPA dataset uses Estab_Yr=0 for 'unknown' instead of NULL. "
            "Pandera's in_range(1800, 2030) caught this. Fixed with "
            "NULLIF(estab_yr, 0) in the dbt staging model. Always check for "
            "domain-specific sentinel values.",
        ),
        (
            "Schema validation finds real issues",
            "First Pandera run revealed: 51K null-species cetacean rows (genus-level "
            "IDs, not bad data), 53 MPA sentinel years, and 2,957 out-of-range AIS "
            "MMSIs (SAR aircraft and aids to navigation, valid but outside the "
            "standard vessel range). Each finding improved our understanding.",
        ),
        (
            "Reserved words bite you in SQL",
            "The cetacean data has an 'order' column - a PostgreSQL reserved keyword. "
            'Without double-quoting ("order") the query fails. Staging renames it to '
            "taxonomic_order so no downstream model needs to worry about this again.",
        ),
        (
            "55 invalid MPA geometries",
            "Quality report found 6.5% of MPA polygons have geometry errors "
            "(self-intersections). ST_MakeValid() in the dbt staging model fixes "
            "these automatically. Without this, spatial joins (ST_Intersects) would "
            "silently return wrong results or fail.",
        ),
        (
            "ruff --fix can't fix line length",
            "E501 (line too long) errors persisted across multiple ruff runs because "
            "--fix doesn't auto-wrap lines. These require manual intervention - "
            "Python's implicit string concatenation is the cleanest solution for long "
            "SQL strings.",
        ),
        (
            "Pre-commit hooks conflict with VS Code",
            "Pre-commit runs ruff which modifies files during the commit. VS Code's "
            "git integration doesn't handle this gracefully. Solution: run "
            "'ruff check --fix && ruff format' manually before committing via CLI.",
        ),
        (
            "Two-thirds of AIS pings are stationary",
            "SOG (speed over ground) is zero for 65.7% of vessel pings - ships at "
            "anchor or moored. These are irrelevant for collision risk. Filtering "
            "sog > 0 will dramatically reduce data volume in the risk model.",
        ),
        (
            "dbt needs an explicit profile: field",
            "dbt_project.yml had 'name: marine_risk' but no 'profile:' key. "
            "dbt 1.11 hit an unbound variable bug instead of a clear error message. "
            "Always include both name and profile in dbt_project.yml.",
        ),
    ]

    for i, (title, description) in enumerate(lessons, 1):
        pdf.lesson_card(i, title, description)

    # -- DATA LANDSCAPE ------------------------------
    pdf.add_page()
    pdf.section_title("Data Landscape")

    pdf.subsection_title("Dataset Overview")

    # Table header
    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.set_font("Helvetica", "B", 9)
    col_widths = [40, 35, 30, 85]
    headers = ["Dataset", "Rows", "Format", "Notes"]
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, h, border=1, fill=True, align="C")
    pdf.ln()

    # Table rows
    pdf.set_text_color(*ReportPDF.DARK_TEXT)
    pdf.set_font("Helvetica", "", 8.5)
    rows = [
        (
            "AIS Positions",
            "3,118,715,727",
            "Parquet",
            "365 daily files, queried via DuckDB",
        ),
        ("Cetacean Sightings", "460,212", "Parquet", "OBIS data, loaded into PostGIS"),
        (
            "Marine Protected Areas",
            "843",
            "GeoParquet",
            "NOAA MPA Inventory, loaded into PostGIS",
        ),
        (
            "Bathymetry",
            "93.6M pixels",
            "GeoTIFF",
            "GEBCO 15-arc-second, sampled on-the-fly",
        ),
    ]
    for row in rows:
        fill = rows.index(row) % 2 == 0
        if fill:
            pdf.set_fill_color(*ReportPDF.LIGHT_BG)
        for w, val in zip(col_widths, row):
            pdf.cell(w, 7, val, border=1, fill=fill, align="C")
        pdf.ln()

    pdf.ln(6)
    pdf.subsection_title("Data Quality Summary")

    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.set_font("Helvetica", "B", 9)
    col_widths2 = [50, 35, 35, 70]
    headers2 = ["Dataset", "Schema Valid", "Avg Completeness", "Key Finding"]
    for w, h in zip(col_widths2, headers2):
        pdf.cell(w, 8, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_text_color(*ReportPDF.DARK_TEXT)
    pdf.set_font("Helvetica", "", 8.5)
    quality_rows = [
        ("Cetacean", "PASS", "97.5%", "11% null species (genus-level IDs)"),
        ("MPA", "PASS", "100%", "55 invalid geometries (6.5%)"),
        ("AIS (sample)", "PASS", "88.7%", "Heading 48%, draft 58% complete"),
    ]
    for row in quality_rows:
        fill = quality_rows.index(row) % 2 == 0
        if fill:
            pdf.set_fill_color(*ReportPDF.LIGHT_BG)
        for w, val in zip(col_widths2, row):
            pdf.cell(w, 7, val, border=1, fill=fill, align="C")
        pdf.ln()

    # -- WHAT'S NEXT ---------------------------------
    pdf.ln(8)
    pdf.section_title("What's Next")

    next_steps = [
        (
            "Phase 5 (cont.)",
            "Build intermediate spatial join models and mart risk score tables in dbt",
        ),
        (
            "Phase 6",
            "Wire everything into Dagster for orchestrated, scheduled pipeline runs",
        ),
        (
            "Phase 7",
            "Exploratory spatial analysis and risk scoring model (GeoPandas + scikit-learn)",
        ),
        (
            "Phase 8",
            "FastAPI backend exposing risk scores, sightings, and vessel traffic endpoints",
        ),
        (
            "Phase 9",
            "Next.js frontend with Deck.gl for interactive risk heatmap visualisation",
        ),
    ]

    for phase, desc in next_steps:
        y = pdf.get_y()
        pdf.set_fill_color(*ReportPDF.TEAL)
        pdf.set_text_color(*ReportPDF.WHITE)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 7, phase, fill=True, align="C")
        pdf.set_text_color(*ReportPDF.DARK_TEXT)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(160, 7, f"  {desc}")
        pdf.ln(9)

    # Save
    output_path = "docs/marine_risk_progress_report.pdf"
    pdf.output(output_path)
    print(f"Report saved to {output_path}")


if __name__ == "__main__":
    build_report()

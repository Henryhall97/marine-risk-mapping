"""Generate Phase 6 summary PDF: Dagster orchestration + pipeline refactor."""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "phase6_dagster_orchestration.pdf"


class ReportPDF(FPDF):
    """Custom PDF with navy/teal theme (matches earlier reports)."""

    NAVY = (15, 32, 65)
    TEAL = (0, 150, 136)
    LIGHT_BG = (240, 245, 250)
    WHITE = (255, 255, 255)
    DARK_TEXT = (30, 30, 30)
    MID_TEXT = (80, 80, 80)
    ACCENT_GREEN = (46, 204, 113)
    ACCENT_AMBER = (243, 156, 18)
    ACCENT_BLUE = (52, 152, 219)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(
                0,
                10,
                "Marine Risk Mapping - Phase 6: Dagster Orchestration",
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

    def bullet(self, text, indent=15):
        x = self.get_x()
        self.set_x(x + indent - 5)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.TEAL)
        self.cell(5, 5.5, chr(8226).encode("latin-1", "replace").decode("latin-1"))
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def stat_boxes(self, stats, y=None):
        """Draw a row of stat boxes."""
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

    def asset_table(self, rows):
        """Draw a coloured table of assets."""
        col_w = [55, 18, 117]
        # Header
        self.set_fill_color(*self.NAVY)
        self.set_text_color(*self.WHITE)
        self.set_font("Helvetica", "B", 9)
        for w, h_text in zip(col_w, ["Group", "Count", "Assets"]):
            self.cell(w, 7, f"  {h_text}", fill=True)
        self.ln()
        # Rows
        self.set_font("Helvetica", "", 8.5)
        for i, (group, count, assets_str) in enumerate(rows):
            bg = self.LIGHT_BG if i % 2 == 0 else self.WHITE
            self.set_fill_color(*bg)
            self.set_text_color(*self.DARK_TEXT)
            self.cell(col_w[0], 7, f"  {group}", fill=True)
            self.set_text_color(*self.TEAL)
            self.cell(col_w[1], 7, f"  {count}", fill=True)
            self.set_text_color(*self.DARK_TEXT)
            self.cell(col_w[2], 7, f"  {assets_str}", fill=True)
            self.ln()
        self.ln(3)

    def tech_card(self, name, category, purpose, details):
        card_w = 190
        x_start = self.get_x()
        y_start = self.get_y()
        if y_start > 250:
            self.add_page()
            y_start = self.get_y()
        self.set_fill_color(*self.LIGHT_BG)
        self.rect(x_start, y_start, card_w, 28, style="F")
        cat_colours = {
            "Orchestration": self.TEAL,
            "Transform": self.ACCENT_BLUE,
            "Config": self.ACCENT_AMBER,
            "Infra": self.ACCENT_GREEN,
        }
        colour = cat_colours.get(category, self.TEAL)
        self.set_fill_color(*colour)
        self.rect(x_start, y_start, 3, 28, style="F")
        self.set_xy(x_start + 6, y_start + 2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*self.NAVY)
        self.cell(80, 6, name)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*colour)
        self.cell(40, 6, f"[{category}]")
        self.set_xy(x_start + 6, y_start + 9)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.DARK_TEXT)
        self.cell(180, 5, purpose)
        self.set_xy(x_start + 6, y_start + 16)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*self.MID_TEXT)
        self.multi_cell(178, 4, details)
        self.set_y(y_start + 31)


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
    pdf.rect(0, 30, 210, 65, style="F")

    pdf.set_xy(10, 38)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.cell(0, 14, "Phase 6", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "Dagster Orchestration & Pipeline Refactor",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "I", 11)
    pdf.set_text_color(180, 200, 220)
    pdf.cell(
        0,
        10,
        "Marine Risk Mapping  |  March 2026",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(30)

    pdf.stat_boxes(
        [
            ("37", "Dagster Assets"),
            ("136", "dbt Passes"),
            ("13", "Files Refactored"),
            ("0", "Errors"),
        ]
    )

    pdf.ln(10)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.multi_cell(
        0,
        5.5,
        (
            "This phase wrapped all 15 Python pipeline scripts and 22 dbt models "
            "into a unified Dagster asset graph, giving us lineage tracking, "
            "selective materialisation, and a web UI for monitoring. "
            "Simultaneously, we centralised all domain constants into "
            "pipeline/config.py and dbt vars to eliminate duplication."
        ),
        align="C",
    )

    # ================================================================
    # PAGE 2: What We Built
    # ================================================================
    pdf.add_page()
    pdf.section_title("1. What We Built")

    pdf.subsection_title("Dagster Asset Graph (37 assets)")
    pdf.body_text(
        "Every step of the pipeline -- from downloading raw AIS data to "
        "producing the final fct_collision_risk mart -- is now a Dagster "
        "asset with tracked lineage, metadata, and retry capability."
    )

    pdf.asset_table(
        [
            ("Ingestion", "8", "raw_ais_data, raw_cetacean_data, raw_mpa_data, ..."),
            ("Database", "2", "postgis_schema, postgis_raw_data"),
            ("Aggregation", "5", "ais_h3_summary, cetacean_sighting_h3, ..."),
            ("dbt (staging)", "6", "stg_cetacean_sightings, stg_ship_strikes, ..."),
            ("dbt (intermediate)", "10", "int_hex_grid, int_vessel_traffic, ..."),
            ("dbt (marts)", "5", "fct_collision_risk, fct_species_risk, ..."),
            ("dbt (seeds)", "1", "species_crosswalk"),
        ]
    )

    pdf.subsection_title("Pipeline Configuration Refactor")
    pdf.body_text(
        "Extracted ~110 magic numbers from 12 files into two central locations:\n"
        "  - pipeline/config.py: Python-side constants (vessel codes, speed "
        "thresholds, decay parameters, file paths)\n"
        "  - dbt_project.yml vars: SQL-side thresholds (bathymetry breaks, "
        "proximity lambdas, spatial join tolerances)\n\n"
        "Also created pipeline/utils.py with shared helpers (to_python, "
        "bulk_insert, assign_h3_cells), reducing assign_cetacean_h3.py and "
        "assign_ship_strike_h3.py from ~115 lines each to ~35 lines."
    )

    # ================================================================
    # PAGE 3: Why -- Design Decisions
    # ================================================================
    pdf.add_page()
    pdf.section_title("2. Why -- Design Decisions")

    pdf.subsection_title("Why Dagster (not Airflow, Prefect, or Makefiles)?")
    pdf.body_text(
        "1. Asset-centric model: Dagster thinks in data assets, not tasks. "
        "Each dbt model, Python script, and database table is a first-class "
        "citizen with lineage and metadata -- a natural fit for a data pipeline.\n\n"
        "2. dagster-dbt integration: The @dbt_assets decorator auto-generates "
        "one Dagster asset per dbt model from the manifest, keeping the two "
        "systems in sync without manual wiring.\n\n"
        "3. Selective materialisation: From the web UI, you can re-run just "
        "the aggregation layer, or just the marts, without touching ingestion. "
        "This saves hours during development.\n\n"
        "4. No infrastructure overhead: dagster dev runs locally as a single "
        "process -- no scheduler, no message broker, no container orchestration "
        "needed for development."
    )

    pdf.subsection_title("Why centralise config into pipeline/config.py?")
    pdf.body_text(
        "Before: DB_CONFIG was defined in 7 files, H3_RESOLUTION in 4, "
        "vessel type codes in 14 inline SQL occurrences, and the NOAA "
        "10-knot speed threshold appeared 4 times in aggregate_ais.py.\n\n"
        "After: One import, one place to change. Vessel codes, speed/size "
        "thresholds, day/night boundaries, nav status codes, proximity "
        "decay parameters, and bathymetry breaks all live in config.py "
        "with the SQL-side mirrors in dbt_project.yml vars."
    )

    pdf.subsection_title("What we intentionally left inline")
    pdf.body_text(
        "Risk model weights (~50 numbers in fct_collision_risk) stay inline "
        "because they are model architecture, not tunable parameters. "
        "Extracting them would scatter context without reducing duplication. "
        "Similarly, Earth-radius and km-per-degree are well-known physical "
        "constants, not domain choices."
    )

    # ================================================================
    # PAGE 4: How -- Implementation
    # ================================================================
    pdf.add_page()
    pdf.section_title("3. How -- Implementation Highlights")

    pdf.subsection_title("Dagster-dbt Integration Pattern")
    pdf.body_text(
        "DbtProject(project_dir, profiles_dir) discovers the dbt project "
        "and calls prepare_if_dev() to auto-parse the manifest at import "
        "time. The @dbt_assets decorator reads the manifest and generates "
        "one Dagster asset per model/seed. DbtCliResource handles CLI "
        "invocation with --profiles-dir automatically."
    )

    pdf.subsection_title("Asset Dependency Wiring")
    pdf.body_text(
        "Python assets use deps=[...] to declare upstream dependencies:\n"
        "  - postgis_raw_data depends on all 8 ingestion assets\n"
        "  - ais_h3_summary depends on raw_ais_data + postgis_raw_data\n"
        "  - cell_proximity depends on ais_h3_summary + all H3 assignment assets\n"
        "  - dbt assets auto-detect their sources from the manifest\n\n"
        "Dagster resolves the full topological order, so the full_pipeline "
        "job executes everything in the correct sequence."
    )

    pdf.subsection_title("Config Centralisation Approach")
    pdf.body_text(
        "Python side: pipeline/config.py exports typed constants. "
        "VESSEL_TYPE_CODES is a dict[str, list[int]] so aggregate_ais.py "
        "can format them for SQL IN clauses via a _sql_in() helper.\n\n"
        "SQL side: dbt_project.yml defines 9 vars (shelf_depth_m, "
        "proximity_whale_lambda, cetacean_recent_year, etc.) referenced "
        "via {{ var('name') }} in models. Values are kept in sync with "
        "config.py manually -- documented in both files."
    )

    # ================================================================
    # PAGE 5: Challenges & Solutions
    # ================================================================
    pdf.add_page()
    pdf.section_title("4. Challenges & Solutions")

    challenges = [
        (
            "fpdf2 Unicode in Helvetica",
            "fpdf2's built-in Helvetica only supports Latin-1. Em dashes, "
            "lambda symbols, and box-drawing characters caused silent "
            "replacement. Solution: ASCII-only strings in PDF generators, "
            "with a _fix_unicode.py helper for cleanup.",
        ),
        (
            "DbtProject profiles_dir",
            "Our profiles.yml lives in transform/, not ~/.dbt/. Without "
            "passing profiles_dir to both DbtProject and DbtCliResource, "
            "dbt parse would fail silently at Dagster load time. Both "
            "now explicitly set profiles_dir=TRANSFORM_DIR.",
        ),
        (
            "Vessel type code ranges in SQL",
            "Config stores passenger codes as [60..69, 1012..1015] but "
            "DuckDB SQL needs 'BETWEEN 60 AND 69 OR IN (1012, 1013...)'. "
            "Solved by expanding ranges with *range() in config.py and "
            "formatting via _sql_in() -- SQL sees flat comma lists.",
        ),
        (
            "Duplicate _run_script helpers",
            "Three asset modules (ingestion, database, aggregation) each "
            "had a near-identical _run_script function. Left as-is for "
            "now -- each may diverge (e.g. aggregation passes extra_args). "
            "A shared utility would add coupling without clear benefit yet.",
        ),
    ]

    for title, desc in challenges:
        pdf.subsection_title(title)
        pdf.body_text(desc)

    # ================================================================
    # PAGE 6: Key Technologies
    # ================================================================
    pdf.add_page()
    pdf.section_title("5. Key Technologies")

    techs = [
        (
            "Dagster 1.12",
            "Orchestration",
            "Asset-centric pipeline orchestration with web UI",
            "37 assets across 4 groups, selective materialisation, metadata tracking",
        ),
        (
            "dagster-dbt 0.28",
            "Orchestration",
            "Auto-generate Dagster assets from dbt manifest",
            "@dbt_assets decorator, DbtProject, DbtCliResource, prepare_if_dev()",
        ),
        (
            "pipeline/config.py",
            "Config",
            "Single source of truth for all domain constants",
            "VESSEL_TYPE_CODES, HIGH_SPEED_KNOTS, proximity decay, bathymetry breaks",
        ),
        (
            "dbt vars",
            "Transform",
            "SQL-side mirrors of Python config constants",
            "9 vars in dbt_project.yml: shelf_depth_m, proximity lambdas, etc.",
        ),
        (
            "pipeline/utils.py",
            "Config",
            "Shared helpers eliminating code duplication",
            "to_python, bulk_insert, assign_h3_cells -- used by 6+ scripts",
        ),
    ]

    for name, cat, purpose, details in techs:
        pdf.tech_card(name, cat, purpose, details)

    # ================================================================
    # PAGE 7: Key Takeaways
    # ================================================================
    pdf.add_page()
    pdf.section_title("6. Key Takeaways")

    takeaways = [
        "37 Dagster assets cover the full pipeline from raw download to dbt marts",
        "dagster-dbt auto-generates 22 assets from the dbt manifest -- zero manual wiring",
        "full_pipeline job materialises everything in topological order",
        "pipeline/config.py: single source of truth for ~60 domain constants",
        "dbt_project.yml vars: 9 SQL-side thresholds referenced via {{ var() }}",
        "13 Python files refactored to import from config.py (was 7x DB_CONFIG duplication)",
        "assign_h3 scripts reduced from ~115 to ~35 lines each via shared utility",
        "136/136 dbt build passes (21 models, 114 tests, 1 seed, 0 errors)",
        "dagster definitions validate passes -- all assets, resources, and jobs resolve",
        "Risk model weights (~50 numbers) intentionally left inline -- architecture not config",
    ]

    for i, text in enumerate(takeaways, 1):
        y = pdf.get_y()
        if y > 265:
            pdf.add_page()
        # Number
        pdf.set_fill_color(*ReportPDF.TEAL)
        cx = 17
        cy = y + 4
        pdf.ellipse(cx - 4, cy - 4, 8, 8, style="F")
        pdf.set_xy(cx - 4, cy - 3)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*ReportPDF.WHITE)
        pdf.cell(8, 6, str(i), align="C")
        # Text
        pdf.set_xy(27, y + 1)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*ReportPDF.DARK_TEXT)
        pdf.multi_cell(165, 5, text)
        pdf.ln(3)

    # ================================================================
    # Save
    # ================================================================
    pdf.output(str(OUTPUT_FILE))
    print(f"PDF written to {OUTPUT_FILE}")
    print(f"  Size: {OUTPUT_FILE.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    build_report()

"""Generate Scalability Assessment PDF.

Comprehensive audit of database, backend API, frontend, and
infrastructure scalability across the marine risk mapping platform.

Usage:
    uv run python docs/generate/generate_scalability_report.py
"""

from pathlib import Path

from fpdf import FPDF

# ── Paths ─────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "scalability_assessment.pdf"


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
    ACCENT_RED = (214, 64, 69)
    ACCENT_BLUE = (52, 152, 219)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(
                0,
                10,
                "Marine Risk Mapping -- Scalability Assessment",
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
            if self.get_y() > 270:
                self.add_page()
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
        if self.get_y() > 245:
            self.add_page()
        y_start = self.get_y()
        self.set_font("Helvetica", "", 9.5)
        n_lines = max(1, len(text) // 80 + 1)
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

    def severity_badge(
        self,
        label: str,
        severity: str,
    ) -> None:
        colour_map = {
            "CRITICAL": self.ACCENT_RED,
            "HIGH": self.ACCENT_AMBER,
            "MEDIUM": self.ACCENT_BLUE,
            "LOW": self.ACCENT_GREEN,
        }
        colour = colour_map.get(severity, self.MID_TEXT)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*colour)
        self.cell(18, 6, severity)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.DARK_TEXT)
        self.cell(0, 6, label, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)


# ═══════════════════════════════════════════════════════════════
# Build report
# ═══════════════════════════════════════════════════════════════


def build_report() -> None:
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Cover page ────────────────────────────────────────────
    pdf.add_page()
    pdf.set_fill_color(*ReportPDF.NAVY)
    pdf.rect(0, 0, 210, 297, style="F")
    pdf.set_y(80)
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.cell(0, 15, "Scalability Assessment", align="C")
    pdf.ln(12)
    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "Marine Risk Mapping Platform",
        align="C",
    )
    pdf.ln(20)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(180, 200, 220)
    pdf.cell(0, 8, "Database | Backend API | Frontend | Infrastructure", align="C")
    pdf.ln(8)
    pdf.cell(0, 8, "March 2026", align="C")
    pdf.ln(30)

    # Summary boxes on cover
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*ReportPDF.WHITE)
    box_data = [
        ("4", "Audit Layers"),
        ("28", "Findings"),
        ("10", "Priority Actions"),
        ("8", "Low-Effort Fixes"),
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

    # ── Executive Summary ─────────────────────────────────────
    pdf.add_page()
    pdf.section_title("1. Executive Summary")
    pdf.body_text(
        "The platform is well-architected for a single-user development "
        "workflow but has critical gaps that would surface under "
        "multi-user production load or data growth. The top issues "
        "cluster around three themes: missing database indexes on "
        "primary query paths, no caching layer in the API, and "
        "full-refresh-only dbt materialisation for tables up to "
        "58M rows."
    )
    pdf.ln(2)
    pdf.stat_boxes(
        [
            ("C", "Database"),
            ("C+", "Backend API"),
            ("B+", "Frontend"),
            ("C+", "Infrastructure"),
        ]
    )
    pdf.ln(4)
    pdf.body_text(
        "The database layer is the most critical bottleneck. "
        "Every spatial API endpoint filters on cell_lat/cell_lon "
        "columns that have no B-tree indexes, forcing full "
        "sequential scans on tables with 1.8M to 58M rows. "
        "The GiST indexes on geometry columns are built by dbt "
        "but never used by the API query patterns."
    )

    # ── Database Scalability ──────────────────────────────────
    pdf.add_page()
    pdf.section_title("2. Database Scalability")

    pdf.subsection_title("2.1 Missing Bbox Indexes")
    pdf.callout_box(
        "CRITICAL",
        "Every spatial API query filters on cell_lat/cell_lon, "
        "but no dbt model defines B-tree indexes on these columns. "
        "All queries are full sequential scans.",
        ReportPDF.ACCENT_RED,
    )
    pdf.metric_table(
        ["Table", "Rows", "API Queries", "Index?", "Impact"],
        [
            [
                "int_hex_grid",
                "1.9M",
                "All 12+ layer endpoints",
                "None",
                "Seq scan",
            ],
            [
                "fct_collision_risk",
                "1.8M",
                "Risk zones/stats/detail",
                "h3_cell only",
                "Seq scan",
            ],
            [
                "fct_collision_risk_seasonal",
                "7.3M",
                "Seasonal risk",
                "h3_cell,season",
                "Seq scan",
            ],
            [
                "fct_collision_risk_ml",
                "7.3M",
                "ML risk endpoints",
                "h3_cell,season",
                "Seq scan",
            ],
            [
                "fct_collision_risk_ml_projected",
                "58M",
                "Climate projections",
                "h3_cell,scenario",
                "Seq scan",
            ],
        ],
        [52, 18, 50, 40, 30],
    )

    pdf.subsection_title("2.2 Intermediate Tables Missing h3_cell Indexes")
    pdf.body_text(
        "Seven intermediate tables used in API JOIN paths "
        "lack h3_cell B-tree indexes. This forces hash joins "
        "instead of faster nested-loop + index-lookup plans:"
    )
    missing = [
        "int_bathymetry (1M rows)",
        "int_proximity (1.9M rows)",
        "int_nisi_reference_risk (1.1M rows)",
        "int_ocean_covariates (1.1M rows)",
        "int_cetacean_density (76K rows)",
        "int_mpa_coverage (21K rows)",
        "int_speed_zone_coverage (30K rows)",
    ]
    for m in missing:
        pdf.bullet(m)

    pdf.subsection_title("2.3 Query Anti-Patterns")
    patterns = [
        (
            "Double-scan pagination: COUNT + SELECT with the same "
            "unindexed bbox filter doubles sequential scan cost."
        ),
        (
            "Risk compare endpoint: Joins two 7.3M-row tables with "
            "bbox filtering only on the left table."
        ),
        (
            "Cell context endpoint: Fires 4 serial queries "
            "including two ST_Intersects spatial lookups."
        ),
        (
            "Correlated subqueries: Event listing uses "
            "2 subqueries per result row across 4 functions."
        ),
    ]
    for p in patterns:
        pdf.bullet(p)

    # ── Backend API ───────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("3. Backend API Scalability")

    pdf.subsection_title("3.1 No Application-Level Caching")
    pdf.callout_box(
        "HIGH SEVERITY",
        "Only bathymetry contour GeoJSON is cached (process "
        "lifetime). All other queries hit PostgreSQL on every "
        "request: macro overview (14K rows, ~5 MB), species "
        "crosswalk (138 static rows), risk stats (recomputed), "
        "ML predictions (re-inferred). No Redis, no lru_cache, "
        "no ETags.",
        ReportPDF.ACCENT_AMBER,
    )

    pdf.subsection_title("3.2 Sync DB Driver on Async Framework")
    pdf.body_text(
        "psycopg2 (synchronous) is used in FastAPI (async). "
        "Sync def route handlers are auto-offloaded to a thread "
        "pool (40 threads default), which works. However, the "
        "7 async def handlers (photo/audio upload routes) call "
        "sync classifier + DB code directly on the event loop, "
        "blocking all concurrent async I/O during inference "
        "(potentially seconds per request). No asyncio.to_thread() "
        "or run_in_executor() usage was found."
    )

    pdf.subsection_title("3.3 No Rate Limiting")
    pdf.body_text(
        "No rate limiting middleware exists. CPU-expensive "
        "classification endpoints (/photo/classify, /audio/classify) "
        "are completely unprotected. Auth endpoints (/login, "
        "/register) are vulnerable to brute-force. No slowapi, "
        "no custom throttling, no per-IP limits."
    )

    pdf.subsection_title("3.4 Unbounded Response Sizes")
    pdf.metric_table(
        ["Endpoint", "Max Rows", "Est. Size", "Paginated?"],
        [
            ["GET /macro/overview", "14,176", "~5 MB", "No"],
            ["GET /risk/zones", "5,000", "~250 KB", "Yes"],
            ["GET /zones/mpas", "926 polys", "~20 MB", "Bbox only"],
            ["GET /contours/bathymetry", "1 blob", "~10 MB", "Cached"],
        ],
        [60, 40, 40, 50],
    )

    pdf.subsection_title("3.5 Connection Pool")
    pdf.body_text(
        "ThreadedConnectionPool: 4-50 connections with "
        "exponential-backoff retry (5 attempts, 50ms base). "
        "Adequate for dev. time.sleep() in retry blocks "
        "a worker thread, compounding under pool exhaustion."
    )

    # ── Frontend ──────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("4. Frontend Scalability")

    pdf.subsection_title("4.1 Strengths")
    strengths = [
        (
            "Dual-resolution map: macro heatmap (H3 res-4, "
            "~14K cells) at overview zoom, detail hexes (res-7) "
            "when zoomed in."
        ),
        ("AbortControllers on both map hooks: stale requests cancelled properly."),
        ("Bbox snapping (0.01 deg rounding) prevents sub-pixel refetch storms."),
        ("Viewport tiling with bounded concurrency (4 simultaneous tile requests)."),
        (
            "Dynamic imports for MapView, classifiers, events "
            "panel -- good code splitting."
        ),
    ]
    for s in strengths:
        pdf.bullet(s)

    pdf.subsection_title("4.2 Concerns")

    pdf.severity_badge(
        "200K cell cache cap = ~160 MB JS heap at capacity",
        "HIGH",
    )
    pdf.severity_badge(
        "No data-fetching library (SWR/React Query) -- "
        "no dedup, no stale-while-revalidate",
        "MEDIUM",
    )
    pdf.severity_badge(
        "Macro cache never evicted -- grows unbounded exploring projection combos",
        "MEDIUM",
    )
    pdf.severity_badge(
        "Three.js ~300KB for landing page only, not tree-shakeable (import *)",
        "MEDIUM",
    )
    pdf.severity_badge(
        "GeoJSON overlays re-fetched on every ~1 deg pan",
        "MEDIUM",
    )
    pdf.severity_badge(
        "Single useMemo for all 12 deck.gl layers -- any toggle rebuilds all",
        "LOW",
    )

    # ── Infrastructure ────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("5. Infrastructure & Pipeline")

    pdf.subsection_title("5.1 Docker PostgreSQL")
    pdf.callout_box(
        "CRITICAL",
        "No shm_size set (Docker default: 64 MB). This forced "
        "disabling parallel query workers entirely "
        "(max_parallel_workers_per_gather = 0), meaning every "
        "query is single-threaded -- including building the "
        "58M-row projection mart. Missing: shared_buffers, "
        "effective_cache_size, maintenance_work_mem.",
        ReportPDF.ACCENT_RED,
    )

    pdf.subsection_title("5.2 Full-Refresh dbt Models")
    pdf.body_text(
        "Every dbt build drops and recreates all 25 tables from "
        "scratch. The 58M-row fct_collision_risk_ml_projected "
        "alone takes 15-30 minutes. A full build is estimated "
        "at 30-60 minutes. No incremental models, no "
        "partitioning, no CLUSTER directives."
    )

    pdf.subsection_title("5.3 Bulk Loading")
    pdf.body_text(
        "All data loading uses psycopg2 execute_values (not "
        "PostgreSQL COPY). For the 9.7M-row AIS table, this is "
        "2-5x slower than COPY. The cetacean loading path uses "
        "df.iterrows() -- the slowest pandas iteration pattern. "
        "The AIS load reads the entire 9.7M x 75-column parquet "
        "into a single pandas DataFrame (~5-10 GB RAM)."
    )

    pdf.subsection_title("5.4 Dagster Orchestration")
    pdf.body_text(
        "No multiprocess_executor configured. All 90 assets run "
        "in a single process, sequentially. Independent branches "
        "cannot execute in parallel."
    )

    pdf.subsection_title("5.5 Data Growth Projections")
    pdf.metric_table(
        ["Dataset", "Current", "+1 Year AIS", "+2 Years AIS"],
        [
            ["ais_h3_summary", "9.7M", "~20M", "~30M"],
            ["int_hex_grid", "1.9M", "~2.5M", "~3M"],
            ["Seasonal marts (x4)", "7.3M", "~10M", "~12M"],
            ["Projected mart (x32)", "58M", "~80M", "~96M"],
            ["OBIS sightings", "~1M", "~1.1M", "~1.2M"],
            ["User submissions", "~100s", "10K-100K", "100K+"],
        ],
        [55, 45, 45, 45],
    )

    # ── Priority Actions ──────────────────────────────────────
    pdf.add_page()
    pdf.section_title("6. Priority Actions")
    pdf.body_text(
        "Ranked by impact vs effort. Items 1-6 and 9-10 are "
        "low effort and can be implemented immediately."
    )

    actions = [
        (
            "1",
            "LOW",
            "CRITICAL",
            "Add (cell_lat, cell_lon) B-tree indexes",
            "dbt config blocks on all mart + grid tables. "
            "Eliminates seq scans on every API call.",
        ),
        (
            "2",
            "LOW",
            "CRITICAL",
            "Docker shm_size + persist PG tuning",
            "Add shm_size: 2g, shared_buffers, "
            "effective_cache_size to docker-compose.yml.",
        ),
        (
            "3",
            "LOW",
            "HIGH",
            "Cache macro overview with TTL",
            "In-memory TTL cache in macro service. "
            "Eliminates the most expensive repeated query.",
        ),
        (
            "4",
            "LOW",
            "HIGH",
            "Add gzip middleware to FastAPI",
            "GZipMiddleware with min_size=1000. "
            "5-10x reduction on large JSON responses.",
        ),
        (
            "5",
            "LOW",
            "HIGH",
            "Fix async handlers blocking event loop",
            "Change async def to def on photo/audio/sighting "
            "routes so FastAPI offloads to thread pool.",
        ),
        (
            "6",
            "LOW",
            "MEDIUM",
            "Add rate limiting middleware",
            "slowapi on /auth/login, /auth/register, /photo/classify, /audio/classify.",
        ),
        (
            "7",
            "MED",
            "HIGH",
            "Convert projected mart to incremental",
            "dbt incremental on (scenario, decade). Avoids 30-min full rebuild.",
        ),
        (
            "8",
            "MED",
            "HIGH",
            "Replace execute_values with COPY",
            "PostgreSQL COPY FROM STDIN for bulk loads > 100K rows. 2-5x faster.",
        ),
        (
            "9",
            "LOW",
            "MEDIUM",
            "Add Dagster multiprocess executor",
            "multiprocess_executor with max_concurrent=4. "
            "Parallelise independent asset branches.",
        ),
        (
            "10",
            "LOW",
            "MEDIUM",
            "Add h3_cell indexes to intermediates",
            "dbt config blocks on 7 intermediate tables missing h3_cell indexes.",
        ),
    ]

    pdf.metric_table(
        ["#", "Effort", "Severity", "Action", "Detail"],
        [[a[0], a[1], a[2], a[3], a[4]] for a in actions],
        [8, 14, 22, 60, 86],
    )

    # ── What's Done Well ──────────────────────────────────────
    pdf.section_title("7. What's Done Well")
    done_well = [
        (
            "Dual-resolution map architecture (macro heatmap + "
            "detail hexes) is excellent."
        ),
        "GiST spatial indexes on all mart geometry columns.",
        "Bounded tile concurrency (4) protects backend pool.",
        "AbortControllers prevent stale fetch accumulation.",
        "Dynamic imports for heavy pages (map, classify, events).",
        "Server-side pagination on all list endpoints.",
        ("dbt config indexes on key marts (h3_cell, risk_score, geom)."),
        "Macro overview pre-aggregation (H3 res-4) is the right pattern.",
        "Exponential backoff retry on DB pool exhaustion.",
        ("Code splitting separates map/classify/events from initial bundle."),
    ]
    for d in done_well:
        pdf.bullet(d)

    # ── Save ──────────────────────────────────────────────────
    pdf.output(str(OUTPUT_FILE))
    print(f"Report saved to {OUTPUT_FILE}")
    print(f"  Pages: {pdf.page_no()}")


if __name__ == "__main__":
    build_report()

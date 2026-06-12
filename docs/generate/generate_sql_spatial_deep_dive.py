"""Generate a styled PDF: SQL, Indexing & Spatial Data Deep Dive.

Covers:
  - How tables and sequential scans work
  - B-tree indexes and when they help
  - JOIN algorithms (nested loop, hash, merge)
  - CTEs: what they are and their limitations
  - GiST indexes and R-trees for spatial data
  - PostGIS spatial joins and when they shine
  - Why Python KDTree beats PostGIS for unindexed KNN
  - Decision framework: when to use SQL vs Python
  - Project-specific examples and performance data

Run with:
    uv run python docs/generate_sql_spatial_deep_dive.py
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
                "Marine Risk Mapping - SQL, Indexing & Spatial Deep Dive",
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

    def code_block(self, code):
        """Draw a monospaced code block with grey background."""
        y = self.get_y()
        if y > 248:
            self.add_page()

        lines = code.strip().split("\n")
        block_h = len(lines) * 4.5 + 6

        self.set_fill_color(245, 245, 245)
        self.rect(14, self.get_y(), 182, block_h, style="F")
        self.set_draw_color(200, 200, 200)
        self.rect(14, self.get_y(), 182, block_h, style="D")

        y_start = self.get_y() + 3
        for i, line in enumerate(lines):
            self.set_xy(18, y_start + i * 4.5)
            self.set_font("Courier", "", 8)
            self.set_text_color(*self.DARK_TEXT)
            self.cell(174, 4.5, line)

        self.set_y(self.get_y() + block_h + 3)

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

    def comparison_card(self, title, without, with_idx, colour):
        """Draw a before/after comparison card."""
        y_start = self.get_y()
        if y_start > 225:
            self.add_page()
            y_start = self.get_y()

        n_lines = (len(without) + len(with_idx)) // 75 + 4
        card_h = max(34, 16 + n_lines * 4.5)

        self.set_fill_color(*self.LIGHT_BG)
        self.rect(10, y_start, 190, card_h, style="F")
        self.set_fill_color(*colour)
        self.rect(10, y_start, 3, card_h, style="F")

        # Title
        self.set_xy(16, y_start + 3)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.NAVY)
        self.cell(180, 5, title)

        # Without
        self.set_xy(16, y_start + 10)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.ACCENT_RED)
        self.cell(30, 5, "Without: ")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(150, 4.5, without)

        # With
        y_mid = self.get_y() + 1
        self.set_xy(16, y_mid)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.ACCENT_GREEN)
        self.cell(30, 5, "With: ")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(150, 4.5, with_idx)

        self.set_y(y_start + card_h + 3)

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
        for w, h in zip(col_widths, headers):
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
                for w, h in zip(col_widths, headers):
                    self.cell(w, 7, h, border=1, fill=True, align="C")
                self.ln()
                self.set_font("Helvetica", "", 8)

            fill = i % 2 == 0
            if fill:
                self.set_fill_color(*self.LIGHT_BG)
            self.set_text_color(*self.DARK_TEXT)
            for w, val in zip(col_widths, row):
                self.cell(w, 6, val, border=1, fill=fill)
            self.ln()
        self.ln(3)


# ── REPORT CONTENT ──────────────────────────────────────


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
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.cell(
        0,
        14,
        "SQL, Indexing & Spatial Data",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "A Deep Dive into Database Performance for Geospatial Pipelines",
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

    # ── Cover stats ─────────────────────────────────
    stats = [
        ("9.7M", "H3 Summary Rows"),
        ("~300K", "Unique Hex Cells"),
        ("843", "MPA Polygons"),
        ("5", "Index Types Used"),
    ]
    box_w = 42
    gap = 4
    total_w = len(stats) * box_w + (len(stats) - 1) * gap
    x_start = (210 - total_w) / 2

    for i, (big, label) in enumerate(stats):
        x = x_start + i * (box_w + gap)
        pdf.set_fill_color(*ReportPDF.LIGHT_BG)
        pdf.rect(x, pdf.get_y(), box_w, 22, style="F")
        pdf.set_xy(x, pdf.get_y() + 2)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*ReportPDF.TEAL)
        pdf.cell(box_w, 10, big, align="C")
        pdf.set_xy(x, pdf.get_y() + 10)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*ReportPDF.MID_TEXT)
        pdf.cell(box_w, 8, label, align="C")

    pdf.ln(30)

    # ── Table of contents ───────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(0, 10, "Contents", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    toc = [
        "1.  Tables & Sequential Scans",
        "2.  B-Tree Indexes",
        "3.  How JOINs Work Under the Hood",
        "4.  Common Table Expressions (CTEs)",
        "5.  GiST Indexes & R-Trees",
        "6.  PostGIS Spatial Joins",
        "7.  The CTE Index Problem (Cetacean Case Study)",
        "8.  Python KDTree vs PostGIS KNN",
        "9.  Raster Sampling: Why Python, Not SQL",
        "10. Decision Framework: SQL vs Python",
        "11. Project Index Inventory",
    ]
    for item in toc:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*ReportPDF.DARK_TEXT)
        pdf.cell(0, 6, item, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ══════════════════════════════════════════════════
    # SECTION 1: Tables & Sequential Scans
    # ══════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("1. Tables & Sequential Scans")

    pdf.body_text(
        "A PostgreSQL table is a collection of rows stored on disk in "
        "heap files. Each row occupies a slot in an 8 KB page. When "
        "you run a query like:"
    )

    pdf.code_block("SELECT * FROM ais_h3_summary\nWHERE h3_cell = 612496793058115583;")

    pdf.body_text(
        "Without any optimisation, Postgres performs a sequential scan: "
        "it reads every single page from disk, examines every row, and "
        "checks the WHERE condition. For the 9.7 million row AIS summary "
        "table, that means reading all 9.7M rows to find matches for one "
        "cell."
    )

    pdf.body_text(
        "This is O(n) - linear time. It scales directly with table size. "
        "For 100 rows it takes microseconds. For 9.7 million rows it can "
        "take 8-10 seconds depending on disk speed and caching."
    )

    pdf.callout_box(
        "Key Concept: Sequential Scan",
        "A sequential scan (Seq Scan in EXPLAIN output) reads every row "
        "in the table from first to last. It is the only option when "
        "Postgres has no index to narrow down which rows match the query. "
        "It is perfectly fine for small tables or queries that need most "
        "rows (e.g. full aggregations).",
        ReportPDF.ACCENT_BLUE,
    )

    pdf.body_text(
        "You can see what Postgres plans to do by prefixing any query "
        "with EXPLAIN ANALYZE. It will show the scan strategy, estimated "
        "row counts, and actual execution times. This is the single most "
        "useful debugging tool for slow queries."
    )

    # ══════════════════════════════════════════════════
    # SECTION 2: B-Tree Indexes
    # ══════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("2. B-Tree Indexes")

    pdf.body_text(
        "An index is a separate, sorted data structure stored alongside "
        "the table that maps column values to the physical locations of "
        "matching rows. Think of a phone book: instead of reading every "
        "page to find 'Hall', you jump to 'H' and narrow down."
    )

    pdf.subsection_title("How B-Trees Work")

    pdf.body_text(
        "The default index type in PostgreSQL is a B-tree (balanced tree). "
        "When you create one:"
    )

    pdf.code_block("CREATE INDEX idx_ais_cell\n    ON ais_h3_summary (h3_cell);")

    pdf.body_text(
        "Postgres builds a tree structure where each internal node "
        "contains sorted key values and pointers to child nodes. The "
        "leaf nodes contain the actual key values paired with pointers "
        "(TIDs) to the corresponding rows in the heap. The tree is "
        "balanced, meaning every leaf is at the same depth - typically "
        "3-4 levels for millions of rows."
    )

    pdf.body_text(
        "To find h3_cell = 612496793058115583, Postgres starts at the "
        "root, follows the correct child pointer at each level, and "
        "arrives at the leaf containing that key in just 3-4 page reads. "
        "This is O(log n) - logarithmic time."
    )

    pdf.simple_table(
        ["Operation", "Without Index", "With B-Tree"],
        [
            [
                "Find one cell in 9.7M rows",
                "Scan 9.7M rows (~8 sec)",
                "~4 page reads (~0.1 ms)",
            ],
            ["Complexity", "O(n) - linear", "O(log n) - logarithmic"],
            ["Range scan (month = Jan)", "Scan all rows", "Jump to start, scan range"],
            [
                "Full aggregation (SUM)",
                "Seq scan (fine)",
                "Seq scan (index not useful)",
            ],
        ],
        col_widths=[48, 66, 76],
    )

    pdf.callout_box(
        "When Indexes Do NOT Help",
        "Indexes only accelerate queries whose WHERE, JOIN ON, or "
        "ORDER BY clauses reference the indexed column(s). A query that "
        "aggregates all rows (SELECT SUM(transits) FROM ais_h3_summary) "
        "still does a sequential scan because it needs every row anyway. "
        "Postgres may also ignore an index if it estimates the query will "
        "return a large fraction of the table (>5-10%), since random I/O "
        "from index lookups can be slower than a single sequential pass.",
        ReportPDF.ACCENT_AMBER,
    )

    pdf.subsection_title("Project Example: AIS Summary Indexes")

    pdf.body_text(
        "In aggregate_ais.py, after writing the ais_h3_summary table, "
        "we create three B-tree indexes:"
    )

    pdf.code_block(
        "CREATE INDEX idx_ais_h3_cell\n"
        "    ON ais_h3_summary (h3_cell);\n"
        "\n"
        "CREATE INDEX idx_ais_h3_month\n"
        "    ON ais_h3_summary (month);\n"
        "\n"
        "CREATE INDEX idx_ais_h3_cell_month\n"
        "    ON ais_h3_summary (h3_cell, month);"
    )

    pdf.body_text(
        "The third is a composite index on (h3_cell, month). This is "
        "particularly useful for the fct_monthly_traffic mart which "
        "queries by both columns. Postgres can satisfy the query by "
        "reading only the index pages - it never touches the table "
        "heap at all. This is called an index-only scan."
    )

    # ══════════════════════════════════════════════════
    # SECTION 3: How JOINs Work
    # ══════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("3. How JOINs Work Under the Hood")

    pdf.body_text(
        "A JOIN combines rows from two (or more) tables based on a "
        "matching condition. The SQL syntax is simple, but under the "
        "hood Postgres must choose a physical algorithm to execute it. "
        "There are three main strategies."
    )

    pdf.subsection_title("3a. Nested Loop Join")

    pdf.body_text(
        "The simplest approach. For each row in Table A, scan Table B "
        "to find matches. Pseudocode:"
    )

    pdf.code_block(
        "for each row_a in Table A:         -- 'outer' table\n"
        "    for each row_b in Table B:     -- 'inner' table\n"
        "        if row_a.key == row_b.key:\n"
        "            emit (row_a, row_b)"
    )

    pdf.body_text(
        "Without an index, this is O(n x m). For two tables of 300K rows "
        "each, that is 90 billion comparisons - disastrous. But if Table B "
        "has a B-tree index on the join key, the inner loop becomes an "
        "index lookup: O(log m) per outer row. The total becomes "
        "O(n x log m), which is fast."
    )

    pdf.callout_box(
        "When Postgres Picks Nested Loop",
        "Nested loop is preferred when the outer table is small (or has "
        "been filtered down) and the inner table has an index on the join "
        "key. It is also the ONLY algorithm that can execute spatial joins "
        "with GiST indexes, because hash and merge joins only work with "
        "equality (=) operators, not geometric predicates like "
        "ST_Intersects.",
        ReportPDF.ACCENT_BLUE,
    )

    pdf.subsection_title("3b. Hash Join")

    pdf.body_text(
        "Postgres builds a hash table from the smaller table, then "
        "scans the larger table and probes the hash for each row:"
    )

    pdf.code_block(
        "-- Phase 1: Build\n"
        "hash_map = {}\n"
        "for row_b in smaller_table:\n"
        "    hash_map[row_b.key].append(row_b)\n"
        "\n"
        "-- Phase 2: Probe\n"
        "for row_a in larger_table:\n"
        "    if row_a.key in hash_map:\n"
        "        for match in hash_map[row_a.key]:\n"
        "            emit (row_a, match)"
    )

    pdf.body_text(
        "This is O(n + m) - it reads each table exactly once. No index "
        "needed. The only requirement is that the hash table fits in "
        "work_mem (default 4 MB in Postgres). If it does not fit, Postgres "
        "spills batches to disk, which is slower but still much better "
        "than nested loop without an index."
    )

    pdf.callout_box(
        "Project Usage: fct_collision_risk.sql",
        "When fct_collision_risk joins six intermediate tables on "
        "h3_cell (an integer equality join), Postgres almost certainly "
        "uses hash joins. Each intermediate table is materialized as a "
        "dbt table. The planner builds a hash map from each smaller table "
        "and probes it with the larger feature set. This is why six "
        "LEFT JOINs on integer keys run in seconds, not minutes.",
        ReportPDF.ACCENT_GREEN,
    )

    pdf.subsection_title("3c. Merge Join")

    pdf.body_text(
        "Both tables are sorted by the join key, then walked through "
        "in parallel like a zipper:"
    )

    pdf.code_block(
        "sort Table A by key    -- O(n log n)\n"
        "sort Table B by key    -- O(m log m)\n"
        "\n"
        "pointer_a = first row of A\n"
        "pointer_b = first row of B\n"
        "while both have rows:\n"
        "    if a.key == b.key: emit match, advance both\n"
        "    elif a.key < b.key: advance a\n"
        "    else: advance b"
    )

    pdf.body_text(
        "Total cost: O(n log n + m log m) for sorting, then O(n + m) "
        "for the merge pass. Postgres picks this when both inputs are "
        "already sorted (e.g., from a B-tree index scan) so the sort "
        "step is free."
    )

    pdf.simple_table(
        ["Algorithm", "Complexity", "Index Needed?", "Best When"],
        [
            [
                "Nested Loop",
                "O(n x m) or O(n log m)",
                "Helps inner table",
                "Small outer, indexed inner",
            ],
            ["Hash Join", "O(n + m)", "No", "Medium/large tables, equality joins"],
            [
                "Merge Join",
                "O(n log n + m log m)",
                "Optional (free sort)",
                "Both sides pre-sorted",
            ],
        ],
        col_widths=[32, 42, 38, 78],
    )

    # ══════════════════════════════════════════════════
    # SECTION 4: CTEs
    # ══════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("4. Common Table Expressions (CTEs)")

    pdf.body_text(
        "A Common Table Expression is a named, temporary result set "
        "defined within a WITH block. It makes complex queries readable "
        "by breaking them into logical steps:"
    )

    pdf.code_block(
        "WITH traffic_agg AS (\n"
        "    SELECT h3_cell, SUM(total_transits) AS total_transits\n"
        "    FROM int_vessel_traffic\n"
        "    GROUP BY h3_cell\n"
        ")\n"
        "SELECT * FROM traffic_agg WHERE total_transits > 100;"
    )

    pdf.subsection_title("How CTEs Execute")

    pdf.body_text(
        "In PostgreSQL 11 and earlier, CTEs were 'optimisation fences'. "
        "Postgres materialised them into temporary result sets and could "
        "not push filters, joins, or index access into them. The CTE was "
        "computed in full first, stored in memory (or temp files), then "
        "the outer query ran against that intermediate result."
    )

    pdf.body_text(
        "Starting with PostgreSQL 12+, CTEs are inlined by default - "
        "the planner merges them into the main query and optimises "
        "globally. This means filters can be pushed down and indexes "
        "can be used. However, a CTE is still materialised (not inlined) "
        "if it is referenced more than once, or if you explicitly write "
        "WITH ... AS MATERIALIZED (...)."
    )

    pdf.callout_box(
        "The Critical Limitation: CTEs Have No Indexes",
        "Even when inlined, a CTE result set is just rows flowing "
        "through the query plan. It has no B-tree, no GiST, no index "
        "of any kind. If a downstream operation needs an index-based "
        "lookup (like GiST KNN nearest-neighbour), it cannot get one "
        "from a CTE. This is the core reason we moved spatial operations "
        "to Python for the cetacean and proximity computations.",
        ReportPDF.ACCENT_RED,
    )

    pdf.subsection_title("dbt and CTEs")

    pdf.body_text(
        "dbt compiles Jinja SQL into pure SQL, and the ref() function "
        "resolves to either a CTE (ephemeral materialisation) or a "
        "table/view reference. In our project, intermediate models are "
        "materialised as tables. This means when fct_collision_risk "
        "references ref('int_vessel_traffic'), it resolves to a real "
        "table with real indexes - not a CTE. This distinction is why "
        "the materialisation strategy matters for performance."
    )

    # ══════════════════════════════════════════════════
    # SECTION 5: GiST Indexes & R-Trees
    # ══════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("5. GiST Indexes & R-Trees")

    pdf.body_text(
        "B-trees work for one-dimensional data: numbers, strings, dates. "
        "They rely on a total ordering (you can sort all values into a "
        "single line). But geometry is two-dimensional - you cannot "
        "meaningfully sort a set of points or polygons into a single "
        "sequence. This is where GiST comes in."
    )

    pdf.subsection_title("What GiST Stands For")

    pdf.body_text(
        "GiST = Generalized Search Tree. It is a PostgreSQL index type "
        "that supports multiple data types and operators beyond simple "
        "equality and ordering. For PostGIS geometry columns, GiST "
        "builds an R-tree internally - a tree of nested bounding boxes."
    )

    pdf.subsection_title("How R-Trees Work")

    pdf.body_text(
        "An R-tree organises spatial objects into a hierarchy of "
        "bounding rectangles. At the top level, the root node holds "
        "a bounding box that encloses ALL objects. Each child node "
        "holds a smaller bounding box covering a region of space. "
        "Leaf nodes contain the actual geometry bounding boxes and "
        "pointers to the table rows."
    )

    pdf.code_block(
        "             [World bounding box]\n"
        "            /                     \\\n"
        "    [North Atlantic]         [South Pacific]\n"
        "    /            \\             /           \\\n"
        "[US East Coast] [UK]   [NZ Coast]   [Chile]\n"
        "  /     \\\n"
        "[MPA A] [MPA B]"
    )

    pdf.body_text(
        "To answer 'which MPA polygon contains this point?', Postgres "
        "starts at the root and asks: does this point's coordinates "
        "fall within the left child's bounding box, the right child's, "
        "or both? It descends only into branches whose bounding box "
        "could contain the point, pruning the rest. At each level it "
        "eliminates a large fraction of candidates."
    )

    pdf.body_text(
        "For our 843 MPA polygons, the R-tree has about 3-4 levels. "
        "A point lookup touches ~4 nodes, then does an exact geometry "
        "test on 0-2 candidate polygons. Compare this to checking all "
        "843 polygons sequentially."
    )

    pdf.subsection_title("Creating a GiST Index")

    pdf.code_block(
        "CREATE INDEX idx_mpa_geom\n    ON marine_protected_areas USING GIST (geom);"
    )

    pdf.body_text(
        "The USING GIST clause tells Postgres to build a GiST index "
        "instead of the default B-tree. This index supports two key "
        "classes of spatial operations:"
    )

    pdf.simple_table(
        ["Operation Type", "SQL Operators", "How GiST Helps"],
        [
            [
                "Containment/Overlap",
                "ST_Contains, ST_Intersects, ST_Within, &&",
                "R-tree prunes by bounding-box overlap",
            ],
            [
                "Nearest Neighbour (KNN)",
                "<-> distance operator with ORDER BY ... LIMIT k",
                "Traverses tree by distance, prunes far branches",
            ],
        ],
        col_widths=[40, 70, 80],
    )

    pdf.callout_box(
        "GiST KNN Requirement",
        "The <-> nearest-neighbour operator ONLY uses the GiST index "
        "when applied to a column of a persistent, indexed table. If "
        "the geometry comes from a CTE, subquery, or function result, "
        "there is no GiST to traverse. Postgres falls back to computing "
        "the distance to every row and sorting - O(n) per query instead "
        "of O(log n).",
        ReportPDF.ACCENT_RED,
    )

    # ══════════════════════════════════════════════════
    # SECTION 6: PostGIS Spatial Joins
    # ══════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("6. PostGIS Spatial Joins")

    pdf.body_text(
        "A spatial join matches rows from two tables based on a "
        "geometric relationship (intersection, containment, proximity) "
        "rather than key equality. This is fundamentally different from "
        "a regular JOIN ... ON a.id = b.id."
    )

    pdf.subsection_title("How a GiST Spatial Join Works")

    pdf.body_text("Consider our MPA overlay in int_mpa_coverage.sql:")

    pdf.code_block(
        "SELECT g.h3_cell, m.site_name, m.iucn_category\n"
        "FROM int_hex_grid g\n"
        "LEFT JOIN stg_marine_protected_areas m\n"
        "    ON ST_Intersects(g.geom, m.geom);"
    )

    pdf.body_text(
        "Under the hood, Postgres executes this as a nested loop with GiST index scan:"
    )

    pdf.body_text(
        "1. For each row in int_hex_grid (the outer table, ~300K cells), "
        "take the cell's geometry."
    )
    pdf.body_text(
        "2. Query the GiST index on marine_protected_areas.geom: which "
        "MPA bounding boxes overlap this cell? The R-tree returns 0-2 "
        "candidates in O(log 843) ~ 3 node lookups."
    )
    pdf.body_text(
        "3. For each candidate, do an exact ST_Intersects test (precise "
        "polygon-polygon math, not just bounding boxes). This filters "
        "out false positives from the bounding box check."
    )
    pdf.body_text("4. Emit the matched rows.")

    pdf.body_text(
        "Total work: 300K cells x O(log 843) index lookups x ~1-2 "
        "exact geometry tests = roughly 1 million operations. This is "
        "why the MPA overlay runs in about 12 seconds."
    )

    pdf.comparison_card(
        "MPA Overlay Performance",
        "Without GiST on MPAs: 300K cells x 843 polygons = 253 million "
        "ST_Intersects calls. Estimated time: 30+ minutes.",
        "With GiST on MPAs: 300K cells x ~3 index lookups x ~1.5 exact "
        "tests = ~1.4M operations. Actual time: ~12 seconds.",
        ReportPDF.ACCENT_GREEN,
    )

    pdf.callout_box(
        "Why This Works So Well",
        "The MPA spatial join is the ideal case for PostGIS: a large set "
        "of points (hex cell centroids) checked against a modest set of "
        "indexed polygons (843 MPAs). The GiST on the polygon table "
        "does all the heavy lifting. The points do not need their own "
        "GiST because they are the outer loop - Postgres reads them "
        "sequentially and probes the polygon index for each one.",
        ReportPDF.ACCENT_BLUE,
    )

    # ══════════════════════════════════════════════════
    # SECTION 7: The CTE Index Problem (Cetacean Case Study)
    # ══════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("7. The CTE Index Problem")

    pdf.subsection_title("The Original Approach (59 Minutes)")

    pdf.body_text(
        "The first attempt at assigning cetacean sightings to H3 cells "
        "was a pure SQL spatial join inside a dbt model. The approach "
        "was conceptually identical to the MPA overlay - but performed "
        "catastrophically differently."
    )

    pdf.body_text("The query structure looked approximately like this:")

    pdf.code_block(
        "SELECT g.h3_cell, s.id, s.species\n"
        "FROM int_hex_grid g\n"
        "JOIN cetacean_sightings s\n"
        "    ON ST_Contains(g.geom, s.geom);"
    )

    pdf.body_text(
        "On the surface, this looks just like the MPA join. But there "
        "is a critical difference in the data shapes:"
    )

    pdf.simple_table(
        ["", "MPA Overlay", "Cetacean Assignment"],
        [
            ["Outer table (grid)", "~300K cells", "~300K cells"],
            ["Inner table", "843 MPA polygons", "~250K sighting points"],
            ["GiST on inner?", "YES (create_schema.py)", "YES (on sightings)"],
            ["GiST on outer (grid)?", "Not needed (outer loop)", "NOT AVAILABLE"],
            ["Geometry types", "Point vs Polygon", "Polygon vs Point"],
        ],
        col_widths=[40, 55, 55],
    )

    pdf.subsection_title("Why It Was Slow: The Direction Problem")

    pdf.body_text(
        "The MPA overlay asks: for each cell point, which polygon "
        "contains it? The GiST is on the polygons (inner table), "
        "and probing it is fast."
    )

    pdf.body_text(
        "The cetacean query asks: for each hex polygon (from "
        "int_hex_grid), which sighting points fall inside it? Now the "
        "hex grid is the outer table. Even though cetacean_sightings "
        "has a GiST on its point geometry, the query optimizer needs "
        "to check 'which points are inside this polygon' for each of "
        "300K hex polygons."
    )

    pdf.body_text(
        "The key issue: int_hex_grid was a dbt-materialised table, "
        "but it had NO GiST index on its geometry column. Without it, "
        "the planner could not efficiently flip the join direction. "
        "The result: Postgres fell back to checking a huge number of "
        "candidate pairs, leading to ~59 minute runtimes."
    )

    pdf.callout_box(
        "Could a GiST on int_hex_grid Have Fixed It?",
        "YES. Adding a GiST index to int_hex_grid.geom would have "
        "allowed Postgres to flip the join: for each sighting point, "
        "probe the hex grid R-tree to find which hex polygon contains "
        "it. That would be: 250K sightings x O(log 300K) = ~4.5M "
        "operations. Estimated time: 30-90 seconds instead of 59 "
        "minutes. The fix in dbt config would have been: "
        "indexes=[{'columns': ['geom'], 'type': 'gist'}]",
        ReportPDF.ACCENT_AMBER,
    )

    pdf.subsection_title("Why We Chose Python H3 Instead")

    pdf.body_text(
        "Even though adding a GiST index would have reduced the spatial "
        "join from 59 minutes to ~1 minute, we chose a fundamentally "
        "different approach: pre-computing the H3 cell assignment in "
        "Python using the h3 library."
    )

    pdf.body_text(
        "The h3.latlng_to_cell(lat, lon, resolution) function takes "
        "a latitude and longitude and computes - via pure arithmetic "
        "on the H3 hexagonal grid spec - which cell it belongs to. "
        "This is O(1) per point: no geometry, no polygon containment "
        "test, no spatial index. Just math."
    )

    pdf.simple_table(
        ["Approach", "Complexity", "Operations", "Est. Time"],
        [
            ["SQL spatial join (no GiST)", "O(n x m)", "75 billion", "~59 minutes"],
            [
                "SQL spatial join (with GiST)",
                "O(n x log m)",
                "~4.5 million",
                "~30-90 seconds",
            ],
            ["Python h3.latlng_to_cell()", "O(n)", "250K", "~2-3 seconds"],
        ],
        col_widths=[52, 38, 40, 60],
    )

    pdf.body_text(
        "The Python approach is 15-30x faster than even the indexed "
        "SQL version, and has zero infrastructure dependencies - no "
        "PostGIS, no indexes, no query planner decisions. It also "
        "means the dbt model (int_cetacean_density) becomes a simple "
        "GROUP BY on an integer column rather than a spatial join."
    )

    # ══════════════════════════════════════════════════
    # SECTION 8: Python KDTree vs PostGIS KNN
    # ══════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("8. Python KDTree vs PostGIS KNN")

    pdf.body_text(
        "The proximity feature (compute_proximity.py) needs to answer: "
        "for each of ~300K hex cells, what is the distance to the "
        "nearest whale sighting and the nearest shipping cell? This is "
        "a nearest-neighbour (KNN) problem."
    )

    pdf.subsection_title("Option A: PostGIS KNN with <-> Operator")

    pdf.code_block(
        "SELECT g.h3_cell,\n"
        "    (SELECT ST_Distance(\n"
        "         g.geom::geography,\n"
        "         w.geom::geography\n"
        "     )\n"
        "     FROM cetacean_sighting_h3 w\n"
        "     ORDER BY g.geom <-> w.geom\n"
        "     LIMIT 1\n"
        "    ) AS whale_dist_m\n"
        "FROM hex_grid g;"
    )

    pdf.body_text(
        "The <-> operator computes distance and, when used with "
        "ORDER BY ... LIMIT k, triggers a GiST index-based KNN scan. "
        "But there are two problems in our context:"
    )

    pdf.body_text(
        "1. The cetacean_sighting_h3 table stores h3_cell as BIGINT, "
        "not as a geometry column. We would need to either add a "
        "geometry column or compute it on the fly - which creates an "
        "unindexed expression."
    )

    pdf.body_text(
        "2. The hex_grid itself comes from a dbt model. If it is "
        "referenced as a CTE or subquery in a more complex query, "
        "neither side has a usable GiST. The <-> operator falls back "
        "to computing distance to every row: O(n) per lookup, "
        "O(n x m) total = 300K x 50K = 15 billion distance calculations."
    )

    pdf.subsection_title("Option B: scipy cKDTree (What We Used)")

    pdf.body_text(
        "A KD-tree (k-dimensional tree) is a binary space-partitioning "
        "structure optimised for nearest-neighbour queries. The scipy "
        "implementation (cKDTree) is written in C and operates entirely "
        "in memory."
    )

    pdf.code_block(
        "from scipy.spatial import cKDTree\n"
        "\n"
        "# Build: O(m log m)\n"
        "tree = cKDTree(whale_xyz_coords)\n"
        "\n"
        "# Query ALL cells at once: O(n log m)\n"
        "distances, indices = tree.query(grid_xyz_coords)"
    )

    pdf.body_text(
        "The tree.query() call finds the nearest neighbour for every "
        "grid point in a single vectorised operation. Internally, it "
        "traverses the KD-tree for each query point, pruning branches "
        "that cannot contain a closer point than the current best."
    )

    pdf.simple_table(
        ["Step", "Complexity", "For Our Data"],
        [
            ["Build KD-tree from 50K whale cells", "O(m log m)", "50K x 17 = 850K ops"],
            ["Query 300K grid cells", "O(n log m)", "300K x 17 = 5.1M ops"],
            ["Total", "O((n+m) log m)", "~6M ops, <1 second"],
        ],
        col_widths=[65, 45, 80],
    )

    pdf.subsection_title("Why KDTree Wins Here")

    pdf.comparison_card(
        "Nearest-Neighbour: PostGIS vs KDTree",
        "PostGIS KNN requires a GiST index on a persistent table. "
        "Our whale and ship cell tables lack geometry columns / GiST. "
        "Without GiST: O(n x m) = 15 billion operations. Even with "
        "GiST: disk-backed, ACID overhead, ~30 seconds.",
        "scipy cKDTree: purpose-built for KNN. In-memory, zero disk "
        "I/O, no SQL overhead, no transaction management. Vectorised "
        "C implementation. Completes in <1 second for our data sizes.",
        ReportPDF.ACCENT_BLUE,
    )

    pdf.callout_box(
        "Haversine Distance",
        "Our compute_proximity.py converts lat/lon to 3D Cartesian "
        "coordinates (x, y, z on the unit sphere) before building the "
        "KD-tree. The Euclidean distance in 3D space approximates "
        "great-circle distance for points that are not antipodal. "
        "After getting the Euclidean nearest neighbour, we compute "
        "the exact haversine distance for the final km value. This "
        "gives accurate results without the computational cost of "
        "geodesic math on every candidate pair.",
        ReportPDF.ACCENT_GREEN,
    )

    # ══════════════════════════════════════════════════
    # SECTION 9: Raster Sampling
    # ══════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("9. Raster Sampling: Why Python, Not SQL")

    pdf.body_text(
        "Bathymetry data comes as a GeoTIFF raster (the GEBCO 2025 "
        "grid): a regular grid of depth values stored as pixels. Each "
        "pixel is a 15 arc-second cell (~450m) with a depth value in "
        "metres. Our file covers the study area and is 187 MB "
        "as int16."
    )

    pdf.subsection_title("The PostGIS Raster Option")

    pdf.body_text(
        "PostgreSQL has a raster extension (postgis_raster) that can "
        "load GeoTIFFs into the database and query them with SQL. "
        "The function ST_Value(raster, point) returns the pixel value "
        "at a given geometry. But this approach has serious drawbacks:"
    )

    pdf.body_text(
        "1. Loading: raster2pgsql imports the GeoTIFF as tiled chunks "
        "in a table. For a 187 MB raster, this creates thousands of "
        "tile rows with large binary columns."
    )

    pdf.body_text(
        "2. Querying: ST_Value on each of 300K cells x 7 sample points "
        "= 2.1M function calls, each requiring tile lookup, "
        "decompression, and pixel extraction. Without careful tiling "
        "and indexing, this is very slow."
    )

    pdf.body_text(
        "3. Complexity: The raster extension is poorly documented, "
        "being deprecated in newer PostGIS versions in favour of "
        "out-of-db raster processing."
    )

    pdf.subsection_title("The Python rasterio Approach (What We Used)")

    pdf.code_block(
        "import rasterio\n"
        "\n"
        "src = rasterio.open('gebco_2025.tif')\n"
        "band = src.read(1)  # Load entire band: 187 MB numpy array\n"
        "\n"
        "# For each sample point:\n"
        "row, col = src.index(lon, lat)  # O(1) coordinate transform\n"
        "depth = band[row, col]          # O(1) array indexing"
    )

    pdf.body_text(
        "The entire raster is loaded into a numpy array once. Each "
        "sample point is converted from geographic coordinates to pixel "
        "indices via an affine transform (simple multiplication), then "
        "the depth is a direct array index. Both operations are O(1)."
    )

    pdf.body_text(
        "For 300K cells x 7 points = 2.1M lookups, the total time is "
        "dominated by the Python loop overhead, not the actual lookups. "
        "Total runtime: ~15 seconds."
    )

    pdf.comparison_card(
        "Raster Sampling Performance",
        "PostGIS raster: Load GeoTIFF into database tiles, "
        "ST_Value() for each of 2.1M points with tile lookup and "
        "decompression overhead. Estimated: 5-15 minutes. Adds "
        "significant database storage.",
        "Python rasterio: Load 187 MB into numpy array once, O(1) "
        "array indexing per point. Total: ~15 seconds. No database "
        "storage needed - reads directly from the GeoTIFF file.",
        ReportPDF.ACCENT_GREEN,
    )

    pdf.callout_box(
        "Why Not Keep the Raster in the Database?",
        "The bathymetry raster is a static reference dataset that "
        "never changes (GEBCO is updated annually). There is no "
        "benefit to putting it in PostgreSQL - it adds storage "
        "overhead, complicates backups, and the query interface is "
        "slower than direct array access. The pattern of 'sample in "
        "Python, write results to a summary table' keeps the database "
        "lean and the pipeline fast.",
        ReportPDF.ACCENT_AMBER,
    )

    # ══════════════════════════════════════════════════
    # SECTION 10: Decision Framework
    # ══════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("10. Decision Framework: SQL vs Python")

    pdf.body_text(
        "The following framework captures how we chose whether to "
        "implement each operation in SQL (dbt/PostGIS) or Python "
        "across the entire pipeline. The guiding principle: use each "
        "tool for what it does best."
    )

    pdf.subsection_title("When to Use SQL / PostGIS")

    pdf.decision_card(
        1,
        "Equality Joins on Pre-Computed Keys",
        "When tables share a common integer key (h3_cell), SQL hash "
        "joins are O(n+m) and hard to beat. All six intermediate "
        "tables join on h3_cell in fct_collision_risk.sql using "
        "plain equality. No spatial operations needed.",
    )

    pdf.decision_card(
        2,
        "Spatial Joins Against Indexed Polygon Tables",
        "When you have a modest number of polygons (<10K) with a "
        "GiST index, ST_Intersects spatial joins are efficient. Our "
        "MPA overlay (843 indexed polygons x 300K cells) runs in "
        "~12 seconds. The R-tree eliminates >99% of candidates.",
    )

    pdf.decision_card(
        3,
        "Aggregation, Window Functions, and Ranking",
        "SQL excels at GROUP BY aggregations, PERCENT_RANK() window "
        "functions, and CASE expressions. These run on the full dataset "
        "in a single pass. The risk scoring in fct_collision_risk.sql "
        "percentile-ranks five features and computes weighted scores "
        "entirely in SQL.",
    )

    pdf.decision_card(
        4,
        "Declarative Transformations with dbt",
        "dbt's ref() system manages dependencies, materialisation, "
        "and testing. Pure SQL transforms benefit from dbt's DAG "
        "execution, incremental builds, and documentation generation. "
        "All intermediate and mart models are dbt SQL models.",
    )

    pdf.subsection_title("When to Use Python")

    pdf.decision_card(
        5,
        "H3 Cell Assignment (Deterministic Math)",
        "The h3 library computes cell membership as O(1) arithmetic. "
        "No geometry, no spatial index, no polygon containment test. "
        "250K sightings in 2-3 seconds vs 30-90 seconds even with an "
        "optimised spatial join. Pure Python wins decisively.",
    )

    pdf.decision_card(
        6,
        "Nearest-Neighbour on Unindexed Data",
        "When neither table has a GiST index on geometry (or the "
        "geometry does not exist as a column), PostGIS KNN degrades "
        "to O(n x m). scipy cKDTree provides O((n+m) log m) with "
        "in-memory, vectorised C implementation. Used for whale and "
        "ship proximity in compute_proximity.py.",
    )

    pdf.decision_card(
        7,
        "Raster I/O (GeoTIFF Sampling)",
        "SQL has no native GeoTIFF reader. PostGIS raster is slow, "
        "poorly documented, and being deprecated. Python rasterio "
        "loads the raster into a numpy array and does O(1) pixel "
        "lookups. Used for bathymetry in sample_bathymetry.py.",
    )

    pdf.decision_card(
        8,
        "Operations Requiring Libraries Not Available in SQL",
        "The DuckDB aggregation pipeline (3.1B AIS pings) uses "
        "DuckDB's H3 and spatial extensions for in-process OLAP. "
        "PostGIS cannot do columnar scans on 3.1B rows efficiently. "
        "OBIS data download uses DuckDB's remote parquet reader. "
        "These capabilities simply do not exist in PostgreSQL.",
    )

    # ══════════════════════════════════════════════════
    # SECTION 11: Project Index Inventory
    # ══════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("11. Project Index Inventory")

    pdf.body_text(
        "A complete catalogue of every index in the project, where "
        "it is created, and what it accelerates."
    )

    pdf.subsection_title("Source Table Indexes (create_schema.py)")

    pdf.body_text(
        "Created at schema initialisation, before any data is loaded. "
        "These indexes exist on the raw source tables and persist for "
        "the lifetime of the database."
    )

    pdf.simple_table(
        ["Index Name", "Table", "Type", "Purpose"],
        [
            [
                "idx_ais_geom",
                "ais_positions",
                "GiST",
                "Spatial queries on raw AIS points",
            ],
            [
                "idx_cetacean_geom",
                "cetacean_sightings",
                "GiST",
                "Spatial queries on raw sightings",
            ],
            [
                "idx_mpa_geom",
                "marine_protected_areas",
                "GiST",
                "MPA overlay spatial join in dbt",
            ],
            [
                "idx_ais_time",
                "ais_positions",
                "B-tree",
                "Time-range queries on AIS data",
            ],
            ["idx_ais_mmsi", "ais_positions", "B-tree", "Vessel-level lookups by MMSI"],
            [
                "idx_cetacean_species",
                "cetacean_sightings",
                "B-tree",
                "Species-level filtering",
            ],
        ],
        col_widths=[38, 45, 18, 89],
    )

    pdf.subsection_title("Python Script Indexes")

    pdf.body_text(
        "Created by aggregation scripts after writing summary tables. "
        "These support downstream dbt model joins."
    )

    pdf.simple_table(
        ["Index Name", "Table", "Type", "Created By"],
        [
            ["idx_ais_h3_cell", "ais_h3_summary", "B-tree", "aggregate_ais.py"],
            ["idx_ais_h3_month", "ais_h3_summary", "B-tree", "aggregate_ais.py"],
            [
                "idx_ais_h3_cell_month",
                "ais_h3_summary",
                "B-tree (composite)",
                "aggregate_ais.py",
            ],
            [
                "idx_cetacean_h3_cell",
                "cetacean_sighting_h3",
                "B-tree",
                "assign_cetacean_h3.py",
            ],
            [
                "idx_bathymetry_h3_cell",
                "bathymetry_h3",
                "B-tree",
                "sample_bathymetry.py",
            ],
        ],
        col_widths=[48, 42, 40, 60],
    )

    pdf.subsection_title("dbt Model Indexes")

    pdf.body_text(
        "Configured in dbt model config blocks. Created automatically "
        "by dbt after materialising each table."
    )

    pdf.simple_table(
        ["Model", "Index Column", "Type", "Supports"],
        [
            ["int_hex_grid", "geom", "GiST", "MPA spatial join (downstream)"],
            ["fct_collision_risk", "h3_cell", "B-tree", "Cell lookups from API"],
            ["fct_collision_risk", "risk_score", "B-tree", "Risk filtering queries"],
            ["fct_collision_risk", "geom", "GiST", "Map tile serving (bbox queries)"],
            ["fct_monthly_traffic", "h3_cell", "B-tree", "Cell-level time series"],
            ["fct_monthly_traffic", "month", "B-tree", "Month-range queries"],
            [
                "fct_monthly_traffic",
                "(h3_cell, month)",
                "B-tree (unique)",
                "Composite lookups",
            ],
        ],
        col_widths=[42, 38, 40, 70],
    )

    pdf.callout_box(
        "Index Strategy Summary",
        "GiST indexes are created only where spatial queries actually "
        "occur: raw source tables (for potential ad-hoc analysis) and "
        "the hex grid (for MPA overlay). The final marts have GiST on "
        "geom for map tile serving. Everything else uses B-tree indexes "
        "on integer keys (h3_cell, month) because all spatial "
        "relationships were pre-computed in Python and reduced to "
        "integer key joins.",
        ReportPDF.ACCENT_GREEN,
    )

    # ── Final summary box ───────────────────────────
    pdf.ln(6)
    y = pdf.get_y()
    if y > 220:
        pdf.add_page()

    pdf.set_fill_color(*ReportPDF.NAVY)
    box_y = pdf.get_y()
    pdf.rect(10, box_y, 190, 48, style="F")

    pdf.set_xy(15, box_y + 5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*ReportPDF.WHITE)
    pdf.cell(180, 8, "Core Design Principle")

    pdf.set_xy(15, box_y + 14)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(200, 220, 240)
    pdf.multi_cell(
        178,
        5,
        "Python handles what SQL structurally cannot: raster I/O, "
        "in-memory spatial trees for unindexed data, and deterministic "
        "H3 cell assignment. PostGIS handles polygon overlays on indexed "
        "tables. dbt handles all relational algebra (joins, aggregation, "
        "ranking, scoring) where B-tree indexes on h3_cell make "
        "everything fast. Each tool operates in its zone of strength.",
    )

    # ── Output ──────────────────────────────────────
    output_path = "docs/sql_spatial_deep_dive.pdf"
    pdf.output(output_path)
    print(f"Report saved to {output_path}")


if __name__ == "__main__":
    build_report()

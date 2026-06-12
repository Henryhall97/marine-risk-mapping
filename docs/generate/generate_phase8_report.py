"""Generate Phase 8 — FastAPI Backend API PDF report.

Comprehensive documentation of the REST API layer: architecture,
database service, authentication, 110 endpoints across 16 route
modules, sighting orchestration, community features, reputation
system, and API design patterns.

Usage:
    uv run python docs/generate/generate_phase8_report.py
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

# ── Paths ─────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "phase8_backend_api.pdf"


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
    ACCENT_BLUE = (52, 152, 219)
    ACCENT_RED = (214, 64, 69)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(
                0,
                10,
                "Marine Risk Mapping -- Phase 8: Backend API",
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
        for w, h_text in zip(col_widths, headers, strict=True):
            self.cell(w, 7, f"  {h_text}", fill=True)
        self.ln()
        self.set_font("Helvetica", "", 9)
        for i, row in enumerate(rows):
            if self.get_y() > 265:
                self.add_page()
                # Re-draw header row after page break
                self.set_fill_color(*self.NAVY)
                self.set_text_color(*self.WHITE)
                self.set_font("Helvetica", "B", 9)
                for w, h_text in zip(col_widths, headers, strict=True):
                    self.cell(w, 7, f"  {h_text}", fill=True)
                self.ln()
                self.set_font("Helvetica", "", 9)
            bg = self.LIGHT_BG if i % 2 == 0 else self.WHITE
            self.set_fill_color(*bg)
            for j, (w, cell_val) in enumerate(zip(col_widths, row, strict=True)):
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
        if self.get_y() > 240:
            self.add_page()
        y_start = self.get_y()
        self.set_fill_color(*self.LIGHT_BG)
        self.set_font("Helvetica", "", 9.5)
        n_lines = max(1, len(text) // 75 + 1)
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

    def code_block(self, text):
        """Render a monospace code snippet in a light box."""
        if self.get_y() > 250:
            self.add_page()
        y = self.get_y()
        self.set_fill_color(245, 245, 245)
        self.set_draw_color(200, 200, 200)
        lines = text.strip().split("\n")
        box_h = 6 + len(lines) * 4.5
        self.rect(15, y, 180, box_h, style="FD")
        self.set_xy(18, y + 3)
        self.set_font("Courier", "", 8.5)
        self.set_text_color(*self.DARK_TEXT)
        for line in lines:
            self.cell(0, 4.5, line)
            self.ln(4.5)
            self.set_x(18)
        self.set_y(y + box_h + 4)


# ═══════════════════════════════════════════════════════════════
# Endpoint inventory data
# ═══════════════════════════════════════════════════════════════

MODULE_COUNTS = [
    ("health.py", 1, "Health check"),
    ("risk.py", 12, "Risk zones, stats, ML, projected, compare"),
    ("species.py", 4, "Species list, crosswalk, risk, seasonal"),
    ("traffic.py", 2, "Monthly & seasonal traffic"),
    ("layers.py", 15, "Spatial overlays (15 layer types)"),
    ("photo.py", 1, "Photo classification"),
    ("audio.py", 1, "Audio classification"),
    ("sightings.py", 1, "Combined sighting report"),
    ("zones.py", 7, "Zone geometries (GeoJSON)"),
    ("violations.py", 5, "Vessel violation CRUD + stats"),
    ("auth.py", 9, "Register, login, profile, reputation"),
    ("submissions.py", 15, "Sighting submission lifecycle"),
    ("events.py", 25, "Community events & comments"),
    ("external_events.py", 6, "External event CRUD + seed"),
    ("media.py", 4, "File upload/serve/metadata"),
    ("macro.py", 2, "Coast-wide macro overview"),
]

TOTAL_ENDPOINTS = sum(c for _, c, _ in MODULE_COUNTS)

# ── Risk endpoint details ────────────────────────────────────

RISK_ENDPOINTS = [
    ("GET", "/risk/zones", "Paginated risk zones (bbox filter)"),
    ("GET", "/risk/zones/stats", "Aggregate risk statistics"),
    ("GET", "/risk/zones/{h3_cell}", "Single-cell full detail"),
    ("GET", "/risk/seasonal", "Seasonal risk (bbox + season)"),
    ("GET", "/risk/ml", "ML-enhanced risk zones"),
    ("GET", "/risk/ml/stats", "ML aggregate statistics"),
    ("GET", "/risk/ml/{h3_cell}", "ML single-cell detail"),
    ("GET", "/risk/ml/projected", "Climate-projected ML risk"),
    (
        "GET",
        "/risk/ml/projected/stats",
        "Projected risk statistics",
    ),
    (
        "GET",
        "/risk/ml/projected/{h3_cell}",
        "Projected single-cell detail",
    ),
    ("GET", "/risk/breakdown/{h3_cell}", "Sub-score breakdown"),
    ("GET", "/risk/compare", "Standard vs ML side-by-side"),
]

LAYER_ENDPOINTS = [
    ("GET", "/layers/bathymetry", "Depth, shelf, slope"),
    ("GET", "/layers/ocean", "SST, MLD, SLA, PP"),
    ("GET", "/layers/whale-predictions", "ISDM whale probs"),
    ("GET", "/layers/sdm-predictions", "SDM OOF predictions"),
    ("GET", "/layers/sdm-projections", "CMIP6 projected SDM"),
    (
        "GET",
        "/layers/sdm-projections/summary",
        "Projection stats",
    ),
    (
        "GET",
        "/layers/isdm-projections",
        "CMIP6 projected ISDM",
    ),
    (
        "GET",
        "/layers/isdm-projections/summary",
        "ISDM proj stats",
    ),
    ("GET", "/layers/mpa", "MPA coverage cells"),
    ("GET", "/layers/speed-zones", "Speed zone coverage"),
    ("GET", "/layers/proximity", "Distances & decay"),
    ("GET", "/layers/nisi-risk", "Nisi reference grid"),
    ("GET", "/layers/cetacean-density", "Sighting density"),
    ("GET", "/layers/strike-density", "Strike density"),
    ("GET", "/layers/traffic-density", "22 traffic metrics"),
    ("GET", "/layers/context/{h3_cell}", "Ecological context"),
]

ZONE_ENDPOINTS = [
    ("GET", "/zones/speed-zones/current", "Active SMAs"),
    ("GET", "/zones/speed-zones/proposed", "Proposed zones"),
    ("GET", "/zones/mpas", "MPA polygons"),
    ("GET", "/zones/bia", "Biologically Important Areas"),
    (
        "GET",
        "/zones/critical-habitat",
        "ESA critical habitat",
    ),
    ("GET", "/zones/shipping-lanes", "TSS, lanes"),
    ("GET", "/zones/slow-zones", "Active DMAs"),
]

AUTH_ENDPOINTS = [
    ("POST", "/auth/register", "Create account"),
    ("POST", "/auth/login", "JWT token login"),
    ("GET", "/auth/me", "Current user profile"),
    ("GET", "/auth/users/{user_id}", "Public profile"),
    ("PATCH", "/auth/bio", "Update bio"),
    (
        "GET",
        "/auth/users/{uid}/reputation/history",
        "Rep history",
    ),
    ("POST", "/auth/credentials", "Submit credential"),
    ("POST", "/auth/avatar", "Upload avatar"),
    ("DELETE", "/auth/avatar", "Remove avatar"),
]

REPUTATION_EVENTS = [
    ("sighting_verified", "+10", "Sighting confirmed by others"),
    ("model_agreement", "+5", "ML model agrees with user"),
    ("verification_consensus", "+3", "User verif reaches consensus"),
    ("verification_given", "+2", "User verifies a sighting"),
    ("credential_verified", "+20", "Professional credential OK"),
    ("sighting_rejected", "-5", "Sighting rejected by community"),
    ("sighting_disputed", "-2", "Sighting receives disputes"),
]

REPUTATION_TIERS = [
    ("Authority", "1000+", "Full trust, moderation rights"),
    ("Expert", "500-999", "High credibility, priority review"),
    ("Contributor", "200-499", "Established community member"),
    ("Observer", "50-199", "Active participant"),
    ("Newcomer", "0-49", "New user, building trust"),
]


# ═══════════════════════════════════════════════════════════════
# Report content
# ═══════════════════════════════════════════════════════════════


def build_report():  # noqa: C901 PLR0915
    pdf = ReportPDF("P", "mm", "A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── 1. Title page ─────────────────────────────────────────
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*ReportPDF.NAVY)
    pdf.cell(
        0,
        14,
        "Phase 8: Backend API",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(*ReportPDF.TEAL)
    pdf.cell(
        0,
        10,
        "FastAPI REST API for Marine Risk Mapping",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*ReportPDF.MID_TEXT)
    pdf.cell(
        0,
        8,
        "Marine Risk Mapping Project",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        8,
        "March 2026",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(12)
    pdf.stat_boxes(
        [
            (str(TOTAL_ENDPOINTS), "API Endpoints"),
            ("16", "Route Modules"),
            ("16", "Service Classes"),
            ("15", "Pydantic Models"),
        ]
    )

    pdf.ln(8)
    pdf.body_text(
        "The Phase 8 backend exposes all collision risk data, "
        "species distributions, vessel traffic analytics, ML "
        "classification services, and community features as a "
        "versioned REST API. Built on FastAPI with Pydantic v2 "
        "validation, psycopg2 connection pooling, and JWT "
        "authentication, it serves the Next.js frontend and "
        "supports third-party integration."
    )

    # ── 2. Architecture Overview ──────────────────────────────
    pdf.add_page()
    pdf.section_title("1. Architecture Overview")

    pdf.body_text(
        "The API is a single FastAPI application defined in "
        "backend/app.py. It follows a three-layer architecture: "
        "route handlers (thin controllers), service modules "
        "(business logic + SQL queries), and Pydantic models "
        "(request/response validation). All state is in "
        "PostgreSQL -- the API is stateless and horizontally "
        "scalable."
    )

    pdf.subsection_title("Application Lifecycle")
    pdf.body_text(
        "FastAPI's async lifespan context manager initialises "
        "the database connection pool on startup (min=4, "
        "max=30 connections via psycopg2 "
        "ThreadedConnectionPool) and tears it down on "
        "shutdown. No background tasks or scheduled jobs "
        "run in the API process."
    )

    pdf.subsection_title("Middleware")
    pdf.bullet(
        "CORS: Allows localhost:3000 (Next.js) and "
        "localhost:5173 (Vite) with credentials, all methods "
        "and headers."
    )
    pdf.bullet(
        "No rate limiting in dev; reverse proxy (nginx/Caddy) "
        "handles rate limiting in production."
    )

    pdf.subsection_title("Router Registration")
    pdf.body_text(
        "Sixteen router modules are registered in app.py. "
        "The health check is mounted at the root (/health). "
        "All domain routers share the /api/v1 prefix. Auth, "
        "submissions, events, and macro routers define their "
        "own prefix internally."
    )

    pdf.metric_table(
        ["Module", "Count", "Domain"],
        [(mod, str(cnt), desc) for mod, cnt, desc in MODULE_COUNTS],
        col_widths=[45, 18, 127],
    )

    pdf.callout_box(
        "Design Decision: Thin Routes",
        "Route handlers validate inputs, call one or more "
        "service functions (which return plain dicts), and "
        "construct Pydantic response models. This keeps "
        "routes under ~30 lines each and makes services "
        "independently testable.",
    )

    # ── 3. Database Service ───────────────────────────────────
    pdf.add_page()
    pdf.section_title("2. Database Service Layer")

    pdf.body_text(
        "All database access flows through "
        "backend/services/database.py, which manages a "
        "psycopg2 ThreadedConnectionPool shared across "
        "the application."
    )

    pdf.subsection_title("Connection Pool")
    pdf.bullet(
        "ThreadedConnectionPool(minconn=4, maxconn=30) "
        "-- thread-safe connection checkout/return."
    )
    pdf.bullet(
        "Connections obtained via get_conn() context "
        "manager with automatic return on exit."
    )
    pdf.bullet(
        "Pool initialised in lifespan startup, closed on "
        "shutdown -- no leaked connections."
    )

    pdf.subsection_title("Query Helpers")
    pdf.metric_table(
        ["Function", "Cursor", "Returns"],
        [
            ("fetch_all(sql, params)", "RealDictCursor", "list[dict]"),
            ("fetch_one(sql, params)", "RealDictCursor", "dict | None"),
            ("fetch_scalar(sql, params)", "tuple cursor", "scalar value"),
            ("execute(sql, params)", "default", "None (side effect)"),
        ],
        col_widths=[60, 50, 80],
    )

    pdf.body_text(
        "RealDictCursor returns rows as Python dicts, which "
        "route handlers pass directly to Pydantic model "
        "constructors. This avoids ORM overhead while keeping "
        "the service layer decoupled from Pydantic."
    )

    pdf.callout_box(
        "Why psycopg2, Not an ORM?",
        "The spatial queries (ST_AsGeoJSON, H3 joins, "
        "percent_rank windows) are complex enough that raw SQL "
        "is clearer than ORM abstractions. psycopg2 also "
        "integrates natively with PostGIS geometry types.",
    )

    # ── 4. Authentication & Authorization ─────────────────────
    pdf.add_page()
    pdf.section_title("3. Authentication & Authorization")

    pdf.body_text(
        "JWT-based authentication with bcrypt password hashing. "
        "Tokens are issued on login and verified via the "
        "Authorization: Bearer header on protected endpoints."
    )

    pdf.subsection_title("Token Flow")
    pdf.numbered_item(
        1, "User registers via POST /auth/register (email + display_name + password)."
    )
    pdf.numbered_item(
        2, "Password hashed with bcrypt (12 rounds) and stored in the users table."
    )
    pdf.numbered_item(
        3, "POST /auth/login returns a JWT (HS256, 24-hour expiry) containing user_id."
    )
    pdf.numbered_item(
        4,
        "Protected routes call require_user() which "
        "decodes the token and returns the user dict.",
    )
    pdf.numbered_item(
        5,
        "optional_user() variant returns None for "
        "anonymous requests (public endpoints).",
    )

    pdf.subsection_title("User Schema")
    pdf.metric_table(
        ["Column", "Type", "Notes"],
        [
            ("id", "SERIAL PK", "Auto-increment"),
            ("email", "VARCHAR UNIQUE", "Login identifier"),
            ("display_name", "VARCHAR", "Public name"),
            ("password_hash", "VARCHAR", "bcrypt output"),
            ("bio", "TEXT", "Optional profile text"),
            ("reputation_score", "INTEGER", "Default 0"),
            ("reputation_tier", "VARCHAR", 'Default "newcomer"'),
            ("avatar_filename", "VARCHAR", "Stored on disk"),
            ("is_admin", "BOOLEAN", "Default false"),
            ("is_active", "BOOLEAN", "Default true"),
            ("created_at", "TIMESTAMPTZ", "Auto"),
        ],
        col_widths=[55, 50, 85],
    )

    pdf.subsection_title("Auth Endpoints (9)")
    pdf.metric_table(
        ["Method", "Path", "Description"],
        [(m, p, d) for m, p, d in AUTH_ENDPOINTS],
        col_widths=[20, 75, 95],
    )

    # ── 5. Endpoint Inventory ─────────────────────────────────
    pdf.add_page()
    pdf.section_title("4. Endpoint Inventory")

    pdf.body_text(
        f"The API exposes {TOTAL_ENDPOINTS} endpoints across "
        f"16 route modules, organised into seven functional "
        f"groups: core risk & data, spatial layers, zone "
        f"geometries, ML classification, community, "
        f"administration, and infrastructure."
    )

    pdf.subsection_title("Risk Endpoints (12)")
    pdf.body_text(
        "Three risk mart variants are exposed: standard "
        "(fct_collision_risk), ML-enhanced "
        "(fct_collision_risk_ml), and climate-projected "
        "(fct_collision_risk_ml_projected). Each has list, "
        "stats, and detail endpoints."
    )
    pdf.metric_table(
        ["Method", "Path", "Description"],
        [(m, p, d) for m, p, d in RISK_ENDPOINTS],
        col_widths=[18, 80, 92],
    )

    pdf.subsection_title("Species Endpoints (4)")
    pdf.metric_table(
        ["Method", "Path", "Description"],
        [
            ("GET", "/species", "List from crosswalk seed"),
            ("GET", "/species/crosswalk", "Full 77-row bridge"),
            ("GET", "/species/risk", "Per-species risk cells"),
            ("GET", "/species/seasonal", "Seasonal density"),
        ],
        col_widths=[18, 65, 107],
    )

    pdf.subsection_title("Traffic Endpoints (2)")
    pdf.metric_table(
        ["Method", "Path", "Description"],
        [
            ("GET", "/traffic/monthly", "Monthly stats (bbox)"),
            ("GET", "/traffic/seasonal", "Seasonal aggregates"),
        ],
        col_widths=[18, 65, 107],
    )

    # ── 6. Spatial Layer Endpoints ────────────────────────────
    pdf.add_page()
    pdf.section_title("5. Spatial Layer Endpoints")

    pdf.body_text(
        "Fifteen layer endpoints expose H3-gridded data for "
        "map overlays. Each accepts bbox parameters "
        "(lat_min, lat_max, lon_min, lon_max) and returns "
        "paginated cell arrays. Season filters are available "
        "on seasonally-varying layers."
    )

    pdf.metric_table(
        ["Method", "Path", "Description"],
        [(m, p, d) for m, p, d in LAYER_ENDPOINTS],
        col_widths=[18, 82, 90],
    )

    pdf.subsection_title("Zone Geometry Endpoints (7)")
    pdf.body_text(
        "Zone endpoints return GeoJSON Feature objects with "
        "full polygon geometries via ST_AsGeoJSON. These "
        "render as vector overlays on the deck.gl map."
    )
    pdf.metric_table(
        ["Method", "Path", "Description"],
        [(m, p, d) for m, p, d in ZONE_ENDPOINTS],
        col_widths=[18, 80, 92],
    )

    pdf.callout_box(
        "Bbox Validation",
        "All spatial endpoints validate: lat_min < lat_max, "
        "lon_min < lon_max, and bbox area <= 100 deg-squared. "
        "Requests exceeding the area limit receive HTTP 400. "
        "This prevents accidentally querying the entire "
        "1.8M-cell grid.",
    )

    # ── 7. ML Classification ─────────────────────────────────
    pdf.add_page()
    pdf.section_title("6. ML Classification Endpoints")

    pdf.subsection_title("Photo Classification")
    pdf.body_text(
        "POST /api/v1/photo/classify accepts a multipart image "
        "upload (JPG/PNG, max 20 MB) with optional lat/lon "
        "coordinates. Returns species probabilities from the "
        "EfficientNet-B4 model and, if coordinates are "
        "provided, H3 cell risk context from "
        "fct_collision_risk."
    )
    pdf.bullet("8 classes: 7 whale species + other_cetacean")
    pdf.bullet("GPS from EXIF metadata (auto-extracted) or user-supplied form fields")
    pdf.bullet("Lazy-loaded singleton -- first request loads model")

    pdf.subsection_title("Audio Classification")
    pdf.body_text(
        "POST /api/v1/audio/classify accepts WAV/FLAC/MP3/AIF "
        "uploads (max 100 MB) with required lat/lon. Audio is "
        "segmented into 4s windows (2s hop) and each segment "
        "classified independently."
    )
    pdf.bullet(
        "8 target species via XGBoost (64 acoustic features) or CNN (mel spectrogram)"
    )
    pdf.bullet("Returns per-segment predictions + dominant species + confidence")
    pdf.bullet("H3 risk context (7 sub-scores) from fct_collision_risk")

    pdf.callout_box(
        "Why Audio Requires GPS",
        "Unlike photos, audio files have no EXIF GPS metadata. "
        "Coordinates are mandatory for H3 cell lookup and risk "
        "context. The endpoint returns HTTP 422 if lat/lon "
        "are missing.",
        colour=ReportPDF.ACCENT_AMBER,
    )

    # ── 8. Sighting Orchestration ─────────────────────────────
    pdf.add_page()
    pdf.section_title("7. Sighting Orchestration")

    pdf.body_text(
        "POST /api/v1/sightings/report is the richest endpoint "
        "in the API. It combines photo classification, audio "
        "classification, spatial risk lookup, species "
        "assessment, and advisory generation into a single "
        "multi-step pipeline."
    )

    pdf.subsection_title("Five-Step Pipeline")
    pdf.numbered_item(
        1,
        "Photo classification: If an image is provided, "
        "classify species and extract EXIF GPS as coordinate "
        "fallback.",
    )
    pdf.numbered_item(
        2,
        "Audio classification: If audio is provided with "
        "coordinates, segment and classify whale species per "
        "4-second window.",
    )
    pdf.numbered_item(
        3,
        "H3 risk lookup: Convert coordinates to an H3 res-7 "
        "cell and fetch all 7 sub-scores from "
        "fct_collision_risk.",
    )
    pdf.numbered_item(
        4,
        "Species assessment: Reconcile user guess, photo "
        "prediction, and audio prediction into a final "
        "determination. Priority: photo+audio consensus > "
        "photo-only > audio-only > user guess.",
    )
    pdf.numbered_item(
        5,
        "Advisory generation: Generate risk advisory based on "
        "risk level and species. 4 severity levels, with "
        "escalation for protected species (right, humpback, "
        "fin, blue, sei, sperm). Includes regional NOAA "
        "authority contacts.",
    )

    pdf.subsection_title("Species Assessment Logic")
    pdf.body_text(
        "The assessment reconciles multiple identification "
        "sources with a confidence-weighted priority system:"
    )
    pdf.bullet(
        "If photo and audio agree on the same species, that "
        "species is returned with boosted confidence."
    )
    pdf.bullet(
        "If they disagree, the photo prediction is preferred "
        "(visual ID is generally more reliable)."
    )
    pdf.bullet("If only one modality is available, its prediction is used directly.")
    pdf.bullet("The user's species guess is the lowest-priority fallback.")

    pdf.subsection_title("Advisory Levels")
    pdf.metric_table(
        ["Level", "Trigger", "Guidance"],
        [
            ("Critical", "Protected species + high risk", "Report immediately"),
            ("High", "High risk zone", "Reduce speed, post lookout"),
            ("Moderate", "Medium risk zone", "Maintain awareness"),
            ("Low", "Low risk zone", "Standard operations"),
        ],
        col_widths=[30, 65, 95],
    )

    # ── 9. Community Features ─────────────────────────────────
    pdf.add_page()
    pdf.section_title("8. Community Features")

    pdf.body_text(
        "The API supports a full community platform with "
        "sighting submissions, peer verification, community "
        "events, and vessel violation reporting. These "
        "features encourage citizen science participation "
        "and data quality improvement."
    )

    pdf.subsection_title("Submissions (15 endpoints)")
    pdf.body_text(
        "Sighting submissions capture classified photos and "
        "audio along with GPS coordinates and species "
        "predictions. The submission lifecycle includes "
        "creation, review, community verification, and "
        "public/private visibility toggling."
    )
    pdf.bullet("GET /submissions/mine -- authenticated user's list")
    pdf.bullet("GET /submissions/public -- community feed of verified sightings")
    pdf.bullet(
        "POST /submissions/{id}/verify -- agree/disagree "
        "vote with optional species correction"
    )
    pdf.bullet("PATCH /submissions/{id}/visibility -- toggle public/private")
    pdf.bullet(
        "GET /submissions/map-sightings -- map-ready verified sightings with H3 cells"
    )

    pdf.subsection_title("Community Events (25 endpoints)")
    pdf.body_text(
        "Events let users organise whale watching trips, "
        "citizen science surveys, and educational outings. "
        "Full CRUD with invite codes, cover photos, member "
        "roles, sighting linking, comments, and summary "
        "statistics."
    )
    pdf.bullet("POST /events -- create event (auto-generates 8-char invite code)")
    pdf.bullet("POST /events/join/{invite_code} -- join by invite")
    pdf.bullet(
        "POST /events/{id}/sightings/{sub_id} -- link a sighting report to the event"
    )
    pdf.bullet(
        "GET /events/{id}/stats -- species breakdown, top contributors, mean risk"
    )
    pdf.bullet("POST /events/{id}/comments -- threaded discussion")
    pdf.bullet("POST /events/{id}/cover -- upload cover photo")

    pdf.subsection_title("External Events (6 endpoints)")
    pdf.body_text(
        "External events (conferences, workshops, NOAA "
        "briefings) can be imported and seeded alongside "
        "user-created events. Full CRUD with seed endpoint "
        "for batch import."
    )

    pdf.subsection_title("Violations (5 endpoints)")
    pdf.body_text(
        "Vessel interaction reports capture speed zone "
        "violations, close approaches, and other concerning "
        "vessel behaviour. CRUD operations plus aggregate "
        "statistics for enforcement analytics."
    )

    # ── 10. Reputation System ─────────────────────────────────
    pdf.add_page()
    pdf.section_title("9. Reputation System")

    pdf.body_text(
        "An event-based reputation system incentivises quality "
        "contributions and builds community trust. Users earn "
        "or lose points through specific actions, advancing "
        "through five tiers that unlock different levels of "
        "credibility."
    )

    pdf.subsection_title("Reputation Events")
    pdf.metric_table(
        ["Event", "Points", "Trigger"],
        [(ev, pts, desc) for ev, pts, desc in REPUTATION_EVENTS],
        col_widths=[60, 22, 108],
    )

    pdf.subsection_title("Tier Progression")
    pdf.metric_table(
        ["Tier", "Score", "Privileges"],
        [(tier, score, desc) for tier, score, desc in REPUTATION_TIERS],
        col_widths=[40, 30, 120],
    )

    pdf.body_text(
        "Reputation scores are floored at zero (no negative "
        "scores). Tier transitions are computed on each "
        "reputation event -- there is no cron job. The "
        "reputation_history table stores all events for "
        "audit and user profile display."
    )

    pdf.callout_box(
        "Credential Verification",
        "Users can submit professional credentials (marine "
        "biology degree, NOAA affiliation, etc.) for manual "
        "review. Verified credentials award +20 points and "
        "are displayed on the public profile. Seven credential "
        "types are supported.",
    )

    # ── 11. API Patterns ──────────────────────────────────────
    pdf.add_page()
    pdf.section_title("10. API Patterns & Conventions")

    pdf.subsection_title("Bbox Validation")
    pdf.body_text(
        "All spatial endpoints enforce: (1) lat_min < lat_max, "
        "(2) lon_min < lon_max, (3) lat in [-90, 90], "
        "(4) lon in [-180, 180], and (5) area <= 100 deg^2. "
        "Invalid requests return HTTP 400 with a descriptive "
        "error message."
    )

    pdf.subsection_title("Pagination")
    pdf.body_text(
        "List endpoints accept limit (default 100, max 5000) "
        "and offset (default 0) query parameters. The service "
        "layer runs a COUNT(*) query first, then the data "
        "query with LIMIT/OFFSET. Responses use the "
        "PaginatedResponse wrapper:"
    )
    pdf.bullet("total: int -- total matching rows")
    pdf.bullet("limit: int -- requested page size")
    pdf.bullet("offset: int -- current offset")
    pdf.bullet("data: list[T] -- page of results")

    pdf.subsection_title("Error Handling")
    pdf.metric_table(
        ["Status", "Meaning", "Example"],
        [
            ("400", "Bad request", "Bbox area exceeds limit"),
            ("401", "Unauthorised", "Missing/expired JWT"),
            ("403", "Forbidden", "Not event creator"),
            ("404", "Not found", "H3 cell not in grid"),
            ("409", "Conflict", "Email already registered"),
            ("422", "Validation error", "Missing required field"),
        ],
        col_widths=[22, 55, 113],
    )

    pdf.subsection_title("Response Assembly Pattern")
    pdf.body_text(
        "Services return plain Python dicts (from "
        "RealDictCursor rows). Route handlers construct "
        "Pydantic models from these dicts using ** unpacking "
        "or explicit field mapping. This decouples the "
        "service layer from the API contract."
    )

    pdf.subsection_title("Upload Limits")
    pdf.metric_table(
        ["Type", "Max Size", "Formats"],
        [
            ("Avatar", "5 MB", "JPG, PNG"),
            ("Credential evidence", "10 MB", "JPG, PNG, PDF"),
            ("Photo classification", "20 MB", "JPG, PNG"),
            ("Audio classification", "100 MB", "WAV, FLAC, MP3, AIF"),
            ("Event cover", "10 MB", "JPG, PNG"),
        ],
        col_widths=[55, 30, 105],
    )

    # ── 12. Pydantic Models ───────────────────────────────────
    pdf.add_page()
    pdf.section_title("11. Pydantic Model Architecture")

    pdf.body_text(
        "Fifteen Pydantic v2 model modules define the API's "
        "type contract. All models use BaseModel with strict "
        "validation. Field-level constraints (ge, le, "
        "min_length, max_length) enforce domain rules at "
        "the schema level."
    )

    pdf.subsection_title("Common Models (backend/models/common.py)")
    pdf.bullet("BboxParams: Constrained lat/lon float fields with range validation")
    pdf.bullet("PaginationParams: limit (1-5000), offset (>= 0)")
    pdf.bullet("PaginatedResponse[T]: Generic wrapper with total, limit, offset, data")

    pdf.subsection_title("Risk Models")
    pdf.bullet(
        "RiskZoneSummary: h3_cell, lat, lon, risk_score, risk_category + 7 sub-scores"
    )
    pdf.bullet("RiskZoneDetail: 76 fields including all raw metrics")
    pdf.bullet("RiskStats: min/max/mean/count/distribution aggregates")

    pdf.subsection_title("Layer Models (30+ schemas)")
    pdf.body_text(
        "Each layer endpoint has its own response schema "
        "with layer-specific fields. Examples: "
        "BathymetryCell (depth, depth_zone, shelf/slope "
        "booleans), OceanCell (sst, mld, sla, pp), "
        "WhalePredictionCell (species-level probabilities), "
        "TrafficDensityCell (22 sub-metrics)."
    )

    pdf.subsection_title("Auth & Community Models")
    pdf.bullet("RegisterRequest: EmailStr + Field validators (min password length 8)")
    pdf.bullet(
        "EventCreate: title (3-200 chars), description "
        "(max 5000), event_type, scheduled_at"
    )
    pdf.bullet("EventStats: species breakdown, top contributors, mean risk score")
    pdf.bullet(
        "ViolationCreate/Response: vessel info, location, violation type, evidence"
    )

    pdf.callout_box(
        "Avatar URL Resolution",
        "Pydantic model_validators in UserProfile and "
        "EventMember convert avatar_filename to a full URL "
        "(/api/v1/media/avatar/{user_id}). This centralises "
        "URL construction and avoids the previous bug where "
        "route helpers built incorrect /avatars/{filename} "
        "paths.",
    )

    # ── 13. Macro Overview ────────────────────────────────────
    pdf.add_page()
    pdf.section_title("12. Macro Overview Service")

    pdf.body_text(
        "The macro endpoints serve pre-aggregated H3 res-4 "
        "data for coast-wide heatmap rendering without "
        "loading 1.8M res-7 cells. The macro_risk_overview "
        "table contains ~14,176 cells x 5 seasons = 70,880 "
        "rows."
    )

    pdf.subsection_title("MacroCell Fields (31)")
    pdf.body_text(
        "Each macro cell includes: h3_cell, lat, lon, "
        "season, mean risk score, risk category, cell count "
        "(child res-7 cells), plus 6 traffic sub-metrics "
        "(avg_monthly_vessels, avg_speed_lethality, "
        "avg_high_speed_fraction, avg_draft_risk_fraction, "
        "night_traffic_ratio, avg_commercial_vessels) and "
        "aggregated environmental and species fields."
    )

    pdf.subsection_title("Bathymetry Contours")
    pdf.body_text(
        "GET /macro/contours/bathymetry returns GeoJSON "
        "contour lines for depth visualisation as a map "
        "overlay. Generated from the H3 bathymetry grid "
        "using PostGIS ST_Contour."
    )

    # ── 14. Testing ───────────────────────────────────────────
    pdf.section_title("13. Testing")

    pdf.body_text(
        "The backend has 121 pytest tests in test_backend.py "
        "covering routes, services, layers, ML risk, "
        "sightings, zones, auth, submissions, events, macro, "
        "and media endpoints. Tests use FastAPI's TestClient "
        "with mocked database services."
    )

    pdf.bullet(
        "Service mocks: patch database.fetch_all/fetch_one to return fixture dicts"
    )
    pdf.bullet("Auth mocks: patch require_user to return a test user dict without JWT")
    pdf.bullet(
        "File upload tests: use UploadFile with BytesIO for "
        "photo/audio/avatar endpoints"
    )
    pdf.bullet(
        "Bbox validation: dedicated tests for area limit, "
        "coordinate inversion, out-of-range"
    )

    # ── 15. Key Takeaways ─────────────────────────────────────
    pdf.add_page()
    pdf.section_title("14. Key Takeaways")

    takeaways = [
        (
            f"{TOTAL_ENDPOINTS} REST endpoints across 16 "
            "modules covering risk, species, traffic, layers, "
            "zones, ML classification, and community."
        ),
        (
            "Three-layer architecture (routes/services/models) "
            "keeps each layer independently testable and "
            "decoupled."
        ),
        (
            "psycopg2 ThreadedConnectionPool (4-30 conns) "
            "with RealDictCursor for zero-ORM spatial SQL."
        ),
        (
            "JWT HS256 auth with bcrypt hashing, 24h expiry, "
            "and require_user/optional_user helpers."
        ),
        (
            "Five-step sighting orchestration: photo + audio "
            "+ H3 risk + species assessment + advisory."
        ),
        (
            "Event-based reputation system with 7 event types, "
            "5 tiers, and score floored at zero."
        ),
        (
            "Bbox validation on all spatial endpoints prevents "
            "accidental full-grid queries (area <= 100 deg^2)."
        ),
        (
            "Lazy-loaded ML singletons -- EfficientNet-B4 and "
            "XGBoost/CNN classifiers load on first request."
        ),
        (
            "Pre-aggregated macro grid (70,880 rows at H3 "
            "res-4) enables instant coast-wide heatmaps."
        ),
        (
            "Pydantic model_validators centralise avatar URL "
            "construction, eliminating a class of URL bugs."
        ),
    ]

    for i, text in enumerate(takeaways, 1):
        pdf.numbered_item(i, text)

    # ── Generate ──────────────────────────────────────────────
    pdf.output(str(OUTPUT_FILE))
    print(f"Generated {OUTPUT_FILE}")
    print(f"  Pages: {pdf.page_no()}")


if __name__ == "__main__":
    build_report()

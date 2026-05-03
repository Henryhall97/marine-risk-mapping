# Copilot Project Instructions — Marine Risk Mapping

> **Last updated:** 2026-03-15  (ArcFace photo classifier + EC2 remote launcher)
> **Update trigger:** See [§ Keeping This File Current](#keeping-this-file-current) at the bottom.

---

## 1. Project Overview

A marine risk mapping platform that combines AIS vessel traffic, cetacean sightings,
ship strike records, bathymetry, ocean covariates, and regulatory zones to predict
whale–vessel collision risk across the study area (lat 2°S–52°N, lon 180°W–59°W
— CONUS, Alaska, Hawaii, Caribbean, and adjacent waters).

**Key output tables (dbt marts):**

| Mart | Rows | Purpose |
|---|---|---|
| `fct_collision_risk` | 1.8M | 7-sub-score composite collision risk per H3 cell |
| `fct_collision_risk_seasonal` | 7.3M | Seasonal variant (×4 seasons) with season-varying sub-scores |
| `fct_collision_risk_ml` | 7.3M | ML-enhanced: ISDM+SDM ensemble whale predictions replace cetacean+habitat (7 sub-scores, 6 species) |
| `fct_collision_risk_ml_projected` | 58M | Climate-projected ML risk (ISDM+SDM ensemble, 6 sub-scores — no proximity, SSP2-4.5/SSP5-8.5, 2030s–2080s) |
| `fct_whale_sdm_training` | 1.8M | Feature matrix for species distribution modelling |
| `fct_whale_sdm_seasonal` | 7.3M | Seasonal SDM training (no traffic features — detection bias) |
| `fct_strike_risk_training` | 1.8M | Feature matrix for strike probability modelling |
| `fct_species_risk` | 98K | Per-species risk aggregation |
| `fct_monthly_traffic` | 9.2M | Monthly vessel traffic statistics |

---

## 2. Repository Structure

```
marine_risk_mapping/
├── .github/
│   └── copilot-instructions.md    ← THIS FILE
├── docker/
│   └── docker-compose.yml         # PostGIS 16 + PostGIS 3.4
├── pipeline/
│   ├── config.py                  # Reads scoring weights from dbt_project.yml; DB_CONFIG from env vars; H3_RESOLUTION, US_BBOX, vessel codes, file paths
│   ├── utils.py                   # Shared helpers: to_python, bulk_insert, assign_h3_cells
│   ├── audio/                     # Whale audio classification (domain library)
│   │   ├── preprocess.py          # Load, resample, segment, mel/PCEN, acoustic features
│   │   └── classify.py            # WhaleAudioClassifier ABC + XGBoost & CNN backends
│   ├── photo/                     # Whale photo classification (domain library)
│   │   ├── preprocess.py          # Resize, normalize, augmentations, dataset class, EXIF GPS
│   │   └── classify.py            # WhalePhotoClassifier: EfficientNet-B4 fine-tune + inference
│   ├── ingestion/                 # Download scripts (AIS, OBIS, NOAA, Copernicus, whale audio, BIA, critical habitat, shipping lanes, slow zones)
│   ├── aggregation/               # H3 assignment + proximity (Python)
│   ├── database/                  # Schema creation + data loading
│   ├── validation/                # Pandera schemas + quality reports
│   └── analysis/                  # ML training, evaluation, feature extraction (10 scripts)
├── transform/                     # dbt project root
│   ├── dbt_project.yml
│   ├── profiles.yml               # Local profiles — use --profiles-dir .
│   ├── macros/
│   │   ├── season_from_month.sql  # CASE macro: month integer → season name
│   │   ├── sub_scores.sql         # 7 sub-score macros (traffic, cetacean, whale_ml, strike, habitat, protection_gap, proximity)
│   │   ├── weighted_risk_score.sql # Composite score macro ('standard' 7-sub, 'ml' 7-sub)
│   │   └── risk_category.sql      # Score → category label macro
│   ├── seeds/
│   │   ├── species_crosswalk.csv  # 71-row species bridge table
│   │   └── seeds.yml
│   └── models/
│       ├── staging/               # 6 views — light cleaning + renaming
│       ├── intermediate/          # 16 tables — feature engineering (10 static + 4 seasonal + 2 ML)
│       └── marts/                 # 8 tables — final analytical outputs (5 static + 3 seasonal/ML)
├── orchestration/                 # Dagster definitions (90 assets)
│   ├── definitions.py             # Entry point: uv run dagster dev -m orchestration.definitions
│   ├── constants.py               # Re-exports from pipeline.config
│   └── assets/
│       ├── ingestion.py           # 14 assets: raw data downloads (incl. whale photos, audio, BIA, zones, CMIP6)
│       ├── database.py            # 2 assets: schema + data load
│       ├── aggregation.py         # 6 assets: H3, bathymetry, proximity, macro grid
│       ├── ml.py                  # 19 assets: feature extraction, SDM, ISDM, predictions, projections, audio, photo, validation
│       └── dbt_assets.py          # 49 assets: auto-generated from dbt manifest
├── backend/                       # FastAPI REST API (Phase 8)
│   ├── app.py                     # FastAPI entry point + lifespan + CORS
│   ├── config.py                  # API config (pagination, CORS, bbox limits)
│   ├── api/                       # Route modules (16: health, risk, species, traffic, layers, photo, audio, sightings, zones, auth, submissions, events, macro, violations, media, export)
│   ├── models/                    # Pydantic request/response schemas (14 modules incl. auth, submissions, events, macro)
│   └── services/                  # DB pool, query services, layers, classifiers, sightings, zones, auth, submissions, events, macro, reputation, obis_export
├── frontend/                      # Next.js 15 + deck.gl 9 dashboard (Phase 9)
│   ├── src/app/                   # 24 pages: /, /map, /report, /classify, /community, /verify, /auth, /profile, /submissions, /events, /insights (×5), /species, /users/[id], /boat/[id], etc.
│   ├── src/components/            # 26 components: MapView, Sidebar, Legend, CellDetail, IDHelper, SightingForm, PhotoClassifier, AudioClassifier, EventsPanel, etc.
│   ├── src/hooks/                 # useMacroData, useMapData (API data fetching + caching)
│   ├── src/contexts/              # AuthContext (JWT token management)
│   └── src/lib/                   # types, colors, api, utils
├── notebooks/                     # Jupyter exploration
├── docs/
│   ├── generate/                  # Diagram generation scripts
│   ├── diagrams/                  # Generated PNG/SVG outputs
│   └── pdfs/                      # Phase summary PDFs (fpdf2)
├── TODO.md                        # Centralised open-item tracker
└── tests/                         # 269 pytest tests (7 modules)
    ├── conftest.py                # Shared fixtures: mock DB, sample DataFrames, sine waveform
    ├── test_config.py             # Weight sums/keys, thresholds, seasons, geo, audio (44 tests)
    ├── test_utils.py              # to_python, bulk_insert, DB connection, SHAP patch (20 tests)
    ├── test_audio.py              # Segment, features, mel, bandpass, augmentation (19 tests)
    ├── test_analysis.py           # Binary metrics, spatial CV, plots (16 tests)
    ├── test_aggregation.py        # Haversine, Cartesian, H3 sampling, decay (14 tests)
    ├── test_validation.py         # Pandera schemas, quality reports (17 tests)
    └── test_backend.py            # FastAPI routes, services, layers, ML risk, sightings, zones, auth, submissions, macro, OBIS export (139 tests)
```

---

## 3. Infrastructure & Connections

| Component | Detail |
|---|---|
| **Database** | PostGIS 16-3.4 in Docker (`marine_risk_postgis`) |
| **Host/Port** | `localhost:5433` |
| **DB name** | `marine_risk` |
| **User / Password** | `marine` / `marine_dev` |
| **Python** | 3.12, managed by `uv` |
| **Package manager** | `uv` — use `uv add <pkg>` to add deps, `uv run` to execute |
| **dbt version** | 1.11.6 (dbt-postgres 1.10.0) |
| **Postgres tuning** | `shared_buffers=2GB`, `effective_cache_size=6GB`, `work_mem=128MB`, `max_parallel_workers_per_gather=0` (set in docker-compose command) |
| **Dagster** | 1.12.15 + dagster-dbt 0.28.15 — 90 assets, 6 jobs, multiprocess executor (max_concurrent=4) |
| **ML stack** | XGBoost 3.2.0, SHAP 0.49.1, Optuna 4.7.0, MLflow 3.10.0 |
| **Audio stack** | librosa 0.11.0, soundfile 0.13.1 (+ optional torch for CNN backend) |
| **API stack** | FastAPI 0.115+, uvicorn, python-multipart, Pydantic v2, slowapi (rate limiting), GZipMiddleware |
| **Frontend stack** | Next.js 15.2, React 19, TypeScript 5.7, deck.gl ~9.1.0, maplibre-gl 4.7, h3-js 4.2, Tailwind 3.4, Recharts |
| **Frontend .npmrc** | `legacy-peer-deps=true` (required for deck.gl peer dep conflicts) |
| **ML features** | `data/processed/ml/` — parquet files + `artifacts/` + `isdm_predictions/` |

### Critical: Running Commands

```bash
# Python scripts — always from project root:
uv run python pipeline/aggregation/compute_proximity.py

# dbt — always from transform/ directory:
cd transform
uv run dbt build --profiles-dir .
uv run dbt test --profiles-dir .
uv run dbt seed --profiles-dir .

# NEVER forget --profiles-dir . (profiles.yml is local, not in ~/.dbt/)

# Dagster — always from project root:
uv run dagster dev -m orchestration.definitions
# Then open http://127.0.0.1:3000

# Targeted refresh jobs (select root assets + all downstream):
# refresh_ais           — AIS → H3 agg → dbt
# refresh_sightings     — cetaceans → H3 → proximity → dbt
# refresh_covariates    — ocean covariates → DB load → dbt
# refresh_zones         — MPA + SMA + speed zones → DB → dbt
# refresh_all_ingestion — all ingestion + full downstream cascade

# FastAPI — always from project root:
uv run uvicorn backend.app:app --reload --port 8000
# Swagger UI: http://127.0.0.1:8000/docs

# Frontend — always from frontend/ directory:
cd frontend
npm install
npm run dev
# Then open http://localhost:3000
# API_BASE: http://localhost:8000 (configured in frontend/src/lib/api.ts)
```

---

## 4. Spatial Data Conventions

| Convention | Value |
|---|---|
| **H3 resolution** | 7 (~1.22 km edge length) |
| **H3 cell type** | BIGINT (not VARCHAR) |
| **Coordinate system** | WGS-84 (SRID 4326) everywhere |
| **Distance unit** | Kilometres (km) |
| **Geometry column** | Always `geom` in source tables |
| **Join key across all models** | `h3_cell` (BIGINT) |

---

## 5. dbt Layer Conventions

### Staging (`stg_*`) — Views
- **Purpose:** Light cleaning, renaming, type casting from raw sources.
- **Naming:** `stg_<source_table_name>.sql`
- **Materialisation:** `view`
- **Rules:**
  - One model per source table.
  - No joins between source tables — only single-source transforms. Exception: seeds (e.g., `stg_ship_strikes` joins `species_crosswalk`).
  - Handle pandas `'NaN'` strings: use `nullif(column, 'NaN')` — pandas writes literal string `'NaN'` not SQL NULL.
  - Expose `species_raw` (original) alongside cleaned columns.

### Intermediate (`int_*`) — Tables
- **Purpose:** Feature engineering, spatial joins, aggregations.
- **Naming:** `int_<domain>.sql`
- **Materialisation:** `table`
- **Rules:**
  - Can join staging models and sources freely.
  - `int_hex_grid` is the master grid (UNION of AIS + cetacean + strike cells = 1.9M cells).
  - All other intermediate models join to `int_hex_grid` via `h3_cell`.
  - Spatial operations with `ST_*` functions must use indexed source tables, never CTEs (CTEs have no GiST indexes → cross joins are catastrophically slow).

### Marts (`fct_*`) — Tables
- **Purpose:** Final analytical outputs, ML training datasets.
- **Naming:** `fct_<business_concept>.sql`
- **Materialisation:** `table`
- **Rules:**
  - Join intermediate models only (no raw source refs except where unavoidable like fct_species_risk).
  - All joins via `h3_cell` LEFT JOIN from `int_hex_grid` or `int_vessel_traffic`.
  - `fct_collision_risk` joins ALL 10 intermediate models.

### dbt Project Vars
`dbt_project.yml` is the **single source of truth** for all shared constants.
`pipeline/config.py` reads it via `yaml.safe_load()` at import time — no manual sync.
dbt macros read the same values via `{{ var('name') }}`.

Var categories (~70 vars total):
- Domain thresholds: `shelf_depth_m`, `slope_depth_m`, `cetacean_recent_year`
- Proximity decay: `proximity_whale_lambda`, `proximity_strike_lambda`, etc.
- V&T logistic: `vt_lethality_beta0`, `vt_lethality_beta1`
- Seasons: `season_winter_months`, etc.
- Composite risk weights: `risk_weight_*` (standard 7), `risk_ml_weight_*` (ML 7), `risk_ml_projected_weight_*` (projected 6 — no proximity)
- Sub-score internal weights: `traffic_w_*` (8), `cetacean_w_*` (3), `whale_ml_w_*` (3),
  `strike_w_*` (3), `habitat_w_bathymetry`/`habitat_w_ocean` (outer 2),
  `habitat_w_shelf`/`edge`/`depth_zone` (inner 3), `proximity_w_*` (3)
- Protection gap tiers: `protection_notake_and_sma` through `protection_none` (8)
  Proposed speed zones excluded (not real protection). SMAs (voluntary) downgraded.
- Risk thresholds: `risk_threshold_critical`/`high`/`medium`/`low` (4)

Season definitions (lists): winter=[12,1,2], spring=[3,4,5], summer=[6,7,8], fall=[9,10,11].

### Seeds
- **`species_crosswalk`** (138 rows): Global cetacean taxonomy with WoRMS identifiers. Bridges 3 naming systems — OBIS (`scientific_name`), Nisi ISDM (`nisi_species`), NMFS strikes (`strike_species`). 94 species + 28 genera + 13 families + 2 suborders + 1 order. Includes `aphia_id` (integer) and `worms_lsid` (LSID URI) for OBIS interoperability.
- Column type overrides: `is_baleen: boolean`, `aphia_id: integer` in `dbt_project.yml`.
- `scientific_name` is the unique key. `aphia_id` is unique + not_null.

---

## 6. Key Data Sources & Quirks

| Source | Rows | Notes |
|---|---|---|
| `ais_h3_summary` | 9.7M | Monthly vessel traffic. ~75 columns per cell-month (incl. V&T lethality, draft risk). |
| `cetacean_sightings` | ~1M | OBIS records. `species` column contains literal `'NaN'` strings from pandas — **must use `nullif()`**. |
| `cetacean_sighting_h3` | 120K | H3 assignment. FK: `sighting_id` → `cetacean_sightings.id`. |
| `ship_strikes` | 261 | NOAA PDF-parsed. Only 67 geocoded. Species values are lowercase short names: `'right'`, `'finback'`, `'humpback'`, `'unknown'` — **not** `'right whale'` or `'North Atlantic right whale'`. |
| `ship_strike_h3` | 67 | FK: `strike_id` → `ship_strikes.id`. |
| `nisi_risk_grid` | 47K | 1-degree global grid. Column is `all_risk` not `all_threat`. |
| `ocean_covariates` | 437K | Copernicus SST, MLD, SLA, PP. **Seasonal** (4 rows per location). Source is monthly NetCDF (2019-2024); `merge_to_parquet()` computes climatological seasonal means. |
| `right_whale_speed_zones` | 5 | **PROPOSED** zones, not active regulations. |
| `seasonal_management_areas` | 10 | **ACTIVE** SMAs from 50 CFR § 224.105. |
| `marine_protected_areas` | 926 | NOAA MPA Inventory polygons. Covers CONUS + Alaska + Hawaii. |
| `bathymetry_h3` | 1.9M | GEBCO bathymetry sampled at H3 centroids + vertices. |
| `cell_proximity` | 2.0M | 4 distance features from Python KDTree. |
| `cetacean_bia` | 85 | NOAA CetMap Biologically Important Areas (feeding, migratory, reproductive). Polygon geometries. |
| `whale_critical_habitat` | 31 | NMFS ESA-designated/proposed critical habitat for whale species. Polygon geometries. |
| `shipping_lanes` | 300 | NOAA Coast Survey shipping lanes, TSS, precautionary areas. Mixed polygon/line geometries. |
| `right_whale_slow_zones` | 6 | Active NOAA Fisheries DMAs with 10-knot speed restrictions. Polygon geometries. Scraped from web — count changes over time. |
| `whale_sdm_projections` | 58.1M | CMIP6 climate-projected whale habitat probabilities. Grain: (h3_cell, season, scenario, decade). 7 species cols (any, blue, fin, humpback, sperm, right, minke). PK: (h3_cell, season, scenario, decade). 2 scenarios × 4 decades × 4 seasons × 1.8M cells. |

---

## 7. Risk Model Architecture

### Standard Mart (`fct_collision_risk`, `fct_collision_risk_seasonal`)
Weighted composite from 7 sub-scores (all percentile-ranked, expert-elicited):

| Sub-score | Weight | Source |
|---|---|---|
| Traffic intensity | 25% | `int_vessel_traffic` (8 components: V&T lethality, draft, volume, vessel type, night) |
| Cetacean presence | 25% | `int_cetacean_density` (sightings, baleen, recent) |
| Proximity blend | 15% | `int_proximity` (whale×ship geometric mean 45%, strike 30%, protection gap 25%) |
| Strike history | 10% | `int_ship_strike_density` (effectively binary: 67 of 1.8M cells non-zero) |
| Habitat suitability | 10% | `int_bathymetry` 80% + ocean productivity PP 20% |
| Protection gap | 10% | `int_mpa_coverage` + `int_speed_zone_coverage` (tiered CASE) |
| Reference risk | 5% | `int_nisi_reference_risk` |

**Important scoring notes (documented in sub_scores.sql):**
- All scores are **relative** (percentile-ranked 0–1), not probabilities.
- Strike sub-score is effectively **binary** (67 non-zero cells).
- Proximity blend **intentionally overlaps** with density sub-scores (gradients vs magnitude).
- Weights are **expert-elicited** (V&T 2007, Rockwood 2021, Nisi 2024), not data-fitted.
- Habitat ocean weight (20% PP) informed by ISDM: PP ranks 5th–6th across species.

### ML-Enhanced Mart (`fct_collision_risk_ml`)
Replaces cetacean + habitat with **ISDM+SDM ensemble** whale predictions. 7 sub-scores:

| Sub-score | Weight | Source |
|---|---|---|
| Whale×traffic interaction | 30% | `P(any whale) × traffic_score` (Rockwood et al. 2021) |
| Traffic intensity | 15% | Same as standard |
| Whale ML exposure | 15% | ISDM+SDM ensemble probability percentiles (any/max/mean) |
| Proximity blend | 15% | Same as standard |
| Strike history | 10% | Same as standard |
| Protection gap | 10% | Same as standard |
| Reference risk | 5% | Same as standard |

**No habitat sub-score** in ML mart — both ISDM and SDM models were trained on env covariates
(SST, MLD, SLA, PP, depth, depth_range), so habitat is already encoded in P(whale).
This avoids double-counting and provides clean separation: standard mart uses expert-
elicited habitat, ML mart delegates habitat to learned species distributions.

**ISDM+SDM Ensemble approach (6 species):**
- **4 shared species** (blue, fin, humpback, sperm): `avg(ISDM, SDM)` — both models
  contribute complementary signal (ISDM from expert data, SDM from OBIS observations).
- **2 SDM-only species** (right whale, minke): SDM prediction used directly — ISDM
  does not cover these species (Nisi et al. trained on 4 species only).
- **Composites** from all 6: `any_whale_prob = 1 − ∏(1 − Pᵢ)`, `max_whale_prob`,
  `mean_whale_prob` computed over the 6 ensembled species.
- `has_ml_predictions` is TRUE if either ISDM or SDM data exists for the cell×season.
- Raw per-source columns (`isdm_*`, `sdm_*`) retained as diagnostic outputs alongside
  the ensembled species columns.

**Why ensemble both current and projected:** Using ISDM-only for current risk but
ISDM+SDM for projected would make the delta (projected − current) uninterpretable —
it would conflate model differences with climate signal. Consistent methodology
enables clean attribution of risk changes to climate projections.

### Climate-Projected ML Risk Mart (`fct_collision_risk_ml_projected`)
Projects ML-enhanced collision risk under CMIP6 climate scenarios. Grain:
`(h3_cell, season, scenario, decade)`. ~58M rows. **6 sub-scores** (no proximity):

| Sub-score | Weight | Source |
|---|---|---|
| Whale×traffic interaction | 35.29% | `P(any whale) × traffic_score` |
| Traffic intensity | 17.65% | Same as current |
| Whale ML exposure | 17.65% | ISDM+SDM ensemble projected probabilities |
| Strike history | 11.76% | Same as current |
| Protection gap | 11.76% | Same as current |
| Reference risk | 5.88% | Same as current |

**No proximity sub-score** — proximity is derived from observed sighting/strike locations
which don't exist for future decades. Weights are renormalised from the current ML
mart weights (÷ 0.85) so relative proportions are preserved.

**Projection dimensions:** 2 scenarios (SSP2-4.5, SSP5-8.5) × 4 decades (2030s, 2040s,
2060s, 2080s) × 4 seasons × 1.8M H3 cells. Ensemble uses ISDM+SDM projected
probabilities from `whale_isdm_projections` and `whale_sdm_projections` tables.

### Seasonal Variant (`fct_collision_risk_seasonal`)
Same 7-sub-score architecture at `(h3_cell, season)` grain. Four inputs vary by season:
traffic intensity, cetacean presence, speed zone coverage, and ocean covariates (habitat).
Static inputs (bathymetry, proximity, strike history, Nisi reference, MPA) are joined
without season key. `percent_rank()` uses `PARTITION BY season` so scores are
season-relative. The seasonal SDM mart (`fct_whale_sdm_seasonal`) deliberately **excludes**
traffic features to avoid detection bias.

### Proximity Decay Functions
- Whale/Ship: half-life 10 km (λ = 0.0693)
- Strike: half-life 25 km (λ = 0.0277)
- Protection: half-life 50 km (λ = 0.01386)

All decay constants, half-lives, and distance caps are defined in `pipeline/config.py`
(`PROXIMITY_HALF_LIFE_*`, `PROXIMITY_LAMBDA_*`, `PROXIMITY_*_CAP_KM`) and mirrored
as dbt `vars` in `dbt_project.yml` for the SQL models.

---

## 8. Seasonal Model Conventions

| Convention | Value |
|---|---|
| **Seasons** | winter=[12,1,2], spring=[3,4,5], summer=[6,7,8], fall=[9,10,11] |
| **Grain** | `(h3_cell, season)` — 4× the static row count |
| **Macro** | `{{ season_from_month('month_col') }}` — CASE expression returning season name |
| **Config source** | `pipeline/config.py` (`SEASONS`, `SEASON_ORDER`) mirrored as dbt `vars` |
| **Season-varying inputs** | traffic, cetacean density, speed zones, ocean covariates |
| **Static inputs** | bathymetry, proximity, strike history, Nisi reference, MPA coverage |
| **Scoring** | `percent_rank() PARTITION BY season` — season-relative percentile ranks |
| **SDM exclusions** | `fct_whale_sdm_seasonal` omits traffic (detection bias) and whale proximity (leakage) |

### Ocean Covariates Seasonal Pipeline
Raw data: monthly NetCDF files (2019–2024, 72 months) from NOAA ERDDAP + Copernicus.
`merge_to_parquet()` computes **climatological seasonal means** — averaging all Januaries,
Februaries, etc. into their respective seasons across all years. This produces 116K rows
(29K locations × 4 seasons). Verified seasonal signal: SST 10°C (winter) → 24°C (summer),
MLD 21m (winter) → 11m (summer).

---

## 9. Known Pitfalls & Anti-Patterns

### NEVER do these:

1. **Pandas NaN strings:** Raw tables loaded from pandas contain `'NaN'` as a literal string, not SQL NULL. Always use `nullif(column, 'NaN')` in staging models.

2. **Spatial joins on CTEs:** CTEs have no GiST spatial indexes. A `ST_DWithin` cross-lateral join on 1.9M rows × anything = minutes to hours. Use Python KDTree for proximity calculations, or ensure you're joining to indexed source tables.

3. **Docker shared memory OOM:** Large window functions with parallel workers exceed Docker's default shared memory. `docker-compose.yml` now has `shm_size: '2g'` and PG tuning in the `command:` block. If you see `could not resize shared memory segment` after a container rebuild, verify the compose settings are intact.

4. **Forgetting `--profiles-dir .`:** The dbt profiles.yml is inside `transform/`, not in `~/.dbt/`. Every dbt command needs `--profiles-dir .` or it will fail with a connection error.

5. **Column rename cascading:** If you rename a column in a staging model (e.g., `species` → `species_raw`), you MUST grep all downstream models for the old name. Use `grep -r "old_column_name" transform/models/` before committing.

6. **`string_agg(DISTINCT x, ',' ORDER BY x)`:** PostgreSQL does not allow `DISTINCT` and `ORDER BY` together in `string_agg` unless the ORDER BY column is the same as the DISTINCT column. Use `string_agg(distinct col, ',' order by col)`.

7. **Ship strike species matching:** Species values in `ship_strikes` are lowercase short names like `'right'`, `'finback'`, `'unknown'` — they do NOT contain `'right whale'`, `'humpback whale'`, etc. Use the `species_crosswalk` seed to map these.

8. **Running scripts from wrong directory:** Python scripts expect to run from the project root (`/Users/henryhall/Code/marine_risk_mapping/`). dbt commands expect to run from `transform/`. Getting this wrong produces confusing "file not found" errors.

9. **Nisi risk grid US bounding box:** `stg_nisi_risk_grid` hard-codes a geographic filter (`lat BETWEEN -2 AND 52, lon BETWEEN -180 AND -59`). Any analysis outside this box will silently return no Nisi reference risk data.

10. **SHAP + XGBoost 3.x incompatibility:** SHAP 0.49.1 crashes with XGBoost ≥3.0 due to removed `save_raw` parameter. Always call `patch_shap_for_xgboost3()` from `pipeline/utils.py` before creating a TreeExplainer.

11. **Seasonal features are one-hot encoded:** The seasonal parquet files contain `season_winter`, `season_spring`, `season_summer`, `season_fall` boolean columns — NOT a string `season` column. To reconstruct the season label, use `idxmax(axis=1)` on these columns.

12. **49% missing ocean covariates in scoring:** When ISDM models score the full H3 grid (7.3M rows), ~49% of cells lack Copernicus ocean covariate data (deep ocean/edge cells). These are filled with median values. This is expected and logged as a warning.

13. **Line length limit is 88 chars (ruff).** All generated Python code must respect the project's 88-character line limit. Break long strings, log messages, function signatures, and help text across multiple lines. Use implicit string concatenation (`"part one" "part two"`) for long log format strings.

14. **Pandas boolean comparisons: never use `== True` / `== False`.** Use `df[col]` for truth, `~df[col]` for false, or `.fillna(False).astype(bool)` when NaN is possible. Ruff rule E712.

15. **Forward-reference type annotations (`pd.DataFrame`, classifier classes).** If a type is only used in annotations and is not imported at module level, add it under `if TYPE_CHECKING:` block. Never use bare string annotations when `from __future__ import annotations` is active — ruff UP037 will flag them.

16. **Column name drift between Python and SQL.** When Python code queries a dbt mart column (e.g. `fct_collision_risk.risk_score`), verify the exact column name in the mart SQL. The column was previously named `composite_risk_score` during development but was renamed — the Python query in `classify.py` was not updated until the ruff cleanup caught it indirectly.

17. **Pandas 2.3 broke `select_dtypes(include=["str"])`.** Use `"object"` or `"string"` instead. The literal `"str"` was silently accepted pre-2.3 but now raises TypeError. Fixed in `pipeline/validation/quality_report.py`.

18. **Mocking `psycopg2.extras.execute_values` in tests.** Don't try to mock cursor internals (`mogrify`, `connection.encoding`). Instead, `patch("pipeline.utils.execute_values")` and assert call count / args. The real `execute_values` does byte-level string joining that MagicMock cannot satisfy.

19. **Pandas `df.where(pd.notnull(df), None)` does NOT convert NaN→None in float columns.** Pandas coerces `None` back to `NaN` for float-dtype columns. When writing DataFrames to PostgreSQL via `executemany`, you must convert NaN→None at the tuple level: `tuple(None if pd.isna(v) else v for v in row)`. Otherwise PostgreSQL stores IEEE-754 NaN (which passes `IS NOT NULL` but poisons `avg()`, `sum()`, etc.).

20. **Frontend `.npmrc` must have `legacy-peer-deps=true`.** deck.gl 9.x has peer dep conflicts with React 19 and luma.gl. Without this flag, `npm install` will fail. The `.npmrc` file is committed to the repo.

21. **Never pipe dbt build output through `| tail`, `| head`, `| grep`, etc.** dbt's interactive progress display does not work with pipes — the command hangs or produces garbled output. Always run `uv run dbt build --profiles-dir .` without any pipe. If running from Copilot, use `isBackground: true` for long builds.

22. **Avatar URLs must use `/api/v1/media/avatar/{user_id}` (singular, user_id).** The media endpoint is `GET /api/v1/media/avatar/{user_id}`. When building avatar URLs in API route helpers, always use the user's ID — never the filename. A previous bug in `_event_summary`/`_event_detail` used `/api/v1/media/avatars/{filename}` (plural + filename) which returned 404. Pydantic model validators handle this correctly via `avatar_filename` → URL conversion; avoid duplicating the logic in route helpers.

23. **H3 v4 requires string hex indices for `cell_to_latlng()`.** H3 cells are stored as int64 BIGINT throughout the project. The h3 v4 Python API (`cell_to_latlng`, `cell_to_boundary`, etc.) does NOT accept numpy int64 directly — it silently fails or raises TypeError. Always convert: `h3.cell_to_latlng(h3.int_to_str(int(cell)))`. The `int()` cast strips the numpy wrapper; `h3.int_to_str()` converts to hex string. A missing conversion in `score_future_sdm.py` caused all 1.8M centroids to silently fail inside a try/except.

24. **Never use emoji characters in frontend code.** Use SVG icon components from `@/components/icons/MarineIcons` instead. Emojis render inconsistently across platforms and break the design system's visual consistency. Available icons include `IconWhale`, `IconCheck`, `IconInfo`, `IconDownload`, `IconCamera`, `IconUsers`, `IconWarning`, `IconAlert`, etc.

25. **Never use `async def` for route handlers that call blocking (sync) code.** FastAPI runs `async def` handlers on the main event loop — if the handler calls sync DB queries, ML inference, or file I/O, it blocks the entire server. Use plain `def` instead; FastAPI automatically offloads `def` handlers to a thread pool. For file uploads, use `file.file.read()` (sync SpooledTemporaryFile) instead of `await file.read()`.

26. **Rate-limited endpoints require a `request: Request` parameter.** slowapi's `@limiter.limit()` decorator needs access to the `Request` object to extract the client IP. When adding rate limiting to a FastAPI endpoint, add `request: Request` as the first parameter after `self` (if any). Auth endpoints: 5/min (register), 10/min (login). Classification endpoints: 10/min. Sighting reports: 20/min.

### ALWAYS do these:

1. **After any model change:** Run `uv run dbt build --profiles-dir .` from `transform/` to verify no breakage.
2. **After renaming columns:** `grep -r "old_name" transform/models/` to find all references.
3. **After adding a new source table:** Add it to `sources.yml` with column descriptions.
4. **After adding a new model:** Add schema + tests to the appropriate `.yml` file (`stg_staging.yml`, `int_intermediate.yml`, or `mart_marts.yml`).
5. **For proximity features:** Use Python `scipy.spatial.cKDTree` (in `compute_proximity.py`), not SQL spatial joins.
6. **Test species joins:** The crosswalk `scientific_name` is the unique key. Strike joins go through `strike_species`. Sighting joins go through `scientific_name`.
7. **After editing Python files:** Run `uv run ruff check <file_or_folder>` and `uv run ruff format <file_or_folder>` to catch lint errors. Pre-commit hooks exist but only run on staged files — always verify manually after multi-file edits.
8. **After renaming a dbt column:** Also `grep -r "old_name" pipeline/` to catch Python code that queries the old column name directly (e.g. `classify.py`, `extract_features.py`).

---

## 10. Current Model Inventory

### Staging (6 views)
| Model | Source(s) |
|---|---|
| `stg_cetacean_sightings` | `cetacean_sightings` |
| `stg_ship_strikes` | `ship_strikes` + `species_crosswalk` (seed) |
| `stg_marine_protected_areas` | `marine_protected_areas` |
| `stg_speed_zones` | `right_whale_speed_zones` UNION `seasonal_management_areas` |
| `stg_ocean_covariates` | `ocean_covariates` |
| `stg_nisi_risk_grid` | `nisi_risk_grid` |

### Intermediate (16 tables — 10 static + 4 seasonal + 2 ML)
| Model | Row Count | Key Dependencies |
|---|---|---|
| `int_hex_grid` | 1.9M | Sources: ais_h3_summary, cetacean_sighting_h3, ship_strike_h3 |
| `int_vessel_traffic` | 9.7M | Source: ais_h3_summary |
| `int_cetacean_density` | 76K | Source: cetacean_sighting_h3 + stg_cetacean_sightings |
| `int_ship_strike_density` | 67 | Source: ship_strike_h3 + stg_ship_strikes |
| `int_bathymetry` | 1M | Source: bathymetry_h3 |
| `int_proximity` | 1.9M | Source: cell_proximity (9 cols: h3_cell + 4 distances + 4 decay scores) |
| `int_mpa_coverage` | 21K | int_hex_grid + stg_marine_protected_areas |
| `int_speed_zone_coverage` | 30K | int_hex_grid + stg_speed_zones |
| `int_ocean_covariates` | 1.1M | int_hex_grid + stg_ocean_covariates (annual mean from seasonal source) |
| `int_nisi_reference_risk` | 1.1M | int_hex_grid + stg_nisi_risk_grid |
| `int_ml_whale_predictions` | 7.3M | Source: ml_whale_predictions (ISDM scored grid) |
| `int_sdm_whale_predictions` | 7.3M | Source: ml_sdm_predictions (OBIS SDM OOF scored grid) |
| `int_vessel_traffic_seasonal` | 4.9M | Monthly AIS → (h3_cell, season) grain |
| `int_cetacean_density_seasonal` | 104K | Sightings → (h3_cell, season) via event_date month |
| `int_speed_zone_coverage_seasonal` | 87K | Active zones per season (handles year-wrapping) |
| `int_ocean_covariates_seasonal` | 4.4M | Spatial nearest-neighbour at (h3_cell, season) grain |

### Marts (9 tables — 5 static + 4 seasonal/ML)
| Model | Row Count | Key Dependencies |
|---|---|---|
| `fct_collision_risk` | 1.8M | ALL 10 static intermediate models |
| `fct_collision_risk_seasonal` | 7.3M | 4 seasonal + 6 static intermediates, percent_rank PARTITION BY season |
| `fct_collision_risk_ml` | 7.3M | ISDM+SDM ensemble + 4 seasonal + 5 static (7 sub-scores, 6 species) |
| `fct_collision_risk_ml_projected` | 58M | ISDM+SDM projected ensemble + sources (6 sub-scores, no proximity) |
| `fct_whale_sdm_training` | 1.8M | 9 intermediate models (no ship_strike_density) |
| `fct_whale_sdm_seasonal` | 7.3M | Seasonal SDM — no traffic features (detection bias), no whale proximity (leakage) |
| `fct_strike_risk_training` | 1.8M | ALL 10 intermediate models |
| `fct_species_risk` | 98K | stg_cetacean_sightings + species_crosswalk + 8 intermediate models |
| `fct_monthly_traffic` | 9.2M | 4 intermediate models |

### Seeds (1)
| Seed | Rows | Purpose |
|---|---|---|
| `species_crosswalk` | 138 | Global cetacean taxonomy + WoRMS AphiaIDs + OBIS/Nisi/NMFS naming bridge |

### Foreign Keys (database-level)
| FK Table | FK Column | → PK Table | PK Column |
|---|---|---|---|
| `cetacean_sighting_h3` | `sighting_id` | `cetacean_sightings` | `id` |
| `ship_strike_h3` | `strike_id` | `ship_strikes` | `id` |

---

## 11. Python Pipeline Scripts

### Shared modules
| Module | Purpose |
|---|---|
| `pipeline/config.py` | Reads scoring weights from `dbt_project.yml` via `yaml.safe_load()`. Also: `DB_CONFIG` (env vars), `H3_RESOLUTION`, `US_BBOX`, `US_BBOX_WIDE`, `VESSEL_TYPE_CODES`, `HIGH_SPEED_KNOTS`, proximity decay constants, `SEASONS` dict, `SEASON_ORDER`, 22 audio constants (`AUDIO_*`), CMIP6 constants (`CMIP6_DIR`, `CMIP6_PROJECTIONS_FILE`, `CMIP6_SCENARIOS`, `CMIP6_DECADES`, `SDM_PROJECTIONS_DIR`), all file paths incl. `BIA_FILE`, `CRITICAL_HABITAT_FILE`, `SHIPPING_LANES_FILE`, `SLOW_ZONES_FILE` |
| `pipeline/utils.py` | Shared helpers: `to_python()`, `bulk_insert()`, `assign_h3_cells()`, `get_connection()`, `table_row_count()` |

All pipeline scripts import from `pipeline.config` instead of defining their own constants.
`assign_cetacean_h3.py` and `assign_ship_strike_h3.py` both delegate to the generic `assign_h3_cells()` utility.
Ocean covariates use `US_BBOX_WIDE` (wider margin for interpolation); all other scripts use `US_BBOX`.

### Scripts

| Script | Purpose | Runtime |
|---|---|---|
| `pipeline/ingestion/download_ais.py` | Download AIS data from MarineCadastre | varies |
| `pipeline/ingestion/download_cetaceans.py` | Download OBIS cetacean records | ~minutes |
| `pipeline/ingestion/parse_ship_strikes.py` | Parse NOAA ship strike PDFs → 261 records | seconds |
| `pipeline/ingestion/download_nisi_2024.py` | Download Nisi et al. risk grid | seconds |
| `pipeline/ingestion/download_ocean_covariates.py` | Download Copernicus SST/MLD/SLA/PP + seasonal merge | ~minutes |
| `pipeline/ingestion/download_mpa.py` | Download NOAA MPA inventory | seconds |
| `pipeline/ingestion/download_sma.py` | Download NARW Seasonal Management Areas | seconds |
| `pipeline/ingestion/download_bia.py` | Download NOAA CetMap BIAs from ArcGIS FeatureServer (85 polygons) | seconds |
| `pipeline/ingestion/download_critical_habitat.py` | Download NMFS whale Critical Habitat from MapServer (31 polygons) | seconds |
| `pipeline/ingestion/download_shipping_lanes.py` | Download NOAA Coast Survey shipping lanes/TSS (300 features) | seconds |
| `pipeline/ingestion/download_slow_zones.py` | Scrape NOAA Fisheries active right whale DMAs (~6 zones) | seconds |
| `pipeline/ingestion/download_cmip6_projections.py` | Generate CMIP6 climate-projected ocean covariates (SSP2-4.5/SSP5-8.5, 2030s–2080s) | seconds |
| `pipeline/aggregation/aggregate_ais.py` | Aggregate 3.1B AIS pings → 9.7M H3 rows | ~hours |
| `pipeline/aggregation/assign_cetacean_h3.py` | Assign sightings to H3 cells | ~minutes |
| `pipeline/aggregation/assign_ship_strike_h3.py` | Assign strikes to H3 cells | seconds |
| `pipeline/aggregation/sample_bathymetry.py` | Sample GEBCO raster at H3 centroids | ~minutes |
| `pipeline/aggregation/compute_proximity.py` | KDTree nearest-neighbour (4 features) | ~4 min |
| `pipeline/aggregation/aggregate_macro_grid.py` | Aggregate H3 res-7 → res-4 macro overview (70,880 rows: 14,176 cells × 5 seasons) | ~2 min |
| `pipeline/database/load_data.py` | Load all data into PostGIS | varies |
| `pipeline/database/load_sdm_predictions.py` | Load SDM OOF predictions into ml_sdm_predictions table | seconds |
| `pipeline/database/load_sdm_projections.py` | Load CMIP6-projected SDM predictions into whale_sdm_projections table | seconds |
| `pipeline/database/create_schema.py` | Create/update PostGIS schema | seconds |
| `pipeline/database/duckdb_views.py` | DuckDB views over Parquet files for Jupyter | seconds |
| `pipeline/ingestion/upload_s3.py` | Upload data/ to S3 (`marine-risk-mapping-hh`) | varies |
| `pipeline/analysis/extract_features.py` | Extract ML features from dbt marts → parquet (SDM, seasonal, strike) | ~2 min |
| `pipeline/analysis/evaluate.py` | Shared evaluation: metrics, ROC/PR plots, calibration, spatial CV | (library) |
| `pipeline/analysis/train_sdm_model.py` | Train static whale SDM (XGBoost, 1.8M rows, 47 features) | ~3 min |
| `pipeline/analysis/train_sdm_seasonal.py` | Train seasonal SDM (7.3M rows, --target per-species, --score-grid) | ~5 min |
| `pipeline/analysis/train_strike_model.py` | Train strike-risk classifier (67 pos / 1.8M cells) | ~3 min |
| `pipeline/analysis/train_isdm_model.py` | Train ISDM models on Nisi data + score H3 grid (--score-grid) | ~2 min |
| `pipeline/analysis/score_future_sdm.py` | Score trained seasonal SDMs on CMIP6-projected covariates (--scenario, --decade) | ~3 min |
| `pipeline/analysis/compare_importances.py` | Compare ML feature importance vs hand-tuned risk weights | seconds |
| `pipeline/analysis/register_model.py` | MLflow model registry: find best run, register, promote | seconds |
| `pipeline/analysis/validate_traffic_risk.py` | Traffic risk validation: weight sums, Jensen's, Nisi correlation, sensitivity | ~5 min |
| `pipeline/analysis/train_audio_classifier.py` | Train whale audio species classifier (XGBoost or CNN) | varies |
| `pipeline/analysis/train_photo_classifier.py` | Train whale photo species classifier (EfficientNet-B4) | varies |
| `pipeline/analysis/train_arcface_classifier.py` | Train alternative ArcFace photo classifier (sub-centre ArcFace + GeM + KNN blend) | varies |
| `pipeline/analysis/train_arcface_remote.py` | Sync ArcFace training to an AWS/EC2 VM over SSH, run remotely, optionally pull artifacts back | varies |
| `pipeline/audio/preprocess.py` | Audio preprocessing: resample, segment, mel/PCEN, 64 acoustic features | (library) |
| `pipeline/audio/classify.py` | WhaleAudioClassifier: XGBoost + CNN backends, H3 risk enrichment | (library) |
| `pipeline/photo/preprocess.py` | Photo preprocessing: resize, normalize, augmentations, dataset class, EXIF GPS | (library) |
| `pipeline/photo/classify.py` | WhalePhotoClassifier: EfficientNet-B4 fine-tune, H3 risk enrichment | (library) |
| `pipeline/photo/arcface_classify.py` | ArcFacePhotoClassifier: timm backbone + GeM + sub-centre ArcFace + gallery KNN | (library) |
| `pipeline/ingestion/download_whale_photos.py` | Download Happywhale Kaggle dataset, filter to 8 target species | varies |
| `pipeline/ingestion/download_whale_audio.py` | Download Watkins (8 spp.) + Zenodo (3 datasets) + SanctSound catalogue | varies |
| `docs/generate/generate_audio_report.py` | Generate 17-page audio classification PDF (diagrams + report) | seconds |
| `docs/generate/generate_validation_report.py` | Generate 12-page scoring validation PDF with embedded plots | seconds |

---

## 12. Testing Checklist

Before considering any change complete:

- [ ] `uv run pytest tests/ -v` passes (251 tests, 0 failures)
- [ ] `uv run dbt build --profiles-dir .` passes (all models + 186 data tests, 0 errors)
- [ ] `uv run ruff check pipeline/ backend/ tests/` passes (0 errors) — run after EVERY Python edit
- [ ] `uv run ruff format pipeline/ backend/ tests/` applied — run after every Python edit
- [ ] If column renamed → `grep -r "old_name" transform/models/` AND `grep -r "old_name" pipeline/` return 0 hits
- [ ] If new model added → schema + tests in appropriate `.yml` file
- [ ] If new source table → entry in `sources.yml`
- [ ] If proximity logic changed → rerun `compute_proximity.py` and then dbt build
- [ ] If species mapping changed → update `species_crosswalk.csv` and `dbt seed`
- [ ] If orchestration assets changed → `uv run dagster definitions validate -m orchestration.definitions`
- [ ] If change affects a documented area → regenerate the relevant PDF(s) (see § PDF report inventory)
---

## 13. ML / MLOps (Phase 7)

### Model Architecture
12 XGBoost binary classifiers trained with spatial block CV (H3 res-2, ~158 km blocks, 5 folds).
All logged to MLflow. Feature extraction pulls from dbt mart tables → parquet → train.

| Model family | Script | Experiment name | Key config |
|---|---|---|---|
| Static whale SDM | `train_sdm_model.py` | `whale_sdm` | 47 features, 1.8M rows |
| Seasonal SDM | `train_sdm_seasonal.py` | `whale_sdm_seasonal` | `--target` switches species |
| Strike risk (experimental) | `train_strike_model.py` | `strike_risk` | scale_pos_weight for 67/1.8M imbalance — parked, too few positives |
| ISDM (Nisi data) | `train_isdm_model.py` | `isdm_species_sdm` | 7 env covariates, `--score-grid` |
| Audio classifier | `train_audio_classifier.py` | `whale_audio_classifier` | XGBoost on 64 acoustic features or CNN on mel spectrograms |

### Per-species targets (seasonal SDM)
`--target` flag: `any_cetacean` (default), `right_whale_present`, `humpback_present`,
`fin_whale_present`, `blue_whale_present`, `sperm_whale_present`, `minke_whale_present`.

### Feature exclusions (detection bias)
- Whale SDMs exclude **traffic features** — survey effort correlates with shipping lanes.
- Whale SDMs exclude **whale proximity** — target leakage.
- Seasonal SDMs exclude **Nisi per-species risk** — reserved for validation.

### Key artefacts
| Path | Content |
|---|---|
| `data/processed/ml/whale_sdm_features.parquet` | 1.8M rows, static SDM features |
| `data/processed/ml/whale_sdm_seasonal_features.parquet` | 7.3M rows, seasonal features |
| `data/processed/ml/strike_risk_features.parquet` | 1.8M rows, strike features |
| `data/processed/ml/artifacts/<model>/` | ROC/PR plots, SHAP, feature importance CSVs |
| `data/processed/ml/isdm_predictions/` | 4 parquet files, ~53 MB each (grid-scored) |
| `data/processed/ml/sdm_projections/` | CMIP6-projected SDM parquets per species × scenario × decade |
| `data/raw/cmip6/cmip6_projections.parquet` | CMIP6 projected ocean covariates (baseline + deltas) |
| `data/processed/ml/audio_features.parquet` | Extracted acoustic features from training audio |
| `data/processed/ml/audio_classifier/` | XGBoost model (.json), CNN model (.pt), metadata JSON |
| `data/processed/ml/artifacts/audio_classifier/` | Confusion matrix, feature importance, classification reports |
| `data/processed/ml/artifacts/audio_classifier/diagrams/` | 7 generated diagrams (pipeline arch, training curves, etc.) |
| `data/raw/whale_audio/` | Training audio: 452 files across 8 species from Watkins + Zenodo |
| `mlruns/` | MLflow tracking store (file-based) |
| `docs/pdfs/phase7_machine_learning.pdf` | 64-page report with all diagnostics |
| `docs/pdfs/traffic_risk_methodology.pdf` | 15-page traffic risk V&T methodology report |
| `docs/pdfs/audio_classification.pdf` | 17-page audio classification report with all diagrams |
| `docs/pdfs/scoring_validation.pdf` | 12-page scoring validation report (8 checks, 6 plots) |

### Spatial CV implementation
`evaluate.py:spatial_cv_split()` assigns H3 cells to parent cells at res-2
and distributes blocks across 5 folds. For seasonal data, all 4 seasons for a
given cell always land in the same fold (spatial grouping, not temporal).

### Running ML commands
```bash
# All ML scripts run from project root
uv run python pipeline/analysis/extract_features.py --dataset all
uv run python pipeline/analysis/train_sdm_model.py [--tune]
uv run python pipeline/analysis/train_sdm_seasonal.py --target right_whale_present [--tune]
uv run python pipeline/analysis/train_strike_model.py [--tune]
uv run python pipeline/analysis/train_isdm_model.py [--score-grid] [--species blue_whale]
uv run python pipeline/analysis/compare_importances.py
uv run python pipeline/analysis/register_model.py --experiment whale_sdm --model-name whale_sdm_xgboost

# Audio classification pipeline
uv run python pipeline/ingestion/download_whale_audio.py --source all
uv run python pipeline/analysis/train_audio_classifier.py [--tune] [--backend cnn]
uv run python pipeline/analysis/validate_traffic_risk.py --section all
```

---

## 14. Audio Classification Pipeline

### Architecture
Two-stage system for classifying whale species from underwater audio recordings:
1. **Preprocessing** (`pipeline/audio/preprocess.py`): load -> resample to 16 kHz mono ->
   segment into 4s windows (2s hop) -> extract mel spectrogram, PCEN, and 64 acoustic features.
2. **Classification** (`pipeline/audio/classify.py`): XGBoost on feature vectors (default)
   or CNN (ResNet18) on mel-spectrogram images (requires torch).

### Folder organisation
- `pipeline/audio/` -- domain-specific **library** code (preprocessing + classifier classes)
- `pipeline/ingestion/download_whale_audio.py` -- follows ingestion convention (alongside download_ais, etc.)
- `pipeline/analysis/train_audio_classifier.py` -- follows analysis convention (alongside train_sdm_model, etc.)
- `docs/generate/generate_audio_report.py` -- generates 17-page PDF with 7 diagrams

### Target species (8 trained)
right_whale, humpback_whale, fin_whale, blue_whale, sperm_whale, minke_whale,
sei_whale, killer_whale.

### Training data
452 audio files across 8 species from 4 public databases -> 10,185 segments after
segmentation (4s windows, 2s hop). Raw file distribution is highly imbalanced
(1 sei whale file vs 179 killer whale files), but segment-level balancing resolves this.

### Three-stage class balancing (consistent across both backends)
1. **Segment cap** (`AUDIO_MAX_SEGMENTS_PER_SPECIES = 2000`): prevents large classes from dominating.
2. **Augmentation** (`AUDIO_AUGMENT_TARGET = 500`): time-stretch, pitch-shift, noise injection
   for species below 500 segments (killer, minke, sei).
3. **Inverse-frequency class weights**: `w_c = N / (C * n_c)` applied to loss function.

### Trained model results

| Model | Accuracy | Macro F1 | Training Time | Key Detail |
|---|---|---|---|---|
| **XGBoost** | 97.9% | 98.2% | 213.7 s | 5-fold stratified CV, 64 acoustic features |
| **CNN (ResNet18)** | 99.3% | 99.4% | 279.7 s | 80/20 split, early stop epoch 12 (best at 5), Apple MPS |

CNN outperforms XGBoost by +1.4% accuracy, particularly on fin/blue whale distinction.
XGBoost weakness: blue/fin confusion (F1 0.95/0.94). CNN resolves this (both >= 0.99).

### CNN early stopping
`AUDIO_CNN_EARLY_STOP_PATIENCE = 7` in `pipeline/config.py`. Tracks val macro F1;
resets counter on improvement, breaks when patience exhausted. Best model weights
restored automatically. Prevents overfitting observed at epoch 10 (val acc dropped to 90.8%).

### Top XGBoost features (by gain)
spectral_rolloff_mean (300), spectral_flatness_mean (149), mfcc_18_std (144),
mfcc_4_mean (123), mfcc_5_mean (95). Spectral shape features dominate because they
capture the fundamental frequency-range separation between species.

### Acoustic features (64 per segment)
MFCCs (20 x mean+std), spectral centroid/bandwidth/rolloff/flatness,
spectral contrast (7 bands), ZCR, RMS energy, dominant frequency,
temporal envelope (mean, std, skew, kurtosis).

### Species-specific frequency bands
Configured in `pipeline/config.py` `WHALE_FREQ_BANDS`. Used for optional
bandpass pre-filtering before feature extraction (e.g. 15-30 Hz for fin whale).

### Training data sources
| Source | Species | Files | Format |
|---|---|---|---|
| Watkins Marine Mammal Sound Database | 8 species (zip bundles) | ~370 | WAV/AIF |
| Zenodo 3624145 | Blue whale D/Z calls | 4 | WAV |
| Zenodo 4293955 | Humpback song units | 65 | WAV |
| Zenodo 8147524 | Fin whale 20 Hz pulses | 13 | WAV |

### Audio config constants (22 in pipeline/config.py)
`AUDIO_SAMPLE_RATE=16000`, `AUDIO_SEGMENT_DURATION=4.0`, `AUDIO_SEGMENT_HOP=2.0`,
`AUDIO_N_MELS=128`, `AUDIO_N_FFT=2048`, `AUDIO_HOP_LENGTH=512`, `AUDIO_N_MFCC=20`,
`AUDIO_FMIN=10`, `AUDIO_FMAX=8000`, `AUDIO_MAX_SEGMENTS_PER_SPECIES=2000`,
`AUDIO_AUGMENT_TARGET=500`, `AUDIO_CNN_EARLY_STOP_PATIENCE=7`,
`AUDIO_AUG_TIME_STRETCH_RANGE=(0.9,1.1)`, `AUDIO_AUG_PITCH_SHIFT_RANGE=(-2.0,2.0)`,
`AUDIO_AUG_NOISE_SNR_RANGE=(15.0,30.0)`, `AUDIO_AUG_TIME_SHIFT_FRACTION=0.25`.

### H3 risk enrichment
`classify_and_enrich(audio_path, lat, lon)` converts coordinates to an H3 cell
and joins to `fct_collision_risk` for spatial risk context alongside species predictions.

### API endpoint (Phase 8)
`POST /api/v1/audio/classify` — multipart audio upload (WAV/FLAC/MP3/AIF, max 100 MB)
+ **required** `(lat, lon)` (no EXIF in audio files).
Returns: per-segment species predictions (4s windows), dominant species across all
segments, confidence, and H3 cell risk summary (7 sub-scores) from `fct_collision_risk`.

---

## 15. Photo Classification Pipeline (Phase 7c)

### Goal
Classify whale species from user-submitted fluke, flank, and dorsal fin photographs.
7 target species (same as audio minus sperm whale, which is absent from Happywhale),
plus an 8th `other_cetacean` class (stratified sample from remaining ~19 Happywhale
species) for graceful rejection of non-target submissions. Sperm whales are deep
divers rarely surface-photographed with identifiable features, so the Happywhale
Kaggle dataset does not include them. Enriches predictions with H3 risk context
when GPS coordinates are available (EXIF or user-supplied).

### Architecture — Single-stage CNN
**One EfficientNet-B4** fine-tuned from ImageNet weights on all body views (fluke,
dorsal, flank) combined. No separate body-part detection stage. 8 output classes
(7 target species + `other_cetacean`).

**Why single-stage, not two-stage:**
- The Happywhale dataset has **no body-part annotations** — a two-stage pipeline
  would require manual labelling of thousands of images before training.
- Species-discriminative features differ by view (right whale callosities visible
  in head shots, humpback patterns on fluke undersides, fin whale chevrons on
  flank), but a CNN learns view-invariant representations automatically.
- Our task is 8-class **species** classification, not 15K-class individual re-ID
  (the original Kaggle competition task). Species is a much easier target —
  single-stage is sufficient.
- Two-stage would only add value if we later pursue individual re-identification
  (metric learning on embeddings), which can be layered on as a future extension.

### Model choice: EfficientNet-B4
- Best accuracy/parameter tradeoff for fine-grained image classification.
- 19M params (vs ResNet50's 25M) — trains faster, smaller checkpoint.
- `torchvision.models.efficientnet_b4(weights="IMAGENET1K_V1")` — already in deps.
- Replace classifier head with `nn.Linear(1792, 8)` for our 8 classes.
- Input resolution: 380×380 (EfficientNet-B4 native).

### Training data — Happywhale Kaggle dataset
| Property | Value |
|---|---|
| **Source** | `kaggle competitions download -c happy-whale-and-dolphin` |
| **Total images** | ~51K training (62 GB raw, JPG) |
| **Species in dataset** | 30 (whales + dolphins) |
| **Species we keep** | 7: right_whale, humpback, fin, blue, minke, sei, killer_whale (no sperm — absent from dataset) |
| **Known label fixes** | `globis` → `short_finned_pilot_whale`, `pilot_whale` → `short_finned_pilot_whale`, `kiler_whale` → `killer_whale`, `bottlenose_dolpin` → `bottlenose_dolphin`, `southern_right_whale` → `right_whale` |
| **Body views** | Mixed: fluke (tail underside), dorsal fin, flank, head — no view label |
| **Individual IDs** | 15K+ unique individuals (unused for species classification) |

We filter to our 7 target species, discard the other 19 (dolphins, pilot whales, etc.
— `southern_right_whale` is remapped to `right_whale` via label fix, not discarded).
Final yield: ~20K images across 8 classes after filtering and capping.

### Species-to-Kaggle label mapping
| Our species | Happywhale label(s) | Key visual features |
|---|---|---|
| right_whale | `right_whale` (fix: `southern_right_whale`) | Callosities on head, broad black fluke, no dorsal fin |
| humpback_whale | `humpback_whale` | Unique fluke underside patterns (black/white), knobby head |
| fin_whale | `fin_whale` | Asymmetric jaw coloring, chevron on right flank, tall dorsal |
| blue_whale | `blue_whale` | Mottled blue-grey, tiny dorsal far back, U-shaped head |
| minke_whale | `minke_whale` | White flipper bands, small pointed head, curved dorsal |
| sei_whale | `sei_whale` | Single central ridge, tall sickle dorsal, uniform dark grey |
| killer_whale | `killer_whale` (fix: `kiler_whale`) | Saddle patch, eye patch, tall dorsal (male) |

### Preprocessing pipeline
1. **Resize** to 380×380 (EfficientNet-B4 native resolution)
2. **Normalize** to ImageNet mean/std: `mean=[0.485, 0.456, 0.406]`, `std=[0.229, 0.224, 0.225]`
3. **Training augmentations**: random horizontal flip, random rotation (±15°),
   color jitter (brightness=0.2, contrast=0.2, saturation=0.2), random resized crop (0.8–1.0)
4. **Validation**: center crop + normalize only (no augmentation)

### Class balancing strategy (mirrors audio pipeline)
1. **Image cap per species** (`PHOTO_MAX_IMAGES_PER_SPECIES`): prevents dominant classes
   (likely humpback) from overwhelming training.
2. **Stratified `other_cetacean`**: ~250 images sampled per non-target species
   (`PHOTO_OTHER_PER_SPECIES_CAP`), pooled into one class for diverse rejection.
   19 non-target species contribute ~3,756 images total.
3. **Weighted random sampler**: inverse-frequency weights in DataLoader for balanced batches.
4. **Label smoothing** (0.1) in `CrossEntropyLoss`: regularises overconfident predictions,
   especially on rare species (sei, blue).

### Training config
| Parameter | Value |
|---|---|
| **Optimizer** | AdamW, lr=1e-4 (head), lr=1e-5 (backbone) — differential LR |
| **Scheduler** | CosineAnnealingLR, T_max=epochs |
| **Epochs** | 30 max, early stopping patience 7 (val macro F1) |
| **Batch size** | 32 (fits in ~6 GB VRAM / Apple MPS) |
| **Split** | 80/20 stratified by species |
| **Metric** | Macro F1 (primary), accuracy (secondary) |

### Folder organisation
```
pipeline/
  photo/
    preprocess.py    # Resize, normalize, augmentations, dataset class
    classify.py      # WhalePhotoClassifier: EfficientNet-B4 fine-tune + inference
pipeline/
  ingestion/
    download_whale_photos.py   # Kaggle API download + species filtering
  analysis/
    train_photo_classifier.py  # Training loop, evaluation, MLflow logging
```

### Config constants (in pipeline/config.py)
`PHOTO_IMAGE_SIZE=380`, `PHOTO_BATCH_SIZE=32`, `PHOTO_EPOCHS=30`,
`PHOTO_LR_HEAD=1e-4`, `PHOTO_LR_BACKBONE=1e-5`, `PHOTO_EARLY_STOP_PATIENCE=7`,
`PHOTO_LABEL_SMOOTHING=0.1`, `PHOTO_MAX_IMAGES_PER_SPECIES=5000`,
`PHOTO_OTHER_PER_SPECIES_CAP=250`,
`PHOTO_IMAGENET_MEAN=(0.485, 0.456, 0.406)`,
`PHOTO_IMAGENET_STD=(0.229, 0.224, 0.225)`.
`WHALE_PHOTO_TARGET_SPECIES` = 7 species (no sperm_whale).
`HAPPYWHALE_LABEL_FIXES` includes `southern_right_whale → right_whale`.

### Key artefacts
| Path | Content |
|---|---|
| `data/raw/whale_photos/` | Filtered Happywhale images (8 species) |
| `data/processed/ml/photo_classifier/` | EfficientNet-B4 checkpoint (.pt), class mapping JSON |
| `data/processed/ml/artifacts/photo_classifier/` | Confusion matrix, per-class metrics, sample predictions |

### H3 risk enrichment (same pattern as audio)
`classify_and_enrich(image_path, lat, lon)` extracts species prediction +
confidence, converts coordinates to H3 cell, joins to `fct_collision_risk`.
GPS may come from EXIF metadata (if geotagged) or user-supplied coordinates.

### API endpoint (Phase 8)
`POST /api/v1/photo/classify` — multipart image upload + optional `(lat, lon)`.
Returns: species probabilities, top prediction, confidence, and (if coords provided)
H3 cell risk summary from `fct_collision_risk`.

### Future extensions
- **Individual re-identification**: Metric learning (ArcFace loss) on embeddings from
  the species classifier's penultimate layer. Would require the full Happywhale
  individual_id labels and a retrieval index.
- **Body-part detection**: If individual re-ID is pursued, a YOLO or Faster-RCNN
  first stage to crop the animal region would improve accuracy.

---

## 16. Explanation & Phase Summary Mode

### During implementation:
- Explain **why** each technical decision was made in the chat, not just what was done.
- Highlight salient points: trade-offs, alternatives considered, scaling implications.
- When introducing a new tool or concept, give a concise "what it is and why we chose it" summary.
- **Do NOT embed these explanations in code docstrings.** Keep docstrings focused on what the code does. Explanations belong in chat and in the phase PDF.

### Phase completion PDF:
At the end of each phase, generate a styled PDF summary into `docs/pdfs/` using the same `ReportPDF` class and visual style as the existing reports (fpdf2, navy/teal theme). The PDF should cover:
1. **What we built** — architecture and key components.
2. **Why** — design decisions and trade-offs.
3. **How** — implementation highlights, code patterns.
4. **Challenges & solutions** — problems hit and how they were resolved.
5. **Key takeaways** — 5-10 bullet points to remember per phase.
6. **Key technologies** — tools, libraries, and patterns used.

Generator scripts go in `docs/generate/`, output PDFs in `docs/pdfs/`.

### PDF report inventory

| Generator | Output PDF | Covers |
|---|---|---|
| `generate_ais_aggregation_report.py` | `ais_aggregation_design.pdf` | AIS 3.1B-ping → H3 pipeline |
| `generate_audio_report.py` | `audio_classification.pdf` | 8-species whale audio classification |
| `generate_phase6_report.py` | `phase6_dagster_orchestration.pdf` | Dagster orchestration (90 assets) |
| `generate_phase7_report.py` | `phase7_machine_learning.pdf` | SDM, ISDM, strike ML pipeline |
| `generate_phase8_report.py` | `phase8_backend_api.pdf` | FastAPI backend (110 endpoints) |
| `generate_projections_report.py` | `climate_projections_ensemble.pdf` | CMIP6 + ISDM+SDM ensemble |
| `generate_sql_spatial_deep_dive.py` | `sql_spatial_deep_dive.pdf` | PostGIS / SQL internals |
| `generate_traffic_risk_report.py` | `traffic_risk_methodology.pdf` | V&T lethality, draft, literature |
| `generate_transformation_report.py` | `transformation_and_risk_model.pdf` | dbt layers + 7-sub-score risk model |
| `generate_validation_report.py` | `scoring_validation.pdf` | 8-check scoring validation |
| `generate_scalability_report.py` | `scalability_assessment.pdf` | 4-layer scalability audit (DB, API, frontend, infra) |
| `generate_competitive_analysis_report.py` | `competitive_analysis.pdf` | Citizen science platform competitive landscape (iNaturalist, Happywhale, Zooniverse, OBIS) |
| `generate_project_journey.py` | `project_journey.pdf` | Full project overview |
| `generate_progress_report.py` | `marine_risk_progress_report.pdf` | Early snapshot (superseded) |

### When to regenerate PDFs

PDFs are generated artefacts — they go **stale** when the underlying code or data
changes. After any material change, identify which report(s) are affected and either
update the generator script or regenerate the PDF:

- **Risk weights or sub-scores change** → `transformation_report`, `projections_report`
- **New/removed dbt models** → `transformation_report`
- **Dagster assets change** → `phase6_report`
- **ML model retrained or architecture changed** → `phase7_report`, `audio_report`
- **API endpoints added/removed** → `phase8_report`
- **Scoring validation updated** → `validation_report`
- **New phase completed** → create a new `generate_phase<N>_report.py`

To regenerate all PDFs at once:
```bash
for f in docs/generate/generate_*_report.py; do uv run python "$f"; done
```

---

## 17. Backend API (Phase 8)

### Architecture
FastAPI REST API serving collision risk data, species distributions, vessel traffic,
photo classification, and audio classification results from the dbt mart tables in PostGIS.

### Endpoints (96 total)

**Core risk & data (10 original):**

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | DB connectivity check |
| `GET` | `/api/v1/risk/zones` | Risk zone summaries (bbox, category/score filters, pagination) |
| `GET` | `/api/v1/risk/zones/stats` | Aggregate risk statistics for a bbox |
| `GET` | `/api/v1/risk/zones/{h3_cell}` | Full detail for a single H3 cell (76 fields) |
| `GET` | `/api/v1/risk/seasonal` | Seasonal risk zones (bbox + season filter) |
| `GET` | `/api/v1/species` | List species from crosswalk seed |
| `GET` | `/api/v1/species/risk` | Per-species risk cells (bbox + species_group filter) |
| `GET` | `/api/v1/traffic/monthly` | Monthly traffic (bbox + month_start/month_end) |
| `POST` | `/api/v1/photo/classify` | Multipart image upload + optional lat/lon → species + risk context |
| `POST` | `/api/v1/audio/classify` | Multipart audio upload + required lat/lon → segment predictions + risk context |

**Spatial layer overlays (13):**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/layers/bathymetry` | Bathymetry cells (bbox + depth_zone filter) |
| `GET` | `/api/v1/layers/ocean` | Ocean covariates: SST, MLD, SLA, PP (bbox + season) |
| `GET` | `/api/v1/layers/whale-predictions` | ISDM whale predictions (bbox + season + species + min_probability) |
| `GET` | `/api/v1/layers/sdm-predictions` | SDM (OBIS-trained) whale predictions — OOF spatial CV (bbox + season + species + min_probability) |
| `GET` | `/api/v1/layers/sdm-projections` | CMIP6 climate-projected whale habitat (scenario + decade + optional season/species/min_probability) |
| `GET` | `/api/v1/layers/sdm-projections/summary` | Projection summary stats across scenarios/decades (optional species filter) |
| `GET` | `/api/v1/layers/mpa` | MPA coverage cells (bbox) |
| `GET` | `/api/v1/layers/speed-zones` | Speed zone coverage (bbox + season) |
| `GET` | `/api/v1/layers/proximity` | Proximity distances & decay scores (bbox) |
| `GET` | `/api/v1/layers/nisi-risk` | Nisi reference risk grid (bbox) |
| `GET` | `/api/v1/layers/cetacean-density` | Cetacean sighting density (bbox + season + min_sightings) |
| `GET` | `/api/v1/layers/strike-density` | Ship strike density (bbox) |
| `GET` | `/api/v1/layers/traffic-density` | Vessel traffic density with 22 sub-metrics (bbox + season) |

**ML risk, breakdowns & comparison (5 new):**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/risk/ml` | ML-enhanced risk zones (bbox + season) |
| `GET` | `/api/v1/risk/ml/stats` | ML risk aggregate statistics (bbox + season) |
| `GET` | `/api/v1/risk/ml/{h3_cell}` | ML risk detail for one cell (season param) |
| `GET` | `/api/v1/risk/breakdown/{h3_cell}` | Full sub-score breakdown for one cell |
| `GET` | `/api/v1/risk/compare` | Standard vs ML side-by-side (bbox + season) |

**Seasonal species & traffic (2 new):**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/species/seasonal` | Seasonal cetacean density (bbox + season + min_sightings) |
| `GET` | `/api/v1/traffic/seasonal` | Seasonal traffic aggregates (bbox + season) |

**Sighting report (1 new):**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/sightings/report` | Multipart form: image + audio + species guess + interaction type + lat/lon → combined classifications, species assessment, risk summary, advisory |

**Zone geometry overlays (7):**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/zones/speed-zones/current` | Current SMAs with GeoJSON geometries |
| `GET` | `/api/v1/zones/speed-zones/proposed` | Proposed speed zones with GeoJSON geometries |
| `GET` | `/api/v1/zones/mpas` | Marine protected areas with GeoJSON geometries (bbox filter) |
| `GET` | `/api/v1/zones/bia` | Biologically Important Areas with GeoJSON geometries (bbox + species/type filter) |
| `GET` | `/api/v1/zones/critical-habitat` | Whale critical habitat polygons (optional species filter) |
| `GET` | `/api/v1/zones/shipping-lanes` | Shipping lanes, TSS, precautionary areas (bbox + zone_type filter) |
| `GET` | `/api/v1/zones/slow-zones` | Active right whale slow zones / DMAs |

**Authentication (6):**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | User registration (bcrypt password hashing) |
| `POST` | `/api/v1/auth/login` | JWT token login |
| `GET` | `/api/v1/auth/me` | Current user profile (requires auth) |
| `GET` | `/api/v1/auth/users/{user_id}` | Public user profile |
| `GET` | `/api/v1/auth/users/{user_id}/reputation/history` | Reputation event history |
| `GET` | `/api/v1/auth/users/{user_id}/credentials` | User expertise credentials |

**Submissions & community (6):**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/submissions/mine` | Authenticated user's submissions |
| `GET` | `/api/v1/submissions/public` | Public community feed (verified sightings) |
| `GET` | `/api/v1/submissions/{id}` | Single submission detail |
| `PATCH` | `/api/v1/submissions/{id}/visibility` | Toggle submission public/private |
| `POST` | `/api/v1/submissions/{id}/verify` | Community verification (agree/disagree + optional species) |
| `GET` | `/api/v1/submissions/user/{user_id}` | Public submissions by a user |

**Macro overview (2):**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/macro/overview` | Coast-wide H3 res-4 pre-aggregated data (season filter) |
| `GET` | `/api/v1/macro/contours/bathymetry` | Bathymetry contour GeoJSON for map overlays |

**Violations (5):**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/violations` | Create vessel violation report |
| `GET` | `/api/v1/violations` | List violations (bbox + date filters) |
| `GET` | `/api/v1/violations/{id}` | Single violation detail |
| `PATCH` | `/api/v1/violations/{id}` | Update violation |
| `GET` | `/api/v1/violations/stats` | Violation statistics |

**Media (3):**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/media/upload` | Upload media file |
| `GET` | `/api/v1/media/{id}` | Get media metadata |
| `DELETE` | `/api/v1/media/{id}` | Delete media file |

**Community events (21):**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/events` | Create event (auto-generates invite code) |
| `GET` | `/api/v1/events` | List public events (status/type filter) |
| `GET` | `/api/v1/events/mine` | User's joined events |
| `POST` | `/api/v1/events/join/{invite_code}` | Join by invite |
| `GET` | `/api/v1/events/invite/{invite_code}` | Preview invite (no auth) |
| `GET` | `/api/v1/events/{id}` | Event detail with members |
| `PATCH` | `/api/v1/events/{id}` | Update event (creator/organizer) |
| `DELETE` | `/api/v1/events/{id}` | Delete event (creator only) |
| `POST` | `/api/v1/events/{id}/join` | Join public event |
| `DELETE` | `/api/v1/events/{id}/leave` | Leave event |
| `PATCH` | `/api/v1/events/{id}/members/{uid}/role` | Change member role |
| `GET` | `/api/v1/events/{id}/sightings` | Event's linked sightings |
| `POST` | `/api/v1/events/{id}/sightings/{sub_id}` | Link sighting to event |
| `DELETE` | `/api/v1/events/{id}/sightings/{sub_id}` | Unlink sighting |
| `GET` | `/api/v1/events/{id}/stats` | Event summary stats (species, contributors, risk) |
| `GET` | `/api/v1/events/{id}/comments` | List comments (oldest first) |
| `POST` | `/api/v1/events/{id}/comments` | Post comment |
| `PATCH` | `/api/v1/events/{id}/comments/{cid}` | Edit own comment |
| `DELETE` | `/api/v1/events/{id}/comments/{cid}` | Delete own comment |
| `POST` | `/api/v1/events/{id}/cover` | Upload cover photo (creator/organizer) |
| `GET` | `/api/v1/events/{id}/cover` | Serve cover image |

**Species crosswalk & cell context (2 additional):**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/species/crosswalk` | Full 138-row species crosswalk with AphiaIDs, worms_lsid |
| `GET` | `/api/v1/layers/context/{h3_cell}` | Cell ecological context (ISDM predictions, observed species, BIA/critical habitat overlaps) |

**OBIS data export (1):**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/export/obis` | Darwin Core Archive ZIP (occurrence.csv, emof.csv, meta.xml, eml.xml) from verified sightings |

### Layer structure
```
backend/
  app.py              ← FastAPI entry + lifespan (pool init/close) + CORS
  config.py           ← DATABASE_URL, pagination, CORS origins, bbox limits
  api/                ← Route modules (16 modules, thin: validation + response assembly)
    health.py         ← GET /health
    risk.py           ← 10 risk endpoints (zones, stats, detail, seasonal, ML×3, breakdown, compare)
    species.py        ← 4 species endpoints (list, risk, seasonal, crosswalk)
    traffic.py        ← 2 traffic endpoints (monthly, seasonal)
    layers.py         ← 12 layer overlay endpoints (+traffic-density, +cell context)
    photo.py          ← 1 photo endpoint
    audio.py          ← 1 audio endpoint
    sightings.py      ← 1 sighting report endpoint (combined photo+audio+risk form, +event_id linking)
    zones.py          ← 7 zone geometry endpoints (current SMAs, proposed zones, MPAs, BIAs, critical habitat, shipping lanes, slow zones)
    auth.py           ← 9 auth endpoints (register, login, me, user profile, reputation, credentials, user management)
    submissions.py    ← 14 submission endpoints (mine, public, detail, visibility, verify, by-user, etc.)
    events.py         ← 21 event endpoints (CRUD, membership, sighting linking, comments, cover, stats)
    macro.py          ← 2 macro overview endpoints (coast-wide res-4 grid, bathymetry contours)
    violations.py     ← 5 violation endpoints (CRUD, stats)
    media.py          ← 3 media endpoints (upload, get, delete)
    export.py         ← 1 OBIS DwC-A export endpoint (verified sightings → ZIP)
  models/             ← Pydantic v2 schemas (14 modules)
    common.py         ← BBox, PaginationParams, PaginatedResponse
    risk.py           ← RiskScores, RiskFlags, RiskZoneSummary/Detail, Seasonal, Stats
    species.py        ← SpeciesInfo, SpeciesRiskCell, CrosswalkEntry, CrosswalkResponse
    traffic.py        ← MonthlyTrafficCell, list response
    layers.py         ← 30+ schemas: per-layer cells, ML risk, breakdown, compare, seasonal, TrafficDensityCell, SdmProjectionCell
    photo.py          ← PhotoClassificationResult, RiskContext, response
    audio.py          ← AudioSegmentResult, AudioRiskContext, AudioClassificationResponse
    sightings.py      ← SightingReportResponse, SpeciesAssessment, RiskAdvisory, InteractionType
    zones.py          ← GeoJSON feature schemas: SpeedZoneFeature, MPAFeature, BIA, CriticalHabitat, ShippingLane, SlowZone, responses
    auth.py           ← UserCreate, UserLogin, UserResponse, TokenResponse
    submissions.py    ← SubmissionResponse, VerificationRequest, visibility schemas
    events.py         ← EventCreate/Update, EventSummary/Detail, EventMember, EventComment, EventStats
    macro.py          ← MacroCell (31 fields incl. 6 traffic sub-metrics), MacroResponse
    violations.py     ← ViolationCreate, ViolationResponse, ViolationStats
  services/           ← Business logic + DB queries (return plain dicts)
    database.py       ← ThreadedConnectionPool (min=4, max=30), fetch_all/one/scalar
    risk.py           ← fct_collision_risk + fct_collision_risk_seasonal queries
    species.py        ← species_crosswalk + fct_species_risk queries + list_crosswalk()
    traffic.py        ← fct_monthly_traffic queries
    layers.py         ← 12 layer + ML risk + breakdown + compare + seasonal + cell context + SDM projection queries
    photo.py          ← Lazy-loaded WhalePhotoClassifier singleton
    audio.py          ← Lazy-loaded WhaleAudioClassifier singleton
    sightings.py      ← Orchestrates photo+audio classifiers, risk lookup, advisory generation
    zones.py          ← ST_AsGeoJSON queries for speed zones, MPAs, BIAs, critical habitat, shipping lanes, slow zones
    auth.py           ← User registration, JWT login, bcrypt hashing, profile queries
    submissions.py    ← Sighting submission CRUD, community verification, visibility
    events.py         ← Event CRUD, membership, sighting linking, comments, cover upload, stats
    macro.py          ← Pre-aggregated macro_risk_overview queries (H3 res-4)
    reputation.py     ← Reputation scoring engine (event-based, tier progression)
    violations.py     ← Violation CRUD + statistics queries
    media.py          ← Media file upload + metadata management
    obis_export.py    ← Darwin Core Archive generation (occurrence + eMoF + meta.xml + eml.xml)
```

### Running the API
```bash
# From project root:
uv run uvicorn backend.app:app --reload --port 8000
# Or:
uv run python -m backend.app

# Swagger UI: http://127.0.0.1:8000/docs
# ReDoc:      http://127.0.0.1:8000/redoc
```

### Key patterns
- **Bbox validation**: All spatial endpoints require `lat_min < lat_max`, `lon_min < lon_max`,
  and area ≤ 100 deg² (`MAX_BBOX_AREA_DEG2`). Enforced in route handlers.
- **Pagination**: `limit` (default 100, max 5000) + `offset` on all list endpoints.
- **DB pool**: `psycopg2.pool.ThreadedConnectionPool` (2–10 connections), initialised in
  FastAPI lifespan, closed on shutdown. All queries use `RealDictCursor` → dicts.
- **Service layer returns dicts**: Route handlers construct Pydantic models from dicts.
  This keeps services independent of Pydantic and testable in isolation.
- **Photo classifier**: Lazy-loaded singleton in `services/photo.py`. First request loads
  the EfficientNet-B4 checkpoint. `File()` default triggers ruff B008 — suppressed with noqa.
- **Audio classifier**: Lazy-loaded singleton in `services/audio.py`. Wraps `WhaleAudioClassifier`
  from `pipeline.audio.classify`. GPS coordinates are **required** (no EXIF in audio). Returns
  segment-level predictions (4s windows, 2s hop) + dominant species + 7-sub-score risk context.
  Accepts WAV/FLAC/MP3/AIF up to 100 MB.
- **CORS**: Allows `localhost:3000` (Next.js) and `localhost:5173` (Vite) dev servers.
- **Macro overview**: Pre-aggregated `macro_risk_overview` table (H3 res-4, ~14,176 cells × 5 seasons
  = 70,880 rows) for coast-wide heatmap rendering without loading 1.8M res-7 cells. Generated by
  `pipeline/aggregation/aggregate_macro_grid.py`. In-memory TTL cache (5 min) in
  `backend/services/macro.py` keyed by `(season, scenario, decade)`. Includes 6 traffic sub-metrics:
  `avg_monthly_vessels`, `avg_speed_lethality`, `avg_high_speed_fraction`,
  `avg_draft_risk_fraction`, `night_traffic_ratio`, `avg_commercial_vessels`.
- **Auth**: JWT-based authentication with bcrypt password hashing. Tokens issued on login,
  verified via `Authorization: Bearer <token>` header. Users table in PostGIS.
- **Submissions**: Sighting reports stored with photo/audio classification results,
  GPS coordinates, species predictions. Community verification system with
  agree/disagree votes and reputation scoring. Biological observation fields
  (behavior, life_stage, calf_present, sea_state_beaufort, observation_platform,
  coordinate_uncertainty_m, sighting_datetime, scientific_name, aphia_id)
  collected for Darwin Core export. Species resolution maps model species or
  user guess → `scientific_name` + `aphia_id` via crosswalk lookup on save.
- **OBIS DwC-A export**: `GET /api/v1/export/obis` generates a Darwin Core Archive ZIP
  from verified sighting submissions. Archive contains `occurrence.csv` (18 DwC terms),
  `extendedMeasurementOrFact.csv` (sea state, group size, platform with NERC/BODC vocabulary
  URIs), `meta.xml` (archive descriptor), and `eml.xml` (dataset metadata, CC-BY 4.0).
  Optional `since`/`until` datetime query params for date-range filtering.
- **Community events**: `community_events` + `event_members` + `event_comments` tables.
  Events have invite codes, cover photos (`data/uploads/event_covers/{event_id}/`),
  and sighting linking (`sighting_submissions.event_id` FK). Stats endpoint computes
  species breakdown, top contributors, risk aggregates. Comments are public.
  DB: 51 migrations total (includes biological observation fields on sighting_submissions). Avatar URLs resolved via Pydantic `model_validator`s
  converting `avatar_filename` → `/api/v1/media/avatar/{user_id}`.
  Sighting report form accepts optional `event_id` Form param for auto-linking.

---

## 18. Frontend Dashboard (Phase 9)

### Architecture
Next.js 15 (App Router) + React 19 + deck.gl 9 + MapLibre GL for interactive
geospatial data visualization of whale–vessel collision risk.

### Key dependencies
`next@15.2`, `react@19`, `deck.gl@~9.1.0` (core, layers, geo-layers, aggregation-layers,
react), `@luma.gl@~9.1.0` (core, engine, webgl), `maplibre-gl@4.7`, `react-map-gl@7.1`,
`h3-js@4.2`, `tailwindcss@3.4`, `recharts`.

### Page routes (24)
| Route | Purpose |
|---|---|
| `/` | Landing page with animated ocean scene, stats, feature cards, sub-score breakdown |
| `/map` | Main interactive map (heatmap + detail hex + cell detail panel) |
| `/insights` | Risk analytics report with charts and breakdowns |
| `/insights/researchers` | Researcher-focused analytics (ISDM, SDM, spatial CV) |
| `/insights/captains` | Captain-focused route planning & risk summaries |
| `/insights/conservation` | Conservation-focused species & habitat analytics |
| `/insights/policy` | Policy-maker regulatory zone analysis |
| `/insights/ports` | Port-level traffic & risk summaries |
| `/species` | Species crosswalk reference (77 taxa, model coverage matrix, search/filter) |
| `/report` | Sighting report form (IDHelper wizard → species guess → photo + audio + GPS, optional `?event_id=` linking) |
| `/report-vessel` | Vessel interaction/violation report |
| `/classify` | Standalone photo/audio classification with runner-up predictions |
| `/verify` | Swipe-based quick review of unverified submissions (agree/disagree/refine) |
| `/events` | Redirect → `/community?tab=events` |
| `/events/[id]` | Event detail (cover photo, summary stats, sightings/members tabs, comments, link/report sighting) |
| `/events/join/[code]` | Join event via invite code |
| `/community` | Unified community hub: tabbed UI (Interactions sightings feed / Events list via `?tab=events`) |
| `/auth` | JWT login + registration |
| `/profile` | Authenticated user profile + submission history |
| `/submissions` | User's own submissions management |
| `/submissions/[id]` | Single submission detail |
| `/users/[id]` | Public user profile with sighting history |
| `/boat/[id]` | Registered vessel detail |
| `/attribution` | Data source attribution & licences |
| `/privacy` | Privacy policy |

### Map architecture (dual-resolution)
- **Overview (zoomed out)**: `HeatmapLayer` renders pre-aggregated H3 res-4 macro data
  (70,880 rows from `macro_risk_overview`). Cached per-season in a `Map<string, MacroCell[]>`.
  Weight field varies by active layer and selected metric (`getMacroWeightField()`).
  Color range varies by metric (`getHeatmapColorRange()`).
- **Detail (zoomed in)**: `H3HexagonLayer` renders individual H3 res-7 cells from the
  full-detail API endpoints. Fetched on viewport change with debouncing.
- **Zoom threshold**: Configured per-layer. Below threshold → heatmap; above → hex detail.
- **Contours**: Optional `GeoJsonLayer` for bathymetry depth contours.

### Layer system
11 switchable layers in `LayerType`: `risk`, `risk_ml`, `cetacean_density`,
`strike_density`, `whale_predictions`, `sdm_predictions`, `sdm_projections`,
`bathymetry`, `ocean`, `traffic_density`.

### GeoJSON zone overlays (8 toggles in Sidebar)
Active SMAs, proposed speed zones, MPAs, BIAs (teal), critical habitat (purple),
shipping lanes (blue), slow zones/DMAs (orange), depth contours.
Each renders as a `GeoJsonLayer` with tooltips showing zone-specific metadata.
BIA + shipping lanes require bbox (skipped when zoomed out); critical habitat
and slow zones fetch once (small datasets, no bbox).

### Traffic density sub-metrics (6)
`TrafficMetric` type: `vessel_density`, `speed_lethality`, `high_speed`, `draft_risk`,
`night_traffic`, `commercial`. Each has a distinct color ramp in the heatmap and maps
to a specific field in both macro data and detail API responses.

### Components (26)
`MapView` (main map + layers + 8 GeoJSON zone overlays), `Sidebar` (layer/season/metric/overlay controls),
`Legend` (dynamic per-layer), `CellDetail` (click-to-inspect panel with expandable metric explanations,
species/habitat context from ISDM + BIA + critical habitat),
`Nav` (7 links: Risk Map, Insights, Species, Classify, Interactions, Violations, Community),
`EventsPanel` (extracted events list with filters/pagination/create modal — rendered in community page Events tab),
`IDHelper` (multi-step species ID wizard — see below), `SightingForm` (report form with species wizard + classifiers),
`PhotoClassifier` (standalone photo species classification), `AudioClassifier` (standalone audio species classification),
`AudioWaveform`, `LocationPin`, `SubmissionMap`, `CoverageMap`, `SightingGlobe`,
`SpeciesPicker`, `SlowZoneWarning`, `ZoneDetail`, `CommentSection`,
`CheckMyRisk`, `VesselManager`, `ViolationForm`, `UserAvatar`,
`CelebrationOverlay`, `CelebrationWhaleScene`, `RevealOnScroll`.

**IDHelper — Species Identification Wizard:**
Multi-step guided species ID embedded in the sighting report form (`/report`).
- **Step 1**: Choose animal type — whale / dolphin / porpoise / unsure. Category descriptions
  include field-guide-style behavioural cues and exception disclaimers (e.g. orca as largest
  dolphin, pygmy/dwarf sperm whales as small-bodied whales).
- **Step 2 (whales only)**: Baleen vs toothed sub-selection with side-by-side anatomy comparison,
  cropped transparent diagrams, 6-cue comparison panel (head shape, blowhole count, mouth, body, blow, size).
- **Step 3**: Region-aware species grid with search, photos, expandable detail cards
  (ID tips, range, taxonomy), and catch-all "unidentified" options per group.
- Data: `WIZARD_GROUPS` (4 groups, ~30 species), `SPECIES_ID_TIPS`, `SPECIES_RANGE`,
  `SPECIES_PHOTOS`, region inference from GPS coordinates.

**Classifier runner-up predictions (PhotoClassifier, AudioClassifier, SightingForm):**
All three classifier display components show the top prediction prominently, then:
- **Runner-ups** (2nd & 3rd choice): always visible with numbered rank bars.
  Close-margin detection (<15pp gap) highlights the bar in amber with a note
  "Close margin — only Xpp behind top pick".
- **Collapsible remaining species** (4th+): chevron toggle, collapsed by default.

**CellDetail enrichment:**
- `MetricExpanded`: Reusable collapsible metric rows with click-to-expand explanations
  (13 traffic density metrics, 5 ocean covariates, 4 bathymetry metrics)
- Species context section: lazy-fetches `GET /layers/context/{h3_cell}` on hex click,
  shows ISDM whale predictions, observed species (common names via crosswalk), BIA zones, critical habitat
- Season-aware: auto-refreshes when season changes, hidden for non-seasonal layers
  (`SEASONAL_LAYERS` set in Sidebar gates the season selector)

**Animation components (16 files in `src/components/animations/`):**
`OceanScene` (main Three.js canvas), `SwimmingWhale` (5 instances with behaviour FSM),
`StarField` (~1800 procedural stars with twinkle), `ShootingStars` (3-slot meteor system),
`WhaleBubbleTrails` (micro-bubbles trailing whale bodies), `GodRays` (24 animated light shafts),
`Bubbles` (80 ambient rising), `FloatingParticles` (200 marine snow),
`SplashSystem` (breach splash particles), `InteractiveWaterSurface` (GPU heightfield),
`CausticFloor`, `SurfaceSplash`, `CameraRig`, `MilkyWay` (value noise FBM + galactic dust).

### Data hooks
- `useMacroData(season)` — fetches + caches `macro_risk_overview` per season
- `useMapData(layer, bbox, season, ...)` — fetches detail hex data for visible viewport

### Frontend running commands
```bash
cd frontend
npm install          # respects .npmrc legacy-peer-deps=true
npm run dev          # http://localhost:3000
npm run build        # production build
npx tsc --noEmit     # type-check without emitting
```

---

## 19. Keeping This File Current

**This file must be updated whenever the project changes materially.**

### When to update:
- A new dbt model is added or removed → update § Model Inventory
- A new source table is added → update § Data Sources and § Model Inventory
- A new pipeline script is created → update § Python Pipeline Scripts
- A new known pitfall is discovered → add to § Known Pitfalls
- The risk model weights change → update § Risk Model Architecture
- Infrastructure changes (new DB, port, tuning) → update § Infrastructure
- Row counts change significantly after a data refresh → update counts in tables
- API endpoints added or removed → update § Backend API + regenerate `phase8_report`
- Frontend pages/components added → update § Frontend Dashboard
- A new PDF generator is created → update the PDF inventory in § Explanation & Phase Summary Mode

### How to update:
After completing a significant change, include a prompt like:

> "Update `.github/copilot-instructions.md` to reflect: [describe change]"

Or, at the end of a session:

> "Review all changes made this session and update copilot-instructions.md accordingly."

> "Check which PDF reports are affected by this session's changes and regenerate them."

### Self-check prompt (run periodically):
> "Read `.github/copilot-instructions.md` and compare it against the actual project state. List any discrepancies and fix them."

### Update format:
When updating this file, always:
1. Update the `Last updated` date at the top.
2. Keep the same section structure — add content within existing sections.
3. If a new section is needed, add it before § Keeping This File Current (always last).
4. Be concise — this file is loaded into every Copilot conversation, so brevity matters.

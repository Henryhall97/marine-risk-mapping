# 🐋 Marine Risk Mapping Platform

This is a platform for predicting and displaying areas of high risk for marine life on the US Coast.

## Overview


Tracking areas of high risk for whale-vessel collisions on the US Coast

Combining multiple data sources including: Ship AIS data, Whale sightings, marine protection zones and bathymetry data to identify at-risk areas.


## Architecture

```
External APIs/Files
        │
        ▼
  ┌───────────┐     ┌───────────┐     ┌───────────┐
  │ Ingestion │────▶│ S3 (Raw)  │────▶│ Dagster   │
  │ Scripts   │     │ + Parquet │     │ + dbt     │
  └───────────┘     └───────────┘     └─────┬─────┘
                                            │
                                            ▼
                                      ┌───────────┐
                                      │ PostGIS   │
                                      │ + DuckDB  │
                                      └─────┬─────┘
                                            │
                                            ▼
                                      ┌───────────┐
                                      │ FastAPI   │
                                      │ Backend   │
                                      └─────┬─────┘
                                            │
                                            ▼
                                      ┌───────────┐
                                      │ Next.js   │
                                      │ Frontend  │
                                      └───────────┘
```

### Data ingestion layer

Data is downloaded from external sources (AIS, whale sightings, bathymetry, protected zones), stored as parquet files and uploaded to S3

### Data transformation layer

Messy data is cleaned and transformed - standardising coordinates, handling missing values, joining across datasets. This is orchestrated with Dagster, using dbt to handle the SQL transformations, validating quality with Pandera, and landing the clean data in PostGIS.

AIS vessel traffic (3.1B pings) is too large for direct spatial joins. A DuckDB-based aggregation pipeline assigns each ping to an H3 hexagonal grid cell (resolution 7, ~1.2km) and produces ~66 traffic features per cell per month — including both ping-weighted (temporal exposure) and vessel-weighted (debiased) metrics. This two-pass approach removes AIS ping-rate bias where Class A transponders broadcast 15x more often than Class B. The aggregated output is written to parquet and loaded into PostGIS for spatial joins with cetacean and MPA data via dbt.

### API Layer

FastAPI sits between the database and anyone who wants the data, exposing endpoints for risk zones, whale sightings, and vessel traffic by region and date.

### Presentation layer

Next.js (React) frontend with Deck.gl for map rendering. Users see an interactive map with risk heatmaps, whale sighting markers, vessel tracks, and filters.



## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Package Management** | uv | Python dependency management and virtual environments |
| **Data Ingestion** | Python (httpx) | Download data from APIs and file sources |
| **Data Storage (Raw)** | AWS S3 + Parquet | Cloud storage for raw data in columnar format |
| **Data Storage (Analytical)** | DuckDB | Fast local analytical queries over Parquet files |
| **Spatial Aggregation** | H3 (Uber) | Hexagonal grid system for AIS traffic aggregation (res 7 ~1.2km) |
| **Data Storage (Spatial)** | PostgreSQL + PostGIS | Production database with spatial query support |
| **Data Transformation** | dbt (dbt-postgres) | SQL-based data transformation with built-in testing |
| **Data Quality** | Pandera | Schema validation and data contracts |
| **Orchestration** | Dagster | Pipeline scheduling, monitoring, and dependency management |
| **Analysis** | Pandas, GeoPandas | Tabular and spatial data manipulation |
| **Risk Model** | XGBoost, scikit-learn | Binary classification for collision risk prediction |
| **ML Experiment Tracking** | MLflow | Experiment logging, model registry, artifact storage |
| **Backend API** | FastAPI, Pydantic | REST API with automatic validation and documentation |
| **Frontend** | Next.js (React), TypeScript | Modern web application framework |
| **Mapping** | Deck.gl (react-map-gl) | High-performance geospatial map rendering |
| **Charts** | Recharts | Dashboard chart components |
| **Containerisation** | Docker, Docker Compose | Multi-service packaging and local orchestration |
| **CI/CD** | GitHub Actions | Automated testing and deployment |
| **Cloud** | AWS (S3, RDS, ECS) | Production hosting and storage |
| **Linting** | Ruff, ESLint | Code quality enforcement (Python and JavaScript) |
| **Testing** | pytest, Vitest | Unit and integration testing (Python and JavaScript) |


## 📊 Data Sources

| Dataset | Source | Format | Description |
|---------|--------|--------|-------------|
| AIS Vessel Tracking | MarineCadastre.gov | CSV | Historical vessel positions and metadata |
| Whale Sightings | OBIS (obis.org) | API/CSV | Marine species observation records |
| Ocean Bathymetry | GEBCO / ETOPO | NetCDF/GeoTIFF | Ocean depth and seafloor topography |
| Marine Protected Areas | NOAA MPA Inventory | Shapefile | Protection zone boundaries and regulations |
| Marine Animal Incidents | NOAA GARFO (InPort 46789) | PDF → CSV | 261 ship strike/entanglement records parsed and geocoded (67 with coords) |
| Right Whale Speed Zones | NOAA Fisheries | Shapefile | Proposed seasonal vessel speed restriction polygons |
| Nisi et al. 2024 Risk Grid | [GitHub: annanisi/Global_Whale_Ship](https://github.com/annanisi/Global_Whale_Ship) | CSV | 1° global grid — whale risk (V×D), hotspots, management gaps for 4 species |
| Nisi et al. 2024 Shipping Density | [GitHub: annanisi/Global_Whale_Ship](https://github.com/annanisi/Global_Whale_Ship) | CSV | 1° global shipping density index (64,800 cells) |
| Nisi et al. 2024 ISDM Training | [GitHub: annanisi/Global_Whale_Ship](https://github.com/annanisi/Global_Whale_Ship) | CSV | 548K presence/absence records for 4 whale species + 7 environmental covariates |

## � Manual Data Prerequisites

Most data is downloaded automatically by the ingestion scripts, but **three datasets must be acquired manually** before running the pipeline:

| Dataset | Source | Expected Path | Why Manual |
|---------|--------|---------------|------------|
| GEBCO Bathymetry | [gebco.net](https://www.gebco.net/data_and_products/gridded_bathymetry_data/) | `data/raw/bathymetry/gebco_2025_n49.0_s24.0_w-130.0_e-65.0.tif` | Requires licence acceptance; large extract emailed |
| Ship Strike PDF | [NOAA InPort 23127](https://www.fisheries.noaa.gov/inport/item/23127) | `data/raw/cetacean/noaa_23127_DS1.pdf` | No stable direct-download URL |
| OBIS Occurrences | `s3://obis-open-data/occurrence/` | `data/raw/occurrence/*.parquet` (~6,800 files) | 180 GB bulk export via AWS CLI |

See [docs/manual_data_acquisition.md](docs/manual_data_acquisition.md) for step-by-step instructions.

## �🚀 Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18+ (for frontend)
- Docker & Docker Compose
- PostgreSQL with PostGIS extension

### Installation

```bash
# Clone the repository
git clone https://github.com/Henryhall97/marine-risk-mapping.git
cd marine-risk-mapping


# Install Python dependencies
uv sync

# Lint and format
uv run ruff check .
uv run ruff format .
```

## � Project Structure

```
marine_risk_mapping/
├── pipeline/              # Python ingestion & validation code
│   ├── ingestion/         # Download scripts (AIS, cetaceans, MPA, bathymetry)
│   ├── database/          # PostGIS schema & data loading, DuckDB views
│   ├── aggregation/       # AIS H3 aggregation (DuckDB two-pass pipeline)
│   └── validation/        # Pandera schemas & data quality reports
├── transform/             # dbt project (SQL transformations)
│   ├── models/
│   │   ├── staging/       # Clean raw data (stg_ models)
│   │   ├── intermediate/  # Spatial joins (int_ models)
│   │   └── marts/         # Final risk scores (fct_/dim_ models)
│   ├── macros/            # Reusable SQL snippets
│   └── tests/             # Custom dbt tests
├── orchestration/         # Dagster project (scheduling & monitoring)
├── backend/               # FastAPI REST API
├── frontend/              # Next.js + Deck.gl dashboard
├── notebooks/             # Jupyter exploration notebooks
│   ├── data_ingestion/    # Data download & exploration
│   └── data_quality/      # Quality reports & visualisations
├── docker/                # Docker Compose & Dockerfiles
├── docs/                  # Design documents (PDF reports)
├── data/                  # Local data files (git-ignored)
│   ├── raw/               # Raw parquet files
│   ├── processed/         # Aggregated output (ais_h3_res7.parquet)
│   └── marine_risk.duckdb # DuckDB analytical database
└── tests/                 # Python unit & integration tests
```

## �📋 Project Status

### Phase 1: Project Setup

| Step | Task | Status |
|------|------|--------|
| 1.1 | Initialise repo with uv | ✅ |
| 1.2 | Create folder structure | ✅ |
| 1.3 | Set up Git and .gitignore | ✅ |
| 1.4 | Configure Ruff | ✅ |
| 1.5 | Write README | ✅ |
| 1.6 | Set up pre-commit hooks | ✅ |

### Phase 2: Data Acquisition

| Step | Task | Status |
|------|------|--------|
| 2.1 | Research and document data sources | ✅ |
| 2.2 | Write AIS download script | ✅ |
| 2.3 | Write whale sightings download script | ✅ |
| 2.4 | Write bathymetry download script | ✅ |
| 2.5 | Write MPA download script | ✅ |
| 2.6 | Store raw data as Parquet | ✅ |
| 2.7 | Upload to S3 | ✅ |
| 2.8 | Download Marine Animal Incident Database (ship strikes + entanglements) | ✅ |
| 2.9 | Download Nisi et al. 2024 data (risk grid, shipping density, ISDM training) | ✅ |
| 2.10 | Download Proposed Right Whale Speed Zone polygons | ✅ |
| 2.11 | Load ship strikes + Nisi data + speed zones into PostGIS (5 new tables) | ✅ |

### Phase 3: Database Setup

| Step | Task | Status |
|------|------|--------|
| 3.1 | Set up PostGIS locally with Docker | ✅ |
| 3.2 | Design schema for spatial data (8 tables + spatial indexes) | ✅ |
| 3.3 | Load raw data into PostGIS | ✅ |
| 3.4 | Set up DuckDB for analytical queries | ✅ |

### Phase 4: Data Quality

| Step | Task | Status |
|------|------|--------|
| 4.1 | Define Pandera schemas | ✅ |
| 4.2 | Add validation to ingestion pipeline | ✅ |
| 4.3 | Create data quality reports | ✅ |

### Phase 5: dbt Transformations

| Step | Task | Status |
|------|------|--------|
| 5.1 | Initialise dbt project | ✅ |
| 5.2 | Build staging models (12/12 tests passing) | ✅ |
| 5.3a | AIS H3 aggregation pipeline (two-pass) | ✅ |
| 5.3b | Build intermediate spatial join models | ✅ |
| 5.4 | Build mart models (risk scores) | ✅ |
| 5.5 | Add dbt tests | ✅ |
| 5.6 | Staging + intermediate models for incident data (ship strikes) | ✅ |
| 5.7 | Staging + intermediate models for Nisi risk & shipping density | ✅ |
| 5.8 | Staging + intermediate models for right whale speed zones | ✅ |
| 5.9 | Update fct_collision_risk with speed zone sub-score | ✅ |

### Phase 6: Pipeline Orchestration

| Step | Task | Status |
|------|------|--------|
| 6.1 | Dagster project scaffold (constants, definitions) | ✅ |
| 6.2 | Define Dagster assets for ingestion + dbt | ⬜ |
| 6.3 | Create schedules and sensors | ⬜ |
| 6.4 | Add monitoring and alerting | ⬜ |

### Phase 7: Risk Model & MLOps

| Step | Task | Status |
|------|------|--------|
| 7.1 | EDA: join incident locations to H3 grid, analyse feature distributions | ⬜ |
| 7.2 | Feature engineering: build training matrix from mart features + incident labels | ⬜ |
| 7.3 | Train binary classifier (XGBoost/LightGBM) with class-imbalance handling | ⬜ |
| 7.4 | Set up MLflow experiment tracking (params, metrics, artifacts) | ⬜ |
| 7.5 | Hyperparameter tuning with cross-validation, log to MLflow | ⬜ |
| 7.6 | Register best model in MLflow Model Registry (staging → production) | ⬜ |
| 7.7 | Add model_training Dagster asset (orchestrated retraining) | ⬜ |
| 7.8 | Compare learned feature importances vs hand-tuned weights | ⬜ |

### Phase 8: FastAPI Backend

| Step | Task | Status |
|------|------|--------|
| 8.1 | Set up FastAPI project structure | ⬜ |
| 8.2 | Build risk score endpoints | ⬜ |
| 8.3 | Build spatial query endpoints | ⬜ |
| 8.4 | Add authentication and rate limiting | ⬜ |
| 8.5 | Write API documentation | ⬜ |
| 8.6 | Whale sighting submission endpoint (POST /api/sightings) | ⬜ |

### Phase 9: Frontend Dashboard

| Step | Task | Status |
|------|------|--------|
| 9.1 | Initialise Next.js project | ⬜ |
| 9.2 | Build map component with Deck.gl | ⬜ |
| 9.3 | Add risk layer visualisation | ⬜ |
| 9.4 | Add filtering and controls | ⬜ |
| 9.5 | Style and polish UI | ⬜ |
| 9.6 | Crowdsourced whale sighting reporting (user submissions via map) | ⬜ |

### Phase 10: Testing

| Step | Task | Status |
|------|------|--------|
| 10.1 | Unit tests for pipeline | ⬜ |
| 10.2 | Integration tests for API | ⬜ |
| 10.3 | End-to-end tests | ⬜ |

### Phase 11: Containerisation & CI/CD

| Step | Task | Status |
|------|------|--------|
| 11.1 | Write Dockerfiles | ⬜ |
| 11.2 | Create Docker Compose config | ⬜ |
| 11.3 | Set up GitHub Actions workflows | ⬜ |

### Phase 12: Cloud Deployment

| Step | Task | Status |
|------|------|--------|
| 12.1 | Provision AWS resources | ⬜ |
| 12.2 | Deploy pipeline to ECS | ⬜ |
| 12.3 | Deploy API and frontend | ⬜ |
| 12.4 | Set up monitoring | ⬜ |

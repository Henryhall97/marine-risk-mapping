# 🐋 Marine Risk Mapping Platform

This is a platform for predicting and displaying areas of high risk for marine life on the US East Coast.

## Overview


Tracking areas of high risk for whale-vessel collisions on the US East Coast

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
| **Data Storage (Spatial)** | PostgreSQL + PostGIS | Production database with spatial query support |
| **Data Transformation** | dbt (dbt-postgres) | SQL-based data transformation with built-in testing |
| **Data Quality** | Pandera | Schema validation and data contracts |
| **Orchestration** | Dagster | Pipeline scheduling, monitoring, and dependency management |
| **Analysis** | Pandas, GeoPandas | Tabular and spatial data manipulation |
| **Risk Model** | GeoPandas, scikit-learn | Spatial feature engineering and risk scoring |
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

## 🚀 Getting Started

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

## 📋 Project Status

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
| 2.1 | Research and document data sources | ⬜ |
| 2.2 | Write AIS download script | ✅ |
| 2.3 | Write whale sightings download script | ⬜ |
| 2.4 | Write bathymetry download script | ⬜ |
| 2.5 | Write MPA download script | ⬜ |
| 2.6 | Store raw data as Parquet | ⬜ |
| 2.7 | Upload to S3 | ⬜ |

### Phase 3: Database Setup

| Step | Task | Status |
|------|------|--------|
| 3.1 | Set up PostGIS locally with Docker | ⬜ |
| 3.2 | Design schema for spatial data | ⬜ |
| 3.3 | Load raw data into PostGIS | ⬜ |
| 3.4 | Set up DuckDB for analytical queries | ⬜ |

### Phase 4: Data Quality

| Step | Task | Status |
|------|------|--------|
| 4.1 | Define Pandera schemas | ⬜ |
| 4.2 | Add validation to ingestion pipeline | ⬜ |
| 4.3 | Create data quality reports | ⬜ |

### Phase 5: dbt Transformations

| Step | Task | Status |
|------|------|--------|
| 5.1 | Initialise dbt project | ⬜ |
| 5.2 | Build staging models | ⬜ |
| 5.3 | Build intermediate spatial join models | ⬜ |
| 5.4 | Build mart models (risk scores) | ⬜ |
| 5.5 | Add dbt tests | ⬜ |

### Phase 6: Pipeline Orchestration

| Step | Task | Status |
|------|------|--------|
| 6.1 | Define Dagster assets | ⬜ |
| 6.2 | Create schedules and sensors | ⬜ |
| 6.3 | Add monitoring and alerting | ⬜ |

### Phase 7: Risk Model

| Step | Task | Status |
|------|------|--------|
| 7.1 | Exploratory spatial analysis in notebooks | ⬜ |
| 7.2 | Build risk scoring model | ⬜ |
| 7.3 | Validate and iterate | ⬜ |

### Phase 8: FastAPI Backend

| Step | Task | Status |
|------|------|--------|
| 8.1 | Set up FastAPI project structure | ⬜ |
| 8.2 | Build risk score endpoints | ⬜ |
| 8.3 | Build spatial query endpoints | ⬜ |
| 8.4 | Add authentication and rate limiting | ⬜ |
| 8.5 | Write API documentation | ⬜ |

### Phase 9: Frontend Dashboard

| Step | Task | Status |
|------|------|--------|
| 9.1 | Initialise Next.js project | ⬜ |
| 9.2 | Build map component with Deck.gl | ⬜ |
| 9.3 | Add risk layer visualisation | ⬜ |
| 9.4 | Add filtering and controls | ⬜ |
| 9.5 | Style and polish UI | ⬜ |

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

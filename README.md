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
| **Audio Classification** | librosa, soundfile, PyTorch | Whale species ID from underwater recordings (XGBoost + CNN) |
| **Photo Classification** | torchvision (EfficientNet-B4) | Whale species ID from fluke/dorsal/flank photos |
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


## 🤖 Machine Learning Models

Twelve XGBoost binary classifiers predict whale presence and collision risk across all US coastal waters, using spatial block cross-validation (H3 resolution 2, ~158 km blocks, 5 folds) and MLflow experiment tracking.

### Model Suite

| Model | Rows | Positives | AUC-ROC | Avg Precision | Purpose |
|-------|------|-----------|---------|---------------|---------|
| **Static SDM** | 1.8M | 76K (4.1%) | 0.952 ± 0.008 | 0.498 ± 0.118 | All-species cetacean presence (annual) |
| **Seasonal SDM** | 7.3M | 104K (1.4%) | 0.956 ± 0.009 | 0.257 ± 0.086 | All-species with seasonal environment |
| **Strike Risk** ⚠️ | 1.8M | 67 (0.004%) | 0.934 ± 0.012 | 0.002 ± 0.001 | Experimental — too few positives for production use |
| Right whale | 7.3M | 3,207 (0.04%) | 0.991 ± 0.003 | 0.068 ± 0.063 | Per-species seasonal SDM |
| Humpback | 7.3M | 20,618 (0.28%) | 0.987 ± 0.002 | 0.199 ± 0.080 | Per-species seasonal SDM |
| Fin whale | 7.3M | 9,948 (0.14%) | 0.982 ± 0.004 | 0.087 ± 0.043 | Per-species seasonal SDM |
| Blue whale | 7.3M | 3,529 (0.05%) | 0.980 ± 0.015 | 0.081 ± 0.059 | Per-species seasonal SDM |
| Sperm whale | 7.3M | 6,744 (0.09%) | 0.954 ± 0.016 | 0.034 ± 0.014 | Per-species seasonal SDM |
| Minke whale | 7.3M | 4,291 (0.06%) | 0.985 ± 0.005 | 0.081 ± 0.075 | Per-species seasonal SDM |
| ISDM Blue | 49K | 50/50 | 0.945 ± 0.001 | 0.945 ± 0.001 | Nisi et al. cross-validation |
| ISDM Fin | 180K | 50/50 | 0.934 ± 0.001 | 0.927 ± 0.001 | Nisi et al. cross-validation |
| ISDM Humpback | 272K | 50/50 | 0.971 ± 0.001 | 0.971 ± 0.000 | Nisi et al. cross-validation |
| ISDM Sperm | 47K | 50/50 | 0.940 ± 0.002 | 0.942 ± 0.002 | Nisi et al. cross-validation |

### Key Design Decisions

- **Spatial block CV:** H3 parent cells at resolution 2 (~158 km edge) prevent spatial autocorrelation leakage. All 4 seasons for a given cell always land in the same fold.
- **No traffic in SDMs:** Traffic features excluded from whale SDMs to avoid detection bias (survey effort correlates with shipping lanes).
- **SHAP explainability:** TreeExplainer with XGBoost 3.x compatibility patch generates per-feature importance and interaction effects.
- **ISDM grid scoring:** Nisi et al. models scored across our full H3 grid (7.3M cell-seasons) for independent validation.

### ML Scripts

```bash
# Feature extraction from dbt marts → parquet
uv run python pipeline/analysis/extract_features.py --dataset all

# Training (each includes 5-fold CV, SHAP, MLflow logging)
uv run python pipeline/analysis/train_sdm_model.py           # Static SDM
uv run python pipeline/analysis/train_sdm_seasonal.py        # Seasonal all-species
uv run python pipeline/analysis/train_sdm_seasonal.py \
    --target right_whale_present                              # Per-species
uv run python pipeline/analysis/train_strike_model.py        # Strike risk
uv run python pipeline/analysis/train_isdm_model.py          # ISDM + grid scoring

# Comparison and registry
uv run python pipeline/analysis/compare_importances.py       # ML vs hand-tuned weights
uv run python pipeline/analysis/register_model.py \
    --experiment whale_sdm --model-name whale_sdm_xgboost    # MLflow registry
```

### Audio Classification

Two complementary classifiers identify 8 cetacean species from underwater audio recordings, using a three-stage class balancing strategy (segment cap, augmentation, inverse-frequency weights) applied consistently across both backends.

| Model | Accuracy | Macro F1 | Method | Training Time |
|-------|----------|----------|--------|---------------|
| **XGBoost** | 97.9% | 98.2% | 5-fold stratified CV on 64 acoustic features | 213.7 s |
| **CNN (ResNet18)** | 99.3% | 99.4% | 80/20 split, mel spectrograms, early stopping | 279.7 s |

- **Training data:** 452 audio files from 4 public databases (Watkins, 3x Zenodo) across 8 species
- **Segments:** 10,185 after preprocessing (4s windows, 2s hop, capped at 2,000/species)
- **CNN detail:** Fine-tuned pretrained ResNet18, Apple MPS accelerated, early stopping (patience=7) at epoch 12 (best at epoch 5)
- **Key finding:** CNN resolves blue/fin whale confusion that limits XGBoost (both >= 0.99 F1 vs 0.95/0.94)

### Audio Classification Scripts

```bash
# Download training audio (Watkins + Zenodo + SanctSound catalogue)
uv run python pipeline/ingestion/download_whale_audio.py --source all

# Train species classifier (XGBoost on acoustic features, default)
uv run python pipeline/analysis/train_audio_classifier.py

# With hyperparameter tuning
uv run python pipeline/analysis/train_audio_classifier.py --tune

# CNN backend (requires torch + torchvision)
uv run python pipeline/analysis/train_audio_classifier.py --backend cnn --epochs 30
```

### Photo Classification

Single-stage EfficientNet-B4 fine-tuned from ImageNet weights classifies 8 whale species from user-submitted fluke, dorsal fin, and flank photographs, plus a 9th `other_cetacean` class (stratified from ~22 non-target Happywhale species) for graceful rejection of dolphin/porpoise submissions.  Trained on the [Happywhale](https://www.kaggle.com/c/happy-whale-and-dolphin) Kaggle dataset (~51K images across 30 species).

| Property | Value |
|----------|-------|
| **Architecture** | EfficientNet-B4 (19M params), classifier head → `nn.Linear(1792, 9)` |
| **Input resolution** | 380 × 380 (native B4 resolution) |
| **Optimizer** | AdamW, differential LR: 1e-4 (head), 1e-5 (backbone) |
| **Scheduler** | CosineAnnealingLR, early stopping patience 7 on val macro F1 |
| **Balancing** | Per-species image cap (5K) + stratified `other_cetacean` (250/species) + WeightedRandomSampler + label smoothing (0.1) |
| **Target species** | right, humpback, fin, blue, sperm, minke, sei, killer whale + `other_cetacean` |

**Why single-stage?** The Happywhale dataset has no body-part annotations — a two-stage pipeline (detect body part → classify species) would require manual labelling thousands of images.  A single CNN learns view-invariant features automatically, and 8-class species classification is a much easier target than 15K-class individual re-ID.

### Photo Classification Scripts

```bash
# Download and filter Happywhale training images (requires Kaggle API key)
uv run python pipeline/ingestion/download_whale_photos.py

# Train EfficientNet-B4 species classifier
uv run python pipeline/analysis/train_photo_classifier.py

# With Optuna hyperparameter tuning
uv run python pipeline/analysis/train_photo_classifier.py --tune

# Evaluate an existing model
uv run python pipeline/analysis/train_photo_classifier.py --evaluate-only
```

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
| Watkins Sound Database | [WHOI](https://whoicf2.whoi.edu/science/B/whalesounds/) | WAV/AIF | ~15K whale vocalisation clips across 8 target species |
| Zenodo Whale Audio | [Zenodo](https://zenodo.org/) | WAV | Annotated recordings: blue (3624145), humpback (4293955), fin (8147524) |
| Happywhale Photos | [Kaggle](https://www.kaggle.com/c/happy-whale-and-dolphin) | JPG + CSV | ~51K whale/dolphin photos; filtered to 8 target species for classification |

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
│   ├── ingestion/         # Download scripts (AIS, cetaceans, MPA, bathymetry, whale audio)
│   ├── database/          # PostGIS schema & data loading, DuckDB views
│   ├── aggregation/       # AIS H3 aggregation (DuckDB two-pass pipeline)
│   ├── audio/             # Whale audio classification (preprocessing + classifier)
│   ├── photo/             # Whale photo classification (EfficientNet-B4 + preprocessing)
│   ├── analysis/          # ML training, evaluation, validation scripts
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
| 6.2 | Define Dagster assets for ingestion + dbt | ✅ |
| 6.3 | Create schedules and sensors | ⬜ |
| 6.4 | Add monitoring and alerting | ⬜ |

### Phase 7: Risk Model & MLOps

| Step | Task | Status |
|------|------|--------|
| 7.1 | Feature engineering: extract SDM + strike training matrices from dbt marts | ✅ |
| 7.2 | Build evaluation harness (spatial block CV, SHAP, calibration, MLflow) | ✅ |
| 7.3 | Train static whale SDM (XGBoost, 1.8M rows, 47 features) | ✅ |
| 7.4 | Train seasonal all-species SDM (7.3M rows × 4 seasons) | ✅ |
| 7.5 | Train 6 per-species seasonal SDMs (right, humpback, fin, blue, sperm, minke) | ✅ |
| 7.6 | Train 4 ISDM cross-validation models (Nisi et al. data) + score H3 grid | ✅ |
| 7.7 | Train strike-risk classifier (67 positives / 1.8M cells) — experimental, parked | ✅ |
| 7.8 | Compare ML feature importance vs hand-tuned collision risk weights — limited utility (SDMs predict presence, not risk) | ⚠️ |
| 7.9 | MLflow model registry tooling (register, promote staging → production) | ✅ |
| 7.10 | Phase 7 PDF report (64 pages, diagnostic diagrams, critical assessment) | ✅ |

### Phase 7b: Audio Classification

| Step | Task | Status |
|------|------|--------|
| 7b.1 | Audio preprocessing pipeline (librosa: resample, segment, mel/PCEN, 64 features) | ✅ |
| 7b.2 | Classifier framework (XGBoost + CNN backends, H3 risk enrichment) | ✅ |
| 7b.3 | Training data download scripts (Watkins, Zenodo, SanctSound) | ✅ |
| 7b.4 | Training pipeline (stratified CV, Optuna, MLflow) | ✅ |
| 7b.5 | Download training data and train XGBoost model (97.9% accuracy, 98.2% F1) | ✅ |
| 7b.6 | Traffic risk V&T lethality methodology + validation | ✅ |
| 7b.7 | Train CNN classifier (99.3% accuracy, 99.4% F1, early stopping) | ✅ |
| 7b.8 | Audio classification PDF report (17 pages, 7 diagrams) | ✅ |

### Phase 7c: Photo Classification

| Step | Task | Status |
|------|------|--------|
| 7c.1 | Photo preprocessing pipeline (EfficientNet-B4 transforms, dataset class, EXIF GPS) | ✅ |
| 7c.2 | Classifier framework (EfficientNet-B4 fine-tune, H3 risk enrichment) | ✅ |
| 7c.3 | Training data download script (Happywhale Kaggle dataset) | ✅ |
| 7c.4 | Training pipeline (stratified split, differential LR, early stopping, MLflow) | ✅ |
| 7c.5 | Download training data and train model | ⬜ |
| 7c.6 | Photo classification PDF report | ⬜ |

### Phase 8: FastAPI Backend

| Step | Task | Status |
|------|------|--------|
| 8.1 | Set up FastAPI project structure (app, config, lifespan, CORS) | ✅ |
| 8.2 | Build risk score endpoints (4 routes: zones, stats, detail, seasonal) | ✅ |
| 8.3 | Build species + traffic + photo endpoints (4 routes) | ✅ |
| 8.4 | Pydantic models + service layer + DB pool | ✅ |
| 8.5 | Backend pytest suite (23 tests, all passing) | ✅ |
| 8.6 | Add authentication and rate limiting | ⬜ |
| 8.7 | Write API documentation | ⬜ |
| 8.8 | Whale sighting submission endpoint (POST /api/sightings) | ⬜ |

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

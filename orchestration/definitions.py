"""Dagster definitions — the single entry point for the orchestration layer.

Launch the Dagster UI with:
    cd /path/to/marine_risk_mapping
    uv run dagster dev -m orchestration.definitions

This wires together:
  - Ingestion assets (download raw data)
  - Database assets (schema creation + data loading)
  - Aggregation assets (H3 assignment, bathymetry, proximity)
  - dbt assets (staging → intermediate → marts)
  - A full-pipeline job for end-to-end runs
"""

from dagster import (
    AssetSelection,
    Definitions,
    define_asset_job,
    load_assets_from_modules,
)
from dagster_dbt import DbtCliResource

from orchestration.assets import aggregation, database, dbt_assets, ingestion, ml
from orchestration.assets.dbt_assets import TRANSFORM_DIR

# ── Assets ──────────────────────────────────────────────────
all_assets = load_assets_from_modules(
    [ingestion, database, aggregation, dbt_assets, ml],
)

# ── Resources ───────────────────────────────────────────────
# DbtCliResource tells dagster-dbt how to invoke the dbt CLI.
# profiles_dir must match the local profiles.yml location.
dbt_resource = DbtCliResource(
    project_dir=TRANSFORM_DIR,
    profiles_dir=TRANSFORM_DIR,
)

# ── Jobs ────────────────────────────────────────────────────
# Full pipeline: ingestion → database → aggregation → dbt
# Dagster resolves the execution order from asset dependencies.
full_pipeline_job = define_asset_job(
    name="full_pipeline",
    description=(
        "End-to-end pipeline: download data, load PostGIS, "
        "run aggregations, then dbt build."
    ),
)

# ── Targeted refresh jobs ───────────────────────────────────
# Each job selects a root ingestion asset and all its downstream
# dependents, so materialising cascades through DB load, H3
# aggregation, and dbt models automatically.

refresh_ais_job = define_asset_job(
    name="refresh_ais",
    description=(
        "Refresh AIS vessel traffic: re-download daily AIS files, "
        "reload PostGIS, re-aggregate H3, rebuild dbt models."
    ),
    selection=AssetSelection.assets(ingestion.raw_ais_data).downstream(),
)

refresh_sightings_job = define_asset_job(
    name="refresh_sightings",
    description=(
        "Refresh cetacean sightings: re-download OBIS data, "
        "reload PostGIS, re-assign H3, recompute proximity, "
        "rebuild dbt models."
    ),
    selection=AssetSelection.assets(ingestion.raw_cetacean_data).downstream(),
)

refresh_covariates_job = define_asset_job(
    name="refresh_covariates",
    description=(
        "Refresh ocean covariates: re-download SST/MLD/SLA/PP "
        "from ERDDAP + Copernicus, reload PostGIS, "
        "rebuild dbt models."
    ),
    selection=AssetSelection.assets(ingestion.raw_ocean_covariates).downstream(),
)

refresh_zones_job = define_asset_job(
    name="refresh_zones",
    description=(
        "Refresh protected zones: re-download MPAs, SMAs, and "
        "speed zones, reload PostGIS, rebuild dbt models."
    ),
    selection=(
        AssetSelection.assets(
            ingestion.raw_mpa_data,
            ingestion.raw_sma_data,
            ingestion.raw_speed_zones,
        ).downstream()
    ),
)

refresh_all_ingestion_job = define_asset_job(
    name="refresh_all_ingestion",
    description=(
        "Refresh ALL raw data sources and cascade through the "
        "entire pipeline (equivalent to full_pipeline but "
        "using --force on all ingestion scripts)."
    ),
    selection=AssetSelection.groups("ingestion").downstream(),
)

# ── Definitions ─────────────────────────────────────────────
defs = Definitions(
    assets=all_assets,
    resources={"dbt": dbt_resource},
    jobs=[
        full_pipeline_job,
        refresh_ais_job,
        refresh_sightings_job,
        refresh_covariates_job,
        refresh_zones_job,
        refresh_all_ingestion_job,
    ],
)

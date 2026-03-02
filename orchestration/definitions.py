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

from dagster import Definitions, define_asset_job, load_assets_from_modules
from dagster_dbt import DbtCliResource

from orchestration.assets import aggregation, database, dbt_assets, ingestion
from orchestration.assets.dbt_assets import TRANSFORM_DIR

# ── Assets ──────────────────────────────────────────────────
all_assets = load_assets_from_modules(
    [ingestion, database, aggregation, dbt_assets],
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

# ── Definitions ─────────────────────────────────────────────
defs = Definitions(
    assets=all_assets,
    resources={"dbt": dbt_resource},
    jobs=[full_pipeline_job],
)

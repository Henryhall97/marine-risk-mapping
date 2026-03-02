"""Database assets — schema creation and data loading.

These assets form the bridge between raw files on disk and the
PostGIS tables that dbt and the aggregation scripts read from.
"""

import subprocess

import psycopg2
from dagster import AssetExecutionContext, MaterializeResult, asset

from orchestration.constants import DB_CONFIG, PROJECT_ROOT


def _run_script(
    context: AssetExecutionContext,
    script: str,
) -> None:
    """Run a pipeline script from project root."""
    cmd = ["uv", "run", "python", script]
    context.log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if result.stdout:
        context.log.info(result.stdout)
    if result.stderr:
        context.log.warning(result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"{script} exited with code {result.returncode}")


def _get_table_counts() -> dict[str, int]:
    """Query row counts for all application tables."""
    tables = [
        "cetacean_sightings",
        "marine_protected_areas",
        "ship_strikes",
        "nisi_risk_grid",
        "nisi_shipping_density",
        "nisi_isdm_training",
        "right_whale_speed_zones",
        "ocean_covariates",
        "seasonal_management_areas",
    ]
    counts = {}
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        for table in tables:
            cur.execute(
                "SELECT EXISTS("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_name = %s"
                ");",
                (table,),
            )
            if cur.fetchone()[0]:
                cur.execute(f"SELECT COUNT(*) FROM {table};")
                counts[table] = cur.fetchone()[0]
            else:
                counts[table] = -1  # table missing
        cur.close()
    finally:
        conn.close()
    return counts


@asset(
    group_name="database",
    kinds={"postgres"},
    description=(
        "Create PostGIS tables and spatial indexes (IF NOT EXISTS — safe to re-run)."
    ),
)
def postgis_schema(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Run create_schema.py to ensure all tables exist."""
    _run_script(context, "pipeline/database/create_schema.py")
    return MaterializeResult(
        metadata={"status": "schema_created"},
    )


@asset(
    group_name="database",
    kinds={"postgres", "python"},
    deps=[
        "postgis_schema",
        "raw_cetacean_data",
        "raw_mpa_data",
        "raw_ship_strikes",
        "raw_nisi_data",
        "raw_ocean_covariates",
        "raw_sma_data",
        "raw_speed_zones",
    ],
    description=(
        "Load all raw data files into PostGIS tables. "
        "Skips tables that already contain rows."
    ),
)
def postgis_raw_data(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Run load_data.py to populate PostGIS from parquet/CSV/shp."""
    _run_script(context, "pipeline/database/load_data.py")
    counts = _get_table_counts()
    context.log.info("Table row counts: %s", counts)
    return MaterializeResult(metadata=counts)

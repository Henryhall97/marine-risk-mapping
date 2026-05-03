"""Aggregation assets — H3 assignment and spatial feature engineering.

These assets wrap the Python scripts that transform raw PostGIS
tables into the H3-indexed tables that dbt reads as sources.
"""

import subprocess

import psycopg2
from dagster import AssetExecutionContext, MaterializeResult, asset

from orchestration.constants import (
    AIS_H3_PARQUET,
    DB_CONFIG,
    PROJECT_ROOT,
)


def _run_script(
    context: AssetExecutionContext,
    script: str,
    extra_args: list[str] | None = None,
) -> None:
    """Run a pipeline script from project root."""
    cmd = ["uv", "run", "python", script]
    if extra_args:
        cmd.extend(extra_args)
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


def _table_count(table: str) -> int:
    """Get the row count of a PostGIS table."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        count = cur.fetchone()[0]
        cur.close()
    finally:
        conn.close()
    return count


# ── AIS aggregation ─────────────────────────────────────────


@asset(
    group_name="aggregation",
    kinds={"python", "duckdb"},
    deps=["raw_ais_data", "postgis_raw_data"],
    description=(
        "Aggregate 3.1B AIS pings → 9.7M H3 cell-month rows "
        "using DuckDB two-pass pipeline, then load into PostGIS."
    ),
)
def ais_h3_summary(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Run the AIS H3 aggregation pipeline.

    This is the longest-running asset (~hours for full 2024).
    Produces a parquet file + loads into the ais_h3_summary table.
    """
    _run_script(
        context,
        "pipeline/aggregation/aggregate_ais.py",
        extra_args=["--load-postgis"],
    )
    rows = _table_count("ais_h3_summary")
    return MaterializeResult(
        metadata={
            "rows": rows,
            "parquet": str(AIS_H3_PARQUET),
        },
    )


# ── H3 cell assignment ──────────────────────────────────────


@asset(
    group_name="aggregation",
    kinds={"python", "h3"},
    deps=["postgis_raw_data"],
    description=(
        "Assign each cetacean sighting to an H3 res-7 cell. "
        "364K sightings → 76K unique cells."
    ),
)
def cetacean_sighting_h3(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Assign cetacean sightings to H3 cells."""
    _run_script(
        context,
        "pipeline/aggregation/assign_cetacean_h3.py",
    )
    rows = _table_count("cetacean_sighting_h3")
    return MaterializeResult(metadata={"rows": rows})


@asset(
    group_name="aggregation",
    kinds={"python", "h3"},
    deps=["postgis_raw_data"],
    description=(
        "Assign each geocoded ship strike to an H3 res-7 cell. "
        "67 strikes with coordinates."
    ),
)
def ship_strike_h3(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Assign ship strikes to H3 cells."""
    _run_script(
        context,
        "pipeline/aggregation/assign_ship_strike_h3.py",
    )
    rows = _table_count("ship_strike_h3")
    return MaterializeResult(metadata={"rows": rows})


# ── Derived spatial features ─────────────────────────────────


@asset(
    group_name="aggregation",
    kinds={"python", "rasterio"},
    deps=["ais_h3_summary", "cetacean_sighting_h3"],
    description=(
        "Sample GEBCO bathymetry at H3 centroids + 6 vertices. "
        "~1M cells with depth_mean, depth_min, depth_max, depth_std."
    ),
)
def bathymetry_h3(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Sample bathymetry raster at H3 cell locations."""
    _run_script(
        context,
        "pipeline/aggregation/sample_bathymetry.py",
    )
    rows = _table_count("bathymetry_h3")
    return MaterializeResult(metadata={"rows": rows})


@asset(
    group_name="aggregation",
    kinds={"python", "scipy"},
    deps=[
        "ais_h3_summary",
        "cetacean_sighting_h3",
        "ship_strike_h3",
        "postgis_raw_data",  # for speed zones + SMAs
    ],
    description=(
        "Compute KDTree nearest-neighbour distances from each "
        "H3 cell to whale sightings, ship strikes, speed zones, "
        "and MPAs. 1.9M cells × 4 distance features."
    ),
)
def cell_proximity(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Compute proximity features via scipy cKDTree.

    This is the last Python pre-computation step before dbt.
    Runtime: ~4 minutes for 1.9M cells.
    """
    _run_script(
        context,
        "pipeline/aggregation/compute_proximity.py",
    )
    rows = _table_count("cell_proximity")
    return MaterializeResult(metadata={"rows": rows})


# ── Macro overview (post-dbt) ────────────────────────────────


@asset(
    group_name="aggregation",
    kinds={"python", "h3"},
    deps=[
        "fct_collision_risk",
        "fct_collision_risk_seasonal",
        "fct_collision_risk_ml",
        "int_ml_whale_predictions",
        "int_sdm_whale_predictions",
    ],
    description=(
        "Aggregate H3 res-7 risk scores to res-4 macro overview "
        "for the coast-wide heatmap. ~14,176 cells × 5 seasons "
        "= 70,880 rows in macro_risk_overview."
    ),
)
def macro_risk_overview(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Aggregate dbt marts to H3 res-4 for the macro API endpoint.

    This runs *after* dbt build because it reads from
    fct_collision_risk and fct_collision_risk_seasonal.
    Runtime: ~2 minutes.
    """
    _run_script(
        context,
        "pipeline/aggregation/aggregate_macro_grid.py",
    )
    rows = _table_count("macro_risk_overview")
    return MaterializeResult(metadata={"rows": rows})

"""Ingestion assets — download raw data from external sources.

Each asset wraps one of the existing pipeline/ingestion scripts.
All downloads are idempotent (skip-if-exists), so re-materialising
is safe and fast when data is already on disk.
"""

import subprocess

from dagster import AssetExecutionContext, MaterializeResult, asset

from orchestration.constants import (
    AIS_RAW_DIR,
    CETACEAN_FILE,
    MPA_FILE,
    NISI_DIR,
    OCEAN_COVARIATES_FILE,
    PROJECT_ROOT,
    SHIP_STRIKES_FILE,
    SMA_FILE,
    SPEED_ZONES_FILE,
)


def _run_script(
    context: AssetExecutionContext,
    script: str,
) -> None:
    """Run a pipeline script via `uv run python <script>` from project root.

    Streams stdout/stderr to the Dagster log so operators see progress.
    Raises on non-zero exit code so the asset fails visibly.
    """
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


# ── Individual ingestion assets ─────────────────────────────


@asset(
    group_name="ingestion",
    kinds={"python"},
    description=(
        "Download 365 daily AIS GeoParquet files from MarineCadastre.gov for 2024."
    ),
)
def raw_ais_data(context: AssetExecutionContext) -> MaterializeResult:
    """Download AIS vessel position data."""
    _run_script(context, "pipeline/ingestion/download_ais.py")
    n_files = len(list(AIS_RAW_DIR.glob("*.parquet")))
    return MaterializeResult(
        metadata={"n_files": n_files, "dir": str(AIS_RAW_DIR)},
    )


@asset(
    group_name="ingestion",
    kinds={"python"},
    description=("Filter OBIS parquets to US coastal cetacean sightings."),
)
def raw_cetacean_data(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Download / filter cetacean sighting records."""
    _run_script(context, "pipeline/ingestion/download_cetaceans.py")
    return MaterializeResult(
        metadata={
            "file": str(CETACEAN_FILE),
            "exists": CETACEAN_FILE.exists(),
        },
    )


@asset(
    group_name="ingestion",
    kinds={"python"},
    description="Download NOAA MPA Inventory polygons.",
)
def raw_mpa_data(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Download Marine Protected Area boundaries."""
    _run_script(context, "pipeline/ingestion/download_mpa.py")
    return MaterializeResult(
        metadata={
            "file": str(MPA_FILE),
            "exists": MPA_FILE.exists(),
        },
    )


@asset(
    group_name="ingestion",
    kinds={"python"},
    description=(
        "Parse NOAA ship strike PDF → structured CSV (261 records, 67 geocoded)."
    ),
)
def raw_ship_strikes(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Parse ship strike incidents from NOAA PDF."""
    _run_script(context, "pipeline/ingestion/parse_ship_strikes.py")
    return MaterializeResult(
        metadata={
            "file": str(SHIP_STRIKES_FILE),
            "exists": SHIP_STRIKES_FILE.exists(),
        },
    )


@asset(
    group_name="ingestion",
    kinds={"python"},
    description=(
        "Download Nisi et al. 2024 risk grid, shipping density, "
        "and ISDM training CSVs from GitHub."
    ),
)
def raw_nisi_data(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Download Nisi et al. reference datasets."""
    _run_script(context, "pipeline/ingestion/download_nisi_2024.py")
    n_files = len(list(NISI_DIR.glob("*.csv")))
    return MaterializeResult(
        metadata={"n_files": n_files, "dir": str(NISI_DIR)},
    )


@asset(
    group_name="ingestion",
    kinds={"python"},
    description=(
        "Download ocean covariates (SST, MLD, SLA, PP) from "
        "NOAA ERDDAP and Copernicus Marine."
    ),
)
def raw_ocean_covariates(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Download ocean covariate grids."""
    _run_script(context, "pipeline/ingestion/download_ocean_covariates.py")
    return MaterializeResult(
        metadata={
            "file": str(OCEAN_COVARIATES_FILE),
            "exists": OCEAN_COVARIATES_FILE.exists(),
        },
    )


@asset(
    group_name="ingestion",
    kinds={"python"},
    description=("Download NARW Seasonal Management Area polygons from NOAA ArcGIS."),
)
def raw_sma_data(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Download Seasonal Management Area boundaries."""
    _run_script(context, "pipeline/ingestion/download_sma.py")
    return MaterializeResult(
        metadata={
            "file": str(SMA_FILE),
            "exists": SMA_FILE.exists(),
        },
    )


@asset(
    group_name="ingestion",
    kinds={"python"},
    description=("Download proposed Right Whale speed zone polygons."),
)
def raw_speed_zones(
    context: AssetExecutionContext,
) -> MaterializeResult:
    """Download proposed speed zone shapefile.

    Note: Speed zones are fetched as part of the MPA download
    script but we model them as a separate asset because they
    feed a distinct downstream path (int_speed_zone_coverage).
    """
    # Speed zones are downloaded by download_mpa.py already,
    # but we still materialise this as a checkpoint.
    return MaterializeResult(
        metadata={
            "file": str(SPEED_ZONES_FILE),
            "exists": SPEED_ZONES_FILE.exists(),
        },
    )

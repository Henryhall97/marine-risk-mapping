"""dbt assets — auto-generated from the dbt manifest.

dagster-dbt reads the dbt manifest.json and creates one Dagster
asset per dbt model, seed, and snapshot. This gives us:
  - Lineage: dbt models appear in the Dagster asset graph alongside
    Python ingestion and aggregation assets.
  - Observability: each dbt model run is logged with row counts,
    execution time, and test results.
  - Selective runs: you can materialise individual dbt models or
    groups (staging, intermediate, marts) from the Dagster UI.

The DbtProject helper also handles `dbt parse` at Dagster load time
to keep the manifest in sync with model changes.
"""

from pathlib import Path

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

# ── dbt project discovery ───────────────────────────────────
# DbtProject resolves the project root and generates the manifest
# at code-load time (dagster dev / dagster-daemon). The
# profiles_dir override ensures `--profiles-dir .` is always
# applied (our profiles.yml lives inside transform/, not ~/.dbt/).

TRANSFORM_DIR = Path(__file__).resolve().parent.parent.parent / "transform"

dbt_project = DbtProject(
    project_dir=TRANSFORM_DIR,
    profiles_dir=TRANSFORM_DIR,
)

# Parse the project to produce/refresh the manifest.
# This runs `dbt parse --profiles-dir <dir>` once at import time.
dbt_project.prepare_if_dev()


# ── Asset definition ────────────────────────────────────────


@dbt_assets(
    manifest=dbt_project.manifest_path,
    project=dbt_project,
)
def marine_risk_dbt_assets(
    context: AssetExecutionContext,
    dbt: DbtCliResource,
) -> None:
    """Materialise all dbt models (staging → intermediate → marts).

    Dagster invokes `dbt build` for whatever subset of models is
    selected. The DbtCliResource handles --profiles-dir and other
    CLI args automatically.
    """
    yield from dbt.cli(["build"], context=context).stream()

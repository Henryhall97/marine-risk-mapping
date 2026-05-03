"""Load SDM climate projections into PostGIS.

Reads per-species projection parquets produced by
``score_future_sdm.py`` and inserts them into the
``whale_sdm_projections`` table at grain
(h3_cell, season, scenario, decade).

Usage:
    uv run python pipeline/database/load_sdm_projections.py
"""

import io
import logging

import pandas as pd
import psycopg2

from pipeline.config import (
    CMIP6_DECADES,
    CMIP6_SCENARIOS,
    DB_CONFIG,
    SDM_PROJECTIONS_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# Species columns — same mapping as score_future_sdm.py
SDM_SPECIES_COLS = [
    "sdm_any_whale",
    "sdm_blue_whale",
    "sdm_fin_whale",
    "sdm_humpback_whale",
    "sdm_sperm_whale",
    "sdm_right_whale",
    "sdm_minke_whale",
]

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS whale_sdm_projections (
    h3_cell               BIGINT NOT NULL,
    season                VARCHAR(10) NOT NULL,
    scenario              VARCHAR(10) NOT NULL,
    decade                VARCHAR(10) NOT NULL,
    sdm_any_whale         DOUBLE PRECISION,
    sdm_blue_whale        DOUBLE PRECISION,
    sdm_fin_whale         DOUBLE PRECISION,
    sdm_humpback_whale    DOUBLE PRECISION,
    sdm_sperm_whale       DOUBLE PRECISION,
    sdm_right_whale       DOUBLE PRECISION,
    sdm_minke_whale       DOUBLE PRECISION,
    PRIMARY KEY (h3_cell, season, scenario, decade)
);
"""

CREATE_INDEXES = [
    ("CREATE INDEX IF NOT EXISTS idx_sdm_proj_h3 ON whale_sdm_projections (h3_cell);"),
    (
        "CREATE INDEX IF NOT EXISTS idx_sdm_proj_season "
        "ON whale_sdm_projections (season);"
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_sdm_proj_scenario "
        "ON whale_sdm_projections (scenario);"
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_sdm_proj_decade "
        "ON whale_sdm_projections (decade);"
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_sdm_proj_lookup "
        "ON whale_sdm_projections (scenario, decade, season);"
    ),
]


def _discover_prediction_files() -> list[tuple[str, str, str, str]]:
    """Scan SDM_PROJECTIONS_DIR for projection parquets.

    Returns list of (species_col_name, scenario, decade, filename).
    E.g.: ('sdm_any_whale', 'ssp245', '2040s',
           'sdm_any_whale_ssp245_2040s_predictions.parquet')
    """
    if not SDM_PROJECTIONS_DIR.exists():
        log.error("Projections dir not found: %s", SDM_PROJECTIONS_DIR)
        return []

    files = []
    for path in sorted(SDM_PROJECTIONS_DIR.glob("*_predictions.parquet")):
        name = path.stem.replace("_predictions", "")

        # Parse: {species}_{scenario}_{decade}
        for scenario in CMIP6_SCENARIOS:
            for decade in CMIP6_DECADES:
                suffix = f"_{scenario}_{decade}"
                if name.endswith(suffix):
                    species = name[: -len(suffix)]
                    if species in SDM_SPECIES_COLS:
                        files.append((species, scenario, decade, path.name))
                    break

    log.info("Found %d projection files", len(files))
    return files


def load_projections() -> None:
    """Merge all projection parquets and load into PostGIS."""
    entries = _discover_prediction_files()
    if not entries:
        log.error(
            "No projection files found in %s. "
            "Run: uv run python "
            "pipeline/analysis/score_future_sdm.py",
            SDM_PROJECTIONS_DIR,
        )
        return

    # ── Group files by (scenario, decade), merge species within ──
    from collections import defaultdict

    groups: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for species_col, scenario, decade, filename in entries:
        groups[(scenario, decade)].append((species_col, filename))

    log.info(
        "Found %d (scenario, decade) groups with %d total files",
        len(groups),
        len(entries),
    )

    chunks: list[pd.DataFrame] = []
    merge_keys = ["h3_cell", "season", "scenario", "decade"]

    for (scenario, decade), species_files in sorted(groups.items()):
        log.info(
            "  Merging %d species for %s/%s …",
            len(species_files),
            scenario,
            decade,
        )
        base: pd.DataFrame | None = None

        for species_col, filename in species_files:
            path = SDM_PROJECTIONS_DIR / filename
            df = pd.read_parquet(path)

            # Rename probability column → standard name
            prob_col = f"{species_col}_prob"
            if prob_col in df.columns:
                df = df.rename(columns={prob_col: species_col})

            keep = [c for c in merge_keys + [species_col] if c in df.columns]
            df_sub = df[keep]

            if base is None:
                base = df_sub
            else:
                base = base.merge(df_sub, on=merge_keys, how="outer")

        if base is not None:
            chunks.append(base)

    if not chunks:
        log.error("No data after merging predictions")
        return

    merged = pd.concat(chunks, ignore_index=True)

    log.info(
        "Merged projections: %s rows, %d columns",
        f"{len(merged):,}",
        len(merged.columns),
    )
    log.info(
        "  Scenarios: %s",
        sorted(merged["scenario"].unique()),
    )
    log.info(
        "  Decades: %s",
        sorted(merged["decade"].unique()),
    )
    log.info(
        "  Seasons: %s",
        sorted(merged["season"].unique()),
    )

    # ── Write to PostGIS ────────────────────────────────
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        # Create table + indexes
        cur.execute(CREATE_TABLE)
        for idx_sql in CREATE_INDEXES:
            cur.execute(idx_sql)

        # Truncate and reload
        cur.execute("TRUNCATE TABLE whale_sdm_projections;")
        log.info("Truncated whale_sdm_projections")

        # Build column list
        all_cols = [
            "h3_cell",
            "season",
            "scenario",
            "decade",
        ] + SDM_SPECIES_COLS

        # Ensure all species columns exist (fill missing with NaN)
        for col in SDM_SPECIES_COLS:
            if col not in merged.columns:
                merged[col] = float("nan")

        # COPY via StringIO
        buf = io.StringIO()
        merged[all_cols].to_csv(
            buf,
            index=False,
            header=False,
            sep="\t",
            na_rep="\\N",
        )
        buf.seek(0)

        log.info("Starting COPY of %s rows…", f"{len(merged):,}")
        conn.autocommit = False
        cur.copy_from(
            buf,
            "whale_sdm_projections",
            columns=all_cols,
            sep="\t",
            null="\\N",
        )
        conn.commit()
        conn.autocommit = True

        # Verify
        cur.execute("SELECT count(*) FROM whale_sdm_projections;")
        count = cur.fetchone()[0]
        log.info(
            "whale_sdm_projections: %s rows loaded ✅",
            f"{count:,}",
        )

        # Summary by scenario/decade
        cur.execute("""
            SELECT scenario, decade, count(*), avg(sdm_any_whale)
            FROM whale_sdm_projections
            GROUP BY scenario, decade
            ORDER BY scenario, decade;
        """)
        for row in cur.fetchall():
            log.info(
                "  %s/%s: %s rows, avg P(whale)=%.4f",
                row[0],
                row[1],
                f"{row[2]:,}",
                row[3] or 0,
            )

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    load_projections()

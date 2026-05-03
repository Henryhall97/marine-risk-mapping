"""Load ISDM climate projections into PostGIS.

Reads per-species ISDM projection parquets produced by
``score_future_isdm.py`` and inserts them into the
``whale_isdm_projections`` table at grain
(h3_cell, season, scenario, decade).

Usage:
    uv run python pipeline/database/load_isdm_projections.py
"""

import io
import logging

import pandas as pd
import psycopg2

from pipeline.config import (
    CMIP6_DECADES,
    CMIP6_SCENARIOS,
    DB_CONFIG,
    ISDM_PROJECTIONS_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# Species columns — same mapping as score_future_isdm.py
ISDM_SPECIES_COLS = [
    "isdm_blue_whale",
    "isdm_fin_whale",
    "isdm_humpback_whale",
    "isdm_sperm_whale",
]

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS whale_isdm_projections (
    h3_cell               BIGINT NOT NULL,
    season                VARCHAR(10) NOT NULL,
    scenario              VARCHAR(10) NOT NULL,
    decade                VARCHAR(10) NOT NULL,
    isdm_blue_whale       DOUBLE PRECISION,
    isdm_fin_whale        DOUBLE PRECISION,
    isdm_humpback_whale   DOUBLE PRECISION,
    isdm_sperm_whale      DOUBLE PRECISION,
    PRIMARY KEY (h3_cell, season, scenario, decade)
);
"""

CREATE_INDEXES = [
    (
        "CREATE INDEX IF NOT EXISTS idx_isdm_proj_h3 "
        "ON whale_isdm_projections (h3_cell);"
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_isdm_proj_season "
        "ON whale_isdm_projections (season);"
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_isdm_proj_scenario "
        "ON whale_isdm_projections (scenario);"
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_isdm_proj_decade "
        "ON whale_isdm_projections (decade);"
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_isdm_proj_lookup "
        "ON whale_isdm_projections "
        "(scenario, decade, season);"
    ),
]


def _discover_prediction_files() -> list[tuple[str, str, str, str]]:
    """Scan ISDM_PROJECTIONS_DIR for projection parquets.

    Returns list of (species_col_name, scenario, decade, filename).
    """
    if not ISDM_PROJECTIONS_DIR.exists():
        log.error(
            "Projections dir not found: %s",
            ISDM_PROJECTIONS_DIR,
        )
        return []

    files = []
    for path in sorted(ISDM_PROJECTIONS_DIR.glob("*_predictions.parquet")):
        name = path.stem.replace("_predictions", "")

        for scenario in CMIP6_SCENARIOS:
            for decade in CMIP6_DECADES:
                suffix = f"_{scenario}_{decade}"
                if name.endswith(suffix):
                    species = name[: -len(suffix)]
                    if species in ISDM_SPECIES_COLS:
                        files.append(
                            (
                                species,
                                scenario,
                                decade,
                                path.name,
                            )
                        )
                    break

    log.info("Found %d ISDM projection files", len(files))
    return files


def load_projections() -> None:
    """Merge all ISDM projection parquets and load into PostGIS."""
    entries = _discover_prediction_files()
    if not entries:
        log.error(
            "No ISDM projection files found in %s. "
            "Run: uv run python "
            "pipeline/analysis/score_future_isdm.py",
            ISDM_PROJECTIONS_DIR,
        )
        return

    # Group files by (scenario, decade), merge species within
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
            path = ISDM_PROJECTIONS_DIR / filename
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
        log.error("No data after merging ISDM predictions")
        return

    merged = pd.concat(chunks, ignore_index=True)

    log.info(
        "Merged ISDM projections: %s rows, %d columns",
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
        cur.execute(CREATE_TABLE)
        for idx_sql in CREATE_INDEXES:
            cur.execute(idx_sql)

        cur.execute("TRUNCATE TABLE whale_isdm_projections;")
        log.info("Truncated whale_isdm_projections")

        all_cols = [
            "h3_cell",
            "season",
            "scenario",
            "decade",
        ] + ISDM_SPECIES_COLS

        for col in ISDM_SPECIES_COLS:
            if col not in merged.columns:
                merged[col] = float("nan")

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
            "whale_isdm_projections",
            columns=all_cols,
            sep="\t",
            null="\\N",
        )
        conn.commit()
        conn.autocommit = True

        cur.execute("SELECT count(*) FROM whale_isdm_projections;")
        count = cur.fetchone()[0]
        log.info(
            "whale_isdm_projections: %s rows loaded ✅",
            f"{count:,}",
        )

        # Summary by scenario/decade
        cur.execute("""
            SELECT scenario, decade, count(*),
                   avg(isdm_blue_whale)
            FROM whale_isdm_projections
            GROUP BY scenario, decade
            ORDER BY scenario, decade;
        """)
        for row in cur.fetchall():
            log.info(
                "  %s/%s: %s rows, avg P(blue)=%.4f",
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

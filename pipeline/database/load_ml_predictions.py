"""Load ML model predictions into PostGIS.

Reads the ISDM per-species whale probability parquet files and
inserts them into the ml_whale_predictions table. This closes
the loop: dbt feature marts → Python ML → PostGIS → dbt risk mart.

The table has one row per (h3_cell, season) with a predicted
probability column for each species.

Usage:
    uv run python pipeline/database/load_ml_predictions.py
"""

import io
import logging

import pandas as pd
import psycopg2

from pipeline.config import DB_CONFIG, ML_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

PREDICTIONS_DIR = ML_DIR / "isdm_predictions"

# Species we have ISDM predictions for
ISDM_SPECIES = ["blue_whale", "fin_whale", "humpback_whale", "sperm_whale"]

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS ml_whale_predictions (
    h3_cell             BIGINT NOT NULL,
    season              VARCHAR(10) NOT NULL,
    isdm_blue_whale     DOUBLE PRECISION,
    isdm_fin_whale      DOUBLE PRECISION,
    isdm_humpback_whale DOUBLE PRECISION,
    isdm_sperm_whale    DOUBLE PRECISION,
    PRIMARY KEY (h3_cell, season)
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_ml_pred_h3 ON ml_whale_predictions (h3_cell);",
    "CREATE INDEX IF NOT EXISTS idx_ml_pred_season ON ml_whale_predictions (season);",
]


def load_predictions() -> None:
    """Merge ISDM prediction parquets and insert into PostGIS."""
    # ── Load and merge all species predictions ──────────────
    merged = None
    for species in ISDM_SPECIES:
        path = PREDICTIONS_DIR / f"isdm_{species}_predictions.parquet"
        if not path.exists():
            log.warning("Prediction file not found: %s — skipping", path)
            continue

        df = pd.read_parquet(path)
        prob_col = f"isdm_{species}_prob"
        df = df.rename(columns={prob_col: f"isdm_{species}"})

        if merged is None:
            merged = df[["h3_cell", "season", f"isdm_{species}"]]
        else:
            merged = merged.merge(
                df[["h3_cell", "season", f"isdm_{species}"]],
                on=["h3_cell", "season"],
                how="outer",
            )

    if merged is None:
        log.error("No prediction files found in %s", PREDICTIONS_DIR)
        return

    log.info(
        "Merged predictions: %d rows, %d columns",
        len(merged),
        len(merged.columns),
    )

    # ── Write to PostGIS ────────────────────────────────────
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        # Create table + indexes
        cur.execute(CREATE_TABLE)
        for idx_sql in CREATE_INDEXES:
            cur.execute(idx_sql)

        # Truncate and reload (idempotent)
        cur.execute("TRUNCATE TABLE ml_whale_predictions;")
        log.info("Truncated ml_whale_predictions")

        # Use COPY via StringIO for speed (50× faster than execute_values)
        species_cols = [f"isdm_{s}" for s in ISDM_SPECIES]
        all_cols = ["h3_cell", "season"] + species_cols

        buf = io.StringIO()
        merged[all_cols].to_csv(buf, index=False, header=False, sep="\t", na_rep="\\N")
        buf.seek(0)

        log.info("Starting COPY of %d rows…", len(merged))
        conn.autocommit = False
        cur.copy_from(
            buf, "ml_whale_predictions", columns=all_cols, sep="\t", null="\\N"
        )
        conn.commit()
        conn.autocommit = True

        # Verify
        cur.execute("SELECT count(*) FROM ml_whale_predictions;")
        count = cur.fetchone()[0]
        log.info("ml_whale_predictions: %d rows loaded ✅", count)

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    load_predictions()

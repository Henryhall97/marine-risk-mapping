"""Load SDM (OBIS-trained) whale predictions into PostGIS.

Reads per-species out-of-fold (OOF) prediction parquets produced by
``train_sdm_seasonal.py --score-grid`` and inserts them into the
``ml_sdm_predictions`` table.  OOF predictions are honest: each cell's
probability comes from a model that never saw that cell during training
(5-fold spatial block CV).

This table sits alongside ``ml_whale_predictions`` (ISDM) and enables
direct visual comparison of OBIS-trained vs Nisi-trained species
distributions on the platform.

Usage:
    uv run python pipeline/database/load_sdm_predictions.py
"""

import io
import logging

import pandas as pd
import psycopg2

from pipeline.config import DB_CONFIG, SDM_PREDICTIONS_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# Species we have SDM OOF predictions for (matches SCORE_TARGETS
# in train_sdm_seasonal.py)
SDM_SPECIES = {
    "sdm_any_whale": "sdm_any_whale_predictions.parquet",
    "sdm_blue_whale": "sdm_blue_whale_predictions.parquet",
    "sdm_fin_whale": "sdm_fin_whale_predictions.parquet",
    "sdm_humpback_whale": "sdm_humpback_whale_predictions.parquet",
    "sdm_sperm_whale": "sdm_sperm_whale_predictions.parquet",
    "sdm_right_whale": "sdm_right_whale_predictions.parquet",
    "sdm_minke_whale": "sdm_minke_whale_predictions.parquet",
}

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS ml_sdm_predictions (
    h3_cell               BIGINT NOT NULL,
    season                VARCHAR(10) NOT NULL,
    sdm_any_whale         DOUBLE PRECISION,
    sdm_blue_whale        DOUBLE PRECISION,
    sdm_fin_whale         DOUBLE PRECISION,
    sdm_humpback_whale    DOUBLE PRECISION,
    sdm_sperm_whale       DOUBLE PRECISION,
    sdm_right_whale       DOUBLE PRECISION,
    sdm_minke_whale       DOUBLE PRECISION,
    PRIMARY KEY (h3_cell, season)
);
"""

CREATE_INDEXES = [
    ("CREATE INDEX IF NOT EXISTS idx_sdm_pred_h3 ON ml_sdm_predictions (h3_cell);"),
    ("CREATE INDEX IF NOT EXISTS idx_sdm_pred_season ON ml_sdm_predictions (season);"),
]


def load_predictions() -> None:
    """Merge SDM OOF prediction parquets and load into PostGIS."""
    # ── Load and merge all species predictions ──────────
    merged: pd.DataFrame | None = None
    for col_name, filename in SDM_SPECIES.items():
        path = SDM_PREDICTIONS_DIR / filename
        if not path.exists():
            log.warning(
                "Prediction file not found: %s — skipping",
                path,
            )
            continue

        df = pd.read_parquet(path)
        prob_col = f"{col_name}_prob"
        df = df.rename(columns={prob_col: col_name})

        if merged is None:
            merged = df[["h3_cell", "season", col_name]]
        else:
            merged = merged.merge(
                df[["h3_cell", "season", col_name]],
                on=["h3_cell", "season"],
                how="outer",
            )

    if merged is None:
        log.error(
            "No prediction files found in %s",
            SDM_PREDICTIONS_DIR,
        )
        return

    log.info(
        "Merged SDM predictions: %d rows, %d columns",
        len(merged),
        len(merged.columns),
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

        # Truncate and reload (idempotent)
        cur.execute("TRUNCATE TABLE ml_sdm_predictions;")
        log.info("Truncated ml_sdm_predictions")

        # Use COPY via StringIO for speed
        species_cols = list(SDM_SPECIES.keys())
        all_cols = ["h3_cell", "season"] + species_cols

        buf = io.StringIO()
        merged[all_cols].to_csv(
            buf,
            index=False,
            header=False,
            sep="\t",
            na_rep="\\N",
        )
        buf.seek(0)

        log.info("Starting COPY of %d rows…", len(merged))
        conn.autocommit = False
        cur.copy_from(
            buf,
            "ml_sdm_predictions",
            columns=all_cols,
            sep="\t",
            null="\\N",
        )
        conn.commit()
        conn.autocommit = True

        # Verify
        cur.execute("SELECT count(*) FROM ml_sdm_predictions;")
        count = cur.fetchone()[0]
        log.info(
            "ml_sdm_predictions: %d rows loaded ✅",
            count,
        )

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    load_predictions()

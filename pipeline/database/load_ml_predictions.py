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
    isdm_blue_whale_sd     DOUBLE PRECISION,
    isdm_fin_whale_sd      DOUBLE PRECISION,
    isdm_humpback_whale_sd DOUBLE PRECISION,
    isdm_sperm_whale_sd    DOUBLE PRECISION,
    isdm_mess_value     DOUBLE PRECISION,
    isdm_extrapolated   BOOLEAN,
    isdm_mod_variable   VARCHAR(32),
    PRIMARY KEY (h3_cell, season)
);
"""

# Backfill columns for an existing table created before Phase 1 (uncertainty).
ALTER_COLUMNS = [
    "ALTER TABLE ml_whale_predictions "
    "ADD COLUMN IF NOT EXISTS isdm_blue_whale_sd DOUBLE PRECISION;",
    "ALTER TABLE ml_whale_predictions "
    "ADD COLUMN IF NOT EXISTS isdm_fin_whale_sd DOUBLE PRECISION;",
    "ALTER TABLE ml_whale_predictions "
    "ADD COLUMN IF NOT EXISTS isdm_humpback_whale_sd DOUBLE PRECISION;",
    "ALTER TABLE ml_whale_predictions "
    "ADD COLUMN IF NOT EXISTS isdm_sperm_whale_sd DOUBLE PRECISION;",
    "ALTER TABLE ml_whale_predictions "
    "ADD COLUMN IF NOT EXISTS isdm_mess_value DOUBLE PRECISION;",
    "ALTER TABLE ml_whale_predictions "
    "ADD COLUMN IF NOT EXISTS isdm_extrapolated BOOLEAN;",
    "ALTER TABLE ml_whale_predictions "
    "ADD COLUMN IF NOT EXISTS isdm_mod_variable VARCHAR(32);",
]

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

        keep = ["h3_cell", "season", f"isdm_{species}"]
        # Bootstrap uncertainty band (optional — present only after
        # --score-grid was run with --bootstrap-k > 0).
        sd_col = f"isdm_{species}_sd"
        if sd_col in df.columns:
            keep.append(sd_col)

        if merged is None:
            merged = df[keep]
        else:
            merged = merged.merge(df[keep], on=["h3_cell", "season"], how="outer")

    if merged is None:
        log.error("No prediction files found in %s", PREDICTIONS_DIR)
        return

    # ── Merge shared extrapolation (MESS) surface ───────────
    mess_path = PREDICTIONS_DIR / "isdm_extrapolation.parquet"
    if mess_path.exists():
        mess = pd.read_parquet(mess_path)
        mess_cols = ["h3_cell", "season"] + [
            c
            for c in ("isdm_mess_value", "isdm_extrapolated", "isdm_mod_variable")
            if c in mess.columns
        ]
        merged = merged.merge(mess[mess_cols], on=["h3_cell", "season"], how="left")
        log.info(
            "Merged MESS extrapolation surface (%.1f%% extrapolated)",
            100 * mess["isdm_extrapolated"].mean()
            if "isdm_extrapolated" in mess.columns
            else float("nan"),
        )
    else:
        log.warning("No extrapolation surface at %s — MESS cols left NULL", mess_path)

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
        # Create table + backfill columns + indexes
        cur.execute(CREATE_TABLE)
        for alter_sql in ALTER_COLUMNS:
            cur.execute(alter_sql)
        for idx_sql in CREATE_INDEXES:
            cur.execute(idx_sql)

        # Truncate and reload (idempotent)
        cur.execute("TRUNCATE TABLE ml_whale_predictions;")
        log.info("Truncated ml_whale_predictions")

        # Use COPY via StringIO for speed (50× faster than execute_values).
        # Build the full ordered column list, filling any column absent from
        # the merged frame (e.g. no bootstrap run) with NULL.
        species_cols = [f"isdm_{s}" for s in ISDM_SPECIES]
        sd_cols = [f"isdm_{s}_sd" for s in ISDM_SPECIES]
        mess_cols = ["isdm_mess_value", "isdm_extrapolated", "isdm_mod_variable"]
        all_cols = ["h3_cell", "season"] + species_cols + sd_cols + mess_cols
        for col in all_cols:
            if col not in merged.columns:
                merged[col] = pd.NA

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

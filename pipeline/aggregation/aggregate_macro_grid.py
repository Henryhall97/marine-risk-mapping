"""Aggregate H3 res-7 risk data to res-4 for the macro overview.

Reads from the dbt marts (fct_collision_risk, fct_collision_risk_seasonal)
and key intermediate tables, groups by H3 res-4 parent cell, and writes
aggregated results to the ``macro_risk_overview`` table.

Produces ~5 500 res-4 cells × 5 rows (annual + 4 seasons) ≈ 27 500 rows.

Usage::

    uv run python pipeline/aggregation/aggregate_macro_grid.py
"""

import logging

import h3
import numpy as np
import pandas as pd

from pipeline.utils import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MACRO_RESOLUTION = 4  # H3 res-4: ~57 km² per hex cell

# ── Table DDL ────────────────────────────────────────────────

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS macro_risk_overview (
    h3_cell             BIGINT       NOT NULL,
    cell_lat            DOUBLE PRECISION NOT NULL,
    cell_lon            DOUBLE PRECISION NOT NULL,
    season              VARCHAR(10)  NOT NULL DEFAULT 'annual',
    risk_score          DOUBLE PRECISION,
    ml_risk_score       DOUBLE PRECISION,
    traffic_score       DOUBLE PRECISION,
    avg_monthly_vessels     DOUBLE PRECISION,
    avg_speed_lethality     DOUBLE PRECISION,
    avg_high_speed_fraction DOUBLE PRECISION,
    avg_draft_risk_fraction DOUBLE PRECISION,
    night_traffic_ratio     DOUBLE PRECISION,
    avg_commercial_vessels  DOUBLE PRECISION,
    cetacean_score      DOUBLE PRECISION,
    strike_score        DOUBLE PRECISION,
    habitat_score       DOUBLE PRECISION,
    proximity_score     DOUBLE PRECISION,
    protection_gap      DOUBLE PRECISION,
    reference_risk      DOUBLE PRECISION,
    total_sightings     INTEGER,
    baleen_sightings    INTEGER,
    total_strikes       INTEGER,
    any_whale_prob      DOUBLE PRECISION,
    isdm_blue_whale     DOUBLE PRECISION,
    isdm_fin_whale      DOUBLE PRECISION,
    isdm_humpback_whale DOUBLE PRECISION,
    isdm_sperm_whale    DOUBLE PRECISION,
    sdm_any_whale       DOUBLE PRECISION,
    sdm_blue_whale      DOUBLE PRECISION,
    sdm_fin_whale       DOUBLE PRECISION,
    sdm_humpback_whale  DOUBLE PRECISION,
    sdm_sperm_whale     DOUBLE PRECISION,
    sst                 DOUBLE PRECISION,
    pp_upper_200m       DOUBLE PRECISION,
    depth_m_mean        DOUBLE PRECISION,
    shelf_fraction      DOUBLE PRECISION,
    child_cell_count    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_macro_overview_season
    ON macro_risk_overview (season);
CREATE INDEX IF NOT EXISTS idx_macro_overview_cell
    ON macro_risk_overview (h3_cell);
"""

# ── Columns we output ────────────────────────────────────────

OUTPUT_COLS = [
    "h3_cell",
    "cell_lat",
    "cell_lon",
    "season",
    "risk_score",
    "ml_risk_score",
    "traffic_score",
    "avg_monthly_vessels",
    "avg_speed_lethality",
    "avg_high_speed_fraction",
    "avg_draft_risk_fraction",
    "night_traffic_ratio",
    "avg_commercial_vessels",
    "cetacean_score",
    "strike_score",
    "habitat_score",
    "proximity_score",
    "protection_gap",
    "reference_risk",
    "total_sightings",
    "baleen_sightings",
    "total_strikes",
    "any_whale_prob",
    "isdm_blue_whale",
    "isdm_fin_whale",
    "isdm_humpback_whale",
    "isdm_sperm_whale",
    "sdm_any_whale",
    "sdm_blue_whale",
    "sdm_fin_whale",
    "sdm_humpback_whale",
    "sdm_sperm_whale",
    "sst",
    "pp_upper_200m",
    "depth_m_mean",
    "shelf_fraction",
    "child_cell_count",
]

# ── H3 helpers ───────────────────────────────────────────────


def _to_parent(cell: int) -> int:
    """Map H3 res-7 cell (BIGINT) to its res-4 parent."""
    return h3.str_to_int(h3.cell_to_parent(h3.int_to_str(cell), MACRO_RESOLUTION))


def _parent_centroids(parents: pd.Series) -> pd.DataFrame:
    """Return DataFrame with h3_cell, cell_lat, cell_lon."""
    unique = parents.unique()
    rows = []
    for p in unique:
        lat, lon = h3.cell_to_latlng(h3.int_to_str(p))
        rows.append({"h3_cell": p, "cell_lat": lat, "cell_lon": lon})
    return pd.DataFrame(rows)


# ── Score aggregation spec ───────────────────────────────────
# (column_name, aggregation_func) — applied after groupby(h3_parent)

AGG_SPEC: dict[str, tuple[str, str]] = {
    "risk_score": ("risk_score", "mean"),
    "traffic_score": ("traffic_score", "mean"),
    "avg_monthly_vessels": ("avg_monthly_vessels", "mean"),
    "avg_speed_lethality": ("avg_speed_lethality", "mean"),
    "avg_high_speed_fraction": ("avg_high_speed_fraction", "mean"),
    "avg_draft_risk_fraction": ("avg_draft_risk_fraction", "mean"),
    "night_traffic_ratio": ("night_traffic_ratio", "mean"),
    "avg_commercial_vessels": ("avg_commercial_vessels", "mean"),
    "cetacean_score": ("cetacean_score", "mean"),
    "strike_score": ("strike_score", "mean"),
    "habitat_score": ("habitat_score", "mean"),
    "proximity_score": ("proximity_score", "mean"),
    "protection_gap": ("protection_gap", "mean"),
    "reference_risk": ("reference_risk_score", "mean"),
    "total_sightings": ("total_sightings", "sum"),
    "baleen_sightings": ("baleen_sightings", "sum"),
    "total_strikes": ("total_strikes", "sum"),
    "sst": ("sst", "mean"),
    "pp_upper_200m": ("pp_upper_200m", "mean"),
    "depth_m_mean": ("depth_m", "mean"),
    "shelf_fraction": ("is_continental_shelf", "mean"),
    "child_cell_count": ("h3_cell", "count"),
}


# ── Core aggregation ─────────────────────────────────────────


def _read_and_aggregate(
    conn,
    sql: str,
    season_label: str,
) -> pd.DataFrame:
    """Read a mart query, map to res-4 parents, aggregate."""
    logger.info("  Reading SQL …")
    df = pd.read_sql(sql, conn)
    logger.info("  Read %s rows", f"{len(df):,}")

    if df.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)

    # Map to parent
    logger.info("  Mapping to H3 res-%d parents …", MACRO_RESOLUTION)
    df["h3_parent"] = df["h3_cell"].apply(_to_parent)

    # Build aggregation spec (skip columns that don't exist)
    agg_dict = {}
    for out_col, (src_col, func) in AGG_SPEC.items():
        if src_col in df.columns:
            agg_dict[out_col] = (src_col, func)

    logger.info("  Aggregating …")
    agg = df.groupby("h3_parent").agg(**agg_dict).reset_index()
    agg["season"] = season_label

    # Centroids
    centroids = _parent_centroids(agg["h3_parent"])
    agg = agg.merge(centroids, left_on="h3_parent", right_on="h3_cell")
    agg.drop(columns=["h3_parent"], inplace=True)

    logger.info(
        "  Aggregated to %s res-%d cells (%s)",
        f"{len(agg):,}",
        MACRO_RESOLUTION,
        season_label,
    )
    return agg


def _aggregate_annual(conn) -> pd.DataFrame:
    """Aggregate the static annual fct_collision_risk."""
    logger.info("── Annual aggregation ─────────────────────")
    sql = """
        SELECT
            cr.h3_cell,
            cr.risk_score,
            cr.traffic_score,
            vt.avg_monthly_vessels,
            vt.avg_speed_lethality,
            vt.avg_high_speed_fraction,
            vt.avg_draft_risk_fraction,
            vt.night_traffic_ratio,
            vt.avg_commercial_vessels,
            cr.cetacean_score,
            cr.strike_score,
            cr.habitat_score,
            cr.proximity_score,
            cr.protection_gap,
            cr.reference_risk_score,
            coalesce(cd.total_sightings, 0)            AS total_sightings,
            coalesce(cd.baleen_whale_sightings, 0)     AS baleen_sightings,
            coalesce(sd.total_strikes, 0)              AS total_strikes,
            oc.sst,
            oc.pp_upper_200m,
            b.depth_m,
            b.is_continental_shelf::int                AS is_continental_shelf
        FROM fct_collision_risk          cr
        LEFT JOIN (
            SELECT h3_cell,
                   avg(avg_monthly_vessels)     AS avg_monthly_vessels,
                   avg(avg_speed_lethality)     AS avg_speed_lethality,
                   avg(avg_high_speed_fraction) AS avg_high_speed_fraction,
                   avg(avg_draft_risk_fraction) AS avg_draft_risk_fraction,
                   avg(night_traffic_ratio)     AS night_traffic_ratio,
                   avg(avg_commercial_vessels)  AS avg_commercial_vessels
            FROM int_vessel_traffic_seasonal
            GROUP BY h3_cell
        ) vt ON cr.h3_cell = vt.h3_cell
        LEFT JOIN int_cetacean_density   cd ON cr.h3_cell = cd.h3_cell
        LEFT JOIN int_ship_strike_density sd ON cr.h3_cell = sd.h3_cell
        LEFT JOIN int_ocean_covariates   oc ON cr.h3_cell = oc.h3_cell
        LEFT JOIN int_bathymetry         b  ON cr.h3_cell = b.h3_cell
    """
    return _read_and_aggregate(conn, sql, "annual")


def _aggregate_seasonal(conn) -> pd.DataFrame:
    """Aggregate fct_collision_risk_seasonal, one season at a time."""
    logger.info("── Seasonal aggregation ───────────────────")
    parts: list[pd.DataFrame] = []

    for season in ("winter", "spring", "summer", "fall"):
        logger.info("Season: %s", season)
        sql = f"""
            SELECT
                cr.h3_cell,
                cr.risk_score,
                cr.traffic_score,
                vt.avg_monthly_vessels,
                vt.avg_speed_lethality,
                vt.avg_high_speed_fraction,
                vt.avg_draft_risk_fraction,
                vt.night_traffic_ratio,
                vt.avg_commercial_vessels,
                cr.cetacean_score,
                cr.strike_score,
                cr.habitat_score,
                cr.proximity_score,
                cr.protection_gap,
                cr.reference_risk_score,
                coalesce(cds.total_sightings, 0)           AS total_sightings,
                coalesce(cds.baleen_whale_sightings, 0)    AS baleen_sightings,
                coalesce(sd.total_strikes, 0)              AS total_strikes,
                ocs.sst,
                ocs.pp_upper_200m,
                b.depth_m,
                b.is_continental_shelf::int                AS is_continental_shelf
            FROM fct_collision_risk_seasonal cr
            LEFT JOIN int_vessel_traffic_seasonal vt
                ON cr.h3_cell = vt.h3_cell AND cr.season = vt.season
            LEFT JOIN int_cetacean_density_seasonal cds
                ON cr.h3_cell = cds.h3_cell AND cr.season = cds.season
            LEFT JOIN int_ship_strike_density sd
                ON cr.h3_cell = sd.h3_cell
            LEFT JOIN int_ocean_covariates_seasonal ocs
                ON cr.h3_cell = ocs.h3_cell AND cr.season = ocs.season
            LEFT JOIN int_bathymetry b
                ON cr.h3_cell = b.h3_cell
            WHERE cr.season = '{season}'
        """  # noqa: S608
        parts.append(_read_and_aggregate(conn, sql, season))

    return pd.concat(parts, ignore_index=True)


def _add_whale_predictions(conn, df: pd.DataFrame) -> pd.DataFrame:
    """Merge ISDM whale predictions (if the table exists)."""
    whale_cols = [
        "any_whale_prob",
        "isdm_blue_whale",
        "isdm_fin_whale",
        "isdm_humpback_whale",
        "isdm_sperm_whale",
    ]
    try:
        logger.info("── ISDM whale predictions ─────────────────")
        wp = pd.read_sql(
            """
            SELECT h3_cell, season,
                   any_whale_prob,
                   isdm_blue_whale, isdm_fin_whale,
                   isdm_humpback_whale, isdm_sperm_whale
            FROM int_ml_whale_predictions
            """,
            conn,
        )
        logger.info("  Read %s rows", f"{len(wp):,}")
    except Exception:
        logger.warning("  int_ml_whale_predictions not found — skipping")
        for c in whale_cols:
            df[c] = np.nan
        return df

    wp["h3_parent"] = wp["h3_cell"].apply(_to_parent)

    # Annual: average across all seasons
    wp_ann = (
        wp.groupby("h3_parent")[whale_cols]
        .mean()
        .reset_index()
        .rename(columns={"h3_parent": "h3_cell"})
    )

    # Seasonal: average within each season
    wp_sea = (
        wp.groupby(["h3_parent", "season"])[whale_cols]
        .mean()
        .reset_index()
        .rename(columns={"h3_parent": "h3_cell"})
    )

    # Merge into annual rows
    annual_mask = df["season"] == "annual"
    annual = df.loc[annual_mask].drop(columns=whale_cols, errors="ignore")
    annual = annual.merge(wp_ann, on="h3_cell", how="left")

    # Merge into seasonal rows
    seasonal = df.loc[~annual_mask].drop(columns=whale_cols, errors="ignore")
    seasonal = seasonal.merge(wp_sea, on=["h3_cell", "season"], how="left")

    combined = pd.concat([annual, seasonal], ignore_index=True)
    logger.info("  Merged whale predictions")
    return combined


def _add_sdm_predictions(conn, df: pd.DataFrame) -> pd.DataFrame:
    """Merge SDM (OBIS-trained) whale predictions (if the table exists)."""
    sdm_cols = [
        "sdm_any_whale",
        "sdm_blue_whale",
        "sdm_fin_whale",
        "sdm_humpback_whale",
        "sdm_sperm_whale",
    ]
    try:
        logger.info("── SDM whale predictions ──────────────────")
        sp = pd.read_sql(
            """
            SELECT h3_cell, season,
                   sdm_any_whale, sdm_blue_whale, sdm_fin_whale,
                   sdm_humpback_whale, sdm_sperm_whale
            FROM int_sdm_whale_predictions
            """,
            conn,
        )
        logger.info("  Read %s rows", f"{len(sp):,}")
    except Exception:
        logger.warning("  int_sdm_whale_predictions not found — skipping")
        for c in sdm_cols:
            df[c] = np.nan
        return df

    sp["h3_parent"] = sp["h3_cell"].apply(_to_parent)

    # Annual: average across all seasons
    sp_ann = (
        sp.groupby("h3_parent")[sdm_cols]
        .mean()
        .reset_index()
        .rename(columns={"h3_parent": "h3_cell"})
    )

    # Seasonal: average within each season
    sp_sea = (
        sp.groupby(["h3_parent", "season"])[sdm_cols]
        .mean()
        .reset_index()
        .rename(columns={"h3_parent": "h3_cell"})
    )

    # Merge into annual rows
    annual_mask = df["season"] == "annual"
    annual = df.loc[annual_mask].drop(columns=sdm_cols, errors="ignore")
    annual = annual.merge(sp_ann, on="h3_cell", how="left")

    # Merge into seasonal rows
    seasonal = df.loc[~annual_mask].drop(columns=sdm_cols, errors="ignore")
    seasonal = seasonal.merge(sp_sea, on=["h3_cell", "season"], how="left")

    combined = pd.concat([annual, seasonal], ignore_index=True)
    logger.info("  Merged SDM predictions")
    return combined


def _add_ml_risk_score(conn, df: pd.DataFrame) -> pd.DataFrame:
    """Merge ML-enhanced risk_score from fct_collision_risk_ml."""
    try:
        logger.info("── ML risk score ──────────────────────────")
        ml = pd.read_sql(
            "SELECT h3_cell, season, risk_score AS ml_risk_score "
            "FROM fct_collision_risk_ml",
            conn,
        )
        logger.info("  Read %s rows", f"{len(ml):,}")
    except Exception:
        logger.warning("  fct_collision_risk_ml not found — skipping")
        df["ml_risk_score"] = np.nan
        return df

    ml["h3_parent"] = ml["h3_cell"].apply(_to_parent)

    # Annual: average across all seasons
    ml_ann = (
        ml.groupby("h3_parent")["ml_risk_score"]
        .mean()
        .reset_index()
        .rename(columns={"h3_parent": "h3_cell"})
    )

    # Seasonal: average within each season
    ml_sea = (
        ml.groupby(["h3_parent", "season"])["ml_risk_score"]
        .mean()
        .reset_index()
        .rename(columns={"h3_parent": "h3_cell"})
    )

    annual_mask = df["season"] == "annual"
    annual = df.loc[annual_mask].drop(columns=["ml_risk_score"], errors="ignore")
    annual = annual.merge(ml_ann, on="h3_cell", how="left")

    seasonal = df.loc[~annual_mask].drop(columns=["ml_risk_score"], errors="ignore")
    seasonal = seasonal.merge(ml_sea, on=["h3_cell", "season"], how="left")

    combined = pd.concat([annual, seasonal], ignore_index=True)
    logger.info("  Merged ML risk score")
    return combined


def _write(conn, df: pd.DataFrame) -> None:
    """Write aggregated rows to macro_risk_overview (truncate first)."""
    # Ensure all output columns exist
    for col in OUTPUT_COLS:
        if col not in df.columns:
            df[col] = None

    df = df[OUTPUT_COLS]

    # pandas .where() cannot replace NaN with None in float-dtype columns
    # (None is coerced back to NaN).  Convert at the tuple level so that
    # PostgreSQL receives SQL NULL instead of IEEE-754 NaN.
    rows = [
        tuple(None if pd.isna(v) else v for v in row)
        for row in df.itertuples(index=False)
    ]
    placeholders = ", ".join(["%s"] * len(OUTPUT_COLS))
    col_list = ", ".join(OUTPUT_COLS)
    sql = f"INSERT INTO macro_risk_overview ({col_list}) VALUES ({placeholders})"

    logger.info("Writing %s rows to macro_risk_overview …", f"{len(rows):,}")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE macro_risk_overview;")
        batch = 5_000
        for i in range(0, len(rows), batch):
            cur.executemany(sql, rows[i : i + batch])
        conn.commit()
    logger.info("  Done")


# ── Main ─────────────────────────────────────────────────────


def main() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE)
            # Migrate: add traffic sub-metric columns if missing
            for col in (
                "avg_monthly_vessels",
                "avg_speed_lethality",
                "avg_high_speed_fraction",
                "avg_draft_risk_fraction",
                "night_traffic_ratio",
                "avg_commercial_vessels",
                "ml_risk_score",
                "sdm_any_whale",
                "sdm_blue_whale",
                "sdm_fin_whale",
                "sdm_humpback_whale",
                "sdm_sperm_whale",
            ):
                cur.execute(
                    "ALTER TABLE macro_risk_overview "
                    f"ADD COLUMN IF NOT EXISTS {col} "
                    "DOUBLE PRECISION"
                )
            conn.commit()

        annual = _aggregate_annual(conn)
        seasonal = _aggregate_seasonal(conn)
        combined = pd.concat([annual, seasonal], ignore_index=True)
        combined = _add_whale_predictions(conn, combined)
        combined = _add_sdm_predictions(conn, combined)
        combined = _add_ml_risk_score(conn, combined)
        _write(conn, combined)

        logger.info(
            "✓ macro_risk_overview: %s rows",
            f"{len(combined):,}",
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()

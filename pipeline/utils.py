"""Shared utility functions for the pipeline.

Provides reusable helpers for database operations and H3 cell
assignment that were previously duplicated across multiple scripts.
"""

import logging
import time
from contextlib import contextmanager

import h3
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from pipeline.config import DB_CONFIG, H3_RESOLUTION

logger = logging.getLogger(__name__)


# ── Type conversion ─────────────────────────────────────────


def to_python(v):
    """Convert pandas/numpy types to native Python for psycopg2.

    psycopg2 cannot adapt numpy scalar types (int64, float64, etc.)
    so we convert them to native Python equivalents.
    """
    if pd.isna(v):
        return None
    if hasattr(v, "item"):
        return v.item()
    return v


# ── Bulk insert ─────────────────────────────────────────────


def bulk_insert(
    cur,
    table: str,
    df: pd.DataFrame,
    batch_size: int = 10_000,
) -> int:
    """Insert a DataFrame into a PostGIS table using execute_values.

    Args:
        cur: psycopg2 cursor (must be in an auto-commit or
             caller-managed transaction).
        table: Target table name.
        df: DataFrame whose columns match the table columns.
        batch_size: Rows per INSERT batch.

    Returns:
        Number of rows inserted.
    """
    cols = list(df.columns)
    col_str = ", ".join(cols)
    template = "(" + ", ".join(["%s"] * len(cols)) + ")"

    records = [
        tuple(to_python(v) for v in row)
        for row in df.itertuples(index=False, name=None)
    ]

    total = len(records)
    for i in range(0, total, batch_size):
        batch = records[i : i + batch_size]
        execute_values(
            cur,
            f"INSERT INTO {table} ({col_str}) VALUES %s",
            batch,
            template=template,
        )
        if (i + batch_size) % 50_000 == 0 or i + batch_size >= total:
            logger.info(
                "  %s: inserted %s / %s rows",
                table,
                f"{min(i + batch_size, total):,}",
                f"{total:,}",
            )

    return total


# ── H3 cell assignment (generic) ───────────────────────────


def assign_h3_cells(
    *,
    source_table: str,
    id_column: str,
    lat_column: str,
    lon_column: str,
    target_table: str,
    fk_column: str,
    fk_reference: str,
    index_name: str,
) -> int:
    """Read points from PostGIS, assign H3 cells, write mapping table.

    This is a generic version of the logic previously duplicated
    in assign_cetacean_h3.py and assign_ship_strike_h3.py.

    Args:
        source_table: Table to read lat/lon from.
        id_column: Primary key column in the source table.
        lat_column: Latitude column name.
        lon_column: Longitude column name.
        target_table: Name of the mapping table to create.
        fk_column: Foreign key column name in the target table.
        fk_reference: FK reference clause, e.g. "cetacean_sightings(id)".
        index_name: Name for the h3_cell index.

    Returns:
        Number of rows written.
    """
    t0 = time.time()

    with get_db_connection() as conn:
        cur = conn.cursor()

        # ── Read source points ────────────────────────────────
        logger.info("Reading %s from PostGIS...", source_table)
        cur.execute(f"""
            SELECT {id_column}, {lat_column}, {lon_column}
            FROM {source_table}
            WHERE {lat_column} IS NOT NULL
              AND {lon_column} IS NOT NULL
        """)
        rows = cur.fetchall()
        logger.info("Read %s records", f"{len(rows):,}")

        # ── Assign H3 cells ──────────────────────────────────
        logger.info("Assigning H3 resolution-%d cells...", H3_RESOLUTION)
        records = []
        for row_id, lat, lon in rows:
            cell_hex = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
            cell_int = int(cell_hex, 16)
            cell_lat, cell_lon = h3.cell_to_latlng(cell_hex)
            records.append((row_id, cell_int, cell_lat, cell_lon))

        unique_cells = len({r[1] for r in records})
        logger.info(
            "Assigned %s cells (%d unique)",
            f"{len(records):,}",
            unique_cells,
        )

        # ── Write to PostGIS ──────────────────────────────────
        logger.info("Writing %s table...", target_table)

        cur.execute(f"DROP TABLE IF EXISTS {target_table} CASCADE;")
        cur.execute(f"""
            CREATE TABLE {target_table} (
                {fk_column}  INTEGER          NOT NULL
                             REFERENCES {fk_reference},
                h3_cell      BIGINT           NOT NULL,
                cell_lat     DOUBLE PRECISION NOT NULL,
                cell_lon     DOUBLE PRECISION NOT NULL,
                PRIMARY KEY ({fk_column})
            );
        """)

        batch_size = 10_000
        total = len(records)
        for i in range(0, total, batch_size):
            batch = records[i : i + batch_size]
            execute_values(
                cur,
                f"INSERT INTO {target_table} "
                f"({fk_column}, h3_cell, cell_lat, cell_lon) "
                "VALUES %s",
                batch,
            )
            if (i + batch_size) % 100_000 == 0 or (i + batch_size >= total):
                logger.info(
                    "  Inserted %s / %s",
                    f"{min(i + batch_size, total):,}",
                    f"{total:,}",
                )

        cur.execute(f"""
            CREATE INDEX {index_name}
                ON {target_table} (h3_cell);
        """)

        cur.close()

    elapsed = time.time() - t0
    logger.info(
        "Done in %.1f seconds — %s records → %s (%d unique H3 cells)",
        elapsed,
        f"{total:,}",
        target_table,
        unique_cells,
    )

    return total


# ── Database helpers ────────────────────────────────────────


@contextmanager
def get_db_connection(*, autocommit=False):
    """Context manager for psycopg2 connections.

    Commits on clean exit, rolls back on exception, always closes.

    Usage::

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")

    Args:
        autocommit: If True, set ``conn.autocommit = True`` so
            each statement commits immediately (useful for DDL).
    """
    conn = psycopg2.connect(**DB_CONFIG)
    if autocommit:
        conn.autocommit = True
    try:
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        conn.close()


def get_connection():
    """Open a psycopg2 connection using the shared DB_CONFIG.

    Prefer ``get_db_connection()`` context manager for new code.
    """
    return psycopg2.connect(**DB_CONFIG)


def table_row_count(table: str) -> int:
    """Return the row count of a PostGIS table."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        count = cur.fetchone()[0]
        cur.close()
    return count


# ── SHAP / XGBoost compatibility ────────────────────────────


def patch_shap_for_xgboost3():
    """Fix SHAP 0.49 + XGBoost 3.x base_score format incompatibility.

    XGBoost ≥3.0 stores learner_model_param values (including
    base_score) as bracket-wrapped strings like '[5E-1]' in the raw
    UBJSON model dump.  SHAP < 0.50 reads the model via
    ``save_raw(raw_format="ubj")`` → ``decode_ubjson_buffer()`` and
    calls ``float()`` on base_score, which fails on the brackets.

    This patches ``shap.explainers._tree.decode_ubjson_buffer`` to
    strip brackets from all ``learner_model_param`` string values
    before SHAP parses them.  Safe to call multiple times (no-op if
    already patched).
    """
    import shap.explainers._tree as _tree_mod

    _orig_decode = _tree_mod.decode_ubjson_buffer

    # Guard against double-patching
    if getattr(_orig_decode, "_xgb3_patched", False):
        return

    def _fixed_decode(fd):
        result = _orig_decode(fd)
        try:
            lmp = result["learner"]["learner_model_param"]
            for key, val in lmp.items():
                if isinstance(val, str) and val.startswith("[") and val.endswith("]"):
                    lmp[key] = val.strip("[]")
        except (KeyError, TypeError, AttributeError):
            pass
        return result

    _fixed_decode._xgb3_patched = True
    _tree_mod.decode_ubjson_buffer = _fixed_decode
    logger.debug("Patched shap.explainers._tree.decode_ubjson_buffer for XGBoost 3.x")

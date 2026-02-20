"""Set up DuckDB views over raw Parquet files.

Creates a DuckDB database with views that point at our local
parquet files. This gives us a SQL interface over the raw data
without loading anything — DuckDB reads parquet directly.
"""

import logging
from pathlib import Path

import duckdb

# Paths to raw data
AIS_DIR = Path("data/raw/ais")
CETACEAN_FILE = Path("data/raw/cetacean/us_cetacean_sightings.parquet")
MPA_FILE = Path("data/raw/mpa/mpa_inventory.parquet")
BATHYMETRY_FILE = Path("data/raw/bathymetry")

# Persistent DuckDB database file (stores views, not data)
DUCKDB_PATH = Path("data/marine_risk.duckdb")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_connection() -> duckdb.DuckDBPyConnection:
    """Open a connection to the persistent DuckDB database.

    Returns:
        A DuckDB connection with spatial extension loaded.
    """
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DUCKDB_PATH))

    # Install and load spatial extension (for geometry support)
    conn.execute("INSTALL spatial;")
    conn.execute("LOAD spatial;")

    return conn


def create_views(conn: duckdb.DuckDBPyConnection) -> None:
    """Create views over raw parquet files.

    Views are like saved queries — they don't copy data,
    they just remember where to read from.

    Args:
        conn: DuckDB connection.
    """
    # AIS: glob pattern reads all daily files as one table
    ais_path = str(AIS_DIR / "*.parquet")
    conn.execute(f"""
        CREATE OR REPLACE VIEW ais AS
        SELECT * FROM read_parquet('{ais_path}');
    """)
    logger.info("Created view: ais → %s", ais_path)

    # Cetacean sightings
    conn.execute(f"""
        CREATE OR REPLACE VIEW cetacean_sightings AS
        SELECT * FROM read_parquet('{CETACEAN_FILE}');
    """)
    logger.info("Created view: cetacean_sightings → %s", CETACEAN_FILE)

    # Marine Protected Areas
    conn.execute(f"""
        CREATE OR REPLACE VIEW mpa AS
        SELECT * FROM read_parquet('{MPA_FILE}');
    """)
    logger.info("Created view: mpa → %s", MPA_FILE)


def verify_views(conn: duckdb.DuckDBPyConnection) -> None:
    """Run quick counts to verify views are working.

    Args:
        conn: DuckDB connection.
    """
    for view in ["ais", "cetacean_sightings", "mpa"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
        logger.info("%s: %s rows", view, f"{count:,}")


def setup_duckdb() -> None:
    """Create the DuckDB database with views over raw data."""
    logger.info("Setting up DuckDB at %s", DUCKDB_PATH)

    conn = get_connection()

    try:
        create_views(conn)
        verify_views(conn)
        logger.info("DuckDB setup complete")
    finally:
        conn.close()


def notebook_connection() -> duckdb.DuckDBPyConnection:
    """Convenience function for use in Jupyter notebooks.

    Returns a connection with views already available so you
    can immediately run queries like:

        import pipeline.database.duckdb_views as db
        conn = db.notebook_connection()
        conn.execute("SELECT * FROM ais LIMIT 10").df()

    Returns:
        A ready-to-use DuckDB connection.
    """
    conn = get_connection()

    # Check if views exist, create if not
    existing = conn.execute("SELECT name FROM duckdb_views()").fetchall()
    view_names = {row[0] for row in existing}

    if not {"ais", "cetacean_sightings", "mpa"}.issubset(view_names):
        logger.info("Views not found — creating them")
        create_views(conn)

    return conn


if __name__ == "__main__":
    setup_duckdb()

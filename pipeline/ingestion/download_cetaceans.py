"""Download cetacean sighting data from OBIS via local parquet files.

Reads the raw OBIS occurrence parquet files (previously downloaded
via robis), filters to cetacean sightings in US coastal waters,
and saves a clean parquet file for downstream loading into PostGIS.

The OBIS data uses the order 'Cetartiodactyla' which includes all
cetaceans (whales, dolphins, porpoises). We filter to:
  - order = Cetartiodactyla
  - not dropped (data quality flag)
  - not absence records (presence-only)
  - US coastal bounding box (lat 24-49, lon -130 to -65)

Run with:
    uv run python -m pipeline.ingestion.download_cetaceans
"""

import logging
from pathlib import Path

import duckdb

# ── Input / Output paths ─────────────────────────────────
RAW_PARQUET_GLOB = "data/raw/occurrence/*.parquet"
OUTPUT_DIR = Path("data/raw/cetacean")
OUTPUT_FILE = OUTPUT_DIR / "us_cetacean_sightings.parquet"

# ── Bounding box for US Coast ────────────────────────────
LAT_MIN, LAT_MAX = 24.0, 49.0
LON_MIN, LON_MAX = -130.0, -65.0

# ── Taxonomic filter ─────────────────────────────────────
# OBIS classifies whales/dolphins under Cetartiodactyla
CETACEAN_ORDER = "Cetartiodactyla"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def extract_cetaceans() -> int:
    """Filter OBIS parquet files to US coastal cetacean sightings.

    Uses DuckDB to read parquet files with pushdown predicates,
    so only matching rows are materialised in memory.

    Returns:
        Number of sightings written.
    """
    logger.info("Reading OBIS parquet files from %s", RAW_PARQUET_GLOB)

    query = f"""
        COPY (
            SELECT
                interpreted.scientificName  AS scientific_name,
                interpreted.decimalLatitude  AS decimal_latitude,
                interpreted.decimalLongitude AS decimal_longitude,
                interpreted.eventDate        AS event_date,
                interpreted.date_year        AS date_year,
                interpreted."order"          AS "order",
                interpreted.family           AS family,
                interpreted.species          AS species,
            FROM read_parquet('{RAW_PARQUET_GLOB}')
            WHERE interpreted."order" = '{CETACEAN_ORDER}'
              AND dropped IS NOT TRUE
              AND absence IS NOT TRUE
              AND interpreted.decimalLatitude
                  BETWEEN {LAT_MIN} AND {LAT_MAX}
              AND interpreted.decimalLongitude
                  BETWEEN {LON_MIN} AND {LON_MAX}
        ) TO '{OUTPUT_FILE}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """

    conn = duckdb.connect()
    conn.execute(query)
    conn.close()

    # Report results
    row_count = duckdb.query(
        f"SELECT count(*) FROM read_parquet('{OUTPUT_FILE}')"
    ).fetchone()[0]

    size_mb = OUTPUT_FILE.stat().st_size / 1e6
    logger.info(
        "Saved %s cetacean sightings to %s (%.1f MB)",
        f"{row_count:,}",
        OUTPUT_FILE,
        size_mb,
    )
    return row_count


def preview_data() -> None:
    """Log a summary of the extracted dataset."""
    logger.info("Previewing extracted data...")

    # Species breakdown
    species_df = duckdb.query(f"""
        SELECT species, count(*) AS cnt
        FROM read_parquet('{OUTPUT_FILE}')
        WHERE species IS NOT NULL
        GROUP BY species
        ORDER BY cnt DESC
        LIMIT 15
    """).to_df()
    logger.info("Top species:\n%s", species_df.to_string(index=False))

    # Year range
    years = duckdb.query(f"""
        SELECT
            min(date_year)::int AS earliest,
            max(date_year)::int AS latest
        FROM read_parquet('{OUTPUT_FILE}')
    """).fetchone()
    logger.info("Year range: %s - %s", years[0], years[1])

    # Family breakdown
    family_df = duckdb.query(f"""
        SELECT family, count(*) AS cnt
        FROM read_parquet('{OUTPUT_FILE}')
        WHERE family IS NOT NULL
        GROUP BY family
        ORDER BY cnt DESC
    """).to_df()
    logger.info("Families:\n%s", family_df.to_string(index=False))


def main() -> None:
    """Download and filter cetacean sightings from OBIS parquets."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists():
        logger.info(
            "Cetacean parquet already exists at %s — skipping",
            OUTPUT_FILE,
        )
        preview_data()
        return

    # Check input files exist
    input_files = list(Path("data/raw/occurrence").glob("*.parquet"))
    if not input_files:
        logger.error(
            "No OBIS parquet files found at %s. "
            "Download them first with robis or the OBIS API.",
            RAW_PARQUET_GLOB,
        )
        raise FileNotFoundError(f"No parquet files found at {RAW_PARQUET_GLOB}")

    logger.info("Found %d OBIS parquet files", len(input_files))

    row_count = extract_cetaceans()
    preview_data()

    logger.info("Done — %s cetacean sightings extracted", f"{row_count:,}")


if __name__ == "__main__":
    main()

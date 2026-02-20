"""Load raw data from Parquet files into PostGIS.

Reads the cleaned Parquet files for AIS positions, cetacean
sightings, and marine protected areas, then inserts them
into the PostGIS tables created by create_schema.py.
"""

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# Database connection settings (match docker-compose.yml)
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "marine_risk",
    "user": "marine",
    "password": "marine_dev",
}

# Data file paths
AIS_DIR = Path("data/raw/ais")
CETACEAN_FILE = Path("data/raw/cetacean/us_cetacean_sightings.parquet")
MPA_FILE = Path("data/raw/mpa/mpa_inventory.parquet")

BATCH_SIZE = 50_000  # rows per INSERT batch for AIS data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_mpa_data(cur) -> None:
    """Load Marine Protected Areas into PostGIS.

    Args:
        cur: psycopg2 cursor.
    """
    if not MPA_FILE.exists():
        logger.warning("MPA file not found: %s", MPA_FILE)
        return

    gdf = gpd.read_parquet(MPA_FILE)
    logger.info("Read %d MPA features", len(gdf))

    rows = []
    for _, row in gdf.iterrows():
        rows.append(
            (
                row["Site_ID"],
                row["Site_Name"],
                row["Gov_Level"],
                row["State"],
                row["Prot_Lvl"],
                row["Mgmt_Agen"],
                row.get("IUCNcat", None),
                int(row["Estab_Yr"]) if pd.notna(row["Estab_Yr"]) else None,
                float(row["AreaKm"]) if pd.notna(row["AreaKm"]) else None,
                float(row["AreaMar"]) if pd.notna(row["AreaMar"]) else None,
                int(row["MarPercent"]) if pd.notna(row["MarPercent"]) else None,
                row.geometry.wkt,
            )
        )

    sql = """
        INSERT INTO marine_protected_areas
            (site_id, site_name, gov_level, state, prot_lvl,
             mgmt_agen, iucn_cat, estab_yr, area_km, area_mar,
             mar_percent, geom)
        VALUES %s
    """
    template = (
        "(%(site_id)s, %(site_name)s, %(gov_level)s, %(state)s, %(prot_lvl)s,"
        " %(mgmt_agen)s, %(iucn_cat)s, %(estab_yr)s, %(area_km)s, %(area_mar)s,"
        " %(mar_percent)s, ST_GeomFromText(%(geom)s, 4326))"
    )

    # Convert list of tuples to list of dicts for named placeholders
    records = [
        {
            "site_id": r[0],
            "site_name": r[1],
            "gov_level": r[2],
            "state": r[3],
            "prot_lvl": r[4],
            "mgmt_agen": r[5],
            "iucn_cat": r[6],
            "estab_yr": r[7],
            "area_km": r[8],
            "area_mar": r[9],
            "mar_percent": r[10],
            "geom": r[11],
        }
        for r in rows
    ]

    execute_values(cur, sql, records, template=template)
    logger.info("Loaded %d MPA features", len(records))


def load_cetacean_data(cur) -> None:
    """Load cetacean sightings into PostGIS.

    Args:
        cur: psycopg2 cursor.
    """
    if not CETACEAN_FILE.exists():
        logger.warning("Cetacean file not found: %s", CETACEAN_FILE)
        return

    df = pd.read_parquet(CETACEAN_FILE)
    logger.info("Read %d cetacean sightings", len(df))

    sql = """
        INSERT INTO cetacean_sightings
            (scientific_name, decimal_latitude, decimal_longitude,
             event_date, date_year, "order", family, species, geom)
        VALUES %s
    """
    template = (
        "(%(name)s, %(lat)s, %(lon)s, %(date)s, %(year)s,"
        " %(order)s, %(family)s, %(species)s,"
        " ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326))"
    )

    records = [
        {
            "name": row.get("scientificName"),
            "lat": row["decimalLatitude"],
            "lon": row["decimalLongitude"],
            "date": str(row.get("eventDate"))
            if pd.notna(row.get("eventDate"))
            else None,
            "year": int(row["date_year"]) if pd.notna(row.get("date_year")) else None,
            "order": row.get("order"),
            "family": row.get("family"),
            "species": row.get("species"),
        }
        for _, row in df.iterrows()
    ]

    execute_values(cur, sql, records, template=template)
    logger.info("Loaded %d cetacean sightings", len(records))


def load_ais_data(cur) -> None:
    """Load AIS position data into PostGIS.

    Uses COPY protocol via a CSV-like string buffer for
    maximum insert speed. Much faster than execute_values
    for millions of rows.

    Args:
        cur: psycopg2 cursor.
    """
    from io import StringIO

    parquet_files = sorted(AIS_DIR.glob("*.parquet"))
    if not parquet_files:
        logger.warning("No AIS parquet files found in %s", AIS_DIR)
        return

    logger.info("Found %d AIS files to load", len(parquet_files))

    total_loaded = 0

    for file_idx, filepath in enumerate(parquet_files, start=1):
        logger.info("(%d/%d) Reading %s", file_idx, len(parquet_files), filepath.name)
        gdf = gpd.read_parquet(filepath)

        # Build a flat DataFrame with WKT geometry (all vectorized)
        flat = pd.DataFrame(
            {
                "mmsi": gdf["mmsi"],
                "base_date_time": gdf["base_date_time"].astype(str),
                "sog": gdf["sog"],
                "cog": gdf["cog"],
                "heading": gdf["heading"],
                "vessel_name": gdf["vessel_name"],
                "imo": gdf["imo"],
                "call_sign": gdf["call_sign"],
                "vessel_type": gdf["vessel_type"],
                "status": gdf["status"],
                "length": gdf["length"],
                "width": gdf["width"],
                "draft": gdf["draft"],
                "cargo": gdf["cargo"],
                "transceiver": gdf["transceiver"],
                "geom": gdf.geometry.apply(lambda g: g.wkt),
            }
        )

        n_rows = len(flat)
        del gdf

        # Write to a string buffer as tab-separated values
        buffer = StringIO()
        flat.to_csv(buffer, sep="\t", header=False, index=False, na_rep="\\N")
        del flat
        buffer.seek(0)

        # Use a temp staging table (text geom), then convert to real geometry
        cur.execute("""
            CREATE TEMP TABLE ais_staging (
                mmsi INTEGER, base_date_time TEXT, sog REAL, cog REAL,
                heading SMALLINT, vessel_name TEXT, imo TEXT, call_sign TEXT,
                vessel_type SMALLINT, status SMALLINT, length REAL,
                width SMALLINT, draft REAL, cargo SMALLINT, transceiver TEXT,
                geom_wkt TEXT
            );
        """)

        # COPY into staging table
        copy_sql = """
            COPY ais_staging
                (mmsi, base_date_time, sog, cog, heading, vessel_name,
                 imo, call_sign, vessel_type, status, length, width,
                 draft, cargo, transceiver, geom_wkt)
            FROM STDIN WITH (FORMAT text, NULL '\\N')
        """
        cur.copy_expert(copy_sql, buffer)

        # Move from staging to real table, converting geometry
        cur.execute("""
            INSERT INTO ais_positions
                (mmsi, base_date_time, sog, cog, heading, vessel_name,
                 imo, call_sign, vessel_type, status, length, width,
                 draft, cargo, transceiver, geom)
            SELECT
                mmsi, base_date_time::timestamp, sog, cog, heading,
                vessel_name, imo, call_sign, vessel_type, status,
                length, width, draft, cargo, transceiver,
                ST_GeomFromText(geom_wkt, 4326)
            FROM ais_staging;
        """)
        cur.execute("DROP TABLE ais_staging;")
        total_loaded += n_rows

        logger.info(
            "(%d/%d) Loaded %s (%d rows) — total so far: %d",
            file_idx,
            len(parquet_files),
            filepath.name,
            n_rows,
            total_loaded,
        )

    logger.info("AIS loading complete: %d total rows", total_loaded)


def load_all_data() -> None:
    """Load all raw data into PostGIS."""
    logger.info("Connecting to PostGIS at %s:%s", DB_CONFIG["host"], DB_CONFIG["port"])

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        # Check if tables already have data
        for table in ["marine_protected_areas", "cetacean_sightings", "ais_positions"]:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            if count > 0:
                logger.info("Table %s already has %d rows — skipping", table, count)
                continue

            if table == "marine_protected_areas":
                load_mpa_data(cur)
            elif table == "cetacean_sightings":
                load_cetacean_data(cur)
            elif table == "ais_positions":
                load_ais_data(cur)

        # Final row counts
        logger.info("--- Final row counts ---")
        for table in ["ais_positions", "cetacean_sightings", "marine_protected_areas"]:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            logger.info("%s: %d rows", table, count)

    finally:
        cur.close()
        conn.close()
        logger.info("Connection closed")


if __name__ == "__main__":
    load_all_data()

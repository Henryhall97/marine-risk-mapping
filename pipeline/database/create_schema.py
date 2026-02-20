"""Create PostGIS schema for marine risk mapping.

Connects to the local PostGIS database and creates tables
for AIS positions, cetacean sightings, and marine protected
areas. Enables the PostGIS extension if not already active.
"""

import logging

import psycopg2

# Database connection settings (match docker-compose.yml)
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "marine_risk",
    "user": "marine",
    "password": "marine_dev",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# SQL to enable PostGIS and create our tables
ENABLE_POSTGIS = "CREATE EXTENSION IF NOT EXISTS postgis;"

CREATE_AIS_TABLE = """
CREATE TABLE IF NOT EXISTS ais_positions (
    id              SERIAL PRIMARY KEY,
    mmsi            INTEGER NOT NULL,
    base_date_time  TIMESTAMP NOT NULL,
    sog             REAL,
    cog             REAL,
    heading         SMALLINT,
    vessel_name     TEXT,
    imo             TEXT,
    call_sign       TEXT,
    vessel_type     SMALLINT,
    status          SMALLINT,
    length          REAL,
    width           SMALLINT,
    draft           REAL,
    cargo           SMALLINT,
    transceiver     CHAR(1),
    geom            GEOMETRY(Point, 4326) NOT NULL
);
"""

CREATE_CETACEAN_TABLE = """
CREATE TABLE IF NOT EXISTS cetacean_sightings (
    id                  SERIAL PRIMARY KEY,
    scientific_name     TEXT,
    decimal_latitude    DOUBLE PRECISION NOT NULL,
    decimal_longitude   DOUBLE PRECISION NOT NULL,
    event_date          TEXT,
    date_year           SMALLINT,
    "order"             TEXT,
    family              TEXT,
    species             TEXT,
    geom                GEOMETRY(Point, 4326) NOT NULL
);
"""

CREATE_MPA_TABLE = """
CREATE TABLE IF NOT EXISTS marine_protected_areas (
    id              SERIAL PRIMARY KEY,
    site_id         TEXT,
    site_name       TEXT,
    gov_level       TEXT,
    state           TEXT,
    prot_lvl        TEXT,
    mgmt_agen       TEXT,
    iucn_cat        TEXT,
    estab_yr        SMALLINT,
    area_km         REAL,
    area_mar        REAL,
    mar_percent     SMALLINT,
    geom            GEOMETRY(MultiPolygon, 4326) NOT NULL
);
"""


def create_tables() -> None:
    """Connect to PostGIS and create all schema tables."""
    logger.info("Connecting to PostGIS at %s:%s", DB_CONFIG["host"], DB_CONFIG["port"])

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        # Step 1: Enable PostGIS extension
        logger.info("Enabling PostGIS extension...")
        cur.execute(ENABLE_POSTGIS)

        # Step 2: Create tables
        tables = {
            "ais_positions": CREATE_AIS_TABLE,
            "cetacean_sightings": CREATE_CETACEAN_TABLE,
            "marine_protected_areas": CREATE_MPA_TABLE,
        }

        for table_name, sql in tables.items():
            logger.info("Creating table: %s", table_name)
            cur.execute(sql)

        # Step 3: Create spatial indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_ais_geom"
            " ON ais_positions USING GIST (geom);",
            "CREATE INDEX IF NOT EXISTS idx_cetacean_geom"
            " ON cetacean_sightings USING GIST (geom);",
            "CREATE INDEX IF NOT EXISTS idx_mpa_geom"
            " ON marine_protected_areas USING GIST (geom);",
            "CREATE INDEX IF NOT EXISTS idx_ais_time"
            " ON ais_positions (base_date_time);",
            "CREATE INDEX IF NOT EXISTS idx_ais_mmsi ON ais_positions (mmsi);",
            "CREATE INDEX IF NOT EXISTS idx_cetacean_species"
            " ON cetacean_sightings (species);",
        ]

        for idx_sql in indexes:
            logger.info("Creating index: %s", idx_sql.split("idx_")[1].split(" ON")[0])
            cur.execute(idx_sql)

        logger.info("Schema creation complete")

    finally:
        cur.close()
        conn.close()
        logger.info("Connection closed")


if __name__ == "__main__":
    create_tables()

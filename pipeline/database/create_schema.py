"""Create PostGIS schema for marine risk mapping.

Connects to the local PostGIS database and creates tables
for AIS positions, cetacean sightings, marine protected areas,
ship strike incidents, right whale speed zones, seasonal management
areas (current active NARW SMAs), ocean covariates (SST, MLD, SLA, PP),
and Nisi et al. (2024) risk reference data.
Enables the PostGIS extension if not already active.
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

CREATE_SHIP_STRIKES_TABLE = """
CREATE TABLE IF NOT EXISTS ship_strikes (
    id                SERIAL PRIMARY KEY,
    incident_date     TEXT,
    species           TEXT,
    sex               TEXT,
    length_m          DOUBLE PRECISION,
    location_desc     TEXT,
    latitude          DOUBLE PRECISION,
    longitude         DOUBLE PRECISION,
    region            TEXT,
    mortality_injury  TEXT,
    raw_text          TEXT,
    geom              GEOMETRY(Point, 4326)
);
"""

CREATE_NISI_RISK_TABLE = """
CREATE TABLE IF NOT EXISTS nisi_risk_grid (
    id                              SERIAL PRIMARY KEY,
    x                               DOUBLE PRECISION NOT NULL,
    y                               DOUBLE PRECISION NOT NULL,
    shipping_index                  DOUBLE PRECISION,
    mgmt                            BOOLEAN,
    mgmt_mandatory                  BOOLEAN,
    region                          TEXT,
    blue_mean_occurrence            DOUBLE PRECISION,
    blue_space_use                  DOUBLE PRECISION,
    blue_risk                       DOUBLE PRECISION,
    blue_hotspot_99                 BOOLEAN,
    blue_hotspot_qs                 TEXT,
    blue_hotspot_protected          BOOLEAN,
    blue_hotspot_protected_mandatory BOOLEAN,
    fin_mean_occurrence             DOUBLE PRECISION,
    fin_space_use                   DOUBLE PRECISION,
    fin_risk                        DOUBLE PRECISION,
    fin_hotspot_99                  BOOLEAN,
    fin_hotspot_qs                  TEXT,
    fin_hotspot_protected           BOOLEAN,
    fin_hotspot_protected_mandatory BOOLEAN,
    humpback_mean_occurrence        DOUBLE PRECISION,
    humpback_space_use              DOUBLE PRECISION,
    humpback_risk                   DOUBLE PRECISION,
    humpback_hotspot_99             BOOLEAN,
    humpback_hotspot_qs             TEXT,
    humpback_hotspot_protected      BOOLEAN,
    humpback_hotspot_protected_mandatory BOOLEAN,
    sperm_mean_occurrence           DOUBLE PRECISION,
    sperm_space_use                 DOUBLE PRECISION,
    sperm_risk                      DOUBLE PRECISION,
    sperm_hotspot_99                BOOLEAN,
    sperm_hotspot_qs                TEXT,
    sperm_hotspot_protected         BOOLEAN,
    sperm_hotspot_protected_mandatory BOOLEAN,
    all_space_use                   DOUBLE PRECISION,
    all_risk                        DOUBLE PRECISION,
    hotspot_overlap                 DOUBLE PRECISION,
    geom                            GEOMETRY(Point, 4326)
);
"""

CREATE_NISI_SHIPPING_TABLE = """
CREATE TABLE IF NOT EXISTS nisi_shipping_density (
    id                              SERIAL PRIMARY KEY,
    x                               DOUBLE PRECISION NOT NULL,
    y                               DOUBLE PRECISION NOT NULL,
    shipping_density                DOUBLE PRECISION,
    shipping_density_speed_weighted DOUBLE PRECISION,
    geom                            GEOMETRY(Point, 4326)
);
"""

CREATE_NISI_ISDM_TABLE = """
CREATE TABLE IF NOT EXISTS nisi_isdm_training (
    id              SERIAL PRIMARY KEY,
    species         TEXT NOT NULL,
    subpopulation   TEXT,
    presence        SMALLINT NOT NULL,
    data_type       TEXT NOT NULL,
    tag_id          TEXT,
    mld             DOUBLE PRECISION,
    pp_upper_200m   DOUBLE PRECISION,
    sla             DOUBLE PRECISION,
    sst             DOUBLE PRECISION,
    sst_sd          DOUBLE PRECISION,
    bathy           DOUBLE PRECISION,
    bathy_sd        DOUBLE PRECISION
);
"""

CREATE_SPEED_ZONES_TABLE = """
CREATE TABLE IF NOT EXISTS right_whale_speed_zones (
    id              SERIAL PRIMARY KEY,
    zone_name       TEXT NOT NULL,
    start_month     SMALLINT NOT NULL,
    start_day       SMALLINT NOT NULL,
    end_month       SMALLINT NOT NULL,
    end_day         SMALLINT NOT NULL,
    area_sq_deg     DOUBLE PRECISION,
    perimeter_deg   DOUBLE PRECISION,
    geom            GEOMETRY(Polygon, 4326) NOT NULL
);
"""

CREATE_OCEAN_COVARIATES_TABLE = """
CREATE TABLE IF NOT EXISTS ocean_covariates (
    id              SERIAL PRIMARY KEY,
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    sst             DOUBLE PRECISION,
    sst_sd          DOUBLE PRECISION,
    mld             DOUBLE PRECISION,
    sla             DOUBLE PRECISION,
    pp_upper_200m   DOUBLE PRECISION,
    geom            GEOMETRY(Point, 4326)
);
"""

CREATE_SMA_TABLE = """
CREATE TABLE IF NOT EXISTS seasonal_management_areas (
    id              SERIAL PRIMARY KEY,
    zone_name       TEXT NOT NULL,
    zone_abbr       VARCHAR(10),
    zone_type       VARCHAR(50),
    zone_comment    TEXT,
    start_month     SMALLINT NOT NULL,
    start_day       SMALLINT NOT NULL,
    end_month       SMALLINT NOT NULL,
    end_day         SMALLINT NOT NULL,
    area_sq_deg     DOUBLE PRECISION,
    perimeter_deg   DOUBLE PRECISION,
    geom            GEOMETRY(Polygon, 4326) NOT NULL
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
            "ship_strikes": CREATE_SHIP_STRIKES_TABLE,
            "nisi_risk_grid": CREATE_NISI_RISK_TABLE,
            "nisi_shipping_density": CREATE_NISI_SHIPPING_TABLE,
            "nisi_isdm_training": CREATE_NISI_ISDM_TABLE,
            "right_whale_speed_zones": CREATE_SPEED_ZONES_TABLE,
            "ocean_covariates": CREATE_OCEAN_COVARIATES_TABLE,
            "seasonal_management_areas": CREATE_SMA_TABLE,
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
            # Ship strikes
            "CREATE INDEX IF NOT EXISTS idx_ship_strikes_geom"
            " ON ship_strikes USING GIST (geom);",
            "CREATE INDEX IF NOT EXISTS idx_ship_strikes_species"
            " ON ship_strikes (species);",
            "CREATE INDEX IF NOT EXISTS idx_ship_strikes_region"
            " ON ship_strikes (region);",
            # Nisi risk grid
            "CREATE INDEX IF NOT EXISTS idx_nisi_risk_geom"
            " ON nisi_risk_grid USING GIST (geom);",
            "CREATE INDEX IF NOT EXISTS idx_nisi_risk_region"
            " ON nisi_risk_grid (region);",
            "CREATE INDEX IF NOT EXISTS idx_nisi_risk_all_risk"
            " ON nisi_risk_grid (all_risk);",
            # Nisi shipping density
            "CREATE INDEX IF NOT EXISTS idx_nisi_shipping_geom"
            " ON nisi_shipping_density USING GIST (geom);",
            "CREATE INDEX IF NOT EXISTS idx_nisi_shipping_density"
            " ON nisi_shipping_density (shipping_density);",
            # Nisi ISDM training data
            "CREATE INDEX IF NOT EXISTS idx_nisi_isdm_species"
            " ON nisi_isdm_training (species);",
            "CREATE INDEX IF NOT EXISTS idx_nisi_isdm_presence"
            " ON nisi_isdm_training (species, presence);",
            # Right whale speed zones
            "CREATE INDEX IF NOT EXISTS idx_speed_zones_geom"
            " ON right_whale_speed_zones USING GIST (geom);",
            # Ocean covariates
            "CREATE INDEX IF NOT EXISTS idx_ocean_cov_geom"
            " ON ocean_covariates USING GIST (geom);",
            # Seasonal management areas
            "CREATE INDEX IF NOT EXISTS idx_sma_geom"
            " ON seasonal_management_areas USING GIST (geom);",
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

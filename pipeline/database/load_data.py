"""Load raw data from Parquet files into PostGIS.

Reads the cleaned Parquet files for cetacean sightings and
marine protected areas, ship strike incidents, right whale
speed zones, current NARW seasonal management areas,
Nisi et al. (2024) whale-ship risk reference data, and ocean
covariates (SST, MLD, SLA, PP), then inserts
them into the PostGIS tables created by create_schema.py.

Note: AIS data is NOT loaded into PostGIS — it stays in
parquet files and is queried directly via DuckDB. Only
pre-aggregated results will land in PostGIS later (via dbt).
"""

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from pipeline.validation.schemas import (
    cetacean_schema,
    mpa_schema,
    validate_dataframe,
)

# Database connection settings (match docker-compose.yml)
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "marine_risk",
    "user": "marine",
    "password": "marine_dev",
}

# Data file paths
CETACEAN_FILE = Path("data/raw/cetacean/us_cetacean_sightings.parquet")
MPA_FILE = Path("data/raw/mpa/mpa_inventory.parquet")
SHIP_STRIKES_FILE = Path("data/processed/ship_strikes/ship_strikes.csv")
NISI_RISK_FILE = Path("data/raw/nisi_2024/global_whale_ship_risk.csv")
NISI_SHIPPING_FILE = Path("data/raw/nisi_2024/shipping_density.csv")
SPEED_ZONES_FILE = Path(
    "data/raw/mpa/Proposed-Right-Whale-Seasonal-Speed-Zones"
    "/Proposed_Right_Whale_Seasonal_Speed_Zones.shp"
)
OCEAN_COVARIATES_FILE = Path("data/raw/ocean/ocean_covariates.parquet")
SMA_FILE = Path(
    "data/raw/mpa/seasonal_management_areas/seasonal_management_areas.geojson"
)
NISI_ISDM_DIR = Path("data/raw/nisi_2024")
NISI_ISDM_FILES = {
    "blue_whale": NISI_ISDM_DIR / "blue_whale_isdm_data.csv",
    "fin_whale": NISI_ISDM_DIR / "fin_whale_isdm_data.csv",
    "humpback_whale": NISI_ISDM_DIR / "humpback_whale_isdm_data.csv",
    "sperm_whale": NISI_ISDM_DIR / "sperm_whale_isdm_data.csv",
}

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

    # Validate before loading — reject all if any failures
    result = validate_dataframe(gdf, mpa_schema)
    if not result["valid"]:
        logger.error(
            "MPA validation failed: %d failures — aborting load",
            result["n_failures"],
        )
        logger.error("Sample failures:\n%s", result["failures"].head(5))
        return
    logger.info("MPA validation passed ✅")

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

    # Validate before loading — reject all if any failures
    result = validate_dataframe(df, cetacean_schema)
    if not result["valid"]:
        logger.error(
            "Cetacean validation failed: %d failures — aborting load",
            result["n_failures"],
        )
        logger.error("Sample failures:\n%s", result["failures"].head(5))
        return
    logger.info("Cetacean validation passed ✅")

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


def _to_python(v):
    """Convert pandas/numpy types to native Python for psycopg2."""
    if pd.isna(v):
        return None
    if hasattr(v, "item"):
        return v.item()
    return v


def _bulk_insert(cur, table: str, df: pd.DataFrame, batch_size: int = 10_000) -> int:
    """Insert a DataFrame into a table using execute_values.

    Returns:
        Number of rows inserted.
    """
    cols = list(df.columns)
    col_str = ", ".join(cols)
    template = "(" + ", ".join(["%s"] * len(cols)) + ")"

    records = [
        tuple(_to_python(v) for v in row)
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


def load_ship_strikes(cur) -> None:
    """Load ship strike incident records into PostGIS.

    Args:
        cur: psycopg2 cursor.
    """
    if not SHIP_STRIKES_FILE.exists():
        logger.warning("Ship strikes file not found: %s", SHIP_STRIKES_FILE)
        return

    df = pd.read_csv(SHIP_STRIKES_FILE)
    logger.info("Read %d ship strike records", len(df))

    geocoded = df.dropna(subset=["latitude", "longitude"])
    logger.info(
        "  %d geocoded, %d without coordinates", len(geocoded), len(df) - len(geocoded)
    )

    records = []
    for _, row in df.iterrows():
        records.append(
            {
                "date": _to_python(row["date"]),
                "species": _to_python(row["species"]),
                "sex": _to_python(row["sex"]),
                "length_m": _to_python(row["length_m"]),
                "location": _to_python(row["location"]),
                "lat": _to_python(row["latitude"]),
                "lon": _to_python(row["longitude"]),
                "region": _to_python(row["region"]),
                "mortality_injury": _to_python(row["mortality_injury"]),
                "raw_text": _to_python(row["raw_text"]),
            }
        )

    sql = """
        INSERT INTO ship_strikes
            (incident_date, species, sex, length_m, location_desc,
             latitude, longitude, region, mortality_injury, raw_text, geom)
        VALUES %s
    """
    template = (
        "(%(date)s, %(species)s, %(sex)s, %(length_m)s, %(location)s,"
        " %(lat)s, %(lon)s, %(region)s, %(mortality_injury)s, %(raw_text)s,"
        " CASE WHEN %(lat)s IS NOT NULL AND %(lon)s IS NOT NULL"
        "   THEN ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)"
        "   ELSE NULL END)"
    )

    execute_values(cur, sql, records, template=template)
    logger.info(
        "Loaded %d ship strike records (%d with geometry)", len(records), len(geocoded)
    )


def load_nisi_risk_grid(cur) -> None:
    """Load Nisi et al. (2024) global whale-ship risk grid into PostGIS.

    Args:
        cur: psycopg2 cursor.
    """
    if not NISI_RISK_FILE.exists():
        logger.warning("Nisi risk grid not found: %s", NISI_RISK_FILE)
        return

    df = pd.read_csv(NISI_RISK_FILE)
    logger.info("Read %s risk grid rows × %d columns", f"{len(df):,}", df.shape[1])

    # Rename columns: dots → underscores for SQL compatibility
    df.columns = [c.replace(".", "_") for c in df.columns]

    # Cast 0/1 integer columns to proper booleans
    bool_cols = [
        c
        for c in df.columns
        if c
        in (
            "mgmt",
            "mgmt_mandatory",
        )
        or c.endswith(
            ("_hotspot_99", "_hotspot_protected", "_hotspot_protected_mandatory")
        )
    ]
    for col in bool_cols:
        df[col] = df[col].astype(bool)

    n = _bulk_insert(cur, "nisi_risk_grid", df)

    # Set geometry from x/y
    cur.execute("""
        UPDATE nisi_risk_grid
        SET geom = ST_SetSRID(ST_MakePoint(x, y), 4326);
    """)
    logger.info("Loaded %s risk grid rows with geometry", f"{n:,}")


def load_nisi_shipping_density(cur) -> None:
    """Load Nisi et al. (2024) shipping density grid into PostGIS.

    Args:
        cur: psycopg2 cursor.
    """
    if not NISI_SHIPPING_FILE.exists():
        logger.warning("Nisi shipping density not found: %s", NISI_SHIPPING_FILE)
        return

    df = pd.read_csv(NISI_SHIPPING_FILE)
    logger.info("Read %s shipping density rows", f"{len(df):,}")

    n = _bulk_insert(cur, "nisi_shipping_density", df)

    # Set geometry from x/y
    cur.execute("""
        UPDATE nisi_shipping_density
        SET geom = ST_SetSRID(ST_MakePoint(x, y), 4326);
    """)
    logger.info("Loaded %s shipping density rows with geometry", f"{n:,}")


def load_nisi_isdm_training(cur) -> None:
    """Load Nisi et al. (2024) ISDM training data into PostGIS.

    Combines all 4 species CSVs into a single table with
    presence/absence labels and environmental covariates.
    Useful for training whale occurrence models.

    Args:
        cur: psycopg2 cursor.
    """
    frames = []
    for species_key, csv_path in NISI_ISDM_FILES.items():
        if not csv_path.exists():
            logger.warning("ISDM file not found: %s", csv_path)
            continue

        df = pd.read_csv(csv_path)
        logger.info("Read %s ISDM rows for %s", f"{len(df):,}", species_key)
        frames.append(df)

    if not frames:
        logger.warning("No ISDM files found — skipping")
        return

    combined = pd.concat(frames, ignore_index=True)
    logger.info("Combined ISDM data: %s rows", f"{len(combined):,}")

    # Drop the unnamed index column if present
    if "Unnamed: 0" in combined.columns:
        combined = combined.drop(columns=["Unnamed: 0"])

    # Standardise column names
    col_map = {
        "PPupper200m": "pp_upper_200m",
    }
    combined = combined.rename(columns=col_map)

    # Select columns in table order
    keep_cols = [
        "species",
        "subpopulation",
        "presence",
        "data_type",
        "tag_id",
        "mld",
        "pp_upper_200m",
        "sla",
        "sst",
        "sst_sd",
        "bathy",
        "bathy_sd",
    ]
    # Only keep columns that exist (sperm whale lacks subpopulation)
    keep_cols = [c for c in keep_cols if c in combined.columns]
    combined = combined[keep_cols]

    n = _bulk_insert(cur, "nisi_isdm_training", combined)
    logger.info(
        "Loaded %s ISDM training rows (%d presences, %d absences)",
        f"{n:,}",
        int((combined["presence"] == 1).sum()),
        int((combined["presence"] == 0).sum()),
    )


def load_speed_zones(cur) -> None:
    """Load Right Whale Seasonal Speed Zone polygons into PostGIS.

    Args:
        cur: psycopg2 cursor.
    """
    if not SPEED_ZONES_FILE.exists():
        logger.warning("Speed zones shapefile not found: %s", SPEED_ZONES_FILE)
        return

    gdf = gpd.read_file(SPEED_ZONES_FILE)
    logger.info("Read %d speed zone polygons", len(gdf))

    records = []
    for _, row in gdf.iterrows():
        records.append(
            {
                "name": row["ssz"],
                "st_mo": int(row["st_mo"]),
                "st_day": int(row["st_day"]),
                "end_mo": int(row["end_mo"]),
                "end_day": int(row["end_day"]),
                "area": float(row["Shape__Are"]),
                "perim": float(row["Shape__Len"]),
                "geom": row.geometry.wkt,
            }
        )

    sql = """
        INSERT INTO right_whale_speed_zones
            (zone_name, start_month, start_day, end_month, end_day,
             area_sq_deg, perimeter_deg, geom)
        VALUES %s
    """
    template = (
        "(%(name)s, %(st_mo)s, %(st_day)s, %(end_mo)s, %(end_day)s,"
        " %(area)s, %(perim)s, ST_GeomFromText(%(geom)s, 4326))"
    )

    execute_values(cur, sql, records, template=template)
    logger.info("Loaded %d speed zone polygons", len(records))


def load_ocean_covariates(cur) -> None:
    """Load ocean covariates (SST, MLD, SLA, PP) into PostGIS.

    Args:
        cur: psycopg2 cursor.
    """
    if not OCEAN_COVARIATES_FILE.exists():
        logger.warning("Ocean covariates file not found: %s", OCEAN_COVARIATES_FILE)
        return

    df = pd.read_parquet(OCEAN_COVARIATES_FILE)
    logger.info("Read %s ocean covariate records", f"{len(df):,}")

    n = _bulk_insert(cur, "ocean_covariates", df)

    # Set geometry from lat/lon
    cur.execute("""
        UPDATE ocean_covariates
        SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        WHERE geom IS NULL;
    """)
    logger.info("Loaded %s ocean covariate records with geometry", f"{n:,}")


def load_sma_data(cur) -> None:
    """Load current NARW Seasonal Management Area polygons into PostGIS.

    These are the active SMAs from 50 CFR § 224.105 downloaded
    from NOAA's ArcGIS feature service.

    Args:
        cur: psycopg2 cursor.
    """
    if not SMA_FILE.exists():
        logger.warning("SMA GeoJSON not found: %s", SMA_FILE)
        return

    gdf = gpd.read_file(SMA_FILE)
    logger.info("Read %d SMA polygons", len(gdf))

    records = []
    for _, row in gdf.iterrows():
        records.append(
            {
                "name": row["zone_name"],
                "abbr": row.get("zone_abbr"),
                "ztype": row.get("zone_type"),
                "comment": row.get("zone_comme"),
                "st_mo": int(row["st_mo"]),
                "st_day": int(row["st_day"]),
                "end_mo": int(row["end_mo"]),
                "end_day": int(row["end_day"]),
                "area": float(row["Shape__Area"])
                if pd.notna(row.get("Shape__Area"))
                else None,
                "perim": float(row["Shape__Length"])
                if pd.notna(row.get("Shape__Length"))
                else None,
                "geom": row.geometry.wkt,
            }
        )

    sql = """
        INSERT INTO seasonal_management_areas
            (zone_name, zone_abbr, zone_type, zone_comment,
             start_month, start_day, end_month, end_day,
             area_sq_deg, perimeter_deg, geom)
        VALUES %s
    """
    template = (
        "(%(name)s, %(abbr)s, %(ztype)s, %(comment)s,"
        " %(st_mo)s, %(st_day)s, %(end_mo)s, %(end_day)s,"
        " %(area)s, %(perim)s, ST_GeomFromText(%(geom)s, 4326))"
    )

    execute_values(cur, sql, records, template=template)
    logger.info("Loaded %d SMA polygons", len(records))


def load_all_data() -> None:
    """Load all raw data into PostGIS."""
    logger.info("Connecting to PostGIS at %s:%s", DB_CONFIG["host"], DB_CONFIG["port"])

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        # Check if tables already have data
        loaders = {
            "marine_protected_areas": load_mpa_data,
            "cetacean_sightings": load_cetacean_data,
            "ship_strikes": load_ship_strikes,
            "nisi_risk_grid": load_nisi_risk_grid,
            "nisi_shipping_density": load_nisi_shipping_density,
            "nisi_isdm_training": load_nisi_isdm_training,
            "right_whale_speed_zones": load_speed_zones,
            "ocean_covariates": load_ocean_covariates,
            "seasonal_management_areas": load_sma_data,
        }

        for table, loader in loaders.items():
            cur.execute(
                "SELECT EXISTS(SELECT 1"
                " FROM information_schema.tables"
                " WHERE table_name = %s);",
                (table,),
            )
            table_exists = cur.fetchone()[0]

            if table_exists:
                cur.execute(f"SELECT COUNT(*) FROM {table};")
                count = cur.fetchone()[0]
                if count > 0:
                    logger.info("Table %s already has %d rows — skipping", table, count)
                    continue

            loader(cur)

        # Final row counts
        logger.info("--- Final row counts ---")
        for table in loaders:
            cur.execute(
                "SELECT EXISTS(SELECT 1"
                " FROM information_schema.tables"
                " WHERE table_name = %s);",
                (table,),
            )
            if cur.fetchone()[0]:
                cur.execute(f"SELECT COUNT(*) FROM {table};")
                count = cur.fetchone()[0]
                logger.info("%s: %d rows", table, count)

    finally:
        cur.close()
        conn.close()
        logger.info("Connection closed")


if __name__ == "__main__":
    load_all_data()

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

import geopandas as gpd
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from pipeline.config import (
    BIA_FILE,
    CETACEAN_FILE,
    CMIP6_PROJECTIONS_FILE,
    CRITICAL_HABITAT_FILE,
    DB_CONFIG,
    MPA_FILE,
    NISI_ISDM_FILES,
    NISI_RISK_FILE,
    NISI_SHIPPING_FILE,
    OCEAN_COVARIATES_FILE,
    OCEAN_MASK_FILE,
    SHIP_STRIKES_FILE,
    SHIPPING_LANES_FILE,
    SLOW_ZONES_FILE,
    SMA_FILE,
    SPEED_ZONES_FILE,
)
from pipeline.utils import bulk_insert, to_python
from pipeline.validation.schemas import (
    cetacean_schema,
    mpa_schema,
    validate_dataframe,
)

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
                "date": to_python(row["date"]),
                "species": to_python(row["species"]),
                "sex": to_python(row["sex"]),
                "length_m": to_python(row["length_m"]),
                "location": to_python(row["location"]),
                "lat": to_python(row["latitude"]),
                "lon": to_python(row["longitude"]),
                "region": to_python(row["region"]),
                "mortality_injury": to_python(row["mortality_injury"]),
                "raw_text": to_python(row["raw_text"]),
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

    n = bulk_insert(cur, "nisi_risk_grid", df)

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

    n = bulk_insert(cur, "nisi_shipping_density", df)

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

    n = bulk_insert(cur, "nisi_isdm_training", combined)
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
    """Load seasonal ocean covariates (SST, MLD, SLA, PP) into PostGIS.

    The parquet file contains (lat, lon, season, sst, sst_sd, mld, sla,
    pp_upper_200m) — climatological seasonal means from 2019–2024.
    Geometry is set from lat/lon after bulk insert.

    Args:
        cur: psycopg2 cursor.
    """
    if not OCEAN_COVARIATES_FILE.exists():
        logger.warning("Ocean covariates file not found: %s", OCEAN_COVARIATES_FILE)
        return

    df = pd.read_parquet(OCEAN_COVARIATES_FILE)
    logger.info("Read %s ocean covariate records", f"{len(df):,}")

    # Ensure season column is present (seasonal parquet)
    if "season" not in df.columns:
        logger.error(
            "Ocean covariates parquet missing 'season' column. "
            "Re-run merge_to_parquet(force=True) to regenerate."
        )
        return

    n = bulk_insert(cur, "ocean_covariates", df)

    # Set geometry from lat/lon
    cur.execute("""
        UPDATE ocean_covariates
        SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        WHERE geom IS NULL;
    """)

    # Log seasonal breakdown
    cur.execute(
        "SELECT season, count(*) FROM ocean_covariates GROUP BY season ORDER BY season;"
    )
    for season, count in cur.fetchall():
        logger.info("  %s: %s rows", season, f"{count:,}")

    logger.info("Loaded %s seasonal ocean covariate records with geometry", f"{n:,}")


def load_cmip6_ocean_covariates(cur) -> None:
    """Load CMIP6 climate-projected ocean covariates into PostGIS.

    The parquet file contains projected SST, MLD, SLA, PP at
    (lat, lon, season, scenario, decade) grain — produced by
    download_cmip6_projections.py from baseline + CMIP6 deltas.
    ~3.5M rows (2 scenarios × 4 decades × 4 seasons × ~109K points).

    Args:
        cur: psycopg2 cursor.
    """
    if not CMIP6_PROJECTIONS_FILE.exists():
        logger.warning(
            "CMIP6 projections file not found: %s",
            CMIP6_PROJECTIONS_FILE,
        )
        return

    df = pd.read_parquet(CMIP6_PROJECTIONS_FILE)
    logger.info("Read %s CMIP6 ocean covariate records", f"{len(df):,}")

    # Keep only the columns we need
    cols = [
        "lat",
        "lon",
        "season",
        "scenario",
        "decade",
        "sst",
        "sst_sd",
        "mld",
        "sla",
        "pp_upper_200m",
    ]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        logger.error(
            "CMIP6 parquet missing columns: %s. Available: %s",
            missing,
            list(df.columns),
        )
        return

    df = df[cols]
    n = bulk_insert(cur, "cmip6_ocean_covariates", df)

    # Set geometry from lat/lon
    cur.execute("""
        UPDATE cmip6_ocean_covariates
        SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        WHERE geom IS NULL;
    """)

    # Log breakdown
    cur.execute(
        "SELECT scenario, decade, count(*)"
        " FROM cmip6_ocean_covariates"
        " GROUP BY scenario, decade"
        " ORDER BY scenario, decade;"
    )
    for scenario, decade, count in cur.fetchall():
        logger.info("  %s / %s: %s rows", scenario, decade, f"{count:,}")

    logger.info(
        "Loaded %s CMIP6 ocean covariate records with geometry",
        f"{n:,}",
    )


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


def load_ocean_mask(cur) -> None:
    """Load Natural Earth ocean polygon into PostGIS.

    The ocean mask is used by dbt to flag H3 cells as ocean vs
    inland (Great Lakes, rivers, etc.) — replacing the naive
    ``depth_m >= 0`` heuristic that misclassifies deep freshwater.

    Args:
        cur: psycopg2 cursor.
    """
    if not OCEAN_MASK_FILE.exists():
        logger.warning("Ocean mask file not found: %s", OCEAN_MASK_FILE)
        return

    gdf = gpd.read_parquet(OCEAN_MASK_FILE)
    logger.info("Read %d ocean mask polygons", len(gdf))

    records = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        # Ensure MultiPolygon for consistent schema
        if geom.geom_type == "Polygon":
            from shapely.geometry import MultiPolygon

            geom = MultiPolygon([geom])
        records.append({"geom": geom.wkt})

    sql = """
        INSERT INTO ocean_mask (geom)
        VALUES %s
    """
    template = "(ST_GeomFromText(%(geom)s, 4326))"

    execute_values(cur, sql, records, template=template)
    logger.info("Loaded %d ocean mask polygons", len(records))


def load_bia_data(cur) -> None:
    """Load Cetacean Biologically Important Areas into PostGIS.

    Args:
        cur: psycopg2 cursor.
    """
    if not BIA_FILE.exists():
        logger.warning("BIA file not found: %s", BIA_FILE)
        return

    gdf = gpd.read_parquet(BIA_FILE)
    logger.info("Read %d BIA polygons", len(gdf))

    records = []
    for _, row in gdf.iterrows():
        records.append(
            {
                "bia_id": row.get("BIA_ID"),
                "region": row.get("region"),
                "sci_name": row.get("sci_name"),
                "cmn_name": row.get("cmn_name"),
                "stock_pop": row.get("stock_pop"),
                "bia_name": row.get("BIA_name"),
                "bia_type": row.get("BIA_type"),
                "bia_time": row.get("BIA_time"),
                "migr_dir": row.get("migr_dir"),
                "bia_size": float(row["BIA_size"])
                if pd.notna(row.get("BIA_size"))
                else None,
                "bia_months": row.get("BIA_months"),
                "area_sq_m": float(row["Shape__Area"])
                if pd.notna(row.get("Shape__Area"))
                else None,
                "perimeter_m": float(row["Shape__Length"])
                if pd.notna(row.get("Shape__Length"))
                else None,
                "geom": row.geometry.wkt,
            }
        )

    sql = """
        INSERT INTO cetacean_bia
            (bia_id, region, sci_name, cmn_name, stock_pop,
             bia_name, bia_type, bia_time, migr_dir, bia_size,
             bia_months, area_sq_m, perimeter_m, geom)
        VALUES %s
    """
    template = (
        "(%(bia_id)s, %(region)s, %(sci_name)s, %(cmn_name)s,"
        " %(stock_pop)s, %(bia_name)s, %(bia_type)s, %(bia_time)s,"
        " %(migr_dir)s, %(bia_size)s, %(bia_months)s,"
        " %(area_sq_m)s, %(perimeter_m)s,"
        " ST_GeomFromText(%(geom)s, 4326))"
    )

    execute_values(cur, sql, records, template=template)
    logger.info("Loaded %d BIA polygons", len(records))


def load_critical_habitat(cur) -> None:
    """Load whale ESA Critical Habitat designations into PostGIS.

    Args:
        cur: psycopg2 cursor.
    """
    if not CRITICAL_HABITAT_FILE.exists():
        logger.warning(
            "Critical habitat file not found: %s",
            CRITICAL_HABITAT_FILE,
        )
        return

    gdf = gpd.read_parquet(CRITICAL_HABITAT_FILE)
    logger.info("Read %d critical habitat polygons", len(gdf))

    records = []
    for _, row in gdf.iterrows():
        records.append(
            {
                "species_label": row.get("species_label"),
                "sci_name": row.get("SCIENAME"),
                "cmn_name": row.get("COMNAME"),
                "list_status": row.get("LISTSTATUS"),
                "ch_status": row.get("CHSTATUS"),
                "unit": row.get("UNIT"),
                "taxon": row.get("TAXON"),
                "lead_office": row.get("LEADOFFICE"),
                "pub_date": row.get("PUBDATE"),
                "effect_date": str(row["EFFECTDATE"])
                if pd.notna(row.get("EFFECTDATE"))
                else None,
                "area_sq_km": float(row["AREASqKm"])
                if pd.notna(row.get("AREASqKm"))
                else None,
                "hab_type": row.get("HABTYPE"),
                "layer_id": int(row["layer_id"])
                if pd.notna(row.get("layer_id"))
                else None,
                "is_proposed": bool(row.get("is_proposed", False)),
                "geom": row.geometry.wkt,
            }
        )

    sql = """
        INSERT INTO whale_critical_habitat
            (species_label, sci_name, cmn_name, list_status,
             ch_status, unit, taxon, lead_office, pub_date,
             effect_date, area_sq_km, hab_type, layer_id,
             is_proposed, geom)
        VALUES %s
    """
    template = (
        "(%(species_label)s, %(sci_name)s, %(cmn_name)s,"
        " %(list_status)s, %(ch_status)s, %(unit)s, %(taxon)s,"
        " %(lead_office)s, %(pub_date)s, %(effect_date)s,"
        " %(area_sq_km)s, %(hab_type)s, %(layer_id)s,"
        " %(is_proposed)s,"
        " ST_GeomFromText(%(geom)s, 4326))"
    )

    execute_values(cur, sql, records, template=template)
    logger.info("Loaded %d critical habitat polygons", len(records))


def load_shipping_lanes(cur) -> None:
    """Load shipping lane / routing regulation polygons into PostGIS.

    Args:
        cur: psycopg2 cursor.
    """
    if not SHIPPING_LANES_FILE.exists():
        logger.warning(
            "Shipping lanes file not found: %s",
            SHIPPING_LANES_FILE,
        )
        return

    gdf = gpd.read_parquet(SHIPPING_LANES_FILE)
    logger.info("Read %d shipping lane polygons", len(gdf))

    records = []
    for _, row in gdf.iterrows():
        records.append(
            {
                "zone_type": row.get("zone_type"),
                "name": row.get("name"),
                "description": row.get("description"),
                "geom": row.geometry.wkt,
            }
        )

    sql = """
        INSERT INTO shipping_lanes
            (zone_type, name, description, geom)
        VALUES %s
    """
    template = (
        "(%(zone_type)s, %(name)s, %(description)s, ST_GeomFromText(%(geom)s, 4326))"
    )

    execute_values(cur, sql, records, template=template)
    logger.info("Loaded %d shipping lane polygons", len(records))


def load_slow_zones(cur) -> None:
    """Load active Right Whale Slow Zones into PostGIS.

    These are ephemeral 15-day voluntary zones scraped from
    the NOAA Fisheries webpage. GeoJSON format.

    Args:
        cur: psycopg2 cursor.
    """
    import json

    if not SLOW_ZONES_FILE.exists():
        logger.warning("Slow zones file not found: %s", SLOW_ZONES_FILE)
        return

    with open(SLOW_ZONES_FILE) as f:
        geojson = json.load(f)

    features = geojson.get("features", [])
    if not features:
        logger.info("No active slow zones in file")
        return

    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    logger.info("Read %d slow zone features", len(gdf))

    records = []
    for _, row in gdf.iterrows():
        records.append(
            {
                "zone_name": row.get("zone_name"),
                "zone_type": row.get("zone_type"),
                "eff_start": row.get("effective_start"),
                "eff_end": row.get("effective_end"),
                "speed": int(row.get("speed_limit_knots", 10)),
                "voluntary": bool(row.get("voluntary", True)),
                "duration": int(row.get("duration_days", 15)),
                "north": float(row["north_lat"])
                if pd.notna(row.get("north_lat"))
                else None,
                "south": float(row["south_lat"])
                if pd.notna(row.get("south_lat"))
                else None,
                "east": float(row["east_lon"])
                if pd.notna(row.get("east_lon"))
                else None,
                "west": float(row["west_lon"])
                if pd.notna(row.get("west_lon"))
                else None,
                "geom": row.geometry.wkt,
            }
        )

    sql = """
        INSERT INTO right_whale_slow_zones
            (zone_name, zone_type, effective_start, effective_end,
             speed_limit_kn, voluntary, duration_days,
             north_lat, south_lat, east_lon, west_lon, geom)
        VALUES %s
    """
    template = (
        "(%(zone_name)s, %(zone_type)s,"
        " %(eff_start)s, %(eff_end)s,"
        " %(speed)s, %(voluntary)s, %(duration)s,"
        " %(north)s, %(south)s, %(east)s, %(west)s,"
        " ST_GeomFromText(%(geom)s, 4326))"
    )

    execute_values(cur, sql, records, template=template)
    logger.info("Loaded %d slow zone features", len(records))


def load_all_data(*, force: bool = False) -> None:
    """Load all raw data into PostGIS.

    Args:
        force: If True, truncate tables before loading so data is
               refreshed. Used by Dagster re-materialisation and
               after bbox / source-data changes.
    """
    logger.info("Connecting to PostGIS at %s:%s", DB_CONFIG["host"], DB_CONFIG["port"])
    if force:
        logger.info("Force mode — tables will be truncated before loading")

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
            "cmip6_ocean_covariates": load_cmip6_ocean_covariates,
            "seasonal_management_areas": load_sma_data,
            "ocean_mask": load_ocean_mask,
            "cetacean_bia": load_bia_data,
            "whale_critical_habitat": load_critical_habitat,
            "shipping_lanes": load_shipping_lanes,
            "right_whale_slow_zones": load_slow_zones,
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
                if force:
                    cur.execute(f"TRUNCATE TABLE {table} CASCADE;")
                    logger.info("Truncated %s (force mode)", table)
                else:
                    cur.execute(f"SELECT COUNT(*) FROM {table};")
                    count = cur.fetchone()[0]
                    if count > 0:
                        logger.info(
                            "Table %s already has %d rows — skipping",
                            table,
                            count,
                        )
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
    import argparse

    parser = argparse.ArgumentParser(description="Load raw data into PostGIS")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Truncate tables before loading (refresh all data)",
    )
    args = parser.parse_args()
    load_all_data(force=args.force)

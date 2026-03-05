"""Pandera schemas for raw data validation.

Each schema defines the expected columns, types, and value
constraints for one of our raw datasets. When we validate a
DataFrame against a schema, Pandera checks every rule and
returns a report of any failures.

Why Pandera?
  - Catches bad data *before* it reaches the database.
  - Schemas double as living documentation of what
    "clean" data looks like.
  - Integrates with pandas/geopandas DataFrames natively.
"""

import logging
import random
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

# ------------------------------------------------------------------
# AIS positions  (one row = one vessel ping)
# ------------------------------------------------------------------
ais_schema = DataFrameSchema(
    columns={
        "mmsi": Column(
            int,
            Check.in_range(100_000_000, 999_999_999),
            description="Maritime Mobile Service Identity (9-digit)",
        ),
        "base_date_time": Column(
            "str",
            nullable=False,
            description="UTC timestamp of the position report",
        ),
        "sog": Column(
            float,
            Check.ge(0),
            nullable=True,
            description="Speed over ground (knots)",
        ),
        "cog": Column(
            float,
            Check.in_range(0.0, 360.0),
            nullable=True,
            description="Course over ground (degrees)",
        ),
        "heading": Column(
            "Int16",
            Check.in_range(0, 511),
            nullable=True,
            description="True heading (511 = not available)",
        ),
        "vessel_name": Column("str", nullable=True),
        "imo": Column("str", nullable=True),
        "call_sign": Column("str", nullable=True),
        "vessel_type": Column("Int16", nullable=True),
        "status": Column("Int16", nullable=True),
        "length": Column(float, nullable=True),
        "width": Column("Int16", nullable=True),
        "draft": Column(float, nullable=True),
        "cargo": Column("Int16", nullable=True),
        "transceiver": Column("str", nullable=True),
    },
    name="AIS Positions",
    description="Raw AIS vessel position reports from MarineCadastre",
    # coerce=True tells Pandera to try casting before failing
    coerce=True,
)

# ------------------------------------------------------------------
# Cetacean sightings  (one row = one whale observation)
# ------------------------------------------------------------------
cetacean_schema = DataFrameSchema(
    columns={
        "scientificName": Column(
            "str",
            nullable=False,
            description="Binomial name, e.g. Balaenoptera musculus",
        ),
        "decimalLatitude": Column(
            float,
            Check.in_range(-2.0, 52.0),
            description="Latitude — clipped to US waters bounding box",
        ),
        "decimalLongitude": Column(
            float,
            Check.in_range(-180.0, -59.0),
            description="Longitude — clipped to US waters bounding box",
        ),
        "eventDate": Column(
            "str",
            nullable=True,
            description="Date of the sighting (ISO-8601 string)",
        ),
        "date_year": Column(
            float,
            Check.in_range(1700, 2030),
            nullable=True,
            description="Observation year extracted from eventDate",
        ),
        "order": Column(
            "str",
            nullable=True,
            description="Taxonomic order (usually Cetacea)",
        ),
        "family": Column(
            "str",
            nullable=True,
            description="Taxonomic family, e.g. Balaenopteridae",
        ),
        "species": Column(
            "str",
            nullable=True,
            description="Common or scientific species name",
        ),
    },
    name="Cetacean Sightings",
    description="Whale/dolphin observation records from OBIS",
    coerce=True,
)

# ------------------------------------------------------------------
# Marine Protected Areas  (one row = one MPA polygon)
# ------------------------------------------------------------------
mpa_schema = DataFrameSchema(
    columns={
        "Site_ID": Column(
            "str",
            nullable=False,
            description="Unique identifier for the MPA site",
        ),
        "Site_Name": Column(
            "str",
            nullable=False,
            description="Human-readable name of the protected area",
        ),
        "Gov_Level": Column(
            "str",
            nullable=True,
            description="Government level: Federal, State, etc.",
        ),
        "State": Column(
            "str",
            nullable=True,
            description="US state(s) the MPA falls within",
        ),
        "Prot_Lvl": Column(
            "str",
            nullable=True,
            description="Protection level classification",
        ),
        "Mgmt_Agen": Column(
            "str",
            nullable=True,
            description="Managing agency, e.g. NOAA, NPS",
        ),
        "IUCNcat": Column(
            "str",
            nullable=True,
            description="IUCN protection category (Ia, II, etc.)",
        ),
        "Estab_Yr": Column(
            float,
            Check(
                lambda d: (d == 0) | d.between(1800, 2030),
                error="Must be 0 (unknown) or between 1800–2030",
            ),
            nullable=True,
            description="Year the MPA was established",
        ),
        "AreaKm": Column(
            float,
            Check.gt(0),
            nullable=True,
            description="Total area in square kilometres",
        ),
        "AreaMar": Column(
            float,
            Check.ge(0),
            nullable=True,
            description="Marine area in square kilometres",
        ),
        "MarPercent": Column(
            float,
            Check.in_range(0, 100),
            nullable=True,
            description="Percentage of area that is marine",
        ),
    },
    name="Marine Protected Areas",
    description="MPA boundaries from NOAA MPA Inventory",
    coerce=True,
)


# ------------------------------------------------------------------
# Validation helpers
# ------------------------------------------------------------------
def validate_dataframe(
    df: "pd.DataFrame",
    schema: DataFrameSchema,
) -> dict:
    """Validate a DataFrame against a Pandera schema.

    Rather than raising on the first error, we collect *all*
    failures into a summary dict.  This lets us build a full
    data-quality report in one pass.

    Args:
        df: The raw DataFrame to check.
        schema: One of ais_schema / cetacean_schema / mpa_schema.

    Returns:
        dict with keys:
          - valid (bool): True if zero failures.
          - n_rows (int): Total rows checked.
          - n_failures (int): Number of individual cell failures.
          - failures (DataFrame|None): Pandera failure cases table.
    """
    try:
        schema.validate(df, lazy=True)
        return {
            "valid": True,
            "n_rows": len(df),
            "n_failures": 0,
            "failures": None,
        }
    except pa.errors.SchemaErrors as exc:
        return {
            "valid": False,
            "n_rows": len(df),
            "n_failures": len(exc.failure_cases),
            "failures": exc.failure_cases,
        }


def validate_ais_file(filepath: "Path") -> dict:
    """Validate a single AIS parquet file.

    Reads one day's AIS data and checks it against
    ais_schema.  Useful for spot-checking files or
    running across all 365 files in a loop.

    Args:
        filepath: Path to an AIS parquet file.

    Returns:
        Validation result dict (see validate_dataframe).
    """

    df = pd.read_parquet(filepath)
    return validate_dataframe(df, ais_schema)


def validate_all() -> dict:
    """Run validation on every raw dataset.

    Returns:
        dict keyed by dataset name, each value is a
        validation result dict.
    """

    results = {}

    # --- Cetacean sightings ---
    cet_path = Path("data/raw/cetacean/us_cetacean_sightings.parquet")
    if cet_path.exists():
        df = pd.read_parquet(cet_path)
        results["cetacean"] = validate_dataframe(df, cetacean_schema)

    # --- MPA ---
    mpa_path = Path("data/raw/mpa/mpa_inventory.parquet")
    if mpa_path.exists():
        gdf = gpd.read_parquet(mpa_path)
        results["mpa"] = validate_dataframe(gdf, mpa_schema)

    # --- AIS: sample first file only (full scan takes too long) ---
    ais_dir = Path("data/raw/ais")
    ais_files = sorted(ais_dir.glob("*.parquet"))
    if ais_files:
        for random_int in random.sample(range(365), 3):
            df = pd.read_parquet(ais_files[random_int])
            results[f"ais_sample_{random_int}"] = validate_dataframe(df, ais_schema)

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    results = validate_all()

    for name, result in results.items():
        status = "✅ PASS" if result["valid"] else "❌ FAIL"
        logger.info(
            "%s  %s — %d rows, %d failures",
            status,
            name,
            result["n_rows"],
            result["n_failures"],
        )
        if result["failures"] is not None:
            # Show first few failure cases
            logger.info(
                "Sample failures:\n%s",
                result["failures"].head(10).to_string(),
            )

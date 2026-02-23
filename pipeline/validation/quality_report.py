"""Data quality report for all raw datasets.

Produces a summary of completeness, value distributions, and
schema validation results for each dataset. Run with:
    python -m pipeline.validation.quality_report

This generates a console report. For visual exploration, see
notebooks/data_quality/01_quality_report.ipynb.
"""

import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Data paths
AIS_DIR = Path("data/raw/ais")
CETACEAN_FILE = Path("data/raw/cetacean/us_cetacean_sightings.parquet")
MPA_FILE = Path("data/raw/mpa/mpa_inventory.parquet")


def completeness_report(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Calculate per-column completeness (% non-null).

    This is the single most useful data quality metric.
    A column that's 95% null is very different from one
    that's 5% null — even if both "pass" a nullable check.

    Args:
        df: The DataFrame to analyse.
        name: Dataset name for logging.

    Returns:
        DataFrame with columns: column, non_null_count,
        total_rows, completeness_pct.
    """
    total = len(df)
    records = []
    for col in df.columns:
        non_null = df[col].notna().sum()
        records.append(
            {
                "column": col,
                "non_null_count": int(non_null),
                "total_rows": total,
                "completeness_pct": round(100 * non_null / total, 2),
            }
        )

    report = pd.DataFrame(records)
    logger.info(
        "\n📊 Completeness — %s (%d rows)\n%s",
        name,
        total,
        report.to_string(index=False),
    )
    return report


def numeric_summary(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Summary statistics for all numeric columns.

    Goes beyond pandas .describe() by adding the percentage
    of zeros — useful for spotting sentinel values (like
    Estab_Yr = 0 meaning "unknown").

    Args:
        df: The DataFrame to analyse.
        name: Dataset name for logging.

    Returns:
        DataFrame with min, max, mean, median, std, zero_pct
        for each numeric column.
    """
    num_cols = df.select_dtypes(include="number").columns
    records = []
    for col in num_cols:
        series = df[col].dropna()
        if len(series) == 0:
            continue
        records.append(
            {
                "column": col,
                "min": series.min(),
                "max": series.max(),
                "mean": round(series.mean(), 2),
                "median": round(series.median(), 2),
                "std": round(series.std(), 2),
                "zero_pct": round(100 * (series == 0).sum() / len(series), 2),
            }
        )

    report = pd.DataFrame(records)
    logger.info(
        "\n📈 Numeric summary — %s\n%s",
        name,
        report.to_string(index=False),
    )
    return report


def categorical_summary(
    df: pd.DataFrame,
    name: str,
    max_unique: int = 20,
) -> pd.DataFrame:
    """Value counts for low-cardinality string columns.

    Only reports columns with ≤ max_unique distinct values.
    High-cardinality columns (like vessel_name) would flood
    the report — we skip those.

    Args:
        df: The DataFrame to analyse.
        name: Dataset name for logging.
        max_unique: Skip columns with more unique values.

    Returns:
        DataFrame with column, n_unique, top_value, top_count.
    """
    str_cols = df.select_dtypes(include=["object", "str"]).columns
    records = []
    for col in str_cols:
        n_unique = df[col].nunique()
        if n_unique > max_unique:
            records.append(
                {
                    "column": col,
                    "n_unique": n_unique,
                    "top_value": "(high cardinality — skipped)",
                    "top_count": None,
                }
            )
            continue

        top = df[col].value_counts().head(1)
        records.append(
            {
                "column": col,
                "n_unique": n_unique,
                "top_value": top.index[0] if len(top) > 0 else None,
                "top_count": int(top.iloc[0]) if len(top) > 0 else 0,
            }
        )

    report = pd.DataFrame(records)
    logger.info(
        "\n🏷️  Categorical summary — %s\n%s",
        name,
        report.to_string(index=False),
    )
    return report


def report_cetacean() -> dict:
    """Run all quality checks on cetacean sightings."""
    from pipeline.validation.schemas import (
        cetacean_schema,
        validate_dataframe,
    )

    logger.info("=" * 60)
    logger.info("🐋 CETACEAN SIGHTINGS")
    logger.info("=" * 60)

    df = pd.read_parquet(CETACEAN_FILE)

    validation = validate_dataframe(df, cetacean_schema)
    status = "✅ PASS" if validation["valid"] else "❌ FAIL"
    logger.info(
        "Schema validation: %s (%d failures)",
        status,
        validation["n_failures"],
    )

    return {
        "validation": validation,
        "completeness": completeness_report(df, "cetacean"),
        "numeric": numeric_summary(df, "cetacean"),
        "categorical": categorical_summary(df, "cetacean"),
    }


def report_mpa() -> dict:
    """Run all quality checks on Marine Protected Areas."""
    import geopandas as gpd

    from pipeline.validation.schemas import (
        mpa_schema,
        validate_dataframe,
    )

    logger.info("=" * 60)
    logger.info("🏝️  MARINE PROTECTED AREAS")
    logger.info("=" * 60)

    gdf = gpd.read_parquet(MPA_FILE)

    validation = validate_dataframe(gdf, mpa_schema)
    status = "✅ PASS" if validation["valid"] else "❌ FAIL"
    logger.info(
        "Schema validation: %s (%d failures)",
        status,
        validation["n_failures"],
    )

    # Geometry-specific checks (Pandera can't do these)
    n_invalid = (~gdf.geometry.is_valid).sum()
    n_empty = gdf.geometry.is_empty.sum()
    logger.info(
        "🗺️  Geometry: %d invalid, %d empty (of %d)",
        n_invalid,
        n_empty,
        len(gdf),
    )

    return {
        "validation": validation,
        "completeness": completeness_report(gdf, "mpa"),
        "numeric": numeric_summary(gdf, "mpa"),
        "categorical": categorical_summary(gdf, "mpa"),
        "invalid_geom": int(n_invalid),
        "empty_geom": int(n_empty),
    }


def report_ais_sample() -> dict:
    """Run quality checks on a single AIS file (first day)."""
    from pipeline.validation.schemas import (
        ais_schema,
        validate_dataframe,
    )

    logger.info("=" * 60)
    logger.info("🚢 AIS POSITIONS (sample: 1 file)")
    logger.info("=" * 60)

    ais_files = sorted(AIS_DIR.glob("*.parquet"))
    if not ais_files:
        logger.warning("No AIS files found")
        return {}

    df = pd.read_parquet(ais_files[0])
    logger.info("Sampled: %s (%d rows)", ais_files[0].name, len(df))

    validation = validate_dataframe(df, ais_schema)
    status = "✅ PASS" if validation["valid"] else "❌ FAIL"
    logger.info(
        "Schema validation: %s (%d failures)",
        status,
        validation["n_failures"],
    )

    return {
        "validation": validation,
        "completeness": completeness_report(df, "ais_sample"),
        "numeric": numeric_summary(df, "ais_sample"),
        "categorical": categorical_summary(df, "ais_sample", max_unique=10),
    }


def run_full_report() -> dict:
    """Run all quality reports and print a final summary.

    Returns:
        dict keyed by dataset name with all sub-reports.
    """
    results = {}

    if CETACEAN_FILE.exists():
        results["cetacean"] = report_cetacean()
    else:
        logger.warning("Skipping cetacean — file not found")

    if MPA_FILE.exists():
        results["mpa"] = report_mpa()
    else:
        logger.warning("Skipping MPA — file not found")

    if AIS_DIR.exists():
        results["ais_sample"] = report_ais_sample()
    else:
        logger.warning("Skipping AIS — directory not found")

    # ---- Final summary table ----
    logger.info("\n" + "=" * 60)
    logger.info("📋 FINAL SUMMARY")
    logger.info("=" * 60)

    summary_rows = []
    for name, report in results.items():
        v = report.get("validation", {})
        comp = report.get("completeness")
        avg_completeness = (
            round(comp["completeness_pct"].mean(), 1) if comp is not None else None
        )
        summary_rows.append(
            {
                "dataset": name,
                "rows": v.get("n_rows", 0),
                "schema_valid": "✅" if v.get("valid") else "❌",
                "failures": v.get("n_failures", 0),
                "avg_completeness_%": avg_completeness,
            }
        )

    summary = pd.DataFrame(summary_rows)
    logger.info("\n%s", summary.to_string(index=False))

    return results


if __name__ == "__main__":
    run_full_report()

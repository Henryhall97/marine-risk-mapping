"""Aggregate raw AIS data into H3 hex cells using DuckDB.

Reads all 365 daily AIS parquet files (~3.1B pings),
assigns each ping to an H3 resolution-7 cell (~1.2km),
and aggregates traffic metrics per cell per month.

This compresses 3.1B rows → ~15M summary rows, making
it feasible to load into PostGIS for spatial joins.

Run with:
    uv run python -m pipeline.aggregation.aggregate_ais
"""

import argparse
import logging
import tempfile
import time
from pathlib import Path

import duckdb
import psycopg2
from psycopg2.extras import execute_values

from pipeline.config import (
    AIS_H3_PARQUET,
    AIS_H3_TEST_PARQUET,
    AIS_RAW_DIR,
    AIS_REQUIRED_LENGTH_M,
    AIS_VTD_PARQUET,
    AIS_VTD_TEST_PARQUET,
    AIS_YEARS,
    DB_CONFIG,
    DEEP_DRAFT_M,
    H3_RESOLUTION,
    HIGH_SPEED_KNOTS,
    LARGE_VESSEL_LENGTH_M,
    MAYETTE_MASS_A,
    MAYETTE_MASS_B,
    NAV_STATUS_RESTRICTED,
    NAV_STATUS_UNDERWAY,
    NIGHT_END_HOUR,
    NIGHT_START_HOUR,
    SEAWATER_DENSITY_T_PER_M3,
    VESSEL_BLOCK_COEFFICIENT,
    VESSEL_TYPE_CODES,
    VT_LETHALITY_BETA0,
    VT_LETHALITY_BETA1,
    VTD_GRID_PATH_MAX_CELLS,
    VTD_MAX_GAP_HOURS,
    VTD_MAX_IMPLIED_SPEED_KN,
    WIDE_VESSEL_WIDTH_M,
)
from pipeline.utils import to_python

# Processed output directory (derived from config)
OUTPUT_DIR = AIS_H3_PARQUET.parent
OUTPUT_FILE = AIS_H3_PARQUET
TEST_OUTPUT_FILE = AIS_H3_TEST_PARQUET
VTD_OUTPUT_FILE = AIS_VTD_PARQUET
VTD_TEST_OUTPUT_FILE = AIS_VTD_TEST_PARQUET

# Resource defaults — keep the laptop usable during long runs
DEFAULT_THREADS = 4
DEFAULT_MEMORY = "8GB"


def _sql_in(codes: list[int] | tuple[int, ...]) -> str:
    """Format a sequence of ints for a SQL IN clause: '30, 1001, 1002'."""
    return ", ".join(str(c) for c in codes)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_connection(
    threads: int = DEFAULT_THREADS,
    memory: str = DEFAULT_MEMORY,
) -> duckdb.DuckDBPyConnection:
    """Open DuckDB with spatial + H3 extensions loaded.

    We use a fresh in-memory connection (not the persistent
    database) to avoid locking conflicts with other scripts.
    The persistent DB has our views; this connection reads
    the parquet files directly.

    Args:
        threads: Max worker threads (default 4 to keep laptop usable).
        memory: Memory limit string, e.g. '8GB'.
    """
    conn = duckdb.connect()

    # Cap resources so the laptop stays responsive
    conn.execute(f"SET threads = {threads};")
    conn.execute(f"SET memory_limit = '{memory}';")

    # In-memory connections do NOT spill to disk by default, so a large
    # aggregation (e.g. the VTD strata cross-product) hard-OOMs at the
    # memory limit. Point DuckDB at a temp directory to enable disk spill
    # and disable insertion-order preservation so COPY can stream output
    # instead of buffering every row in memory.
    temp_dir = Path(tempfile.gettempdir()) / "marine_risk_duckdb"
    temp_dir.mkdir(parents=True, exist_ok=True)
    conn.execute(f"SET temp_directory = '{temp_dir}';")
    conn.execute("SET preserve_insertion_order = false;")
    logger.info("DuckDB resource limits: threads=%d, memory=%s", threads, memory)

    # Spatial: extracts lat/lon from GeoParquet geometry
    conn.execute("INSTALL spatial; LOAD spatial;")

    # H3: assigns hex cells — community extension
    conn.execute("INSTALL h3 FROM community; LOAD h3;")

    logger.info("DuckDB ready with spatial + H3 extensions")
    return conn


def build_aggregation_query(*, test_mode: bool = False) -> str:
    """Build the two-pass SQL that aggregates AIS pings to H3 cells.

    Pass 1 — vessel_summaries: Collapse pings to one row per
      (cell, month, vessel). This removes ping-rate bias: a Class A
      ship broadcasting every 2 seconds and a Class B every 30 seconds
      each get one row with their median speed, max size, etc.

    Pass 2 — cell aggregation: Aggregate vessel summaries into cell-
      level metrics. Produces both "ping-weighted" columns (good for
      temporal exposure) and "vessel-weighted" columns (fair comparison
      across vessel types).

    DuckDB executes this as a streaming pipeline — it doesn't load
    all 3.1B rows into memory at once.

    All domain constants (vessel type codes, speed/size thresholds,
    day/night boundaries, nav status codes) are defined in
    pipeline/config.py — see VESSEL_TYPE_CODES, HIGH_SPEED_KNOTS,
    LARGE_VESSEL_LENGTH_M, WIDE_VESSEL_WIDTH_M, DEEP_DRAFT_M,
    NIGHT_START_HOUR, NIGHT_END_HOUR, NAV_STATUS_*.

    Args:
        test_mode: If True, only process January data for fast validation.

    Returns:
        SQL query string.
    """
    if test_mode:
        first_year = AIS_YEARS[0]
        ais_glob = str(AIS_RAW_DIR / f"ais-{first_year}-01-*.parquet")
        logger.info("TEST MODE: processing January %d only", first_year)
    else:
        ais_glob = str(AIS_RAW_DIR / "*.parquet")

    # Pre-format vessel type codes for SQL IN clauses
    fishing = _sql_in(VESSEL_TYPE_CODES["fishing"])
    tug = _sql_in(VESSEL_TYPE_CODES["tug"])
    passenger = _sql_in(VESSEL_TYPE_CODES["passenger"])
    cargo = _sql_in(VESSEL_TYPE_CODES["cargo"])
    tanker = _sql_in(VESSEL_TYPE_CODES["tanker"])
    pleasure = _sql_in(VESSEL_TYPE_CODES["pleasure"])
    military = _sql_in(VESSEL_TYPE_CODES["military"])
    restricted = _sql_in(NAV_STATUS_RESTRICTED)

    # Per-category block coefficient Cb for the Mayette displacement-draft
    # fallback. Built from config so VESSEL_BLOCK_COEFFICIENT stays the
    # single source of truth. 'military' folds to 'other' in vessel_typed,
    # so the else branch covers it.
    block_coef_case = (
        "case v.vessel_category\n"
        + "\n".join(
            f"        when '{cat}' then {cb}"
            for cat, cb in VESSEL_BLOCK_COEFFICIENT.items()
            if cat != "other"
        )
        + f"\n        else {VESSEL_BLOCK_COEFFICIENT['other']}\n    end"
    )

    return f"""
    -- ================================================================
    -- CTE 1: Extract raw fields, filter to moving vessels
    -- ================================================================
    with raw_pings as (

        select
            mmsi,
            base_date_time,
            sog,
            cog,
            vessel_type,
            status,
            -- 0 = "not reported" in AIS; convert to NULL
            -- so aggregates (avg, p95, count) reflect real values only
            nullif(length, 0) as length,
            nullif(width, 0)  as width,
            nullif(draft, 0)  as draft,
            ST_Y(geometry) as lat,
            ST_X(geometry) as lon
        from read_parquet('{ais_glob}')
        where sog > 0

    ),

    -- ================================================================
    -- CTE 2: Assign H3 cell, month, and local solar time
    -- ================================================================
    with_h3 as (

        select
            *,
            h3_latlng_to_cell(lat, lon, {H3_RESOLUTION})
                as h3_cell,
            date_trunc('month', base_date_time::timestamp)
                as month,
            -- Approximate local solar hour (double-mod for negatives)
            ((extract(hour from base_date_time::timestamp)
              + lon / 15.0) % 24 + 24) % 24
                as local_hour
        from raw_pings

    ),

    -- ================================================================
    -- CTE 3: Add day/night boolean
    -- ================================================================
    with_time_of_day as (

        select
            *,
            (local_hour < {NIGHT_END_HOUR}
                or local_hour >= {NIGHT_START_HOUR}) as is_night
        from with_h3

    ),

    -- ================================================================
    -- PASS 1: One row per (cell, month, vessel)
    -- Removes ping-rate bias — each vessel counts equally regardless
    -- of whether it broadcasts every 2s (Class A) or 30s (Class B).
    -- ================================================================
    vessel_summaries as (

        select
            h3_cell,
            month,
            mmsi,

            -- Ping count for this vessel in this cell/month
            count(*)                          as vessel_ping_count,

            -- Use the FIRST non-null value for static vessel attributes
            -- (these don't change ping-to-ping for the same MMSI)
            max(vessel_type)                  as vessel_type,
            max(length)                       as vessel_length,
            max(width)                        as vessel_width,
            max(draft)                        as vessel_draft,

            -- Speed: median is robust to outlier pings
            percentile_cont(0.5) within group
                (order by sog)                as vessel_median_speed,
            max(sog)                          as vessel_max_speed,

            -- Pings above NOAA lethal threshold (overall + day/night)
            count(*) filter (
                where sog > {HIGH_SPEED_KNOTS}
            )                                 as vessel_high_speed_pings,
            count(*) filter (
                where sog > {HIGH_SPEED_KNOTS} and not is_night
            )                                 as vessel_day_high_speed_pings,
            count(*) filter (
                where sog > {HIGH_SPEED_KNOTS} and is_night
            )                                 as vessel_night_high_speed_pings,

            -- Nav status counts for this vessel
            count(*) filter (
                where status = {NAV_STATUS_UNDERWAY}
            )                                 as vessel_underway_pings,
            count(*) filter (
                where status in ({restricted})
            )                                 as vessel_restricted_pings,
            count(status)                     as vessel_status_reports,

            -- Day/night ping split for this vessel
            count(*) filter (
                where not is_night
            )                                 as vessel_day_pings,
            count(*) filter (
                where is_night
            )                                 as vessel_night_pings,

            -- Day/night speed for this vessel
            avg(sog) filter (
                where not is_night
            )                                 as vessel_day_avg_speed,
            avg(sog) filter (
                where is_night
            )                                 as vessel_night_avg_speed,

            -- COG: sin/cos components for circular statistics
            -- (plain stddev breaks at the 360°/0° wrap)
            avg(sin(radians(cog)))            as vessel_sin_cog,
            avg(cos(radians(cog)))            as vessel_cos_cog,
            count(cog)                        as vessel_cog_reports

        from with_time_of_day
        group by h3_cell, month, mmsi

    ),

    -- ================================================================
    -- CTE 4: Categorise vessel type for stratified draft imputation
    -- ================================================================
    vessel_typed as (

        select
            *,
            case
                when vessel_type between 70 and 79
                    or vessel_type in ({cargo})           then 'cargo'
                when vessel_type between 80 and 89
                    or vessel_type in ({tanker})           then 'tanker'
                when vessel_type between 60 and 69
                    or vessel_type in ({passenger})        then 'passenger'
                when vessel_type = 30
                    or vessel_type in ({fishing})          then 'fishing'
                when vessel_type in ({tug})                then 'tug'
                when vessel_type in ({pleasure})           then 'pleasure'
                else 'other'
            end as vessel_category
        from vessel_summaries

    ),

    -- ================================================================
    -- CTE 5: Per-type regression coefficients + medians for draft
    -- Fitted from vessels that report both draft and length.
    -- Types with R²<0.05 (tugs, fishing) use median-only fallback.
    -- ================================================================
    draft_regression as (

        select
            vessel_category,
            regr_slope(vessel_draft, vessel_length)     as slope,
            regr_intercept(vessel_draft, vessel_length)  as intercept,
            regr_r2(vessel_draft, vessel_length)          as r2,
            count(vessel_draft)                           as n_with_draft,
            median(vessel_draft)                          as type_median_draft
        from vessel_typed
        where vessel_draft is not null
        group by vessel_category

    ),

    -- Global fallback median for vessels with no type match
    draft_global as (

        select median(vessel_draft) as global_median_draft
        from vessel_typed
        where vessel_draft is not null

    ),

    -- ================================================================
    -- CTE 6: Impute missing drafts per vessel
    -- Priority: (1) reported draft, (2) type regression from length
    -- if R²≥0.05 and n≥20, (3) Mayette displacement solve from
    -- length×beam, (4) type median, (5) global median.
    -- Clamped to [0.5, 25.0] metres.
    -- ================================================================
    vessel_with_draft as (

        select
            v.*,
            coalesce(
                v.vessel_draft,
                -- Regression imputation (only if the type regression is useful)
                case when v.vessel_length is not null
                          and dr.r2 >= 0.05
                          and dr.n_with_draft >= 20
                     then greatest(0.5, least(25.0,
                          dr.intercept + dr.slope * v.vessel_length))
                end,
                -- Mayette (2026) displacement solve: T = mass / (ρ·L·B·Cb),
                -- mass = MASS_A·L^MASS_B. Needs both length AND beam.
                -- Physics-based fallback when the type regression is weak
                -- but the vessel reports geometry.
                case when v.vessel_length is not null
                          and v.vessel_width is not null
                          and v.vessel_length > 0
                          and v.vessel_width > 0
                     then greatest(0.5, least(25.0,
                          ({MAYETTE_MASS_A} * power(v.vessel_length,
                              {MAYETTE_MASS_B}))
                          / ({SEAWATER_DENSITY_T_PER_M3} * v.vessel_length
                              * v.vessel_width * ({block_coef_case}))))
                end,
                -- Type median fallback (tugs, fishing, etc.)
                dr.type_median_draft,
                -- Last resort: global median
                gs.global_median_draft
            ) as vessel_draft_imputed,
            v.vessel_draft is null as draft_was_imputed
        from vessel_typed v
        left join draft_regression dr
            on v.vessel_category = dr.vessel_category
        cross join draft_global gs

    ),

    -- ================================================================
    -- CTE 7: Add Vanderlaan & Taggart (2007) speed-lethality per vessel
    -- P(lethal|speed) = 1 / (1 + exp(-(β₀ + β₁ × speed_knots)))
    -- Applied per-vessel BEFORE aggregation to avoid Jensen's inequality
    -- bias from averaging speeds then applying the non-linear function.
    -- ================================================================
    vessel_with_lethality as (

        select
            *,
            1.0 / (1.0 + exp(-({VT_LETHALITY_BETA0}
                + {VT_LETHALITY_BETA1}
                * coalesce(vessel_median_speed, 0))))
                as vessel_lethality_prob
        from vessel_with_draft

    )

    -- ================================================================
    -- PASS 2: Aggregate vessel summaries to cell + month
    -- Produces both ping-weighted (exposure) and vessel-weighted
    -- (debiased) metrics for downstream modelling.
    -- ================================================================
    select
        h3_cell,
        month,

        -- Cell centroid (saves downstream H3 decoding)
        h3_cell_to_lat(h3_cell)               as cell_lat,
        h3_cell_to_lng(h3_cell)               as cell_lon,

        -- ── Traffic volume ──────────────────────────────
        sum(vessel_ping_count)                as ping_count,
        count(*)                              as unique_vessels,

        -- ── AIS-required traffic (IWC standard scoping) ──
        -- Vessels LEGALLY mandated to broadcast AIS (SOLAS Class-A
        -- proxy): length ≥ AIS_REQUIRED_LENGTH_M OR any passenger
        -- vessel type regardless of length. Emitted ALONGSIDE the
        -- all-traffic counts so non-AIS small craft are an explicit,
        -- documented blind spot (Rockwood convention) rather than a
        -- silent omission. See pipeline/config.py AIS_REQUIRED_LENGTH_M.
        count(*) filter (
            where vessel_length >= {AIS_REQUIRED_LENGTH_M}
               or vessel_type in ({passenger})
        )                                     as ais_required_vessels,
        sum(vessel_ping_count) filter (
            where vessel_length >= {AIS_REQUIRED_LENGTH_M}
               or vessel_type in ({passenger})
        )                                     as ais_required_pings,

        -- ── Ping-weighted speed (exposure measure) ──────
        -- A vessel lingering for hours DOES create more
        -- collision risk, so ping-weighted is still valid.
        sum(vessel_ping_count * vessel_median_speed)
            / nullif(sum(vessel_ping_count), 0)
                                              as pw_avg_speed_knots,
        max(vessel_max_speed)                 as max_speed_knots,
        sum(vessel_high_speed_pings)          as high_speed_pings,
        count(*) filter (
            where vessel_high_speed_pings > 0
        )                                     as high_speed_vessel_count,

        -- ── Vessel-weighted speed (debiased) ────────────
        -- Each vessel counts once regardless of ping rate.
        avg(vessel_median_speed)              as vw_avg_speed_knots,
        percentile_cont(0.5) within group
            (order by vessel_median_speed)    as vw_median_speed_knots,

        -- ── Speed-lethality (Vanderlaan & Taggart 2007) ─
        -- Per-vessel lethality averaged (exact, no Jensen's bias)
        avg(vessel_lethality_prob)            as vw_avg_lethality,
        sum(vessel_ping_count * vessel_lethality_prob)
            / nullif(sum(vessel_ping_count), 0)
                                              as pw_avg_lethality,
        max(vessel_lethality_prob)            as max_lethality,

        -- ── Risk fractions ──────────────────────────────
        count(*) filter (
            where vessel_high_speed_pings > 0
        )::double precision
            / nullif(count(*)::double precision, 0)
                                              as high_speed_fraction,
        -- Uses imputed draft (regression from length where missing)
        count(*) filter (
            where vessel_draft_imputed > {DEEP_DRAFT_M}
        )::double precision
            / nullif(count(*)::double precision, 0)
                                              as draft_risk_fraction,

        -- ── Vessel size: length ─────────────────────────
        -- Ping-weighted average
        sum(vessel_ping_count * vessel_length)
            / nullif(sum(
                case when vessel_length is not null
                     then vessel_ping_count end
              ), 0)                           as pw_avg_length_m,
        -- Vessel-weighted average
        avg(vessel_length)                    as vw_avg_length_m,
        max(vessel_length)                    as max_length_m,
        percentile_cont(0.95) within group
            (order by vessel_length)          as p95_length_m,
        count(vessel_length)                  as length_report_count,
        count(*) filter (
            where vessel_length > {LARGE_VESSEL_LENGTH_M}
        )                                     as large_vessel_count,

        -- ── Vessel size: width ──────────────────────────
        sum(vessel_ping_count * vessel_width)
            / nullif(sum(
                case when vessel_width is not null
                     then vessel_ping_count end
              ), 0)                           as pw_avg_width_m,
        avg(vessel_width)                     as vw_avg_width_m,
        max(vessel_width)                     as max_width_m,
        percentile_cont(0.95) within group
            (order by vessel_width)           as p95_width_m,
        count(vessel_width)                   as width_report_count,
        count(*) filter (
            where vessel_width > {WIDE_VESSEL_WIDTH_M}
        )                                     as wide_vessel_count,

        -- ── Vessel size: draft ──────────────────────────
        sum(vessel_ping_count * vessel_draft)
            / nullif(sum(
                case when vessel_draft is not null
                     then vessel_ping_count end
              ), 0)                           as pw_avg_draft_m,
        avg(vessel_draft)                     as vw_avg_draft_m,
        max(vessel_draft)                     as max_draft_m,
        percentile_cont(0.95) within group
            (order by vessel_draft)           as p95_draft_m,
        count(vessel_draft)                   as draft_report_count,
        count(*) filter (
            where vessel_draft > {DEEP_DRAFT_M}
        )                                     as deep_draft_count,

        -- ── Draft imputation stats ──────────────────────
        -- Imputed average draft (uses regression from length where missing)
        avg(vessel_draft_imputed)             as vw_avg_draft_imputed_m,
        count(*) filter (
            where draft_was_imputed
        )                                     as draft_imputed_count,

        -- ── Course diversity (circular statistics) ──────
        -- Uses Yamartino method: σ = √(−2·ln(R)) in degrees
        -- where R = mean resultant length of COG bearings.
        -- least/greatest guard against floating-point edge cases.

        -- Per-vessel maneuvering signal:
        -- How much does each vessel change heading in this cell?
        -- High value = vessel is turning/maneuvering frequently.
        avg(
            case when power(vessel_sin_cog, 2)
                    + power(vessel_cos_cog, 2) > 1e-10
                 then degrees(sqrt(greatest(-2.0 * ln(
                     greatest(least(sqrt(
                         power(vessel_sin_cog, 2)
                       + power(vessel_cos_cog, 2)
                     ), 1.0), 1e-10)
                 ), 0.0)))
            end
        )                                     as avg_circ_cog_stddev,

        -- Cross-vessel heading diversity:
        -- Are ships all going the same direction or crossing?
        -- High value = vessels heading in many different directions.
        -- Normalise each vessel to unit heading vector, average
        -- those unit vectors, then compute circular stddev.
        case when count(vessel_sin_cog) >= 2
             then degrees(sqrt(greatest(-2.0 * ln(
                 greatest(least(sqrt(
                     power(avg(
                         vessel_sin_cog
                         / nullif(sqrt(
                             power(vessel_sin_cog, 2)
                           + power(vessel_cos_cog, 2)
                         ), 0)
                     ), 2)
                   + power(avg(
                         vessel_cos_cog
                         / nullif(sqrt(
                             power(vessel_sin_cog, 2)
                           + power(vessel_cos_cog, 2)
                         ), 0)
                     ), 2)
                 ), 1.0), 1e-10)
             ), 0.0)))
        end                                   as cross_vessel_circ_cog_stddev,

        count(vessel_sin_cog)                 as cog_vessel_count,
        sum(vessel_cog_reports)               as cog_report_count,

        -- ── Navigational status ─────────────────────────
        -- Ping-weighted (exposure time in each status)
        sum(vessel_underway_pings)            as underway_engine_pings,
        sum(vessel_restricted_pings)          as restricted_maneuver_pings,
        sum(vessel_status_reports)            as status_report_count,
        -- Vessel-weighted (how many vessels were restricted)
        count(*) filter (
            where vessel_restricted_pings > 0
        )                                     as restricted_vessel_count,

        -- ── Day / Night split ───────────────────────────
        -- Ping-weighted (total exposure by time of day)
        sum(vessel_day_pings)                 as day_ping_count,
        sum(vessel_night_pings)               as night_ping_count,
        -- Vessel-weighted (how many distinct vessels by time of day)
        count(*) filter (
            where vessel_day_pings > 0
        )                                     as day_unique_vessels,
        count(*) filter (
            where vessel_night_pings > 0
        )                                     as night_unique_vessels,
        -- Vessel-weighted avg speed by time of day
        avg(vessel_day_avg_speed)             as vw_day_avg_speed_knots,
        avg(vessel_night_avg_speed)           as vw_night_avg_speed_knots,
        -- Day/night high-speed: exact counts (not estimated)
        sum(vessel_day_high_speed_pings)      as day_high_speed_pings,
        sum(vessel_night_high_speed_pings)    as night_high_speed_pings,
        count(*) filter (
            where vessel_day_high_speed_pings > 0
        )                                     as day_high_speed_vessel_count,
        count(*) filter (
            where vessel_night_high_speed_pings > 0
        )                                     as night_high_speed_vessel_count,

        -- ── Vessel type: vessel-weighted (debiased) ─────
        count(*) filter (
            where vessel_type in ({fishing})
        )                                     as fishing_vessels,
        count(*) filter (
            where vessel_type in ({tug})
        )                                     as tug_vessels,
        count(*) filter (
            where vessel_type in ({passenger})
        )                                     as passenger_vessels,
        count(*) filter (
            where vessel_type in ({cargo})
        )                                     as cargo_vessels,
        count(*) filter (
            where vessel_type in ({tanker})
        )                                     as tanker_vessels,
        count(*) filter (
            where vessel_type in ({pleasure})
        )                                     as pleasure_vessels,
        count(*) filter (
            where vessel_type in ({military})
        )                                     as military_vessels,

        -- ── Vessel type: ping-weighted (exposure time) ──
        sum(vessel_ping_count) filter (
            where vessel_type in ({fishing})
        )                                     as fishing_pings,
        sum(vessel_ping_count) filter (
            where vessel_type in ({tug})
        )                                     as tug_pings,
        sum(vessel_ping_count) filter (
            where vessel_type in ({passenger})
        )                                     as passenger_pings,
        sum(vessel_ping_count) filter (
            where vessel_type in ({cargo})
        )                                     as cargo_pings,
        sum(vessel_ping_count) filter (
            where vessel_type in ({tanker})
        )                                     as tanker_pings,
        sum(vessel_ping_count) filter (
            where vessel_type in ({pleasure})
        )                                     as pleasure_pings,
        sum(vessel_ping_count) filter (
            where vessel_type in ({military})
        )                                     as military_pings

    from vessel_with_lethality
    group by h3_cell, month
    """


def _vessel_category_case(type_col: str) -> str:
    """Build the SQL CASE that maps a raw AIS vessel_type to a category.

    Mirrors the ping-based aggregation's vessel_typed CTE but keeps a
    distinct 'military' bucket (the ping query folds it into 'other')
    so the per-class teleport threshold can be applied.
    """
    cargo = _sql_in(VESSEL_TYPE_CODES["cargo"])
    tanker = _sql_in(VESSEL_TYPE_CODES["tanker"])
    passenger = _sql_in(VESSEL_TYPE_CODES["passenger"])
    fishing = _sql_in(VESSEL_TYPE_CODES["fishing"])
    tug = _sql_in(VESSEL_TYPE_CODES["tug"])
    pleasure = _sql_in(VESSEL_TYPE_CODES["pleasure"])
    military = _sql_in(VESSEL_TYPE_CODES["military"])
    return f"""
            case
                when {type_col} between 70 and 79
                    or {type_col} in ({cargo})      then 'cargo'
                when {type_col} between 80 and 89
                    or {type_col} in ({tanker})     then 'tanker'
                when {type_col} between 60 and 69
                    or {type_col} in ({passenger})  then 'passenger'
                when {type_col} = 30
                    or {type_col} in ({fishing})    then 'fishing'
                when {type_col} in ({tug})          then 'tug'
                when {type_col} in ({pleasure})     then 'pleasure'
                when {type_col} in ({military})     then 'military'
                else 'other'
            end"""


def _teleport_threshold_case(cat_col: str) -> str:
    """Build the SQL CASE mapping vessel_category → max implied speed (kn)."""
    whens = "\n".join(
        f"                when '{cat}' then {kn}"
        for cat, kn in VTD_MAX_IMPLIED_SPEED_KN.items()
    )
    return f"""
            case {cat_col}
{whens}
                else 40.0
            end"""


def build_vtd_strata_query(
    *, test_mode: bool = False, ais_glob: str | None = None
) -> str:
    """Build the SQL that computes true vessel-traffic-density (VTD) strata.

    Unlike the ping-count aggregation, this reconstructs each MMSI's
    TRACK as ordered segments between consecutive positions and credits
    every H3 cell the track-km travelled WITHIN it, divided by the cell's
    area (km²). Grounded in Rockwood (2017) ArcGIS Track Builder +
    the EMODnet vessel-density method.

    Pipeline:
      1. Order pings by timestamp per (mmsi, month) → segments via LAG.
      2. Per segment: Δt, haversine km, implied speed (segment-level).
      3. Per-class teleport filter + 6 h gap filter drop impossible jumps.
      4. Hybrid apportionment: same-cell segments (the dense-AIS common
         case) take the full haversine length at zero geometry cost;
         boundary-spanning segments are clipped exactly with
         ST_Intersection against the few H3 cells the great-circle line
         crosses; rare long post-gap legs (> VTD_GRID_PATH_MAX_CELLS)
         fall back to the origin cell.
      5. GROUP BY the joint strata key
         (h3_cell, month, vessel_type, size_class, speed_bin) — a single
         cross-product so Phase 4 can apply Garrison lethality per
         (size, speed) bin without Jensen / geometry-contrast bias.

    Args:
        test_mode: If True, only process January of the first year.
        ais_glob: Explicit parquet glob to read. When supplied (used by
            the per-month chunked full run) it overrides test_mode/full
            glob selection so peak memory stays bounded to one month.

    Returns:
        SQL query string producing the VTD strata table.
    """
    if ais_glob is None:
        if test_mode:
            first_year = AIS_YEARS[0]
            ais_glob = str(AIS_RAW_DIR / f"ais-{first_year}-01-*.parquet")
            logger.info("VTD TEST MODE: processing January %d only", first_year)
        else:
            ais_glob = str(AIS_RAW_DIR / "*.parquet")

    category_case = _vessel_category_case("v_type")
    teleport_case = _teleport_threshold_case("vessel_category")
    cap = VTD_GRID_PATH_MAX_CELLS

    # Great-circle segment line as WKT (lon lat order for ST_GeomFromText)
    seg_line = (
        "ST_GeomFromText('LINESTRING(' || prev_lon || ' ' || prev_lat "
        "|| ', ' || lon || ' ' || lat || ')')"
    )

    return f"""
    -- ================================================================
    -- CTE 1: Raw positions (keep all moving pings; static cols nulled)
    -- ================================================================
    with raw_pings as (
        select
            mmsi,
            base_date_time::timestamp                 as ts,
            vessel_type,
            nullif(length, 0)                         as length,
            ST_Y(geometry)                            as lat,
            ST_X(geometry)                            as lon
        from read_parquet('{ais_glob}')
        where sog > 0
    ),

    -- ================================================================
    -- CTE 2: Assign H3 cell + month
    -- ================================================================
    with_h3 as (
        select
            *,
            h3_latlng_to_cell(lat, lon, {H3_RESOLUTION}) as h3_cell,
            date_trunc('month', ts)                       as month
        from raw_pings
    ),

    -- ================================================================
    -- CTE 3: Per-(mmsi, month) static vessel attributes
    -- ================================================================
    vessel_static as (
        select
            mmsi,
            month,
            max(length)        as v_length,
            max(vessel_type)   as v_type
        from with_h3
        group by mmsi, month
    ),

    -- ================================================================
    -- CTE 4: Order pings and pull the previous position via LAG
    -- ================================================================
    ordered as (
        select
            w.mmsi,
            w.month,
            w.ts,
            w.lat,
            w.lon,
            w.h3_cell,
            lag(w.lat)     over win as prev_lat,
            lag(w.lon)     over win as prev_lon,
            lag(w.ts)      over win as prev_ts,
            lag(w.h3_cell) over win as prev_h3
        from with_h3 w
        window win as (partition by w.mmsi, w.month order by w.ts)
    ),

    -- ================================================================
    -- CTE 5: Build segments — Δt, haversine km, implied speed
    -- ================================================================
    segments as (
        select
            o.month,
            o.h3_cell,
            o.prev_h3,
            o.lat,
            o.lon,
            o.prev_lat,
            o.prev_lon,
            vs.v_type,
            vs.v_length,
            date_diff('second', o.prev_ts, o.ts) / 3600.0   as dt_hours,
            2 * 6371.0 * asin(sqrt(
                power(sin(radians(o.lat - o.prev_lat) / 2), 2)
              + cos(radians(o.prev_lat)) * cos(radians(o.lat))
                * power(sin(radians(o.lon - o.prev_lon) / 2), 2)
            ))                                               as seg_km
        from ordered o
        join vessel_static vs
            on o.mmsi = vs.mmsi and o.month = vs.month
        where o.prev_ts is not null
    ),

    -- ================================================================
    -- CTE 6: Classify (category, size class, mass) + implied speed
    -- ================================================================
    classified as (
        select
            *,
            {category_case}                              as vessel_category,
            case
                when v_length is null then 'unknown'
                when v_length < 50    then 'small'
                when v_length < 100   then 'medium'
                when v_length < 200   then 'large'
                else 'vlarge'
            end                                          as size_class,
            case
                when v_length is not null and v_length > 0
                then {MAYETTE_MASS_A} * power(v_length, {MAYETTE_MASS_B})
            end                                          as vessel_mass_t,
            case
                when dt_hours > 0 then (seg_km / dt_hours) / 1.852
            end                                          as implied_speed_kn
        from segments
    ),

    -- ================================================================
    -- CTE 7: Filter teleports (per class) + gaps + zero-length
    -- ================================================================
    filtered as (
        select
            *,
            row_number() over () as seg_id,
            case
                when implied_speed_kn <= 10 then 'le10'
                when implied_speed_kn <= 12 then '10_12'
                when implied_speed_kn <= 15 then '12_15'
                else 'gt15'
            end as speed_bin
        from classified
        where dt_hours > 0
          and dt_hours <= {VTD_MAX_GAP_HOURS}
          and seg_km > 0
          and implied_speed_kn is not null
          and implied_speed_kn <= ({teleport_case})
    ),

    -- ================================================================
    -- APPORTIONMENT — three branches unioned into per-cell track-km
    -- ================================================================
    apportioned as (

        -- (1) Same-cell fast path: full length, zero geometry cost
        select
            h3_cell, month, vessel_category, size_class, speed_bin,
            seg_km                       as cell_km,
            implied_speed_kn, vessel_mass_t
        from filtered
        where prev_h3 = h3_cell

        union all

        -- (2) Short boundary-spanning: exact ST_Intersection clip.
        -- Fractions are renormalised per segment so the clipped pieces
        -- sum to the full segment length (H3 grid-path cells can zig-zag
        -- relative to the straight geodesic, dropping a few % otherwise).
        select
            cand_cell                    as h3_cell,
            month, vessel_category, size_class, speed_bin,
            seg_km * (frac / nullif(seg_frac_sum, 0))    as cell_km,
            implied_speed_kn, vessel_mass_t
        from (
            select
                *,
                sum(frac) over (partition by seg_id)     as seg_frac_sum
            from (
                select
                    f.seg_id, f.month, f.vessel_category, f.size_class,
                    f.speed_bin, f.seg_km, f.implied_speed_kn,
                    f.vessel_mass_t, cand_cell,
                    ST_Length(ST_Intersection(
                        ST_GeomFromText(h3_cell_to_boundary_wkt(cand_cell)),
                        {seg_line}
                    )) / nullif(ST_Length({seg_line}), 0)    as frac
                from filtered f,
                     unnest(h3_grid_path_cells(f.prev_h3, f.h3_cell))
                         as t(cand_cell)
                where f.prev_h3 <> f.h3_cell
                  and h3_grid_distance(f.prev_h3, f.h3_cell)
                      between 1 and {cap}
            ) clipped
            where frac > 0
        ) renorm

        union all

        -- (3) Long post-gap leg (or undefined path): credit origin cell
        select
            prev_h3                      as h3_cell,
            month, vessel_category, size_class, speed_bin,
            seg_km                       as cell_km,
            implied_speed_kn, vessel_mass_t
        from filtered
        where prev_h3 <> h3_cell
          and not (h3_grid_distance(prev_h3, h3_cell) between 1 and {cap})
    )

    -- ================================================================
    -- Final strata aggregation on the joint cross-product key
    -- ================================================================
    select
        h3_cell,
        month,
        vessel_category                          as vessel_type,
        size_class,
        speed_bin,
        h3_cell_to_lat(h3_cell)                  as cell_lat,
        h3_cell_to_lng(h3_cell)                  as cell_lon,
        sum(cell_km)                             as track_km,
        count(*)                                 as n_segments,
        sum(cell_km * implied_speed_kn)
            / nullif(sum(cell_km), 0)            as mean_implied_speed_kn,
        sum(cell_km * vessel_mass_t)
            / nullif(sum(
                case when vessel_mass_t is not null then cell_km end
            ), 0)                                as mean_vessel_mass_t,
        h3_cell_area(h3_cell, 'km^2')            as cell_area_km2,
        sum(cell_km) / nullif(h3_cell_area(h3_cell, 'km^2'), 0)
                                                 as vtd_km_per_km2
    from apportioned
    where h3_cell is not null
    group by h3_cell, month, vessel_category, size_class, speed_bin
    """


def run_vtd_aggregation(
    conn: duckdb.DuckDBPyConnection,
    output_file: Path = VTD_OUTPUT_FILE,
    *,
    test_mode: bool = False,
) -> int:
    """Execute the VTD strata query and write results to parquet.

    The full run is chunked **month by month**. The track-reconstruction
    branch (LAG window + h3_grid_path_cells row-explosion + ST_Intersection
    clip) contains operators that DuckDB cannot spill to disk, so a single
    12-month query OOMs at the memory limit. Because the strata key includes
    ``month``, the per-month partitions are disjoint and need no cross-chunk
    re-aggregation — each month is written as its own parquet part inside a
    directory, then loaded together.

    Args:
        conn: DuckDB connection with spatial + H3 extensions.
        output_file: Single-file output for test mode; for the full run its
            stem is used as the partition directory of per-month parts.
        test_mode: If True, only process January data (single file).

    Returns:
        Number of strata rows written.
    """
    logger.info("Starting VTD strata aggregation...")
    logger.info("  Input:  %s", AIS_RAW_DIR)
    logger.info("  Grain:  (h3_cell, month, vessel_type, size_class, speed_bin)")

    t0 = time.time()

    if test_mode:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        query = build_vtd_strata_query(test_mode=True)
        copy_sql = f"""
        COPY (
            {query}
        ) TO '{output_file}' (FORMAT PARQUET, COMPRESSION ZSTD);
        """
        conn.execute(copy_sql)
        read_glob = str(output_file)
    else:
        # Partition directory derived from the output file stem.
        part_dir = output_file.with_suffix("")
        part_dir.mkdir(parents=True, exist_ok=True)

        for year in AIS_YEARS:
            for month in range(1, 13):
                ym = f"{year}-{month:02d}"
                month_glob = str(AIS_RAW_DIR / f"ais-{ym}-*.parquet")
                if not list(AIS_RAW_DIR.glob(f"ais-{ym}-*.parquet")):
                    logger.info("  Skipping %s (no raw files)", ym)
                    continue
                part_file = part_dir / f"part-{ym}.parquet"
                # Resume: skip a month already written by a previous run.
                # A zero-byte part is a failed write — remove and redo.
                if part_file.exists():
                    if part_file.stat().st_size > 0:
                        logger.info("  Skipping %s (part already exists)", ym)
                        continue
                    part_file.unlink()
                logger.info("  Aggregating month %s ...", ym)
                query = build_vtd_strata_query(ais_glob=month_glob)
                copy_sql = f"""
                COPY (
                    {query}
                ) TO '{part_file}' (FORMAT PARQUET, COMPRESSION ZSTD);
                """
                conn.execute(copy_sql)
        read_glob = str(part_dir / "part-*.parquet")

    elapsed = time.time() - t0
    logger.info("VTD query complete in %.1f seconds", elapsed)

    row_count = conn.execute(
        f"SELECT count(*) FROM read_parquet('{read_glob}')"
    ).fetchone()[0]
    logger.info(
        "Wrote %s VTD strata rows (%s)",
        f"{row_count:,}",
        read_glob,
    )
    return row_count


def load_vtd_to_postgis(parquet_path: Path = VTD_OUTPUT_FILE) -> None:
    """Load the VTD strata parquet into PostGIS as ais_vtd_strata.

    Args:
        parquet_path: Path to the VTD strata parquet file, or the single-file
            test output. For the full run the per-month partition directory
            (``parquet_path`` stem) is read instead.
    """
    part_dir = parquet_path.with_suffix("")
    if part_dir.is_dir() and list(part_dir.glob("part-*.parquet")):
        read_glob = str(part_dir / "part-*.parquet")
    elif parquet_path.exists():
        read_glob = str(parquet_path)
    else:
        logger.error("VTD strata parquet not found: %s", parquet_path)
        logger.error("Run VTD aggregation first (--vtd).")
        return

    logger.info("Loading %s into PostGIS...", read_glob)
    read_conn = duckdb.connect()
    read_conn.execute("INSTALL spatial; LOAD spatial;")
    df = read_conn.execute(f"SELECT * FROM read_parquet('{read_glob}')").fetchdf()
    read_conn.close()
    logger.info("Read %s VTD strata rows from parquet", f"{len(df):,}")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    try:
        cur.execute("DROP TABLE IF EXISTS ais_vtd_strata CASCADE;")
        cur.execute("""
            CREATE TABLE ais_vtd_strata (
                h3_cell               BIGINT NOT NULL,
                month                 DATE   NOT NULL,
                vessel_type           TEXT   NOT NULL,
                size_class            TEXT   NOT NULL,
                speed_bin             TEXT   NOT NULL,
                cell_lat              DOUBLE PRECISION,
                cell_lon              DOUBLE PRECISION,
                track_km              DOUBLE PRECISION,
                n_segments            BIGINT,
                mean_implied_speed_kn DOUBLE PRECISION,
                mean_vessel_mass_t    DOUBLE PRECISION,
                cell_area_km2         DOUBLE PRECISION,
                vtd_km_per_km2        DOUBLE PRECISION,
                PRIMARY KEY (h3_cell, month, vessel_type, size_class, speed_bin)
            );
        """)

        cols = list(df.columns)
        col_str = ", ".join(cols)
        template = "(" + ", ".join(["%s"] * len(cols)) + ")"
        records = [
            tuple(to_python(v) for v in row)
            for row in df.itertuples(index=False, name=None)
        ]
        batch_size = 10_000
        total = len(records)
        for i in range(0, total, batch_size):
            batch = records[i : i + batch_size]
            execute_values(
                cur,
                f"INSERT INTO ais_vtd_strata ({col_str}) VALUES %s",
                batch,
                template=template,
            )
            if (i + batch_size) % 100_000 == 0 or i + batch_size >= total:
                logger.info(
                    "  Inserted %s / %s rows",
                    f"{min(i + batch_size, total):,}",
                    f"{total:,}",
                )

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_vtd_cell
                ON ais_vtd_strata (h3_cell);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_vtd_cell_month
                ON ais_vtd_strata (h3_cell, month);
        """)
        conn.commit()
        logger.info("Loaded %s rows into PostGIS ais_vtd_strata", f"{total:,}")
    except Exception:
        conn.rollback()
        logger.exception("Failed to load VTD strata into PostGIS")
        raise
    finally:
        cur.close()
        conn.close()


def run_aggregation(
    conn: duckdb.DuckDBPyConnection,
    output_file: Path = OUTPUT_FILE,
    *,
    test_mode: bool = False,
) -> int:
    """Execute the aggregation query and write results to parquet.

    Runs the two-pass query, copies the result directly to a
    parquet file using DuckDB's COPY statement (avoids loading
    the full result set into Python memory).

    Args:
        conn: DuckDB connection with spatial + H3 extensions.
        output_file: Where to write the output parquet file.
        test_mode: If True, only process January data.

    Returns:
        Number of rows written.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    query = build_aggregation_query(test_mode=test_mode)

    logger.info("Starting AIS H3 aggregation...")
    logger.info("  Input:  %s/*.parquet", AIS_RAW_DIR)
    logger.info("  Output: %s", output_file)
    logger.info("  H3 resolution: %d (~1.2km cells)", H3_RESOLUTION)

    t0 = time.time()

    # COPY ... TO writes directly to parquet — DuckDB streams
    # the query result to disk without materialising in memory.
    copy_sql = f"""
    COPY (
        {query}
    ) TO '{output_file}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """
    conn.execute(copy_sql)

    elapsed = time.time() - t0
    logger.info("Aggregation query complete in %.1f seconds", elapsed)

    # Count rows in the output file to confirm
    row_count = conn.execute(
        f"SELECT count(*) FROM read_parquet('{output_file}')"
    ).fetchone()[0]

    file_size_mb = output_file.stat().st_size / (1024 * 1024)

    logger.info(
        "Wrote %s rows to %s (%.1f MB, ZSTD compressed)",
        f"{row_count:,}",
        output_file,
        file_size_mb,
    )

    return row_count


def load_to_postgis(parquet_path: Path = OUTPUT_FILE) -> None:
    """Load the aggregated parquet into PostGIS for dbt joins.

    Creates the ais_h3_summary table and bulk-loads the data
    using psycopg2's execute_values for fast batch inserts.
    DuckDB reads the parquet; pandas bridges to psycopg2.

    This only loads the key columns needed by dbt intermediate
    models. The full 66-column parquet remains the source of
    truth for the risk model.

    Args:
        parquet_path: Path to the aggregated parquet file.
    """
    if not parquet_path.exists():
        logger.error("Aggregated parquet not found: %s", parquet_path)
        logger.error("Run aggregation first.")
        return

    logger.info("Loading %s into PostGIS...", parquet_path)

    # Read via DuckDB for speed (it handles parquet natively)
    read_conn = duckdb.connect()
    read_conn.execute("INSTALL spatial; LOAD spatial;")

    df = read_conn.execute(f"SELECT * FROM read_parquet('{parquet_path}')").fetchdf()
    read_conn.close()

    logger.info("Read %s rows from parquet", f"{len(df):,}")

    # Connect to PostGIS
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # Create table (drop + recreate for idempotency)
        cur.execute("DROP TABLE IF EXISTS ais_h3_summary CASCADE;")
        cur.execute("""
            CREATE TABLE ais_h3_summary (
                h3_cell            BIGINT       NOT NULL,
                month              DATE         NOT NULL,
                cell_lat           DOUBLE PRECISION,
                cell_lon           DOUBLE PRECISION,

                -- Traffic volume
                ping_count         BIGINT,
                unique_vessels     INTEGER,

                -- AIS-required traffic (IWC standard scoping)
                ais_required_vessels   INTEGER,
                ais_required_pings     BIGINT,

                -- Speed (ping-weighted + vessel-weighted)
                pw_avg_speed_knots     DOUBLE PRECISION,
                max_speed_knots        DOUBLE PRECISION,
                high_speed_pings       BIGINT,
                high_speed_vessel_count INTEGER,
                vw_avg_speed_knots     DOUBLE PRECISION,
                vw_median_speed_knots  DOUBLE PRECISION,

                -- Length
                pw_avg_length_m    DOUBLE PRECISION,
                vw_avg_length_m    DOUBLE PRECISION,
                max_length_m       DOUBLE PRECISION,
                p95_length_m       DOUBLE PRECISION,
                length_report_count INTEGER,
                large_vessel_count INTEGER,

                -- Width
                pw_avg_width_m     DOUBLE PRECISION,
                vw_avg_width_m     DOUBLE PRECISION,
                max_width_m        DOUBLE PRECISION,
                p95_width_m        DOUBLE PRECISION,
                width_report_count INTEGER,
                wide_vessel_count  INTEGER,

                -- Draft
                pw_avg_draft_m     DOUBLE PRECISION,
                vw_avg_draft_m     DOUBLE PRECISION,
                max_draft_m        DOUBLE PRECISION,
                p95_draft_m        DOUBLE PRECISION,
                draft_report_count INTEGER,
                deep_draft_count   INTEGER,

                -- Course diversity
                avg_circ_cog_stddev          DOUBLE PRECISION,
                cross_vessel_circ_cog_stddev DOUBLE PRECISION,
                cog_vessel_count   INTEGER,
                cog_report_count   BIGINT,

                -- Nav status
                underway_engine_pings      BIGINT,
                restricted_maneuver_pings  BIGINT,
                status_report_count        BIGINT,
                restricted_vessel_count    INTEGER,

                -- Day/Night
                day_ping_count     BIGINT,
                night_ping_count   BIGINT,
                day_unique_vessels INTEGER,
                night_unique_vessels INTEGER,
                vw_day_avg_speed_knots   DOUBLE PRECISION,
                vw_night_avg_speed_knots DOUBLE PRECISION,
                day_high_speed_pings     BIGINT,
                night_high_speed_pings   BIGINT,
                day_high_speed_vessel_count  INTEGER,
                night_high_speed_vessel_count INTEGER,

                -- Vessel type (vessel-weighted)
                fishing_vessels    INTEGER,
                tug_vessels        INTEGER,
                passenger_vessels  INTEGER,
                cargo_vessels      INTEGER,
                tanker_vessels     INTEGER,
                pleasure_vessels   INTEGER,
                military_vessels   INTEGER,

                -- Vessel type (ping-weighted)
                fishing_pings      BIGINT,
                tug_pings          BIGINT,
                passenger_pings    BIGINT,
                cargo_pings        BIGINT,
                tanker_pings       BIGINT,
                pleasure_pings     BIGINT,
                military_pings     BIGINT,

                -- Speed-lethality (Vanderlaan & Taggart 2007)
                vw_avg_lethality       DOUBLE PRECISION,
                pw_avg_lethality       DOUBLE PRECISION,
                max_lethality          DOUBLE PRECISION,
                high_speed_fraction    DOUBLE PRECISION,
                draft_risk_fraction    DOUBLE PRECISION,

                -- Draft imputation
                vw_avg_draft_imputed_m DOUBLE PRECISION,
                draft_imputed_count    INTEGER,

                PRIMARY KEY (h3_cell, month)
            );
        """)

        # Bulk insert using execute_values
        cols = list(df.columns)
        col_str = ", ".join(cols)
        template = "(" + ", ".join(["%s"] * len(cols)) + ")"

        # Convert to list of tuples, handling NaN → None
        # and numpy types → native Python (psycopg2 can't adapt numpy)
        records = [
            tuple(to_python(v) for v in row)
            for row in df.itertuples(index=False, name=None)
        ]

        batch_size = 10_000
        total = len(records)
        for i in range(0, total, batch_size):
            batch = records[i : i + batch_size]
            execute_values(
                cur,
                f"INSERT INTO ais_h3_summary ({col_str}) VALUES %s",
                batch,
                template=template,
            )
            if (i + batch_size) % 100_000 == 0 or i + batch_size >= total:
                logger.info(
                    "  Inserted %s / %s rows",
                    f"{min(i + batch_size, total):,}",
                    f"{total:,}",
                )

        # Create indexes for dbt joins
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ais_h3_cell
                ON ais_h3_summary (h3_cell);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ais_h3_month
                ON ais_h3_summary (month);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ais_h3_cell_month
                ON ais_h3_summary (h3_cell, month);
        """)

        conn.commit()
        logger.info(
            "Loaded %s rows into PostGIS ais_h3_summary",
            f"{total:,}",
        )

    except Exception:
        conn.rollback()
        logger.exception("Failed to load into PostGIS")
        raise
    finally:
        cur.close()
        conn.close()


def main() -> None:
    """Run the full AIS aggregation pipeline.

    1. Open DuckDB with extensions
    2. Run the two-pass aggregation query
    3. Write results to parquet
    4. Optionally load into PostGIS (--load-postgis flag)
    """

    parser = argparse.ArgumentParser(
        description="Aggregate AIS data into H3 hex cells",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: process January of first configured year only",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=DEFAULT_THREADS,
        help=f"Max DuckDB worker threads (default: {DEFAULT_THREADS})",
    )
    parser.add_argument(
        "--memory",
        type=str,
        default=DEFAULT_MEMORY,
        help=f"DuckDB memory limit (default: {DEFAULT_MEMORY})",
    )
    parser.add_argument(
        "--load-postgis",
        action="store_true",
        help="Also load the aggregated data into PostGIS",
    )
    parser.add_argument(
        "--postgis-only",
        action="store_true",
        help="Skip aggregation, just load existing parquet into PostGIS",
    )
    parser.add_argument(
        "--vtd",
        action="store_true",
        help="Run the true VTD strata aggregation (Phase 2) instead of "
        "the ping-count aggregation",
    )
    parser.add_argument(
        "--vtd-postgis-only",
        action="store_true",
        help="Skip VTD aggregation, just load existing VTD parquet into PostGIS",
    )
    args = parser.parse_args()

    t_start = time.time()

    # ── VTD strata mode (Phase 2) ──────────────────────────────
    if args.vtd or args.vtd_postgis_only:
        vtd_output = VTD_TEST_OUTPUT_FILE if args.test else VTD_OUTPUT_FILE
        if args.vtd_postgis_only:
            part_dir = vtd_output.with_suffix("")
            has_parts = part_dir.is_dir() and bool(
                list(part_dir.glob("part-*.parquet"))
            )
            if not vtd_output.exists() and not has_parts:
                logger.error("No VTD parquet found at %s — run --vtd first", vtd_output)
                return
            load_vtd_to_postgis(vtd_output)
        else:
            conn = get_connection(threads=args.threads, memory=args.memory)
            row_count = run_vtd_aggregation(conn, vtd_output, test_mode=args.test)
            conn.close()
            logger.info("VTD aggregation complete: %s strata rows", f"{row_count:,}")
            if args.load_postgis:
                load_vtd_to_postgis(vtd_output)
        elapsed = time.time() - t_start
        logger.info("Total elapsed: %dm %.1fs", int(elapsed // 60), elapsed % 60)
        return

    output_file = TEST_OUTPUT_FILE if args.test else OUTPUT_FILE

    if args.postgis_only:
        if not output_file.exists():
            logger.error("No parquet found at %s — run aggregation first", output_file)
            return
        load_to_postgis(output_file)
    else:
        conn = get_connection(threads=args.threads, memory=args.memory)
        row_count = run_aggregation(conn, output_file, test_mode=args.test)
        conn.close()

        logger.info("Aggregation complete: %s rows", f"{row_count:,}")

        if args.load_postgis:
            load_to_postgis(output_file)

    elapsed = time.time() - t_start
    minutes = int(elapsed // 60)
    seconds = elapsed % 60
    logger.info("Total elapsed: %dm %.1fs", minutes, seconds)


if __name__ == "__main__":
    main()

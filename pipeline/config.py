"""Centralised configuration for the marine risk mapping pipeline.

Single source of truth for database credentials, H3 resolution,
geographic bounding box, and file paths used across ingestion,
aggregation, and database scripts.

Database credentials are read from environment variables (MR_DB_*)
with local dev defaults so nothing breaks without a .env file.

Scoring weights and domain thresholds are read from
transform/dbt_project.yml so dbt SQL and Python share one
source of truth — no manual sync required.
"""

import os
from pathlib import Path

import yaml

# ── Project root (two levels up from this file) ────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Load dbt vars (single source of truth for shared constants) ──
_DBT_PROJECT_FILE = PROJECT_ROOT / "transform" / "dbt_project.yml"
with open(_DBT_PROJECT_FILE) as _f:
    _dbt_cfg = yaml.safe_load(_f)
_DBT_VARS: dict = _dbt_cfg.get("vars", {})

# ── Database connection (env vars override defaults) ────────
DB_CONFIG: dict[str, str | int] = {
    "host": os.environ.get("MR_DB_HOST", "localhost"),
    "port": int(os.environ.get("MR_DB_PORT", "5433")),
    "dbname": os.environ.get("MR_DB_NAME", "marine_risk"),
    "user": os.environ.get("MR_DB_USER", "marine"),
    "password": os.environ.get("MR_DB_PASSWORD", "marine_dev"),
}

# ── H3 spatial indexing ─────────────────────────────────────
H3_RESOLUTION = 7  # ~1.22 km edge length

# ── AIS data range ──────────────────────────────────────────
# Years of AIS data to download and process. Each year produces
# 365 daily GeoParquet files from MarineCadastre.gov.
AIS_YEARS: list[int] = [2024]

# ── AIS vessel type codes (ITU-R M.1371 + MarineCadastre 1001+) ─
VESSEL_TYPE_CODES: dict[str, list[int]] = {
    "fishing": [30, 1001, 1002],
    "tug": [31, 32, 52, 1023, 1025],
    "passenger": [*range(60, 70), 1012, 1013, 1014, 1015],
    "cargo": [*range(70, 80), 1003, 1004, 1016],
    "tanker": [*range(80, 90), 1017, 1024],
    "pleasure": [36, 37, 1019],
    "military": [35, 1021],
}

# ── AIS navigational status codes ───────────────────────────
NAV_STATUS_UNDERWAY: int = 0  # Under way using engine
NAV_STATUS_RESTRICTED: tuple[int, ...] = (2, 3)  # Not under command / restricted

# ── Speed & size thresholds ──────────────────────────────────
HIGH_SPEED_KNOTS = 10  # NOAA lethal strike threshold
LARGE_VESSEL_LENGTH_M = 100  # Ocean-going commercial (RISK-FLAGGING threshold)
WIDE_VESSEL_WIDTH_M = 20  # Wide-beam commercial (RISK-FLAGGING threshold)
DEEP_DRAFT_M = 8  # Deep-draft vessel (RISK-FLAGGING threshold)

# ── AIS carriage requirement (SOLAS Class-A proxy) ───────────
# IWC strike-risk standard distinguishes "AIS-required" vessels —
# those LEGALLY mandated to broadcast AIS — from voluntarily-equipped
# small craft. SOLAS mandates AIS for ≥300 GT international / ≥500 GT
# all tonnage / ALL passenger ships. AIS feeds lack reliable gross
# tonnage, so we proxy the mandate with vessel length (~20 m / 65 ft)
# PLUS all passenger vessel types regardless of length.
# This is NOT a risk-flagging threshold (cf. LARGE_VESSEL_LENGTH_M);
# it scopes traffic to Rockwood's "AIS-required large commercial"
# convention so non-AIS small craft become an explicit, documented
# blind spot rather than a silent omission. See aggregate_ais.py
# (ais_required_vessels / ais_required_pings).
AIS_REQUIRED_LENGTH_M = 20  # SOLAS Class-A practical length proxy

# ── Vanderlaan & Taggart (2007) speed-lethality logistic ─────
# P(lethal | speed) = 1 / (1 + exp(-(β₀ + β₁ × speed_knots)))
# Fitted to 40 observed whale-vessel collisions with known outcomes.
# Retained as the back-compat / V&T-vs-Garrison sensitivity baseline.
VT_LETHALITY_BETA0: float = _DBT_VARS["vt_lethality_beta0"]
VT_LETHALITY_BETA1: float = _DBT_VARS["vt_lethality_beta1"]

# ── Phase 2: True vessel-traffic-density (VTD) segment build ──
# VTD = track distance travelled per km² per cell (km⁻¹), built from
# consecutive AIS positions per MMSI track (Rockwood 2017 Track Builder
# + EMODnet vessel-density method) rather than ping/vessel counts.
#
# Gap threshold: split a track wherever the inter-ping gap exceeds this
# many hours (default 6 h — leans LONG because many offshore cells have
# sparse AIS; a short cap would artificially empty them).
VTD_MAX_GAP_HOURS: float = 6.0

# Teleport / outlier filter — PER VESSEL CLASS. Drop any segment whose
# implied speed (haversine_km / Δt) exceeds the class ceiling: such a
# jump is a GPS error or MMSI collision, not real travel. MarineCadastre
# is pre-cleaned by USCG, so this only catches residual spikes.
VTD_MAX_IMPLIED_SPEED_KN: dict[str, float] = {
    "cargo": 30.0,
    "tanker": 28.0,
    "passenger": 45.0,  # fast ferries / high-speed craft
    "fishing": 25.0,
    "tug": 20.0,
    "pleasure": 50.0,
    "military": 50.0,
    "other": 40.0,
}

# Segment-to-cell apportionment: above this H3 grid-distance (cells)
# the exact ST_Intersection clip is skipped and the (rare) long
# post-gap leg is credited wholly to its origin cell. Bounds geometry
# cost; ~1.2 km/cell ⇒ 150 cells ≈ 180 km corridor.
VTD_GRID_PATH_MAX_CELLS: int = 150

# Speed-bin upper edges (knots) for the joint strata grain. Binned on
# each SEGMENT's own implied speed (not the vessel median): one
# decelerating ship deposits track-km into 2+ bins of the same stratum.
VTD_SPEED_BIN_EDGES: tuple[float, ...] = (10.0, 12.0, 15.0)
VTD_SPEED_BIN_LABELS: tuple[str, ...] = ("le10", "10_12", "12_15", "gt15")

# Vessel size-class upper edges (length m) — the IWC standard's 4 size
# classes. Length < 50 → small, 50–100 → medium, 100–200 → large,
# ≥ 200 → vlarge; unknown length → 'unknown'.
VTD_SIZE_CLASS_EDGES: tuple[float, ...] = (50.0, 100.0, 200.0)
VTD_SIZE_CLASS_LABELS: tuple[str, ...] = (
    "small",
    "medium",
    "large",
    "vlarge",
)

# ── Garrison et al. (2025) speed-lethality (IWC-recommended upgrade) ──
# Logistic on vessel speed × size class × whale taxon. Replaces V&T at
# TWO touchpoints: (A) Phase 2 traffic screening uses the taxon-agnostic
# 'generic' curve per size class; (B) Phase 4 mortality uses the full
# speed × size × taxon parameterisation.
#
# The authoritative coefficients live in the dbt seed
# transform/seeds/garrison_lethality_coeffs.csv (read by the
# garrison_lethality() macro). The dict below MIRRORS the seed's
# touchpoint-A 'generic' rows so the DuckDB VTD aggregation can evaluate
# the same curve in-pipeline without a DB round-trip. Keep in sync.
#
# REAL coefficients from Garrison et al. (2025) Front. Mar. Sci.
# 11:1467387, Table 3 (logit-scale best model: Speed + VesselSize +
# Humpback + Speed*Humpback; n=192, R2=0.291). Non-humpback ("other")
# slope beta1=0.129/kn. Garrison's four size classes are defined on
# vessel LENGTH (Small <12.1m, Medium 12.2-19.7m, Large 19.8-108m,
# XL >=108m). AIS carriage starts ~20m, so essentially all our vessels
# fall in Garrison Large or XL — the only edge that matters is 108m.
# We map our length bins (50/100/200m) onto that split: small/medium
# -> Garrison Large (beta0=-1.127), large/vlarge -> Garrison XL
# (beta0=+0.754). The only approximation is the narrow 100-108m band
# (our 100m edge ~ Garrison's 108m). XL is lethal at any realistic
# speed (P>=0.5 even at 0 kn), matching the paper's Table 4.
GARRISON_GENERIC_BETA: dict[str, tuple[float, float]] = {
    # size_class: (beta0, beta1)  →  P = 1/(1+exp(-(β0 + β1·speed_kn)))
    "small": (-1.127, 0.129),  # → Garrison Large (19.8-108m)
    "medium": (-1.127, 0.129),  # → Garrison Large
    "large": (0.754, 0.129),  # → Garrison XL (>=108m)
    "vlarge": (0.754, 0.129),  # → Garrison XL
    "unknown": (-1.127, 0.129),  # fall back to Large (modal AIS class)
}

# ── Mayette & Brillant (2026) vessel-mass-from-length regression ─────
# mass_t ≈ MASS_A × length_m^MASS_B  (allometric displacement scaling).
# Three Phase-2 uses: (i) draft imputation via the displacement relation
# mass ≈ ρ·L·B·T·Cb → solve T when AIS draft is null; (ii) a mass
# covariate for Garrison size stratification; (iii) cross-check vs OLS.
# PROVISIONAL coefficients (geometric L³ scaling, calibrated so a 100 m
# vessel ≈ 7,000 t) pending the published regression table.
MAYETTE_MASS_A: float = 0.007
MAYETTE_MASS_B: float = 3.0

# Seawater density (t/m³) for the displacement relation.
SEAWATER_DENSITY_T_PER_M3: float = 1.025

# Per-category block coefficient Cb (fraction of the L×B×T box the hull
# fills) for the displacement draft solve. Fuller hulls (tankers) → high.
VESSEL_BLOCK_COEFFICIENT: dict[str, float] = {
    "cargo": 0.70,
    "tanker": 0.82,
    "passenger": 0.62,
    "fishing": 0.55,
    "tug": 0.55,
    "pleasure": 0.45,
    "military": 0.50,
    "other": 0.65,
}


def vessel_mass_from_length(length_m: float) -> float:
    """Estimate vessel displacement (tonnes) from length (Mayette 2026).

    mass_t = MASS_A × length_m^MASS_B. Returns 0.0 for non-positive
    length so callers can treat it as "unknown".
    """
    if length_m is None or length_m <= 0:
        return 0.0
    return MAYETTE_MASS_A * (length_m**MAYETTE_MASS_B)


def draft_from_displacement(
    length_m: float,
    beam_m: float,
    vessel_category: str,
) -> float | None:
    """Solve draft T (m) from the displacement relation mass ≈ ρ·L·B·T·Cb.

    Uses the Mayette mass estimate and a per-category block coefficient.
    Returns None when length or beam are missing (cannot solve).
    """
    if not length_m or not beam_m or length_m <= 0 or beam_m <= 0:
        return None
    cb = VESSEL_BLOCK_COEFFICIENT.get(vessel_category, 0.65)
    mass_t = vessel_mass_from_length(length_m)
    denom = SEAWATER_DENSITY_T_PER_M3 * length_m * beam_m * cb
    if denom <= 0:
        return None
    return mass_t / denom


# ── Day/night boundaries (local solar hour) ──────────────────
NIGHT_START_HOUR = 20  # 8 PM local
NIGHT_END_HOUR = 6  # 6 AM local

# ── Proximity decay half-lives (km) ─────────────────────────
PROXIMITY_HALF_LIFE_WHALE_KM = 10.0
PROXIMITY_HALF_LIFE_STRIKE_KM = 25.0
PROXIMITY_HALF_LIFE_PROTECTION_KM = 50.0
PROXIMITY_DISTANCE_CAP_KM: float = _DBT_VARS["proximity_distance_cap_km"]
PROXIMITY_PROTECTION_CAP_KM: float = _DBT_VARS["proximity_protection_cap_km"]

# Derived decay rates: λ = ln(2) / half-life
_LN2 = 0.693147180559945
PROXIMITY_LAMBDA_WHALE: float = _DBT_VARS["proximity_whale_lambda"]
PROXIMITY_LAMBDA_STRIKE: float = _DBT_VARS["proximity_strike_lambda"]
PROXIMITY_LAMBDA_PROTECTION: float = _DBT_VARS["proximity_protection_lambda"]

# ── Bathymetry classification (metres, negative = below sea level)
SHELF_DEPTH_M: int = _DBT_VARS["shelf_depth_m"]
SLOPE_DEPTH_M: int = _DBT_VARS["slope_depth_m"]

# ── Cetacean analysis ────────────────────────────────────────
CETACEAN_RECENT_YEAR: int = _DBT_VARS["cetacean_recent_year"]
BALEEN_FAMILIES: tuple[str, ...] = (
    "Balaenopteridae",  # Rorquals: blue, fin, humpback, minke
    "Balaenidae",  # Right whales
    "Eschrichtiidae",  # Gray whale
)

# ── Study bounding box ──────────────────────────────────────
# Covers CONUS, Alaska, Hawaii, Caribbean & adjacent corridors:
# south to the Galápagos (~1.4°S), east to Barbados (~59.5°W),
# north to the Aleutians/Kodiak (~52°N), west to the Aleutian chain.
# Note: ocean covariates intentionally use a wider box
# (US_BBOX_WIDE) because Copernicus grid cells near the
# boundary need extra margin for interpolation.
US_BBOX = {
    "lat_min": -2.0,
    "lat_max": 52.0,
    "lon_min": -180.0,
    "lon_max": -59.0,
}

US_BBOX_WIDE = {
    "lat_min": -3.0,
    "lat_max": 53.0,
    "lon_min": -180.0,
    "lon_max": -58.0,
}

# ── Data directories ────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# ── Raw data file paths ────────────────────────────────────
AIS_RAW_DIR = RAW_DIR / "ais"
CETACEAN_FILE = RAW_DIR / "cetacean" / "us_cetacean_sightings.parquet"
OBIS_PARQUET_GLOB = "data/raw/occurrence/*.parquet"  # MANUAL

MPA_FILE = RAW_DIR / "mpa" / "mpa_inventory.parquet"
SPEED_ZONES_FILE = (
    RAW_DIR
    / "mpa"
    / "Proposed-Right-Whale-Seasonal-Speed-Zones"
    / "Proposed_Right_Whale_Seasonal_Speed_Zones.shp"
)
SMA_DIR = RAW_DIR / "mpa" / "seasonal_management_areas"
SMA_FILE = SMA_DIR / "seasonal_management_areas.geojson"

BIA_FILE = RAW_DIR / "zones" / "cetacean_bia.parquet"
CRITICAL_HABITAT_FILE = RAW_DIR / "zones" / "whale_critical_habitat.parquet"
SHIPPING_LANES_FILE = RAW_DIR / "zones" / "shipping_lanes_regulations.parquet"
SLOW_ZONES_FILE = RAW_DIR / "zones" / "right_whale_slow_zones.geojson"

OCEAN_MASK_FILE = RAW_DIR / "ocean_mask" / "ocean_mask.parquet"

SHIP_STRIKES_PDF = RAW_DIR / "cetacean" / "noaa_23127_DS1.pdf"  # MANUAL
SHIP_STRIKES_FILE = PROCESSED_DIR / "ship_strikes" / "ship_strikes.csv"

NISI_DIR = RAW_DIR / "nisi_2024"
NISI_RISK_FILE = NISI_DIR / "global_whale_ship_risk.csv"
NISI_SHIPPING_FILE = NISI_DIR / "shipping_density.csv"
NISI_ISDM_FILES = {
    "blue_whale": NISI_DIR / "blue_whale_isdm_data.csv",
    "fin_whale": NISI_DIR / "fin_whale_isdm_data.csv",
    "humpback_whale": NISI_DIR / "humpback_whale_isdm_data.csv",
    "sperm_whale": NISI_DIR / "sperm_whale_isdm_data.csv",
}

OCEAN_DIR = RAW_DIR / "ocean"
OCEAN_COVARIATES_FILE = OCEAN_DIR / "ocean_covariates.parquet"

# ── Survey line-transect data (Phase 3 DSM density engine) ──
# Harmonised tidy tables produced by pipeline/ingestion/download_survey_*.py.
# Python does download + tidy ONLY; all statistics (detection function,
# segmentation, DSM GAM) live in the R density/ toolchain.
SURVEY_DIR = RAW_DIR / "surveys"
GOMMAPPS_DIR = SURVEY_DIR / "gommapps"
GOMMAPPS_CACHE_DIR = GOMMAPPS_DIR / "ncei_csv"
GOMMAPPS_SEGMENTS_FILE = GOMMAPPS_DIR / "survey_segments.parquet"
GOMMAPPS_SIGHTINGS_FILE = GOMMAPPS_DIR / "survey_sightings.parquet"
GOMMAPPS_COVARIATES_FILE = GOMMAPPS_DIR / "survey_detection_covariates.parquet"

# NCEI archive accessions holding GoMMAPPS visual line-transect data
# (vessel: Gordon Gunter + Pisces; aerial: Twin Otter).  Turtle/seabird/CTD
# accessions in the same programme lack VisualSightingData CSVs and are
# skipped automatically by the downloader.
GOMMAPPS_ACCESSIONS: list[str] = [
    "0241032",
    "0242273",
    "0243468",
    "0243469",
    "0243654",
    "0244002",
    "0247205",
    "0247206",
    "0256800",
]

# ── CMIP6 climate projections ──────────────────────────────
CMIP6_DIR = RAW_DIR / "cmip6"
CMIP6_PROJECTIONS_FILE = CMIP6_DIR / "cmip6_projections.parquet"
CMIP6_SCENARIOS: list[str] = ["ssp245", "ssp585"]
CMIP6_DECADES: list[str] = ["2030s", "2040s", "2060s", "2080s"]

# Reference period used for delta-method bias correction.
# Must match the observational baseline period (ocean_covariates.parquet,
# Copernicus 2019–2024).  All SSP scenarios are functionally identical
# in 2019–2024 because cumulative emissions have not yet diverged, so
# per-scenario reference rows differ only by sampling noise.
CMIP6_REFERENCE_DECADE: str = "reference"
CMIP6_REFERENCE_YEARS: tuple[int, int] = (2019, 2024)
CMIP6_PROJECTIONS_BACKUP_FILE = CMIP6_DIR / "cmip6_projections.pre_delta"

# ── SDM projections (scored on CMIP6 covariates) ───────────
SDM_PROJECTIONS_DIR = PROCESSED_DIR / "ml" / "sdm_projections"
ISDM_PROJECTIONS_DIR = PROCESSED_DIR / "ml" / "isdm_projections"

# MANUAL: see docs/manual_data_acquisition.md
BATHYMETRY_RASTER = RAW_DIR / "bathymetry" / "gebco_2025_n52.0_s-2.0_w-180.0_e-59.0.tif"

# ── Processed data file paths ──────────────────────────────
AIS_H3_DIR = PROCESSED_DIR / "ais"
AIS_H3_PARQUET = AIS_H3_DIR / "ais_h3_res7.parquet"
AIS_H3_TEST_PARQUET = AIS_H3_DIR / "ais_h3_res7_test.parquet"

# Phase 2 — true vessel-traffic-density (VTD) strata output.
# Grain: (h3_cell, month, vessel_type, size_class, speed_bin).
AIS_VTD_PARQUET = AIS_H3_DIR / "ais_vtd_strata_res7.parquet"
AIS_VTD_TEST_PARQUET = AIS_H3_DIR / "ais_vtd_strata_res7_test.parquet"

# ── DuckDB ──────────────────────────────────────────────────
DUCKDB_PATH = DATA_DIR / "marine_risk.duckdb"

# ── dbt ─────────────────────────────────────────────────────
DBT_PROJECT_DIR = PROJECT_ROOT / "transform"
DBT_PROFILES_DIR = PROJECT_ROOT / "transform"

# ── ML / MLflow ─────────────────────────────────────────────
ML_DIR = PROCESSED_DIR / "ml"
STRIKE_FEATURES_FILE = ML_DIR / "strike_risk_features.parquet"
SDM_FEATURES_FILE = ML_DIR / "whale_sdm_features.parquet"
SDM_SEASONAL_FEATURES_FILE = ML_DIR / "whale_sdm_seasonal_features.parquet"
SDM_PREDICTIONS_DIR = ML_DIR / "sdm_predictions"
MLRUNS_DIR = PROJECT_ROOT / "mlruns"
MLFLOW_DB = PROJECT_ROOT / "mlruns.db"
MLFLOW_TRACKING_URI = f"sqlite:///{MLFLOW_DB}"

# ── Seasons (from dbt vars — meteorological, North Atlantic whale ecology) ──
SEASONS: dict[str, list[int]] = {
    "winter": _DBT_VARS["season_winter_months"],
    "spring": _DBT_VARS["season_spring_months"],
    "summer": _DBT_VARS["season_summer_months"],
    "fall": _DBT_VARS["season_fall_months"],
}
SEASON_ORDER: list[str] = ["winter", "spring", "summer", "fall"]

# ── Spatial cross-validation ────────────────────────────────
H3_CV_RESOLUTION = 2  # ~158 km edge — parent cells for CV fold grouping
N_CV_FOLDS = 5

# ── SDM sampling-bias correction (IWC Phase 1b item C) ──────
# Target-group background (Phillips et al. 2009): restrict SDM training
# background/absence to cells where the target group (any cetacean) was
# observed, so the background reflects survey effort rather than raw
# environmental availability. Cells with no cetacean observation at all
# are treated as "unsurveyed" and excluded from model fitting (they are
# still scored by the final model for grid coverage).
SDM_TARGET_GROUP_BACKGROUND = True
# Spatial thinning (Aiello-Lammens et al. 2015, spThin): drop presence
# records closer than this distance to a retained presence, reducing the
# influence of spatially oversampled survey areas. 0 disables thinning.
SDM_THINNING_DIST_KM = 10.0

# ── Collision risk sub-score weights (from dbt vars) ────────
# dbt_project.yml is the single source of truth.
COLLISION_RISK_WEIGHTS: dict[str, float] = {
    "traffic_score": _DBT_VARS["risk_weight_traffic"],
    "cetacean_score": _DBT_VARS["risk_weight_cetacean"],
    "proximity_score": _DBT_VARS["risk_weight_proximity"],
    "strike_score": _DBT_VARS["risk_weight_strike"],
    "habitat_score": _DBT_VARS["risk_weight_habitat"],
    "protection_gap": _DBT_VARS["risk_weight_protection_gap"],
    "reference_risk_score": _DBT_VARS["risk_weight_reference"],
}

# ── ML-enhanced collision risk weights ──────────────────────
COLLISION_RISK_ML_WEIGHTS: dict[str, float] = {
    "interaction_score": _DBT_VARS["risk_ml_weight_interaction"],
    "traffic_score": _DBT_VARS["risk_ml_weight_traffic"],
    "whale_ml_score": _DBT_VARS["risk_ml_weight_whale_ml"],
    "proximity_score": _DBT_VARS["risk_ml_weight_proximity"],
    "strike_score": _DBT_VARS["risk_ml_weight_strike"],
    "protection_gap": _DBT_VARS["risk_ml_weight_protection_gap"],
    "reference_risk_score": _DBT_VARS["risk_ml_weight_reference"],
}

# ── Risk category thresholds (score >= threshold → label) ──
RISK_THRESHOLDS: dict[str, float] = {
    "critical": _DBT_VARS["risk_threshold_critical"],
    "high": _DBT_VARS["risk_threshold_high"],
    "medium": _DBT_VARS["risk_threshold_medium"],
    "low": _DBT_VARS["risk_threshold_low"],
    # Anything below low threshold → "minimal" (implicit)
}

# ── Sub-score internal weights ──────────────────────────────

TRAFFIC_SCORE_WEIGHTS: dict[str, float] = {
    "speed_lethality": _DBT_VARS["traffic_w_speed_lethality"],
    "high_speed_fraction": _DBT_VARS["traffic_w_high_speed_fraction"],
    "vessels": _DBT_VARS["traffic_w_vessels"],
    "large_vessels": _DBT_VARS["traffic_w_large_vessels"],
    "draft_risk": _DBT_VARS["traffic_w_draft_risk"],
    "draft_risk_fraction": _DBT_VARS["traffic_w_draft_risk_fraction"],
    "commercial": _DBT_VARS["traffic_w_commercial"],
    "night_traffic": _DBT_VARS["traffic_w_night_traffic"],
}

CETACEAN_SCORE_WEIGHTS: dict[str, float] = {
    "sightings": _DBT_VARS["cetacean_w_sightings"],
    "baleen": _DBT_VARS["cetacean_w_baleen"],
    "recent": _DBT_VARS["cetacean_w_recent"],
}

WHALE_ML_SCORE_WEIGHTS: dict[str, float] = {
    "any": _DBT_VARS["whale_ml_w_any"],
    "max": _DBT_VARS["whale_ml_w_max"],
    "mean": _DBT_VARS["whale_ml_w_mean"],
}

STRIKE_SCORE_WEIGHTS: dict[str, float] = {
    "total": _DBT_VARS["strike_w_total"],
    "fatal": _DBT_VARS["strike_w_fatal"],
    "baleen": _DBT_VARS["strike_w_baleen"],
}

HABITAT_SCORE_WEIGHTS: dict[str, float] = {
    "bathymetry": _DBT_VARS["habitat_w_bathymetry"],
    "ocean": _DBT_VARS["habitat_w_ocean"],
}

HABITAT_BATHY_WEIGHTS: dict[str, float] = {
    "shelf": _DBT_VARS["habitat_w_shelf"],
    "edge": _DBT_VARS["habitat_w_edge"],
    "depth_zone": _DBT_VARS["habitat_w_depth_zone"],
}

DEPTH_ZONE_SCORES: dict[str, float] = {
    "shelf": _DBT_VARS["depth_zone_shelf"],
    "slope": _DBT_VARS["depth_zone_slope"],
    "abyssal": _DBT_VARS["depth_zone_abyssal"],
}

PROXIMITY_SCORE_WEIGHTS: dict[str, float] = {
    "whale_ship": _DBT_VARS["proximity_w_whale_ship"],
    "strike": _DBT_VARS["proximity_w_strike"],
    "protection": _DBT_VARS["proximity_w_protection"],
}

PROTECTION_GAP_SCORES: dict[str, float] = {
    "notake_and_sma": _DBT_VARS["protection_notake_and_sma"],
    "notake_only": _DBT_VARS["protection_notake_only"],
    "strict_and_sma": _DBT_VARS["protection_strict_and_sma"],
    "strict_mpa": _DBT_VARS["protection_strict_mpa"],
    "mpa_and_sma": _DBT_VARS["protection_mpa_and_sma"],
    "any_mpa": _DBT_VARS["protection_any_mpa"],
    "sma_only": _DBT_VARS["protection_sma_only"],
    "none": _DBT_VARS["protection_none"],
}

# Validate all sub-score weight sets sum to 1.0
for _name, _weights in [
    ("COLLISION_RISK_WEIGHTS", COLLISION_RISK_WEIGHTS),
    ("COLLISION_RISK_ML_WEIGHTS", COLLISION_RISK_ML_WEIGHTS),
    ("TRAFFIC_SCORE_WEIGHTS", TRAFFIC_SCORE_WEIGHTS),
    ("CETACEAN_SCORE_WEIGHTS", CETACEAN_SCORE_WEIGHTS),
    ("WHALE_ML_SCORE_WEIGHTS", WHALE_ML_SCORE_WEIGHTS),
    ("STRIKE_SCORE_WEIGHTS", STRIKE_SCORE_WEIGHTS),
    ("HABITAT_SCORE_WEIGHTS", HABITAT_SCORE_WEIGHTS),
    ("HABITAT_BATHY_WEIGHTS", HABITAT_BATHY_WEIGHTS),
    ("PROXIMITY_SCORE_WEIGHTS", PROXIMITY_SCORE_WEIGHTS),
]:
    _total = round(sum(_weights.values()), 10)
    if _total != 1.0:
        raise ValueError(f"{_name} sum to {_total}, expected 1.0")

# Validate thresholds are strictly descending
_vals = list(RISK_THRESHOLDS.values())
if _vals != sorted(_vals, reverse=True) or len(set(_vals)) != len(_vals):
    raise ValueError(f"RISK_THRESHOLDS must be strictly descending: {_vals}")

# ── Audio classification ────────────────────────────────────
WHALE_AUDIO_RAW_DIR = RAW_DIR / "whale_audio"
WHALE_AUDIO_PROCESSED_DIR = PROCESSED_DIR / "whale_audio"
AUDIO_MODEL_DIR = ML_DIR / "audio_classifier"

# Preprocessing parameters
AUDIO_SAMPLE_RATE = 16_000  # Hz — standard for marine bioacoustics
AUDIO_SEGMENT_DURATION = 4.0  # seconds per classification window
AUDIO_SEGMENT_HOP = 2.0  # seconds hop (50 % overlap)
AUDIO_N_MELS = 128  # mel frequency bins
AUDIO_N_FFT = 2048  # FFT window size
AUDIO_HOP_LENGTH = 512  # STFT hop length
AUDIO_N_MFCC = 20  # MFCC coefficients
AUDIO_FMIN = 10  # Hz — captures blue whale infrasonic
AUDIO_FMAX = 8000  # Hz — upper bound for most cetacean calls

# ── Audio species lists — three-pass design ─────────────────
# Pass 1 (critical): 9 ESA-listed species + other_cetacean gatekeeper.
# other_cetacean is trained on clips from broad species so the model
# learns "not a large whale" as a coherent category, not just a residual.
# Bowhead included: ESA-listed, strong acoustic signal in WMMSDB (306 clips).
WHALE_AUDIO_SPECIES: list[str] = [
    "right_whale",
    "humpback_whale",
    "fin_whale",
    "blue_whale",
    "sperm_whale",
    "minke_whale",
    "sei_whale",
    "killer_whale",
    "bowhead_whale",
    "other_cetacean",  # gatekeeper — triggers escalation to broad pass
]

# Pass 2 (broad): ~15 non-critical cetacean species.
# Critically: NO overlap with WHALE_AUDIO_SPECIES (no double-learning).
# Non-cetaceans (walrus, seals, manatee) are excluded from training classes
# but their clips can be used as hard negatives in unknown_cetacean.
# Harbor porpoise and Dall's porpoise excluded — primary vocalizations
# are ultrasonic (100-150 kHz), outside our AUDIO_FMAX=8000 Hz pipeline.
WHALE_AUDIO_BROAD_SPECIES: list[str] = [
    "spotted_dolphin",  # S. attenuata — 860 clips
    "long_finned_pilot_whale",  # G. melaena — 700 clips
    "atlantic_white_sided_dolphin",  # L. acutus — 493 clips
    "spinner_dolphin",  # S. longirostris — 487 clips
    "striped_dolphin",  # S. coeruleoalba — 332 clips
    "rissos_dolphin",  # Grampus griseus — 331 clips
    "clymene_dolphin",  # S. clymene — 312 clips
    "common_dolphin",  # D. delphis — 282 clips
    "atlantic_spotted_dolphin",  # S. frontalis — 244 clips
    "short_finned_pilot_whale",  # G. macrorhynchus — 224 clips
    "bottlenose_dolphin",  # T. truncatus — 168 clips
    "beluga",  # D. leucas — 133 clips
    "narwhal",  # M. monoceros — 72 clips
    "gray_whale",  # E. robustus — 32 clips (augmented)
    "unknown_cetacean",  # catch-all for broad pass
]

# Pass 3 (rare): species with 5-19 WMMSDB clips — too few for a softmax
# head but usable for cosine-similarity retrieval against mean embeddings
# computed from the broad model backbone.
# Clips for non-cetaceans (seals, walrus) are intentionally omitted.
WHALE_AUDIO_RARE_SPECIES: list[str] = [
    "amazon_river_dolphin",  # Inia geoffrensis — 30 clips
    "heavisides_dolphin",  # Cephalorhynchus heavisidii — 14 clips
    "tucuxi",  # Sotalia fluviatilis — 12 clips
    "melon_headed_whale",  # Peponocephala electra — 9 clips (audio)
    "lagenodelphis_dolphin",  # Lagenodelphis hosei — 7 clips
]

# Species-specific frequency bands (Hz) for bandpass pre-filtering
WHALE_FREQ_BANDS: dict[str, tuple[float, float]] = {
    "right_whale": (50, 500),  # upcalls
    "humpback_whale": (80, 4000),  # song units (4 kHz captures most)
    "fin_whale": (15, 30),  # 20 Hz pulses
    "blue_whale": (10, 100),  # infrasonic calls
    "sperm_whale": (2000, 8000),  # clicks (broadband, peak energy 2–8 kHz)
    "minke_whale": (50, 300),  # boing / bioduck calls
    "sei_whale": (20, 100),  # downsweep calls
    "killer_whale": (500, 8000),  # pulsed calls + whistles
}

# ── Audio training / balancing constants ─────────────────────
AUDIO_MAX_SEGMENTS_PER_SPECIES = 2000  # cap to prevent class domination
AUDIO_AUGMENT_TARGET = 500  # floor for underrepresented species
AUDIO_CNN_EARLY_STOP_PATIENCE = 7  # stop if val F1 doesn't improve for N epochs

# Augmentation hyper-parameters
AUDIO_AUG_TIME_STRETCH_RANGE = (0.9, 1.1)  # rate multiplier
AUDIO_AUG_PITCH_SHIFT_RANGE = (-2.0, 2.0)  # semitones
AUDIO_AUG_NOISE_SNR_RANGE = (15.0, 30.0)  # dB
AUDIO_AUG_TIME_SHIFT_FRACTION = 0.25  # ±25 % of segment length

# ── Photo classification ─────────────────────────────────────
WHALE_PHOTO_RAW_DIR = RAW_DIR / "whale_photos"
PHOTO_MODEL_DIR = ML_DIR / "photo_classifier"

# Preprocessing parameters
PHOTO_IMAGE_SIZE = 224  # 380→224 for faster MPS training
PHOTO_BATCH_SIZE = 64  # Doubled from 32 — 224px images use ~4× less memory
PHOTO_EPOCHS = 30  # max epochs (early stopping will cut short)
PHOTO_LR_HEAD = 1e-4  # learning rate for classifier head
PHOTO_LR_BACKBONE = 1e-5  # learning rate for backbone (10× lower)
PHOTO_EARLY_STOP_PATIENCE = 7  # stop if val macro F1 stalls
PHOTO_LABEL_SMOOTHING = 0.1  # regularises overconfident predictions
PHOTO_MAX_IMAGES_PER_SPECIES = 5000  # cap dominant classes
PHOTO_OTHER_PER_SPECIES_CAP = 250  # per non-target species for other_cetacean
PHOTO_BACKBONE_FREEZE_EPOCHS = 2  # freeze backbone for first N epochs (head warmup)

PHOTO_IMAGENET_MEAN = (0.485, 0.456, 0.406)
PHOTO_IMAGENET_STD = (0.229, 0.224, 0.225)

# The 7 critical target species (before adding other_cetacean gatekeeper).
# sperm_whale not in Happywhale dataset (deep divers, rarely surface-photographed).
WHALE_PHOTO_TARGET_SPECIES: list[str] = [
    "right_whale",
    "humpback_whale",
    "fin_whale",
    "blue_whale",
    "minke_whale",
    "sei_whale",
    "killer_whale",
]

# Known label fixes in the Happywhale Kaggle dataset
HAPPYWHALE_LABEL_FIXES: dict[str, str] = {
    "globis": "short_finned_pilot_whale",
    "pilot_whale": "short_finned_pilot_whale",
    "kiler_whale": "killer_whale",
    "bottlenose_dolpin": "bottlenose_dolphin",
    "southern_right_whale": "right_whale",
}

# Confidence thresholds for pass escalation.
# Critical → broad if: top_pred == "other_cetacean" OR max_conf < threshold.
# Broad → rare if: top_pred == "unknown_cetacean" OR max_conf < threshold.
AUDIO_CRITICAL_CONFIDENCE_THRESHOLD: float = 0.65
AUDIO_BROAD_CONFIDENCE_THRESHOLD: float = 0.50

# Output directories for multi-pass audio models.
AUDIO_BROAD_MODEL_DIR = ML_DIR / "audio_classifier_broad"
AUDIO_RARE_EMBEDDINGS_DIR = ML_DIR / "audio_classifier_rare"

# ── Photo species lists — three-pass design ──────────────────
# Pass 1 (critical): 7 ESA-listed species + other_cetacean gatekeeper.
# Note: sperm_whale excluded — absent from Happywhale dataset (deep divers).
# Note: bowhead excluded from photo critical — absent from Happywhale.
WHALE_PHOTO_SPECIES: list[str] = [
    "right_whale",
    "humpback_whale",
    "fin_whale",
    "blue_whale",
    "minke_whale",
    "sei_whale",
    "killer_whale",
    "other_cetacean",  # gatekeeper — triggers escalation to broad pass
]

# Pass 2 (broad): all Happywhale species with >= 50 images that are NOT
# in the critical list. Confirmed from audit: 18 species, 32,116 images.
# No overlap with WHALE_PHOTO_SPECIES.
WHALE_PHOTO_BROAD_TARGET_SPECIES: list[str] = [
    "bottlenose_dolphin",  # 10,781 images
    "beluga",  # 7,443 images
    "false_killer_whale",  # 3,326 images
    "dusky_dolphin",  # 3,139 images
    "spinner_dolphin",  # 1,700 images
    "melon_headed_whale",  # 1,689 images  ← was missing from old list
    "gray_whale",  # 1,123 images
    "short_finned_pilot_whale",  # 745 images
    "spotted_dolphin",  # 490 images
    "common_dolphin",  # 347 images
    "cuviers_beaked_whale",  # 341 images  ← was missing from old list
    "long_finned_pilot_whale",  # 238 images  ← was missing from old list
    "white_sided_dolphin",  # 229 images  ← was missing from old list
    "brydes_whale",  # 154 images  ← was missing from old list
    "pantropic_spotted_dolphin",  # 145 images  ← was missing from old list
    "commersons_dolphin",  # 90 images   ← was missing from old list
    "pygmy_killer_whale",  # 76 images   ← was missing from old list
    "rough_toothed_dolphin",  # 60 images   ← was missing from old list
    "unknown_cetacean",  # catch-all for broad pass
]

# Pass 3 (rare): only frasiers_dolphin (14 images) falls here from Happywhale.
# Embedding similarity against broad model backbone representations.
WHALE_PHOTO_RARE_SPECIES: list[str] = [
    "frasiers_dolphin",  # 14 images in Happywhale
]

# Confidence thresholds for photo pass escalation.
PHOTO_CRITICAL_CONFIDENCE_THRESHOLD: float = 0.65
PHOTO_BROAD_CONFIDENCE_THRESHOLD: float = 0.50

# Output directories for multi-pass photo models.
PHOTO_BROAD_MODEL_DIR = ML_DIR / "photo_classifier_broad"
PHOTO_RARE_EMBEDDINGS_DIR = ML_DIR / "photo_classifier_rare"

# ── ArcFace photo classifier (Kaggle Happywhale 1st-place approach) ──────────
# Sub-centre ArcFace with dynamic margins + GeM multi-scale pooling.
# Backbone via timm.  Gallery-based KNN inference blended with logit scores.
# Reference: Abe & Yamaguchi (2022), https://github.com/knshnb/kaggle-happywhale-1st-place
ARCFACE_IMAGE_SIZE: int = 448  # richer features than B4's 224 px
ARCFACE_BACKBONE: str = "tf_efficientnet_b7"  # best single-model from paper
ARCFACE_OUT_INDICES: tuple[int, int] = (3, 4)  # last two backbone stages
ARCFACE_N_CENTER: int = 2  # sub-centre k — handles fluke/dorsal/flank modes
ARCFACE_GEM_P: float = 3.0  # GeM pooling exponent (fixed, not learned)
ARCFACE_S: float = 30.0  # ArcFace scale factor
ARCFACE_MARGIN_POWER: float = -0.5  # dynamic: margin ∝ n_samples^power
ARCFACE_MARGIN_COEF: float = 0.45  # margin scaling coefficient
ARCFACE_MARGIN_CONS: float = 0.05  # margin additive constant
ARCFACE_LR_BACKBONE: float = 1.6e-3  # warmup cosine — backbone param group
ARCFACE_LR_HEAD: float = 1.6e-2  # 10× backbone (head converges faster)
ARCFACE_BATCH_SIZE: int = 16
ARCFACE_EPOCHS: int = 30
ARCFACE_EARLY_STOP_PATIENCE: int = 7  # val macro-F1 patience
ARCFACE_WARMUP_RATIO: float = 0.1  # fraction of epochs for LR warmup
ARCFACE_KNN_RATIO: float = 0.5  # blend: KNN × ratio + logit × (1 − ratio)
ARCFACE_KNN_NEIGHBORS: int = 50  # top-K gallery neighbours per query
ARCFACE_MODEL_DIR = ML_DIR / "photo_classifier_arcface"
ARCFACE_BROAD_MODEL_DIR = ML_DIR / "photo_classifier_arcface_broad"

# ── iNaturalist photo download ────────────────────────────────────────────────
# Research-grade cetacean photos from iNaturalist Open Data.
# Supplements Happywhale Kaggle dataset — adds sperm_whale + bowhead_whale
# (absent from Happywhale) and extra gallery images for underrepresented species.
INAT_MAX_PER_SPECIES: int = 500  # default cap for broad species
INAT_REQUEST_DELAY: float = 0.7  # seconds between API pages (≤60 req/min)
INAT_PHOTO_SIZE: str = "large"  # iNat size token: large = 1024 px long edge

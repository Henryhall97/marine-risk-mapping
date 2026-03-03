"""Centralised configuration for the marine risk mapping pipeline.

Single source of truth for database credentials, H3 resolution,
geographic bounding box, and file paths used across ingestion,
aggregation, and database scripts.

Database credentials are read from environment variables (MR_DB_*)
with local dev defaults so nothing breaks without a .env file.
"""

import os
from pathlib import Path

# ── Project root (two levels up from this file) ────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

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
LARGE_VESSEL_LENGTH_M = 100  # Ocean-going commercial
WIDE_VESSEL_WIDTH_M = 20  # Wide-beam commercial
DEEP_DRAFT_M = 8  # Deep-draft vessel

# ── Vanderlaan & Taggart (2007) speed-lethality logistic ─────
# P(lethal | speed) = 1 / (1 + exp(-(β₀ + β₁ × speed_knots)))
# Fitted to 40 observed whale-vessel collisions with known outcomes.
VT_LETHALITY_BETA0 = -4.89  # Intercept
VT_LETHALITY_BETA1 = 0.41  # Speed coefficient (per knot)

# ── Day/night boundaries (local solar hour) ──────────────────
NIGHT_START_HOUR = 20  # 8 PM local
NIGHT_END_HOUR = 6  # 6 AM local

# ── Proximity decay half-lives (km) ─────────────────────────
PROXIMITY_HALF_LIFE_WHALE_KM = 10.0
PROXIMITY_HALF_LIFE_STRIKE_KM = 25.0
PROXIMITY_HALF_LIFE_PROTECTION_KM = 50.0
PROXIMITY_DISTANCE_CAP_KM = 700.0
PROXIMITY_PROTECTION_CAP_KM = 1000.0

# Derived decay rates: λ = ln(2) / half-life
_LN2 = 0.693147180559945
PROXIMITY_LAMBDA_WHALE = _LN2 / PROXIMITY_HALF_LIFE_WHALE_KM  # ≈ 0.0693
PROXIMITY_LAMBDA_STRIKE = _LN2 / PROXIMITY_HALF_LIFE_STRIKE_KM  # ≈ 0.0277
PROXIMITY_LAMBDA_PROTECTION = _LN2 / PROXIMITY_HALF_LIFE_PROTECTION_KM  # ≈ 0.01386

# ── Bathymetry classification (metres, negative = below sea level)
SHELF_DEPTH_M = -200  # Continental shelf break
SLOPE_DEPTH_M = -1000  # Slope–abyssal boundary

# ── Cetacean analysis ────────────────────────────────────────
CETACEAN_RECENT_YEAR = 2019  # "Recent" sighting cutoff year
BALEEN_FAMILIES: tuple[str, ...] = (
    "Balaenopteridae",  # Rorquals: blue, fin, humpback, minke
    "Balaenidae",  # Right whales
    "Eschrichtiidae",  # Gray whale
)

# ── US coastal bounding box ─────────────────────────────────
# All pipeline scripts filter to this region.
# Note: ocean covariates intentionally use a wider box
# (US_BBOX_WIDE) because Copernicus grid cells near the
# boundary need extra margin for interpolation.
US_BBOX = {
    "lat_min": 24.0,
    "lat_max": 49.0,
    "lon_min": -130.0,
    "lon_max": -65.0,
}

US_BBOX_WIDE = {
    "lat_min": 24.0,
    "lat_max": 50.0,
    "lon_min": -130.0,
    "lon_max": -60.0,
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

# MANUAL: see docs/manual_data_acquisition.md
BATHYMETRY_RASTER = RAW_DIR / "bathymetry" / "gebco_2025_n49.0_s24.0_w-130.0_e-65.0.tif"

# ── Processed data file paths ──────────────────────────────
AIS_H3_DIR = PROCESSED_DIR / "ais"
AIS_H3_PARQUET = AIS_H3_DIR / "ais_h3_res7.parquet"
AIS_H3_TEST_PARQUET = AIS_H3_DIR / "ais_h3_res7_test.parquet"

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
MLRUNS_DIR = PROJECT_ROOT / "mlruns"
MLFLOW_TRACKING_URI = f"file://{MLRUNS_DIR}"

# ── Seasons (meteorological, aligned with North Atlantic whale ecology) ──
SEASONS: dict[str, list[int]] = {
    "winter": [12, 1, 2],  # Right whale calving (SE US), low survey effort
    "spring": [3, 4, 5],  # Northward migration, SMAs activate
    "summer": [6, 7, 8],  # Feeding season (Gulf of Maine), peak surveys
    "fall": [9, 10, 11],  # Southward migration, SMAs deactivate
}
SEASON_ORDER: list[str] = ["winter", "spring", "summer", "fall"]

# ── Spatial cross-validation ────────────────────────────────
H3_CV_RESOLUTION = 2  # ~158 km edge — parent cells for CV fold grouping
N_CV_FOLDS = 5

# ── Collision risk sub-score weights ────────────────────────
# Must stay in sync with risk_weight_* vars in dbt_project.yml.
COLLISION_RISK_WEIGHTS: dict[str, float] = {
    "traffic_score": 0.25,
    "cetacean_score": 0.25,
    "proximity_score": 0.15,
    "strike_score": 0.10,
    "habitat_score": 0.10,
    "protection_gap": 0.10,
    "reference_risk_score": 0.05,
}

# ── ML-enhanced collision risk weights ──────────────────────
COLLISION_RISK_ML_WEIGHTS: dict[str, float] = {
    "interaction_score": 0.25,
    "traffic_score": 0.15,
    "whale_ml_score": 0.10,
    "proximity_score": 0.15,
    "strike_score": 0.10,
    "habitat_score": 0.10,
    "protection_gap": 0.10,
    "reference_risk_score": 0.05,
}

# ── Risk category thresholds (score >= threshold → label) ──
# Must stay in sync with risk_threshold_* vars in dbt_project.yml.
RISK_THRESHOLDS: dict[str, float] = {
    "critical": 0.70,
    "high": 0.50,
    "medium": 0.35,
    "low": 0.20,
    # Anything below 0.20 → "minimal" (implicit)
}

# ── Sub-score internal weights ──────────────────────────────
# Must stay in sync with matching vars in dbt_project.yml.

TRAFFIC_SCORE_WEIGHTS: dict[str, float] = {
    "speed_lethality": 0.20,
    "high_speed_fraction": 0.10,
    "vessels": 0.20,
    "large_vessels": 0.10,
    "draft_risk": 0.10,
    "draft_risk_fraction": 0.05,
    "commercial": 0.10,
    "night_traffic": 0.15,
}

CETACEAN_SCORE_WEIGHTS: dict[str, float] = {
    "sightings": 0.35,
    "baleen": 0.35,
    "recent": 0.30,
}

WHALE_ML_SCORE_WEIGHTS: dict[str, float] = {
    "any": 0.50,
    "max": 0.30,
    "mean": 0.20,
}

STRIKE_SCORE_WEIGHTS: dict[str, float] = {
    "total": 0.40,
    "fatal": 0.35,
    "baleen": 0.25,
}

HABITAT_SCORE_WEIGHTS: dict[str, float] = {
    "shelf": 0.50,
    "edge": 0.30,
    "depth_zone": 0.20,
}

DEPTH_ZONE_SCORES: dict[str, float] = {
    "shelf": 1.0,
    "slope": 0.5,
    "abyssal": 0.1,
}

PROXIMITY_SCORE_WEIGHTS: dict[str, float] = {
    "whale_ship": 0.45,
    "strike": 0.30,
    "protection": 0.25,
}

PROTECTION_GAP_SCORES: dict[str, float] = {
    "sma_and_notake": 0.1,
    "sma_only": 0.2,
    "proposed_and_mpa": 0.3,
    "notake_only": 0.3,
    "proposed_only": 0.4,
    "strict_mpa": 0.5,
    "any_mpa": 0.7,
    "none": 1.0,
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

# Target species labels (order matters for model output indices)
WHALE_AUDIO_SPECIES: list[str] = [
    "right_whale",
    "humpback_whale",
    "fin_whale",
    "blue_whale",
    "sperm_whale",
    "minke_whale",
    "sei_whale",
    "killer_whale",
    "unknown_whale",
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

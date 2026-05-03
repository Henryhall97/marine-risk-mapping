"""Tests for pipeline.config — the centralised configuration module.

These tests verify the structural integrity of every weight dict,
threshold ordering, season definitions, and path types. Because
config.py already validates weight sums at import time, several
of these tests serve as regression guards: if someone changes
dbt_project.yml in a way that breaks constraints, we'll catch it
here with a clear message rather than a cryptic ImportError.
"""

from pathlib import Path

# ── Weight dict structure ───────────────────────────────────


class TestWeightDictSums:
    """Every weight dict that feeds a percentile-ranked composite
    must sum to exactly 1.0 (± floating-point tolerance)."""

    def test_collision_risk_weights_sum(self):
        from pipeline.config import COLLISION_RISK_WEIGHTS

        assert abs(sum(COLLISION_RISK_WEIGHTS.values()) - 1.0) < 1e-9

    def test_collision_risk_ml_weights_sum(self):
        from pipeline.config import COLLISION_RISK_ML_WEIGHTS

        assert abs(sum(COLLISION_RISK_ML_WEIGHTS.values()) - 1.0) < 1e-9

    def test_traffic_score_weights_sum(self):
        from pipeline.config import TRAFFIC_SCORE_WEIGHTS

        assert abs(sum(TRAFFIC_SCORE_WEIGHTS.values()) - 1.0) < 1e-9

    def test_cetacean_score_weights_sum(self):
        from pipeline.config import CETACEAN_SCORE_WEIGHTS

        assert abs(sum(CETACEAN_SCORE_WEIGHTS.values()) - 1.0) < 1e-9

    def test_whale_ml_score_weights_sum(self):
        from pipeline.config import WHALE_ML_SCORE_WEIGHTS

        assert abs(sum(WHALE_ML_SCORE_WEIGHTS.values()) - 1.0) < 1e-9

    def test_strike_score_weights_sum(self):
        from pipeline.config import STRIKE_SCORE_WEIGHTS

        assert abs(sum(STRIKE_SCORE_WEIGHTS.values()) - 1.0) < 1e-9

    def test_habitat_score_weights_sum(self):
        from pipeline.config import HABITAT_SCORE_WEIGHTS

        assert abs(sum(HABITAT_SCORE_WEIGHTS.values()) - 1.0) < 1e-9

    def test_habitat_bathy_weights_sum(self):
        from pipeline.config import HABITAT_BATHY_WEIGHTS

        assert abs(sum(HABITAT_BATHY_WEIGHTS.values()) - 1.0) < 1e-9

    def test_proximity_score_weights_sum(self):
        from pipeline.config import PROXIMITY_SCORE_WEIGHTS

        assert abs(sum(PROXIMITY_SCORE_WEIGHTS.values()) - 1.0) < 1e-9


class TestWeightDictKeys:
    """Guard the expected keys so that renaming a sub-score
    without updating Python callers gets caught immediately."""

    def test_collision_risk_has_7_standard_keys(self):
        from pipeline.config import COLLISION_RISK_WEIGHTS

        expected = {
            "traffic_score",
            "cetacean_score",
            "proximity_score",
            "strike_score",
            "habitat_score",
            "protection_gap",
            "reference_risk_score",
        }
        assert set(COLLISION_RISK_WEIGHTS.keys()) == expected

    def test_collision_risk_ml_has_7_keys_no_habitat(self):
        from pipeline.config import COLLISION_RISK_ML_WEIGHTS

        assert "habitat_score" not in COLLISION_RISK_ML_WEIGHTS
        assert len(COLLISION_RISK_ML_WEIGHTS) == 7
        assert "interaction_score" in COLLISION_RISK_ML_WEIGHTS
        assert "whale_ml_score" in COLLISION_RISK_ML_WEIGHTS

    def test_traffic_weights_have_8_components(self):
        from pipeline.config import TRAFFIC_SCORE_WEIGHTS

        assert len(TRAFFIC_SCORE_WEIGHTS) == 8
        assert "speed_lethality" in TRAFFIC_SCORE_WEIGHTS
        assert "night_traffic" in TRAFFIC_SCORE_WEIGHTS


# ── Weight values are positive ──────────────────────────────


class TestWeightValues:
    """All individual weights must be strictly positive."""

    def test_all_weights_positive(self):
        from pipeline.config import (
            CETACEAN_SCORE_WEIGHTS,
            COLLISION_RISK_ML_WEIGHTS,
            COLLISION_RISK_WEIGHTS,
            HABITAT_BATHY_WEIGHTS,
            HABITAT_SCORE_WEIGHTS,
            PROXIMITY_SCORE_WEIGHTS,
            STRIKE_SCORE_WEIGHTS,
            TRAFFIC_SCORE_WEIGHTS,
            WHALE_ML_SCORE_WEIGHTS,
        )

        all_dicts = [
            COLLISION_RISK_WEIGHTS,
            COLLISION_RISK_ML_WEIGHTS,
            TRAFFIC_SCORE_WEIGHTS,
            CETACEAN_SCORE_WEIGHTS,
            WHALE_ML_SCORE_WEIGHTS,
            STRIKE_SCORE_WEIGHTS,
            HABITAT_SCORE_WEIGHTS,
            HABITAT_BATHY_WEIGHTS,
            PROXIMITY_SCORE_WEIGHTS,
        ]
        for d in all_dicts:
            for key, val in d.items():
                assert val > 0, f"{key} = {val} is not positive"


# ── Risk thresholds ─────────────────────────────────────────


class TestRiskThresholds:
    def test_strictly_descending(self):
        from pipeline.config import RISK_THRESHOLDS

        vals = list(RISK_THRESHOLDS.values())
        for i in range(len(vals) - 1):
            assert vals[i] > vals[i + 1], f"Threshold {vals[i]} not > {vals[i + 1]}"

    def test_all_between_0_and_1(self):
        from pipeline.config import RISK_THRESHOLDS

        for label, val in RISK_THRESHOLDS.items():
            assert 0 < val < 1, f"{label} = {val} not in (0, 1)"

    def test_four_thresholds(self):
        from pipeline.config import RISK_THRESHOLDS

        assert list(RISK_THRESHOLDS.keys()) == [
            "critical",
            "high",
            "medium",
            "low",
        ]


# ── Season definitions ──────────────────────────────────────


class TestSeasons:
    def test_four_seasons(self):
        from pipeline.config import SEASON_ORDER, SEASONS

        assert len(SEASONS) == 4
        assert SEASON_ORDER == ["winter", "spring", "summer", "fall"]

    def test_each_season_has_3_months(self):
        from pipeline.config import SEASONS

        for name, months in SEASONS.items():
            assert len(months) == 3, f"{name} has {len(months)} months"

    def test_all_12_months_covered(self):
        from pipeline.config import SEASONS

        all_months = sorted(m for months in SEASONS.values() for m in months)
        assert all_months == list(range(1, 13))

    def test_winter_wraps_year(self):
        from pipeline.config import SEASONS

        assert 12 in SEASONS["winter"]
        assert 1 in SEASONS["winter"]


# ── Geographic bounds ───────────────────────────────────────


class TestGeoBounds:
    def test_us_bbox_keys(self):
        from pipeline.config import US_BBOX

        assert set(US_BBOX.keys()) == {
            "lat_min",
            "lat_max",
            "lon_min",
            "lon_max",
        }

    def test_us_bbox_valid_ranges(self):
        from pipeline.config import US_BBOX

        assert US_BBOX["lat_min"] < US_BBOX["lat_max"]
        assert US_BBOX["lon_min"] < US_BBOX["lon_max"]
        # Covers Galápagos (~-2°) to Aleutians (~52°N)
        assert US_BBOX["lat_min"] >= -5
        assert US_BBOX["lat_max"] <= 55

    def test_wide_bbox_is_superset(self):
        from pipeline.config import US_BBOX, US_BBOX_WIDE

        assert US_BBOX_WIDE["lat_max"] >= US_BBOX["lat_max"]
        assert US_BBOX_WIDE["lon_max"] >= US_BBOX["lon_max"]


# ── Spatial constants ───────────────────────────────────────


class TestSpatialConstants:
    def test_h3_resolution(self):
        from pipeline.config import H3_RESOLUTION

        assert H3_RESOLUTION == 7

    def test_proximity_decay_rates_positive(self):
        from pipeline.config import (
            PROXIMITY_LAMBDA_PROTECTION,
            PROXIMITY_LAMBDA_STRIKE,
            PROXIMITY_LAMBDA_WHALE,
        )

        assert PROXIMITY_LAMBDA_WHALE > 0
        assert PROXIMITY_LAMBDA_STRIKE > 0
        assert PROXIMITY_LAMBDA_PROTECTION > 0

    def test_whale_lambda_largest(self):
        """Whale decay should be fastest (shortest half-life)."""
        from pipeline.config import (
            PROXIMITY_LAMBDA_PROTECTION,
            PROXIMITY_LAMBDA_STRIKE,
            PROXIMITY_LAMBDA_WHALE,
        )

        assert PROXIMITY_LAMBDA_WHALE > PROXIMITY_LAMBDA_STRIKE
        assert PROXIMITY_LAMBDA_STRIKE > PROXIMITY_LAMBDA_PROTECTION


# ── Path types ──────────────────────────────────────────────


class TestPaths:
    def test_project_root_is_path(self):
        from pipeline.config import PROJECT_ROOT

        assert isinstance(PROJECT_ROOT, Path)

    def test_key_paths_are_path_objects(self):
        from pipeline.config import (
            AIS_RAW_DIR,
            BATHYMETRY_RASTER,
            CETACEAN_FILE,
            DATA_DIR,
            ML_DIR,
            MPA_FILE,
            PROCESSED_DIR,
            RAW_DIR,
        )

        for p in [
            DATA_DIR,
            RAW_DIR,
            PROCESSED_DIR,
            AIS_RAW_DIR,
            CETACEAN_FILE,
            MPA_FILE,
            BATHYMETRY_RASTER,
            ML_DIR,
        ]:
            assert isinstance(p, Path), f"{p} is not a Path"

    def test_dbt_project_dir_exists(self):
        from pipeline.config import DBT_PROJECT_DIR

        assert DBT_PROJECT_DIR.is_dir()


# ── Database config ─────────────────────────────────────────


class TestDBConfig:
    def test_required_keys(self):
        from pipeline.config import DB_CONFIG

        assert set(DB_CONFIG.keys()) == {
            "host",
            "port",
            "dbname",
            "user",
            "password",
        }

    def test_port_is_int(self):
        from pipeline.config import DB_CONFIG

        assert isinstance(DB_CONFIG["port"], int)

    def test_default_values(self):
        """Without env vars, defaults should be local dev."""
        from pipeline.config import DB_CONFIG

        assert DB_CONFIG["host"] == "localhost"
        assert DB_CONFIG["port"] == 5433
        assert DB_CONFIG["dbname"] == "marine_risk"


# ── Audio constants ─────────────────────────────────────────


class TestAudioConstants:
    def test_sample_rate(self):
        from pipeline.config import AUDIO_SAMPLE_RATE

        assert AUDIO_SAMPLE_RATE == 16_000

    def test_species_list_length(self):
        from pipeline.config import WHALE_AUDIO_SPECIES

        # 9 ESA-listed species (incl. bowhead) + other_cetacean gatekeeper
        assert len(WHALE_AUDIO_SPECIES) == 10
        assert "other_cetacean" in WHALE_AUDIO_SPECIES

    def test_freq_bands_subset_of_species(self):
        from pipeline.config import WHALE_AUDIO_SPECIES, WHALE_FREQ_BANDS

        for sp in WHALE_FREQ_BANDS:
            assert sp in WHALE_AUDIO_SPECIES, (
                f"{sp} in freq bands but not in species list"
            )

    def test_freq_bands_are_ordered_pairs(self):
        from pipeline.config import WHALE_FREQ_BANDS

        for sp, (lo, hi) in WHALE_FREQ_BANDS.items():
            assert lo < hi, f"{sp} band: {lo} >= {hi}"
            assert lo > 0
            assert hi <= AUDIO_FMAX_CEILING

    def test_segment_hop_less_than_duration(self):
        from pipeline.config import AUDIO_SEGMENT_DURATION, AUDIO_SEGMENT_HOP

        assert AUDIO_SEGMENT_HOP < AUDIO_SEGMENT_DURATION


# Allow freq_bands test to reference a reasonable ceiling
AUDIO_FMAX_CEILING = 20_000  # Hz


# ── Protection gap scores ──────────────────────────────────


class TestProtectionGapScores:
    def test_scores_between_0_and_1(self):
        from pipeline.config import PROTECTION_GAP_SCORES

        for tier, score in PROTECTION_GAP_SCORES.items():
            assert 0 <= score <= 1, f"{tier} = {score}"

    def test_none_is_highest_gap(self):
        from pipeline.config import PROTECTION_GAP_SCORES

        assert PROTECTION_GAP_SCORES["none"] == max(PROTECTION_GAP_SCORES.values())

    def test_notake_and_sma_is_lowest_gap(self):
        from pipeline.config import PROTECTION_GAP_SCORES

        assert PROTECTION_GAP_SCORES["notake_and_sma"] == min(
            PROTECTION_GAP_SCORES.values()
        )

    def test_no_proposed_tiers(self):
        """Proposed zones must not appear — they are not real protection."""
        from pipeline.config import PROTECTION_GAP_SCORES

        for tier in PROTECTION_GAP_SCORES:
            assert "proposed" not in tier, f"Proposed tier still present: {tier}"

    def test_sma_only_near_unprotected(self):
        """SMA-only should score much higher (worse) than any MPA tier."""
        from pipeline.config import PROTECTION_GAP_SCORES

        assert PROTECTION_GAP_SCORES["sma_only"] > PROTECTION_GAP_SCORES["any_mpa"]


# ── Depth zone scores ──────────────────────────────────────


class TestDepthZoneScores:
    def test_scores_between_0_and_1(self):
        from pipeline.config import DEPTH_ZONE_SCORES

        for zone, score in DEPTH_ZONE_SCORES.items():
            assert 0 <= score <= 1, f"{zone} = {score}"

    def test_shelf_highest(self):
        """Continental shelf is the primary whale habitat zone."""
        from pipeline.config import DEPTH_ZONE_SCORES

        assert DEPTH_ZONE_SCORES["shelf"] >= DEPTH_ZONE_SCORES["slope"]
        assert DEPTH_ZONE_SCORES["slope"] >= DEPTH_ZONE_SCORES["abyssal"]

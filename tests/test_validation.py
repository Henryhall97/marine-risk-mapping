"""Tests for pipeline.validation — Pandera schemas and quality reports.

All tests use synthetic DataFrames, no disk I/O required.
"""

import pandas as pd
import pytest
from pandera.errors import SchemaError, SchemaErrors

# ── Pandera schema validation ───────────────────────────────


class TestCetaceanSchema:
    def test_valid_data_passes(self, sample_sightings_df):
        from pipeline.validation.schemas import cetacean_schema

        # Should not raise
        cetacean_schema.validate(sample_sightings_df)

    def test_lat_out_of_range_fails(self, sample_sightings_df):
        from pipeline.validation.schemas import cetacean_schema

        bad = sample_sightings_df.copy()
        bad.loc[0, "decimalLatitude"] = 80.0  # Arctic, outside US bbox
        with pytest.raises((SchemaError, SchemaErrors)):
            cetacean_schema.validate(bad)

    def test_lon_out_of_range_fails(self, sample_sightings_df):
        from pipeline.validation.schemas import cetacean_schema

        bad = sample_sightings_df.copy()
        bad.loc[0, "decimalLongitude"] = 10.0  # Europe
        with pytest.raises((SchemaError, SchemaErrors)):
            cetacean_schema.validate(bad)

    def test_missing_scientific_name_fails(self, sample_sightings_df):
        from pipeline.validation.schemas import cetacean_schema

        bad = sample_sightings_df.copy()
        bad.loc[0, "scientificName"] = None
        with pytest.raises((SchemaError, SchemaErrors)):
            cetacean_schema.validate(bad)


class TestAISSchema:
    def test_valid_ais_row(self):
        from pipeline.validation.schemas import ais_schema

        df = pd.DataFrame(
            {
                "mmsi": [123456789],
                "base_date_time": ["2024-01-01T00:00:00"],
                "sog": [12.5],
                "cog": [180.0],
                "heading": pd.array([270], dtype="Int16"),
                "vessel_name": ["TEST VESSEL"],
                "imo": ["1234567"],
                "call_sign": ["ABCD"],
                "vessel_type": pd.array([70], dtype="Int16"),
                "status": pd.array([0], dtype="Int16"),
                "length": [200.0],
                "width": pd.array([30], dtype="Int16"),
                "draft": [10.5],
                "cargo": pd.array([0], dtype="Int16"),
                "transceiver": ["A"],
            }
        )
        ais_schema.validate(df)

    def test_invalid_mmsi_fails(self):
        from pipeline.validation.schemas import ais_schema

        df = pd.DataFrame(
            {
                "mmsi": [999],  # Too short
                "base_date_time": ["2024-01-01"],
                "sog": [10.0],
                "cog": [90.0],
                "heading": pd.array([0], dtype="Int16"),
                "vessel_name": [None],
                "imo": [None],
                "call_sign": [None],
                "vessel_type": pd.array([None], dtype="Int16"),
                "status": pd.array([None], dtype="Int16"),
                "length": [None],
                "width": pd.array([None], dtype="Int16"),
                "draft": [None],
                "cargo": pd.array([None], dtype="Int16"),
                "transceiver": [None],
            }
        )
        with pytest.raises((SchemaError, SchemaErrors)):
            ais_schema.validate(df)


class TestValidateDataframe:
    """Test the validate_dataframe() wrapper that returns a result dict."""

    def test_valid_returns_valid_true(self, sample_sightings_df):
        from pipeline.validation.schemas import (
            cetacean_schema,
            validate_dataframe,
        )

        result = validate_dataframe(sample_sightings_df, cetacean_schema)
        assert result["valid"] is True
        assert result["n_failures"] == 0

    def test_invalid_returns_failures(self, sample_sightings_df):
        from pipeline.validation.schemas import (
            cetacean_schema,
            validate_dataframe,
        )

        bad = sample_sightings_df.copy()
        bad.loc[0, "decimalLatitude"] = 80.0
        result = validate_dataframe(bad, cetacean_schema)
        assert result["valid"] is False
        assert result["n_failures"] > 0


# ── Quality report functions ────────────────────────────────


class TestCompletenessReport:
    def test_all_complete(self):
        from pipeline.validation.quality_report import completeness_report

        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        report = completeness_report(df, "test")
        assert all(report["completeness_pct"] == 100.0)

    def test_partial_nulls(self):
        from pipeline.validation.quality_report import completeness_report

        df = pd.DataFrame({"a": [1, None, 3], "b": [None, None, 6]})
        report = completeness_report(df, "test")
        a_row = report[report["column"] == "a"].iloc[0]
        assert a_row["completeness_pct"] == pytest.approx(66.67, abs=0.01)
        b_row = report[report["column"] == "b"].iloc[0]
        assert b_row["completeness_pct"] == pytest.approx(33.33, abs=0.01)

    def test_empty_dataframe(self):
        from pipeline.validation.quality_report import completeness_report

        df = pd.DataFrame({"a": pd.Series(dtype=float)})
        report = completeness_report(df, "empty")
        assert len(report) == 1
        assert report.iloc[0]["total_rows"] == 0


class TestNumericSummary:
    def test_basic_stats(self):
        from pipeline.validation.quality_report import numeric_summary

        df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0]})
        report = numeric_summary(df, "test")
        row = report.iloc[0]
        assert row["min"] == 1.0
        assert row["max"] == 5.0
        assert row["mean"] == 3.0
        assert row["zero_pct"] == 0.0

    def test_ignores_string_columns(self):
        from pipeline.validation.quality_report import numeric_summary

        df = pd.DataFrame({"name": ["a", "b"], "val": [1.0, 2.0]})
        report = numeric_summary(df, "test")
        assert len(report) == 1
        assert report.iloc[0]["column"] == "val"

    def test_zero_percentage(self):
        from pipeline.validation.quality_report import numeric_summary

        df = pd.DataFrame({"x": [0, 0, 1, 2, 3]})
        report = numeric_summary(df, "test")
        assert report.iloc[0]["zero_pct"] == 40.0


class TestCategoricalSummary:
    def test_low_cardinality(self):
        from pipeline.validation.quality_report import categorical_summary

        df = pd.DataFrame({"color": ["red", "blue", "red", "green"]})
        report = categorical_summary(df, "test", max_unique=20)
        assert len(report) == 1
        assert report.iloc[0]["n_unique"] == 3
        assert report.iloc[0]["top_value"] == "red"

    def test_high_cardinality_skipped(self):
        from pipeline.validation.quality_report import categorical_summary

        df = pd.DataFrame({"id": [f"item_{i}" for i in range(100)]})
        report = categorical_summary(df, "test", max_unique=20)
        # High-cardinality columns appear with a skip marker
        assert len(report) == 1
        assert report.iloc[0]["n_unique"] == 100
        assert "skipped" in report.iloc[0]["top_value"]

    def test_numeric_columns_skipped(self):
        from pipeline.validation.quality_report import categorical_summary

        df = pd.DataFrame({"x": [1, 2, 3]})
        report = categorical_summary(df, "test")
        assert len(report) == 0

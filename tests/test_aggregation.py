"""Tests for pipeline.aggregation — proximity and bathymetry helpers.

Tests the pure-math functions that don't touch PostGIS.
"""

import numpy as np
import pytest

# ── haversine_km() ──────────────────────────────────────────


class TestHaversine:
    def test_zero_distance(self):
        from pipeline.aggregation.compute_proximity import haversine_km

        d = haversine_km(
            np.array([40.0]),
            np.array([-74.0]),
            np.array([40.0]),
            np.array([-74.0]),
        )
        assert d[0] == pytest.approx(0.0, abs=1e-10)

    def test_known_distance_ny_to_la(self):
        """NYC (40.7,-74.0) → LA (34.1,-118.2) ≈ 3944 km."""
        from pipeline.aggregation.compute_proximity import haversine_km

        d = haversine_km(
            np.array([40.7128]),
            np.array([-74.0060]),
            np.array([34.0522]),
            np.array([-118.2437]),
        )
        assert 3900 < d[0] < 4000

    def test_vectorised(self):
        from pipeline.aggregation.compute_proximity import haversine_km

        lats1 = np.array([0.0, 0.0, 0.0])
        lons1 = np.array([0.0, 0.0, 0.0])
        lats2 = np.array([0.0, 1.0, 2.0])
        lons2 = np.array([0.0, 0.0, 0.0])
        d = haversine_km(lats1, lons1, lats2, lons2)
        assert d.shape == (3,)
        assert d[0] == pytest.approx(0.0, abs=1e-10)
        # 1° lat ≈ 111 km
        assert 110 < d[1] < 112
        assert 220 < d[2] < 224

    def test_symmetry(self):
        from pipeline.aggregation.compute_proximity import haversine_km

        d_ab = haversine_km(
            np.array([30.0]),
            np.array([-80.0]),
            np.array([45.0]),
            np.array([-90.0]),
        )
        d_ba = haversine_km(
            np.array([45.0]),
            np.array([-90.0]),
            np.array([30.0]),
            np.array([-80.0]),
        )
        assert d_ab[0] == pytest.approx(d_ba[0], rel=1e-10)


# ── to_cartesian() ──────────────────────────────────────────


class TestToCartesian:
    def test_shape(self):
        from pipeline.aggregation.compute_proximity import to_cartesian

        lats = np.array([30.0, 40.0, 50.0])
        lons = np.array([-70.0, -80.0, -90.0])
        xy = to_cartesian(lats, lons)
        assert xy.shape == (3, 2)

    def test_origin_at_zero(self):
        from pipeline.aggregation.compute_proximity import to_cartesian

        xy = to_cartesian(np.array([0.0]), np.array([0.0]))
        assert xy[0, 0] == pytest.approx(0.0)
        assert xy[0, 1] == pytest.approx(0.0)

    def test_latitude_scales_by_111(self):
        """1° latitude ≈ 111 km in the y direction."""
        from pipeline.aggregation.compute_proximity import (
            KM_PER_DEG_LAT,
            to_cartesian,
        )

        xy = to_cartesian(np.array([0.0, 1.0]), np.array([0.0, 0.0]))
        dy = xy[1, 1] - xy[0, 1]
        assert dy == pytest.approx(KM_PER_DEG_LAT, rel=1e-6)


# ── get_sample_points() ────────────────────────────────────


class TestGetSamplePoints:
    def test_returns_7_points(self):
        import h3

        from pipeline.aggregation.sample_bathymetry import get_sample_points

        # Use a known H3 cell (Times Square area)
        cell_hex = h3.latlng_to_cell(40.758, -73.985, 7)
        points = get_sample_points(cell_hex)
        assert len(points) == 7

    def test_points_are_lat_lon_tuples(self):
        import h3

        from pipeline.aggregation.sample_bathymetry import get_sample_points

        cell_hex = h3.latlng_to_cell(40.758, -73.985, 7)
        points = get_sample_points(cell_hex)
        for lat, lon in points:
            assert -90 <= lat <= 90
            assert -180 <= lon <= 180

    def test_centroid_is_first(self):
        import h3

        from pipeline.aggregation.sample_bathymetry import get_sample_points

        cell_hex = h3.latlng_to_cell(40.758, -73.985, 7)
        points = get_sample_points(cell_hex)
        centroid = h3.cell_to_latlng(cell_hex)
        assert points[0] == pytest.approx(centroid, abs=1e-10)


# ── Exponential decay math ──────────────────────────────────


class TestExponentialDecay:
    """Verify the proximity decay formula used in compute_proximity."""

    def test_at_zero_distance(self):
        """Score at distance 0 should be 1.0."""
        lam = 0.0693  # ~10 km half-life
        score = np.exp(-lam * 0.0)
        assert score == pytest.approx(1.0)

    def test_at_half_life(self):
        """Score at half-life distance should be ~0.5."""
        from pipeline.config import PROXIMITY_LAMBDA_WHALE

        half_life = 10.0
        score = np.exp(-PROXIMITY_LAMBDA_WHALE * half_life)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_monotone_decreasing(self):
        from pipeline.config import PROXIMITY_LAMBDA_WHALE

        distances = np.array([0, 5, 10, 20, 50, 100])
        scores = np.exp(-PROXIMITY_LAMBDA_WHALE * distances)
        for i in range(len(scores) - 1):
            assert scores[i] > scores[i + 1]

    def test_protection_decay_slower(self):
        """Protection has longest half-life → slowest decay."""
        from pipeline.config import (
            PROXIMITY_LAMBDA_PROTECTION,
            PROXIMITY_LAMBDA_WHALE,
        )

        d = 25.0
        whale_score = np.exp(-PROXIMITY_LAMBDA_WHALE * d)
        prot_score = np.exp(-PROXIMITY_LAMBDA_PROTECTION * d)
        assert prot_score > whale_score

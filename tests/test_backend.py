"""Tests for the FastAPI backend — routes, services, config.

All database interactions are mocked at the service layer so
tests run without PostGIS.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture()
def client():
    """Create a test client with the pool pre-initialised."""
    with (
        patch("backend.services.database.init_pool"),
        patch("backend.services.database.close_pool"),
    ):
        from backend.app import app

        with TestClient(app) as c:
            yield c


# ── Health ──────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_healthy(self, client: TestClient):
        with patch("backend.api.health.fetch_scalar", return_value=1):
            r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"
        assert body["database"] == "connected"

    def test_degraded_on_db_failure(self, client: TestClient):
        with patch(
            "backend.api.health.fetch_scalar",
            side_effect=Exception("connection refused"),
        ):
            r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "degraded"
        assert body["database"] == "unreachable"


# ── Risk zones ──────────────────────────────────────────────

_SAMPLE_RISK_ROW = {
    "h3_cell": 607252735839895551,
    "cell_lat": 40.5,
    "cell_lon": -73.2,
    "risk_score": 0.85,
    "risk_category": "critical",
}

_BBOX = {
    "lat_min": 40.0,
    "lat_max": 41.0,
    "lon_min": -74.0,
    "lon_max": -72.0,
}


class TestRiskZones:
    def test_list_risk_zones(self, client: TestClient):
        with (
            patch(
                "backend.services.risk.count_risk_zones",
                return_value=1,
            ),
            patch(
                "backend.services.risk.get_risk_zones",
                return_value=[_SAMPLE_RISK_ROW],
            ),
        ):
            r = client.get("/api/v1/risk/zones", params=_BBOX)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["risk_category"] == "critical"

    def test_list_risk_zones_with_filters(self, client: TestClient):
        with (
            patch(
                "backend.services.risk.count_risk_zones",
                return_value=0,
            ),
            patch(
                "backend.services.risk.get_risk_zones",
                return_value=[],
            ),
        ):
            params = {
                **_BBOX,
                "risk_category": "high",
                "min_risk_score": 0.7,
            }
            r = client.get("/api/v1/risk/zones", params=params)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_invalid_bbox_lat_order(self, client: TestClient):
        params = {
            "lat_min": 42.0,
            "lat_max": 40.0,
            "lon_min": -74.0,
            "lon_max": -72.0,
        }
        r = client.get("/api/v1/risk/zones", params=params)
        assert r.status_code == 400

    def test_invalid_bbox_too_large(self, client: TestClient):
        params = {
            "lat_min": 10.0,
            "lat_max": 60.0,
            "lon_min": -150.0,
            "lon_max": -50.0,
        }
        r = client.get("/api/v1/risk/zones", params=params)
        assert r.status_code == 400
        assert "exceeds" in r.json()["detail"].lower()

    def test_invalid_risk_category(self, client: TestClient):
        params = {**_BBOX, "risk_category": "extreme"}
        r = client.get("/api/v1/risk/zones", params=params)
        assert r.status_code == 400

    def test_get_risk_zone_detail_found(self, client: TestClient):
        full_row = {
            **_SAMPLE_RISK_ROW,
            "traffic_score": 0.9,
            "cetacean_score": 0.7,
            "proximity_score": 0.6,
            "strike_score": 0.0,
            "habitat_score": 0.5,
            "protection_gap": 0.3,
            "reference_risk_score": 0.4,
            "has_traffic": True,
            "has_whale_sightings": True,
            "in_mpa": False,
            "has_strike_history": False,
            "in_speed_zone": False,
            "in_current_sma": False,
            "in_proposed_zone": False,
            "has_nisi_reference": True,
            "months_active": 12,
            "total_pings": 50000,
            "avg_monthly_vessels": 42.5,
            "peak_monthly_vessels": 80.0,
            "avg_speed_knots": 12.3,
            "peak_speed_knots": 25.0,
            "avg_high_speed_vessels": 5.0,
            "avg_large_vessels": 10.0,
            "avg_speed_lethality": 0.6,
            "night_traffic_ratio": 0.3,
            "avg_commercial_vessels": 15.0,
            "avg_fishing_vessels": 8.0,
            "total_sightings": 25,
            "unique_species": 3,
            "recent_sightings": 10,
            "baleen_whale_sightings": 20,
            "total_strikes": 0,
            "fatal_strikes": 0,
            "strike_species_list": None,
            "depth_m": -150.0,
            "depth_zone": "shelf",
            "is_continental_shelf": True,
            "sst": 18.5,
            "mld": 30.0,
            "pp_upper_200m": 0.5,
            "dist_to_nearest_whale_km": 5.2,
            "dist_to_nearest_ship_km": 1.1,
            "dist_to_nearest_strike_km": 200.0,
            "dist_to_nearest_protection_km": 15.0,
            "mpa_count": 0,
            "has_strict_protection": False,
            "zone_count": 0,
            "zone_names": None,
            "nisi_all_risk": 0.6,
        }
        with patch(
            "backend.services.risk.get_risk_zone_detail",
            return_value=full_row,
        ):
            r = client.get(f"/api/v1/risk/zones/{_SAMPLE_RISK_ROW['h3_cell']}")
        assert r.status_code == 200
        body = r.json()
        assert body["risk_score"] == 0.85
        assert body["scores"]["traffic_score"] == 0.9
        assert body["flags"]["has_traffic"] is True
        assert body["months_active"] == 12

    def test_get_risk_zone_detail_not_found(self, client: TestClient):
        with patch(
            "backend.services.risk.get_risk_zone_detail",
            return_value=None,
        ):
            r = client.get("/api/v1/risk/zones/999")
        assert r.status_code == 404


# ── Risk stats ──────────────────────────────────────────────


class TestRiskStats:
    def test_stats_found(self, client: TestClient):
        mock_stats = {
            "total_cells": 500,
            "avg_risk_score": 0.45,
            "max_risk_score": 0.95,
            "min_risk_score": 0.01,
            "category_counts": {
                "critical": 10,
                "high": 50,
                "medium": 200,
                "low": 200,
                "minimal": 40,
            },
        }
        with patch(
            "backend.services.risk.get_risk_stats",
            return_value=mock_stats,
        ):
            r = client.get("/api/v1/risk/zones/stats", params=_BBOX)
        assert r.status_code == 200
        body = r.json()
        assert body["total_cells"] == 500
        assert body["category_counts"]["critical"] == 10

    def test_stats_empty_bbox(self, client: TestClient):
        with patch(
            "backend.services.risk.get_risk_stats",
            return_value=None,
        ):
            r = client.get("/api/v1/risk/zones/stats", params=_BBOX)
        assert r.status_code == 404


# ── Seasonal risk ───────────────────────────────────────────


class TestSeasonalRisk:
    def test_list_seasonal(self, client: TestClient):
        seasonal_row = {
            "h3_cell": 607252735839895551,
            "season": "winter",
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "risk_score": 0.72,
            "risk_category": "high",
            "traffic_score": 0.8,
            "cetacean_score": 0.6,
            "proximity_score": 0.5,
            "strike_score": 0.0,
            "habitat_score": 0.4,
            "protection_gap": 0.2,
            "reference_risk_score": 0.3,
            "has_traffic": True,
            "has_whale_sightings": True,
            "in_mpa": False,
            "has_strike_history": False,
            "in_speed_zone": True,
            "in_current_sma": True,
            "in_proposed_zone": False,
            "has_nisi_reference": True,
        }
        with (
            patch(
                "backend.services.risk.count_seasonal_risk_zones",
                return_value=1,
            ),
            patch(
                "backend.services.risk.get_seasonal_risk_zones",
                return_value=[seasonal_row],
            ),
        ):
            params = {**_BBOX, "season": "winter"}
            r = client.get("/api/v1/risk/seasonal", params=params)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["season"] == "winter"
        assert body["data"][0]["scores"]["traffic_score"] == 0.8

    def test_invalid_season(self, client: TestClient):
        params = {**_BBOX, "season": "autumn"}
        r = client.get("/api/v1/risk/seasonal", params=params)
        assert r.status_code == 400


# ── Species ─────────────────────────────────────────────────


class TestSpecies:
    def test_list_species(self, client: TestClient):
        mock_rows = [
            {
                "species_group": "right_whale",
                "common_name": "North Atlantic Right Whale",
                "scientific_name": "Eubalaena glacialis",
                "is_baleen": True,
                "conservation_priority": "critical",
            },
            {
                "species_group": "humpback_whale",
                "common_name": "Humpback Whale",
                "scientific_name": "Megaptera novaeangliae",
                "is_baleen": True,
                "conservation_priority": "high",
            },
        ]
        with patch(
            "backend.services.species.list_species",
            return_value=mock_rows,
        ):
            r = client.get("/api/v1/species")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert body["data"][0]["species_group"] == "right_whale"

    def test_species_risk(self, client: TestClient):
        mock_row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "species": "Eubalaena glacialis",
            "common_name": "North Atlantic Right Whale",
            "species_group": "right_whale",
            "is_baleen": True,
            "sighting_count": 15,
            "earliest_year": 2010,
            "latest_year": 2023,
            "avg_monthly_vessels": 30.0,
            "avg_speed_knots": 11.0,
            "depth_m": -50.0,
            "depth_zone": "shelf",
            "in_speed_zone": True,
            "mpa_count": 1,
            "species_risk_score": 0.88,
        }
        with (
            patch(
                "backend.services.species.count_species_risk",
                return_value=1,
            ),
            patch(
                "backend.services.species.get_species_risk",
                return_value=[mock_row],
            ),
        ):
            params = {
                **_BBOX,
                "species_group": "right_whale",
            }
            r = client.get("/api/v1/species/risk", params=params)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["species_risk_score"] == 0.88


# ── Traffic ─────────────────────────────────────────────────


class TestTraffic:
    def test_monthly_traffic(self, client: TestClient):
        mock_row = {
            "h3_cell": 607252735839895551,
            "month": "2023-06-01",
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "unique_vessels": 45,
            "ping_count": 12000,
            "vw_avg_speed_knots": 10.5,
            "max_speed_knots": 22.0,
            "high_speed_vessel_count": 3,
            "large_vessel_count": 8,
            "day_unique_vessels": 35,
            "night_unique_vessels": 20,
            "cargo_vessels": 12,
            "tanker_vessels": 5,
            "fishing_vessels": 10,
            "passenger_vessels": 3,
            "depth_zone": "shelf",
            "is_continental_shelf": True,
            "in_mpa": False,
        }
        with (
            patch(
                "backend.services.traffic.count_monthly_traffic",
                return_value=1,
            ),
            patch(
                "backend.services.traffic.get_monthly_traffic",
                return_value=[mock_row],
            ),
        ):
            params = {
                **_BBOX,
                "month_start": "2023-01-01",
                "month_end": "2023-12-01",
            }
            r = client.get("/api/v1/traffic/monthly", params=params)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["unique_vessels"] == 45
        assert body["data"][0]["month"] == "2023-06-01"

    def test_traffic_bbox_validation(self, client: TestClient):
        params = {
            "lat_min": 42.0,
            "lat_max": 40.0,
            "lon_min": -74.0,
            "lon_max": -72.0,
        }
        r = client.get("/api/v1/traffic/monthly", params=params)
        assert r.status_code == 400


# ── Photo classification ────────────────────────────────────


class TestPhotoClassify:
    def test_classify_success(self, client: TestClient):
        mock_result = {
            "predicted_species": "humpback_whale",
            "confidence": 0.92,
            "probabilities": {
                "humpback_whale": 0.92,
                "fin_whale": 0.04,
                "right_whale": 0.02,
                "other_cetacean": 0.02,
            },
            "gps_source": "user",
            "risk_context": {
                "h3_cell": 607252735839895551,
                "cell_lat": 40.5,
                "cell_lon": -73.2,
                "risk_score": 0.75,
                "risk_category": "high",
            },
        }
        with patch(
            "backend.services.photo.classify_photo",
            return_value=mock_result,
        ):
            r = client.post(
                "/api/v1/photo/classify",
                files={
                    "file": (
                        "whale.jpg",
                        b"\xff\xd8\xff" + b"\x00" * 100,
                        "image/jpeg",
                    )
                },
                data={"lat": "40.5", "lon": "-73.2"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["classification"]["predicted_species"] == "humpback_whale"
        assert body["classification"]["confidence"] == 0.92
        assert body["gps_source"] == "user"
        assert body["risk_context"]["risk_category"] == "high"

    def test_classify_no_gps(self, client: TestClient):
        mock_result = {
            "predicted_species": "fin_whale",
            "confidence": 0.88,
            "probabilities": {"fin_whale": 0.88},
            "gps_source": None,
        }
        with patch(
            "backend.services.photo.classify_photo",
            return_value=mock_result,
        ):
            r = client.post(
                "/api/v1/photo/classify",
                files={
                    "file": (
                        "whale.png",
                        b"\x89PNG" + b"\x00" * 100,
                        "image/png",
                    )
                },
            )
        assert r.status_code == 200
        body = r.json()
        assert body["risk_context"] is None
        assert body["gps_source"] is None

    def test_classify_unsupported_type(self, client: TestClient):
        r = client.post(
            "/api/v1/photo/classify",
            files={
                "file": (
                    "doc.pdf",
                    b"%PDF-1.4",
                    "application/pdf",
                )
            },
        )
        assert r.status_code == 415

    def test_classify_model_unavailable(self, client: TestClient):
        with patch(
            "backend.services.photo.classify_photo",
            side_effect=RuntimeError("model not found"),
        ):
            r = client.post(
                "/api/v1/photo/classify",
                files={
                    "file": (
                        "whale.jpg",
                        b"\xff\xd8\xff" + b"\x00" * 100,
                        "image/jpeg",
                    )
                },
            )
        assert r.status_code == 503


# ── Config ──────────────────────────────────────────────────


class TestAudioClassify:
    def test_classify_success(self, client: TestClient):
        mock_result = {
            "filename": "recording.wav",
            "lat": 42.3,
            "lon": -70.5,
            "h3_cell": 607252735839895551,
            "dominant_species": "humpback_whale",
            "n_segments": 3,
            "segments": [
                {
                    "segment_idx": 0,
                    "start_sec": 0.0,
                    "end_sec": 4.0,
                    "predicted_species": "humpback_whale",
                    "confidence": 0.91,
                    "probabilities": {
                        "humpback_whale": 0.91,
                        "fin_whale": 0.05,
                    },
                },
                {
                    "segment_idx": 1,
                    "start_sec": 2.0,
                    "end_sec": 6.0,
                    "predicted_species": "humpback_whale",
                    "confidence": 0.88,
                    "probabilities": {
                        "humpback_whale": 0.88,
                        "fin_whale": 0.07,
                    },
                },
                {
                    "segment_idx": 2,
                    "start_sec": 4.0,
                    "end_sec": 8.0,
                    "predicted_species": "fin_whale",
                    "confidence": 0.72,
                    "probabilities": {
                        "fin_whale": 0.72,
                        "humpback_whale": 0.20,
                    },
                },
            ],
            "risk_context": {
                "risk_score": 0.75,
                "traffic_score": 0.8,
                "cetacean_score": 0.6,
                "proximity_score": 0.5,
                "strike_score": 0.0,
                "habitat_score": 0.4,
                "protection_gap": 0.2,
                "reference_risk_score": 0.3,
            },
        }
        with patch(
            "backend.services.audio.classify_audio",
            return_value=mock_result,
        ):
            r = client.post(
                "/api/v1/audio/classify",
                files={
                    "file": (
                        "recording.wav",
                        b"RIFF" + b"\x00" * 100,
                        "audio/wav",
                    )
                },
                data={"lat": "42.3", "lon": "-70.5"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["dominant_species"] == "humpback_whale"
        assert body["n_segments"] == 3
        assert len(body["segments"]) == 3
        assert body["segments"][0]["confidence"] == 0.91
        assert body["risk_context"]["risk_score"] == 0.75
        assert body["h3_cell"] == 607252735839895551

    def test_classify_no_risk_context(self, client: TestClient):
        mock_result = {
            "filename": "short.wav",
            "lat": 30.0,
            "lon": -80.0,
            "h3_cell": 607252735839895551,
            "dominant_species": "right_whale",
            "n_segments": 1,
            "segments": [
                {
                    "segment_idx": 0,
                    "start_sec": 0.0,
                    "end_sec": 4.0,
                    "predicted_species": "right_whale",
                    "confidence": 0.95,
                    "probabilities": {"right_whale": 0.95},
                },
            ],
            "risk_context": None,
        }
        with patch(
            "backend.services.audio.classify_audio",
            return_value=mock_result,
        ):
            r = client.post(
                "/api/v1/audio/classify",
                files={
                    "file": (
                        "short.wav",
                        b"RIFF" + b"\x00" * 50,
                        "audio/wav",
                    )
                },
                data={"lat": "30.0", "lon": "-80.0"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["risk_context"] is None
        assert body["dominant_species"] == "right_whale"

    def test_classify_missing_coordinates(self, client: TestClient):
        """lat and lon are required for audio — should fail."""
        r = client.post(
            "/api/v1/audio/classify",
            files={
                "file": (
                    "recording.wav",
                    b"RIFF" + b"\x00" * 100,
                    "audio/wav",
                )
            },
        )
        assert r.status_code == 422  # validation error

    def test_classify_model_unavailable(self, client: TestClient):
        with patch(
            "backend.services.audio.classify_audio",
            side_effect=FileNotFoundError("model not found"),
        ):
            r = client.post(
                "/api/v1/audio/classify",
                files={
                    "file": (
                        "recording.wav",
                        b"RIFF" + b"\x00" * 100,
                        "audio/wav",
                    )
                },
                data={"lat": "42.3", "lon": "-70.5"},
            )
        assert r.status_code == 503

    def test_classify_empty_file(self, client: TestClient):
        r = client.post(
            "/api/v1/audio/classify",
            files={"file": ("empty.wav", b"", "audio/wav")},
            data={"lat": "42.3", "lon": "-70.5"},
        )
        assert r.status_code == 400


# ── Config (unchanged) ─────────────────────────────────────


class TestConfig:
    def test_config_values(self):
        from backend.config import (
            API_TITLE,
            API_VERSION,
            CORS_ORIGINS,
            DEFAULT_PAGE_SIZE,
            MAX_BBOX_AREA_DEG2,
            MAX_PAGE_SIZE,
        )

        assert DEFAULT_PAGE_SIZE == 100
        assert MAX_PAGE_SIZE == 5_000
        assert MAX_BBOX_AREA_DEG2 == 100.0
        assert "http://localhost:3000" in CORS_ORIGINS
        assert API_TITLE == "Marine Risk Mapping API"
        assert API_VERSION == "0.1.0"

    def test_database_url_format(self):
        from backend.config import DATABASE_URL

        assert DATABASE_URL.startswith("postgresql://")
        assert "marine_risk" in DATABASE_URL


# ── Layer endpoints ─────────────────────────────────────────

_SAMPLE_BATHY_ROW = {
    "h3_cell": 607252735839895551,
    "cell_lat": 40.5,
    "cell_lon": -73.2,
    "depth_m": -120.0,
    "min_depth_m": -150.0,
    "max_depth_m": -90.0,
    "depth_range_m": 60.0,
    "depth_zone": "continental_shelf",
    "is_continental_shelf": True,
    "is_shelf_edge": False,
    "is_land": False,
}


class TestBathymetryLayer:
    def test_list_bathymetry(self, client: TestClient):
        with (
            patch(
                "backend.services.layers.count_bathymetry",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_bathymetry",
                return_value=[_SAMPLE_BATHY_ROW],
            ),
        ):
            r = client.get("/api/v1/layers/bathymetry", params=_BBOX)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["depth_m"] == -120.0
        assert body["data"][0]["depth_zone"] == "continental_shelf"

    def test_depth_zone_filter(self, client: TestClient):
        with (
            patch(
                "backend.services.layers.count_bathymetry",
                return_value=0,
            ),
            patch(
                "backend.services.layers.get_bathymetry",
                return_value=[],
            ),
        ):
            params = {**_BBOX, "depth_zone": "deep_ocean"}
            r = client.get("/api/v1/layers/bathymetry", params=params)
        assert r.status_code == 200

    def test_invalid_depth_zone(self, client: TestClient):
        params = {**_BBOX, "depth_zone": "abyss"}
        r = client.get("/api/v1/layers/bathymetry", params=params)
        assert r.status_code == 400

    def test_bbox_validation(self, client: TestClient):
        params = {
            "lat_min": 42.0,
            "lat_max": 40.0,
            "lon_min": -74.0,
            "lon_max": -72.0,
        }
        r = client.get("/api/v1/layers/bathymetry", params=params)
        assert r.status_code == 400


class TestOceanCovariateLayer:
    def test_list_annual(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "season": None,
            "sst": 18.5,
            "sst_sd": 2.1,
            "mld": 25.0,
            "sla": 0.02,
            "pp_upper_200m": 0.45,
        }
        with (
            patch(
                "backend.services.layers.count_ocean_covariates",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_ocean_covariates",
                return_value=[row],
            ),
        ):
            r = client.get("/api/v1/layers/ocean", params=_BBOX)
        assert r.status_code == 200
        body = r.json()
        assert body["data"][0]["sst"] == 18.5
        assert body["data"][0]["season"] is None

    def test_list_seasonal(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "season": "summer",
            "sst": 24.0,
            "sst_sd": 1.5,
            "mld": 11.0,
            "sla": 0.03,
            "pp_upper_200m": 0.60,
        }
        with (
            patch(
                "backend.services.layers.count_ocean_covariates",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_ocean_covariates",
                return_value=[row],
            ),
        ):
            params = {**_BBOX, "season": "summer"}
            r = client.get("/api/v1/layers/ocean", params=params)
        assert r.status_code == 200
        assert r.json()["data"][0]["season"] == "summer"

    def test_invalid_season(self, client: TestClient):
        params = {**_BBOX, "season": "autumn"}
        r = client.get("/api/v1/layers/ocean", params=params)
        assert r.status_code == 400


class TestWhalePredictionLayer:
    def test_list_predictions(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "season": "winter",
            "isdm_blue_whale": 0.12,
            "isdm_fin_whale": 0.35,
            "isdm_humpback_whale": 0.45,
            "isdm_sperm_whale": 0.02,
            "max_whale_prob": 0.45,
            "mean_whale_prob": 0.24,
            "any_whale_prob": 0.65,
        }
        with (
            patch(
                "backend.services.layers.count_whale_predictions",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_whale_predictions",
                return_value=[row],
            ),
        ):
            params = {**_BBOX, "season": "winter"}
            r = client.get("/api/v1/layers/whale-predictions", params=params)
        assert r.status_code == 200
        body = r.json()
        assert body["data"][0]["any_whale_prob"] == 0.65

    def test_species_filter(self, client: TestClient):
        with (
            patch(
                "backend.services.layers.count_whale_predictions",
                return_value=0,
            ),
            patch(
                "backend.services.layers.get_whale_predictions",
                return_value=[],
            ),
        ):
            params = {
                **_BBOX,
                "species": "blue_whale",
                "min_probability": 0.5,
            }
            r = client.get("/api/v1/layers/whale-predictions", params=params)
        assert r.status_code == 200

    def test_invalid_species(self, client: TestClient):
        params = {**_BBOX, "species": "narwhal"}
        r = client.get("/api/v1/layers/whale-predictions", params=params)
        assert r.status_code == 400


class TestMPALayer:
    def test_list_mpa(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "mpa_count": 2,
            "mpa_names": "Stellwagen Bank,Gerry Studds",
            "protection_level": "multi_use",
            "has_no_take_zone": False,
        }
        with (
            patch(
                "backend.services.layers.count_mpa_coverage",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_mpa_coverage",
                return_value=[row],
            ),
        ):
            r = client.get("/api/v1/layers/mpa", params=_BBOX)
        assert r.status_code == 200
        body = r.json()
        assert body["data"][0]["mpa_count"] == 2


class TestSpeedZoneLayer:
    def test_list_static(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "season": None,
            "zone_count": 1,
            "zone_names": "Great South Channel",
            "current_sma_count": 1,
            "proposed_zone_count": 0,
            "max_season_days": 90,
            "season_labels": "winter,spring",
        }
        with (
            patch(
                "backend.services.layers.count_speed_zones",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_speed_zones",
                return_value=[row],
            ),
        ):
            r = client.get("/api/v1/layers/speed-zones", params=_BBOX)
        assert r.status_code == 200
        assert r.json()["data"][0]["zone_count"] == 1

    def test_seasonal_filter(self, client: TestClient):
        with (
            patch(
                "backend.services.layers.count_speed_zones",
                return_value=0,
            ),
            patch(
                "backend.services.layers.get_speed_zones",
                return_value=[],
            ),
        ):
            params = {**_BBOX, "season": "winter"}
            r = client.get("/api/v1/layers/speed-zones", params=params)
        assert r.status_code == 200


class TestProximityLayer:
    def test_list_proximity(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "dist_to_nearest_whale_km": 5.2,
            "dist_to_nearest_ship_km": 1.1,
            "dist_to_nearest_strike_km": 200.0,
            "dist_to_nearest_protection_km": 15.0,
            "whale_proximity_score": 0.7,
            "ship_proximity_score": 0.9,
            "strike_proximity_score": 0.01,
            "protection_proximity_score": 0.3,
        }
        with (
            patch(
                "backend.services.layers.count_proximity",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_proximity",
                return_value=[row],
            ),
        ):
            r = client.get("/api/v1/layers/proximity", params=_BBOX)
        assert r.status_code == 200
        body = r.json()
        assert body["data"][0]["whale_proximity_score"] == 0.7


class TestNisiRiskLayer:
    def test_list_nisi(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "nisi_all_risk": 0.65,
            "nisi_shipping_index": 0.8,
            "nisi_whale_space_use": 0.5,
            "nisi_blue_risk": 0.2,
            "nisi_fin_risk": 0.4,
            "nisi_humpback_risk": 0.6,
            "nisi_sperm_risk": 0.1,
            "nisi_has_management": True,
            "nisi_has_mandatory_mgmt": False,
            "nisi_hotspot_overlap": True,
        }
        with (
            patch(
                "backend.services.layers.count_nisi_risk",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_nisi_risk",
                return_value=[row],
            ),
        ):
            r = client.get("/api/v1/layers/nisi-risk", params=_BBOX)
        assert r.status_code == 200
        body = r.json()
        assert body["data"][0]["nisi_all_risk"] == 0.65


class TestCetaceanDensityLayer:
    def test_list_density(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "season": None,
            "total_sightings": 25,
            "unique_species": 3,
            "baleen_sightings": 20,
            "recent_sightings": 10,
            "right_whale_sightings": 5,
            "humpback_sightings": 10,
            "fin_whale_sightings": 5,
            "blue_whale_sightings": 0,
            "sperm_whale_sightings": 5,
            "minke_whale_sightings": 0,
        }
        with (
            patch(
                "backend.services.layers.count_cetacean_density",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_cetacean_density",
                return_value=[row],
            ),
        ):
            r = client.get("/api/v1/layers/cetacean-density", params=_BBOX)
        assert r.status_code == 200
        body = r.json()
        assert body["data"][0]["total_sightings"] == 25

    def test_min_sightings_filter(self, client: TestClient):
        with (
            patch(
                "backend.services.layers.count_cetacean_density",
                return_value=0,
            ),
            patch(
                "backend.services.layers.get_cetacean_density",
                return_value=[],
            ),
        ):
            params = {**_BBOX, "min_sightings": 10}
            r = client.get("/api/v1/layers/cetacean-density", params=params)
        assert r.status_code == 200


class TestStrikeDensityLayer:
    def test_list_strikes(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "total_strikes": 3,
            "fatal_strikes": 1,
            "serious_injury_strikes": 1,
            "baleen_strikes": 2,
            "right_whale_strikes": 1,
            "unique_species_groups": 2,
            "species_list": "right,finback",
        }
        with (
            patch(
                "backend.services.layers.count_strike_density",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_strike_density",
                return_value=[row],
            ),
        ):
            r = client.get("/api/v1/layers/strike-density", params=_BBOX)
        assert r.status_code == 200
        body = r.json()
        assert body["data"][0]["total_strikes"] == 3
        assert body["data"][0]["species_list"] == "right,finback"


# ── ML risk endpoints ───────────────────────────────────────


class TestMLRisk:
    def test_list_ml_risk(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "season": "winter",
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "risk_score": 0.78,
            "risk_category": "high",
        }
        with (
            patch(
                "backend.services.layers.count_ml_risk_zones",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_ml_risk_zones",
                return_value=[row],
            ),
        ):
            params = {**_BBOX, "season": "winter"}
            r = client.get("/api/v1/risk/ml", params=params)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["risk_category"] == "high"

    def test_ml_risk_stats(self, client: TestClient):
        stats = {
            "total_cells": 200,
            "avg_risk_score": 0.42,
            "max_risk_score": 0.92,
            "min_risk_score": 0.01,
            "category_counts": {"high": 30, "medium": 100, "low": 70},
        }
        with patch(
            "backend.services.layers.get_ml_risk_stats",
            return_value=stats,
        ):
            r = client.get("/api/v1/risk/ml/stats", params=_BBOX)
        assert r.status_code == 200
        assert r.json()["total_cells"] == 200

    def test_ml_risk_stats_empty(self, client: TestClient):
        with patch(
            "backend.services.layers.get_ml_risk_stats",
            return_value=None,
        ):
            r = client.get("/api/v1/risk/ml/stats", params=_BBOX)
        assert r.status_code == 404

    def test_ml_risk_detail(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "season": "winter",
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "risk_score": 0.78,
            "risk_category": "high",
            "whale_traffic_interaction_score": 0.8,
            "traffic_score": 0.7,
            "whale_ml_exposure_score": 0.6,
            "proximity_score": 0.5,
            "strike_score": 0.0,
            "protection_gap": 0.3,
            "reference_risk_score": 0.4,
            "any_whale_prob": 0.65,
            "max_whale_prob": 0.45,
            "mean_whale_prob": 0.24,
            "isdm_blue_whale": 0.12,
            "isdm_fin_whale": 0.35,
            "isdm_humpback_whale": 0.45,
            "isdm_sperm_whale": 0.02,
        }
        with patch(
            "backend.services.layers.get_ml_risk_detail",
            return_value=row,
        ):
            r = client.get(
                f"/api/v1/risk/ml/{row['h3_cell']}",
                params={"season": "winter"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["scores"]["whale_traffic_interaction"] == 0.8
        assert body["any_whale_prob"] == 0.65

    def test_ml_risk_detail_not_found(self, client: TestClient):
        with patch(
            "backend.services.layers.get_ml_risk_detail",
            return_value=None,
        ):
            r = client.get("/api/v1/risk/ml/999")
        assert r.status_code == 404

    def test_invalid_season_ml(self, client: TestClient):
        params = {**_BBOX, "season": "autumn"}
        r = client.get("/api/v1/risk/ml", params=params)
        assert r.status_code == 400


# ── Risk breakdown ──────────────────────────────────────────


class TestRiskBreakdown:
    def test_breakdown_found(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "risk_score": 0.85,
            "risk_category": "critical",
            "traffic_score": 0.9,
            "pctl_vessels": 0.88,
            "pctl_speed_lethality": 0.92,
            "pctl_large_vessels": 0.85,
            "pctl_draft_risk": 0.7,
            "pctl_high_speed_fraction": 0.6,
            "pctl_draft_risk_fraction": 0.5,
            "pctl_commercial": 0.8,
            "pctl_night_traffic": 0.4,
            "cetacean_score": 0.7,
            "total_sightings": 25,
            "unique_species": 3,
            "proximity_score": 0.6,
            "dist_to_nearest_whale_km": 5.2,
            "dist_to_nearest_ship_km": 1.1,
            "strike_score": 0.0,
            "total_strikes": 0,
            "habitat_score": 0.5,
            "depth_m": -120.0,
            "depth_zone": "shelf",
            "sst": 18.5,
            "pp_upper_200m": 0.45,
            "protection_gap": 0.3,
            "mpa_count": 1,
            "in_speed_zone": True,
            "reference_risk_score": 0.4,
            "nisi_all_risk": 0.6,
        }
        with patch(
            "backend.services.layers.get_risk_breakdown",
            return_value=row,
        ):
            r = client.get(f"/api/v1/risk/breakdown/{row['h3_cell']}")
        assert r.status_code == 200
        body = r.json()
        assert body["risk_score"] == 0.85
        assert body["traffic"]["pctl_vessels"] == 0.88
        assert body["depth_m"] == -120.0
        assert body["in_speed_zone"] is True

    def test_breakdown_not_found(self, client: TestClient):
        with patch(
            "backend.services.layers.get_risk_breakdown",
            return_value=None,
        ):
            r = client.get("/api/v1/risk/breakdown/999")
        assert r.status_code == 404


# ── Risk compare ────────────────────────────────────────────


class TestRiskCompare:
    def test_compare(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "standard_risk_score": 0.65,
            "standard_risk_category": "medium",
            "ml_risk_score": 0.78,
            "ml_risk_category": "high",
            "score_difference": 0.13,
        }
        with (
            patch(
                "backend.services.layers.count_risk_compare",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_risk_compare",
                return_value=[row],
            ),
        ):
            r = client.get("/api/v1/risk/compare", params=_BBOX)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["data"][0]["score_difference"] == 0.13

    def test_compare_bbox_validation(self, client: TestClient):
        params = {
            "lat_min": 42.0,
            "lat_max": 40.0,
            "lon_min": -74.0,
            "lon_max": -72.0,
        }
        r = client.get("/api/v1/risk/compare", params=params)
        assert r.status_code == 400


# ── Seasonal species ────────────────────────────────────────


class TestSeasonalSpecies:
    def test_list_seasonal(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "season": "winter",
            "total_sightings": 12,
            "unique_species": 2,
            "baleen_sightings": 10,
            "recent_sightings": 5,
            "right_whale_sightings": 8,
            "humpback_sightings": 2,
            "fin_whale_sightings": 0,
            "blue_whale_sightings": 0,
            "sperm_whale_sightings": 0,
            "minke_whale_sightings": 0,
        }
        with (
            patch(
                "backend.services.layers.count_seasonal_species",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_seasonal_species",
                return_value=[row],
            ),
        ):
            params = {**_BBOX, "season": "winter"}
            r = client.get("/api/v1/species/seasonal", params=params)
        assert r.status_code == 200
        body = r.json()
        assert body["data"][0]["season"] == "winter"
        assert body["data"][0]["right_whale_sightings"] == 8

    def test_invalid_season(self, client: TestClient):
        params = {**_BBOX, "season": "autumn"}
        r = client.get("/api/v1/species/seasonal", params=params)
        assert r.status_code == 400

    def test_min_sightings_filter(self, client: TestClient):
        with (
            patch(
                "backend.services.layers.count_seasonal_species",
                return_value=0,
            ),
            patch(
                "backend.services.layers.get_seasonal_species",
                return_value=[],
            ),
        ):
            params = {**_BBOX, "min_sightings": 5}
            r = client.get("/api/v1/species/seasonal", params=params)
        assert r.status_code == 200


# ── Seasonal traffic ────────────────────────────────────────


class TestSeasonalTraffic:
    def test_list_seasonal(self, client: TestClient):
        row = {
            "h3_cell": 607252735839895551,
            "cell_lat": 40.5,
            "cell_lon": -73.2,
            "season": "summer",
            "total_months": 18,
            "total_pings": 50000,
            "avg_monthly_vessels": 42.5,
            "avg_speed_knots": 12.3,
            "avg_high_speed_fraction": 0.15,
            "avg_draft_risk_fraction": 0.08,
            "avg_large_vessels": 10.0,
            "avg_commercial_vessels": 15.0,
            "avg_fishing_vessels": 8.0,
            "avg_night_fraction": 0.3,
        }
        with (
            patch(
                "backend.services.layers.count_seasonal_traffic",
                return_value=1,
            ),
            patch(
                "backend.services.layers.get_seasonal_traffic",
                return_value=[row],
            ),
        ):
            params = {**_BBOX, "season": "summer"}
            r = client.get("/api/v1/traffic/seasonal", params=params)
        assert r.status_code == 200
        body = r.json()
        assert body["data"][0]["season"] == "summer"
        assert body["data"][0]["avg_monthly_vessels"] == 42.5

    def test_invalid_season(self, client: TestClient):
        params = {**_BBOX, "season": "autumn"}
        r = client.get("/api/v1/traffic/seasonal", params=params)
        assert r.status_code == 400

    def test_bbox_validation(self, client: TestClient):
        params = {
            "lat_min": 42.0,
            "lat_max": 40.0,
            "lon_min": -74.0,
            "lon_max": -72.0,
        }
        r = client.get("/api/v1/traffic/seasonal", params=params)
        assert r.status_code == 400


# ── Sighting report endpoint ───────────────────────────────

_MOCK_PHOTO_RESULT = {
    "predicted_species": "humpback_whale",
    "confidence": 0.92,
    "probabilities": {"humpback_whale": 0.92, "fin_whale": 0.05},
    "gps_source": "user",
    "risk_context": {
        "h3_cell": 607252735839895551,
        "cell_lat": 40.5,
        "cell_lon": -73.2,
        "risk_score": 0.72,
        "risk_category": "high",
    },
}

_MOCK_AUDIO_RESULT = {
    "file": "upload.wav",
    "lat": 40.5,
    "lon": -73.2,
    "h3_cell": 607252735839895551,
    "dominant_species": "humpback_whale",
    "n_segments": 2,
    "segments": [
        {
            "segment_idx": 0,
            "start_sec": 0.0,
            "end_sec": 4.0,
            "predicted_species": "humpback_whale",
            "confidence": 0.88,
            "probabilities": {"humpback_whale": 0.88},
        },
        {
            "segment_idx": 1,
            "start_sec": 2.0,
            "end_sec": 6.0,
            "predicted_species": "humpback_whale",
            "confidence": 0.91,
            "probabilities": {"humpback_whale": 0.91},
        },
    ],
    "risk_context": {
        "risk_score": 0.72,
        "traffic_score": 0.6,
        "cetacean_score": 0.8,
    },
}

_MOCK_RISK_DATA = {
    "h3_cell": 607252735839895551,
    "risk_score": 0.72,
    "risk_category": "high",
    "traffic_score": 0.6,
    "cetacean_score": 0.8,
    "proximity_score": 0.5,
    "strike_score": 0.0,
    "habitat_score": 0.4,
    "protection_gap": 0.3,
    "reference_risk_score": 0.2,
}


class TestSightingReport:
    """Tests for POST /api/v1/sightings/report."""

    def test_photo_only(self, client: TestClient):
        """Submit image + species guess, no audio."""
        with (
            patch(
                "backend.services.sightings.photo_svc.classify_photo",
                return_value=_MOCK_PHOTO_RESULT,
            ),
            patch(
                "backend.services.sightings.get_cell_risk",
                return_value=_MOCK_RISK_DATA,
            ),
        ):
            r = client.post(
                "/api/v1/sightings/report",
                data={
                    "species_guess": "humpback_whale",
                    "description": "Large whale breaching",
                    "interaction_type": "passive_observation",
                    "lat": "40.5",
                    "lon": "-73.2",
                },
                files={
                    "image": ("whale.jpg", b"fake-image", "image/jpeg"),
                },
            )
        assert r.status_code == 200
        body = r.json()

        assert body["user_input"]["species_guess"] == "humpback_whale"
        assert body["user_input"]["description"] == "Large whale breaching"
        assert body["photo_classification"]["predicted_species"] == "humpback_whale"
        assert body["photo_classification"]["confidence"] == 0.92
        assert body["audio_classification"] is None
        assert body["species_assessment"]["source"] == "photo"
        assert body["species_assessment"]["user_agrees"] is True
        assert body["risk_summary"]["risk_score"] == 0.72
        assert body["advisory"]["level"] in (
            "high",
            "critical",
            "moderate",
        )
        assert body["location"]["h3_cell"] is not None
        assert "sighting_id" in body
        assert "timestamp" in body

    def test_audio_only(self, client: TestClient):
        """Submit audio + lat/lon, no image."""
        with (
            patch(
                "backend.services.sightings.audio_svc.classify_audio",
                return_value=_MOCK_AUDIO_RESULT,
            ),
            patch(
                "backend.services.sightings.get_cell_risk",
                return_value=_MOCK_RISK_DATA,
            ),
        ):
            r = client.post(
                "/api/v1/sightings/report",
                data={
                    "lat": "40.5",
                    "lon": "-73.2",
                    "interaction_type": "acoustic_detection",
                },
                files={
                    "audio": ("rec.wav", b"fake-audio", "audio/wav"),
                },
            )
        assert r.status_code == 200
        body = r.json()

        assert body["photo_classification"] is None
        assert body["audio_classification"]["dominant_species"] == "humpback_whale"
        assert body["audio_classification"]["n_segments"] == 2
        assert body["species_assessment"]["source"] == "audio"
        assert body["risk_summary"] is not None

    def test_photo_and_audio(self, client: TestClient):
        """Submit both image and audio."""
        with (
            patch(
                "backend.services.sightings.photo_svc.classify_photo",
                return_value=_MOCK_PHOTO_RESULT,
            ),
            patch(
                "backend.services.sightings.audio_svc.classify_audio",
                return_value=_MOCK_AUDIO_RESULT,
            ),
            patch(
                "backend.services.sightings.get_cell_risk",
                return_value=_MOCK_RISK_DATA,
            ),
        ):
            r = client.post(
                "/api/v1/sightings/report",
                data={
                    "species_guess": "fin_whale",
                    "lat": "40.5",
                    "lon": "-73.2",
                },
                files={
                    "image": ("whale.jpg", b"fake-image", "image/jpeg"),
                    "audio": ("rec.wav", b"fake-audio", "audio/wav"),
                },
            )
        assert r.status_code == 200
        body = r.json()

        assert body["photo_classification"] is not None
        assert body["audio_classification"] is not None
        # Both models agree on humpback, user guessed fin
        assert body["species_assessment"]["source"] == "photo+audio"
        assert body["species_assessment"]["user_agrees"] is False

    def test_species_guess_only(self, client: TestClient):
        """No media — just a species guess + location."""
        with patch(
            "backend.services.sightings.get_cell_risk",
            return_value=_MOCK_RISK_DATA,
        ):
            r = client.post(
                "/api/v1/sightings/report",
                data={
                    "species_guess": "right_whale",
                    "interaction_type": "near_miss",
                    "lat": "40.5",
                    "lon": "-73.2",
                },
            )
        assert r.status_code == 200
        body = r.json()

        assert body["photo_classification"] is None
        assert body["audio_classification"] is None
        assert body["species_assessment"]["source"] == "user_only"
        assert body["species_assessment"]["model_confidence"] == 0.0
        # Near-miss escalates to critical
        assert body["advisory"]["level"] == "critical"
        assert "Near-miss" in body["advisory"]["message"]

    def test_strike_advisory(self, client: TestClient):
        """Strike interaction triggers NOAA notification advisory."""
        with (
            patch(
                "backend.services.sightings.photo_svc.classify_photo",
                return_value=_MOCK_PHOTO_RESULT,
            ),
            patch(
                "backend.services.sightings.get_cell_risk",
                return_value=_MOCK_RISK_DATA,
            ),
        ):
            r = client.post(
                "/api/v1/sightings/report",
                data={
                    "interaction_type": "strike",
                    "lat": "40.5",
                    "lon": "-73.2",
                },
                files={
                    "image": ("whale.jpg", b"fake-image", "image/jpeg"),
                },
            )
        assert r.status_code == 200
        body = r.json()

        assert body["advisory"]["level"] == "critical"
        assert "NOAA" in body["advisory"]["message"]
        assert "1-866-755-6622" in body["advisory"]["message"]

    def test_no_input_returns_400(self, client: TestClient):
        """Must provide at least image, audio, or species_guess."""
        r = client.post("/api/v1/sightings/report", data={})
        assert r.status_code == 400

    def test_audio_without_coords_returns_400(self, client: TestClient):
        """Audio requires lat/lon (no EXIF in audio files)."""
        r = client.post(
            "/api/v1/sightings/report",
            data={},
            files={
                "audio": ("rec.wav", b"fake-audio", "audio/wav"),
            },
        )
        assert r.status_code == 400

    def test_invalid_interaction_type(self, client: TestClient):
        """Reject unknown interaction types."""
        r = client.post(
            "/api/v1/sightings/report",
            data={
                "species_guess": "humpback_whale",
                "interaction_type": "collision",
            },
        )
        assert r.status_code == 400

    def test_unsupported_image_type(self, client: TestClient):
        """Reject non-image MIME types."""
        r = client.post(
            "/api/v1/sightings/report",
            data={"lat": "40.5", "lon": "-73.2"},
            files={
                "image": ("doc.pdf", b"fake", "application/pdf"),
            },
        )
        assert r.status_code == 415

    def test_no_location_no_risk(self, client: TestClient):
        """Without coords, risk summary should be null."""
        with patch(
            "backend.services.sightings.photo_svc.classify_photo",
            return_value={
                "predicted_species": "humpback_whale",
                "confidence": 0.85,
                "probabilities": {"humpback_whale": 0.85},
                "gps_source": None,
            },
        ):
            r = client.post(
                "/api/v1/sightings/report",
                data={},
                files={
                    "image": ("whale.jpg", b"fake-image", "image/jpeg"),
                },
            )
        assert r.status_code == 200
        body = r.json()

        assert body["risk_summary"] is None
        assert body["location"] is None
        assert body["photo_classification"] is not None
        # Advisory still generated (low risk default)
        assert body["advisory"] is not None

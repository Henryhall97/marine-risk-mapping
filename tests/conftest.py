"""Shared fixtures for the marine risk mapping test suite."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# ── Database fixtures ───────────────────────────────────────


@pytest.fixture()
def mock_db_connection():
    """Provide a mock psycopg2 connection + cursor.

    The context-manager protocol is wired up so that code using
    ``with get_db_connection() as conn:`` works without a real DB.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


@pytest.fixture()
def patch_db_connection(mock_db_connection):
    """Patch ``pipeline.utils.get_db_connection`` to return the mock."""
    mock_conn, _ = mock_db_connection
    with patch(
        "pipeline.utils.psycopg2.connect",
        return_value=mock_conn,
    ):
        yield mock_db_connection


# ── Sample data fixtures ────────────────────────────────────


@pytest.fixture()
def sample_sightings_df():
    """Minimal cetacean sightings DataFrame for schema testing."""
    return pd.DataFrame(
        {
            "scientificName": [
                "Balaenoptera musculus",
                "Megaptera novaeangliae",
            ],
            "decimalLatitude": [35.5, 42.1],
            "decimalLongitude": [-72.3, -68.9],
            "eventDate": ["2023-06-15", "2024-01-20"],
            "date_year": [2023.0, 2024.0],
            "order": ["Cetacea", "Cetacea"],
            "family": ["Balaenopteridae", "Balaenopteridae"],
            "species": ["Blue Whale", "Humpback Whale"],
        }
    )


@pytest.fixture()
def sample_binary_predictions():
    """Synthetic binary classification arrays for metric tests."""
    rng = np.random.default_rng(42)
    n = 200
    y_true = rng.integers(0, 2, size=n)
    y_prob = np.clip(
        y_true * 0.7 + rng.normal(0, 0.2, n),
        0.01,
        0.99,
    )
    return y_true, y_prob


@pytest.fixture()
def sample_h3_df():
    """DataFrame with H3 cells for spatial block testing."""
    import h3

    # 50 random US coastal points → H3 cells
    rng = np.random.default_rng(123)
    lats = rng.uniform(25.0, 48.0, size=50)
    lons = rng.uniform(-128.0, -67.0, size=50)
    cells = [
        int(h3.latlng_to_cell(lat, lon, 7), 16)
        for lat, lon in zip(lats, lons, strict=True)
    ]
    return pd.DataFrame({"h3_cell": cells, "value": rng.random(50)})


@pytest.fixture()
def sine_waveform():
    """1-second 440 Hz sine wave at 16 kHz sample rate."""
    sr = 16_000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    return np.sin(2 * np.pi * 440 * t).astype(np.float32), sr

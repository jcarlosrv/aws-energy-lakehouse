import pandas as pd
import pytest

import weather


def test_frame_parses_the_hourly_block():
    payload = {
        "hourly": {
            "time": ["2026-01-01T00:00", "2026-01-01T01:00"],
            "temperature_2m": [3.1, 2.8],
            "relative_humidity_2m": [90, 91],
            "wind_speed_10m": [12.0, 11.0],
            "direct_radiation": [0.0, 0.0],
        }
    }
    frame = weather._frame(payload)
    assert list(frame["timestamp"]) == [
        pd.Timestamp("2026-01-01 00:00"),
        pd.Timestamp("2026-01-01 01:00"),
    ]
    assert frame["temperature_2m"].tolist() == [3.1, 2.8]


def test_missing_hourly_block_raises():
    with pytest.raises(weather.WeatherError, match="no hourly block"):
        weather._frame({"error": True})

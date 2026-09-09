import numpy as np
import pandas as pd
import pytest

import forecast_handler
import config
import features
import weather

def test_past_weather_days_covers_the_week_ago_delta_for_a_stale_anchor():
    hours = forecast_handler.PAST_WEATHER_DAYS * 24
    assert hours >= features.ROLL_OFFSET_HOURS + config.MAX_STALENESS_HOURS


def test_the_handler_actually_requests_that_much_past_weather(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured.update(params)
        raise weather.requests.RequestException("stop before the network")

    monkeypatch.setattr(weather.requests, "get", fake_get)
    with pytest.raises(weather.WeatherError):
        weather.forecast("DE", past_days=forecast_handler.PAST_WEATHER_DAYS)
    assert captured["past_days"] * 24 >= 168 + config.MAX_STALENESS_HOURS

def _history(codes=("DE", "FR"), hours=2000, end="2026-03-01 00:00"):
    frames = []
    last = pd.Timestamp(end)
    stamps = pd.date_range(last - pd.Timedelta(hours=hours - 1), periods=hours, freq="h")
    for code in codes:
        frames.append(
            pd.DataFrame(
                {
                    "country": code,
                    "timestamp": stamps,
                    "load_mw": np.arange(hours, dtype=float),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_fresh_countries_are_kept():
    history = _history()
    now = pd.Timestamp("2026-03-01 06:00")
    fresh, skipped = forecast_handler.select_fresh(history, now)
    assert set(fresh) == {"DE", "FR"}
    assert skipped == {}


def test_a_single_stale_country_is_skipped_not_raised():
    history = _history(codes=("DE",))
    stale = _history(codes=("FR",), end="2026-02-01 00:00")
    fresh, skipped = forecast_handler.select_fresh(
        pd.concat([history, stale]), pd.Timestamp("2026-03-01 06:00")
    )
    assert set(fresh) == {"DE"}
    assert skipped["FR"]["status"] == "stale"


def test_anchor_ignores_stale_countries():
    history = _history(codes=("DE",))
    stale = _history(codes=("FR",), end="2026-02-01 00:00")
    fresh, _ = forecast_handler.select_fresh(
        pd.concat([history, stale]), pd.Timestamp("2026-03-01 06:00")
    )
    assert forecast_handler.anchor_of(fresh) == pd.Timestamp("2026-03-01 00:00")


def test_all_stale_raises():
    history = _history(end="2026-01-01 00:00")
    with pytest.raises(RuntimeError, match="no country"):
        forecast_handler.require_any(
            *forecast_handler.select_fresh(history, pd.Timestamp("2026-03-01 06:00"))
        )


def test_trailing_months_covers_the_current_and_previous_month():
    months = forecast_handler.trailing_months(pd.Timestamp("2026-03-04 07:00"))
    assert months == [(2026, 2), (2026, 3)]


def test_nl_is_excluded_from_the_history_query(monkeypatch):
    captured = {}

    def fake_run_query(sql):
        captured["sql"] = sql
        return pd.DataFrame({"country": [], "timestamp": [], "load_mw": []})

    monkeypatch.setattr(forecast_handler, "run_query", fake_run_query)
    forecast_handler.load_history(pd.Timestamp("2026-03-04 07:00"))
    assert "country <> 'NL'" in captured["sql"]


def _history_with_gap(gap_day, hours=2000, end="2026-03-01 00:00"):
    last = pd.Timestamp(end)
    stamps = pd.date_range(last - pd.Timedelta(hours=hours - 1), periods=hours, freq="h")
    frame = pd.DataFrame(
        {
            "country": "FR",
            "timestamp": stamps,
            "load_mw": np.arange(hours, dtype=float) + 1000.0,
        }
    )
    gap = pd.Timestamp(gap_day)
    return frame[
        (frame["timestamp"] < gap) | (frame["timestamp"] >= gap + pd.Timedelta(days=1))
    ]


def _flat_weather(targets):
    index = pd.date_range(targets.min() - pd.Timedelta(hours=336), targets.max(), freq="h")
    return pd.DataFrame(
        {
            "timestamp": index,
            "temperature_2m": 10.0,
            "relative_humidity_2m": 50.0,
            "wind_speed_10m": 5.0,
            "direct_radiation": 100.0,
        }
    )


def _built(gap_day):
    anchor = pd.Timestamp("2026-03-01 00:00")
    targets = pd.date_range(anchor + pd.Timedelta(hours=1), periods=168, freq="h")
    history = _history_with_gap(gap_day)
    return features.build_features(
        features.clean_load(history), targets, "FR", _flat_weather(targets)
    )


def test_a_gap_outside_the_seasonal_base_still_forecasts():
    # Feb 18 lands in the lag_336h window (Feb 15 01:00 - Feb 22 00:00)
    usable, degraded = forecast_handler.usability(_built("2026-02-18"))
    assert usable
    assert "load_lag_336h" in degraded


def test_a_gap_in_the_seasonal_base_is_still_skipped():
    # Feb 25 lands in the lag_168h window (Feb 22 01:00 - Mar 1 00:00)
    usable, degraded = forecast_handler.usability(_built("2026-02-25"))
    assert not usable
    assert degraded["load_lag_168h"] == 24

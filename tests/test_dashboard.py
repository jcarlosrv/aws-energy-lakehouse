import pandas as pd

import dashboard


def test_actuals_are_joined_to_earlier_forecasts_on_timestamp():
    stamps = pd.date_range("2026-03-01", periods=3, freq="h")
    actuals = pd.DataFrame({"country": "DE", "timestamp": stamps, "load_mw": [10.0, 11.0, 12.0]})
    forecasts = pd.DataFrame({"country": "DE", "timestamp": stamps, "predicted_mw": [9.0, 11.5, 13.0]})
    payload = dashboard.build_payload(actuals, forecasts, {"mae": 1.0}, pd.Timestamp("2026-03-01 02:00"))
    compared = payload["countries"]["DE"]["compared"]
    assert len(compared) == 3
    assert compared[0] == {"timestamp": "2026-03-01T00:00:00", "actual_mw": 10.0, "predicted_mw": 9.0}


def test_forecast_hours_without_actuals_are_not_compared():
    stamps = pd.date_range("2026-03-01", periods=3, freq="h")
    actuals = pd.DataFrame({"country": "DE", "timestamp": stamps[:1], "load_mw": [10.0]})
    forecasts = pd.DataFrame({"country": "DE", "timestamp": stamps, "predicted_mw": [9.0, 11.5, 13.0]})
    payload = dashboard.build_payload(actuals, forecasts, {}, pd.Timestamp("2026-03-01 02:00"))
    assert len(payload["countries"]["DE"]["compared"]) == 1
    assert len(payload["countries"]["DE"]["forecast"]) == 3

def test_recent_carries_the_trailing_actuals_for_each_country():
    stamps = pd.date_range("2026-03-01", periods=5, freq="h")
    actuals = pd.DataFrame(
        {"country": "DE", "timestamp": stamps, "load_mw": [10.0, 11.0, 12.0, 13.0, 14.0]}
    )
    forecasts = pd.DataFrame(
        {"country": "DE", "timestamp": stamps, "predicted_mw": [9.0] * 5}
    )
    payload = dashboard.build_payload(
        actuals, forecasts, {}, pd.Timestamp("2026-03-01 04:00"), recent_hours=3
    )
    recent = payload["countries"]["DE"]["recent"]
    assert len(recent) == 3
    assert recent[0] == {"timestamp": "2026-03-01T02:00:00", "actual_mw": 12.0}
    assert recent[-1] == {"timestamp": "2026-03-01T04:00:00", "actual_mw": 14.0}


def test_recent_is_empty_when_a_country_has_no_actuals():
    stamps = pd.date_range("2026-03-01", periods=3, freq="h")
    actuals = pd.DataFrame({"country": "DE", "timestamp": stamps, "load_mw": [10.0, 11.0, 12.0]})
    forecasts = pd.DataFrame({"country": "ES", "timestamp": stamps, "predicted_mw": [9.0] * 3})
    payload = dashboard.build_payload(actuals, forecasts, {}, pd.Timestamp("2026-03-01 02:00"))
    assert payload["countries"]["ES"]["recent"] == []

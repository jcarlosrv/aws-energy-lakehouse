import numpy as np
import pandas as pd
import pytest

import features


def _history(start="2025-11-01", hours=2000):
    """load_mw equals the row's position, so lag assertions are exact."""
    stamps = pd.date_range(start, periods=hours, freq="h")
    return pd.DataFrame({"timestamp": stamps, "load_mw": np.arange(hours, dtype=float)})


def _targets_after(history, count=3):
    last = history["timestamp"].iloc[-1]
    return pd.date_range(last + pd.Timedelta(hours=1), periods=count, freq="h")

def _weather(start="2025-11-01", hours=2200):
    stamps = pd.date_range(start, periods=hours, freq="h")
    return pd.DataFrame(
        {
            "timestamp": stamps,
            "temperature_2m": np.linspace(0.0, 20.0, hours),
            "relative_humidity_2m": np.full(hours, 80.0),
            "wind_speed_10m": np.full(hours, 10.0),
            "direct_radiation": np.zeros(hours),
        }
    )


def test_column_order_is_exactly_feature_columns():
    history = _history()
    frame = features.build_features(history, _targets_after(history), "DE",_weather())
    assert list(frame.columns) == features.FEATURE_COLUMNS


def test_lags_resolve_to_the_correct_earlier_hour():
    history = _history(hours=2000)
    targets = _targets_after(history, count=1)
    frame = features.build_features(history, targets, "DE",_weather())
    # target sits at position 2000; lag 168 is position 1832, and load_mw == position
    assert frame["load_lag_168h"].iloc[0] == 2000 - 168
    assert frame["load_lag_336h"].iloc[0] == 2000 - 336
    assert frame["load_lag_504h"].iloc[0] == 2000 - 504


def test_rolling_window_ends_at_t_minus_168h_not_at_t():
    history = _history(hours=2000)
    targets = _targets_after(history, count=1)
    frame = features.build_features(history, targets, "DE",_weather())
    # window covers positions 1665..1832 inclusive; mean of an arithmetic run
    assert frame["load_roll_mean_168h"].iloc[0] == pytest.approx((1665 + 1832) / 2)


@pytest.mark.parametrize("country", ["DE", "FR", "ES", "IT", "PL"])
def test_new_years_day_is_a_holiday_in_every_country(country):
    history = _history(start="2025-11-01", hours=2000)
    targets = pd.DatetimeIndex(["2026-01-01 12:00", "2026-01-05 12:00"])
    frame = features.build_features(history, targets, country,_weather())
    assert frame["is_holiday"].tolist() == [1, 0]


def test_weekend_flag_matches_day_of_week():
    history = _history(hours=2000)
    targets = pd.DatetimeIndex(["2026-01-03 00:00", "2026-01-05 00:00"])  # Sat, Mon
    frame = features.build_features(history, targets, "DE",_weather())
    assert frame["is_weekend"].tolist() == [1, 0]


def test_insufficient_history_yields_nan_rather_than_raising():
    history = _history(hours=100)
    targets = _targets_after(history, count=1)
    frame = features.build_features(history, targets, "DE",_weather())
    assert frame[features.LAG_COLUMNS].isna().any().any()

def _load_series(values):
    stamps = pd.date_range("2026-01-01", periods=len(values), freq="h")
    return pd.DataFrame({"timestamp": stamps, "load_mw": [float(v) for v in values]})

def test_clean_load_bridges_an_isolated_bad_reading():
    frame = features.clean_load(_load_series([40000, 41000, 0, 43000, 44000]))
    assert frame["load_mw"].iloc[2] == pytest.approx(42000.0)


def test_clean_load_leaves_a_long_outage_as_nan():
    frame = features.clean_load(_load_series([40000] + [0] * 6 + [45000]))
    assert frame["load_mw"].isna().any()


def test_clean_load_leaves_plausible_values_untouched():
    frame = features.clean_load(_load_series([40000, 41000, 42000]))
    assert frame["load_mw"].tolist() == [40000.0, 41000.0, 42000.0]

def test_temp_delta_is_this_hour_minus_the_same_hour_last_week():
    history = _history(hours=2000)
    targets = _targets_after(history, count=1)
    observed = _weather(hours=2200)
    frame = features.build_features(history, targets, "DE", observed)
    series = observed.set_index("timestamp")["temperature_2m"]
    target = targets[0]
    expected = series.loc[target] - series.loc[target - pd.Timedelta(hours=168)]
    assert frame["temp_delta_168h"].iloc[0] == pytest.approx(expected)
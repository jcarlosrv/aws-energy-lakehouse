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


def test_column_order_is_exactly_feature_columns():
    history = _history()
    frame = features.build_features(history, _targets_after(history), "DE")
    assert list(frame.columns) == features.FEATURE_COLUMNS


def test_lags_resolve_to_the_correct_earlier_hour():
    history = _history(hours=2000)
    targets = _targets_after(history, count=1)
    frame = features.build_features(history, targets, "DE")
    # target sits at position 2000; lag 168 is position 1832, and load_mw == position
    assert frame["load_lag_168h"].iloc[0] == 2000 - 168
    assert frame["load_lag_336h"].iloc[0] == 2000 - 336
    assert frame["load_lag_504h"].iloc[0] == 2000 - 504


def test_rolling_window_ends_at_t_minus_168h_not_at_t():
    history = _history(hours=2000)
    targets = _targets_after(history, count=1)
    frame = features.build_features(history, targets, "DE")
    # window covers positions 1665..1832 inclusive; mean of an arithmetic run
    assert frame["load_roll_mean_168h"].iloc[0] == pytest.approx((1665 + 1832) / 2)


@pytest.mark.parametrize("country", ["DE", "FR", "ES", "IT", "PL", "NL"])
def test_new_years_day_is_a_holiday_in_every_country(country):
    history = _history(start="2025-11-01", hours=2000)
    targets = pd.DatetimeIndex(["2026-01-01 12:00", "2026-01-05 12:00"])
    frame = features.build_features(history, targets, country)
    assert frame["is_holiday"].tolist() == [1, 0]


def test_weekend_flag_matches_day_of_week():
    history = _history(hours=2000)
    targets = pd.DatetimeIndex(["2026-01-03 00:00", "2026-01-05 00:00"])  # Sat, Mon
    frame = features.build_features(history, targets, "DE")
    assert frame["is_weekend"].tolist() == [1, 0]


def test_insufficient_history_yields_nan_rather_than_raising():
    history = _history(hours=100)
    targets = _targets_after(history, count=1)
    frame = features.build_features(history, targets, "DE")
    assert frame[features.LAG_COLUMNS].isna().any().any()
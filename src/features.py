import holidays
import pandas as pd

LAG_HOURS = (168, 336, 504)
ROLL_WINDOW_HOURS = 168
ROLL_OFFSET_HOURS = 168
MIN_HISTORY_HOURS = 504
MIN_PLAUSIBLE_LOAD_MW = 500.0
INTERPOLATE_LIMIT_HOURS = 3

COUNTRY_CODES = ("DE", "FR", "ES", "IT", "PL", "NL")

LAG_COLUMNS = [f"load_lag_{lag}h" for lag in LAG_HOURS]

FEATURE_COLUMNS = [
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "is_holiday",
    *LAG_COLUMNS,
    "load_roll_mean_168h",
    "load_roll_std_168h",
    "country",
]

CATEGORICAL_COLUMNS = ["country"]

def clean_load(history):
    """Blank implausible readings and bridge short gaps."""
    cleaned = history.sort_values("timestamp").copy()
    cleaned.loc[cleaned["load_mw"] < MIN_PLAUSIBLE_LOAD_MW, "load_mw"] = float("nan")
    cleaned["load_mw"] = cleaned["load_mw"].interpolate(
        limit=INTERPOLATE_LIMIT_HOURS, limit_area="inside"
    )
    return cleaned

def build_features(history, targets, country):
    series = history.set_index("timestamp")["load_mw"].sort_index()
    rolling = series.rolling(ROLL_WINDOW_HOURS, min_periods=ROLL_WINDOW_HOURS)
    roll_mean = rolling.mean()
    roll_std = rolling.std()

    index = pd.DatetimeIndex(targets)
    frame = pd.DataFrame(index=index)

    frame["hour"] = index.hour
    frame["day_of_week"] = index.dayofweek
    frame["month"] = index.month
    frame["is_weekend"] = (index.dayofweek >= 5).astype(int)

    calendar = holidays.country_holidays(country, years=sorted(set(index.year)))
    frame["is_holiday"] = [int(stamp.date() in calendar) for stamp in index]

    for lag in LAG_HOURS:
        shifted = index - pd.Timedelta(hours=lag)
        frame[f"load_lag_{lag}h"] = series.reindex(shifted).to_numpy()

    offset = index - pd.Timedelta(hours=ROLL_OFFSET_HOURS)
    frame["load_roll_mean_168h"] = roll_mean.reindex(offset).to_numpy()
    frame["load_roll_std_168h"] = roll_std.reindex(offset).to_numpy()

    frame["country"] = pd.Categorical([country] * len(index), categories=COUNTRY_CODES)

    return frame[FEATURE_COLUMNS]
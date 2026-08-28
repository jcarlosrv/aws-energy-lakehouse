import io
import json
import math

import boto3
import pandas as pd

import features
import weather
from athena import run_query
from config import (
    ATHENA_TABLE,
    BUCKET,
    FORECAST_PREFIX,
    HISTORY_MONTHS,
    HORIZON_HOURS,
    MAX_STALENESS_HOURS,
    MODEL_KEY,
)

# the week-ago temperature delta looks back ROLL_OFFSET_HOURS from the first
# target, and the anchor may itself trail now by MAX_STALENESS_HOURS
PAST_WEATHER_DAYS = math.ceil(
    (features.ROLL_OFFSET_HOURS + MAX_STALENESS_HOURS) / 24
)

_s3 = None
_booster = None


def _s3_client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3")
    return _s3


def _model():
    global _booster
    if _booster is None:
        import lightgbm as lgb

        body = _s3_client().get_object(Bucket=BUCKET, Key=MODEL_KEY)["Body"].read()
        _booster = lgb.Booster(model_str=body.decode("utf-8"))
    return _booster


def trailing_months(now, count=HISTORY_MONTHS):
    period = pd.Period(now, freq="M")
    return [
        ((period - offset).year, (period - offset).month)
        for offset in reversed(range(count))
    ]


def load_history(now):
    clauses = " OR ".join(
        f"(year = {year} AND month = {month})" for year, month in trailing_months(now)
    )
    frame = run_query(
        f"SELECT country, timestamp, load_mw FROM {ATHENA_TABLE} "
        f"WHERE country <> 'NL' AND ({clauses})"
    )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    return frame.sort_values(["country", "timestamp"])


def select_fresh(history, now):
    fresh, skipped = {}, {}
    for country, group in history.groupby("country"):
        newest = group["timestamp"].max()
        age_hours = (now - newest) / pd.Timedelta(hours=1)
        if age_hours > MAX_STALENESS_HOURS:
            skipped[country] = {
                "status": "stale",
                "newest": newest.isoformat(),
                "age_hours": round(age_hours, 1),
            }
        else:
            fresh[country] = group
    return fresh, skipped


def require_any(fresh, skipped):
    if not fresh:
        raise RuntimeError(f"no country has fresh data: {json.dumps(skipped)}")
    return fresh, skipped


def anchor_of(fresh):
    return min(group["timestamp"].max() for group in fresh.values())


def _write_forecast(country, issued, frame):
    key = (
        f"{FORECAST_PREFIX}/country={country}"
        f"/issued={issued:%Y-%m-%dT%H}/predictions.parquet"
    )
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False, compression="snappy")
    _s3_client().put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())
    return key


def handler(event, context):
    event = event or {}
    now = (
        pd.Timestamp(event["now"])
        if event.get("now")
        else pd.Timestamp.now(tz="UTC").tz_localize(None).floor("h")
    )

    history = load_history(now)
    fresh, skipped = require_any(*select_fresh(history, now))
    issued = anchor_of(fresh)
    targets = pd.date_range(
        issued + pd.Timedelta(hours=1), periods=HORIZON_HOURS, freq="h"
    )

    booster = _model()
    written = {}
    for country, group in fresh.items():
        try:
            observed = weather.forecast(country, past_days=PAST_WEATHER_DAYS)
        except weather.WeatherError as exc:
            skipped[country] = {"status": "weather_unavailable", "detail": str(exc)}
            continue

        built = features.build_features(
            features.clean_load(group), targets, country, observed
        )
        if built[features.REQUIRED_COLUMNS].isna().any().any():
            skipped[country] = {"status": "insufficient_history"}
            continue

        # the model predicts the residual against seasonal naive, so add it back
        predictions = built["load_lag_168h"].to_numpy() + booster.predict(built)
        key = _write_forecast(
            country,
            issued,
            pd.DataFrame(
                {
                    "timestamp": targets,
                    "predicted_mw": predictions,
                    "temperature_2m": built["temperature_2m"].to_numpy(),
                }
            ),
        )
        written[country] = {"status": "ok", "hours": len(targets), "key": key}

    summary = {"issued": issued.isoformat(), "countries": written, "skipped": skipped}
    print(json.dumps(summary))

    if not written:
        raise RuntimeError(f"no country produced a forecast at {issued.isoformat()}")

    return summary
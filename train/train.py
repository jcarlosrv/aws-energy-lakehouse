import json
import sys
from pathlib import Path

import boto3
import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import features  # noqa: E402
import weather  # noqa: E402
from athena import run_query  # noqa: E402
from config import ATHENA_TABLE, BUCKET, METRICS_KEY, MODEL_KEY  # noqa: E402

TEST_WEEKS = 8
VALID_WEEKS = 4
MAX_ROUNDS = 3000
EARLY_STOPPING_ROUNDS = 50
MIN_IMPROVEMENT = 0.05
CACHE_DIR = Path(__file__).resolve().parents[1] / ".weather-cache"


def cached_weather(country, start, end):
    """Historical weather is immutable; fetch each window once."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{country}_{start:%Y%m%d}_{end:%Y%m%d}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    observed = weather.history(country, start, end)
    observed.to_parquet(path, index=False)
    return observed


def load_history():
    frame = run_query(
        f"SELECT country, timestamp, load_mw FROM {ATHENA_TABLE} WHERE country <> 'NL'"
    )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    return frame.sort_values(["country", "timestamp"])


def build_training_frame(history):
    parts = []
    for country, group in history.groupby("country", observed=True):
        group = features.clean_load(group)
        targets = pd.DatetimeIndex(group["timestamp"])
        observed = cached_weather(
            country,
            targets.min() - pd.Timedelta(days=7),
            targets.max(),
        )
        built = features.build_features(group, targets, country, observed)
        built["target"] = (
            group.set_index("timestamp")["load_mw"].reindex(targets).to_numpy()
        )
        parts.append(built)

    frame = pd.concat(parts).dropna(
        subset=features.LAG_COLUMNS + features.WEATHER_COLUMNS + ["target"]
    )
    frame["residual"] = frame["target"] - frame["load_lag_168h"]
    return frame.sort_index()


def split(frame):
    last = frame.index.max()
    test_from = last - pd.Timedelta(weeks=TEST_WEEKS)
    valid_from = test_from - pd.Timedelta(weeks=VALID_WEEKS)
    return (
        frame[frame.index <= valid_from],
        frame[(frame.index > valid_from) & (frame.index <= test_from)],
        frame[frame.index > test_from],
    )


def score(actual, predicted):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    error = actual - predicted
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error ** 2))),
        "mape": float(np.mean(np.abs(error / actual)) * 100),
    }


def main():
    frame = build_training_frame(load_history())
    train, valid, test = split(frame)
    print(f"train {len(train)}  valid {len(valid)}  test {len(test)}")

    dtrain = lgb.Dataset(
        train[features.FEATURE_COLUMNS],
        label=train["residual"],
        categorical_feature=features.CATEGORICAL_COLUMNS,
    )
    dvalid = lgb.Dataset(
        valid[features.FEATURE_COLUMNS],
        label=valid["residual"],
        categorical_feature=features.CATEGORICAL_COLUMNS,
        reference=dtrain,
    )

    model = lgb.train(
        {
            "objective": "regression",
            "metric": "l1",
            "learning_rate": 0.05,
            "verbosity": -1,
            "seed": 42,
        },
        dtrain,
        num_boost_round=MAX_ROUNDS,
        valid_sets=[dvalid],
        callbacks=[
            lgb.early_stopping(EARLY_STOPPING_ROUNDS),
            lgb.log_evaluation(100),
        ],
    )
    print(f"best iteration {model.best_iteration}")

    actual = test["target"].to_numpy()
    baseline = test["load_lag_168h"].to_numpy()
    predicted = baseline + model.predict(test[features.FEATURE_COLUMNS])

    metrics = {
        "model": score(actual, predicted),
        "seasonal_naive_168h": score(actual, baseline),
        "test_weeks": TEST_WEEKS,
        "valid_weeks": VALID_WEEKS,
        "best_iteration": int(model.best_iteration),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "per_country": {},
    }

    for country in features.COUNTRY_CODES:
        mask = (test["country"] == country).to_numpy()
        if not mask.any():
            continue
        metrics["per_country"][country] = {
            "model": score(actual[mask], predicted[mask]),
            "seasonal_naive_168h": score(actual[mask], baseline[mask]),
        }

    print(json.dumps(metrics, indent=2))

    improvement = 1 - metrics["model"]["mae"] / metrics["seasonal_naive_168h"]["mae"]
    rmse_improvement = 1 - metrics["model"]["rmse"] / metrics["seasonal_naive_168h"]["rmse"]
    per_country = {
        country: 1 - scores["model"]["mae"] / scores["seasonal_naive_168h"]["mae"]
        for country, scores in metrics["per_country"].items()
    }
    metrics["improvement"] = {
        "mae": improvement,
        "rmse": rmse_improvement,
        "per_country_mae": per_country,
    }
    print(f"MAE improvement over seasonal naive:  {improvement:.1%}")
    print(f"RMSE improvement over seasonal naive: {rmse_improvement:.1%}")

    failures = []
    if improvement < MIN_IMPROVEMENT:
        failures.append(f"pooled MAE improvement {improvement:.1%} below {MIN_IMPROVEMENT:.0%}")
    if rmse_improvement < 0:
        failures.append(f"pooled RMSE {-rmse_improvement:.1%} worse than the baseline")
    losers = {c: v for c, v in per_country.items() if v < 0}
    if losers:
        detail = ", ".join(f"{c} {v:+.1%}" for c, v in sorted(losers.items()))
        failures.append(f"worse than baseline per country: {detail}")

    if failures:
        print("GATE FAILED. Nothing uploaded.")
        for reason in failures:
            print(f"  - {reason}")
        return

    s3 = boto3.client("s3")
    s3.put_object(Bucket=BUCKET, Key=MODEL_KEY, Body=model.model_to_string().encode())
    s3.put_object(
        Bucket=BUCKET, Key=METRICS_KEY, Body=json.dumps(metrics, indent=2).encode()
    )
    print(f"uploaded s3://{BUCKET}/{MODEL_KEY}")


if __name__ == "__main__":
    main()
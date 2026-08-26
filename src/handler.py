import io
import json

import boto3
import pandas as pd
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError

from config import (
    BUCKET,
    COUNTRIES,
    CURATED_PREFIX,
    LOOKBACK_DAYS,
    PLAUSIBLE_LOAD_MAX,
    PLAUSIBLE_LOAD_MIN,
    RAW_PREFIX,
    SSM_TOKEN_PARAMETER,
    ZONE_OVERRIDE,
)

_s3 = None
_token = None


def _s3_client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3")
    return _s3


def _entsoe_token():
    global _token
    if _token is None:
        response = boto3.client("ssm").get_parameter(
            Name=SSM_TOKEN_PARAMETER, WithDecryption=True
        )
        _token = response["Parameter"]["Value"]
    return _token


def _resolve_window(event):
    start, end = event.get("start"), event.get("end")
    if start and end:
        return pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    now = pd.Timestamp.now(tz="UTC").normalize()
    return now - pd.Timedelta(days=LOOKBACK_DAYS), now


def _fetch_country(client, code, start, end):
    zone = ZONE_OVERRIDE.get(code, code)
    result = client.query_load(zone, start=start, end=end)
    return result.iloc[:, 0] if isinstance(result, pd.DataFrame) else result


def _to_hourly(series):
    hourly = series.resample("1h").mean()
    hourly.index = hourly.index.tz_convert("UTC").tz_localize(None)
    frame = pd.DataFrame(
        {"timestamp": hourly.index, "load_mw": hourly.values.astype("float64")}
    )
    return frame[frame["load_mw"].between(PLAUSIBLE_LOAD_MIN, PLAUSIBLE_LOAD_MAX)]


def _write_raw(code, series, start, end):
    frame = series.rename("load_mw").rename_axis("timestamp").reset_index()
    key = f"{RAW_PREFIX}/country={code}/{start:%Y%m%d}-{end:%Y%m%d}.csv"
    _s3_client().put_object(
        Bucket=BUCKET, Key=key, Body=frame.to_csv(index=False).encode("utf-8")
    )


def _merge_partition(code, year, month, incoming):
    key = f"{CURATED_PREFIX}/country={code}/year={year:04d}/month={month:02d}/data.parquet"
    client = _s3_client()

    try:
        body = client.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        incoming = pd.concat([pd.read_parquet(io.BytesIO(body)), incoming], ignore_index=True)
    except client.exceptions.NoSuchKey:
        pass

    merged = (
        incoming.drop_duplicates(subset="timestamp", keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    buffer = io.BytesIO()
    merged.to_parquet(buffer, index=False, compression="snappy")
    client.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())
    return len(merged)


def handler(event, context):
    start, end = _resolve_window(event or {})
    client = EntsoePandasClient(api_key=_entsoe_token())
    results = {}

    for code in COUNTRIES:
        try:
            series = _fetch_country(client, code, start, end)
        except NoMatchingDataError:
            results[code] = {"status": "no_data"}
            continue
        except Exception as exc:
            results[code] = {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}
            continue

        _write_raw(code, series, start, end)
        frame = _to_hourly(series)
        if frame.empty:
            results[code] = {"status": "empty"}
            continue

        keyed = frame.assign(
            year=frame["timestamp"].dt.year, month=frame["timestamp"].dt.month
        )
        partitions = {
            f"{year:04d}-{month:02d}": _merge_partition(
                code, year, month, group[["timestamp", "load_mw"]]
            )
            for (year, month), group in keyed.groupby(["year", "month"])
        }
        results[code] = {"status": "ok", "hours": len(frame), "partitions": partitions}

    summary = {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "countries": results,
    }
    print(json.dumps(summary))

    if not any(r["status"] == "ok" for r in results.values()):
        raise RuntimeError(f"no country produced data for {start.date()} -> {end.date()}")

    return summary
import pandas as pd

WINDOW_HOURS = 168


def _records(frame, columns):
    out = []
    for row in frame.itertuples(index=False):
        record = {"timestamp": pd.Timestamp(row.timestamp).isoformat()}
        for column in columns:
            record[column] = float(getattr(row, column))
        out.append(record)
    return out


def build_payload(actuals, forecasts, metrics, issued, window_hours=WINDOW_HOURS):
    issued = pd.Timestamp(issued)
    span = pd.Timedelta(hours=window_hours)
    countries = {}
    for country in sorted(set(forecasts["country"])):
        country_forecast = forecasts[
            (forecasts["country"] == country)
            & (forecasts["timestamp"] > issued - span)
            & (forecasts["timestamp"] <= issued + span)
        ].sort_values("timestamp")
        country_actual = actuals[
            (actuals["country"] == country)
            & (actuals["timestamp"] > issued - span)
            & (actuals["timestamp"] <= issued)
        ].sort_values("timestamp")
        merged = country_forecast.merge(
            country_actual[["timestamp", "load_mw"]], on="timestamp", how="inner"
        ).rename(columns={"load_mw": "actual_mw"})
        recent = country_actual.rename(columns={"load_mw": "actual_mw"})
        countries[country] = {
            "recent": _records(recent, ["actual_mw"]),
            "forecast": _records(country_forecast, ["predicted_mw"]),
            "compared": _records(merged, ["actual_mw", "predicted_mw"]),
        }
    return {
        "issued": issued.isoformat(),
        "metrics": metrics,
        "countries": countries,
    }
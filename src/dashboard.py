import pandas as pd


def _records(frame, columns):
    out = []
    for row in frame.itertuples(index=False):
        record = {"timestamp": pd.Timestamp(row.timestamp).isoformat()}
        for column in columns:
            record[column] = float(getattr(row, column))
        out.append(record)
    return out


def build_payload(actuals, forecasts, metrics, issued):
    countries = {}
    for country in sorted(set(forecasts["country"])):
        country_forecast = forecasts[forecasts["country"] == country]
        country_actual = actuals[actuals["country"] == country]
        merged = country_forecast.merge(
            country_actual[["timestamp", "load_mw"]], on="timestamp", how="inner"
        ).rename(columns={"load_mw": "actual_mw"})
        countries[country] = {
            "forecast": _records(country_forecast, ["predicted_mw"]),
            "compared": _records(merged, ["actual_mw", "predicted_mw"]),
        }
    return {
        "issued": pd.Timestamp(issued).isoformat(),
        "metrics": metrics,
        "countries": countries,
    }
import pandas as pd
import requests

from config import CITIES, WEATHER_VARIABLES

ARCHIVE_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 30


class WeatherError(RuntimeError):
    pass


def _frame(payload):
    hourly = payload.get("hourly")
    if not hourly:
        raise WeatherError(f"no hourly block in response: {str(payload)[:200]}")
    frame = pd.DataFrame(hourly)
    frame["timestamp"] = pd.to_datetime(frame.pop("time"))
    return frame.sort_values("timestamp").reset_index(drop=True)


def _get(url, params):
    params = dict(params, hourly=",".join(WEATHER_VARIABLES), timezone="UTC")
    try:
        response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise WeatherError(f"{url}: {type(exc).__name__}: {exc}") from exc
    if response.status_code != 200:
        raise WeatherError(f"{url} returned {response.status_code}: {response.text[:200]}")
    return _frame(response.json())


def history(country, start, end):
    latitude, longitude = CITIES[country]
    return _get(
        ARCHIVE_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": f"{start:%Y-%m-%d}",
            "end_date": f"{end:%Y-%m-%d}",
        },
    )


def forecast(country, days=8):
    latitude, longitude = CITIES[country]
    return _get(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "forecast_days": days,
            "past_days": 7,
        },
    )
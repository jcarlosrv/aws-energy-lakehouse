"""Central configuration for the ENTSO-E load ingest job"""

BUCKET = "jcarlosrv-energy-lakehouse"
RAW_PREFIX = "raw/entsoe-load"
CURATED_PREFIX = "curated/energy"

SSM_TOKEN_PARAMETER = "/energy-lakehouse/entsoe-token"

COUNTRIES = {
    "DE": {"name": "Germany",     "tz": "Europe/Berlin",   "region": "Central"},
    "FR": {"name": "France",      "tz": "Europe/Paris",    "region": "West"},
    "ES": {"name": "Spain",       "tz": "Europe/Madrid",   "region": "Iberia"},
    "IT": {"name": "Italy",       "tz": "Europe/Rome",     "region": "South"},
    "PL": {"name": "Poland",      "tz": "Europe/Warsaw",   "region": "Central"},
    "NL": {"name": "Netherlands", "tz": "Europe/Amsterdam","region": "West"},
}

ZONE_OVERRIDE = {"DE": "DE_LU"}

LOOKBACK_DAYS = 8

PLAUSIBLE_LOAD_MIN = 0.0
PLAUSIBLE_LOAD_MAX = 120_000.0
ATHENA_DATABASE = "energy"
ATHENA_TABLE = "entsoe_load"
ATHENA_WORKGROUP = "primary"
ATHENA_RESULTS_PREFIX = "athena-results"

MODEL_KEY = "models/model.txt"
METRICS_KEY = "models/metrics.json"
FORECAST_PREFIX = "forecasts"
DASHBOARD_KEY = "dashboard/latest.json"

HORIZON_HOURS = 168
MAX_STALENESS_HOURS = 72
HISTORY_MONTHS = 2

WEATHER_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "direct_radiation",
)

CITIES = {
    "DE": (52.5200, 13.4050),
    "FR": (48.8566, 2.3522),
    "ES": (40.4168, -3.7038),
    "IT": (41.9028, 12.4964),
    "PL": (52.2297, 21.0122),
}
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
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "validate_payload.py"

GOOD = {
    "issued": "2026-08-28T23:00:00",
    "metrics": {},
    "countries": {
        code: {
            "recent": [{"timestamp": "2026-08-28T23:00:00", "actual_mw": 1.0}],
            "forecast": [{"timestamp": "2026-08-29T00:00:00", "predicted_mw": 1.0}],
            "compared": [],
        }
        for code in ("DE", "ES", "FR", "IT", "PL")
    },
}


def run(tmp_path, text):
    target = tmp_path / "latest.json"
    target.write_text(text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(target)], capture_output=True, text=True
    )


def test_a_good_payload_is_accepted(tmp_path):
    assert run(tmp_path, json.dumps(GOOD)).returncode == 0


def test_a_missing_country_is_rejected(tmp_path):
    payload = json.loads(json.dumps(GOOD))
    del payload["countries"]["PL"]
    assert run(tmp_path, json.dumps(payload)).returncode != 0


def test_an_empty_countries_block_is_rejected(tmp_path):
    payload = json.loads(json.dumps(GOOD))
    payload["countries"] = {}
    assert run(tmp_path, json.dumps(payload)).returncode != 0


def test_a_nan_value_is_rejected(tmp_path):
    text = json.dumps(GOOD).replace('"actual_mw": 1.0', '"actual_mw": NaN')
    assert run(tmp_path, text).returncode != 0
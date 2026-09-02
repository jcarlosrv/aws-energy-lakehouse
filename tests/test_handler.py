import requests

import handler

FAKE_TOKEN = "aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb"
ENTSOE_ERROR = (
    "503 Server Error: Service Unavailable for url: "
    "https://web-api.tp.entsoe.eu/api?documentType=A65"
    f"&securityToken={FAKE_TOKEN}&periodStart=202608240000"
)


def test_error_detail_redacts_the_security_token():
    detail = handler._safe_detail(requests.exceptions.HTTPError(ENTSOE_ERROR))

    assert FAKE_TOKEN not in detail


def test_error_detail_keeps_the_diagnostic_information():
    detail = handler._safe_detail(requests.exceptions.HTTPError(ENTSOE_ERROR))

    assert "HTTPError" in detail
    assert "503" in detail
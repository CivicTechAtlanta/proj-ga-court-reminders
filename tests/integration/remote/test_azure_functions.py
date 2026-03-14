"""Integration test: hit the local Azure Functions endpoint.

Requires the Azure Functions host to be running locally (default: http://localhost:7071).
Tests are skipped automatically if the host is not reachable.
"""

import urllib.error
import urllib.request
import json

import pytest

pytestmark = pytest.mark.integration_azure

BASE_URL = "http://localhost:7071/api"


def _post_json(path, body):
    """POST JSON to the local function endpoint and return (status, body text)."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/{path}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.URLError as exc:
        pytest.skip(f"Function host not reachable: {exc}")


def test_twilio_handler_returns_home_menu():
    """Any inbound SMS should return the demo home scenario selector."""
    status, body = _post_json("twilioHandler", {"Body": "hello", "From": "+15550000001"})
    assert status == 200
    assert "7, 3, 1 countdown" in body


def test_twilio_handler_no_body():
    """Missing Body/From still returns a valid TwiML response."""
    status, body = _post_json("twilioHandler", {})
    assert status == 200
    assert "<Response>" in body

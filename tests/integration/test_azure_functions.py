"""Integration test: hit the local Azure Functions endpoint.

Requires the function host to be running locally (`make run`).

Usage:
    make test-azure
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


def test_twilio_handler_with_name():
    status, body = _post_json("twilioHandler", {"name": "World"})
    assert status == 200
    assert "Hello, World" in body


def test_twilio_handler_without_name():
    status, body = _post_json("twilioHandler", {})
    assert status == 200
    assert "Pass a name" in body

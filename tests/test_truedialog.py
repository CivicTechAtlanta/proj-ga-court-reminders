"""Unit tests for the truedialog access layer.

The HTTP transport is injected, so nothing here opens a connection to
TrueDialog. A few tests run the default urllib transport against a
throwaway HTTP server on localhost to prove the request that actually
leaves the process.
"""

import base64
import json
import logging
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from truedialog import (
    SmsResult,
    TrueDialogApiError,
    TrueDialogClient,
    TrueDialogConfig,
    TrueDialogConfigError,
    TrueDialogConnectionError,
    TrueDialogError,
    normalize_us_phone,
    truedialog_client,
)
from truedialog.client import HttpRequest, HttpResponse, urllib_transport

CONFIG = TrueDialogConfig(
    api_key="key",
    api_secret="secret",
    account_id="12345",
    channel_id="22",
    base_url="https://truedialog.example/api/v2.1",
)

ACCEPTED = {
    "id": 987,
    "accountId": 12345,
    "statusId": 1,
    "status": "Executed",
    "targets": ["+14045550142"],
    "channels": [{"id": 22}],
    "message": "See you in court.",
    "created": "2026-09-09T12:00:00",
}


class FakeTransport:
    """Hands back canned responses and records every request it saw."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return self.responses.pop(0)


def json_response(status, payload):
    body = json.dumps(payload).encode()
    return HttpResponse(status, body, {"Content-Type": "application/json"})


def client_with(*responses):
    transport = FakeTransport(*responses)
    return TrueDialogClient(CONFIG, transport=transport), transport


def explode(name):
    raise AssertionError("secret loader must not be called")


# ------------------------------------------------------------- send_message


def test_send_message_posts_a_push_campaign_with_basic_auth():
    client, transport = client_with(json_response(201, ACCEPTED))

    result = client.send_message("+14045550142", "See you in court.")

    (request,) = transport.requests
    assert request.method == "POST"
    assert request.url == (
        "https://truedialog.example/api/v2.1/account/12345/action-pushcampaign"
    )
    token = base64.b64encode(b"key:secret").decode()
    assert request.headers["Authorization"] == f"Basic {token}"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["Accept"] == "application/json"
    assert request.timeout == 10.0
    assert json.loads(request.body) == {
        "Channels": ["22"],
        "Targets": ["+14045550142"],
        "Message": "See you in court.",
        "CampaignId": 0,
        "Execute": True,
        "ForceOptIn": False,
        "IgnoreInvalidTargets": False,
    }
    assert result == SmsResult(
        action_id=987,
        account_id=12345,
        status_id=1,
        status="Executed",
        targets=("+14045550142",),
        created="2026-09-09T12:00:00",
        raw=ACCEPTED,
    )
    assert result.raw["message"] == "See you in court."


def test_send_message_normalizes_every_recipient_and_honours_options():
    client, transport = client_with(json_response(201, ACCEPTED))

    client.send_message(
        ["(404) 555-0142", "1-678-555-0199"],
        "Reminder",
        channel_id=31,
        execute=False,
        force_opt_in=True,
        ignore_invalid_targets=True,
        schedules=["2026-09-10T09:00:00"],
    )

    body = json.loads(transport.requests[0].body)
    assert body["Targets"] == ["+14045550142", "+16785550199"]
    assert body["Channels"] == ["31"]
    assert (body["Execute"], body["ForceOptIn"], body["IgnoreInvalidTargets"]) == (
        False,
        True,
        True,
    )
    assert body["Schedules"] == ["2026-09-10T09:00:00"]


@pytest.mark.parametrize(
    ("to", "message", "problem"),
    [
        ("+14045550142", "   ", "message"),
        ("555-0142", "Reminder", "phone"),
        ([], "Reminder", "recipient"),
    ],
)
def test_send_message_rejects_bad_input_before_calling_the_api(to, message, problem):
    client, transport = client_with(json_response(201, ACCEPTED))

    with pytest.raises(ValueError, match=problem):
        client.send_message(to, message)

    assert transport.requests == []


def test_send_message_logs_without_message_text_or_full_number(caplog):
    client, _ = client_with(json_response(201, ACCEPTED))

    with caplog.at_level(logging.INFO, logger="truedialog.client"):
        client.send_message("+14045550142", "See you in court.")

    assert "See you in court." not in caplog.text
    assert "+14045550142" not in caplog.text
    assert "***0142" in caplog.text
    assert "987" in caplog.text


# ------------------------------------------------------------------ errors


def test_api_errors_carry_status_and_decoded_body():
    client, _ = client_with(json_response(400, {"message": "Channel 22 unavailable"}))

    with pytest.raises(TrueDialogApiError) as excinfo:
        client.send_message("+14045550142", "Reminder")

    error = excinfo.value
    assert error.status == 400
    assert error.body == {"message": "Channel 22 unavailable"}
    assert "POST /account/12345/action-pushcampaign" in str(error)
    assert "HTTP 400" in str(error)
    assert "Channel 22 unavailable" in str(error)


def test_non_json_error_bodies_are_kept_as_text():
    client, _ = client_with(HttpResponse(502, b"<html>Bad Gateway</html>"))

    with pytest.raises(TrueDialogApiError) as excinfo:
        client.user_info()

    assert excinfo.value.status == 502
    assert excinfo.value.body == "<html>Bad Gateway</html>"


def test_unexpected_success_bodies_are_reported():
    client, _ = client_with(HttpResponse(200, b"[1, 2, 3]"))

    with pytest.raises(TrueDialogError, match="Unexpected response body"):
        client.user_info()


# -------------------------------------------------------------- read calls


def test_ping_reports_whether_the_credentials_are_accepted():
    accepted, _ = client_with(json_response(200, {"userName": "courtbot"}))
    assert accepted.ping() is True

    rejected, _ = client_with(json_response(401, {"message": "Unauthorized"}))
    assert rejected.ping() is False

    broken, _ = client_with(json_response(500, {"message": "boom"}))
    with pytest.raises(TrueDialogApiError):
        broken.ping()


def test_read_calls_use_get_without_a_body():
    client, transport = client_with(
        json_response(200, {"id": 12345}), json_response(200, {"userName": "x"})
    )

    assert client.account_info() == {"id": 12345}
    assert client.user_info() == {"userName": "x"}

    assert [(r.method, r.url, r.body) for r in transport.requests] == [
        ("GET", "https://truedialog.example/api/v2.1/account/12345", None),
        ("GET", "https://truedialog.example/api/v2.1/userinfo", None),
    ]
    assert "Content-Type" not in transport.requests[0].headers


def test_empty_success_bodies_become_empty_dicts():
    client, _ = client_with(HttpResponse(204, b""))
    assert client.user_info() == {}


# ------------------------------------------------------- urllib transport


class RecordingHandler(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self._record(self.rfile.read(length))
        self._reply(201, ACCEPTED)

    def do_GET(self):
        self._record(b"")
        self._reply(404, {"message": "Account not found"})

    def _record(self, body):
        headers = {name.lower(): value for name, value in self.headers.items()}
        self.seen.append((self.command, self.path, headers, body))

    def _reply(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def local_api():
    RecordingHandler.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/v2.1", RecordingHandler.seen
    finally:
        server.shutdown()
        server.server_close()


def test_urllib_transport_sends_the_real_request(local_api):
    base_url, seen = local_api
    config = TrueDialogConfig(
        api_key="key", api_secret="secret", account_id="12345", base_url=base_url
    )
    client = TrueDialogClient(config)  # default transport

    result = client.send_message("(404) 555-0142", "See you in court.")

    assert result.action_id == 987
    (method, path, headers, body) = seen[0]
    assert (method, path) == ("POST", "/api/v2.1/account/12345/action-pushcampaign")
    assert (
        headers["authorization"] == "Basic " + base64.b64encode(b"key:secret").decode()
    )
    assert headers["content-type"] == "application/json"
    assert json.loads(body)["Targets"] == ["+14045550142"]


def test_urllib_transport_returns_error_statuses_instead_of_raising(local_api):
    base_url, _ = local_api

    response = urllib_transport(
        HttpRequest("GET", base_url + "/account/1", {}, None, 5.0)
    )

    assert response.status == 404
    assert json.loads(response.body) == {"message": "Account not found"}


def test_urllib_transport_wraps_connection_failures():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        unused_port = probe.getsockname()[1]
    request = HttpRequest(
        "GET", f"http://127.0.0.1:{unused_port}/userinfo", {}, None, 2.0
    )

    with pytest.raises(TrueDialogConnectionError):
        urllib_transport(request)


# ------------------------------------------------------------------ config


def test_config_reads_the_environment_with_defaults():
    environ = {
        "TRUEDIALOG_API_KEY": "key",
        "TRUEDIALOG_API_SECRET": "secret",
        "TRUEDIALOG_ACCOUNT_ID": "12345",
    }

    config = TrueDialogConfig.from_env(environ=environ, secret_loader=explode)

    assert config == TrueDialogConfig(
        api_key="key", api_secret="secret", account_id="12345"
    )
    assert config.channel_id == "22"
    assert config.base_url == "https://api.truedialog.com/api/v2.1"
    assert config.timeout_seconds == 10.0


def test_config_prefers_secrets_manager_values():
    environ = {
        "TRUEDIALOG_SECRET_ID": "CourtBotTrueDialog",
        "TRUEDIALOG_CHANNEL_ID": "31",
        "TRUEDIALOG_BASE_URL": "http://localhost:4566/truedialog",
        "TRUEDIALOG_TIMEOUT_SECONDS": "2.5",
    }
    secret = {"api_key": "k", "api_secret": "s", "account_id": 12345}
    loaded = []

    def loader(name):
        loaded.append(name)
        return secret

    config = TrueDialogConfig.from_env(environ=environ, secret_loader=loader)

    assert loaded == ["CourtBotTrueDialog"]
    assert config == TrueDialogConfig(
        api_key="k",
        api_secret="s",
        account_id="12345",
        channel_id="31",
        base_url="http://localhost:4566/truedialog",
        timeout_seconds=2.5,
    )


def test_config_names_every_missing_setting():
    with pytest.raises(TrueDialogConfigError) as excinfo:
        TrueDialogConfig.from_env(
            environ={"TRUEDIALOG_API_KEY": "key"}, secret_loader=explode
        )

    message = str(excinfo.value)
    assert "TRUEDIALOG_API_SECRET" in message
    assert "TRUEDIALOG_ACCOUNT_ID" in message
    assert "TRUEDIALOG_API_KEY" not in message


def test_factory_builds_a_client_from_the_environment(monkeypatch):
    monkeypatch.setenv("TRUEDIALOG_API_KEY", "key")
    monkeypatch.setenv("TRUEDIALOG_API_SECRET", "secret")
    monkeypatch.setenv("TRUEDIALOG_ACCOUNT_ID", "12345")
    monkeypatch.delenv("TRUEDIALOG_SECRET_ID", raising=False)

    assert isinstance(truedialog_client(), TrueDialogClient)
    assert isinstance(truedialog_client(CONFIG), TrueDialogClient)


# ------------------------------------------------------------ phone/models


@pytest.mark.parametrize(
    "number",
    [
        "4045550142",
        "(404) 555-0142",
        "404.555.0142",
        "1-404-555-0142",
        "+1 404 555 0142",
        "+14045550142",
    ],
)
def test_normalize_us_phone_accepts_common_formats(number):
    assert normalize_us_phone(number) == "+14045550142"


@pytest.mark.parametrize(
    "number",
    ["", "555-0142", "04045550142", "4041550142", "+44 20 7946 0958", "24045550142"],
)
def test_normalize_us_phone_rejects_everything_else(number):
    with pytest.raises(ValueError, match="Not a valid US phone number"):
        normalize_us_phone(number)


def test_sms_result_tolerates_missing_fields():
    assert SmsResult.from_response({}) == SmsResult(
        action_id=None,
        account_id=None,
        status_id=None,
        status=None,
        targets=(),
        created=None,
        raw={},
    )

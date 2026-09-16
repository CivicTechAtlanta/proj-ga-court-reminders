"""The seed Lambda follows the CloudFormation custom-resource protocol."""

import json

import pytest

import database_loader
from court_db import DatabaseConfig


def sqlserver_config():
    return DatabaseConfig(
        engine="sqlserver",
        host="h",
        port=1433,
        database="courtdb",
        user="u",
        password="p",
    )


class FakeRepository:
    """A different count per lead time, so a summary that mixed two of them
    up could not pass."""

    COUNTS = {7: 12, 3: 3, 1: 2}

    def upcoming_hearings(self, days_ahead=7):
        return [object()] * self.COUNTS[days_ahead]


def cfn_event(request_type):
    return {
        "RequestType": request_type,
        "ResponseURL": "https://cloudformation.example/response",
        "StackId": "stack-1",
        "RequestId": "req-1",
        "LogicalResourceId": "CourtDatabaseSeed",
        "ResourceProperties": {"SeedVersion": "abc"},
    }


@pytest.fixture()
def seeded(monkeypatch):
    calls = {"loads": [], "responses": []}
    monkeypatch.setattr(
        database_loader.DatabaseConfig, "from_env", staticmethod(sqlserver_config)
    )
    monkeypatch.setattr(
        database_loader,
        "load_fixtures",
        lambda config: (
            calls["loads"].append(config)
            or {"database": "courtdb", "row_counts": {"tblCase": 11}}
        ),
    )
    monkeypatch.setattr(
        database_loader, "court_case_repository", lambda config: FakeRepository()
    )
    monkeypatch.setattr(
        database_loader,
        "use_test_phone",
        lambda config, number: (
            calls.setdefault("phones", []).append(number)
            or {"7": "CR-2026-000112", "3": "CR-2026-000113", "1": "CR-2026-000114"}
        ),
    )
    monkeypatch.setattr(
        database_loader,
        "_send_response",
        lambda url, body: calls["responses"].append((url, body)),
    )
    return calls


def test_create_seeds_and_answers_cloudformation_with_data(seeded):
    database_loader.handler(cfn_event("Create"), None)

    assert len(seeded["loads"]) == 1
    (url, body) = seeded["responses"][0]
    assert url == "https://cloudformation.example/response"
    assert body["Status"] == "SUCCESS"
    assert body["PhysicalResourceId"] == "court-database-seed"
    assert body["StackId"] == "stack-1"
    assert body["RequestId"] == "req-1"
    assert body["LogicalResourceId"] == "CourtDatabaseSeed"
    assert body["Data"]["UpcomingHearings"] == "12"
    assert json.loads(body["Data"]["HearingsByLeadTime"]) == {"7": 12, "3": 3, "1": 2}
    assert json.loads(body["Data"]["RowCounts"]) == {"tblCase": 11}


def test_update_reseeds(seeded):
    database_loader.handler(
        {**cfn_event("Update"), "PhysicalResourceId": "court-database-seed"}, None
    )
    assert len(seeded["loads"]) == 1
    assert seeded["responses"][0][1]["Status"] == "SUCCESS"


def test_delete_answers_without_touching_the_database(seeded):
    database_loader.handler(
        {**cfn_event("Delete"), "PhysicalResourceId": "court-database-seed"}, None
    )
    assert seeded["loads"] == []
    (_, body) = seeded["responses"][0]
    assert body["Status"] == "SUCCESS"
    assert body["PhysicalResourceId"] == "court-database-seed"
    assert body["Data"] == {}


def test_failure_is_reported_to_cloudformation_then_raised(seeded, monkeypatch):
    def broken(config):
        raise RuntimeError("cannot connect")

    monkeypatch.setattr(database_loader, "load_fixtures", broken)

    with pytest.raises(RuntimeError, match="cannot connect"):
        database_loader.handler(cfn_event("Create"), None)

    (_, body) = seeded["responses"][0]
    assert body["Status"] == "FAILED"
    assert "cannot connect" in body["Reason"]


def test_direct_invoke_returns_the_summary(seeded):
    summary = database_loader.handler({}, None)
    # Every lead time the reminder workflow texts on, counted in one pass, so
    # a reseed reports whether each threshold has anything to find.
    assert summary["hearings_by_lead_time"] == {"7": 12, "3": 3, "1": 2}
    # The seven-day window keeps a key of its own: the stack output and
    # `./script/db/verify` both mean that one specifically.
    assert summary["upcoming_hearings"] == 12
    assert summary["row_counts"] == {"tblCase": 11}
    assert seeded["responses"] == []


def test_the_reported_lead_times_are_the_ones_the_reminders_use():
    assert database_loader.REMINDER_LEAD_TIMES == (7, 3, 1)


def test_send_response_puts_json_to_the_response_url():
    import json as _json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_PUT(self):
            length = int(self.headers["Content-Length"])
            received["body"] = _json.loads(self.rfile.read(length))
            received["content_type"] = self.headers.get("Content-Type")
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/response?token=abc"
        database_loader._send_response(url, {"Status": "SUCCESS", "Data": {"A": "1"}})
    finally:
        server.shutdown()

    assert received["body"] == {"Status": "SUCCESS", "Data": {"A": "1"}}
    # S3 pre-signed URLs reject a Content-Type that was not part of the signature.
    assert received["content_type"] == ""


def test_a_phone_in_the_event_points_the_ladder_at_it(seeded):
    """The one way a real number reaches the fixtures, and it takes somebody
    invoking the Lambda by hand with it."""
    summary = database_loader.handler({"phone": "(404) 555-1234"}, None)

    # Normalized before it is written, whatever format was typed.
    assert seeded["phones"] == ["+14045551234"]
    assert summary["test_phone"]["cases"] == {
        "7": "CR-2026-000112",
        "3": "CR-2026-000113",
        "1": "CR-2026-000114",
    }
    # Masked in the summary: this is printed, and CloudWatch keeps logs for
    # years while a number ties a person to a court case.
    assert summary["test_phone"]["number"] == "***1234"
    assert "4045551234" not in json.dumps(summary)


def test_a_seed_without_a_phone_rewrites_nothing(seeded):
    """What the daily EventBridge reseed sends, so the schedule can never put
    a real number in the dev database."""
    summary = database_loader.handler({}, None)

    assert seeded.get("phones") is None
    assert "test_phone" not in summary


def test_a_bad_phone_in_the_event_is_refused_before_anything_is_loaded(seeded):
    """Checked before the seed runs, so a typo costs nothing. The message
    carries only the last four digits; it lands in CloudWatch."""
    with pytest.raises(ValueError, match=r"Not a valid US phone number: \*\*\*0134"):
        database_loader.handler({"phone": "555-0134"}, None)
    assert seeded["loads"] == []
    assert seeded.get("phones") is None


def test_cloudformation_never_carries_a_phone(seeded):
    """The custom resource seeds through _seed_data, which takes no event
    fields; a ResourceProperties phone must not become a destination."""
    database_loader.handler({**cfn_event("Create"), "phone": "+14045551234"}, None)
    assert seeded.get("phones") is None

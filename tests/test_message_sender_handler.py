"""The CourtBotMessageSender handler: direct invokes, function URL, and queue."""

import base64
import json

import pytest

import message_sender
from truedialog import (
    SmsResult,
    TrueDialogApiError,
    TrueDialogConfig,
    TrueDialogConfigError,
    TrueDialogConnectionError,
)

CONFIG = TrueDialogConfig(
    api_key="key", api_secret="secret", account_id="12345", channel_id="22"
)
API_KEY = "expected-key"
SEND = {"to": "(404) 555-0142", "message": "See you in court."}


class FakeClient:
    def __init__(self, ping=True):
        self.sent = []
        self.ping_result = ping
        self.send_error = None

    def send_message(self, to, message):
        if self.send_error:
            raise self.send_error
        self.sent.append((to, message))
        return SmsResult(
            action_id=987,
            account_id=12345,
            status_id=1,
            status="Executed",
            targets=("+14045550142",),
            created=None,
            raw={},
        )

    def ping(self):
        if isinstance(self.ping_result, Exception):
            raise self.ping_result
        return self.ping_result


@pytest.fixture
def client(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(
        message_sender.TrueDialogConfig, "from_env", classmethod(lambda cls: CONFIG)
    )
    monkeypatch.setattr(message_sender, "truedialog_client", lambda config: fake)
    monkeypatch.setenv(
        "SENDER_API_KEY_SECRET_ID", "arn:aws:secretsmanager:x:1:secret:k"
    )
    monkeypatch.setattr(message_sender, "_secret_string", lambda secret_id: API_KEY)
    message_sender._sender_api_key.cache_clear()
    yield fake
    message_sender._sender_api_key.cache_clear()


def http_event(method="POST", body=None, key=API_KEY, encode=False):
    event = {
        "version": "2.0",
        "rawPath": "/",
        "requestContext": {
            "http": {"method": method, "path": "/", "sourceIp": "203.0.113.5"}
        },
        "headers": {"content-type": "application/json"},
    }
    if key is not None:
        event["headers"]["X-Api-Key"] = key  # the handler must not care about case
    if body is not None:
        raw = body if isinstance(body, str) else json.dumps(body)
        if encode:
            raw = base64.b64encode(raw.encode()).decode()
        event["body"] = raw
        event["isBase64Encoded"] = encode
    return event


def body_of(response):
    return json.loads(response["body"])


# --------------------------------------------------------- direct invokes


def test_direct_invoke_sends_without_a_key(client, capsys):
    response = message_sender.handler(SEND, None)

    assert client.sent == [("(404) 555-0142", "See you in court.")]
    assert response["statusCode"] == 200
    assert body_of(response) == {
        "sent": True,
        "action_id": 987,
        "status": "Executed",
        "targets": ["+14045550142"],
    }
    logged = capsys.readouterr().out
    assert "See you in court." not in logged
    assert "555-0142" not in logged
    assert "***0142" in logged


def test_direct_invoke_reports_readiness_for_any_other_event(client):
    body = body_of(message_sender.handler({}, None))

    assert client.sent == []
    assert body["sent"] is False
    assert body["credentials_accepted"] is True
    assert (body["account_id"], body["channel_id"]) == ("12345", "22")


def test_direct_invoke_reports_an_unreachable_api_without_failing(client):
    client.ping_result = TrueDialogConnectionError("no route")

    body = body_of(message_sender.handler({"path": "/local-test"}, None))

    assert body["credentials_accepted"] is None
    assert "no route" in body["error"]


def test_direct_invoke_lets_send_failures_surface(client):
    client.send_error = RuntimeError("TrueDialog rejected it")

    with pytest.raises(RuntimeError, match="rejected"):
        message_sender.handler(SEND, None)


# ------------------------------------------------------------ function URL


def test_http_post_with_the_key_sends(client, capsys):
    response = message_sender.handler(http_event(body=SEND), None)

    assert response["statusCode"] == 200
    assert body_of(response)["sent"] is True
    assert client.sent == [("(404) 555-0142", "See you in court.")]
    logged = capsys.readouterr().out
    assert "POST / from 203.0.113.5" in logged
    assert API_KEY not in logged
    assert "See you in court." not in logged


@pytest.mark.parametrize("key", [None, "wrong-key", ""])
def test_http_refuses_a_missing_or_wrong_key(client, key):
    response = message_sender.handler(http_event(body=SEND, key=key), None)

    assert response["statusCode"] == 401
    assert client.sent == []


def test_http_fails_closed_when_no_key_secret_is_configured(client, monkeypatch):
    monkeypatch.delenv("SENDER_API_KEY_SECRET_ID")

    response = message_sender.handler(http_event(body=SEND), None)

    assert response["statusCode"] == 401
    assert client.sent == []


def test_http_get_reports_readiness(client):
    response = message_sender.handler(http_event(method="GET"), None)

    assert response["statusCode"] == 200
    assert body_of(response)["sent"] is False
    assert body_of(response)["credentials_accepted"] is True
    assert client.sent == []


def test_http_refuses_other_methods(client):
    response = message_sender.handler(http_event(method="PUT", body=SEND), None)

    assert response["statusCode"] == 405
    assert client.sent == []


@pytest.mark.parametrize(
    "body", ["{not json", {"to": "+14045550142"}, {"message": "hi"}, "[1, 2]", ""]
)
def test_http_rejects_malformed_or_incomplete_bodies(client, body):
    response = message_sender.handler(http_event(body=body), None)

    assert response["statusCode"] == 400
    assert "error" in body_of(response)
    assert client.sent == []


def test_http_decodes_base64_bodies(client):
    response = message_sender.handler(http_event(body=SEND, encode=True), None)

    assert response["statusCode"] == 200
    assert client.sent == [("(404) 555-0142", "See you in court.")]


def test_http_maps_bad_numbers_to_400(client):
    client.send_error = ValueError("Not a valid US phone number: '555'")

    response = message_sender.handler(http_event(body=SEND), None)

    assert response["statusCode"] == 400
    assert "phone number" in body_of(response)["error"]


def test_http_maps_truedialog_rejections_to_502(client):
    client.send_error = TrueDialogApiError(
        400, {"message": "bad channel"}, "POST", "/account/1/action-pushcampaign"
    )

    response = message_sender.handler(http_event(body=SEND), None)

    assert response["statusCode"] == 502
    assert body_of(response)["truedialog_status"] == 400
    assert "bad channel" in body_of(response)["error"]


def test_http_reports_an_unfilled_truedialog_secret_as_503(client, monkeypatch):
    def unfilled(cls):
        raise TrueDialogConfigError("Missing TrueDialog settings: TRUEDIALOG_API_KEY")

    monkeypatch.setattr(
        message_sender.TrueDialogConfig, "from_env", classmethod(unfilled)
    )

    response = message_sender.handler(http_event(body=SEND), None)

    assert response["statusCode"] == 503
    assert "TRUEDIALOG_API_KEY" in body_of(response)["error"]


# ------------------------------------------------------------ outbox queue


def sqs_event(*bodies, message_ids=None):
    """The shape an SQS event source mapping delivers."""
    ids = message_ids or [f"msg-{index}" for index in range(len(bodies))]
    return {
        "Records": [
            {
                "messageId": message_id,
                "receiptHandle": "AQEB-handle",
                "body": body if isinstance(body, str) else json.dumps(body),
                "attributes": {"ApproximateReceiveCount": "1"},
                "messageAttributes": {},
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:us-east-2:1:CourtBotOutbox",
                "awsRegion": "us-east-2",
            }
            for body, message_id in zip(bodies, ids)
        ]
    }


def test_queue_messages_use_the_same_shape_as_the_function_url(client):
    """One standard input: whatever the URL accepts, the queue accepts."""
    over_the_url = message_sender.handler(http_event(body=SEND), None)
    client.sent.clear()
    over_the_queue = message_sender.handler(sqs_event(SEND), None)

    assert json.loads(over_the_url["body"])["sent"] is True
    assert over_the_queue == {"batchItemFailures": []}
    assert client.sent == [("(404) 555-0142", "See you in court.")]


def test_whole_batch_is_sent_and_nothing_is_reported_back(client):
    second = {"to": "+16785550199", "message": "Reminder"}

    response = message_sender.handler(sqs_event(SEND, second), None)

    assert response == {"batchItemFailures": []}
    assert client.sent == [
        ("(404) 555-0142", "See you in court."),
        ("+16785550199", "Reminder"),
    ]


@pytest.mark.parametrize(
    "bad",
    [
        "{not json",
        "[1, 2]",
        "",
        json.dumps({"to": "+14045550142"}),
        json.dumps({"message": "hi"}),
    ],
)
def test_only_the_failing_record_is_reported(client, bad):
    response = message_sender.handler(
        sqs_event(SEND, bad, message_ids=["good", "bad"]), None
    )

    # The good one is sent and deleted; only the bad id goes back on the queue.
    assert response == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert client.sent == [("(404) 555-0142", "See you in court.")]


def test_a_send_failure_reports_that_record_without_losing_the_others(client):
    send_one = client.send_message

    def fail_the_first(to, message):
        if to == "(404) 555-0142":
            raise TrueDialogApiError(400, {"message": "bad channel"}, "POST", "/x")
        return send_one(to, message)

    client.send_message = fail_the_first
    second = {"to": "+16785550199", "message": "Reminder"}

    response = message_sender.handler(
        sqs_event(SEND, second, message_ids=["fails", "works"]), None
    )

    assert response == {"batchItemFailures": [{"itemIdentifier": "fails"}]}
    assert client.sent == [("+16785550199", "Reminder")]


def test_queue_logs_carry_no_phone_number_or_message_text(client, capsys):
    client.send_message = lambda to, message: (_ for _ in ()).throw(
        ValueError("Not a valid US phone number: '555-0142'")
    )

    message_sender.handler(sqs_event(SEND, message_ids=["msg-a"]), None)

    logged = capsys.readouterr().out
    assert "See you in court." not in logged
    assert "555-0142" not in logged
    assert "404" not in logged
    # Enough to find the payload in the dead letter queue, and no more.
    assert "msg-a" in logged
    assert "ValueError" in logged


def test_truedialog_rejections_are_logged_with_their_status(client, capsys):
    client.send_message = lambda to, message: (_ for _ in ()).throw(
        TrueDialogApiError(429, {"message": "slow down"}, "POST", "/x")
    )

    message_sender.handler(sqs_event(SEND), None)

    assert "TrueDialog answered HTTP 429" in capsys.readouterr().out


def test_an_unusable_secret_fails_the_whole_batch(client, monkeypatch):
    """Nothing is deleted from the queue when the credentials are missing."""

    def unfilled(cls):
        raise TrueDialogConfigError("Missing TrueDialog settings: TRUEDIALOG_API_KEY")

    monkeypatch.setattr(
        message_sender.TrueDialogConfig, "from_env", classmethod(unfilled)
    )

    with pytest.raises(TrueDialogConfigError):
        message_sender.handler(sqs_event(SEND), None)

    assert client.sent == []


def test_records_from_other_event_sources_are_not_treated_as_queue_messages(client):
    event = {"Records": [{"eventSource": "aws:s3", "s3": {}}]}

    response = message_sender.handler(event, None)

    # Falls through to the readiness report rather than silently doing nothing.
    assert json.loads(response["body"])["sent"] is False
    assert client.sent == []


# ------------------------------------------------------------- deduplication


class FakeLog:
    """Stands in for the DynamoDB-backed sent log."""

    def __init__(self, already=()):
        self.already = {str(i) for i in already}
        self.recorded = []

    def already_sent(self, reminder_id):
        return str(reminder_id) in self.already

    def record(self, reminder_id):
        self.recorded.append(str(reminder_id))
        self.already.add(str(reminder_id))


@pytest.fixture
def log(monkeypatch):
    fake = FakeLog()
    monkeypatch.setattr(message_sender, "sent_log", lambda: fake)
    return fake


def test_redelivering_the_same_queue_message_does_not_text_twice(client, log):
    """The SQS message id alone is enough, with no help from the producer."""
    event = sqs_event(SEND, message_ids=["msg-a"])

    first = message_sender.handler(event, None)
    second = message_sender.handler(event, None)

    assert first == {"batchItemFailures": []}
    assert second == {"batchItemFailures": []}  # still a success, so SQS deletes it
    assert client.sent == [("(404) 555-0142", "See you in court.")]
    assert log.recorded == ["msg-a"]


def test_a_reminder_id_in_the_body_beats_the_queue_message_id(client, log):
    """Two different deliveries of the same reminder are still one text."""
    body = dict(SEND, reminder_id="hearing-42")

    message_sender.handler(sqs_event(body, message_ids=["msg-a"]), None)
    message_sender.handler(sqs_event(body, message_ids=["msg-b"]), None)

    assert len(client.sent) == 1
    assert log.recorded == ["hearing-42"]


def test_nothing_is_recorded_when_the_send_fails(client, log):
    """Otherwise a failed reminder would be suppressed on the retry and
    never reach anyone."""
    client.send_message = lambda to, message: (_ for _ in ()).throw(
        TrueDialogApiError(500, {"message": "boom"}, "POST", "/x")
    )

    response = message_sender.handler(sqs_event(SEND, message_ids=["msg-a"]), None)

    assert response == {"batchItemFailures": [{"itemIdentifier": "msg-a"}]}
    assert log.recorded == []


def test_a_duplicate_is_reported_rather_than_silently_dropped(client, log):
    log.already.add("hearing-42")
    body = dict(SEND, reminder_id="hearing-42")

    response = message_sender.handler(http_event(body=body), None)

    assert response["statusCode"] == 200
    assert body_of(response) == {
        "sent": False,
        "duplicate": True,
        "reminder_id": "hearing-42",
    }
    assert client.sent == []


def test_http_without_a_reminder_id_sends_every_time(client, log):
    """A developer curling twice means it; only an id asks for suppression."""
    message_sender.handler(http_event(body=SEND), None)
    message_sender.handler(http_event(body=SEND), None)

    assert len(client.sent) == 2
    assert log.recorded == []


def test_a_successful_send_reports_the_id_it_recorded(client, log):
    body = dict(SEND, reminder_id="hearing-42")

    response = message_sender.handler(http_event(body=body), None)

    assert body_of(response)["sent"] is True
    assert body_of(response)["reminder_id"] == "hearing-42"
    assert log.recorded == ["hearing-42"]

"""Send court-reminder text messages through TrueDialog.

Three ways in, all carrying the same JSON object:

    {"to": "+14045550142", "message": "See you in court Thursday."}

  * a message on the outbox queue (the CourtBotOutboxUrl stack output)
  * a POST to the sender's function URL (the SenderUrl stack output),
    which additionally needs the x-api-key header
  * a direct invocation, from make local-invoke, the console, or another
    Lambda, which needs no key because reaching the function already
    required AWS permissions

A GET on the function URL, or a direct invocation with any other event,
reports readiness instead of sending:

    curl "$SENDER_URL" -H "x-api-key: $SENDER_API_KEY"
"""

import base64
import hmac
import json
import os
from functools import lru_cache

from truedialog import (
    TrueDialogApiError,
    TrueDialogConfig,
    TrueDialogConfigError,
    TrueDialogConnectionError,
    truedialog_client,
)


def handler(event, context):
    if _is_sqs_event(event):
        return _handle_sqs(event)
    if _is_http_request(event):
        return _handle_http(event)
    print("request: {}".format(json.dumps(_redacted(event))))
    return _respond(200, _run(event))


def _client():
    """The TrueDialog client for this invocation, and the config behind it."""
    config = TrueDialogConfig.from_env()
    return config, truedialog_client(config)


def _send(client, request):
    """Send one text and describe what TrueDialog accepted."""
    result = client.send_message(request["to"], request["message"])
    return {
        "sent": True,
        "action_id": result.action_id,
        "status": result.status,
        "targets": list(result.targets),
    }


def _run(event):
    """Send when the event names a recipient and message; otherwise report
    whether the TrueDialog secret resolves and the credentials work."""
    config, client = _client()

    if isinstance(event, dict) and event.get("to") and event.get("message"):
        return _send(client, event)

    report = {
        "sent": False,
        "account_id": config.account_id,
        "channel_id": config.channel_id,
        "hint": 'send {"to": "+1...", "message": "..."} to send one text',
    }
    try:
        report["credentials_accepted"] = client.ping()
    except TrueDialogConnectionError as error:
        report["credentials_accepted"] = None
        report["error"] = str(error)
    return report


# ------------------------------------------------------------ outbox queue


def _is_sqs_event(event):
    records = event.get("Records") if isinstance(event, dict) else None
    return bool(records) and all(
        isinstance(record, dict) and record.get("eventSource") == "aws:sqs"
        for record in records
    )


def _handle_sqs(event):
    """Send one text per queue message, reporting failures per record.

    The event source mapping asks for batch item failures, so every id
    returned here goes back on the queue and every other record is
    deleted. A record that keeps failing moves to the dead letter queue
    after the queue's redrive limit, which is where to find the payload:
    the log lines below carry no phone number and no message text.

    A failure to build the client at all, such as a TrueDialog secret
    nobody has filled in, raises instead, which fails the whole batch and
    leaves every message on the queue.
    """
    records = event["Records"]
    queue = records[0].get("eventSourceARN", "an unnamed queue")
    print(f"request: {len(records)} queue message(s) from {queue}")

    _, client = _client()
    failures = []
    for record in records:
        message_id = record.get("messageId")
        try:
            _send(client, _queue_request(record))
        except Exception as error:
            print(f"queue message {message_id} failed: {_reason(error)}")
            failures.append({"itemIdentifier": message_id})

    print(f"sent {len(records) - len(failures)} of {len(records)} queue message(s)")
    return {"batchItemFailures": failures}


def _queue_request(record):
    """The {to, message} object one queue message carries.

    Deliberately the same shape the function URL accepts, so a reminder
    can reach the sender by either route without being reshaped.
    """
    parsed = json.loads(record.get("body") or "")
    if not isinstance(parsed, dict):
        raise ValueError("the message body must be a JSON object")
    if not parsed.get("to") or not parsed.get("message"):
        raise ValueError('the message body needs "to" and "message"')
    return parsed


def _reason(error):
    """Why one record failed, quoting nothing from its payload. An invalid
    phone number is in the message the wrapper raises, and logs outlive the
    queue, so only the kind of failure is recorded here."""
    if isinstance(error, TrueDialogApiError):
        return f"{type(error).__name__}, TrueDialog answered HTTP {error.status}"
    return type(error).__name__


# ------------------------------------------------------------ function URL


def _is_http_request(event):
    return isinstance(event, dict) and "http" in (event.get("requestContext") or {})


def _handle_http(event):
    http = event["requestContext"]["http"]
    method = str(http.get("method", "")).upper()
    # Nothing from the headers or body is logged: they hold the key and PII.
    print(f"request: {method} {http.get('path')} from {http.get('sourceIp')}")

    headers = {
        str(name).lower(): value for name, value in (event.get("headers") or {}).items()
    }
    if not _key_accepted(headers.get("x-api-key")):
        return _respond(401, {"error": "missing or invalid x-api-key header"})

    if method == "GET":
        request = {}
    elif method == "POST":
        try:
            request = _json_body(event)
        except ValueError as error:
            return _respond(400, {"error": f"the body must be a JSON object: {error}"})
        if not request.get("to") or not request.get("message"):
            return _respond(400, {"error": 'the body needs "to" and "message"'})
    else:
        return _respond(405, {"error": "GET reports readiness; POST sends a text"})

    try:
        return _respond(200, _run(request))
    except TrueDialogConfigError as error:
        return _respond(503, {"error": str(error)})
    except ValueError as error:  # an invalid phone number or a blank message
        return _respond(400, {"error": str(error)})
    except TrueDialogApiError as error:
        return _respond(502, {"error": str(error), "truedialog_status": error.status})
    except TrueDialogConnectionError as error:
        return _respond(502, {"error": str(error)})


def _key_accepted(presented):
    expected = _sender_api_key(os.environ.get("SENDER_API_KEY_SECRET_ID", ""))
    if not presented or not expected:
        return False
    return hmac.compare_digest(str(presented).encode(), expected.encode())


@lru_cache(maxsize=4)
def _sender_api_key(secret_id):
    """The key the URL requires, cached for the life of the container.
    Without a configured secret every HTTP request is refused."""
    return _secret_string(secret_id) if secret_id else None


def _secret_string(secret_id):
    # Imported lazily: boto3 ships in the Lambda runtime but is not a
    # project dependency.
    import boto3

    client = boto3.client("secretsmanager")
    return client.get_secret_value(SecretId=secret_id)["SecretString"]


def _json_body(event):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    parsed = json.loads(raw) if raw.strip() else {}
    if not isinstance(parsed, dict):
        raise ValueError("expected an object")
    return parsed


def _respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _redacted(event):
    """A direct-invoke event as logged: no message text, no full number."""
    if not isinstance(event, dict):
        return event
    redacted = dict(event)
    if redacted.get("to"):
        redacted["to"] = "***" + str(redacted["to"])[-4:]
    if redacted.get("message"):
        redacted["message"] = f"<{len(str(redacted['message']))} chars>"
    return redacted

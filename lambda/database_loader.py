"""Seed the deployed court database with the schema and fixtures.

CloudFormation invokes this Lambda as the CourtDatabaseSeed custom resource
during `cdk deploy`: SQL Server on RDS in AWS, Postgres on Floci's RDS
emulation locally, both from inside the database VPC that a laptop cannot
reach. It drops and recreates every table, so it is for development
databases only.

Invoking it with an empty event re-runs the seed and returns the summary,
which is how the fixture dates get re-anchored to today. Two things do that:
`make db-reset` on a laptop, and the CourtDatabaseDailyReseed EventBridge
rule against the AWS dev database every morning (see cdk_stack.py). The
summary counts hearings at each reminder lead time, so one look at the run
says whether every threshold has something to find.

An event of {"phone": "+14045551234"} additionally points the clean case at
each lead time at that number, so a developer can put their own handset in
the fixtures and watch a reminder arrive. The scheduled reseed sends {} and
so can never do this; only somebody invoking the Lambda by hand can.

The Lambda is the custom resource's service token, so it answers
CloudFormation itself with a PUT to the pre-signed ResponseURL. That answer
is always sent, success or failure; otherwise CloudFormation waits an hour
before giving up on the resource.
"""

import json
import os
import traceback
import urllib.request

from court_db import DatabaseConfig, court_case_repository
from court_db.seed import load_fixtures, use_test_phone
from truedialog import mask, normalize_us_phone


PHYSICAL_RESOURCE_ID = "court-database-seed"

# The lead times the reminder workflow texts on. The fixtures anchor a clean
# case at each one, so a seed that reports a zero here has gone stale or
# loaded something unexpected.
REMINDER_LEAD_TIMES = (7, 3, 1)


def handler(event, context):
    if "ResponseURL" not in event:
        return _seed(event.get("phone"))

    # Logged so a resource stuck waiting on CloudFormation can be answered by
    # hand; the URL is a short-lived, write-only pre-signed S3 URL.
    print(
        f"CloudFormation {event['RequestType']} request {event['RequestId']} "
        f"for {event['LogicalResourceId']}; ResponseURL={event['ResponseURL']}"
    )
    try:
        data = {} if event["RequestType"] == "Delete" else _seed_data()
    except Exception as exc:  # noqa: BLE001 - CloudFormation must hear back
        traceback.print_exc()
        _respond(event, "FAILED", {}, reason=f"{type(exc).__name__}: {exc}")
        raise
    return _respond(event, "SUCCESS", data)


def _seed(phone=None) -> dict:
    config = DatabaseConfig.from_env()
    # Checked before anything is loaded: the event carries whatever the caller
    # sent, and a mistyped number should not cost a full reseed first. Raises
    # ValueError naming only the last four digits.
    number = normalize_us_phone(phone) if phone else None
    print(
        f"seeding {config.engine} at {config.host}:{config.port}/{config.database} "
        f"as {config.user} (secret {'set' if os.getenv('COURT_DB_SECRET_ID') else 'unset'})"
    )
    summary = load_fixtures(config)
    if number:
        summary["test_phone"] = {
            "number": mask(number),
            "cases": use_test_phone(config, number),
        }
        print(f"reminder ladder now points at {mask(number)}")
    repository = court_case_repository(config)
    counts = {
        str(days): len(repository.upcoming_hearings(days_ahead=days))
        for days in REMINDER_LEAD_TIMES
    }
    summary["hearings_by_lead_time"] = counts
    # Kept as its own key: the CourtDatabaseSeedHearings stack output and
    # `make db-verify` both mean the seven-day window specifically, and
    # expect 12 rows right after loading.
    summary["upcoming_hearings"] = counts["7"]
    print(json.dumps(summary))
    return summary


def _seed_data() -> dict:
    summary = _seed()
    return {
        "UpcomingHearings": str(summary["upcoming_hearings"]),
        "HearingsByLeadTime": json.dumps(summary["hearings_by_lead_time"]),
        "RowCounts": json.dumps(summary["row_counts"]),
    }


def _respond(event, status, data, reason="See the CloudWatch log stream"):
    # The data lives with the RDS instance; a Delete of the seed resource (or
    # the stack) is answered without touching the database.
    body = {
        "Status": status,
        "Reason": reason,
        "PhysicalResourceId": event.get("PhysicalResourceId", PHYSICAL_RESOURCE_ID),
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": data,
    }
    _send_response(event["ResponseURL"], body)
    return body


def _send_response(url, body):
    payload = json.dumps(body).encode()
    request = urllib.request.Request(
        url,
        data=payload,
        method="PUT",
        headers={"Content-Type": "", "Content-Length": str(len(payload))},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print(f"CloudFormation response accepted: HTTP {response.status}")

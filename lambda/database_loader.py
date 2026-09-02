"""Seed the deployed court database with the schema and fixtures.

CloudFormation invokes this Lambda as the CourtDatabaseSeed custom resource
during `cdk deploy`: SQL Server on RDS in AWS, Postgres on Floci's RDS
emulation locally, both from inside the database VPC that a laptop cannot
reach. It drops and recreates every table, so it is for development
databases only. Invoking it directly with an empty event re-runs the seed
by hand and returns the summary.

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
from court_db.seed import load_fixtures


PHYSICAL_RESOURCE_ID = "court-database-seed"


def handler(event, context):
    if "ResponseURL" not in event:
        return _seed()

    try:
        data = {} if event["RequestType"] == "Delete" else _seed_data()
    except Exception as exc:  # noqa: BLE001 - CloudFormation must hear back
        traceback.print_exc()
        _respond(event, "FAILED", {}, reason=f"{type(exc).__name__}: {exc}")
        raise
    return _respond(event, "SUCCESS", data)


def _seed() -> dict:
    config = DatabaseConfig.from_env()
    print(
        f"seeding {config.engine} at {config.host}:{config.port}/{config.database} "
        f"as {config.user} (secret {'set' if os.getenv('COURT_DB_SECRET_ID') else 'unset'})"
    )
    summary = load_fixtures(config)
    # The same check as `make db-verify` locally: 11 rows right after loading.
    summary["upcoming_hearings"] = len(
        court_case_repository(config).upcoming_hearings()
    )
    print(json.dumps(summary))
    return summary


def _seed_data() -> dict:
    summary = _seed()
    return {
        "UpcomingHearings": str(summary["upcoming_hearings"]),
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

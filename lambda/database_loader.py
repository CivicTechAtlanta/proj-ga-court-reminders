"""Seed the AWS dev database with the court case schema and fixtures.

CloudFormation invokes this Lambda through the CourtDatabaseSeed custom
resource during `cdk deploy`, from inside the database VPC that a laptop
cannot reach. It drops and recreates every table, so it is for the
development database only. Invoking it directly with an empty event re-runs
the seed by hand and returns the summary.
"""

import json

from court_db import DatabaseConfig, court_case_repository
from court_db.seed import load_fixtures


PHYSICAL_RESOURCE_ID = "court-database-seed"


def handler(event, context):
    if event.get("RequestType") == "Delete":
        # The data lives with the RDS instance; removing the seed resource
        # (or the stack) must not reach into the database.
        return {
            "PhysicalResourceId": event.get("PhysicalResourceId", PHYSICAL_RESOURCE_ID)
        }

    config = DatabaseConfig.from_env()
    if config.engine != "sqlserver":
        raise RuntimeError(
            "The loader targets SQL Server only; the local Postgres database "
            "seeds itself from db/init on first start."
        )

    summary = load_fixtures(config)
    # The same check as `make db-verify` locally: 11 rows right after loading.
    summary["upcoming_hearings"] = len(
        court_case_repository(config).upcoming_hearings()
    )
    print(json.dumps(summary))

    if "RequestType" not in event:
        return summary
    return {
        "PhysicalResourceId": PHYSICAL_RESOURCE_ID,
        "Data": {
            "UpcomingHearings": str(summary["upcoming_hearings"]),
            "RowCounts": json.dumps(summary["row_counts"]),
        },
    }

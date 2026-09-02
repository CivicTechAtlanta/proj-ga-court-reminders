"""Load the court case schema and fixtures into the AWS dev database.

Runs inside the database VPC, which a developer laptop cannot reach.
Invoke it with `make aws-db-load`; it drops and recreates every table, so
it is for the development database only.
"""

from court_db import DatabaseConfig, court_case_repository
from court_db.seed import load_fixtures


def handler(event, context):
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
    return summary

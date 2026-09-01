#!/usr/bin/env python3
"""CDK app entry point.

Context key `court_db` chooses the court database wiring:
  aws   (default) deploy CourtDatabaseStack and connect the Lambdas to it
  local           Lambdas only, for the Floci emulator; the court_db wrapper
                  falls back to the Docker Postgres fixtures
"""

import os

import aws_cdk

from cdk_stack import CourtReminderStack
from database_stack import CourtDatabaseStack
from github_stack import GithubDeployStack


app = aws_cdk.App()

environment = aws_cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
)

court_db = app.node.try_get_context("court_db") or "aws"
if court_db not in {"aws", "local"}:
    raise SystemExit(f"Unknown court_db context {court_db!r}; expected aws or local")

GithubDeployStack(app, "GithubActionStack")

database = None
if court_db == "aws":
    database = CourtDatabaseStack(app, "CourtDatabaseStack", env=environment)

CourtReminderStack(app, "CourtReminderStack", database=database, env=environment)

app.synth()

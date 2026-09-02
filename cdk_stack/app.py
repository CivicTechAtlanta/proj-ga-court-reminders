#!/usr/bin/env python3
"""CDK app entry point.

Context key `court_db` chooses how the court database stack is built:
  aws   (default) RDS SQL Server Express, the production-shaped engine
  local           RDS Postgres for the Floci emulator, which runs real
                  Postgres containers but cannot start SQL Server
Both modes deploy CourtDatabaseStack, seed it during the deploy, and
connect every Lambda to it through Secrets Manager. Values crossing from
the database stack to the Lambda stack use CloudFormation exports
(cdk.json sets defaultCrossStackReferences to "strong") because Floci does
not resolve the weak Fn::GetStackOutput form.
"""

import os

import aws_cdk

from cdk_stack import CourtReminderStack
from database_stack import CourtDatabaseStack
from github_stack import GithubActionStack


app = aws_cdk.App()

environment = aws_cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
)

court_db = app.node.try_get_context("court_db") or "aws"
if court_db not in {"aws", "local"}:
    raise SystemExit(f"Unknown court_db context {court_db!r}; expected aws or local")

GithubActionStack(app, "GithubActionStack")

database = CourtDatabaseStack(
    app,
    "CourtDatabaseStack",
    local=court_db == "local",
    env=environment,
)

CourtReminderStack(app, "CourtReminderStack", database=database, env=environment)

app.synth()

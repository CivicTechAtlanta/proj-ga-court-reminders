#!/usr/bin/env python3
import os

import aws_cdk

from cdk_stack import CourtReminderStack
from github_stack import GithubDeployStack


app = aws_cdk.App()

GithubDeployStack(app, "GithubActionStack")

CourtReminderStack(
    app,
    "CourtReminderStack",
    env=aws_cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
)

app.synth()

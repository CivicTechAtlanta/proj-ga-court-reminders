import os

from constructs import Construct
from aws_cdk import (
    Stack,
    Duration,
    aws_iam,
)


class GithubDeployStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        github_oidc_provider = aws_iam.OidcProviderNative(
            self,
            "Github iDP",
            url="https://token.actions.githubusercontent.com",
            client_ids=["sts.amazonaws.com"],
            thumbprints=["6938fd4d98bab03faadb97b34396831e3780aea1"],
        )

        github_role = aws_iam.Role(
            self,
            "GithubActionRole",
            description="Role assumed by Github Actions for deployments",
            assumed_by=aws_iam.WebIdentityPrincipal(
                github_oidc_provider.open_id_connect_provider_arn,
                conditions={
                    "StringEquals": {
                        "token.actions.githubusercontent.com:sub": "repo:CivicTechAtlanta/proj-ga-court-reminders:ref:refs/heads/main",
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    }
                }
            ),
            max_session_duration=Duration.hours(1),
        )

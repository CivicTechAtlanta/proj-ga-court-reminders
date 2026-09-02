from constructs import Construct
from aws_cdk import (
    Stack,
    Duration,
    aws_iam,
    CfnOutput,
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
                },
            ),
            max_session_duration=Duration.hours(1),
        )

        github_role.add_to_policy(
            aws_iam.PolicyStatement(
                resources=["*"],
                actions=[
                    "ec2:DescribeAvailabilityZones",
                    "ssm:GetParameter",
                    "cloudFormation:*",
                    "iam:PassRole",
                    "s3:GetBucketLocation",
                    "s3:ListBucket",
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                ],
            )
        )

        # Let CDK use its bootstrap roles (lookup, deploy, file and image
        # publishing) rather than this role's own credentials. Context lookups
        # such as a VPC's availability zones need the lookup role; without
        # this, synth fails with "not authorized to perform:
        # ec2:DescribeAvailabilityZones". The default bootstrap qualifier is
        # hnb659fds.
        github_role.add_to_policy(
            aws_iam.PolicyStatement(
                actions=["sts:AssumeRole"],
                resources=[
                    self.format_arn(
                        service="iam",
                        region="",
                        resource="role",
                        resource_name="cdk-hnb659fds-*",
                    )
                ],
            )
        )

        # Output Role ARN to place in github secret: AWS_GITHUBACTIONROLE_ARN
        CfnOutput(
            self,
            "GitHubActionsRoleArn",
            value=github_role.role_arn,
            description="ARN for GitHub Actions role",
        )

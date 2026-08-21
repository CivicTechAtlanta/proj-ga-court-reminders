"""Deploy the project's Lambda definitions to the local AWS emulator.

After the first deployment, the script uses faster updates when possible.
"""

import os
import subprocess

import boto3
from botocore.exceptions import ClientError


STACK_NAME = "CourtReminderStack"
LOCAL_ENDPOINT_URL = "http://localhost:4566"


def _stack_exists():
    client = boto3.client(
        "cloudformation",
        endpoint_url=LOCAL_ENDPOINT_URL,
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )
    try:
        client.describe_stacks(StackName=STACK_NAME)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in {
            "ResourceNotFoundException",
            "ValidationError",
        }:
            return False
        raise
    return True


def main():
    if os.getenv("AWS_ENDPOINT_URL") != LOCAL_ENDPOINT_URL:
        raise SystemExit(
            "This helper only runs against local Floci. Use `make local-deploy`."
        )

    command = ["cdk", "deploy", STACK_NAME, "--require-approval", "never"]
    if _stack_exists():
        command.append("--hotswap")
        print("Existing Floci stack found; deploying Lambda changes with CDK hotswap")
    else:
        print("No Floci application stack found; running the initial CDK deployment")
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()

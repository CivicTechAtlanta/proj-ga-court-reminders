"""Deploy the CDK stacks to the local AWS emulator.

After the first deployment, the script uses faster updates when possible.
Values from the repository .env file are passed to the synth so that, in
local mode, CourtReminderStack can copy the TRUEDIALOG_* settings into the
TrueDialog secret it creates inside Floci.
"""

import os
import subprocess
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


STACK_NAME = "CourtReminderStack"
LOCAL_ENDPOINT_URL = "http://localhost:4566"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _dotenv(path):
    """KEY=VALUE pairs from a .env file: blank lines, comments, and an
    `export ` prefix are tolerated and surrounding quotes are stripped."""
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _deploy_environment():
    """The shell environment, plus .env values for anything it does not set."""
    return {**_dotenv(ENV_FILE), **os.environ}


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

    command = [
        "cdk",
        "deploy",
        STACK_NAME,
        "--require-approval",
        "never",
        # Floci's RDS runs Postgres, MySQL, and MariaDB containers but cannot
        # start SQL Server, so CourtDatabaseStack deploys as Postgres here.
        "--context",
        "court_db=local",
    ]
    if _stack_exists():
        command.append("--hotswap")
        print("Existing Floci stack found; deploying Lambda changes with CDK hotswap")
    else:
        print("No Floci application stack found; running the initial CDK deployment")
    subprocess.run(command, check=True, env=_deploy_environment())


if __name__ == "__main__":
    main()

"""Prepare the local AWS emulator so CDK can deploy resources into it.

The script skips this setup when Floci is already ready.
"""

import os
import subprocess

import boto3
from botocore.exceptions import ClientError


BOOTSTRAP_VERSION_PARAMETER = "/cdk-bootstrap/hnb659fds/version"
LOCAL_ENDPOINT_URL = "http://localhost:4566"


def main():
    if os.getenv("AWS_ENDPOINT_URL") != LOCAL_ENDPOINT_URL:
        raise SystemExit(
            "This helper only runs against local Floci. Use `make local-bootstrap`."
        )

    client = boto3.client(
        "ssm",
        endpoint_url=LOCAL_ENDPOINT_URL,
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )
    try:
        client.get_parameter(Name=BOOTSTRAP_VERSION_PARAMETER)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {
            "ParameterNotFound",
            "ResourceNotFoundException",
        }:
            raise
        subprocess.run(["cdk", "bootstrap"], check=True)
        return

    print("Floci CDK bootstrap already exists; skipping")


if __name__ == "__main__":
    main()

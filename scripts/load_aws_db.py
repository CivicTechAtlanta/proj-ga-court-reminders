"""Load the AWS dev database with the local fixture data.

Invokes the CourtBotDatabaseLoader Lambda, which runs inside the database
VPC. Needs AWS credentials for the deployed account; refuses to run with
the local Floci endpoint configured.
"""

import json
import os

import boto3


FUNCTION_HINT = "CourtBotDatabaseLoader"


def _function_name(client):
    names = [
        function["FunctionName"]
        for page in client.get_paginator("list_functions").paginate()
        for function in page.get("Functions", [])
    ]
    matches = [name for name in names if FUNCTION_HINT.lower() in name.lower()]
    if len(matches) != 1:
        raise SystemExit(
            f"Expected one {FUNCTION_HINT} function, found {matches or 'none'}. "
            "Deploy CourtReminderStack in aws mode first."
        )
    return matches[0]


def main():
    if os.getenv("AWS_ENDPOINT_URL"):
        raise SystemExit(
            "AWS_ENDPOINT_URL is set; this loader targets the real AWS account, "
            "not Floci. The local Postgres database seeds itself on first start."
        )

    client = boto3.client("lambda")
    name = _function_name(client)
    print(f"Invoking {name}; this drops and reloads every court table")
    response = client.invoke(
        FunctionName=name, InvocationType="RequestResponse", Payload=b"{}"
    )
    result = response["Payload"].read().decode()
    if response.get("FunctionError"):
        raise SystemExit(result)
    print(json.dumps(json.loads(result), indent=2))


if __name__ == "__main__":
    main()

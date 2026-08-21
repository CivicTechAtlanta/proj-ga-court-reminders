"""Find a locally deployed Lambda by its readable name and run it.

An optional JSON file provides test input to the Lambda.
"""

import argparse
import json
import os
from pathlib import Path

import boto3


def _function_name(client, requested):
    names = [
        function["FunctionName"]
        for function in client.list_functions().get("Functions", [])
    ]
    if requested in names:
        return requested

    matches = [name for name in names if requested.lower() in name.lower()]
    if len(matches) != 1:
        available = ", ".join(sorted(names)) or "none"
        raise RuntimeError(
            f"Could not uniquely resolve {requested}. Available functions: {available}"
        )
    return matches[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("function", help="CDK construct name or deployed function name")
    parser.add_argument("event", nargs="?", help="optional JSON event file")
    args = parser.parse_args()

    payload = b"{}"
    if args.event:
        payload = Path(args.event).read_bytes()
        json.loads(payload)

    client = boto3.client(
        "lambda",
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )
    response = client.invoke(
        FunctionName=_function_name(client, args.function),
        InvocationType="RequestResponse",
        Payload=payload,
    )
    result = response["Payload"].read().decode()
    if response.get("FunctionError"):
        raise RuntimeError(result)
    try:
        print(json.dumps(json.loads(result), indent=2))
    except json.JSONDecodeError:
        print(result)


if __name__ == "__main__":
    main()

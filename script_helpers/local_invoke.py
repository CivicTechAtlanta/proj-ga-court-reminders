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


def invoke(function, payload=b"{}"):
    """Run a locally deployed Lambda and return its response body as text.

    Raises RuntimeError carrying the Lambda's own error payload when the
    function itself fails, so a caller sees the traceback rather than a
    successful-looking empty result.
    """
    client = boto3.client(
        "lambda",
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )
    response = client.invoke(
        FunctionName=_function_name(client, function),
        InvocationType="RequestResponse",
        Payload=payload,
    )
    result = response["Payload"].read().decode()
    if response.get("FunctionError"):
        raise RuntimeError(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("function", help="CDK construct name or deployed function name")
    parser.add_argument("event", nargs="?", help="optional JSON event file")
    args = parser.parse_args()

    payload = b"{}"
    if args.event:
        payload = Path(args.event).read_bytes()
        json.loads(payload)

    result = invoke(args.function, payload)
    try:
        print(json.dumps(json.loads(result), indent=2))
    except json.JSONDecodeError:
        print(result)


if __name__ == "__main__":
    main()

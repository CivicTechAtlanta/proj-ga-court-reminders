"""Print the URL that reaches the text sender running in Floci.

Floci does not provision Lambda function URLs, so the SenderUrl stack output
is unresolved locally and there is no address to POST to. What does work is
Floci's Lambda invoke endpoint, which accepts unsigned requests and hands the
posted JSON to the handler as its event. That is the address to put in
Insomnia's Local (Floci) environment.

The function name changes on every `. script/reset`, so ask for it rather
than writing it down.
"""

import os

import boto3

LOCAL_ENDPOINT_URL = "http://localhost:4566"
REMINDER_STACK = "CourtReminderStack"
SENDER_LOGICAL_ID = "CourtBotMessageSender"


def main():
    if os.getenv("AWS_ENDPOINT_URL") != LOCAL_ENDPOINT_URL:
        raise SystemExit(
            "This helper only reads local Floci."
        )

    # Through the stack rather than by listing: a rolled-back update can
    # leave orphaned functions behind in Floci.
    resources = boto3.client("cloudformation").list_stack_resources(
        StackName=REMINDER_STACK
    )["StackResourceSummaries"]
    name = _physical_id(resources, "AWS::Lambda::Function", SENDER_LOGICAL_ID)
    print(f"{LOCAL_ENDPOINT_URL}/2015-03-31/functions/{name}/invocations")


def _physical_id(resources, resource_type, logical_id_prefix):
    matches = [
        resource["PhysicalResourceId"]
        for resource in resources
        if resource["ResourceType"] == resource_type
        and resource["LogicalResourceId"].startswith(logical_id_prefix)
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"Expected one {resource_type} named {logical_id_prefix}*, "
            f"found {len(matches)}. Is the stack deployed? Try `. script/setup`."
        )
    return matches[0]


if __name__ == "__main__":
    main()

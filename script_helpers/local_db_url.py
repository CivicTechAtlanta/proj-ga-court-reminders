"""Print the connection URL of the court database running in Floci.

By default the URL is for clients on this machine (DBeaver, psql), through
the RDS proxy port docker-compose.yml publishes. With --docker-network it
is for containers on the project's Docker network, such as the psql
container that `make db-psql` starts. Credentials come from the Secrets
Manager secret CourtDatabaseStack writes; locally they are dummy values.
"""

import argparse
import json
import os

import boto3


LOCAL_ENDPOINT_URL = "http://localhost:4566"
DATABASE_STACK = "CourtDatabaseStack"
SECRET_LOGICAL_ID = "CourtCaseDatabaseCredentials"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--docker-network",
        action="store_true",
        help="address the database as containers on the compose network see it",
    )
    args = parser.parse_args()

    if os.getenv("AWS_ENDPOINT_URL") != LOCAL_ENDPOINT_URL:
        raise SystemExit("This helper only reads local Floci. Use `make db-url`.")

    # Resolve the instance and secret through the stack rather than by
    # listing: a rolled-back update can leave orphaned copies behind in Floci.
    resources = boto3.client("cloudformation").list_stack_resources(
        StackName=DATABASE_STACK
    )["StackResourceSummaries"]
    instance_id = _physical_id(resources, "AWS::RDS::DBInstance", "CourtCaseDatabase")
    secret_arn = _physical_id(
        resources, "AWS::SecretsManager::Secret", SECRET_LOGICAL_ID
    )

    instance = boto3.client("rds").describe_db_instances(
        DBInstanceIdentifier=instance_id
    )["DBInstances"][0]
    endpoint = instance["Endpoint"]
    creds = json.loads(
        boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)[
            "SecretString"
        ]
    )

    host = endpoint["Address"] if args.docker_network else "localhost"
    print(
        f"postgresql://{creds['username']}:{creds['password']}"
        f"@{host}:{endpoint['Port']}/{creds['dbname']}"
    )


def _physical_id(resources, resource_type, logical_prefix):
    matches = [
        r["PhysicalResourceId"]
        for r in resources
        if r["ResourceType"] == resource_type
        and r["LogicalResourceId"].startswith(logical_prefix)
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"Expected one {resource_type} {logical_prefix}* in {DATABASE_STACK}, "
            f"found {len(matches)}; run: make local-start"
        )
    return matches[0]


if __name__ == "__main__":
    main()

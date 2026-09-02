"""Start the court-reminder workflow.

Finds the hearings due for a reminder through the court_db wrapper: the
docker-compose Postgres fixtures when running in Floci, RDS SQL Server in
AWS. Future work will hand the hearings to the message sender.
"""

import json
from dataclasses import asdict

from court_db import court_case_repository


def handler(event, context):
    print("request: {}".format(json.dumps(event)))
    hearings = court_case_repository().upcoming_hearings()
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "upcoming_hearings": len(hearings),
                "hearings": [asdict(hearing) for hearing in hearings],
            },
            default=str,
        ),
    }

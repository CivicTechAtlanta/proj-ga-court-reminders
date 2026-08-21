"""Start the court-reminder workflow.

Future work will use this Lambda to find upcoming hearings and prepare reminders.
"""

import json

def handler(event, context):
    print("request: {}".format(json.dumps(event)))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": "hello cdk. path hit: {}\n".format(event["path"]),
    }

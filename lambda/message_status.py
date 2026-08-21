"""Check whether a court-reminder text was delivered or failed.

Future work will connect this Lambda to delivery information from TrueDialog.
"""

import json

def handler(event, context):
    print("request: {}".format(json.dumps(event)))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": "this lambda handles fetching message statuses",
    }

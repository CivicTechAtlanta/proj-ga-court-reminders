"""Handle replies from people who receive court-reminder text messages.

Future work will connect this Lambda to TrueDialog and opt-out handling.
"""

import json


def handler(event, context):
    print("request: {}".format(json.dumps(event)))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": "this lambda handles message responses from trudialog.",
    }

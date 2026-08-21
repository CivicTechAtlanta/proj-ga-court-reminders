"""Send court-reminder text messages.

Future work will connect this Lambda to a queue and the text-message provider.
"""

import json

def handler(event, context):
    print("request: {}".format(json.dumps(event)))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": "this lambda will read from an sqs queue\n {}",
    }

import json

def handler(event, context):
    print("request: {}".format(json.dumps(event)))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": "this lambda handles message responses from trudialog."
    }

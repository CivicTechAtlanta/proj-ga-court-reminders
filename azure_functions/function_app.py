import logging
import traceback
import os
import time
import json
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import azure.functions as func
from azure.data.tables import TableServiceClient
from azure.storage.queue import (
    QueueClient,
    BinaryBase64EncodePolicy,
    BinaryBase64DecodePolicy,
)
from azure.core.exceptions import ResourceExistsError

from court_reminder import __version__

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

TABLE_NAME = "inboundmessages"
QUEUE_NAME = "outboundmessages"


def get_table_client():
    conn_str = os.environ["AzureWebJobsStorage"]
    service = TableServiceClient.from_connection_string(conn_str)

    return service.create_table_if_not_exists(TABLE_NAME)


def get_queue_client():
    conn_str = os.environ["AzureWebJobsStorage"]
    client = QueueClient.from_connection_string(
        conn_str=conn_str,
        queue_name=QUEUE_NAME,
        message_encode_policy=BinaryBase64EncodePolicy(),
    )
    try:
        client.create_queue()
    except ResourceExistsError:
        pass

    return client


def save_message(table, phone_number, message_body):
    row_key = f"{time.time_ns():19}"
    entity = {"PartitionKey": phone_number, "RowKey": row_key, "message": message_body}

    table.upsert_entity(entity=entity)


@app.function_name(name="twilioSender")
@app.queue_trigger(
    arg_name="queue_item", queue_name=QUEUE_NAME, connection="AzureWebJobsStorage"
)
def twilioSender(queue_item: func.QueueMessage) -> None:
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    phone_number = os.environ["TWILIO_PHONE_NUMBER"]
    to_phone_number = os.environ["TO_PHONE_NUMBER"]

    if account_sid is None or auth_token is None or not account_sid or not auth_token:
        logging.warn("missing account sid or auth token")
        return

    try:
        client = Client(account_sid, auth_token)
        item = queue_item.get_json()
        client.messages.create(
            body=item["message"], from_=phone_number, to=item["to_number"]
        )
    except Exception as e:
        logging.error(f"Function failed: {e}")
        logging.error(traceback.format_exc())


@app.route(route="twilioHandler")
def twilioHandler(req: func.HttpRequest) -> func.HttpResponse:
    try:
        table = get_table_client()
        queue = get_queue_client()

        body = dict(req.form)
        from_number = body.get("From", "unknown")
        message_body = body.get("Body", "")
        logging.info(f"SMS from {from_number}: {message_body}")

        save_message(table, from_number, message_body)

        reply_text = "Welcome to the Atlanta Municipal Court Reminder Demo. \n Which scenario do you want to play out?\n\n1. 7,3,1\n2. Missed\n"
        json_str = json.dumps({"to_number": from_number, "message": reply_text})

        queue.send_message(json_str.encode('utf-8'))
        # queue.send_message(json.dumps({'to_number': from_number, 'message': reply_text}), visibility_timeout=<7 minutes in seconds>)

        return func.HttpResponse(
            str(MessagingResponse()), status_code=200, mimetype="application/xml"
        )

    except Exception as e:
        logging.error(f"Function failed: {e}")
        logging.error(traceback.format_exc())
        return func.HttpResponse("Internal error", status_code=500)

import azure.functions as func
import logging
import traceback
import os
from azure.data.tables import TableServiceClient
import time
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from court_reminder import __version__

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

TABLE_NAME="stateMachine"
MAX_NS=9999999999999999999

def get_table_client():
    conn_str = os.environ["AzureWebJobsStorage"]
    service = TableServiceClient.from_connection_string(conn_str)

    return service.create_table_if_not_exists(TABLE_NAME)

def save_message(table, phone_number, message_body):
    row_key = f'{(MAX_NS - time.time_ns()):19}'
    entity = {
        "PartitionKey": phone_number,
        "RowKey": row_key,
        "message": message_body
    }
    
    table.upsert_entity(entity=entity)

@app.route(route="run")
def run(req: func.HttpRequest) -> func.HttpResponse:
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    phone_number = os.environ["TWILIO_PHONE_NUMBER"]
    to_phone_number = os.environ["TO_PHONE_NUMBER"]
    
    try:
        client = Client(account_sid, auth_token) 
        client.messages.create(body="Your court appointment will occur in 7 days.", from_=phone_number, to=to_phone_number)
        return func.HttpResponse('done', status_code=200, mimetype="application/text")
    except Exception as e:
        logging.error(f"Function failed: {e}")
        logging.error(traceback.format_exc())
        return func.HttpResponse("Internal error", status_code=500)


@app.route(route="twilioHandler")
def twilioHandler(req: func.HttpRequest) -> func.HttpResponse:
    try:
        table = get_table_client()

        body = dict(req.form)
        from_number = body.get("From", "unknown")
        message_body = body.get("Body", "")
        logging.info(f"SMS from {from_number}: {message_body}")

        save_message(table, from_number, message_body)

        queried = table.query_entities(query_filter="PartitionKey eq @number", select=["PartitionKey", "RowKey", "message"], parameters={"number": from_number})
        for item in queried:
            print(item)
        

        reply_text = "Welcome to the Atlanta Municipal Court Reminder Demo. \n Which scenario do you want to play out?\n\n1. 7,3,1\n2. Missed\n"
        twilio_response = MessagingResponse()
        twilio_response.message(reply_text)

        return func.HttpResponse(str(twilio_response), status_code=200, mimetype="application/xml")

    except Exception as e:
        logging.error(f"Function failed: {e}")
        logging.error(traceback.format_exc())
        return func.HttpResponse("Internal error", status_code=500)

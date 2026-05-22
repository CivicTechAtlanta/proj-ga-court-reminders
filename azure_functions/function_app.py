import azure.functions as func
import logging
import traceback
import os
from azure.data.tables import TableServiceClient
import time

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



@app.route(route="twilioHandler")
def twilioHandler(req: func.HttpRequest) -> func.HttpResponse:
    try:
        table = get_table_client()

        body = dict(req.form)
        from_number = body.get("From", "unknown")
        message_body = body.get("Body", "")
        logging.info(f"SMS from {from_number}: {message_body}")

        save_message(table, from_number, message_body)

        queried = table.query_entities(query_filter="PartitionKey eq @number", select=["PartitionKey", "RowKey", "message"], parameters={"number": "123-456-7890"})
        for item in queried:
            print(item)
        

        reply_text = "Welcome to the Atlanta Municipal Court Reminder Demo. \n Which scenario do you want to play out?\n\n1. 7,3,1\n2. Missed\n"
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            f"  <Message>{reply_text}</Message>"
            "</Response>"
        )
        return func.HttpResponse(twiml, status_code=200, mimetype="application/xml")

    except Exception as e:
        logging.error(f"Function failed: {e}")
        logging.error(traceback.format_exc())
        return func.HttpResponse("Internal error", status_code=500)

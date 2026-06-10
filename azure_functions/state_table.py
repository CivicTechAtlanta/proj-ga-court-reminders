import logging
import traceback
import os
import time
import json
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import azure.functions as func
from azure.data.tables import TableServiceClient

MESSAGES_TABLE_NAME = "inboundmessages"
STATE_TABLE_NAME = "demostate"

def get_state_table_client():
    conn_str = os.environ["AzureWebJobsStorage"]
    service = TableServiceClient.from_connection_string(conn_str)

    return service.create_table_if_not_exists(STATE_TABLE_NAME)

table = get_state_table_client()

def update_state(phone_number, new_state, queued_messages=None) -> None:
    if queued_messages is None:
        queued_messages = json.dumps([])

    entity = {
        "PartitionKey": "state_table",
        "RowKey": phone_number,
        "CurrentState": new_state,
        "QueuedMessages": queued_messages,
        "LastUpdated": f"{time.time_ns()}",
    }

    table.upsert_entity(entity=entity)


def get_state(phone_number):
    items = table.query_entities(
        query_filter="PartitionKey eq 'state_table' and RowKey eq @phonenumber",
        select=["PartitionKey", "RowKey", "CurrentState", "QueuedMessages"],
        parameters={"phonenumber": phone_number},
    )

    for state_item in items:
        return state_item
    
    update_state(phone_number, "initial")
    return get_state(phone_number)
    
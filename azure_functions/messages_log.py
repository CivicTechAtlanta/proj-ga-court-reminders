import os
import time

from azure.data.tables import TableServiceClient

MESSAGES_TABLE_NAME = "inboundmessages"

def get_messages_table_client():
    conn_str = os.environ["AzureWebJobsStorage"]
    service = TableServiceClient.from_connection_string(conn_str)

    return service.create_table_if_not_exists(MESSAGES_TABLE_NAME)

table = get_messages_table_client()

def save_message(phone_number, message_body):
    row_key = f"{time.time_ns():19}"
    entity = {"PartitionKey": phone_number, "RowKey": row_key, "message": message_body}

    table.upsert_entity(entity=entity)
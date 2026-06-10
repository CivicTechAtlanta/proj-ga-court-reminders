import os
import time
import json
from azure.storage.queue import (
    QueueClient,
    BinaryBase64EncodePolicy,
    BinaryBase64DecodePolicy,
)
from azure.core.exceptions import ResourceExistsError

QUEUE_NAME = "outboundmessages"

def get_queue_client():
    conn_str = os.environ["AzureWebJobsStorage"]
    client = QueueClient.from_connection_string(
        conn_str=conn_str,
        queue_name=QUEUE_NAME,
        message_encode_policy=BinaryBase64EncodePolicy(),
        messade_decode_policy=BinaryBase64DecodePolicy(),
    )
    try:
        client.create_queue()
    except ResourceExistsError:
        pass

    return client

def toQueueMessage(to_number, message):
    return json.dumps({"to_number": to_number, "message": message}).encode("utf-8")
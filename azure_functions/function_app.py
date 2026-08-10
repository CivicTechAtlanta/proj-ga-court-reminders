import logging
import traceback
import os
import time
import json
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import azure.functions as func


from court_reminder import __version__

from state_table import get_state, update_state
from messages_log import save_message
from message_queue import get_queue_client, toQueueMessage, QUEUE_NAME

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="twilioSender")
@app.queue_trigger(
    arg_name="queue_item", queue_name=QUEUE_NAME, connection="AzureWebJobsStorage"
)
def twilioSender(queue_item: func.QueueMessage) -> None:
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    phone_number = os.environ["TWILIO_PHONE_NUMBER"]

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
        queue = get_queue_client()

        body = dict(req.form)
        from_number = body.get("From", "unknown")
        message_body = body.get("Body", "")
        save_message(from_number, message_body)
        logging.info(f"SMS from {from_number}: {message_body}")

        current_state = get_state(from_number)
        if "EXIT" in message_body:
            handle_exit(queue, from_number, current_state)
        elif current_state["CurrentState"] == "initial":
            reply_text = "Welcome to the Civic Tech Atlanta Court Reminder Demo. \n Which scenario do you want to play out?\n\n1. 7,3,1\n2. Missed\n"
            queue.send_message(toQueueMessage(from_number, reply_text))
            update_state(from_number, "menu_sent")
        elif current_state["CurrentState"] == "menu_sent":
            if len(message_body) > 0 and message_body[0] == "1":
                run_scenario_1(queue, from_number)
            elif len(message_body) > 0 and message_body[0] == "2":
                run_scenario_2(queue, from_number)
            else:
                queue.send_message(
                    toQueueMessage(
                        from_number, "Unexpected input. Please reply with 1 or 2."
                    )
                )

        return func.HttpResponse(
            str(MessagingResponse()), status_code=200, mimetype="application/xml"
        )

    except Exception as e:
        logging.error(f"Function failed: {e}")
        logging.error(traceback.format_exc())
        return func.HttpResponse("Internal error", status_code=500)


def run_scenario_1(queue, from_number):
    current_time = time.time()
    fake_court_date = time.ctime(current_time + (60 * 10))
    queue.send_message(
        toQueueMessage(
            from_number,
            "Welcome. Your fake court date is 10 minutes from now on {}. We'll text you 7 min, 3 min, and 1 min before your fake court date. \n\n Text EXIT to end the demo.".format(
                fake_court_date
            ),
        )
    )

    enqueued_one = queue.send_message(
        toQueueMessage(
            from_number,
            "Your fake court date is 7 minutes from now. \nDetails: \n1234 Main St, Atlanta, GA\nCourt Room ABC\n{} \n\n Text EXIT to end the demo.".format(
                fake_court_date
            ),
        ),
        visibility_timeout=3 * 60,
    )
    enqueued_two = queue.send_message(
        toQueueMessage(
            from_number,
            "Your fake court date is 3 minutes from now. \nDetails: \n1234 Main St, Atlanta, GA\nCourt Room ABC\n{} \n\n Text EXIT to end the demo.".format(
                fake_court_date
            ),
        ),
        visibility_timeout=7 * 60,
    )
    enqueued_three = queue.send_message(
        toQueueMessage(
            from_number,
            "Your fake court date is 1 minute from now. \nDetails: \n1234 Main St, Atlanta, GA\nCourt Room ABC\n{} \n\n Text EXIT to end the demo.".format(
                fake_court_date
            ),
        ),
        visibility_timeout=9 * 60,
    )

    messages_queued = json.dumps(
        [
            {
                "id": enqueued_one.id,
                "pop_receipt": enqueued_one.pop_receipt,
            },
            {
                "id": enqueued_two.id,
                "pop_receipt": enqueued_two.pop_receipt,
            },
            {
                "id": enqueued_three.id,
                "pop_receipt": enqueued_three.pop_receipt,
            },
        ]
    )

    update_state(
        from_number,
        "initial",
        queued_messages=messages_queued,
    )


def run_scenario_2(queue, from_number):
    current_time = time.time()
    fake_court_date = time.ctime(current_time + (60 * 10))
    queue.send_message(
        toQueueMessage(
            from_number,
            "Welcome. Your fake court date is 10 minutes from now on {}. We'll text you 7 min, 3 min, and 1 min before your fake court date and 1 minute after the missed fake court date. \n\n Text EXIT to end the demo.".format(
                fake_court_date
            ),
        )
    )

    enqueued_one = queue.send_message(
        toQueueMessage(
            from_number,
            "Your fake court date is 7 minutes from now. \nDetails: \n1234 Main St, Atlanta, GA\nCourt Room ABC\n{} \n\n Text EXIT to end the demo.".format(
                fake_court_date
            ),
        ),
        visibility_timeout=3 * 60,
    )
    enqueued_two = queue.send_message(
        toQueueMessage(
            from_number,
            "Your fake court date is 3 minutes from now. \nDetails: \n1234 Main St, Atlanta, GA\nCourt Room ABC\n{} \n\n Text EXIT to end the demo.".format(
                fake_court_date
            ),
        ),
        visibility_timeout=7 * 60,
    )
    enqueued_three = queue.send_message(
        toQueueMessage(
            from_number,
            "Your fake court date is 1 minute from now. \nDetails: \n1234 Main St, Atlanta, GA\nCourt Room ABC\n{} \n\n Text EXIT to end the demo.".format(
                fake_court_date
            ),
        ),
        visibility_timeout=9 * 60,
    )
    enqueued_four = queue.send_message(
        toQueueMessage(
            from_number,
            "We noticed you missed your court date. You'll need to reschedule. \n\n Text EXIT to end the demo.",
        ),
        visibility_timeout=11 * 60,
    )
    messages_queued = json.dumps(
        [
            {
                "id": enqueued_one.id,
                "pop_receipt": enqueued_one.pop_receipt,
            },
            {
                "id": enqueued_two.id,
                "pop_receipt": enqueued_two.pop_receipt,
            },
            {
                "id": enqueued_three.id,
                "pop_receipt": enqueued_three.pop_receipt,
            },
            {"id": enqueued_four.id, "pop_receipt": enqueued_four.pop_receipt},
        ]
    )

    update_state(
        from_number,
        "initial",
        queued_messages=messages_queued,
    )


def handle_exit(queue, to_number, current_state):
    queue.send_message(
        toQueueMessage(
            to_number,
            "Demo exited.",
        )
    )

    message_refs = json.loads(current_state["QueuedMessages"])
    for ref in message_refs:
        print("deleting queue message: {}".format(ref["id"]))
        queue.delete_message(ref["id"], pop_receipt=ref["pop_receipt"])

    update_state(to_number, "initial")

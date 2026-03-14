import json
import logging
import os

import azure.functions as func

from court_reminder import __version__
from court_reminder.state import AzureTableStateStore, InMemoryStateStore
from court_reminder.twilio_handler import advance_scenario, handle_inbound_sms

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


_memory_store = InMemoryStateStore()


def _get_state_store():
    if os.environ.get("STATE_BACKEND") == "memory":
        return _memory_store
    return AzureTableStateStore(table_client=None)


def format_twiml(messages: list[str]) -> str:
    body = "".join(f"<Message>{m}</Message>" for m in messages)
    return f"<Response>{body}</Response>"


@app.route(route="twilioHandler")
def twilioHandler(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("court-reminder %s: twilioHandler triggered.", __version__)

    phone = req.form.get("From", "")
    body = req.form.get("Body", "")
    logging.info("From=%s Body=%s", phone, body)

    state_store = _get_state_store()
    messages = handle_inbound_sms(phone, body, state_store)

    return func.HttpResponse(
        format_twiml(messages),
        status_code=200,
        mimetype="application/xml",
    )


@app.route(route="advanceScenario")
def advanceScenario(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("court-reminder %s: advanceScenario triggered.", __version__)

    try:
        data = req.get_json()
        phone = data.get("phone", "")
    except ValueError:
        return func.HttpResponse("Missing JSON body with 'phone'", status_code=400)

    state_store = _get_state_store()
    messages = advance_scenario(phone, state_store)

    return func.HttpResponse(
        json.dumps({"messages": messages}),
        status_code=200,
        mimetype="application/json",
    )

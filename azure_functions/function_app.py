import azure.functions as func
import logging
import traceback

from court_reminder import __version__

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="twilioHandler")
def twilioHandler(req: func.HttpRequest) -> func.HttpResponse:
    # logging.info(
    #     "court-reminder %s: HTTP trigger function processed a request.", __version__
    # )

    # name = req.params.get("name")
    # if not name:
    #     try:
    #         req_body = req.get_json()
    #     except ValueError:
    #         pass
    #     else:
    #         name = req_body.get("name")

    # if name:
    #     return func.HttpResponse(
    #         f"Hello, {name}. This HTTP triggered function executed successfully."
    #     )
    # else:
    #     return func.HttpResponse(
    #         "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
    #         status_code=200,
    #     )

    try:
        body = dict(req.form)
        from_number = body.get("From", "unknown")
        message_body = body.get("Body", "")
        logging.info(f"SMS from {from_number}: {message_body}")

        reply_text = "Hello! Thank you for subscribing to the Dekalb County Courtbot!"
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

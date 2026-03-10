import azure.functions as func
import logging

from court_reminder import __version__

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="twilioHandler")
def twilioHandler(req: func.HttpRequest) -> func.HttpResponse:
    logging.info(
        "court-reminder %s: HTTP trigger function processed a request.", __version__
    )

    body = req.get_json()
    logging.info("received body: %s", body)

    return func.HttpResponse("done\n", status_code=200)

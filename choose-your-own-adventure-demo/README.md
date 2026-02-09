#### Setting up demo locally
1) Navigate to `choose-your-own-adventure-demo` folder
2) Setup Python virtual environment `python3 -m venv .venv`
3) Then install Python dependencies `.venv/bin/python -m pip install -r ./court-reminder-demo/requirements.txt`
4) Create `local.settings.json` `cp local.settings.json.copythis local.settings.json`
6) Install Azure Functions `npm i -g azure-functions-core-tools@4`
    Alternatively, follow the instructions [here](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=linux%2Cisolated-process%2Cnode-v4%2Cpython-v2%2Chttp-trigger%2Ccontainer-apps&pivots=programming-language-csharp#install-the-azure-functions-core-tools)
7) Start up Azurite storage emulator `docker run -p 10000:10000 -p 10001:10001 -p 10002:10002 mcr.microsoft.com/azure-storage/azurite azurite --disableTelemetry`

#### Running Locally
1) In a terminal, navigate to `choose-your-own-adventure-demo` folder
2) Start Azure Core Tools `func start`
3) Use curl or Postman to trigger function `curl -X POST http://localhost:7071/api/twilioHandler --data '<json data>'`
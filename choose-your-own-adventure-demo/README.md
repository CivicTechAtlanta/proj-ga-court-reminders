# Choose Your Own Adventure Demo

## Setting up demo locally
1) Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
2) Navigate to `choose-your-own-adventure-demo` folder
3) Install dependencies:
   ```bash
   uv sync
   ```
4) Create `local.settings.json` `cp local.settings.json.copythis local.settings.json`
5) Install Azure Functions `npm i -g azure-functions-core-tools@4`
    Alternatively, follow the instructions [here](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=linux%2Cisolated-process%2Cnode-v4%2Cpython-v2%2Chttp-trigger%2Ccontainer-apps&pivots=programming-language-csharp#install-the-azure-functions-core-tools)
6) Start up Azurite storage emulator `docker run -p 10000:10000 -p 10001:10001 -p 10002:10002 mcr.microsoft.com/azure-storage/azurite azurite --disableTelemetry`

## Running Locally

1) In a terminal, navigate to `choose-your-own-adventure-demo` folder
2) Start Azure Core Tools `uv run func start`
3) Use curl or Postman to trigger function `curl -X POST http://localhost:7071/api/twilioHandler --data '<json data>'`

## Running Tests

```bash
uv run python -m pytest
```

## Deployment via GitHub Actions

1. Set this repo Actions secret: `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` (can be found in Azure app along top bar, "Get Publish Profile")

## Running in Cloud

### Setup

1. Go to Storage Account "chooseyourownadventure" > Security + Networking > Access Keys
1. Copy one of the "Connection String" values (either for key1 or key2)
1. Save into the app settings in Azure, under `AzureWebJobsStorage`
  - Note: you can get to this in the VS Code Azure extension > Function App > choose-your-own-adventure-demo > Application Settings

### Example cURL request against deployed app

1. Go to choose-your-own-adventure-demo > Functions > App > Keys, and copy the value from "default"
1. Copy the code below into a terminal and replace the `<redacted>` "code" query parameter with value from step 1

```bash
curl -L "https://choose-your-own-adventure-demo-a5anercqfqdpfggr.canadacentral-01.azurewebsites.net/api/twilioHandler?code=<redacted>" \
  -H "Content-Type: application/json" \
  --data '{"name": "Brent"}'
```

Response if successful:

```bash
Hello, Brent. This HTTP triggered function executed successfully.%
```

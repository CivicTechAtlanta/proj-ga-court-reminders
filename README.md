# GA Court Reminders

An Azure Functions app that sends SMS court date reminders via Twilio.

## Local Development

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
2. Install dependencies & Create local.settings.json (For details, se "setup" in repo top-level [`Makefile`](./Makefile)):
   ```bash
   make setup
   ```
3. Install Azure Functions Core Tools:
   ```bash
   npm i -g azure-functions-core-tools@4
   ```
   Alternatively, follow the [official instructions](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=macos%2Cisolated-process%2Cnode-v4%2Cpython-v2%2Chttp-trigger%2Ccontainer-apps&pivots=programming-language-python#install-the-azure-functions-core-tools).
4. Start Azurite storage emulator:
   ```bash
   docker run -p 10000:10000 -p 10001:10001 -p 10002:10002 mcr.microsoft.com/azure-storage/azurite azurite --disableTelemetry
   ```

## Running Locally

1. Start the Azure Function:
   ```bash
   make run
   ```
2. Trigger the function:
   ```bash
   curl -X POST http://localhost:7071/api/twilioHandler --data '{"name": "World"}'
   ```

## Running Tests

Unit tests (no credentials needed):
```bash
make test
```

### Integration Tests

Integration tests hit real external services and require credentials.

| Command | What it does |
|---|---|
| `make test` | Unit tests only (default) |
| `make test-twilio` | Twilio SMS integration tests |
| `make test-azure` | Azure Functions integration tests |
| `make test-integration` | All integration tests |
| `make test-all` | Unit + integration tests |

**Twilio SMS setup** — sends actual SMS messages to a test number:
1. Copy `.template.env` to `.env` and fill in your Twilio credentials
2. Run `make test-twilio`

## Deployment via GitHub Actions

Set the repo Actions secret: `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` (found in Azure portal > Function App > "Get Publish Profile")

Note, this is likely already set in [Repo > Settings > Secrets and Variables > Actions](https://github.com/CivicTechAtlanta/proj-ga-court-reminders/settings/secrets/actions).  Including this section so we explicitly call it out for future maintainers

## Running in Cloud

### Setup

1. Go to Storage Account "chooseyourownadventure" > Security + Networking > Access Keys
2. Copy one of the "Connection String" values (either for key1 or key2)
3. Save into the app settings in Azure, under `AzureWebJobsStorage`
   - You can access this in the VS Code Azure extension > Function App > choose-your-own-adventure-demo-flex > Application Settings

### Example cURL request against deployed app

1. Go to choose-your-own-adventure-demo-flex > Functions > App > Keys, and copy the value from "default"
2. Replace `<redacted>` with the key value:

```bash
curl -L "https://choose-your-own-adventure-demo-a5anercqfqdpfggr.canadacentral-01.azurewebsites.net/api/twilioHandler?code=<redacted>" \
  -H "Content-Type: application/json" \
  --data '{"name": "World"}'
```

Expected response:
```
Hello, World. This HTTP triggered function executed successfully.
```

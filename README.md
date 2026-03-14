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
4. (Optional) Start Azurite storage emulator — only needed once `AzureTableStateStore` is implemented (currently a stub). For now, use `STATE_BACKEND=memory` in `local.settings.json`:
   ```bash
   docker run -p 10000:10000 -p 10001:10001 -p 10002:10002 mcr.microsoft.com/azure-storage/azurite azurite --disableTelemetry
   ```

## Running Locally

1. Start the Azure Function - you will see a stream of logs in this terminal session:
   ```bash
   make func-run
   ```
2. In a separate terminal session, trigger the function:
   ```bash
   curl -X POST http://localhost:7071/api/twilioHandler \
     --data 'Body=hello&From=%2B15550000001'
   ```

If it succeeds, you'll see a message output

Note, the subsequent instructions walk through more realistic flows.  Above `POST` request is just to show a single simple API interaction.

## Running Tests

Unit tests (no credentials needed):
```bash
make test
```

### Integration Tests

Integration tests are split into local (no server required) and remote (hit real services).

| Command | What it does |
|---|---|
| `make test-twilio` | Twilio SMS tests — sends real SMS, requires credentials |
| `make test-azure` | Azure Functions host tests — requires `make func-run` |
| `make test-integration` | All remote integration tests |
| `make test-all` | Unit + all integration tests |

**Twilio SMS setup** — sends actual SMS messages to a test number:
1. Copy `.template.env` to `.env` and fill in your Twilio credentials
2. Run `make test-twilio`

As it runs and if it's succeeding, you'll see something like:

```text
Sent (SID: SM05531c6d6f98aac52338542b68b7fff3)
Waiting 5s...
Sending: You have an appointment in 5 seconds
Sent (SID: SM49b05ad155691131b05065b5e790b233)
...
```

## Deployment via GitHub Actions

Set the repo Actions secret: `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` (found in Azure portal > Function App > "Get Publish Profile")

Note, this is likely already set in [Repo > Settings > Secrets and Variables > Actions](https://github.com/CivicTechAtlanta/proj-ga-court-reminders/settings/secrets/actions).  Including this section so we explicitly call it out for future maintainers

Deployment is handled by the GitHub Action [deploy_to_azure_functions.yml](.github/workflows/deploy_to_azure_functions.yml)

## Running in Cloud

### Setup

1. Go to Storage Account "chooseyourownadventure" > Security + Networking > Access Keys
2. Copy one of the "Connection String" values (either for key1 or key2)
3. Save into the app settings in Azure, under `AzureWebJobsStorage`
   - You can access this in the VS Code Azure extension > Function App > choose-your-own-adventure-demo-flex-eus > Application Settings

### Example cURL request against deployed app

Once the Azure function is deployed, get the Invoke URL by running:

```bash
func azure functionapp list-functions choose-your-own-adventure-demo-flex-eus --show-keys
```

Output will look like:

```
Functions in choose-your-own-adventure-demo-flex-eus:
    twilioHandler - [httpTrigger]
        Invoke url: https://choose-your-own-adventure-demo-flex-eus-dpaedjd2evcxhcd5.eastus-01.azurewebsites.net/api/twiliohandler?code=<your-key>
```

Copy the full `Invoke url` value. In the cURL below, replace `<redacted>` with the `code=...` query parameter value from that URL.

```bash
curl -L "https://choose-your-own-adventure-demo-flex-eus-dpaedjd2evcxhcd5.eastus-01.azurewebsites.net/api/twiliohandler?code=<redacted>" \
  --data 'Body=hello&From=%2B15550000001'
```

Expected response:
```xml
<Response><Message>Welcome to the GA Court Reminder demo - which scenario do you want to play out?

(1) 7, 3, 1 countdown
(2) Missed + Warrant [Unavailable atm]</Message></Response>
```

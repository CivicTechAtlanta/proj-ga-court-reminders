# proj-ga-court-reminders

## Prerequisites

(Shaun Mosley can invite to these if needed...DM him in Slack)

Invite to Azure directory: https://portal.azure.com/?feature.msaljs=true#settings/directory
- Domain: devopscivictechatlanta.onmicrosoft.com

Azure Subscription (this is a child of the above directory)
- Name: Georgia Court Reminders Demo

Invite to Twilio account
- Account Name: Georgia Court Reminders Demo

## Local Environment Setup

1. Install VS Code Extensions

These are managed in the file: [.vscode/extensions.json](.vscode/extensions.json)

When you open this project in VS Code, if you don't have one of the extensions listed above, there should be a pop-up asking you if you want to install recommended extensions

1. Install Azure CLI

Assuming Mac for instructions below

```bash
# Install via brew
brew update && brew install azure-cli

# Check installed properly
az --version
```

1. Log in to Georgia Court Reminders Demo Azure subscription

```bash
az login
```

It will take you to a web browser to log in.  Once you log in, make sure to choose the Azure subscription listed in the [Prerequisites](#prerequisites) section

1. Install uv for Python environment management

Follow instructions here: https://docs.astral.sh/uv/#installation

```bash
# Check uv is installed
uv --version
```

## Run app locally

Option 1: with uv

```bash
uv sync

# Run via "flask"
uv run flask run --port 8000

# Run via "python"
uv run python app.py
```

Option 2: with Docker
- Note, using "podman" here because that's what Brent has installed on his laptop.  Can probably swap out "docker" for "podman"

```bash
podman build -t court-reminders .
podman run -p 8000:8000 court-reminders
# then go to http://localhost:8000
```

## Spin up Azure Infra

(If needed...this infrastructure may already be live - if so, you can skip this step)

```bash
# Login and set subscription
az login
az account set --subscription "4848da1c-a0e9-4a1d-be4f-3e90c6f2ef9b"

# Create resource group
az group create --name rg-courtreminders-dev --location eastus

# Deploy the Bicep template
az deployment group create \
  --resource-group rg-courtreminders-dev \
  --template-file infra/main.bicep \
  --parameters environmentName=dev
```

## Tear down Azure Infra

(If needed)

Note, everything being deployed rolls up to a named resource group, so when we delete that resource group, it destroys all infrastructure tied to it

```bash
az group delete --name rg-courtreminders-dev --yes
```

## Deploy App to Azure

```bash
# Get the login token
az acr login --name acrcourtremindersdev --expose-token

# This outputs a JSON with accessToken. Use it with podman:
podman login acrcourtremindersdev.azurecr.io \
  --username 00000000-0000-0000-0000-000000000000 \
  --password <accessToken from above>

az acr build --registry acrcourtremindersdev --image court-reminders:latest .

# Update the app to use your image
az containerapp update \
  --name ca-courtreminders-dev \
  --resource-group rg-courtreminders-dev \
  --image acrcourtremindersdev.azurecr.io/court-reminders:latest
```

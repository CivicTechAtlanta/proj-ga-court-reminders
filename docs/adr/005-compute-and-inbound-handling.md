# ADR-005: Compute platform and inbound message handling

## Status

Accepted

## Context

The court reminder system requires compute to handle three distinct workloads:

1. **Inbound message handling** - respond to incoming SMS messages in near-real-time
2. **Outbound reminder dispatch** - send scheduled reminders at configured intervals before court dates
3. **Daily case check** - poll for case updates, evaluate state, and trigger messages as needed

The system is built and maintained by a small volunteer civic-tech team. Compute infrastructure should be low-cost, low-maintenance, and easy to deploy via GitHub Actions.

Azure Functions are stateless by default - each invocation has no memory of previous calls. This is a feature, not a limitation: the three workloads are all event-driven (HTTP request, timer tick) and require no persistent in-process state. Conversation state is managed externally in Table Storage per [ADR-002](002-conversation-state-storage.md).

Two sub-decisions are covered here:
1. **What compute platform** hosts the functions
2. **How inbound messages reach the function** - webhooks vs. polling

### Options considered: compute platform

| Option | Pros | Cons |
|---|---|---|
| **Azure Functions - Linux Consumption** | Serverless - scales to zero, no idle cost; event-driven model maps naturally to all three workloads (HTTP trigger for inbound, timer trigger for scheduled/daily); free tier (1M executions/month) covers our scale; native integration with Azure Table Storage, managed identity, and other Azure services; deploys cleanly via GitHub Actions | Cold start latency on inbound messages (typically <1s - acceptable for SMS but not ideal) |
| **Azure Functions - Flex Consumption** | All benefits of Linux Consumption plus virtual network integration, faster cold starts, and per-function scaling; scales to zero like Consumption | Not yet selected - planned upgrade once initial deployment is stable; slightly more complex configuration |
| **Azure App Service** | Always-on - no cold start; familiar web app model; easy to host a persistent polling loop | Always-on means always paying - free tier (F1) is limited and not suitable for production; more operational overhead than Functions for an event-driven workload |
| **Azure Container Apps** | More control over runtime; supports long-running processes | More complex to configure and deploy; overkill for our workload; higher operational burden for a volunteer team |
| **Azure VM** | Full control; can run persistent polling loops | Highest operational burden - patching, uptime monitoring, SSH access; not serverless; costs accrue whether or not the system is active; explicitly ruled out during architecture review (FigJam 2026.02.11) |

### Options considered: inbound message handling

| Option | Pros | Cons |
|---|---|---|
| **Webhooks (HTTP trigger)** | Real-time - response sent immediately on message receipt; no wasted API calls; natural fit for Azure Functions HTTP trigger; clean request/response model matches Twilio's expected TwiML response; response latency is imperceptible to the user | Requires a publicly accessible HTTPS endpoint - local development needs ngrok or equivalent to expose the Function |
| **Polling (timer trigger)** | Simpler local development - no public endpoint needed; easier to replay and debug a batch of messages | Artificial latency up to the poll interval; wasted API calls when no messages arrive; response latency is noticeable to users if poll interval is more than a few seconds; awkward request/response model - Twilio expects an immediate TwiML reply, polling breaks this contract |

### Local development with webhooks

Webhooks require a publicly accessible HTTPS endpoint during local development. The standard approach is ngrok, which creates a secure tunnel from a public URL to a local port. The workflow is:

1. Start the Azure Function locally via `func start`
2. Run `ngrok http 7071` to expose the local port
3. Update the Twilio webhook URL in the console to the ngrok URL
4. Inbound messages route through ngrok to the local Function in real time

This adds a setup step for local development but is a well-understood pattern with good tooling support. ngrok's free tier is sufficient for development use.

### Twilio's request/response model
Twilio expects an immediate TwiML (XML) response from the webhook endpoint containing the reply message. This maps cleanly to an Azure Functions HTTP trigger - receive the POST, process the message, return TwiML. Polling breaks this contract entirely since there is no active HTTP connection to respond on; a polling-based approach would require a separate Twilio API call to send the reply, adding latency and complexity.

## Decision

### Compute platform
Azure Functions on the Linux Consumption plan initially, with a planned migration to Flex Consumption in the near term.

The three workloads map cleanly to Azure Functions trigger types:
- HTTP trigger for inbound message handling
- timer trigger for outbound reminder dispatch
- daily case checks

The free tier comfortably covers our expected volume. The serverless model eliminates idle infrastructure cost and operational overhead, which matters for a volunteer team with no dedicated ops capacity.

**Linux Consumption** is the starting point - it is the simplest to provision, well-documented, and sufficient for initial development and demo use. Cold start latency is acceptable for SMS at this stage.

**Flex Consumption** is the planned next step once the initial deployment is stable. It retains the scale-to-zero model while addressing cold start latency and adding virtual network integration support. The migration requires no application code changes - only infrastructure configuration updates.

Azure App Service was the main alternative considered. Its always-on model avoids cold starts but introduces cost and operational overhead that isn't justified at our scale.

### Inbound message handling

Webhooks via Azure Functions HTTP trigger.

The real-time response model is the right fit for SMS conversations - users expect near-immediate replies, and the polling latency is both noticeable and unnecessary. Webhooks map cleanly to the HTTP trigger model Azure Functions already supports, and the Twilio request/response contract (receive POST, return TwiML) is a natural fit. The ngrok local development requirement is minor friction that the team is comfortable accepting.

## Consequences

**Easier:**
- No infrastructure to manage between deployments - the platform handles scaling, availability, and runtime patching.
- GitHub Actions deployment is well-supported via the Azure Functions action.
- All three workloads deploy as functions within the same Function App, sharing configuration, managed identity, and the existing storage account (per [ADR-002](002-conversation-state-storage.md)).
- Response latency is imperceptible - the reply TwiML is returned in the same HTTP response that Twilio is already waiting on.
- No separate outbound API call needed to send replies - the response body is the message.
- Clean local development loop once ngrok is configured - inbound test messages route directly to the local Function.

**Harder:**
- Cold starts on Linux Consumption are a known limitation. The planned migration to Flex Consumption addresses this - it is an infrastructure-only change with no impact on application code. Until then, cold start latency on inbound messages is acceptable for SMS.
- Local development requires the Azure Functions Core Tools and Azurite (local storage emulator) to replicate the runtime environment.
- Local development requires ngrok (or equivalent). The ngrok URL changes on each restart unless using a paid ngrok account with a fixed domain - the Twilio webhook URL needs to be updated each session. This should be documented in the project README.
- The Azure Function endpoint must be secured - Twilio signs its webhook requests and the Function should validate the `X-Twilio-Signature` header to reject spoofed requests.

**Relationship to other ADRs:**
- The Function App's storage account is shared with conversation and case state per [ADR-002](002-conversation-state-storage.md).
- The tree-walking engine runs within the HTTP trigger function per [ADR-003](003-message-flow-definition-format.md).
- The daily case check and reminder dispatch timer triggers are documented in [ADR-006](006-daily-check-and-cadence.md).

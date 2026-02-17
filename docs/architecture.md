# Architecture

High-level architecture for the GA Court Reminders system.

> See the [FigJam board](https://www.figma.com/board/Iy3apztPLkVpphvhcbO9q3/2025.11-Georgia-Court-reminders?node-id=109-594&t=9oD6U3qNmy7vGaTx-1) for the visual diagram

## Overview

The system sends automated court-date reminders via SMS using Twilio, hosted on Azure Functions

## Components

- **Azure Functions** - Serverless compute hosting all workloads ([ADR-005](adr/005-compute-and-inbound-handling.md))
  - **HTTP trigger** - receives inbound SMS via Twilio webhooks, runs the conversation engine, returns TwiML
  - **Timer triggers** - daily case check and reminder dispatch on a configurable cadence ([ADR-006](adr/006-daily-check-and-cadence.md))
- **Twilio** - SMS gateway for sending and receiving messages
- **Conversation Engine** - Manages choose-your-own-adventure message flows ([ADR-003](adr/003-message-flow-definition-format.md))
  - **YAML flow definitions** - declarative conversation trees in `docs/flows/`
  - **Tree-walking engine** - interprets YAML flows, routes user replies, manages branching and reprompts
- **Azure Table Storage** - Persists conversation state and case data ([ADR-002](adr/002-conversation-state-storage.md))
  - **ConversationState table** - per-user conversation position, updated on every inbound message
  - **CaseQueue table** - per-case state for the daily check loop (court dates, reminders sent, grace periods)
- **Cadence configuration** - checked-in config (`config/settings.yml`) controlling reminder thresholds and time units ([ADR-006](adr/006-daily-check-and-cadence.md))
- **Demo strategy pattern** - pluggable scenario selection with mock court data ([ADR-004](adr/004-demo-scenario-data-and-selection.md))

## Data model

See [`docs/data-model.md`](data-model.md) for the full table schemas.

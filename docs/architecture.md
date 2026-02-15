# Architecture

High-level architecture for the GA Court Reminders system.

> See the [FigJam board](https://www.figma.com/board/Iy3apztPLkVpphvhcbO9q3/2025.11-Georgia-Court-reminders?node-id=109-594&t=9oD6U3qNmy7vGaTx-1) for the visual diagram

## Overview

The system sends automated court-date reminders via SMS using Twilio, hosted on Azure Functions

## Components

- **Azure Function** -- HTTP-triggered function handling Twilio webhooks
- **Twilio** -- SMS gateway for sending and receiving messages
- **Conversation Engine** -- Manages choose-your-own-adventure message flows

# Data model

This document describes the Azure Table Storage schema used by the system. See [ADR-002](adr/002-conversation-state-storage.md) for the storage decision rationale.

## Table: `ConversationState`

Per-user conversation position, written on every inbound message.

| Field | Type | Notes |
| --- | --- | --- |
| `PartitionKey` | string | Phone number (E.164 format, e.g. `+14045550123`) |
| `RowKey` | string | Fixed value `"state"` |
| `current_step` | string | Current node ID in the flow YAML |
| `flow_id` | string | Which flow the user is currently in (e.g. `court_reminder_v1`) |
| `context` | JSON string | Template variables: `first_name`, `court_name`, `court_date`, `court_time`, `court_phone` |
| `updated_at` | datetime | Timestamp of last write - used for TTL cleanup |

## Table: `CaseQueue`

Per-case state for the daily check loop, written by the timer trigger.

| Field | Type | Notes |
| --- | --- | --- |
| `PartitionKey` | string | Phone number (E.164 format) |
| `RowKey` | string | Case ID from source system |
| `status` | string | `active`, `paid`, `warrant` |
| `original_court_date` | datetime | Original scheduled court date |
| `rescheduled_court_date` | datetime or null | Set when court date is rescheduled within grace period |
| `grace_period_start` | datetime or null | Set when original court date is missed; grace period expires 30 days after this value |
| `last_reminder_sent` | string or null | Threshold value of last reminder sent (e.g. `"7"`) - used to resume partial cadence after reschedule |
| `updated_at` | datetime | Timestamp of last write |

`last_reminder_sent` is the key field for the partial cadence resume logic (per [ADR-006](adr/006-daily-check-and-cadence.md)) - on reschedule, the system evaluates which thresholds are still in the future relative to the new court date and skips any that are at or below `last_reminder_sent`.

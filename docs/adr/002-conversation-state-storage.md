# ADR-002: Conversation state storage

## Status

Accepted

## Context

The court reminder system uses a choose-your-own-adventure SMS flow where each user progresses through a conversation tree. We need to persist per-user conversation state (current scenario, current step, court date/timestamp) between incoming messages so responses are context-aware.

Azure Functions are stateless by default - each invocation has no memory of previous calls. We need a storage layer that:

- Persists state across function invocations
- Supports lookup by phone number (the natural key for SMS conversations)
- Is simple enough for a volunteer civic-tech team to operate
- Stays within free-tier or low-cost Azure resources

### Options considered

| Option | Pros | Cons |
|---|---|---|
| **Azure Table Storage** | Serverless, cheap (free tier covers our scale), native Azure SDK, key-value fits our access pattern | No relational queries, limited indexing |
| **Azure Cosmos DB** | Globally distributed, flexible querying | Overkill for our scale, more expensive, complex pricing model |
| **SQLite on Azure Files** | Familiar SQL interface, zero cost | Concurrent write contention with Functions, operational burden to manage the file mount |
| **In-memory (dict)** | Zero setup | State lost on every cold start - unusable for real conversations |

## Decision

Use **Azure Table Storage** with the following schema:

- **Table name:** `conversationstate`
- **PartitionKey:** phone number (e.g. `+14045551234`)
- **RowKey:** fixed string `"current"` (one row per user, overwritten on each transition)
- **Columns:**
  - `scenario` (str) - current scenario: `"home"`, `"scenario_1"`, `"scenario_2"`
  - `step` (str) - current step within the scenario (e.g. `"welcome"`, `"countdown_7min"`, `"missed"`)
  - `court_datetime` (str, ISO 8601, nullable) - simulated court date used for countdown messages

Example data:

PartitionKey | RowKey  | scenario   | step           | court_datetime
------------ | ------- | ---------- | -------------- | --------------------
+14045551234 | current | scenario_1 | countdown_7min | 2026-03-11T14:30:00Z
+14045550000 | current | home       | welcome        | null

Note on RowKey = "current":
- The single-row-per-user pattern (RowKey="current", overwrite on transition) is chosen because our only access pattern is "look up current state by phone number." We never need to query across users or replay history at this stage.
- Including this as a placeholder in case we decide in the future to build in audit logging on the Azure side (rather than Twilio).  In this case, we would set the RowKey to be a timestamp

For local development, Azure Table Storage is emulated via [Azurite](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite) (same Docker container already used for blob storage, port 10002).

## Consequences

- **Easier:** No additional infrastructure to provision - reuses the storage account Azure Functions already requires. Simple key-value API maps cleanly to "look up state by phone number." Azurite emulates Table Storage locally on the same port already in use.
- **Harder:** No relational queries - if we later need to query across users (e.g. "all users with a court date tomorrow"), we'll need a secondary index or a different storage layer for that use case. Full conversation history is not retained; if audit logging becomes a requirement, a separate append-only table should be added.

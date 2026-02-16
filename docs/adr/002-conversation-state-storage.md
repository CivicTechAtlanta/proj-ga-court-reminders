# ADR-002: Conversation state storage

## Status

Proposed

## Context

The court reminder system uses a choose-your-own-adventure SMS flow where each user progresses through a conversation tree. We need to persist per-user conversation state (current step, selected options, court date info) between incoming messages so responses are context-aware.

Azure Functions are stateless by default — each invocation has no memory of previous calls. We need a storage layer that:

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
| **In-memory (dict)** | Zero setup | State lost on every cold start — unusable for real conversations |

## Decision

*To be decided by the team.*

<!-- Recommended: Azure Table Storage. It's the simplest option that meets all requirements, costs effectively nothing at our scale, and pairs naturally with Azure Functions (same storage account). Phone number as PartitionKey gives us fast lookups. -->

## Consequences

*To be filled in after the decision is made.*

<!-- If Azure Table Storage:
- **Easier:** No additional infrastructure to provision — reuses the storage account Azure Functions already requires. Simple key-value API maps cleanly to "look up state by phone number."
- **Harder:** No relational queries — if we later need to query across users (e.g., "all users with a court date tomorrow"), we'll need a secondary index or a different approach for that use case. -->

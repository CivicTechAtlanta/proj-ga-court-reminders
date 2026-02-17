# ADR-002: Conversation state storage

## Status

Proposed

## Context

The court reminder system uses a choose-your-own-adventure SMS flow where each user progresses through a conversation tree. We need to persist per-user conversation state (current step, selected options, court date info) between incoming messages so responses are context-aware.

Azure Functions are stateless by default - each invocation has no memory of previous calls. We need a storage layer that:
- Persists state across function invocations
- Supports lookup by phone number (the natural key for SMS conversations)
- Is simple enough for a volunteer civic-tech team to operate
- Stays within free-tier or low-cost Azure resources

**Dependency on ADR-003:** The scope of state that needs to be persisted depends on the outcome of ADR-003 (Message Flow Definition Format). If Twilio Studio is adopted, conversation position is managed by Studio's own execution context and this storage layer need only persist court date data and user outcomes. If YAML config is adopted, this layer must track each user's position in the conversation tree - every inbound message triggers a read-modify-write cycle and the storage choice carries more weight.

Either way, a storage layer is required. The options below are evaluated against the heavier YAML-engine scenario; all remain valid (and simpler) under Twilio Studio.

**Dependency on ADR-006:** The daily case check (ADR-006) requires additional fields beyond conversation state - specifically court date tracking, rescheduled dates, and grace period data. These are stored in the same Table Storage account but in a separate table from conversation state. See [`docs/data-model.md`](../data-model.md) for the full table schemas.

### Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| **Azure Table Storage** | Serverless, free tier covers our scale, native Azure SDK, key-value fits our access pattern, reuses existing Functions storage account | No relational queries, limited indexing - cross-user queries (e.g. "all users with court date tomorrow") would require a secondary approach |
| **Azure Durable Functions** | State is implicit in code - no storage schema to design; conversation flow expressed as sequential code rather than a manual state machine; built-in `wait_for_external_event` fits SMS reply pattern well | Replay-based execution model has a steep learning curve and non-linear debugging; higher conceptual and operational burden for a volunteer team; uses Table Storage + Blobs under the hood anyway; partially overlaps with ADR-003 scope |
| **Azure Cosmos DB** | Flexible querying, free tier (1000 RU/s, 25GB) would cover our scale | Significant operational complexity relative to our needs; overkill for a key-value access pattern with no relational query requirements |
| **Azure SQL** | Familiar SQL interface, relational querying if needed | Free tier limited and being retired; relational model is unnecessary overhead for a key-value access pattern; adds infra complexity with no benefit at our scale |
| **Azure Blob Storage (JSON per user)** | Free tier is generous, dead simple, reuses existing storage account | Concurrent write risk - rapid successive messages from the same user could cause race conditions on blob updates |
| **SQLite on Azure Files** | Familiar SQL interface, zero cost | Concurrent write contention with stateless Functions invocations is a fundamental architectural mismatch, not just an operational inconvenience |
| **In-memory (dict)** | Zero setup | State lost on every cold start - unusable for real conversations |

## Decision

Azure Table Storage.

It is the simplest option that meets all requirements under both ADR-003 scenarios. Phone number as `PartitionKey` gives fast, direct lookups - exactly the access pattern SMS conversations require. It reuses the storage account Azure Functions already provisions, so there is no additional infrastructure to manage and the marginal cost at our volume is effectively zero.

Azure Durable Functions is the most architecturally interesting alternative - its `wait_for_external_event` primitive maps naturally to SMS conversations - but the replay-based execution model introduces meaningful complexity for a volunteer team, and it uses Table Storage under the hood anyway. If ADR-003 resolves to YAML config, Durable Functions is worth revisiting as a flow engine option, but that evaluation belongs in ADR-003.

### Table schema

See [`docs/data-model.md`](../data-model.md) for the full table schemas.

## Consequences

**If ADR-003 resolves to YAML config (heavier usage):**
- Every inbound message triggers a read-modify-write on the `ConversationState` row. At our expected volume this is well within Table Storage's free tier, but the application code must handle this cycle reliably on every invocation.
- Schema evolution requires care - Table Storage is schemaless, so adding new fields is easy, but code must handle missing fields gracefully for rows written before a schema change.
- No relational queries across users. Cross-user queries (e.g. "all users with a court date tomorrow") should be handled separately - options include logging state changes to Blob Storage or surfacing data through a reporting pipeline.

**If ADR-003 resolves to Twilio Studio (lighter usage):**
- `ConversationState` becomes a simple record store for court date data and user outcomes. The read-modify-write pattern is less frequent and the operational burden is minimal.
- The same storage account and schema can be retained if ADR-003 later migrates from Studio to YAML config - no storage migration required.

**Either way:**
- No additional infrastructure to provision. The Functions storage account is already required, so Table Storage comes along for free.
- TTL-style cleanup (expiring stale `ConversationState` rows after a court date passes) can be handled with a simple scheduled Function that deletes rows older than N days. `CaseQueue` rows are self-cleaning via terminal state removal (per ADR-006).
- The `CaseQueue` table is append-light but read-heavy during the daily check loop - all active cases are read on every timer invocation. At our expected volume this is well within free tier limits.

**Relationship to other ADRs:**
- Both tables share the storage account that Azure Functions already requires per [ADR-005](005-compute-and-inbound-handling.md).
- The `ConversationState` schema is driven by the flow engine per [ADR-003](003-message-flow-definition-format.md).
- The `CaseQueue` schema is driven by the daily check logic and cadence configuration per [ADR-006](006-daily-check-and-cadence.md).

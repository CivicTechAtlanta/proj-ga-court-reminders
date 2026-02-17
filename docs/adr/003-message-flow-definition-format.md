# ADR-003: Message flow definition format

## Status

Proposed

## Context

The system implements a choose-your-own-adventure conversation flow over SMS. Users receive prompts, reply with a choice (e.g., "1" or "2"), and the system routes them to the next step. We need a way to define these conversation trees that is:

- Version-controllable alongside the code
- Expressive enough to handle branching, looping, and conditional logic
- Testable - we should be able to validate flows without sending real SMS
- Maintainable by developers on a volunteer civic-tech team

Flow definitions will be authored and maintained by developers only. Non-developer editing is not a requirement. The system must handle unexpected reply patterns (e.g., free text, out-of-range inputs) deterministically - LLM-based interpretation is out of scope.

### Options considered

| Option | Pros | Cons |
|---|---|---|
| **YAML/JSON config files** | Flow definitions are data, not code - separates conversation logic from application code; human-readable and easy to review in PRs; testable by loading config and simulating user choices; no additional vendor dependency or cost | Requires building and maintaining a tree-walking engine; expressiveness is limited for complex conditional logic; unexpected-reply handling must be defined in the engine layer |
| **Hardcoded Python** | Full language expressiveness; easiest to test; no parser or engine to build; unexpected-reply handling is natural in code; no additional cost or dependency | Flow logic coupled to application code - harder to read, review, and modify flows in isolation; changes require code deploys; flow structure less visible to someone unfamiliar with the codebase |
| **Twilio Studio** | Visual flow builder; hosted by Twilio so no engine to build | Flow definitions live outside Git - no PR review, no automated testing without Twilio account access, no CI/CD integration; custom logic requires Twilio Functions (Node.js), not our Python codebase; $0.0025 per flow execution on top of SMS costs; no-code builder provides no advantage for a developer-only team |
| **Twilio Studio + Conversations API** | Adds human agent handoff capability | All cons of Twilio Studio plus additional complexity and cost; overkill unless human handoff is required |
| **Database-driven (admin UI)** | Real-time updates without deploys | Significant upfront build cost; harder to version-control; overkill for our scale and team |

### Key trade-off: YAML config vs. hardcoded Python

With non-developer editing off the table, the decision is essentially: **should flow definitions be data or code?**

**YAML config** enforces a clean separation between flow definition and application logic. Flows are readable as standalone documents, diffs are meaningful in PRs, and the engine can be tested independently of any specific flow. The cost is building and owning a tree-walking engine.

**Hardcoded Python** skips the engine entirely and gets full language expressiveness for free. A well-structured Python module with a clear boundary can be just as readable as YAML. The cost is that flow logic lives inside the codebase rather than alongside it - someone new to the project has to read code to understand what the flow does.

Twilio Studio is not a strong fit for a developer-only team with a Python codebase and Git-based workflow. Its primary advantage is no-code accessibility, which is not a requirement here.

## Decision

YAML config files.

The separation of flow definitions from application code is worth the cost of building a tree-walking engine. As flows evolve - new court types, updated messaging, A/B variants - having flow logic in version-controlled YAML makes changes reviewable, diffable, and deployable independently of application code changes. The engine itself is a small, well-scoped component that can be unit tested in isolation.

Hardcoded Python is a legitimate alternative and the right choice if the conversation trees remain simple and stable. If early implementation reveals that YAML expressiveness is insufficient for our branching and unexpected-reply handling logic, migrating to hardcoded Python is low-risk - the engine boundary makes it a contained swap.

## Consequences

**Easier:**
- Flow changes (updated messages, new branches, revised options) are isolated to YAML files - no application code changes required, clean PRs, easy to review.
- The tree-walking engine can be unit tested independently by simulating user input sequences against a config, with no Twilio account or live SMS required.
- Adding new flows (e.g., a different flow per court type, or the demo scenario selection menu per ADR-004) requires no code changes - just a new YAML file.

**Harder:**
- A tree-walking engine must be built and maintained. This is the primary ongoing cost of this decision.
- Complex conditional logic (e.g., branching based on court date proximity, county-specific messaging) may strain YAML expressiveness and require escape hatches into Python - these should be designed carefully to avoid the engine becoming a second application layer.
- Unexpected-reply handling (free text, out-of-range inputs) must be defined as a first-class pattern in the engine, not an afterthought.

**Relationship to other ADRs:**
- YAML config means Azure Functions own the full tree-walking engine and must track each user's position in the conversation tree on every inbound message. This is the heavier storage scenario described in [ADR-002](002-conversation-state-storage.md) - the read-modify-write cycle on Table Storage occurs on every reply.
- The tree-walking engine runs within Azure Functions per [ADR-005](005-compute-and-inbound-handling.md).

**Reference implementation:**
See [`docs/flows/court_reminder_v1.yml`](../flows/court_reminder_v1.yml) for a reference implementation of this schema and [`docs/flows/court_reminder_v1.md`](../flows/court_reminder_v1.md) for the annotated flow diagram.

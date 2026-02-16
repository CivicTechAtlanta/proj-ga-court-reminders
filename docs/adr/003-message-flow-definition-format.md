# ADR-003: Message flow definition format

## Status

Proposed

## Context

The system implements a choose-your-own-adventure conversation flow over SMS. Users receive prompts, reply with a choice (e.g., "1" or "2"), and the system routes them to the next step. We need a way to define these conversation trees that is:

- Easy for non-developers (legal aid staff, case managers) to review and edit
- Version-controllable alongside the code
- Expressive enough to handle branching, looping, and conditional logic
- Testable — we should be able to validate flows without sending real SMS

### Options considered

| Option | Pros | Cons |
|---|---|---|
| **Twilio Studio** | Visual drag-and-drop flow builder; no-code — non-developers can build and edit flows directly; built-in `Send & Wait for Reply` and `Split Based On` widgets map naturally to our branching pattern; hosted by Twilio so no engine to build or maintain; can connect to Conversations API for human handoff | Flow definitions live in Twilio's platform, not in our Git repo — harder to review in PRs and track changes; $0.0025 per flow execution on top of SMS costs; adds vendor lock-in beyond just the messaging layer; custom logic requires Twilio Functions (Node.js), not our Python codebase; testing requires Twilio account access |
| **Twilio Studio + Conversations API** | Combines Studio's visual builder with Conversations API's multi-channel threading; enables human agent handoff after automated flow completes; distinct message threads per interaction | More complex architecture; two Twilio products to learn and manage; Conversations API adds its own pricing; overkill unless we need human handoff or multi-channel support |
| **YAML/JSON config files** | Human-readable, easy to review in PRs; separates flow logic from application code; version-controlled; non-developers can edit with minimal training; no additional vendor dependency or cost; testable by loading config and simulating user choices | Limited expressiveness for complex logic; needs a custom parser/tree-walking engine to be built; non-developers still need basic Git/PR workflow to make changes |
| **Hardcoded Python** | Full language expressiveness; easy to test; no parser needed; no additional cost | Non-developers can't edit flows; changes require code deploys; flow logic tangled with application code |
| **Database-driven (admin UI)** | Non-developers can edit without PRs; real-time updates | Significant upfront build cost for the UI; harder to version-control; overkill for our current scale |

### Key trade-off: Twilio Studio vs. YAML config

The central question is whether to own the conversation engine or delegate it to Twilio:

- **Twilio Studio** is fastest to a working prototype — the visual builder handles branching natively with zero custom code. But it moves flow definitions out of our repo and into a vendor platform, making code review, automated testing, and CI/CD harder.
- **YAML config** keeps everything in Git and testable in our Python stack, but requires us to build and maintain a tree-walking engine.

A hybrid approach is also possible: start with Twilio Studio to validate flows quickly, then migrate to YAML once the conversation trees stabilize and we need tighter version control.

## Decision

*To be decided by the team.*

## Consequences

*To be filled in after the decision is made.*

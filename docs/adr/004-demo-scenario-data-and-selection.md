# ADR-004: Demo scenario data and selection

## Status

Proposed

## Context

For the MVP, the system demonstrates conversation flows using simulated court case data - there is no real court data source. We need to decide:

1. **Where mock scenario data lives** - how we define the fake case details (court dates, case types, locations) that get interpolated into messages
2. **How demo users select a scenario** - when someone texts the demo number, how do they end up in a specific scenario

The demo architecture uses a strategy pattern with pluggable scenario logic. Each scenario needs its own mock data to exercise different conversation paths (e.g., court date is tomorrow, court date is next week, missed court date).

In future versions (v2+), mock data will be replaced by real court case data from a manual upload or court system integration. The data layer should be easy to swap without rewriting scenario logic.

### Where mock data lives

| Option | Pros | Cons |
|---|---|---|
| **CSV files in repo** | Version-controlled; easy to review in PRs; natural tabular format for case data; same format likely used for real data in v2+; loader built now reusable later | Needs a loader; no built-in schema enforcement without a validation layer |
| **JSON/YAML fixture files in repo** | Version-controlled; readable; loads cleanly in both app and tests | Less natural for tabular data than CSV; another file format to maintain alongside flow YAML |
| **Hardcoded in each scenario class** | Simplest; no file I/O; data lives next to the logic that uses it | Mixes data with logic; harder to swap for real data later |
| **Seeded into storage (Table Storage)** | Exercises the real storage layer; closer to production architecture | More setup overhead; requires a seed script and storage dependency just to run locally |

A hybrid approach is also valid: CSV files as the source of truth, with an optional seed script that loads them into Table Storage for environments where you want to exercise the full stack end-to-end.

### Mock data validation

Regardless of where mock data lives, we need confidence that it conforms to a known schema (required fields, valid types, acceptable values). This becomes more important in v2+ when real data enters the system.

| Option | Pros | Cons |
|---|---|---|
| **Pydantic models** | Define a `CourtCase` model with typed fields and constraints; validates on load with clear error messages; likely coming in as a dependency anyway; the same model becomes the validation layer for real data in v2+ | Requires Python to validate - non-devs can't validate independently |
| **Pandera** | Schema validation for DataFrames; integrates with pytest | Pulls in pandas as a transitive dependency; heavier than Pydantic for our needs |
| **Great Expectations** | Full data quality framework; rich expectation library; generates validation reports | Its own ecosystem to learn and maintain; overkill for a small fixture set |
| **Plain pytest assertions** | Zero new dependencies | Ad-hoc; schema is implicit in test code rather than declared as a reusable model |

### How demo users select a scenario

| Option | Pros | Cons |
|---|---|---|
| **Initial SMS menu ("Reply 1 for X, 2 for Y")** | Self-contained; user discovers scenarios naturally; no external docs needed; menu is itself a flow definable in YAML per ADR-003 | Adds a routing step before the real flow; menu must be maintained as scenarios change |
| **Cheat-sheet shared alongside the demo number** | Zero code required; easy to update | Relies on users reading the doc before texting; easy to lose in a demo context |
| **Keyword trigger ("Text DEMO1 to start")** | Simple routing; no menu step | Users need to know keywords ahead of time |
| **Different phone numbers per scenario** | Clean separation; no routing logic needed | Costs more Twilio numbers; harder to manage |

## Decision

**Mock data location:** CSV files in `docs/flows/` alongside the flow definitions, with Pydantic validation on load.

CSV is the natural format for tabular case data and establishes a continuity path to v2+ - the loader and `CourtCase` Pydantic model built for mock data become the same artifacts used when real data enters the system. The `CourtCase` model defines the contract between the data layer and scenario logic; swapping mock CSV for a real data source in v2+ requires no changes to scenario code.

A seed script that loads CSV data into Table Storage is a valid optional companion for full-stack local testing, but CSV remains the source of truth.

**Scenario selection:** Initial SMS menu, defined as a YAML flow per [ADR-003](003-message-flow-definition-format.md).

The menu is self-contained - no external docs required - and it exercises the flow engine directly. Defining it as a YAML flow means it gets the same version control, diff, and test treatment as any other flow. The menu routes users into scenario-specific flows by setting their initial state and branching to the appropriate flow entry point.

## Consequences

**Easier:**
- Adding or modifying scenarios means editing a CSV file and updating the menu flow YAML - no application code changes required.
- The `CourtCase` Pydantic model is a first-class artifact from day one. When v2+ brings real data, the model already defines the expected schema and validation rules.
- The demo selection menu is testable the same way any other flow is tested - by simulating user input sequences against the YAML config, with no Twilio account required (per [ADR-003](003-message-flow-definition-format.md)).
- CSV files are readable and editable by anyone, which helps when designing new demo scenarios collaboratively.

**Harder:**
- The loader must parse CSV and instantiate validated `CourtCase` objects on startup - a small but real piece of infrastructure to build and maintain.
- The demo menu YAML must be kept in sync with available scenarios. Adding a new scenario means updating both the CSV data and the menu flow.
- If the demo menu grows beyond a handful of scenarios, the SMS menu UX degrades (long option lists don't work well over SMS). At that point a keyword trigger or cheat-sheet approach may be worth revisiting.

**Relationship to other ADRs:**
- The demo selection menu is a YAML flow and should be added to `docs/flows/` per [ADR-003](003-message-flow-definition-format.md).
- Scenario state (selected scenario, court case context) is persisted in Table Storage per [ADR-002](002-conversation-state-storage.md) - the `CourtCase` fields become part of the user's context row.

**Reference implementation:**
See [`docs/flows/court_reminder_v1.yml`](../flows/court_reminder_v1.yml) for an example of the flow schema that mock data feeds into.

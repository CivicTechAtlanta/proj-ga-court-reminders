# ADR-004: Demo scenario data and selection

## Status

Proposed

## Context

For the MVP, the system demonstrates conversation flows using simulated court case data — there is no real court data source. We need to decide:

1. **Where mock scenario data lives** — how we define the fake case details (court dates, case types, locations) that get interpolated into messages
2. **How demo users select a scenario** — when someone texts the demo number, how do they end up in "Scenario #1" vs. "Scenario #2" vs. the demo home screen

The demo architecture (see FigJam board, 2026.02.11) shows a strategy pattern at the bottom layer with pluggable scenario logic. Each scenario needs its own mock data to exercise different conversation paths (e.g., court date is tomorrow, court date is next week, missed court date).

In future versions (v2+), mock data will be replaced by real court case data from a manual upload or court system integration. The data layer should be easy to swap without rewriting scenario logic.

### Where mock data lives

| Option | Pros | Cons |
|---|---|---|
| **CSV files in repo** | Version-controlled; easy to review in PRs; non-devs can edit in Excel/Google Sheets and export; natural tabular format for case data | Needs a loader; no built-in schema enforcement without a validation layer |
| **JSON/YAML fixture files in repo** | Version-controlled; easy to review in PRs; readable by non-devs; loads cleanly in both the app and tests | Less natural for tabular data than CSV; another file format to maintain |
| **Hardcoded in each scenario class** | Simplest; no file I/O; data lives right next to the logic that uses it | Mixes data with logic; harder for non-devs to edit; harder to swap for real data later |
| **Seeded into storage (Table Storage / DB)** | Exercises the real storage layer; closer to production architecture | More setup overhead for a demo; requires a seed script and storage dependency just to run locally |

### Mock data validation

Regardless of where mock data lives, we need confidence that it conforms to a known schema (required fields, valid types, acceptable values). This becomes even more important in v2+ when real data enters the system.

| Option | Pros | Cons |
|---|---|---|
| **Pydantic models** | Define a `CourtCase` model in Python with typed fields and constraints; validates on load with clear error messages; zero new runtime — one dependency the project will likely want anyway; the same model becomes the validation layer for real data in v2+ | Requires Python to validate (non-devs can't validate independently) |
| **Pandera** | Schema validation for pandas/polars DataFrames; define column types, constraints, and checks as a schema class; integrates with pytest | Pulls in pandas as a transitive dependency; heavier than Pydantic for our current needs |
| **Great Expectations** | Full data quality framework; rich expectation library (`expect_column_values_to_not_be_null`, etc.); generates validation reports | Its own ecosystem to learn and maintain; overkill for a small fixture set |
| **Plain pytest assertions** | Load CSV/JSON in a test, assert on column names and value ranges; zero new dependencies | Ad-hoc; schema is implicit in test code rather than declared as a reusable model |

### How demo users select a scenario

| Option | Pros | Cons |
|---|---|---|
| **Initial SMS menu ("Reply 1 for X, 2 for Y")** | Self-contained; user discovers scenarios naturally; no external docs needed | Adds a routing step before the real flow; menu itself needs to be maintained |
| **Cheat-sheet shared alongside the demo number** | Zero code required; easy to update | Relies on users reading the doc; easy to lose track of |
| **Keyword trigger ("Text DEMO1 to start")** | Simple routing; no menu step | Users need to know the keywords ahead of time |
| **Different phone numbers per scenario** | Clean separation; no routing logic needed | Costs more Twilio numbers; harder to manage |

## Decision

*To be decided by the team.*

## Consequences

*To be filled in after the decision is made.*

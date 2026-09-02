# ADR-002: Docker Postgres simulates the production court case DB

## Status

Accepted, amended 2026-09-02: the Postgres no longer runs as its own compose
service. `CourtDatabaseStack` deploys it to Floci as an RDS Postgres instance,
seeded during `cdk deploy` by the same scripts (now under
`lambda/court_db/seed/postgres/`), and docker-compose.yml publishes Floci's
RDS proxy port (7001) so `make db-psql`, GUIs, and the integration tests reach
it from the host. The fidelity choices below are unchanged.

## Context

Reminders are driven in production by a T-SQL query against an Odyssey-style
SQL Server court case-management system (tblCase, tblCaseParty, tblPartyPhone,
tblCaseEvent, tblEvent, tblEventType, plus `dbo.fnGetLookupDescription`). We
cannot run that system locally, but development needs prod-shaped data to query
against instead of dates faked in-memory.

## Decision

Run Postgres locally (originally `postgres:17-alpine` via `docker-compose.yml`,
seeded on first start through the image's `/docker-entrypoint-initdb.d`
mechanism; since the amendment above, the RDS Postgres that Floci hosts,
seeded by the CDK deploy) from the scripts in `lambda/court_db/seed/postgres/`.

Fidelity choices, so the prod query runs near-verbatim (see the translation in
`db/queries/next_week_hearings.sql`):

- **Unquoted, prod-cased identifiers.** Postgres folds unquoted identifiers to
  lowercase on both DDL and query sides, so `tblCase`/`CaseID` written in SQL
  Server casing resolve unchanged. Rule: never quote an identifier in any SQL
  file here — one quoted `"CaseID"` in DDL would break every unquoted query.
- **A `dbo` schema** with database-level `search_path = dbo, public`, so
  `dbo.fnGetLookupDescription(...)` and bare table names both work. The
  function is implemented over a `tblLookup` table.
- **`timestamp` without time zone** mirrors SQL Server `datetime`, and the
  container runs `TZ=America/New_York` so `CURRENT_DATE` behaves like prod's
  court-local `GETDATE()`. The remaining T-SQL delta is date arithmetic only
  (`DATEADD(d,7,CONVERT(DATE,GETDATE()))` → `CURRENT_DATE + 7`).
- **Date-relative fixtures.** Event times are computed from `CURRENT_DATE` at
  first start, so the 7-days-out window matches immediately, and scenarios
  cover every filter in the query: window boundaries (inclusive lower,
  exclusive upper), phone-type filter, first-defendant-only join, a duplicate
  phone row collapsed by DISTINCT, and a case with daily hearings for 14 days.
  Data quality mirrors the benchmark database so downstream normalization
  gets exercised: phone numbers span E.164, parens/dots/dashes, bare digits,
  extension text, a format-variant duplicate DISTINCT cannot collapse, and
  garbage entries (placeholder text, truncated, empty); names include ALL
  CAPS, stray whitespace, suffixes and 'LAST, FIRST' jammed into one field,
  FNU/LNU placeholders, and mojibake; PhoneType is unconstrained and dirty
  ('Cell', 'CELL PHONE') so the query's case-sensitive filter visibly misses
  those rows; one courtroom code has no lookup row (CourtRoom returns NULL),
  and case numbers include a trailing space and an off-format value.

## Consequences

Easier: `make local-start` gives zero-config prod-shaped data; the prod query needs
only its date arithmetic translated; fixtures exercise every query filter, so
the expected result (11 rows, 12 without DISTINCT) doubles as a regression
check.

More difficult: it is still Postgres, not SQL Server — other T-SQL built-ins
would need translating, and SQL Server-specific behavior (locking hints,
collations) is not reproduced. Fixture dates freeze at first start, so the
7-days-out query goes stale roughly a week later; `make db-reset` re-seeds
and re-anchors. And identifier quoting is a standing trap: all SQL
against this database must leave identifiers unquoted.

# ADR-002: Docker Postgres simulates the production court case DB

## Status

Accepted, amended 2026-09-02: the Postgres no longer runs as its own compose
service. `CourtDatabaseStack` deploys it to Floci as an RDS Postgres instance,
seeded during `cdk deploy` by the same scripts (now under
`lambda/court_db/seed/postgres/`), and docker-compose.yml publishes Floci's
RDS proxy port (7001) so `./script/db/psql`, GUIs, and the integration tests reach
it from the host.

Amended 2026-09-16: this ADR previously claimed the reminder query's
`IN ('CELL','MOBILE')` is case-sensitive and so misses rows typed `'Cell'`.
That was only ever true of the Postgres simulation. SQL Server's default
collation (`SQL_Latin1_General_CP1_CI_AS`, confirmed on the 2022 server the
fixtures load into) compares case-insensitively, so in production those rows
*are* matched and those people *are* texted. #43 documented that divergence
and pinned it with an xfail; this amendment closes it instead: `PhoneType` is
now `citext` in the Postgres schema, which fixes the simulation rather than
the query — see the collation bullet below. The other fidelity choices are
unchanged.

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
- **A case-insensitive `tblPartyPhone.PhoneType`.** SQL Server compares
  strings under a case-insensitive collation, so prod's
  `IN ('CELL','MOBILE')` matches `'Cell'` too. Postgres `text` does not, and
  the gap is not cosmetic: it decides who gets a text message. Anyone whose
  `PhoneType` was keyed as `'Cell'` is reminded in production and would be
  invisible in local testing. The column is therefore converted to `citext`
  by its own seed script, `lambda/court_db/seed/postgres/04-phone-type-citext.sql`,
  which runs after the fixtures load, rather than by editing the base schema
  (the extension is created in `public`, so a re-seed's `DROP SCHEMA dbo`
  leaves it alone). `citext` reproduces the prod collation for `=`, `IN`, `DISTINCT` and `LIKE`
  while still storing and returning the original casing. Fixing the schema
  rather than the query keeps `db/queries/next_week_hearings.sql` a verbatim
  copy of what prod runs — rewriting it as `UPPER(pp.PhoneType) IN (...)`
  would change who prod texts, which is a decision for the court, not a
  simulation-fidelity fix. Note this is a per-column fix, not a
  database-wide one; see Consequences.
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
  ('Cell', 'CELL PHONE') — 'Cell' is matched on both engines now that the
  collation lines up, while 'CELL PHONE' is a different label, not a casing
  variant, and is missed on both; one courtroom code has no lookup row
  (CourtRoom returns NULL), and case numbers include a trailing space and an
  off-format value.

## Consequences

Easier: `./script/setup` gives zero-config prod-shaped data; the prod query needs
only its date arithmetic translated; fixtures exercise every query filter, so
the expected result (13 rows seven days out, 14 without DISTINCT) doubles as
a regression check — and it is now one number for both engines, which
`tests/test_court_db_seed_integration.py` asserts by loading the same fixtures
into a real SQL Server and comparing the two result sets row for row.

More difficult: it is still Postgres, not SQL Server — other T-SQL built-ins
would need translating, and SQL Server-specific behavior (locking hints) is
not reproduced. Collation fidelity is per-column, not database-wide: SQL
Server compares *every* string case-insensitively, whereas only
`tblPartyPhone.PhoneType` is case-insensitive here, because that is the one
column the reminder query filters on and so the one that decides who gets
texted. `tblCase.CaseNumber`, `tblEvent.CourtRoomCode` and `tblLookup`'s
columns are still case-sensitive in Postgres and case-insensitive in prod; a
fixture differing only in casing there would diverge the same way, and the
remedy is the same (make the column `citext`). Postgres also compares
trailing spaces that SQL Server ignores, which
`test_hearings_for_case_requires_an_exact_match_on_postgres` pins as a known
difference. Fixture dates freeze at first start, so the 7-days-out query goes
stale roughly a week later; `./script/db/reset` re-seeds and re-anchors
locally, and in AWS a weekly EventBridge rule does the same to the dev
database. And identifier quoting is a standing trap: all SQL against this
database must leave identifiers unquoted.

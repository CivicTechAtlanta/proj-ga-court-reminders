"""Seed the fixtures into a real SQL Server and compare with local Postgres.

Runs only when a SQL Server is reachable with these variables set, e.g. a
local container: COURT_MSSQL_HOST (default localhost), COURT_MSSQL_PORT
(default 1433), COURT_MSSQL_USER (default sa), COURT_MSSQL_PASSWORD
(required). The Postgres comparison additionally needs `. script/setup`.
"""

import os

import pytest

from court_db import DatabaseConfig, court_case_repository
from court_db.seed import load_fixtures
from court_db.sqlserver import SqlServerCourtCaseRepository

pytestmark = pytest.mark.integration_court_db


@pytest.fixture(scope="module")
def sqlserver_config():
    password = os.getenv("COURT_MSSQL_PASSWORD")
    if not password:
        pytest.skip("set COURT_MSSQL_PASSWORD to test against a SQL Server")
    config = DatabaseConfig(
        engine="sqlserver",
        host=os.getenv("COURT_MSSQL_HOST", "localhost"),
        port=int(os.getenv("COURT_MSSQL_PORT", "1433")),
        database="courtdb",
        user=os.getenv("COURT_MSSQL_USER", "sa"),
        password=password,
    )
    try:
        summary = load_fixtures(config)
    except Exception as exc:
        pytest.skip(f"SQL Server not reachable: {exc}")
    return config, summary


def test_loader_reports_the_expected_row_counts(sqlserver_config):
    _, summary = sqlserver_config
    assert summary["row_counts"] == {
        "tblLookup": 4,
        "tblEventType": 5,
        "tblParty": 18,
        "tblCase": 14,
        "tblCaseParty": 18,
        "tblPartyPhone": 21,
        "tblEvent": 6,
        "tblCaseEvent": 28,
    }


# Postgres returns 12 rows seven days out; SQL Server returns 13. The extra
# one is Whitfield's phone row typed 'Cell', which the reminder query's
# IN ('CELL','MOBILE') matches here and not on Postgres, because SQL Server's
# default collation is case-insensitive and Postgres compares case-sensitively.
# Predates the 7/3/1 ladder: the fixtures at the time of writing documented 11
# rows and this server returned 12. See test_sqlserver_matches_local_postgres.
SEVEN_DAY_ROWS = 13


def test_sqlserver_returns_one_more_row_than_postgres_seven_days_out(sqlserver_config):
    config, _ = sqlserver_config
    hearings = SqlServerCourtCaseRepository(config).upcoming_hearings()
    assert len(hearings) == SEVEN_DAY_ROWS
    dirty = [h for h in hearings if h.phone_type not in {"CELL", "MOBILE"}]
    assert [(h.case_number, h.phone_type) for h in dirty] == [
        ("CR-2026-000104", "Cell")
    ]


def test_sqlserver_fills_every_reminder_lead_time(sqlserver_config):
    """The 7/3/1 ladder the fixtures anchor, on the engine AWS actually runs.
    A zero here means a reminder threshold has nothing to fire on right after
    a seed. The three and one day counts match Postgres exactly; only the
    seven-day total carries the collation difference above."""
    config, _ = sqlserver_config
    repository = SqlServerCourtCaseRepository(config)
    counts = {days: len(repository.upcoming_hearings(days)) for days in (7, 3, 1)}
    assert counts == {7: SEVEN_DAY_ROWS, 3: 3, 1: 2}
    for days, case_number in (
        (7, "CR-2026-000112"),
        (3, "CR-2026-000113"),
        (1, "CR-2026-000114"),
    ):
        matching = [
            hearing
            for hearing in repository.upcoming_hearings(days)
            if hearing.case_number == case_number
        ]
        assert len(matching) == 1, (days, case_number)
        assert matching[0].phone_type == "CELL"


@pytest.mark.xfail(
    reason="SQL Server's case-insensitive default collation returns one row "
    "Postgres does not (see SEVEN_DAY_ROWS). Production is SQL Server, so the "
    "local Postgres simulation is the side that diverges. Not strict: a server "
    "with a case-sensitive collation would agree with Postgres and pass.",
    strict=False,
)
def test_sqlserver_matches_local_postgres(sqlserver_config):
    config, _ = sqlserver_config
    postgres = court_case_repository(DatabaseConfig.from_env(environ={}))
    try:
        postgres.ping()
    except Exception:
        pytest.skip("court database not running in Floci; run: . script/setup")

    def key(hearing):
        return (
            hearing.case_number,
            hearing.event_type,
            hearing.event_datetime.time(),
            hearing.court_room,
            hearing.phone_type,
            hearing.phone_number,
        )

    assert sorted(
        map(key, SqlServerCourtCaseRepository(config).upcoming_hearings())
    ) == sorted(map(key, postgres.upcoming_hearings()))


def test_sqlserver_ignores_trailing_spaces_in_case_number_lookups(sqlserver_config):
    config, _ = sqlserver_config
    repository = SqlServerCourtCaseRepository(config)
    # Both spellings match on SQL Server; only the padded one does on Postgres.
    assert len(repository.hearings_for_case("CR-2026-000103")) == 1
    assert len(repository.hearings_for_case("CR-2026-000103 ")) == 1

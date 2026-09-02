"""Seed the fixtures into a real SQL Server and compare with local Postgres.

Runs only when a SQL Server is reachable with these variables set, e.g. a
local container: COURT_MSSQL_HOST (default localhost), COURT_MSSQL_PORT
(default 1433), COURT_MSSQL_USER (default sa), COURT_MSSQL_PASSWORD
(required). The Postgres comparison additionally needs `make local-start`.
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
        "tblParty": 15,
        "tblCase": 11,
        "tblCaseParty": 15,
        "tblPartyPhone": 18,
        "tblEvent": 6,
        "tblCaseEvent": 25,
    }


def test_sqlserver_returns_the_documented_eleven_hearings(sqlserver_config):
    config, _ = sqlserver_config
    hearings = SqlServerCourtCaseRepository(config).upcoming_hearings()
    assert len(hearings) == 11


def test_sqlserver_matches_local_postgres(sqlserver_config):
    config, _ = sqlserver_config
    postgres = court_case_repository(DatabaseConfig.from_env(environ={}))
    try:
        postgres.ping()
    except Exception:
        pytest.skip("court database not running in Floci; run: make local-start")

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

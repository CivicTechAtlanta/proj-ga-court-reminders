"""Integration tests against the court database running in Floci.

These run only when the local stack is deployed (make local-start), through
the RDS proxy port docker-compose.yml publishes; otherwise each test skips
with a pointer to the command. They prove the wrapper
pulls the same rows as the canonical query in
db/queries/next_week_hearings.sql.
"""

from pathlib import Path

import pytest

from court_db import DatabaseConfig, court_case_repository
from court_db.postgres import PostgresCourtCaseRepository, open_connection

pytestmark = pytest.mark.integration_court_db

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_QUERY = REPO_ROOT / "db" / "queries" / "next_week_hearings.sql"


@pytest.fixture()
def repository():
    repo = court_case_repository()
    try:
        repo.ping()
    except Exception:
        pytest.skip("court database not running in Floci; run: make local-start")
    return repo


def test_factory_defaults_to_the_local_postgres_db(repository):
    assert isinstance(repository, PostgresCourtCaseRepository)
    assert repository.ping() is True


def test_upcoming_hearings_matches_the_canonical_query(repository):
    hearings = repository.upcoming_hearings(days_ahead=7)

    config = DatabaseConfig.from_env(environ={})
    with open_connection(config) as connection, connection.cursor() as cursor:
        cursor.execute(CANONICAL_QUERY.read_text())
        canonical = cursor.fetchall()

    assert [
        (h.case_id, h.case_party_id, h.case_number, h.event_datetime) for h in hearings
    ] == [(row[0], row[1], row[2], row[4]) for row in canonical]


def test_upcoming_hearings_respects_the_phone_type_filter(repository):
    # Phone NUMBERS stay dirty on purpose (ADR 002 seeds empty and garbage
    # values for downstream normalization); only the TYPE filter is strict.
    for hearing in repository.upcoming_hearings(days_ahead=7):
        assert hearing.phone_type in {"CELL", "MOBILE"}


def test_hearings_for_case_returns_all_dates_for_one_case(repository):
    upcoming = repository.upcoming_hearings(days_ahead=7)
    if not upcoming:
        pytest.skip("fixture dates have aged out; run: make db-reset")

    case_number = upcoming[0].case_number
    hearings = repository.hearings_for_case(case_number)

    assert hearings
    assert {hearing.case_number for hearing in hearings} == {case_number}

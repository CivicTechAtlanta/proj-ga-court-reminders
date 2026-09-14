"""Integration tests against the court database running in Floci.

These run only when the local stack is deployed (. script/setup), through
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
        pytest.skip("court database not running in Floci; run: . script/setup")
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


def test_every_reminder_lead_time_has_a_clean_case_to_fire_on(repository):
    """The 7/3/1 ladder the fixtures anchor, which is what `. script/db/reset`
    exists to refresh. A zero here means a reminder threshold would find
    nothing right after a seed."""
    ladder = {7: "CR-2026-000112", 3: "CR-2026-000113", 1: "CR-2026-000114"}
    counts = {days: len(repository.upcoming_hearings(days)) for days in ladder}
    if not any(counts.values()):
        pytest.skip("fixture dates have aged out; run: . script/db/reset")

    assert counts == {7: 12, 3: 3, 1: 2}
    for days, case_number in ladder.items():
        matching = [
            hearing
            for hearing in repository.upcoming_hearings(days)
            if hearing.case_number == case_number
        ]
        assert len(matching) == 1, (days, case_number)
        # One clean E.164 cell number each, so a threshold test has an
        # unambiguous number to assert the sender was handed.
        assert matching[0].phone_type == "CELL"
        assert matching[0].phone_number.startswith("+1404555011")


def test_upcoming_hearings_respects_the_phone_type_filter(repository):
    # Phone NUMBERS stay dirty on purpose (ADR 002 seeds empty and garbage
    # values for downstream normalization); only the TYPE filter is strict.
    for hearing in repository.upcoming_hearings(days_ahead=7):
        assert hearing.phone_type in {"CELL", "MOBILE"}


def test_hearings_for_case_returns_all_dates_for_one_case(repository):
    upcoming = repository.upcoming_hearings(days_ahead=7)
    if not upcoming:
        pytest.skip("fixture dates have aged out; run: . script/db/reset")

    case_number = upcoming[0].case_number
    hearings = repository.hearings_for_case(case_number)

    assert hearings
    assert {hearing.case_number for hearing in hearings} == {case_number}


def test_hearings_for_case_requires_an_exact_match_on_postgres(repository):
    # Fixture case 3 is stored with a trailing space. Postgres compares text
    # byte for byte; SQL Server ignores trailing spaces in `=`, so the same
    # lookup matches there (see test_court_db_seed_integration.py).
    assert repository.hearings_for_case("CR-2026-000103") == []
    hearings = repository.hearings_for_case("CR-2026-000103 ")
    assert len(hearings) == 1
    assert hearings[0].phone_type == "HOME"

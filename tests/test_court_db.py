"""Unit tests for the court_db access layer.

Database drivers are never imported: adapters accept an injected connect
callable, so these tests run without Postgres, SQL Server, or AWS.
"""

from contextlib import contextmanager
from datetime import datetime

import pytest

from court_db import DatabaseConfig, Hearing, court_case_repository
from court_db.postgres import PostgresCourtCaseRepository
from court_db.sqlserver import SqlServerCourtCaseRepository


SAMPLE_ROW = (
    101,
    202,
    "24-CR-00042",
    "Arraignment",
    datetime(2026, 9, 7, 9, 0),
    "Courtroom 3B",
    "CELL",
    "+14045550142",
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConnection:
    def __init__(self, rows):
        self.cursor_used = FakeCursor(rows)

    def cursor(self):
        return self.cursor_used

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_connect(rows):
    connection = FakeConnection(rows)

    @contextmanager
    def connect():
        yield connection

    return connection, connect


def local_config(engine="postgres"):
    return DatabaseConfig(
        engine=engine,
        host="localhost",
        port=7001,
        database="courtdb",
        user="court",
        password="court",
    )


@pytest.mark.parametrize(
    "repository_class", [PostgresCourtCaseRepository, SqlServerCourtCaseRepository]
)
def test_adapters_map_rows_to_hearings(repository_class):
    connection, connect = fake_connect([SAMPLE_ROW])
    repository = repository_class(local_config(), connect=connect)

    hearings = repository.upcoming_hearings(days_ahead=7)

    assert hearings == [
        Hearing(
            case_id=101,
            case_party_id=202,
            case_number="24-CR-00042",
            event_type="Arraignment",
            event_datetime=datetime(2026, 9, 7, 9, 0),
            court_room="Courtroom 3B",
            phone_type="CELL",
            phone_number="+14045550142",
        )
    ]
    (_, params) = connection.cursor_used.executed[0]
    assert params == {"days": 7}


@pytest.mark.parametrize(
    "repository_class", [PostgresCourtCaseRepository, SqlServerCourtCaseRepository]
)
def test_adapters_share_the_column_contract(repository_class):
    connection, connect = fake_connect([])
    repository_class(local_config(), connect=connect).upcoming_hearings()

    (sql, _) = connection.cursor_used.executed[0]
    first_column = sql.split("SELECT DISTINCT")[1].split(",")[0].strip()
    assert first_column == "c.CaseID"
    assert "PhoneNumber" in sql


def test_config_defaults_match_the_floci_database():
    config = DatabaseConfig.from_env(environ={})
    assert config == local_config()


def test_config_prefers_secrets_manager_values():
    environ = {
        "COURT_DB_ENGINE": "sqlserver",
        "COURT_DB_SECRET_ID": "CourtDatabaseSecret",
    }
    secret = {
        "host": "db.internal.example",
        "port": 1433,
        "dbname": "courtcases",
        "username": "courtadmin",
        "password": "generated",
    }
    loaded = []

    def loader(name):
        loaded.append(name)
        return secret

    config = DatabaseConfig.from_env(environ=environ, secret_loader=loader)

    assert loaded == ["CourtDatabaseSecret"]
    assert config == DatabaseConfig(
        engine="sqlserver",
        host="db.internal.example",
        port=1433,
        database="courtcases",
        user="courtadmin",
        password="generated",
    )


def test_factory_selects_adapter_by_engine():
    assert isinstance(
        court_case_repository(local_config("postgres")), PostgresCourtCaseRepository
    )
    assert isinstance(
        court_case_repository(local_config("sqlserver")), SqlServerCourtCaseRepository
    )


def test_factory_rejects_unknown_engine():
    with pytest.raises(ValueError, match="mysql"):
        court_case_repository(local_config("mysql"))


@pytest.mark.parametrize(
    "repository_class", [PostgresCourtCaseRepository, SqlServerCourtCaseRepository]
)
def test_ping_runs_a_trivial_query(repository_class):
    connection, connect = fake_connect([(1,)])
    assert repository_class(local_config(), connect=connect).ping() is True
    (sql, _) = connection.cursor_used.executed[0]
    assert sql == "SELECT 1"


@pytest.mark.parametrize(
    "repository_class", [PostgresCourtCaseRepository, SqlServerCourtCaseRepository]
)
def test_hearings_for_case_filters_by_case_number(repository_class):
    connection, connect = fake_connect([SAMPLE_ROW])
    repository = repository_class(local_config(), connect=connect)

    hearings = repository.hearings_for_case("24-CR-00042")

    assert [hearing.case_number for hearing in hearings] == ["24-CR-00042"]
    (sql, params) = connection.cursor_used.executed[0]
    assert params == {"case_number": "24-CR-00042"}
    assert "CaseNumber = %(case_number)s" in sql


def test_config_falls_back_to_env_for_fields_the_secret_lacks():
    # RDS SQL Server secrets have no dbname (CDK cannot name the database for
    # that engine), so COURT_DB_NAME must fill it in.
    environ = {
        "COURT_DB_ENGINE": "sqlserver",
        "COURT_DB_NAME": "courtdb",
        "COURT_DB_SECRET_ID": "arn:aws:secretsmanager:us-east-1:1:secret:x",
    }
    secret = {
        "host": "db.internal",
        "port": "1433",
        "username": "courtadmin",
        "password": "p",
    }

    config = DatabaseConfig.from_env(environ=environ, secret_loader=lambda name: secret)

    assert (config.host, config.port, config.database, config.user) == (
        "db.internal",
        1433,
        "courtdb",
        "courtadmin",
    )


def test_config_ignores_the_secret_loader_when_no_secret_is_configured():
    def explode(name):
        raise AssertionError("secret loader must not be called")

    config = DatabaseConfig.from_env(environ={}, secret_loader=explode)
    assert config.host == "localhost"

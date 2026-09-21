"""Unit tests for the SQL Server seed runner. No driver or server needed."""

from pathlib import Path

import pytest

from court_db import DatabaseConfig
from court_db.seed import (
    LADDER_CASES,
    SEED_ROOT,
    TABLES,
    load_fixtures,
    split_batches,
    use_test_phone,
)

SQL_DIR = SEED_ROOT / "sqlserver"
POSTGRES_SQL_DIR = SEED_ROOT / "postgres"


class FakeCursor:
    def __init__(self, log, params=None):
        self.log = log
        self.params = params if params is not None else []

    def execute(self, sql, params=None):
        self.log.append(sql)
        self.params.append(params)

    def fetchall(self):
        return [(42,)]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConnection:
    def __init__(self, database, log):
        self.database = database
        self.log = log
        self.params = []
        self.autocommit_set = None
        self.committed = False
        self.closed = False

    def autocommit(self, value):
        self.autocommit_set = value

    def cursor(self):
        return FakeCursor(self.log, self.params)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False


def code_of(batch):
    """The batch with -- comment lines removed, so comments cannot match."""
    return "\n".join(
        line for line in batch.splitlines() if not line.lstrip().startswith("--")
    ).strip()


def fake_connect():
    connections = []

    def connect(config):
        connection = FakeConnection(config.database, [])
        connections.append(connection)
        return connection

    return connections, connect


def aws_config():
    return DatabaseConfig(
        engine="sqlserver",
        host="db.internal",
        port=1433,
        database="courtdb",
        user="courtadmin",
        password="secret",
    )


def test_split_batches_on_go_lines_case_insensitively_and_ignores_comments():
    sql = "CREATE TABLE a (x int);\nGO\n\ngo -- second batch\nINSERT INTO a VALUES (1);\nGO\n"
    assert split_batches(sql) == [
        "CREATE TABLE a (x int);",
        "INSERT INTO a VALUES (1);",
    ]


def test_split_batches_does_not_split_inside_a_line():
    assert split_batches("SELECT 'GO' AS word;\nGOTO_label: SELECT 1;") == [
        "SELECT 'GO' AS word;\nGOTO_label: SELECT 1;"
    ]


def test_shipped_scripts_cover_every_table_and_isolate_the_function():
    scripts = sorted(Path(SQL_DIR).glob("*.sql"))
    assert [s.name for s in scripts] == [
        "01-schema.sql",
        "02-reference-data.sql",
        "03-fixtures.sql",
    ]
    schema = scripts[0].read_text()
    for table in TABLES:
        assert f"CREATE TABLE dbo.{table}" in schema

    function_batches = [
        code_of(b) for b in split_batches(schema) if "CREATE FUNCTION" in code_of(b)
    ]
    assert len(function_batches) == 1
    assert function_batches[0].startswith("CREATE FUNCTION")
    assert function_batches[0].count("CREATE ") == 1


def test_fixtures_match_the_postgres_seed_row_for_row():
    postgres = (POSTGRES_SQL_DIR / "03-fixtures.sql").read_text()
    sqlserver = (Path(SQL_DIR) / "03-fixtures.sql").read_text()

    # Every phone number and case number seeded locally is seeded in AWS too.
    for literal in [
        "'(404) 555-0101'",
        "'404-555-0110 ext. 12'",
        "'UNKNOWN'",
        "'CR-2026-000103 '",
        "'26CR000111'",
        "'DOE, JANE'",
        "'O''Brien'",
        # The 7/3/1 reminder ladder, which must exist in both engines or a
        # threshold that works locally finds nothing in AWS.
        "'CR-2026-000112'",
        "'CR-2026-000113'",
        "'CR-2026-000114'",
        "'+14045550116'",
        "'+14045550117'",
        "'+14045550118'",
    ]:
        assert literal in postgres and literal in sqlserver
    assert postgres.count("'DEFENDANT'") == sqlserver.count("'DEFENDANT'")


def test_load_fixtures_creates_database_then_runs_scripts_in_order_and_commits():
    connections, connect = fake_connect()

    summary = load_fixtures(aws_config(), connect=connect)

    master, target = connections
    assert master.database == "master"
    assert master.autocommit_set is True
    assert master.closed is True
    assert master.log == ["IF DB_ID('courtdb') IS NULL CREATE DATABASE [courtdb]"]

    assert target.database == "courtdb"
    assert target.committed is True
    assert code_of(target.log[0]).startswith("DROP TABLE IF EXISTS dbo.tblCaseEvent")
    assert any(code_of(b).startswith("CREATE FUNCTION") for b in target.log)
    assert target.log[-len(TABLES) :] == [
        f"SELECT COUNT(*) FROM dbo.{table}" for table in TABLES
    ]

    assert summary["engine"] == "sqlserver"
    assert summary["database"] == "courtdb"
    assert list(summary["scripts"]) == [
        "01-schema.sql",
        "02-reference-data.sql",
        "03-fixtures.sql",
    ]
    assert summary["row_counts"] == {table: 42 for table in TABLES}


def test_load_fixtures_rejects_unsafe_database_names():
    _, connect = fake_connect()
    config = DatabaseConfig(
        engine="sqlserver",
        host="h",
        port=1,
        database="courtdb; DROP",
        user="u",
        password="p",
    )
    with pytest.raises(ValueError):
        load_fixtures(config, connect=connect)


def test_postgres_seed_runs_each_script_as_one_batch_without_creating_a_database():
    connections, connect = fake_connect()
    config = DatabaseConfig(
        engine="postgres",
        host="172.25.0.3",
        port=7001,
        database="courtdb",
        user="courtadmin",
        password="secret",
    )

    summary = load_fixtures(config, connect=connect)

    (target,) = connections  # no master connection: courtdb already exists
    assert target.database == "courtdb"
    assert target.committed is True
    assert summary["engine"] == "postgres"
    assert summary["scripts"] == {
        "01-schema.sql": 1,
        "02-reference-data.sql": 1,
        "03-fixtures.sql": 1,
        "04-phone-type-citext.sql": 1,
    }
    schema = target.log[0]
    assert "DROP SCHEMA IF EXISTS dbo CASCADE" in schema


def test_postgres_scripts_have_no_psql_meta_commands():
    for script in POSTGRES_SQL_DIR.glob("*.sql"):
        for line in script.read_text().splitlines():
            assert not line.lstrip().startswith("\\"), f"{script.name}: {line}"


def test_postgres_scripts_cover_every_table():
    schema = (POSTGRES_SQL_DIR / "01-schema.sql").read_text()
    for table in TABLES:
        assert f"CREATE TABLE {table} (" in schema, table
    assert "CREATE FUNCTION fnGetLookupDescription" in schema


def test_the_ladder_cases_are_the_ones_the_fixtures_seed():
    """Both engines must carry every case use_test_phone rewrites, or a
    developer's number lands in one environment and not the other."""
    assert LADDER_CASES == {
        7: "CR-2026-000112",
        3: "CR-2026-000113",
        1: "CR-2026-000114",
    }
    for sql_dir in (POSTGRES_SQL_DIR, Path(SQL_DIR)):
        fixtures = (sql_dir / "03-fixtures.sql").read_text()
        for case_number in LADDER_CASES.values():
            assert f"'{case_number}'" in fixtures, (sql_dir.name, case_number)


def test_use_test_phone_rewrites_one_row_per_lead_time_and_commits():
    connections, connect = fake_connect()

    rewritten = use_test_phone(aws_config(), "+14045551234", connect=connect)

    (target,) = connections
    assert target.committed is True
    assert rewritten == {
        "7": "CR-2026-000112",
        "3": "CR-2026-000113",
        "1": "CR-2026-000114",
    }
    # One statement per ladder case, and nothing else touched.
    assert len(target.log) == len(LADDER_CASES)
    for statement in target.log:
        assert code_of(statement).startswith("UPDATE dbo.tblPartyPhone")
    # Parameterized, never interpolated: the number reaches the driver as a
    # value, so no phone string can become SQL.
    assert target.params == [
        {"phone": "+14045551234", "case_number": case_number}
        for case_number in LADDER_CASES.values()
    ]


def test_use_test_phone_leaves_every_other_number_alone():
    """The dirty phone rows are the point of these fixtures; a test number
    must not overwrite them."""
    connections, connect = fake_connect()

    use_test_phone(aws_config(), "+14045551234", connect=connect)

    (target,) = connections
    for statement in target.log:
        # Scoped through tblCase by case number, not a blanket UPDATE.
        assert "WHERE PartyID IN (" in statement
        assert "FROM dbo.tblCase WHERE CaseNumber = %(case_number)s" in statement


def test_use_test_phone_rejects_an_engine_it_has_no_scripts_for():
    _, connect = fake_connect()
    config = DatabaseConfig(
        engine="oracle", host="h", port=1, database="courtdb", user="u", password="p"
    )
    with pytest.raises(ValueError):
        use_test_phone(config, "+14045551234", connect=connect)

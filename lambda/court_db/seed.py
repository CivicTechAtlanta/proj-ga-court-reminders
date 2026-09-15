"""Load the court case schema and fixtures into a database.

The scripts under court_db/seed/<engine>/ carry the same data for each
engine: Postgres for the RDS instance Floci hosts locally, SQL Server for
RDS in AWS. The seed Lambda runs this during `cdk deploy`.
"""

import re
from dataclasses import replace
from pathlib import Path

from . import postgres, sqlserver


SEED_ROOT = Path(__file__).parent / "seed"

_ENGINES = {
    "postgres": postgres.open_connection,
    "sqlserver": sqlserver.open_connection,
}

# Tables in load order; counted after loading for the summary.
TABLES = [
    "tblLookup",
    "tblEventType",
    "tblParty",
    "tblCase",
    "tblCaseParty",
    "tblPartyPhone",
    "tblEvent",
    "tblCaseEvent",
]

# The clean case the fixtures anchor at each reminder lead time, keyed by days
# out. One hearing and one cell number each, which is what makes them the
# rows worth pointing at a real phone (see use_test_phone).
LADDER_CASES = {7: "CR-2026-000112", 3: "CR-2026-000113", 1: "CR-2026-000114"}

# Identifiers unquoted per ADR 002, and the same %(name)s paramstyle on both
# engines, so this one statement runs on Postgres and SQL Server alike.
_SET_LADDER_PHONE = """
UPDATE dbo.tblPartyPhone
SET PhoneNumber = %(phone)s
WHERE PartyID IN (
    SELECT FirstDefendantID FROM dbo.tblCase WHERE CaseNumber = %(case_number)s
)
"""

_GO_LINE = re.compile(r"^[ \t]*GO[ \t]*(?:--.*)?$", re.IGNORECASE | re.MULTILINE)
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def split_batches(sql: str) -> list[str]:
    """Split a script on T-SQL GO separator lines, dropping empty batches.

    GO is a client-side convention drivers reject, so each batch must be
    sent on its own. Postgres scripts have no GO lines and run as one batch.
    """
    return [batch.strip() for batch in _GO_LINE.split(sql) if batch.strip()]


def load_fixtures(config, sql_dir=None, connect=None) -> dict:
    """Run every seed script for the configured engine, in name order.

    Rerunnable: the schema scripts drop and recreate everything, and the
    fixtures re-anchor their dates to the server's current date.
    """
    if config.engine not in _ENGINES:
        raise ValueError(f"No seed scripts for engine {config.engine!r}")
    if not _IDENTIFIER.match(config.database):
        raise ValueError(f"Unsafe database name {config.database!r}")
    sql_dir = Path(sql_dir) if sql_dir else SEED_ROOT / config.engine
    connect = connect or _ENGINES[config.engine]

    if config.engine == "sqlserver":
        # RDS SQL Server starts with no user database (CDK cannot name one),
        # whereas Postgres gets courtdb from the instance's database_name.
        _ensure_sqlserver_database(config, connect)

    scripts = sorted(sql_dir.glob("*.sql"))
    executed = {}
    with connect(config) as connection:
        with connection.cursor() as cursor:
            for script in scripts:
                batches = split_batches(script.read_text(encoding="utf-8"))
                for batch in batches:
                    cursor.execute(batch)
                executed[script.name] = len(batches)
            counts = {table: _count_rows(cursor, table) for table in TABLES}
        connection.commit()

    return {
        "engine": config.engine,
        "database": config.database,
        "scripts": executed,
        "row_counts": counts,
    }


def _ensure_sqlserver_database(config, connect):
    # CREATE DATABASE cannot run inside the implicit transaction the driver
    # opens, so this one statement runs in autocommit mode against master.
    connection = connect(replace(config, database="master"))
    try:
        connection.autocommit(True)
        with connection.cursor() as cursor:
            cursor.execute(
                f"IF DB_ID('{config.database}') IS NULL "
                f"CREATE DATABASE [{config.database}]"
            )
    finally:
        connection.close()


def _count_rows(cursor, table):
    cursor.execute(f"SELECT COUNT(*) FROM dbo.{table}")
    return cursor.fetchall()[0][0]


def use_test_phone(config, number, connect=None) -> dict:
    """Point the reminder ladder's three cases at one real phone number.

    The fixtures otherwise carry nothing but reserved 555-01XX numbers, which
    cannot ring anybody. Testing the whole path to a handset needs a number
    that can, so this rewrites the phone row behind the clean case at each
    lead time -- CR-2026-000112, -000113 and -000114 -- and nothing else.
    Every dirty row the fixtures exist to exercise is left alone, and one
    person then has a hearing seven, three and one day out.

    `number` must already be normalized (the caller validates, because the
    message that comes back from a bad one belongs where somebody can read
    it). Passing it per run rather than reading it from configuration is
    deliberate, and the same rule `./script/sms/verify` follows: there is no
    stored setting that could quietly become the destination.

    Returns the case number rewritten at each lead time.
    """
    if config.engine not in _ENGINES:
        raise ValueError(f"No seed scripts for engine {config.engine!r}")
    connect = connect or _ENGINES[config.engine]

    rewritten = {}
    with connect(config) as connection:
        with connection.cursor() as cursor:
            for days, case_number in LADDER_CASES.items():
                cursor.execute(
                    _SET_LADDER_PHONE, {"phone": number, "case_number": case_number}
                )
                rewritten[str(days)] = case_number
        connection.commit()
    return rewritten

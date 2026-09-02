"""Load the court case schema and fixtures into a SQL Server database.

The T-SQL under court_db/seed/sqlserver/ is the native counterpart of the
Postgres scripts in db/init/ that seed the local Docker database on first
start. Running this against the AWS dev instance gives it the same data.
"""

import re
from dataclasses import replace
from pathlib import Path

from .sqlserver import open_connection


SQL_DIR = Path(__file__).parent / "seed" / "sqlserver"

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

_GO_LINE = re.compile(r"^[ \t]*GO[ \t]*(?:--.*)?$", re.IGNORECASE | re.MULTILINE)
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def split_batches(sql: str) -> list[str]:
    """Split a T-SQL script on GO separator lines, dropping empty batches.

    GO is a client-side convention, not T-SQL, so drivers reject it; each
    batch must be sent on its own.
    """
    return [batch.strip() for batch in _GO_LINE.split(sql) if batch.strip()]


def load_fixtures(config, sql_dir=SQL_DIR, connect=open_connection) -> dict:
    """Create the database if needed, then run every script in sql_dir in name order.

    Rerunnable: the schema script drops and recreates everything, and the
    fixtures re-anchor their dates to the server's current date.
    """
    if not _IDENTIFIER.match(config.database):
        raise ValueError(f"Unsafe database name {config.database!r}")

    _ensure_database(config, connect)

    scripts = sorted(Path(sql_dir).glob("*.sql"))
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
        "database": config.database,
        "scripts": executed,
        "row_counts": counts,
    }


def _ensure_database(config, connect):
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

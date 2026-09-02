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

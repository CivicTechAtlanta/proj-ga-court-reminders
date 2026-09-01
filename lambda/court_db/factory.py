"""Composition root: pick the repository for the configured engine."""

from .config import DatabaseConfig
from .postgres import PostgresCourtCaseRepository
from .repository import CourtCaseRepository
from .sqlserver import SqlServerCourtCaseRepository


_ENGINES = {
    "postgres": PostgresCourtCaseRepository,
    "sqlserver": SqlServerCourtCaseRepository,
}


def court_case_repository(config: DatabaseConfig | None = None) -> CourtCaseRepository:
    """Build the repository for the current environment.

    With no argument, configuration comes from the COURT_DB_* environment
    variables (local Docker Postgres by default; set COURT_DB_ENGINE and
    COURT_DB_SECRET_NAME on the Lambda for RDS SQL Server).
    """
    config = config or DatabaseConfig.from_env()
    try:
        repository_class = _ENGINES[config.engine]
    except KeyError:
        supported = ", ".join(sorted(_ENGINES))
        raise ValueError(
            f"Unknown COURT_DB_ENGINE {config.engine!r}; expected one of: {supported}"
        ) from None
    return repository_class(config)

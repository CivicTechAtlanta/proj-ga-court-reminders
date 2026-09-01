"""Database access layer for the court reminder Lambdas.

Handlers should import only from this package root:

    from court_db import court_case_repository

    hearings = court_case_repository().upcoming_hearings()
"""

from .config import DatabaseConfig
from .factory import court_case_repository
from .models import Hearing
from .repository import CourtCaseRepository

__all__ = [
    "CourtCaseRepository",
    "DatabaseConfig",
    "Hearing",
    "court_case_repository",
]

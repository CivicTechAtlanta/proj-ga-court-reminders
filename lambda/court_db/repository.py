"""The port every court database adapter implements.

Application code depends only on this interface; the concrete engine
(local Postgres fixture DB, production SQL Server) is an injection detail
chosen in factory.py.
"""

from abc import ABC, abstractmethod

from .models import Hearing


class CourtCaseRepository(ABC):
    @abstractmethod
    def ping(self) -> bool:
        """True when the configured database answers a trivial query.

        Lets each environment verify connectivity before doing real work.
        """

    @abstractmethod
    def upcoming_hearings(self, days_ahead: int = 7) -> list[Hearing]:
        """Hearings on the single day exactly days_ahead from today.

        The window is court-local: inclusive of midnight days_ahead out,
        exclusive of midnight the day after.
        """

    @abstractmethod
    def hearings_for_case(self, case_number: str) -> list[Hearing]:
        """Every hearing on one case, regardless of date.

        Supports responding to an inbound message about a known case.
        """

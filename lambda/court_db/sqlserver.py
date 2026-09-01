"""Adapter for the production Odyssey-style SQL Server database.

The hearing SQL is the near-verbatim production T-SQL (see ADR 002);
only the day offset is parameterized. The pymssql driver is a
placeholder choice pending the production connectivity decision.
"""

from .models import Hearing
from .repository import CourtCaseRepository


_HEARING_SELECT = """
SELECT DISTINCT
    c.CaseID,
    cp.CasePartyID,
    c.CaseNumber,
    et.EventTypeDescription,
    ce.CaseStartDateTime AS EventDateTime,
    dbo.fnGetLookupDescription(e.CourtRoomCode, 'CourtRoom') AS CourtRoom,
    pp.PhoneType,
    pp.PhoneNumber
FROM tblCase c WITH(NOLOCK)
INNER JOIN tblCaseParty cp WITH(NOLOCK)
    ON c.CaseID = cp.CaseID AND c.FirstDefendantID = cp.PartyID
INNER JOIN tblPartyPhone pp WITH(NOLOCK)
    ON cp.PartyID = pp.PartyID
INNER JOIN tblCaseEvent ce WITH(NOLOCK)
    ON c.CaseID = ce.CaseID
INNER JOIN tblEvent e WITH(NOLOCK)
    ON ce.EventID = e.EventID
INNER JOIN tblEventType et WITH(NOLOCK)
    ON ce.CaseEventTypeID = et.EventTypeID
"""

_UPCOMING_HEARINGS = (
    _HEARING_SELECT
    + """
WHERE
    ce.CaseStartDateTime >= DATEADD(d, %(days)s, CONVERT(DATE, GETDATE()))
    AND ce.CaseStartDateTime < DATEADD(d, %(days)s + 1, CONVERT(DATE, GETDATE()))
    AND pp.PhoneType IN ('CELL', 'MOBILE')
ORDER BY EventDateTime, CaseNumber
"""
)

_HEARINGS_FOR_CASE = (
    _HEARING_SELECT
    + """
WHERE c.CaseNumber = %(case_number)s
ORDER BY EventDateTime, CaseNumber
"""
)


class SqlServerCourtCaseRepository(CourtCaseRepository):
    def __init__(self, config, connect=None):
        self._config = config
        self._connect = connect or self._driver_connect

    def ping(self) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1", {})
            return cursor.fetchall()[0][0] == 1

    def upcoming_hearings(self, days_ahead: int = 7) -> list[Hearing]:
        return self._fetch_hearings(_UPCOMING_HEARINGS, {"days": days_ahead})

    def hearings_for_case(self, case_number: str) -> list[Hearing]:
        return self._fetch_hearings(_HEARINGS_FOR_CASE, {"case_number": case_number})

    def _fetch_hearings(self, sql, params) -> list[Hearing]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, params)
            return [Hearing.from_row(row) for row in cursor.fetchall()]

    def _driver_connect(self):
        try:
            import pymssql
        except ImportError as exc:
            raise RuntimeError(
                "The SQL Server driver is not installed. Add pymssql to the "
                "lambda dependencies before deploying against RDS."
            ) from exc

        return pymssql.connect(
            server=self._config.host,
            port=str(self._config.port),
            database=self._config.database,
            user=self._config.user,
            password=self._config.password,
        )

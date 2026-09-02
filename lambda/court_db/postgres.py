"""Adapter for the local Docker Postgres fixture database.

The hearing SQL matches db/queries/next_week_hearings.sql with the day
offset parameterized. Identifiers stay unquoted per ADR 002 so the
prod-cased names fold to the fixture schema.
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
FROM tblCase c
INNER JOIN tblCaseParty cp
    ON c.CaseID = cp.CaseID AND c.FirstDefendantID = cp.PartyID
INNER JOIN tblPartyPhone pp
    ON cp.PartyID = pp.PartyID
INNER JOIN tblCaseEvent ce
    ON c.CaseID = ce.CaseID
INNER JOIN tblEvent e
    ON ce.EventID = e.EventID
INNER JOIN tblEventType et
    ON ce.CaseEventTypeID = et.EventTypeID
"""

_UPCOMING_HEARINGS = (
    _HEARING_SELECT
    + """
WHERE
    ce.CaseStartDateTime >= CURRENT_DATE + %(days)s
    AND ce.CaseStartDateTime < CURRENT_DATE + (%(days)s + 1)
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


class PostgresCourtCaseRepository(CourtCaseRepository):
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
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                f"The psycopg driver could not be imported: {exc}. It is either "
                "missing from the bundle (lambda/requirements.txt needs "
                "psycopg[binary]) or built for a different CPU architecture "
                "than the one running this code."
            ) from exc

        return psycopg.connect(
            host=self._config.host,
            port=self._config.port,
            dbname=self._config.database,
            user=self._config.user,
            password=self._config.password,
        )

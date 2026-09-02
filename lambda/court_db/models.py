"""Domain models returned by the court database layer.

Handlers work with these plain objects; database drivers and SQL never
leak past the court_db package boundary.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Hearing:
    """One upcoming hearing for a first defendant with a phone on file."""

    case_id: int
    case_party_id: int
    case_number: str
    event_type: str
    event_datetime: datetime
    court_room: str | None
    phone_type: str
    phone_number: str

    @classmethod
    def from_row(cls, row):
        """Build a Hearing from a driver row in the shared SELECT order.

        Every repository must SELECT columns in this order: CaseID,
        CasePartyID, CaseNumber, EventTypeDescription, EventDateTime,
        CourtRoom, PhoneType, PhoneNumber.
        """
        return cls(
            case_id=row[0],
            case_party_id=row[1],
            case_number=row[2],
            event_type=row[3],
            event_datetime=row[4],
            court_room=row[5],
            phone_type=row[6],
            phone_number=row[7],
        )

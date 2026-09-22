"""What one reminder looks like on its way to the outbox queue.

A ReminderMessage carries exactly the JSON the text sender accepts, by
either of its two routes (the outbox queue or its function URL):

    {"to": "+14045550142", "message": "...", "reminder_id": "..."}

The reminder_id is the part of this module worth reading twice. The sender
keeps a log of the ids it has already texted and skips a repeat, so the id
is what makes the daily run safe to repeat: a retry, a redelivery, or a
second run on the same day re-queues the same ids and the sender drops
them. Get the id wrong and the system either texts people twice or, worse,
suppresses a reminder that should have gone out.
"""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime

from truedialog import normalize_us_phone


@dataclass(frozen=True)
class ReminderMessage:
    """One text, addressed and ready for the queue."""

    to: str
    message: str
    reminder_id: str

    def as_queue_body(self) -> dict:
        """The message body the sender parses off the queue."""
        return {
            "to": self.to,
            "message": self.message,
            "reminder_id": self.reminder_id,
        }


def recipient(hearing) -> str:
    """The hearing's phone number in E.164, or raise ValueError.

    The court database holds numbers as people typed them, including
    extensions, truncated entries and placeholder text (see ADR 002), so
    some rows have no usable number at all. Normalizing here keeps those
    out of the queue: left in, each one would burn three delivery attempts
    before landing in the dead letter queue.
    """
    return normalize_us_phone(hearing.phone_number)


def court_date(hearing) -> str:
    """The hearing's day as the copy writes it: "Monday, September 28".

    The weekday is what a person plans a ride or a day off around; the year
    is left off because no reminder goes out more than a week ahead.
    """
    day = _court_day(hearing.event_datetime)
    # day.day rather than %d, which would print "October 05"; the
    # unpadded %-d is not portable.
    return f"{day:%A, %B} {day.day}"


def reminder_id(label: str, hearing, to: str) -> str:
    """A stable id for "this reminder, for this court date, to this number".

    Stable across runs, so re-running a day is a no-op at the sender.
    Distinct per threshold, because one person gets both a seven-day and a
    one-day text about the same hearing. Distinct per number, so a party
    with two cell numbers on file is reached on both, while the same number
    stored in two formats (which DISTINCT cannot collapse) is texted once.

    Distinct per court date, but not per hearing. The copy names only the
    date, so a number with two hearings on one day -- two cases, or two
    people sharing a phone -- would be sent the same text twice; one id per
    day makes that one text. Someone in court on consecutive days still
    hears about each.

    The number is hashed rather than included. The sender prints this id
    when it suppresses a duplicate, CloudWatch keeps logs for years, and a
    phone number ties a person to a court case.
    """
    day = _court_day(hearing.event_datetime)
    return f"{label}:{day:%Y%m%d}:{_number_tag(to)}"


def _court_day(event_datetime) -> date:
    """The calendar day a hearing falls on, court-local like the query."""
    if isinstance(event_datetime, datetime):
        return event_datetime.date()
    # A driver that hands back a string still has to produce a stable id.
    return datetime.fromisoformat(str(event_datetime)).date()


def _number_tag(to: str) -> str:
    return hashlib.sha256(to.encode()).hexdigest()[:8]

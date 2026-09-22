"""The reminder thresholds, and the copy each one sends.

**This is the file to edit.** One class per threshold, one `message()`
each, and nothing else to learn: the query window, phone handling, ids,
batching and queueing are all done for you in logic.py.

To change a threshold's copy, edit its `message()`. What you are handed is
a `Hearing` (see court_db/models.py):

    hearing.case_number      "CR-2026-000101" (may have a trailing space)
    hearing.event_type       "Arraignment"
    hearing.event_datetime   datetime, court-local
    hearing.court_room       "Courtroom 1A", or None when the code has no
                             lookup row -- always handle the None
    hearing.phone_number     as typed by a clerk; you do not need to touch
                             it, the pipeline normalizes and validates it
    hearing.case_id, hearing.case_party_id

`court_date(hearing)` is the hearing's day as the copy writes it, "Monday,
September 28". Return the text to send, or None to send this person
nothing -- that is where per-threshold rules go (an opt-out, a paid case, a
hearing type that should not be texted about).

Three things to know before your copy ships:

  * A reminder is one text per phone number per court date. A number with
    two hearings that day is sent the first one's text (the query orders
    by time); the copy below names only the day, so both would read the
    same anyway.
  * The stack deploys with REMINDERS_DRY_RUN set, so nothing is texted.
    Clearing that flag is a deliberate one-line change in cdk_stack.py, to
    be made once the copy is approved.
  * Keep a message inside one SMS segment (160 GSM-7 characters) unless a
    longer text is intended; TrueDialog bills and splits by segment.
    tests/test_reminders.py holds every threshold to that.
"""

from enum import Enum

from .logic import SenderLogic
from .messages import court_date


class ReminderThreshold(Enum):
    """How far ahead of a hearing a reminder goes out.

    Declared in the order the daily run works through them, counting down,
    matching the 7/3/1 cadence in ADR 006.
    """

    SEVEN_DAYS = 7
    THREE_DAYS = 3
    ONE_DAY = 1

    @property
    def days(self) -> int:
        return self.value

    @classmethod
    def parse(cls, value) -> "ReminderThreshold":
        """A threshold from its name ("ONE_DAY") or its day count (1)."""
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(value)
        try:
            return cls[str(value).strip().upper()]
        except KeyError:
            raise ValueError(
                f"Unknown reminder threshold {value!r}; expected one of: "
                + ", ".join(threshold.name for threshold in cls)
            ) from None


class SevenDayReminder(SenderLogic):
    """A week out: the first a person hears from us about this hearing.

    This one carries the weight -- it may be the only notice someone gets
    with time to arrange a ride, childcare or a day off work.
    """

    threshold = ReminderThreshold.SEVEN_DAYS

    def message(self, hearing):
        return (
            "ATL Court Reminders : Seven days notice. "
            f"You have a court date on {court_date(hearing)}. "
            "Reply STOP to discontinue."
        )


class ThreeDayReminder(SenderLogic):
    """Three days out: the reminder that lands while plans can still change."""

    threshold = ReminderThreshold.THREE_DAYS

    def message(self, hearing):
        return (
            "ATL Court Reminders : Three days until your court date. "
            f"You have a court date on {court_date(hearing)}. "
            "Reply STOP to discontinue."
        )


class OneDayReminder(SenderLogic):
    """The day before: short, specific, and about tomorrow."""

    threshold = ReminderThreshold.ONE_DAY

    def message(self, hearing):
        return (
            "ATL Court Reminders : Your court date is tomorrow, "
            f"on {court_date(hearing)}. "
            "Reply STOP to discontinue."
        )


_SENDERS = {
    ReminderThreshold.SEVEN_DAYS: SevenDayReminder,
    ReminderThreshold.THREE_DAYS: ThreeDayReminder,
    ReminderThreshold.ONE_DAY: OneDayReminder,
}


def sender_for(threshold, **kwargs) -> SenderLogic:
    """The SenderLogic for one threshold, named however it arrived."""
    return _SENDERS[ReminderThreshold.parse(threshold)](**kwargs)


def every_sender(**kwargs) -> list[SenderLogic]:
    """One sender per threshold, in the order the daily run uses."""
    return [sender_for(threshold, **kwargs) for threshold in ReminderThreshold]

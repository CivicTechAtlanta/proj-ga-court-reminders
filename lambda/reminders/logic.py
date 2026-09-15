"""The three steps that turn a court calendar into queued text messages.

    SenderLogic(days=7).run()

    sender = SevenDayReminder()
    hearings = sender.query()        # who has a hearing that far out
    messages = sender.generate(hearings)   # what each of them should be told
    summary  = sender.send(messages)       # onto the outbox queue

Each step takes the previous step's output, and each falls back to running
the step before it when called on its own, so `sender.send()` is the whole
pipeline and `run()` is the same thing with a summary worth logging.

Only `message()` is meant to be overridden. Everything else -- the query
window, phone normalization, id minting, batching -- is the same for every
threshold and lives here. See thresholds.py for where the copy goes.
"""

from court_db import court_case_repository

from .messages import ReminderMessage, recipient, reminder_id
from .outbox import outbox as default_outbox


class SenderLogic:
    """Queue the reminders due for one threshold, for example seven days out.

    Subclasses set `threshold` and override `message()`. Instantiate this
    class directly with `days=` for a one-off window that has no threshold
    of its own.

    The repository and outbox are constructor arguments so tests can pass
    fakes; left out, they are built from the environment on first use.
    """

    #: Set by the subclasses in thresholds.py. None means "days= only".
    threshold = None

    def __init__(self, days=None, repository=None, outbox=None):
        if days is None:
            if self.threshold is None:
                raise ValueError(
                    "SenderLogic needs days=, or a subclass that sets threshold"
                )
            days = self.threshold.days
        self.days = int(days)
        self._repository = repository
        self._outbox = outbox

    def __repr__(self):
        return f"{type(self).__name__}(days={self.days})"

    @property
    def label(self) -> str:
        """What this threshold is called in ids, logs and summaries."""
        return self.threshold.name if self.threshold else f"DAY_{self.days}"

    @property
    def repository(self):
        if self._repository is None:
            self._repository = court_case_repository()
        return self._repository

    @property
    def outbox(self):
        if self._outbox is None:
            self._outbox = default_outbox()
        return self._outbox

    # ------------------------------------------------------------- query

    def query(self):
        """The hearings this threshold is responsible for today.

        One day's worth, court-local: hearings from midnight `days` out to
        midnight the day after, for first defendants with a cell number on
        file. The window is the repository's; this only chooses how far out.
        """
        return self.repository.upcoming_hearings(days_ahead=self.days)

    # ---------------------------------------------------------- generate

    def message(self, hearing) -> str | None:
        """The text one person gets. Return None to send them nothing.

        This is the seam each threshold fills in, and the default is
        deliberately plain: a subclass that has not been written yet still
        produces something a developer can see on the queue. Returning None
        is how a threshold skips a hearing it has decided not to text
        about.

        Anything this returns is sent verbatim, so keep it inside one SMS
        segment (160 GSM-7 characters) unless a longer text is intended.
        """
        return placeholder_message(self.label, hearing)

    def generate(self, hearings=None) -> list[ReminderMessage]:
        """One ReminderMessage per hearing that should be texted about."""
        messages, _ = self._plan(hearings)
        return messages

    def _plan(self, hearings=None):
        """generate(), plus a count of why hearings were dropped."""
        hearings = self.query() if hearings is None else hearings
        messages, skipped, seen = [], {}, set()
        for hearing in hearings:
            text = self.message(hearing)
            if not text:
                skipped["no_message"] = skipped.get("no_message", 0) + 1
                continue
            try:
                to = recipient(hearing)
            except ValueError:
                # The number itself is never logged; the wrapper masks it
                # even in the error it raises.
                skipped["unusable_phone"] = skipped.get("unusable_phone", 0) + 1
                continue
            identifier = reminder_id(self.label, hearing, to)
            if identifier in seen:
                # The query returns one row per phone row, and the same
                # number stored in two formats survives its DISTINCT (see
                # ADR 002). Collapsing here rather than leaving it to the
                # sender's log keeps the queue honest, and matters because
                # that log degrades to remembering nothing when no table is
                # configured -- which would text this person twice.
                skipped["duplicate"] = skipped.get("duplicate", 0) + 1
                continue
            seen.add(identifier)
            messages.append(
                ReminderMessage(to=to, message=text, reminder_id=identifier)
            )
        return messages, skipped

    # -------------------------------------------------------------- send

    def send(self, messages=None) -> dict:
        """Put the messages on the outbox queue. Generates them if not given."""
        messages = self.generate() if messages is None else messages
        return self.outbox.publish(messages)

    # --------------------------------------------------------------- run

    def run(self) -> dict:
        """The whole pipeline, with the numbers worth logging.

        Safe to run more than once a day. Every message carries a stable
        reminder_id, so a repeat run queues ids the sender has already
        texted and the sender drops them.
        """
        hearings = self.query()
        messages, skipped = self._plan(hearings)
        published = self.outbox.publish(messages)
        summary = {
            "threshold": self.label,
            "days": self.days,
            "hearings": len(hearings),
            "messages": len(messages),
            "skipped": skipped,
            **published,
        }
        print(
            f"{self.label}: {summary['hearings']} hearing(s), "
            f"{summary['messages']} message(s), "
            f"{summary['queued']} queued, {len(summary['failed'])} failed"
            + (" (dry run)" if published.get("dry_run") else "")
        )
        return summary


def placeholder_message(label: str, hearing) -> str:
    """Stand-in copy, marked so it cannot ship unnoticed.

    Every threshold starts with this. Replacing it -- the DRAFT marker
    included -- is the work described in thresholds.py.
    """
    when = hearing.event_datetime
    where = f" in {hearing.court_room}" if hearing.court_room else ""
    return (
        f"[DRAFT {label}] Reminder: {hearing.event_type} for case "
        f"{str(hearing.case_number).strip()} on {when}{where}."
    )

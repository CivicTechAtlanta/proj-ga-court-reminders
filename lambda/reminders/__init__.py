"""Reminder production for the court reminder Lambdas.

Handlers should import only from this package root:

    from reminders import every_sender, sender_for

    for sender in every_sender():
        sender.run()

The threshold copy lives in thresholds.py; the pipeline behind it lives in
logic.py.
"""

from .logic import SenderLogic, placeholder_message
from .messages import ReminderMessage, court_date, recipient, reminder_id
from .outbox import DryRunOutbox, Outbox, outbox
from .thresholds import (
    OneDayReminder,
    ReminderThreshold,
    SevenDayReminder,
    ThreeDayReminder,
    every_sender,
    sender_for,
)

__all__ = [
    "DryRunOutbox",
    "OneDayReminder",
    "Outbox",
    "ReminderMessage",
    "ReminderThreshold",
    "SenderLogic",
    "SevenDayReminder",
    "ThreeDayReminder",
    "court_date",
    "every_sender",
    "outbox",
    "placeholder_message",
    "recipient",
    "reminder_id",
    "sender_for",
]

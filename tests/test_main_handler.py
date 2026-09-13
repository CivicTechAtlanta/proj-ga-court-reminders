"""CourtBotMain: the daily run that queues the reminders due today."""

import json

import pytest

import main
from reminders import DryRunOutbox, ReminderThreshold


class FakeSender:
    """Records that it ran, instead of touching a database or a queue."""

    def __init__(self, threshold, outbox=None, fail=False):
        self.threshold = threshold
        self.outbox = outbox
        self._fail = fail

    def run(self):
        if self._fail:
            raise RuntimeError("the database is down")
        return {"threshold": self.threshold.name, "queued": 1}


def record_senders(monkeypatch, failing=()):
    """Replace the real senders; return the list of the ones built."""
    built = []

    def fake_sender_for(threshold, outbox=None):
        sender = FakeSender(threshold, outbox, fail=threshold.name in failing)
        built.append(sender)
        return sender

    monkeypatch.setattr(main, "sender_for", fake_sender_for)
    return built


def body(response):
    return json.loads(response["body"])


def test_the_scheduled_run_covers_every_threshold(monkeypatch):
    """The EventBridge event names no threshold, so the default path is the
    whole daily cadence."""
    built = record_senders(monkeypatch)

    response = main.handler({"source": "aws.events"}, None)

    assert [sender.threshold for sender in built] == list(ReminderThreshold)
    assert body(response)["thresholds"] == ["SEVEN_DAYS", "THREE_DAYS", "ONE_DAY"]
    assert body(response)["queued"] == 3
    assert response["statusCode"] == 200


@pytest.mark.parametrize(
    "event",
    [{"thresholds": ["ONE_DAY"]}, {"thresholds": [1]}, {"threshold": "ONE_DAY"}],
)
def test_one_threshold_can_be_run_by_hand(monkeypatch, event):
    built = record_senders(monkeypatch)

    response = main.handler(event, None)

    assert [sender.threshold for sender in built] == [ReminderThreshold.ONE_DAY]
    assert body(response)["queued"] == 1


def test_an_event_can_force_a_dry_run(monkeypatch):
    built = record_senders(monkeypatch)

    main.handler({"thresholds": ["ONE_DAY"], "dry_run": True}, None)

    assert isinstance(built[0].outbox, DryRunOutbox)


def test_without_the_flag_the_stack_decides_whether_to_queue(monkeypatch):
    """An event must not be able to turn a dry run off; leaving the outbox
    unset is what lets REMINDERS_DRY_RUN decide."""
    built = record_senders(monkeypatch)

    main.handler({"thresholds": ["ONE_DAY"], "dry_run": False}, None)

    assert built[0].outbox is None


def test_one_broken_threshold_does_not_stop_the_others(monkeypatch):
    """Somebody's hearing is tomorrow: a failure in the seven-day copy must
    not take the one-day reminders down with it."""
    built = record_senders(monkeypatch, failing={"THREE_DAYS"})

    with pytest.raises(RuntimeError, match="THREE_DAYS"):
        main.handler({}, None)

    assert [sender.threshold for sender in built] == list(ReminderThreshold)


def test_an_unknown_threshold_is_refused(monkeypatch):
    record_senders(monkeypatch)
    with pytest.raises(ValueError, match="TWO_DAYS"):
        main.handler({"thresholds": ["TWO_DAYS"]}, None)


def test_a_non_list_of_thresholds_is_refused(monkeypatch):
    record_senders(monkeypatch)
    with pytest.raises(ValueError, match="must be a list"):
        main.handler({"thresholds": "ONE_DAY"}, None)


def test_the_documented_sample_event_runs(monkeypatch):
    """The event the README tells a newcomer to invoke."""
    from pathlib import Path

    event = json.loads(
        (
            Path(__file__).resolve().parent.parent / "scripts/events/reminder-run.json"
        ).read_text()
    )
    built = record_senders(monkeypatch)

    main.handler(event, None)

    assert [sender.threshold for sender in built] == [ReminderThreshold.ONE_DAY]
    assert isinstance(built[0].outbox, DryRunOutbox)

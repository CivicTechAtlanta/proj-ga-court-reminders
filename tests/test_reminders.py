"""The producer end: query, generate, send, and the ids that make it safe."""

import json
from datetime import datetime

import pytest

import message_sender
from court_db import Hearing
from reminders import (
    DryRunOutbox,
    Outbox,
    ReminderThreshold,
    SenderLogic,
    SevenDayReminder,
    every_sender,
    outbox,
    reminder_id,
    sender_for,
)


def hearing(**overrides) -> Hearing:
    fields = {
        "case_id": 1,
        "case_party_id": 2,
        "case_number": "CR-2026-000101",
        "event_type": "Arraignment",
        "event_datetime": datetime(2026, 9, 20, 9, 0),
        "court_room": "Courtroom 1A",
        "phone_type": "CELL",
        "phone_number": "(404) 555-0101",
    }
    return Hearing(**{**fields, **overrides})


class FakeRepository:
    def __init__(self, hearings=None):
        self.hearings = [hearing()] if hearings is None else hearings
        self.asked_for = []

    def upcoming_hearings(self, days_ahead=7):
        self.asked_for.append(days_ahead)
        return self.hearings


class FakeSqs:
    """Accepts every entry unless its body names one to fail."""

    def __init__(self, fail_ids=()):
        self.batches = []
        self._fail_ids = set(fail_ids)

    def send_message_batch(self, QueueUrl, Entries):  # noqa: N803 - boto3 casing
        self.batches.append(Entries)
        successful, failed = [], []
        for entry in Entries:
            body = json.loads(entry["MessageBody"])
            target = failed if body["reminder_id"] in self._fail_ids else successful
            target.append({"Id": entry["Id"], "Code": "InternalError"})
        return {"Successful": successful, "Failed": failed}


def sender(hearings=None, **kwargs):
    return SevenDayReminder(
        repository=FakeRepository(hearings), outbox=DryRunOutbox(), **kwargs
    )


# ------------------------------------------------------------- thresholds


def test_each_threshold_knows_how_many_days_out_it_is():
    assert ReminderThreshold.SEVEN_DAYS.days == 7
    assert ReminderThreshold.THREE_DAYS.days == 3
    assert ReminderThreshold.ONE_DAY.days == 1


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ONE_DAY", ReminderThreshold.ONE_DAY),
        ("one_day", ReminderThreshold.ONE_DAY),
        (" Three_Days ", ReminderThreshold.THREE_DAYS),
        (7, ReminderThreshold.SEVEN_DAYS),
        (ReminderThreshold.ONE_DAY, ReminderThreshold.ONE_DAY),
    ],
)
def test_a_threshold_can_be_named_by_name_or_by_days(value, expected):
    assert ReminderThreshold.parse(value) is expected


def test_an_unknown_threshold_says_what_the_choices_are():
    with pytest.raises(ValueError, match="SEVEN_DAYS"):
        ReminderThreshold.parse("TWO_DAYS")


def test_the_daily_run_counts_down_from_seven():
    assert [s.days for s in every_sender()] == [7, 3, 1]
    assert [s.label for s in every_sender()] == ["SEVEN_DAYS", "THREE_DAYS", "ONE_DAY"]


def test_a_sender_without_a_threshold_still_works_from_days_alone():
    ad_hoc = SenderLogic(days=5, repository=FakeRepository(), outbox=DryRunOutbox())
    assert ad_hoc.label == "DAY_5"
    assert ad_hoc.query() and ad_hoc.repository.asked_for == [5]


def test_the_base_class_refuses_to_guess_a_window():
    with pytest.raises(ValueError, match="days="):
        SenderLogic()


# ------------------------------------------------------------------ query


def test_each_threshold_queries_its_own_window():
    for threshold in ReminderThreshold:
        repository = FakeRepository()
        sender_for(threshold, repository=repository, outbox=DryRunOutbox()).query()
        assert repository.asked_for == [threshold.days]


# --------------------------------------------------------------- generate


def test_a_generated_message_is_addressed_in_e164():
    (message,) = sender().generate()
    assert message.to == "+14045550101"
    assert message.message
    assert message.reminder_id.startswith("SEVEN_DAYS:")


def test_a_hearing_with_an_unusable_number_is_dropped_not_queued():
    """Left in, each of these would burn three delivery attempts and land in
    the dead letter queue."""
    hearings = [hearing(), hearing(case_party_id=3, phone_number="none on file")]
    messages, skipped = sender(hearings)._plan()
    assert [m.to for m in messages] == ["+14045550101"]
    assert skipped == {"unusable_phone": 1}


def test_a_threshold_can_decline_to_text_about_a_hearing():
    class Quiet(SevenDayReminder):
        def message(self, hearing):
            return None if hearing.event_type == "Arraignment" else "text"

    messages, skipped = Quiet(
        repository=FakeRepository([hearing(), hearing(event_type="Trial")]),
        outbox=DryRunOutbox(),
    )._plan()
    assert len(messages) == 1
    assert skipped == {"no_message": 1}


def test_generate_accepts_hearings_from_an_earlier_query():
    one = sender()
    assert len(one.generate(one.query())) == 1


# ------------------------------------------------------------ reminder ids


def test_the_same_reminder_gets_the_same_id_every_run():
    """What makes re-running a day a no-op at the sender."""
    assert sender().generate()[0].reminder_id == sender().generate()[0].reminder_id


def test_each_threshold_gets_its_own_id_for_one_hearing():
    ids = {
        sender_for(threshold, repository=FakeRepository(), outbox=DryRunOutbox())
        .generate()[0]
        .reminder_id
        for threshold in ReminderThreshold
    }
    assert len(ids) == 3


def test_two_numbers_on_one_hearing_are_two_reminders():
    """Same party, same hearing, two cell numbers: both get the text."""
    messages = sender([hearing(), hearing(phone_number="404-555-0199")]).generate()
    assert len({m.reminder_id for m in messages}) == 2


def test_one_number_stored_two_ways_is_texted_once():
    """The query returns a row per phone row and its DISTINCT cannot collapse
    a format variant (ADR 002). Leaving it to the sender's log would text this
    person twice wherever that log is not configured."""
    messages, skipped = sender(
        [hearing(), hearing(phone_number="(404) 555.0101")]
    )._plan()

    assert len(messages) == 1
    assert skipped == {"duplicate": 1}


def test_an_id_carries_no_phone_number():
    """The sender prints this id when it suppresses a duplicate, and
    CloudWatch keeps logs for years."""
    generated = reminder_id("ONE_DAY", hearing(), "+14045550101")
    assert "4045550101" not in generated
    assert "5550101" not in generated


# ------------------------------------------------------------------- send


def test_send_generates_the_messages_when_it_is_not_given_any():
    assert sender().send()["dry_run"] is True


def test_a_dry_run_queues_nothing_and_shows_what_it_would_have_sent():
    result = sender().send()
    assert result["queued"] == 0
    assert [m["to"] for m in result["would_send"]] == ["+14045550101"]


def test_messages_are_queued_in_batches_of_ten():
    hearings = [hearing(case_party_id=n) for n in range(23)]
    client = FakeSqs()
    result = SevenDayReminder(
        repository=FakeRepository(hearings),
        outbox=Outbox("https://queue", client=client),
    ).send()
    assert [len(batch) for batch in client.batches] == [10, 10, 3]
    assert result == {"queued": 23, "failed": [], "dry_run": False}


def test_one_rejected_message_does_not_stop_the_others():
    rejected = sender().generate()[0].reminder_id
    hearings = [hearing(), hearing(case_party_id=3)]
    client = FakeSqs(fail_ids=[rejected])
    result = SevenDayReminder(
        repository=FakeRepository(hearings),
        outbox=Outbox("https://queue", client=client),
    ).send()
    assert result["queued"] == 1
    assert result["failed"] == [rejected]


def test_a_queued_body_is_one_the_text_sender_accepts():
    """The producer and the consumer agree on the message shape. Asserted
    against the sender's own parser so the two cannot drift apart."""
    (message,) = sender().generate()
    record = {"body": json.dumps(message.as_queue_body())}
    parsed = message_sender._queue_request(record)
    assert parsed["to"] == message.to
    assert parsed["message"] == message.message
    assert parsed["reminder_id"] == message.reminder_id


# ---------------------------------------------------------------- the run


def test_a_run_reports_what_it_did():
    summary = sender([hearing(), hearing(phone_number="")]).run()
    assert summary["threshold"] == "SEVEN_DAYS"
    assert summary["days"] == 7
    assert summary["hearings"] == 2
    assert summary["messages"] == 1
    assert summary["skipped"] == {"unusable_phone": 1}
    assert summary["queued"] == 0 and summary["dry_run"] is True


# --------------------------------------------------------- outbox factory


def test_nothing_is_queued_until_a_queue_is_configured():
    assert isinstance(outbox({}), DryRunOutbox)


def test_the_dry_run_flag_wins_over_a_configured_queue():
    environ = {"OUTBOX_QUEUE_URL": "https://queue", "REMINDERS_DRY_RUN": "true"}
    assert isinstance(outbox(environ), DryRunOutbox)


def test_a_configured_queue_without_the_flag_really_sends():
    environ = {"OUTBOX_QUEUE_URL": "https://queue", "REMINDERS_DRY_RUN": "false"}
    assert isinstance(outbox(environ), Outbox)

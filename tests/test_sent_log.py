"""The record of reminders already texted. No DynamoDB is contacted: the
client is injected."""

import time

import pytest

from sent_log import DEFAULT_RETENTION_DAYS, NoSentLog, SentLog, sent_log


class FakeDynamo:
    def __init__(self, items=None):
        self.items = dict(items or {})
        self.gets = []
        self.puts = []

    def get_item(self, TableName, Key, ConsistentRead=False):
        self.gets.append((TableName, Key, ConsistentRead))
        key = Key["reminder_id"]["S"]
        return {"Item": self.items[key]} if key in self.items else {}

    def put_item(self, TableName, Item):
        self.puts.append((TableName, Item))
        self.items[Item["reminder_id"]["S"]] = Item


def test_an_unknown_reminder_has_not_been_sent():
    dynamo = FakeDynamo()
    log = SentLog("sent-reminders", client=dynamo)

    assert log.already_sent("hearing-42") is False
    (table, key, consistent) = dynamo.gets[0]
    assert table == "sent-reminders"
    assert key == {"reminder_id": {"S": "hearing-42"}}
    # A stale read would send the text twice, which is the whole point.
    assert consistent is True


def test_a_recorded_reminder_reads_back_as_sent():
    log = SentLog("sent-reminders", client=FakeDynamo())

    log.record("hearing-42")

    assert log.already_sent("hearing-42") is True


def test_recording_stamps_a_time_and_an_expiry():
    dynamo = FakeDynamo()
    before = int(time.time())

    SentLog("sent-reminders", client=dynamo, retention_days=30).record("hearing-42")

    (table, item) = dynamo.puts[0]
    assert table == "sent-reminders"
    assert item["reminder_id"] == {"S": "hearing-42"}
    sent_at, expires_at = int(item["sent_at"]["N"]), int(item["expires_at"]["N"])
    assert sent_at >= before
    assert expires_at - sent_at == 30 * 86400


def test_ids_that_are_not_strings_still_work():
    dynamo = FakeDynamo()
    log = SentLog("sent-reminders", client=dynamo)

    log.record(4242)

    assert log.already_sent(4242) is True
    assert dynamo.puts[0][1]["reminder_id"] == {"S": "4242"}


def test_recording_the_same_reminder_twice_is_harmless():
    dynamo = FakeDynamo()
    log = SentLog("sent-reminders", client=dynamo)

    log.record("hearing-42")
    log.record("hearing-42")

    assert len(dynamo.puts) == 2
    assert log.already_sent("hearing-42") is True


def test_without_a_table_nothing_is_remembered_or_suppressed():
    log = NoSentLog()

    log.record("hearing-42")

    assert log.already_sent("hearing-42") is False


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({}, NoSentLog),
        ({"SENT_LOG_TABLE": ""}, NoSentLog),
        ({"SENT_LOG_TABLE": "t"}, SentLog),
    ],
)
def test_the_factory_needs_a_table_name(environ, expected):
    assert isinstance(sent_log(environ=environ), expected)


def test_the_default_retention_outlives_any_retry():
    # The queue keeps a message four days and retries within a twelve minute
    # visibility timeout, so thirty days is far beyond any redelivery.
    assert DEFAULT_RETENTION_DAYS >= 30

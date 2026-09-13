"""A record of which reminders have already been texted.

The sender is driven by an SQS queue, whose delivery is at-least-once: the
same message can arrive twice, and a text TrueDialog has already accepted
can be retried when its response fails to reach us. Court reminders are a
bad thing to send twice, so each one may carry an id, and this module
remembers the ids that have been sent.

The order is deliberate. An id is written only after TrueDialog accepts the
text, never before, so a process that dies mid-send leaves no record and
the retry sends the reminder. That biases the system toward an occasional
duplicate rather than a silent miss, which is the right way round when a
missed reminder means somebody misses a hearing.

Two gaps remain, both narrow and both a consequence of that ordering:

  * a crash between TrueDialog accepting and the write landing lets the
    retry send a second text
  * two invocations racing on the same id can both read "not sent" and
    both send

Set SENT_LOG_TABLE to the DynamoDB table holding the ids. With it unset
nothing is recorded and nothing is suppressed, which is how unit tests and
plain HTTP calls run.
"""

import os
import time

DEFAULT_RETENTION_DAYS = 30


class SentLog:
    """Reminder ids already texted, in a DynamoDB table keyed on reminder_id."""

    def __init__(self, table_name, client=None, retention_days=DEFAULT_RETENTION_DAYS):
        self._table_name = table_name
        self._client = client
        self._retention_days = retention_days

    @property
    def client(self):
        if self._client is None:
            # Imported lazily: boto3 ships in the Lambda runtime but is not a
            # project dependency.
            import boto3

            self._client = boto3.client("dynamodb")
        return self._client

    def already_sent(self, reminder_id) -> bool:
        response = self.client.get_item(
            TableName=self._table_name,
            Key={"reminder_id": {"S": str(reminder_id)}},
            ConsistentRead=True,
        )
        return "Item" in response

    def record(self, reminder_id) -> None:
        """Note that this reminder went out. Called only after TrueDialog
        accepts it, and safe to repeat: the same id overwrites itself."""
        expires_at = int(time.time()) + self._retention_days * 86400
        self.client.put_item(
            TableName=self._table_name,
            Item={
                "reminder_id": {"S": str(reminder_id)},
                "sent_at": {"N": str(int(time.time()))},
                "expires_at": {"N": str(expires_at)},
            },
        )


class NoSentLog:
    """Stands in where no table is configured: remembers nothing, suppresses
    nothing. Every send proceeds and every retry sends again."""

    def already_sent(self, reminder_id) -> bool:
        return False

    def record(self, reminder_id) -> None:
        return None


def sent_log(environ=None):
    """The log for the current environment, or one that does nothing when
    SENT_LOG_TABLE is unset."""
    environ = os.environ if environ is None else environ
    table_name = environ.get("SENT_LOG_TABLE")
    return SentLog(table_name) if table_name else NoSentLog()

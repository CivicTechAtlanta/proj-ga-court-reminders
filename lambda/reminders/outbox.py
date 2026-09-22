"""Where generated reminders go: the outbox queue, or nowhere.

The producer runs inside the database VPC, whose isolated subnets have no
route to the internet. SQS is reached through the VPC interface endpoint
CourtDatabaseStack adds; without that endpoint every send here hangs until
the Lambda times out.

Set OUTBOX_QUEUE_URL to the CourtBotOutboxUrl stack output. With it unset,
or with REMINDERS_DRY_RUN set to a true value, nothing is queued and
nothing is texted: the run reports what it would have sent instead. That
is the default until the message copy is approved, and it is the same
shape of stand-in as the sender's NoSentLog.
"""

import json
import os

# SQS accepts at most ten entries, and 256 KB, in one SendMessageBatch.
BATCH_LIMIT = 10

_TRUE = {"1", "true", "yes", "on"}


class Outbox:
    """The CourtBotOutbox queue that feeds the text sender."""

    def __init__(self, queue_url, client=None):
        self._queue_url = queue_url
        self._client = client

    @property
    def client(self):
        if self._client is None:
            # Imported lazily: boto3 ships in the Lambda runtime but is not a
            # project dependency.
            import boto3

            self._client = boto3.client("sqs")
        return self._client

    @property
    def dry_run(self) -> bool:
        return False

    def publish(self, messages) -> dict:
        """Put every message on the queue, reporting failures per message.

        SQS can reject individual entries of a batch, so a partial failure
        is normal and is counted rather than raised: one unroutable
        reminder must not stop the rest of the day's reminders. The failed
        ids are logged (they carry no phone number by construction) and
        returned, so the caller can decide what a failure means.
        """
        messages = list(messages)
        queued, failed = 0, []
        for batch in _batched(messages, BATCH_LIMIT):
            response = self.client.send_message_batch(
                QueueUrl=self._queue_url,
                Entries=[
                    {
                        # Unique within the batch only. The reminder_id is
                        # the identity that matters, and it travels in the
                        # body where the sender reads it.
                        "Id": str(index),
                        "MessageBody": json.dumps(message.as_queue_body()),
                    }
                    for index, message in enumerate(batch)
                ],
            )
            queued += len(response.get("Successful", []))
            for failure in response.get("Failed", []):
                entry = batch[int(failure["Id"])]
                print(
                    f"reminder {entry.reminder_id} was not queued: "
                    f"{failure.get('Code', 'unknown')}"
                )
                failed.append(entry.reminder_id)
        return {"queued": queued, "failed": failed, "dry_run": False}


class DryRunOutbox:
    """Stands in where no queue is configured: queues nothing, texts nobody.

    Returns the messages it did not send so a manual invocation can show
    them in its response. They are deliberately not printed: a log line
    outlives the queue by years, and a reminder carries a case number.
    """

    @property
    def dry_run(self) -> bool:
        return True

    def publish(self, messages) -> dict:
        messages = list(messages)
        print(f"dry run: {len(messages)} reminder(s) not queued")
        return {
            "queued": 0,
            "failed": [],
            "dry_run": True,
            "would_send": [message.as_queue_body() for message in messages],
        }


def outbox(environ=None):
    """The outbox for the current environment, or one that queues nothing."""
    environ = os.environ if environ is None else environ
    queue_url = environ.get("OUTBOX_QUEUE_URL")
    if not queue_url or _is_true(environ.get("REMINDERS_DRY_RUN")):
        return DryRunOutbox()
    return Outbox(queue_url)


def _is_true(value) -> bool:
    return str(value).strip().lower() in _TRUE


def _batched(items, size):
    for start in range(0, len(items), size):
        yield items[start : start + size]

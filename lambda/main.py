"""Queue the court reminders that are due today.

The producer end of the reminder pipeline, and the only thing on a
schedule: CourtBotDailyReminders invokes it once a day, it asks the court
database who has a hearing seven, three and one day out, turns each of
those into a text, and puts them on the outbox queue for
CourtBotMessageSender to deliver.

    EventBridge -> CourtBotMain -> CourtBotOutbox -> CourtBotMessageSender

Invoked by hand it takes a few optional keys, none of which the scheduled
event carries:

    {}                              every threshold, as the schedule runs it
    {"thresholds": ["ONE_DAY"]}     just these (names or day counts)
    {"threshold": 7}                just this one
    {"dry_run": true}               generate and report, queue nothing

`dry_run` can only be turned on here, never off: the stack decides whether
real texts are queued (REMINDERS_DRY_RUN in cdk_stack.py), and an event
must not be able to override that.

Running twice in a day is safe. Every message carries a stable
reminder_id, so the second run queues ids the sender has already texted
and the sender drops them.
"""

import json

from reminders import DryRunOutbox, ReminderThreshold, sender_for


def handler(event, context):
    event = event if isinstance(event, dict) else {}
    thresholds = _requested(event)
    forced_dry_run = DryRunOutbox() if event.get("dry_run") else None
    print(
        "running thresholds: "
        + ", ".join(threshold.name for threshold in thresholds)
        + (" (forced dry run)" if forced_dry_run else "")
    )

    results, failures = [], []
    for threshold in thresholds:
        try:
            results.append(sender_for(threshold, outbox=forced_dry_run).run())
        except Exception as error:  # noqa: BLE001 - one bad threshold must
            # not stop the others; somebody's hearing is tomorrow.
            print(f"{threshold.name} failed: {type(error).__name__}: {error}")
            failures.append(threshold.name)
            results.append({"threshold": threshold.name, "error": str(error)})

    body = {
        "thresholds": [threshold.name for threshold in thresholds],
        "queued": sum(result.get("queued", 0) for result in results),
        "results": results,
    }
    if failures:
        # Raising is what makes a broken run visible in Lambda's metrics
        # rather than passing as a quiet success. The retry is safe for the
        # thresholds that already succeeded; their ids are already sent.
        print(json.dumps(body, default=str))
        raise RuntimeError("reminder thresholds failed: " + ", ".join(failures))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _requested(event) -> list[ReminderThreshold]:
    """The thresholds this invocation should run, defaulting to all of them.

    The scheduled event names none, so the daily run is the default path.
    """
    requested = event.get("thresholds")
    if requested is None and event.get("threshold") is not None:
        requested = [event["threshold"]]
    if requested is None:
        return list(ReminderThreshold)
    if not isinstance(requested, list):
        raise ValueError('"thresholds" must be a list')
    return [ReminderThreshold.parse(value) for value in requested]

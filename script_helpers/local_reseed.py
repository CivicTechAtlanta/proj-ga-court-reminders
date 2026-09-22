"""Reload the local court database and report what a reminder run will find.

    ./script/db/reset
    ./script/db/reset +14045551234
    uv run python script_helpers/local_reseed.py --phone +14045551234

Runs the CourtBotDatabaseLoader Lambda in Floci, the same one that seeds the
database during a deploy: it drops every table and reloads the fixtures with
their dates re-anchored to today. Re-anchoring is the point. A hearing that
was seven days out yesterday is six days out now, so within a week the 7/3/1
reminder thresholds stop matching anything and the fixtures are untestable
until somebody reseeds.

The AWS dev database gets the same treatment every Monday from the
CourtDatabaseWeeklyReseed rule in cdk_stack.py. This is the laptop
equivalent, and `./script/db/reset` runs it.

Everything in the database is destroyed, including anything added by hand.

--phone puts your own handset in the fixtures: the clean case at each lead
time gets that number instead of its reserved 555-01XX one, so one person
has a hearing seven, three and one day out and can watch all three reminders
arrive. Every other row keeps its unreachable number. It is an argument
rather than a setting on purpose, the same rule `./script/sms/verify` follows,
so no stored value can quietly become the destination.

Exits non-zero when a lead time comes back with no hearings, because a
reseed that leaves a threshold with nothing to find is not worth testing
against.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# The phone helpers live in the Lambda bundle; import them the way
# script_helpers/truedialog_check.py does.
sys.path.insert(0, str(REPO_ROOT / "lambda"))

import local_invoke  # noqa: E402
from truedialog import mask, normalize_us_phone  # noqa: E402


LOADER = "CourtBotDatabaseLoader"

# Reads better in a report than a bare number of days.
LEAD_TIME_LABELS = {"7": "seven days out", "3": "three days out", "1": "one day out"}


def _label(days: str) -> str:
    return LEAD_TIME_LABELS.get(days, f"{days} days out")


def _report(summary) -> None:
    print(f"reseeded {summary['engine']}/{summary['database']}")

    print("\nrows loaded")
    width = max(len(table) for table in summary["row_counts"])
    for table, count in summary["row_counts"].items():
        print(f"  {table:<{width}}  {count:>4}")

    print("\nhearings the reminder query returns")
    counts = summary["hearings_by_lead_time"]
    width = max(len(_label(days)) for days in counts)
    for days, count in counts.items():
        print(f"  {_label(days):<{width}}  {count:>4}")


def _report_test_phone(summary) -> None:
    test_phone = summary.get("test_phone")
    if not test_phone:
        return
    print(f"\nreminder ladder now points at {test_phone['number']}")
    width = max(len(_label(days)) for days in test_phone["cases"])
    for days, case_number in test_phone["cases"].items():
        print(f"  {_label(days):<{width}}  {case_number}")
    print(
        "\nThese rows can now reach a real handset. Every other fixture number "
        "stays in the unreachable 555-01XX range."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--phone",
        metavar="NUMBER",
        help="put this number on the clean case at each lead time, so a "
        "reminder run can text you; any US format",
    )
    args = parser.parse_args(argv)

    event = b"{}"
    if args.phone:
        # Rejected here as well as in the Lambda, so a typo is one line in
        # this terminal rather than a traceback out of CloudWatch.
        try:
            number = normalize_us_phone(args.phone)
        except ValueError as error:
            print(
                f"{error}. Pass a US number, for example +14045551234.", file=sys.stderr
            )
            return 2
        print(f"seeding the reminder ladder with {mask(number)}")
        event = json.dumps({"phone": number}).encode()

    summary = json.loads(local_invoke.invoke(LOADER, event))
    _report(summary)
    _report_test_phone(summary)

    counts = summary["hearings_by_lead_time"]
    empty = [_label(days) for days, count in counts.items() if not count]
    if empty:
        print(
            f"\nNo hearings {', '.join(empty)}. The fixtures under "
            "lambda/court_db/seed/ anchor a clean case at every lead time, so "
            "check what this seed actually loaded.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

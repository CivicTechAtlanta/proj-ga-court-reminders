"""Check the TrueDialog credentials in .env, and optionally send one text.

This lives outside the test suite on purpose. A test run must never reach an
external service or spend message credit, so the one thing that can text a
real person is a command somebody types deliberately:

    uv run python scripts/truedialog_check.py                  # checks only
    uv run python scripts/truedialog_check.py --send +14045550142

or through the script

    . script/sms/verify
    . script/sms/verify +14045550142

The recipient is an argument rather than a setting, so there is no
configured number that could quietly become the destination.
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# The wrapper lives in the Lambda bundle; import it the way the handlers do.
sys.path.insert(0, str(REPO_ROOT / "lambda"))

import env_file  # noqa: E402
from truedialog import (  # noqa: E402
    TrueDialogClient,
    TrueDialogConfig,
    TrueDialogConfigError,
    TrueDialogError,
    mask,
)

MESSAGE = "GA Court Reminders test message. Reply STOP to opt out."


def _config():
    """Settings from .env, with the shell winning where both set a value."""
    import os

    environ = {**env_file.read(), **os.environ}
    return TrueDialogConfig.from_env(environ=environ)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--send",
        metavar="PHONE",
        help="send one real text to this number; costs message credit",
    )
    args = parser.parse_args(argv)

    try:
        config = _config()
    except TrueDialogConfigError as error:
        print(f"not configured: {error}")
        return 1

    client = TrueDialogClient(config)
    print(f"account {config.account_id} over channel {config.channel_id}")

    try:
        if not client.ping():
            print("TrueDialog rejected these credentials for that account")
            return 1
        print("Trudialog credentials accepted")

        if args.send:
            result = client.send_message(args.send, MESSAGE)
            print(
                f"sent to {mask(args.send)}: action {result.action_id}, {result.status}"
            )
        else:
            print(
                "no text sent; pass --send <phone> to trudialog_check.py to send text"
            )
    except TrueDialogError as error:
        print(f"failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

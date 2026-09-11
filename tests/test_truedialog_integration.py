"""Integration tests against the real TrueDialog API.

They skip unless the TRUEDIALOG_* settings are in the environment, or in a
.env file when python-dotenv is installed:

    uv run --group integration pytest tests/test_truedialog_integration.py -v -rs

The send test additionally needs TRUEDIALOG_TEST_NUMBER, the phone that
receives the message. Leaving it unset keeps a plain `uv run pytest` from
texting anyone or spending message credit.
"""

import os

import pytest

from truedialog import TrueDialogClient, TrueDialogConfig, TrueDialogConfigError

pytestmark = pytest.mark.integration_truedialog


@pytest.fixture(scope="module")
def client():
    # .env is read here rather than at import. At import it would run during
    # collection of the whole suite, and a contributor's .env would leak its
    # values, empty ones included, into every other test's environment.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # the integration dependency group is optional
        pass

    try:
        config = TrueDialogConfig.from_env()
    except TrueDialogConfigError as error:
        pytest.skip(str(error))
    return TrueDialogClient(config)


def test_credentials_are_accepted(client):
    # Checks the configured account, not /userinfo: a key can be denied
    # /userinfo (HTTP 403) and still send perfectly well.
    assert client.ping() is True


def test_account_is_visible_to_these_credentials(client):
    account = client.account_info()
    assert str(account["id"]) == client._config.account_id


def test_send_one_hello_world_text(client):
    number = os.getenv("TRUEDIALOG_TEST_NUMBER")
    if not number:
        pytest.skip("TRUEDIALOG_TEST_NUMBER not set; not texting anyone")

    result = client.send_message(
        number, "GA Court Reminders test message. Reply STOP to opt out."
    )

    assert result.action_id
    print(f"TrueDialog action {result.action_id}: {result.status}")

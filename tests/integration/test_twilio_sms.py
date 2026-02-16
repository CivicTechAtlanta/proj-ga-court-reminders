"""Integration test: send countdown SMS reminders via Twilio.

Requires a .env file at the repo root with Twilio credentials
(see .template.env for a template).

Usage:
    uv run --group integration python -m pytest tests/integration/test_twilio_sms.py -v

Check message logs at: https://console.twilio.com/us1/develop/sms/overview
"""

import os
import time

import pytest
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

pytestmark = pytest.mark.integration_twilio


@pytest.fixture(scope="module")
def twilio_client():
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    if not account_sid or not auth_token:
        pytest.skip("Twilio credentials not configured (see .template.env)")
    return Client(account_sid, auth_token)


@pytest.fixture(scope="module")
def sms_config():
    messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
    test_number = os.getenv("TWILIO_TEST_NUMBER")
    if not messaging_service_sid or not test_number:
        pytest.skip("Twilio SMS config not set (see .template.env)")
    return {
        "messaging_service_sid": messaging_service_sid,
        "to_number": f"+{test_number}",
    }


def send_reminder(client, sms_config, message):
    """Send a reminder message via Twilio."""
    return client.messages.create(
        messaging_service_sid=sms_config["messaging_service_sid"],
        to=sms_config["to_number"],
        body=message,
    )


def test_countdown_reminders(twilio_client, sms_config):
    """Send three countdown reminder messages with delays between each."""
    msg = send_reminder(
        twilio_client, sms_config, "You have an appointment in 30 seconds"
    )
    assert msg.sid
    time.sleep(15)

    msg = send_reminder(
        twilio_client, sms_config, "You have an appointment in 15 seconds"
    )
    assert msg.sid
    time.sleep(15)

    msg = send_reminder(twilio_client, sms_config, "Your appointment is starting")
    assert msg.sid

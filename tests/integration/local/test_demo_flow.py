"""Integration test: walk through the demo flow by calling handlers directly.

No running server required — uses InMemoryStateStore.

"""

import pytest

from court_reminder.state import InMemoryStateStore
from court_reminder.twilio_handler import advance_scenario, handle_inbound_sms

pytestmark = pytest.mark.integration_local


def _make_store():
    return InMemoryStateStore()


def _sms(store, phone: str, body: str) -> str:
    messages = handle_inbound_sms(phone, body, store)
    return "\n".join(messages)


def _advance(store, phone: str) -> list[str]:
    return advance_scenario(phone, store)


class TestDemoFlow:
    def test_first_contact_sends_welcome(self):
        store = _make_store()
        text = _sms(store, "+15550000001", "hello")
        assert "which scenario" in text.lower()

    def test_invalid_input_loops_back_to_welcome(self):
        store = _make_store()
        _sms(store, "+15550000002", "hello")  # establish state
        text = _sms(store, "+15550000002", "banana")
        assert "which scenario" in text.lower()

    def test_scenario_2_unavailable(self):
        store = _make_store()
        text = _sms(store, "+15550000003", "2")
        assert "not available" in text.lower()
        assert "which scenario" in text.lower()

    def test_exit_from_home_ends_session(self):
        store = _make_store()
        text = _sms(store, "+15550000004", "EXIT")
        assert "ended" in text.lower()

    def test_full_scenario_1_flow(self):
        store = _make_store()
        phone = "+15550000005"

        # Select scenario 1
        text = _sms(store, phone, "1")
        assert "10 minutes" in text
        assert "EXIT" in text

        # Advance: countdown_7min -> countdown_3min
        messages = _advance(store, phone)
        assert any("7 minute(s)" in m for m in messages)

        # Advance: countdown_3min -> countdown_1min
        messages = _advance(store, phone)
        assert any("3 minute(s)" in m for m in messages)

        # Advance: countdown_1min -> missed
        messages = _advance(store, phone)
        assert any("1 minute(s)" in m for m in messages)

        # Advance: missed -> rescheduled
        messages = _advance(store, phone)
        assert any("reschedule" in m.lower() for m in messages)
        assert any("15 min" in m for m in messages)

    def test_inbound_sms_during_countdown_returns_acknowledgment(self):
        store = _make_store()
        phone = "+15550000006"
        _sms(store, phone, "1")  # enter scenario_1
        text = _sms(store, phone, "are we there yet?")
        assert "EXIT" in text

    def test_exit_during_countdown_ends_session(self):
        store = _make_store()
        phone = "+15550000007"
        _sms(store, phone, "1")  # state is countdown_7min
        text = _sms(store, phone, "END")
        assert "ended" in text.lower()

        # Next message should restart from welcome
        text = _sms(store, phone, "hello")
        assert "which scenario" in text.lower()

    def test_advance_home_is_empty(self):
        store = _make_store()
        messages = _advance(store, "+15550000008")
        assert messages == []

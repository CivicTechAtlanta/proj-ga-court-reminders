from court_reminder.state import ConversationState, InMemoryStateStore
from court_reminder.twilio_handler import advance_scenario, handle_inbound_sms

PHONE = "+11234567890"


def store():
    return InMemoryStateStore()


def test_first_contact_sends_welcome():
    s = store()
    msgs = handle_inbound_sms(PHONE, "hello", s)
    assert len(msgs) == 1
    assert "which scenario" in msgs[0].lower()


def test_select_scenario_1():
    s = store()
    msgs = handle_inbound_sms(PHONE, "1", s)
    assert s.get(PHONE).scenario == "scenario_1"
    assert s.get(PHONE).step == "countdown_7min"
    assert s.get(PHONE).court_datetime is not None
    assert len(msgs) == 1
    assert "10 minutes" in msgs[0]


def test_advance_through_full_countdown():
    s = store()
    handle_inbound_sms(PHONE, "1", s)  # enter scenario_1, state is now countdown_7min

    # 7min -> 3min
    msgs = advance_scenario(PHONE, s)
    assert "7 minute(s)" in msgs[0]
    assert s.get(PHONE).step == "countdown_3min"

    # 3min -> 1min
    msgs = advance_scenario(PHONE, s)
    assert "3 minute(s)" in msgs[0]
    assert s.get(PHONE).step == "countdown_1min"

    # 1min -> missed
    msgs = advance_scenario(PHONE, s)
    assert "1 minute(s)" in msgs[0]
    assert s.get(PHONE).step == "missed"

    # missed -> countdown_7min (rescheduled)
    msgs = advance_scenario(PHONE, s)
    assert "reschedule" in msgs[0].lower()
    assert s.get(PHONE).step == "countdown_7min"


def test_exit_ends_session():
    s = store()
    handle_inbound_sms(PHONE, "1", s)
    msgs = handle_inbound_sms(PHONE, "EXIT", s)
    assert "ended" in msgs[0].lower()
    assert s.get(PHONE) is None


def test_new_message_after_exit_sends_welcome():
    s = store()
    handle_inbound_sms(PHONE, "EXIT", s)
    msgs = handle_inbound_sms(PHONE, "hello", s)
    assert "which scenario" in msgs[0].lower()


def test_invalid_input_resends_welcome():
    s = store()
    msgs = handle_inbound_sms(PHONE, "banana", s)
    assert "which scenario" in msgs[-1].lower()


def test_select_scenario_2_unavailable():
    s = store()
    msgs = handle_inbound_sms(PHONE, "2", s)
    assert len(msgs) == 2
    assert "not available" in msgs[0].lower()
    assert "which scenario" in msgs[1].lower()
    assert s.get(PHONE).scenario == "home"


def test_advance_home_returns_empty():
    s = store()
    msgs = advance_scenario(PHONE, s)
    assert msgs == []

from court_reminder.state import ConversationState, InMemoryStateStore


def test_default_state():
    state = ConversationState()
    assert state.scenario == "home"
    assert state.step == "welcome"
    assert state.court_datetime is None


def test_get_missing_returns_none():
    store = InMemoryStateStore()
    assert store.get("+11234567890") is None


def test_save_and_get():
    store = InMemoryStateStore()
    state = ConversationState(scenario="scenario_1", step="countdown_7min", court_datetime="2026-01-01T12:00:00+00:00")
    store.save("+11234567890", state)
    result = store.get("+11234567890")
    assert result == state


def test_save_overwrites():
    store = InMemoryStateStore()
    phone = "+11234567890"
    store.save(phone, ConversationState(scenario="home"))
    store.save(phone, ConversationState(scenario="scenario_1", step="missed"))
    result = store.get(phone)
    assert result is not None
    assert result.scenario == "scenario_1"


def test_delete_removes_state():
    store = InMemoryStateStore()
    phone = "+11234567890"
    store.save(phone, ConversationState())
    store.delete(phone)
    assert store.get(phone) is None


def test_delete_missing_is_noop():
    store = InMemoryStateStore()
    store.delete("+10000000000")  # should not raise

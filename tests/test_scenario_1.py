from court_reminder.scenarios.scenario_1 import Scenario1


s1 = Scenario1()


def test_countdown_7min_advance():
    resp = s1.advance("countdown_7min", "2026-01-01T12:00:00+00:00")
    assert resp.next_step == "countdown_3min"
    assert "7 minute(s)" in resp.messages[0]
    assert "EXIT" in resp.messages[0]


def test_countdown_3min_advance():
    resp = s1.advance("countdown_3min", "2026-01-01T12:00:00+00:00")
    assert resp.next_step == "countdown_1min"
    assert "3 minute(s)" in resp.messages[0]


def test_countdown_1min_advance():
    resp = s1.advance("countdown_1min", "2026-01-01T12:00:00+00:00")
    assert resp.next_step == "missed"
    assert "1 minute(s)" in resp.messages[0]


def test_missed_advance_resets_to_countdown_7min():
    resp = s1.advance("missed", "2026-01-01T12:00:00+00:00")
    assert resp.next_step == "countdown_7min"
    assert resp.court_datetime is not None
    assert resp.court_datetime != "2026-01-01T12:00:00+00:00"
    assert "reschedule" in resp.messages[0].lower()
    assert "15 min" in resp.messages[0]


def test_handle_during_countdown_returns_acknowledgment():
    resp = s1.handle("countdown_7min", "are we there yet?", "2026-01-01T12:00:00+00:00")
    assert resp.next_step == "countdown_7min"
    assert resp.next_scenario == "scenario_1"
    assert "EXIT" in resp.messages[0]


def test_advance_unknown_step_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown step"):
        s1.advance("bogus_step", None)

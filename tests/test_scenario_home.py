from court_reminder.scenarios.home import HomeScenario


home = HomeScenario()


def test_first_contact_sends_welcome():
    resp = home.handle("welcome", "hello", None)
    assert len(resp.messages) == 1
    assert "which scenario" in resp.messages[0].lower()
    assert resp.next_scenario == "home"
    assert resp.next_step == "welcome"


def test_valid_selection_1_routes_to_scenario_1():
    resp = home.handle("welcome", "1", None)
    assert resp.next_scenario == "scenario_1"
    assert resp.next_step == "countdown_7min"
    assert resp.court_datetime is not None
    assert len(resp.messages) == 1
    assert "10 minutes" in resp.messages[0]
    assert "EXIT" in resp.messages[0]


def test_unavailable_scenario_2_loops_back():
    resp = home.handle("welcome", "2", None)
    assert resp.next_scenario == "home"
    assert resp.next_step == "welcome"
    assert len(resp.messages) == 2
    assert "not available" in resp.messages[0].lower()
    assert "which scenario" in resp.messages[1].lower()


def test_invalid_input_resends_welcome():
    for body in ["banana", "99", "", "3"]:
        resp = home.handle("welcome", body, None)
        assert resp.next_scenario == "home"
        assert "which scenario" in resp.messages[-1].lower()

"""Twilio webhook handler for incoming and outgoing SMS."""

from court_reminder.message_parser import parse
from court_reminder.scenarios.home import HomeScenario
from court_reminder.scenarios.scenario_1 import Scenario1
from court_reminder.state import ConversationState, StateStore

_EXIT_MESSAGE = "Thanks for trying the GA Court Reminder demo! Your session has ended."

_SCENARIOS = {
    "home": HomeScenario(),
    "scenario_1": Scenario1(),
}


def handle_inbound_sms(phone: str, body: str, state_store: StateStore) -> list[str]:
    """Process an inbound SMS and return outbound message bodies."""
    msg = parse(body)

    if msg.is_exit:
        state_store.delete(phone)
        return [_EXIT_MESSAGE]

    state = state_store.get(phone) or ConversationState()
    scenario = _SCENARIOS[state.scenario]
    response = scenario.handle(state.step, body, state.court_datetime)

    state_store.save(
        phone,
        ConversationState(
            scenario=response.next_scenario,
            step=response.next_step,
            court_datetime=response.court_datetime,
        ),
    )
    return response.messages


def advance_scenario(phone: str, state_store: StateStore) -> list[str]:
    """Advance the timed scenario step. Returns [] if the scenario has no timed steps."""
    state = state_store.get(phone) or ConversationState()

    if state.scenario == "home":
        return []

    scenario = _SCENARIOS[state.scenario]
    response = scenario.advance(state.step, state.court_datetime)

    state_store.save(
        phone,
        ConversationState(
            scenario=response.next_scenario,
            step=response.next_step,
            court_datetime=response.court_datetime,
        ),
    )
    return response.messages

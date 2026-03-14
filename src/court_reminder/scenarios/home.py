"""Home scenario — demo entry point and scenario selector."""

from court_reminder.message_parser import parse
from court_reminder.scenarios._utils import format_dt, now_plus, _EXIT_HINT
from court_reminder.scenarios.base import BaseScenario, ScenarioResponse

_WELCOME = (
    "Welcome to the GA Court Reminder demo - which scenario do you want to play out?\n\n"
    "(1) 7, 3, 1 countdown\n"
    "(2) Missed + Warrant [Unavailable atm]"
)

_UNAVAILABLE = "Sorry, that scenario is not available yet."


class HomeScenario(BaseScenario):
    def handle(self, step: str, message_body: str, court_datetime: str | None) -> ScenarioResponse:
        msg = parse(message_body)

        if msg.scenario_choice == 1:
            dt = now_plus(10)
            return ScenarioResponse(
                messages=[
                    f"Welcome - your fake court date is 10 minutes from now at {format_dt(dt)}. "
                    "We'll text you 7 min, 3 min, and 1 min before your fake court date."
                    + _EXIT_HINT
                ],
                next_scenario="scenario_1",
                next_step="countdown_7min",
                court_datetime=dt,
            )

        if msg.scenario_choice == 2:
            return ScenarioResponse(
                messages=[_UNAVAILABLE, _WELCOME],
                next_scenario="home",
                next_step="welcome",
            )

        return ScenarioResponse(
            messages=[_WELCOME],
            next_scenario="home",
            next_step="welcome",
        )

    def advance(self, step: str, court_datetime: str | None) -> ScenarioResponse:
        raise NotImplementedError("HomeScenario has no timed advance steps")

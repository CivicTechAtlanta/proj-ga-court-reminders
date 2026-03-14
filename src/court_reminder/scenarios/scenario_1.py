"""Scenario 1 — 7-3-1 countdown demo flow."""

from court_reminder.scenarios._utils import format_dt, now_plus, _EXIT_HINT
from court_reminder.scenarios.base import BaseScenario, ScenarioResponse

_LOCATION = "1234 Main St, Atlanta, GA\nCourt Room ABC"


def _reminder(n: int, court_datetime: str) -> str:
    return (
        f"Your fake court date is {n} minute(s) from now.\n\n"
        f"Details:\n{_LOCATION}\n{format_dt(court_datetime)}"
        + _EXIT_HINT
    )


class Scenario1(BaseScenario):
    def handle(self, step: str, message_body: str, court_datetime: str | None) -> ScenarioResponse:
        """Acknowledge inbound SMS during a running countdown."""
        return ScenarioResponse(
            messages=["Your countdown is running. Text EXIT / FINISH / END to end the demo."],
            next_scenario="scenario_1",
            next_step=step,
            court_datetime=court_datetime,
        )

    def advance(self, step: str, court_datetime: str | None) -> ScenarioResponse:
        if step == "countdown_7min":
            return ScenarioResponse(
                messages=[_reminder(7, court_datetime)],  # type: ignore[arg-type]
                next_scenario="scenario_1",
                next_step="countdown_3min",
                court_datetime=court_datetime,
            )

        if step == "countdown_3min":
            return ScenarioResponse(
                messages=[_reminder(3, court_datetime)],  # type: ignore[arg-type]
                next_scenario="scenario_1",
                next_step="countdown_1min",
                court_datetime=court_datetime,
            )

        if step == "countdown_1min":
            return ScenarioResponse(
                messages=[_reminder(1, court_datetime)],  # type: ignore[arg-type]
                next_scenario="scenario_1",
                next_step="missed",
                court_datetime=court_datetime,
            )

        if step == "missed":
            dt = now_plus(15)
            return ScenarioResponse(
                messages=[
                    f"We noticed you missed your court date. You'll need to reschedule.\n\n"
                    f"For this demo, we'll reschedule you 15 min from now at {format_dt(dt)}"
                    + _EXIT_HINT
                ],
                next_scenario="scenario_1",
                next_step="countdown_7min",
                court_datetime=dt,
            )

        raise ValueError(f"Unknown step for Scenario1.advance: {step!r}")

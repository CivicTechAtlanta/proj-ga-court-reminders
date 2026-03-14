"""Base scenario interface for conversation flows."""

from dataclasses import dataclass


@dataclass
class ScenarioResponse:
    messages: list[str]
    next_scenario: str
    next_step: str
    court_datetime: str | None = None


class BaseScenario:
    def handle(self, step: str, message_body: str, court_datetime: str | None) -> ScenarioResponse:
        raise NotImplementedError

    def advance(self, step: str, court_datetime: str | None) -> ScenarioResponse:
        raise NotImplementedError

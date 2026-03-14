"""Parse incoming SMS messages into structured commands."""

from dataclasses import dataclass

_EXIT_WORDS = {"exit", "finish", "end"}


@dataclass
class ParsedMessage:
    raw: str
    is_exit: bool
    scenario_choice: int | None


def parse(body: str) -> ParsedMessage:
    stripped = body.strip()
    lowered = stripped.lower()

    if lowered in _EXIT_WORDS:
        return ParsedMessage(raw=body, is_exit=True, scenario_choice=None)
    elif stripped.isdigit():
        return ParsedMessage(raw=body, is_exit=False, scenario_choice=int(stripped))
    else:
        return ParsedMessage(raw=body, is_exit=False, scenario_choice=None)

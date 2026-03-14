import pytest

from court_reminder.message_parser import ParsedMessage, parse


@pytest.mark.parametrize("word", ["EXIT", "exit", "Finish", "finish", "END", "end"])
def test_exit_words(word):
    result = parse(word)
    assert result.is_exit is True
    assert result.scenario_choice is None


@pytest.mark.parametrize("word", ["EXIT", "exit", "  exit  "])
def test_exit_strips_whitespace(word):
    assert parse(word).is_exit is True


@pytest.mark.parametrize("choice,expected", [("1", 1), ("2", 2), ("99", 99)])
def test_valid_scenario_choices(choice, expected):
    result = parse(choice)
    assert result.is_exit is False
    assert result.scenario_choice == expected


@pytest.mark.parametrize("body", ["banana", "", "hello world", "1a", "a1"])
def test_invalid_input(body):
    result = parse(body)
    assert result.is_exit is False
    assert result.scenario_choice is None


def test_raw_preserved():
    body = "  EXIT  "
    result = parse(body)
    assert result.raw == body

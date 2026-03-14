"""Conversation state management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ConversationState:
    scenario: str = "home"
    step: str = "welcome"
    court_datetime: str | None = None


class StateStore(Protocol):
    def get(self, phone: str) -> ConversationState | None: ...
    def save(self, phone: str, state: ConversationState) -> None: ...
    def delete(self, phone: str) -> None: ...


class InMemoryStateStore:
    def __init__(self) -> None:
        self._store: dict[str, ConversationState] = {}

    def get(self, phone: str) -> ConversationState | None:
        return self._store.get(phone)

    def save(self, phone: str, state: ConversationState) -> None:
        self._store[phone] = state

    def delete(self, phone: str) -> None:
        self._store.pop(phone, None)


class AzureTableStateStore:
    """Stubbed out — raises NotImplementedError. Implement before deploying to prod."""
    def __init__(self, table_client: object) -> None:
        self._table_client = table_client

    def get(self, phone: str) -> ConversationState | None:
        raise NotImplementedError

    def save(self, phone: str, state: ConversationState) -> None:
        raise NotImplementedError

    def delete(self, phone: str) -> None:
        raise NotImplementedError

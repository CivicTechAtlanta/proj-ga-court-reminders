"""The CourtBotMain handler reports upcoming hearings through the wrapper."""

import json
from datetime import datetime

import main
from court_db import Hearing


class FakeRepository:
    def upcoming_hearings(self, days_ahead=7):
        return [
            Hearing(
                case_id=1,
                case_party_id=2,
                case_number="CR-2026-000101",
                event_type="Arraignment",
                event_datetime=datetime(2026, 9, 8, 9, 0),
                court_room="Courtroom 1A",
                phone_type="CELL",
                phone_number="(404) 555-0101",
            )
        ]


def test_handler_returns_hearings_as_json(monkeypatch):
    monkeypatch.setattr(main, "court_case_repository", lambda: FakeRepository())

    response = main.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["upcoming_hearings"] == 1
    assert body["hearings"][0]["case_number"] == "CR-2026-000101"
    assert body["hearings"][0]["event_datetime"] == "2026-09-08 09:00:00"

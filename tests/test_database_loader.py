"""The seed Lambda follows the CloudFormation custom-resource protocol."""

import json

import pytest

import database_loader
from court_db import DatabaseConfig


def sqlserver_config():
    return DatabaseConfig(
        engine="sqlserver",
        host="h",
        port=1433,
        database="courtdb",
        user="u",
        password="p",
    )


class FakeRepository:
    def upcoming_hearings(self, days_ahead=7):
        return [object()] * 11


@pytest.fixture()
def seeded(monkeypatch):
    calls = []
    monkeypatch.setattr(
        database_loader.DatabaseConfig, "from_env", staticmethod(sqlserver_config)
    )
    monkeypatch.setattr(
        database_loader,
        "load_fixtures",
        lambda config: (
            calls.append(config)
            or {"database": "courtdb", "row_counts": {"tblCase": 11}}
        ),
    )
    monkeypatch.setattr(
        database_loader, "court_case_repository", lambda config: FakeRepository()
    )
    return calls


def test_create_seeds_and_reports_data_for_cloudformation(seeded):
    response = database_loader.handler({"RequestType": "Create"}, None)

    assert len(seeded) == 1
    assert response["PhysicalResourceId"] == "court-database-seed"
    assert response["Data"]["UpcomingHearings"] == "11"
    assert json.loads(response["Data"]["RowCounts"]) == {"tblCase": 11}


def test_update_reseeds(seeded):
    database_loader.handler(
        {"RequestType": "Update", "PhysicalResourceId": "court-database-seed"}, None
    )
    assert len(seeded) == 1


def test_delete_never_touches_the_database(seeded):
    response = database_loader.handler(
        {"RequestType": "Delete", "PhysicalResourceId": "court-database-seed"}, None
    )
    assert seeded == []
    assert response == {"PhysicalResourceId": "court-database-seed"}


def test_direct_invoke_returns_the_summary(seeded):
    summary = database_loader.handler({}, None)
    assert summary["upcoming_hearings"] == 11
    assert summary["row_counts"] == {"tblCase": 11}


def test_refuses_non_sqlserver_engines(monkeypatch):
    monkeypatch.setattr(
        database_loader.DatabaseConfig,
        "from_env",
        staticmethod(lambda: DatabaseConfig("postgres", "h", 5432, "d", "u", "p")),
    )
    with pytest.raises(RuntimeError, match="SQL Server only"):
        database_loader.handler({"RequestType": "Create"}, None)

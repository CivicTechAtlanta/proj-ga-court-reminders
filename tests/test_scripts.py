"""The helper scripts' decision logic, with Docker and AWS faked out."""

import pytest

import local_cleanup
import local_db_url


def test_cleanup_claims_stack_containers_by_name(monkeypatch):
    monkeypatch.setattr(
        local_cleanup, "_inspect", lambda name: pytest.fail("no inspect needed")
    )
    assert local_cleanup._belongs_to_project(
        "floci-CourtReminderStack-CourtBotMain-abc"
    )
    assert local_cleanup._belongs_to_project("floci-CourtDatabaseStack-CustomVpc-abc")
    assert not local_cleanup._belongs_to_project("cms_postgres")


@pytest.mark.parametrize("name", ["floci-rds-4bf1c7", "floci-ecr-registry"])
def test_cleanup_claims_shared_helpers_only_on_the_project_network(monkeypatch, name):
    networks = {}
    monkeypatch.setattr(
        local_cleanup, "_inspect", lambda n: {"NetworkSettings": {"Networks": networks}}
    )
    networks.clear()
    networks["bridge"] = {}
    assert not local_cleanup._belongs_to_project(name)
    networks[local_cleanup.PROJECT_NETWORK] = {}
    assert local_cleanup._belongs_to_project(name)


def test_cleanup_removes_only_what_it_claimed_and_reports_volumes(monkeypatch):
    calls = []
    monkeypatch.setattr(
        local_cleanup,
        "_docker",
        lambda *args: {
            (
                "ps",
                "--all",
                "--format",
                "{{.Names}}",
            ): "floci-CourtReminderStack-a\nother\n",
            (
                "volume",
                "ls",
                "--quiet",
            ): "floci-code-CourtReminderStack-a\nfloci-rds-1\nunrelated\n",
        }[args],
    )
    monkeypatch.setattr(
        local_cleanup,
        "_inspect",
        lambda n: {
            "NetworkSettings": {"Networks": {}},
            "Mounts": [
                {"Type": "volume", "Name": "floci-rds-1"},
                {"Type": "bind", "Name": "x"},
            ],
        },
    )
    monkeypatch.setattr(
        local_cleanup.subprocess, "run", lambda cmd, check: calls.append(cmd)
    )
    monkeypatch.setattr("sys.argv", ["local_cleanup.py", "--volumes"])

    local_cleanup.main()

    assert calls == [
        ["docker", "rm", "--force", "floci-CourtReminderStack-a"],
        ["docker", "volume", "rm", "floci-code-CourtReminderStack-a", "floci-rds-1"],
    ]


def test_db_url_resolves_resources_through_the_stack():
    resources = [
        {
            "ResourceType": "AWS::RDS::DBInstance",
            "LogicalResourceId": "CourtCaseDatabaseF7",
            "PhysicalResourceId": "inst-1",
        },
        {
            "ResourceType": "AWS::SecretsManager::Secret",
            "LogicalResourceId": "CourtCaseDatabaseCredentials65",
            "PhysicalResourceId": "arn:secret",
        },
        {
            "ResourceType": "AWS::SecretsManager::Secret",
            "LogicalResourceId": "SomethingElse",
            "PhysicalResourceId": "arn:other",
        },
    ]
    assert (
        local_db_url._physical_id(
            resources, "AWS::RDS::DBInstance", "CourtCaseDatabase"
        )
        == "inst-1"
    )
    assert (
        local_db_url._physical_id(
            resources, "AWS::SecretsManager::Secret", "CourtCaseDatabaseCredentials"
        )
        == "arn:secret"
    )
    with pytest.raises(SystemExit, match="found 0"):
        local_db_url._physical_id(resources, "AWS::RDS::DBInstance", "Missing")

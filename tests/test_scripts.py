"""The helper scripts' decision logic, with Docker and AWS faked out."""

import json

import pytest

import env_file
import local_cdk_deploy
import local_cleanup
import local_db_url
import local_reseed


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


def test_env_file_reads_key_value_pairs(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "# TrueDialog\n"
        "TRUEDIALOG_API_KEY=abc\n"
        'TRUEDIALOG_API_SECRET="s3cr=3t"\n'
        "TRUEDIALOG_ACCOUNT_ID = 777 \n"
        "EMPTY=\n"
        "\n"
        "export FOO='bar'\n"
        "not a setting\n"
    )
    assert env_file.read(path) == {
        "TRUEDIALOG_API_KEY": "abc",
        "TRUEDIALOG_API_SECRET": "s3cr=3t",
        "TRUEDIALOG_ACCOUNT_ID": "777",
        "EMPTY": "",
        "FOO": "bar",
    }
    assert env_file.read(tmp_path / "missing") == {}


def test_local_deploy_lets_the_shell_override_dotenv(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("TRUEDIALOG_API_KEY=from-file\nTRUEDIALOG_ACCOUNT_ID=777\n")
    monkeypatch.setattr(env_file, "ENV_FILE", path)
    monkeypatch.setenv("TRUEDIALOG_API_KEY", "from-shell")
    # Stated rather than assumed: a developer running this with a real .env
    # already loaded would otherwise see their own value win.
    monkeypatch.delenv("TRUEDIALOG_ACCOUNT_ID", raising=False)

    environment = local_cdk_deploy._deploy_environment()

    assert environment["TRUEDIALOG_API_KEY"] == "from-shell"
    assert environment["TRUEDIALOG_ACCOUNT_ID"] == "777"


def reseed_summary(counts=None, **top_level):
    """What the seed Lambda answers a direct invoke with. `counts` overrides
    individual lead times; anything else lands at the top of the summary."""
    return json.dumps(
        {
            "engine": "postgres",
            "database": "courtdb",
            "row_counts": {"tblCase": 14, "tblCaseEvent": 28},
            "hearings_by_lead_time": {"7": 12, "3": 3, "1": 2, **(counts or {})},
            **top_level,
        }
    )


def fake_loader(monkeypatch, summary=None, calls=None, events=None):
    """Stand in for the seed Lambda, recording what was invoked and with what."""
    answer = reseed_summary() if summary is None else summary

    def invoke(function, payload=b"{}"):
        if calls is not None:
            calls.append(function)
        if events is not None:
            events.append(json.loads(payload))
        return answer

    monkeypatch.setattr(local_reseed.local_invoke, "invoke", invoke)


def test_reseed_runs_the_seed_lambda_and_reports_every_lead_time(monkeypatch, capsys):
    calls = []
    fake_loader(monkeypatch, calls=calls)

    assert local_reseed.main([]) == 0

    assert calls == ["CourtBotDatabaseLoader"]
    lines = [" ".join(line.split()) for line in capsys.readouterr().out.splitlines()]
    assert "reseeded postgres/courtdb" in lines
    assert "tblCaseEvent 28" in lines
    # Days named rather than numbered: the report is read, not parsed.
    assert "seven days out 12" in lines
    assert "three days out 3" in lines
    assert "one day out 2" in lines


def test_reseed_fails_when_a_lead_time_has_nothing_to_fire_on(monkeypatch, capsys):
    """A seed that leaves a threshold empty is worse than a loud failure: the
    reminder run that finds nothing looks exactly like one with nothing due."""
    fake_loader(monkeypatch, summary=reseed_summary({"3": 0}))

    assert local_reseed.main([]) == 1

    error = capsys.readouterr().err
    assert "three days out" in error
    assert "lambda/court_db/seed/" in error


def test_reseed_labels_a_lead_time_it_does_not_know(monkeypatch, capsys):
    fake_loader(monkeypatch, summary=reseed_summary({"14": 4}))

    assert local_reseed.main([]) == 0

    lines = [" ".join(line.split()) for line in capsys.readouterr().out.splitlines()]
    assert "14 days out 4" in lines


def test_reseed_sends_no_phone_unless_asked(monkeypatch, capsys):
    events = []
    fake_loader(monkeypatch, events=events)

    assert local_reseed.main([]) == 0

    assert events == [{}]
    assert "points at" not in capsys.readouterr().out


def test_reseed_passes_a_normalized_phone_and_says_which_cases_took_it(
    monkeypatch, capsys
):
    events = []
    fake_loader(
        monkeypatch,
        events=events,
        summary=reseed_summary(
            test_phone={
                "number": "***1234",
                "cases": {
                    "7": "CR-2026-000112",
                    "3": "CR-2026-000113",
                    "1": "CR-2026-000114",
                },
            }
        ),
    )

    assert local_reseed.main(["--phone", "(404) 555-1234"]) == 0

    # Normalized before it leaves this machine, whatever format was typed.
    assert events == [{"phone": "+14045551234"}]
    out = capsys.readouterr().out
    lines = [" ".join(line.split()) for line in out.splitlines()]
    assert "seven days out CR-2026-000112" in lines
    assert "three days out CR-2026-000113" in lines
    assert "one day out CR-2026-000114" in lines
    # The whole number never reaches the terminal, only its last four digits.
    assert "***1234" in out
    assert "4045551234" not in out


def test_reseed_refuses_a_bad_phone_without_touching_the_database(monkeypatch, capsys):
    calls = []
    fake_loader(monkeypatch, calls=calls)

    assert local_reseed.main(["--phone", "555-0134"]) == 2

    assert calls == []
    assert "Not a valid US phone number" in capsys.readouterr().err

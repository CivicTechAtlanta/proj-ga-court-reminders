"""Template assertions for both CDK modes.

Bundling is disabled through the aws:cdk:bundling-stacks context so no
Docker is needed; the assets are never built, only referenced. The rest of
the context comes from cdk.json so these tests see the project's real
feature flags (strong cross-stack references among them).
"""

import json
from pathlib import Path

import aws_cdk
import pytest
from aws_cdk.assertions import Match, Template

import cdk_stack as reminder_module
import database_stack as database_module
from cdk_stack import CourtReminderStack
from database_stack import CourtDatabaseStack
from github_stack import GithubDeployStack

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV = aws_cdk.Environment(account="123456789012", region="us-east-1")


def synth(local: bool, machine: str = "x86_64"):
    context = json.loads((REPO_ROOT / "cdk.json").read_text())["context"]
    context["aws:cdk:bundling-stacks"] = []
    app = aws_cdk.App(context=context)
    database = CourtDatabaseStack(app, "CourtDatabaseStack", local=local, env=ENV)
    original = reminder_module.platform.machine
    reminder_module.platform.machine = lambda: machine
    try:
        reminder = CourtReminderStack(
            app, "CourtReminderStack", database=database, env=ENV
        )
    finally:
        reminder_module.platform.machine = original
    return Template.from_stack(database), Template.from_stack(reminder)


def functions(template):
    return template.find_resources("AWS::Lambda::Function")


# ---------------------------------------------------------------- AWS mode


def test_aws_database_is_encrypted_private_sql_server_with_no_nat():
    database, _ = synth(local=False)
    database.has_resource_properties(
        "AWS::RDS::DBInstance",
        {
            "Engine": "sqlserver-ex",
            "DBInstanceIdentifier": "courtbot-dev",
            "StorageEncrypted": True,
            "PubliclyAccessible": False,
            "DeletionProtection": False,
        },
    )
    database.resource_count_is("AWS::EC2::NatGateway", 0)
    database.resource_count_is("AWS::EC2::VPCEndpoint", 1)
    database.resource_count_is("AWS::SecretsManager::SecretTargetAttachment", 1)
    database.resource_count_is("Custom::VpcRestrictDefaultSG", 1)


def test_aws_lambdas_join_the_vpc_and_read_the_secret():
    _, reminder = synth(local=False)
    lambdas = functions(reminder)
    assert len(lambdas) == 5  # four handlers plus the seed loader
    for logical_id, resource in lambdas.items():
        properties = resource["Properties"]
        assert "VpcConfig" in properties, logical_id
        assert "Architectures" not in properties, logical_id  # x86-64 default
        env = properties["Environment"]["Variables"]
        assert env["COURT_DB_ENGINE"] == "sqlserver"
        assert env["COURT_DB_NAME"] == "courtdb"
        assert "COURT_DB_SECRET_ID" in env
    reminder.resource_count_is("AWS::IAM::Policy", 5)
    reminder.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Action": Match.array_with(
                                    ["secretsmanager:GetSecretValue"]
                                )
                            }
                        )
                    ]
                )
            }
        },
    )


def test_seed_custom_resource_is_served_by_the_loader_directly():
    _, reminder = synth(local=False)
    seeds = reminder.find_resources("Custom::CourtDatabaseSeed")
    assert len(seeds) == 1
    (seed,) = seeds.values()
    token = json.dumps(seed["Properties"]["ServiceToken"])
    assert "CourtBotDatabaseLoader" in token
    assert len(seed["Properties"]["SeedVersion"]) == 12
    assert not any("framework" in name for name in functions(reminder))
    reminder.has_output("CourtDatabaseSeedHearings", {})


def test_cross_stack_values_are_exported_not_weak_references():
    _, reminder = synth(local=False)
    rendered = json.dumps(reminder.to_json())
    assert "Fn::ImportValue" in rendered
    assert "Fn::GetStackOutput" not in rendered


# -------------------------------------------------------------- local mode


def test_local_database_is_postgres_with_plain_credentials_and_no_sg_lockdown():
    database, _ = synth(local=True)
    database.has_resource_properties(
        "AWS::RDS::DBInstance",
        {"Engine": "postgres", "DBName": "courtdb", "MasterUsername": "court"},
    )
    database.resource_count_is("Custom::VpcRestrictDefaultSG", 0)
    database.resource_count_is("AWS::SecretsManager::SecretTargetAttachment", 0)
    (instance,) = database.find_resources("AWS::RDS::DBInstance").values()
    assert "DBInstanceIdentifier" not in instance["Properties"]
    (secret,) = database.find_resources("AWS::SecretsManager::Secret").values()
    rendered = json.dumps(secret["Properties"]["SecretString"])
    for fragment in ('"username":"court"', '"password":"court"', '"dbname":"courtdb"'):
        assert fragment in rendered.replace(" ", "").replace("\\", "")


@pytest.mark.parametrize(
    ("machine", "expected"),
    [("arm64", "arm64"), ("aarch64", "arm64"), ("x86_64", "x86_64")],
)
def test_local_lambdas_are_built_for_the_host_architecture(machine, expected):
    _, reminder = synth(local=True, machine=machine)
    for logical_id, resource in functions(reminder).items():
        properties = resource["Properties"]
        assert properties["Architectures"] == [expected], logical_id
        assert properties["Environment"]["Variables"]["COURT_DB_ENGINE"] == "postgres"


def test_seed_version_changes_when_a_seed_script_changes(tmp_path, monkeypatch):
    scripts = tmp_path / "postgres"
    scripts.mkdir()
    (scripts / "01-schema.sql").write_text("CREATE TABLE a (x int);")
    monkeypatch.setattr(reminder_module, "_SEED_ROOT", tmp_path)
    before = reminder_module._seed_version()

    (scripts / "01-schema.sql").write_text("CREATE TABLE a (x int, y int);")
    assert reminder_module._seed_version() != before
    assert len(before) == 12


def test_database_stack_rejects_nothing_but_exposes_engine_and_flags():
    app = aws_cdk.App()
    assert CourtDatabaseStack(app, "A", local=True).engine == "postgres"
    assert CourtDatabaseStack(app, "B").engine == "sqlserver"
    assert database_module.CourtDatabaseStack(app, "C", local=False).local is False


# ------------------------------------------------------- GitHub Actions role


def test_github_role_can_assume_the_cdk_bootstrap_roles():
    app = aws_cdk.App()
    template = Template.from_stack(GithubDeployStack(app, "GithubActionStack"))
    (policy,) = template.find_resources("AWS::IAM::Policy").values()
    statements = policy["Properties"]["PolicyDocument"]["Statement"]
    assume = [s for s in statements if s["Action"] == "sts:AssumeRole"]
    assert len(assume) == 1
    assert "cdk-hnb659fds-*" in json.dumps(assume[0]["Resource"])
    # The role itself must still be assumable only from this repo's main branch.
    (role,) = template.find_resources("AWS::IAM::Role").values()
    trust = json.dumps(role["Properties"]["AssumeRolePolicyDocument"])
    assert "repo:CivicTechAtlanta/proj-ga-court-reminders:ref:refs/heads/main" in trust

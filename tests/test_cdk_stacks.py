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


def assert_endpoints(database):
    """Secrets Manager (interface, for the credentials) and S3 (gateway, for
    the seed Lambda's answer to CloudFormation): the isolated subnets have no
    other route to either."""
    endpoints = database.find_resources("AWS::EC2::VPCEndpoint")
    by_type = {}
    for resource in endpoints.values():
        props = resource["Properties"]
        by_type[props.get("VpcEndpointType", "Gateway")] = json.dumps(
            props["ServiceName"]
        )
    assert set(by_type) == {"Interface", "Gateway"}, by_type
    assert "secretsmanager" in by_type["Interface"]
    assert ".s3" in by_type["Gateway"]


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
    assert_endpoints(database)
    database.resource_count_is("AWS::SecretsManager::SecretTargetAttachment", 1)
    database.resource_count_is("Custom::VpcRestrictDefaultSG", 1)


def test_aws_lambdas_join_the_vpc_and_read_the_secret():
    _, reminder = synth(local=False)
    lambdas = functions(reminder)
    assert len(lambdas) == 5  # four handlers plus the seed loader
    for logical_id, resource in lambdas.items():
        properties = resource["Properties"]
        assert "Architectures" not in properties, logical_id  # x86-64 default
        env = properties["Environment"]["Variables"]
        if properties["Handler"] == "message_sender.handler":
            # The sender lives outside the VPC so it can reach TrueDialog.
            assert "VpcConfig" not in properties
            assert not any(name.startswith("COURT_DB_") for name in env)
            continue
        assert "VpcConfig" in properties, logical_id
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


def loader(template):
    """Logical id of the CourtBotDatabaseLoader function."""
    ((logical_id, _),) = [
        (logical_id, resource)
        for logical_id, resource in functions(template).items()
        if resource["Properties"]["Handler"] == "database_loader.handler"
    ]
    return logical_id


def test_the_dev_database_reseeds_itself_every_morning():
    """Fixture dates are relative to the day they load, so a week after a
    deploy nothing sits at the 7/3/1 reminder thresholds and the environment
    is untestable until somebody reseeds it."""
    _, reminder = synth(local=False)

    ((rule_id, rule),) = reminder.find_resources("AWS::Events::Rule").items()
    assert rule["Properties"]["ScheduleExpression"] == (
        f"cron(0 {reminder_module.RESEED_HOUR_UTC} * * ? *)"
    )
    (target,) = rule["Properties"]["Targets"]
    assert target["Arn"] == {"Fn::GetAtt": [loader(reminder), "Arn"]}
    # The empty event the loader reads as "seed and return the summary", the
    # same one `. script/db/reset` sends; anything else looks like CloudFormation.
    assert target["Input"] == "{}"

    reminder.has_resource_properties(
        "AWS::Lambda::Permission",
        {
            "Action": "lambda:InvokeFunction",
            "Principal": "events.amazonaws.com",
            "SourceArn": {"Fn::GetAtt": [rule_id, "Arn"]},
        },
    )
    reminder.has_output("CourtDatabaseDailyReseedRule", {"Value": {"Ref": rule_id}})


def test_the_seed_waits_for_its_log_group():
    """Otherwise the loader's first run creates the group itself and the
    stack fails with "The specified log group already exists"."""
    _, reminder = synth(local=False)

    (seed,) = reminder.find_resources("Custom::CourtDatabaseSeed").values()
    (log_group_id,) = [
        logical_id
        for logical_id in reminder.find_resources("AWS::Logs::LogGroup")
        if logical_id.startswith("CourtBotDatabaseLoaderLogGroup")
    ]
    assert log_group_id in seed["DependsOn"]


def test_cross_stack_values_are_exported_not_weak_references():
    _, reminder = synth(local=False)
    rendered = json.dumps(reminder.to_json())
    assert "Fn::ImportValue" in rendered
    assert "Fn::GetStackOutput" not in rendered


def secret_string(secret):
    """The SecretString of a synthesized secret as text, joining a Fn::Join
    of literal parts when CDK renders it that way."""
    value = secret["Properties"]["SecretString"]
    if isinstance(value, str):
        return value
    return "".join(value["Fn::Join"][1])


def sender(template):
    """Logical id and resource of the CourtBotMessageSender function."""
    ((logical_id, resource),) = [
        (logical_id, resource)
        for logical_id, resource in functions(template).items()
        if resource["Properties"]["Handler"] == "message_sender.handler"
    ]
    return logical_id, resource


def secret_named(template, prefix):
    """Logical id and resource of the one secret whose id starts with prefix."""
    ((logical_id, resource),) = [
        (logical_id, resource)
        for logical_id, resource in template.find_resources(
            "AWS::SecretsManager::Secret"
        ).items()
        if logical_id.startswith(prefix)
    ]
    return logical_id, resource


def statements_granting(template, action):
    for policy in template.find_resources("AWS::IAM::Policy").values():
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]:
            actions = statement["Action"]
            if action in ([actions] if isinstance(actions, str) else actions):
                resources = statement["Resource"]
                yield [resources] if not isinstance(resources, list) else resources


def test_aws_sender_reads_the_truedialog_secret(monkeypatch):
    # AWS mode never copies the deployer's environment into the template.
    monkeypatch.setenv("TRUEDIALOG_API_KEY", "must-not-leak")
    _, reminder = synth(local=False)

    logical_id, secret = secret_named(reminder, "TrueDialogCredentials")
    assert json.loads(secret_string(secret)) == {
        "api_key": "",
        "api_secret": "",
        "account_id": "",
        "channel_id": "22",
    }
    reference = {"Ref": logical_id}
    for name, resource in functions(reminder).items():
        env = resource["Properties"]["Environment"]["Variables"]
        if resource["Properties"]["Handler"] == "message_sender.handler":
            assert env["TRUEDIALOG_SECRET_ID"] == reference
        else:
            assert "TRUEDIALOG_SECRET_ID" not in env, name
    assert any(
        reference in resources
        for resources in statements_granting(reminder, "secretsmanager:GetSecretValue")
    )
    reminder.has_output("TrueDialogSecretArn", {"Value": reference})


def test_sender_has_a_public_url_guarded_by_a_generated_api_key():
    _, reminder = synth(local=False)
    sender_id, sender_resource = sender(reminder)

    (url,) = reminder.find_resources("AWS::Lambda::Url").values()
    assert url["Properties"]["AuthType"] == "NONE"
    assert url["Properties"]["TargetFunctionArn"] == {"Fn::GetAtt": [sender_id, "Arn"]}
    reminder.has_resource_properties(
        "AWS::Lambda::Permission",
        {
            "Action": "lambda:InvokeFunctionUrl",
            "FunctionUrlAuthType": "NONE",
            "Principal": "*",
        },
    )

    key_id, key = secret_named(reminder, "SenderApiKey")
    assert key["Properties"]["GenerateSecretString"] == {
        "ExcludePunctuation": True,
        "PasswordLength": 40,
    }
    env = sender_resource["Properties"]["Environment"]["Variables"]
    assert env["SENDER_API_KEY_SECRET_ID"] == {"Ref": key_id}
    assert any(
        {"Ref": key_id} in resources
        for resources in statements_granting(reminder, "secretsmanager:GetSecretValue")
    )
    reminder.has_output(
        "SenderUrl", {"Value": {"Fn::GetAtt": [Match.any_value(), "FunctionUrl"]}}
    )
    reminder.has_output("SenderApiKeySecretArn", {"Value": {"Ref": key_id}})


def test_sender_is_fed_by_an_outbox_queue_with_dead_letters():
    _, reminder = synth(local=False)
    sender_id, sender_resource = sender(reminder)

    queues = reminder.find_resources("AWS::SQS::Queue")
    (outbox_id,) = [
        k for k in queues if k.startswith("CourtBotOutbox") and "Dead" not in k
    ]
    (dead_id,) = [k for k in queues if k.startswith("CourtBotOutboxDeadLetters")]
    outbox = queues[outbox_id]["Properties"]
    assert outbox["RedrivePolicy"] == {
        "deadLetterTargetArn": {"Fn::GetAtt": [dead_id, "Arn"]},
        "maxReceiveCount": reminder_module.OUTBOX_DELIVERY_ATTEMPTS,
    }

    reminder.has_resource_properties(
        "AWS::Lambda::EventSourceMapping",
        {
            "EventSourceArn": {"Fn::GetAtt": [outbox_id, "Arn"]},
            "FunctionName": {"Ref": sender_id},
            "BatchSize": reminder_module.OUTBOX_BATCH_SIZE,
            # Without this one bad message would re-text its whole batch.
            "FunctionResponseTypes": ["ReportBatchItemFailures"],
        },
    )
    assert any(
        {"Fn::GetAtt": [outbox_id, "Arn"]} in resources
        for resources in statements_granting(reminder, "sqs:ReceiveMessage")
    )
    reminder.has_output("CourtBotOutboxUrl", {"Value": {"Ref": outbox_id}})
    reminder.has_output("CourtBotOutboxDeadLettersUrl", {"Value": {"Ref": dead_id}})
    assert "VpcConfig" not in sender_resource["Properties"]


def test_sent_reminders_are_remembered_so_a_retry_does_not_text_twice():
    _, reminder = synth(local=False)
    sender_id, sender_resource = sender(reminder)

    ((table_id, table),) = reminder.find_resources("AWS::DynamoDB::Table").items()
    props = table["Properties"]
    assert props["KeySchema"] == [{"AttributeName": "reminder_id", "KeyType": "HASH"}]
    assert props["BillingMode"] == "PAY_PER_REQUEST"
    # Rows must expire on their own; nobody is going to prune this table.
    assert props["TimeToLiveSpecification"] == {
        "AttributeName": "expires_at",
        "Enabled": True,
    }

    env = sender_resource["Properties"]["Environment"]["Variables"]
    assert env["SENT_LOG_TABLE"] == {"Ref": table_id}
    assert any(
        {"Fn::GetAtt": [table_id, "Arn"]} in resources
        for resources in statements_granting(reminder, "dynamodb:PutItem")
    )
    reminder.has_output("SentRemindersTable", {"Value": {"Ref": table_id}})


def test_one_queue_record_per_invocation():
    """Pinned deliberately. The sender is not idempotent, so a batch larger
    than one would let a single crash resend every text already handed to
    TrueDialog earlier in that batch."""
    _, reminder = synth(local=False)

    assert reminder_module.OUTBOX_BATCH_SIZE == 1
    reminder.has_resource_properties(
        "AWS::Lambda::EventSourceMapping", {"BatchSize": 1}
    )


def test_the_queue_hides_a_message_for_at_least_as_long_as_a_send_can_take():
    """SQS rejects a visibility timeout below the function timeout, so this
    guards the sender's timeout against being raised on its own."""
    _, reminder = synth(local=False)
    _, sender_resource = sender(reminder)

    (outbox,) = [
        queue["Properties"]
        for logical_id, queue in reminder.find_resources("AWS::SQS::Queue").items()
        if logical_id.startswith("CourtBotOutbox") and "Dead" not in logical_id
    ]

    assert outbox["VisibilityTimeout"] >= sender_resource["Properties"]["Timeout"]
    assert (
        reminder_module.SENDER_TIMEOUT.to_seconds()
        == sender_resource["Properties"]["Timeout"]
    )


# -------------------------------------------------------------- local mode


def test_local_database_is_postgres_with_plain_credentials_and_no_sg_lockdown():
    database, _ = synth(local=True)
    database.has_resource_properties(
        "AWS::RDS::DBInstance",
        {"Engine": "postgres", "DBName": "courtdb", "MasterUsername": "court"},
    )
    database.resource_count_is("Custom::VpcRestrictDefaultSG", 0)
    database.resource_count_is("AWS::SecretsManager::SecretTargetAttachment", 0)
    assert_endpoints(database)
    (instance,) = database.find_resources("AWS::RDS::DBInstance").values()
    assert "DBInstanceIdentifier" not in instance["Properties"]
    (secret,) = database.find_resources("AWS::SecretsManager::Secret").values()
    rendered = json.dumps(secret["Properties"]["SecretString"])
    for fragment in ('"username":"court"', '"password":"court"', '"dbname":"courtdb"'):
        assert fragment in rendered.replace(" ", "").replace("\\", "")


def test_local_truedialog_secret_is_filled_from_the_environment(monkeypatch):
    monkeypatch.setenv("TRUEDIALOG_API_KEY", "local-key")
    monkeypatch.setenv("TRUEDIALOG_API_SECRET", "local-secret")
    monkeypatch.setenv("TRUEDIALOG_ACCOUNT_ID", "777")
    monkeypatch.delenv("TRUEDIALOG_CHANNEL_ID", raising=False)
    _, reminder = synth(local=True)

    logical_id, secret = secret_named(reminder, "TrueDialogCredentials")
    assert json.loads(secret_string(secret)) == {
        "api_key": "local-key",
        "api_secret": "local-secret",
        "account_id": "777",
        "channel_id": "22",
    }
    _, sender_resource = sender(reminder)
    env = sender_resource["Properties"]["Environment"]["Variables"]
    assert env["TRUEDIALOG_SECRET_ID"] == {"Ref": logical_id}


def test_floci_gets_no_daily_reseed():
    """Nothing schedules a laptop's database at 07:00 UTC, and Floci is not
    where an EventBridge schedule would be proved anyway. Locally the same
    reseed is a person running `. script/db/reset`."""
    _, reminder = synth(local=True)
    reminder.resource_count_is("AWS::Events::Rule", 0)


def test_local_sender_gets_the_same_url_queue_and_a_fixed_key():
    _, reminder = synth(local=True)

    reminder.resource_count_is("AWS::Lambda::Url", 1)
    # The queue is the same in both modes, so the local stack exercises it.
    reminder.resource_count_is("AWS::SQS::Queue", 2)
    reminder.resource_count_is("AWS::Lambda::EventSourceMapping", 1)
    _, key = secret_named(reminder, "SenderApiKey")
    assert secret_string(key) == reminder_module.LOCAL_SENDER_API_KEY == "local-dev-key"
    _, sender_resource = sender(reminder)
    assert "VpcConfig" not in sender_resource["Properties"]


@pytest.mark.parametrize(
    ("machine", "expected"),
    [("arm64", "arm64"), ("aarch64", "arm64"), ("x86_64", "x86_64")],
)
def test_local_lambdas_are_built_for_the_host_architecture(machine, expected):
    _, reminder = synth(local=True, machine=machine)
    for logical_id, resource in functions(reminder).items():
        properties = resource["Properties"]
        assert properties["Architectures"] == [expected], logical_id
        if properties["Handler"] != "message_sender.handler":
            env = properties["Environment"]["Variables"]
            assert env["COURT_DB_ENGINE"] == "postgres"


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

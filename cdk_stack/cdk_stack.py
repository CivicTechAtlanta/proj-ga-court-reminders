import hashlib
import os
import platform
from pathlib import Path

from constructs import Construct
from aws_cdk import (
    CfnOutput,
    CustomResource,
    Duration,
    SecretValue,
    Stack,
    aws_ec2,
    aws_lambda,
    aws_lambda_event_sources,
    aws_secretsmanager,
    aws_sqs,
)
from aws_cdk import aws_lambda_python_alpha as lp

from database_stack import CourtDatabaseStack

# The x-api-key value the text sender accepts on Floci, where nothing is at
# stake. In AWS, CloudFormation generates a random one (see _sender_api_key).
LOCAL_SENDER_API_KEY = "local-dev-key"

# One queue message is one text, so a batch takes as long as TrueDialog does:
# the sender's timeout covers OUTBOX_BATCH_SIZE sends at the wrapper's
# ten-second HTTP timeout, with room left for a cold start. Shorter than the
# other handlers on purpose, because SQS makes a queue message invisible for
# at least the function timeout while it is being processed.
SENDER_TIMEOUT = Duration.minutes(2)
OUTBOX_BATCH_SIZE = 5
# AWS asks for a visibility timeout of six times the function timeout.
OUTBOX_VISIBILITY_TIMEOUT = Duration.minutes(12)
# Receives before a message moves to the dead letter queue.
OUTBOX_DELIVERY_ATTEMPTS = 3


class CourtReminderStack(Stack):
    """The reminder Lambdas, placed next to the court database.

    Every Lambda except the text sender joins the database VPC and client
    security group and gets the COURT_DB_* settings the court_db wrapper
    reads: the engine the database stack chose (SQL Server in AWS, Postgres
    on Floci) and the Secrets Manager secret holding its credentials. The
    sender runs outside the VPC behind a public function URL instead, so it
    can reach TrueDialog and developers can reach it (see _expose_sender).
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        database: CourtDatabaseStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._database = database

        self._function("CourtBotMain", "main.py", timeout=Duration.minutes(15))
        sender = self._function(
            "CourtBotMessageSender",
            "message_sender.py",
            timeout=SENDER_TIMEOUT,
            in_vpc=False,
        )
        self._expose_sender(sender)
        self._outbox(sender)
        self._function(
            "CourtBotMessageResponse",
            "message_response.py",
            timeout=Duration.minutes(15),
        )
        self._function(
            "CourtBotMessageStatus", "message_status.py", timeout=Duration.minutes(15)
        )
        self._seed_database()

    def _expose_sender(self, sender: lp.PythonFunction) -> None:
        """Inbound and outbound traffic for the text sender.

        Outbound: the sender is the one Lambda outside the database VPC, so
        it reaches api.truedialog.com and Secrets Manager over the public
        internet at no cost. The isolated subnets have no route out, and a
        NAT gateway would cost more than the rest of this environment.

        Inbound: a function URL, which is free and needs no API Gateway.
        Developers POST {"to", "message"} to it and GET it for a readiness
        report. The URL itself is public, so the handler refuses requests
        whose x-api-key header does not match the SenderApiKey secret.
        """
        truedialog = self._truedialog_secret()
        truedialog.grant_read(sender)
        # The ARN, not the name, for the same Floci reason as COURT_DB_SECRET_ID.
        sender.add_environment("TRUEDIALOG_SECRET_ID", truedialog.secret_arn)

        api_key = self._sender_api_key()
        api_key.grant_read(sender)
        sender.add_environment("SENDER_API_KEY_SECRET_ID", api_key.secret_arn)

        url = sender.add_function_url(auth_type=aws_lambda.FunctionUrlAuthType.NONE)
        CfnOutput(
            self,
            "SenderUrl",
            value=url.url,
            description="POST {to, message} here with the x-api-key header to send "
            "a text; GET reports readiness",
        )
        CfnOutput(
            self,
            "SenderApiKeySecretArn",
            value=api_key.secret_arn,
            description="Secret holding the x-api-key value that SenderUrl requires",
        )

    def _outbox(self, sender: lp.PythonFunction) -> None:
        """The queue that will feed the text sender, and its dead letters.

        A queue message carries exactly the JSON the function URL accepts,
        so a reminder reaches the sender the same way by either route:

            {"to": "+14045550142", "message": "See you in court Thursday."}

        Nothing produces messages yet. CourtBotMain will once the reminder
        copy has a home; until then, put one on the queue by hand with
        `aws sqs send-message` against the CourtBotOutboxUrl output.

        The sender reports failures per record, so one bad message never
        re-texts the rest of its batch. A record that keeps failing moves to
        the dead letter queue with its payload intact after
        OUTBOX_DELIVERY_ATTEMPTS receives, which is where to look when a
        reminder never arrives.
        """
        dead_letters = aws_sqs.Queue(
            self,
            "CourtBotOutboxDeadLetters",
            encryption=aws_sqs.QueueEncryption.SQS_MANAGED,
            retention_period=Duration.days(14),
        )
        outbox = aws_sqs.Queue(
            self,
            "CourtBotOutbox",
            encryption=aws_sqs.QueueEncryption.SQS_MANAGED,
            visibility_timeout=OUTBOX_VISIBILITY_TIMEOUT,
            retention_period=Duration.days(4),
            dead_letter_queue=aws_sqs.DeadLetterQueue(
                max_receive_count=OUTBOX_DELIVERY_ATTEMPTS, queue=dead_letters
            ),
        )
        sender.add_event_source(
            aws_lambda_event_sources.SqsEventSource(
                outbox,
                batch_size=OUTBOX_BATCH_SIZE,
                report_batch_item_failures=True,
            )
        )
        CfnOutput(
            self,
            "CourtBotOutboxUrl",
            value=outbox.queue_url,
            description="Queue feeding the text sender; a message is the same "
            '{"to", "message"} JSON the sender URL accepts',
        )
        CfnOutput(
            self,
            "CourtBotOutboxDeadLettersUrl",
            value=dead_letters.queue_url,
            description="Where a queue message lands after "
            f"{OUTBOX_DELIVERY_ATTEMPTS} failed attempts",
        )

    def _truedialog_secret(self) -> aws_secretsmanager.Secret:
        """The TrueDialog API credentials, as the truedialog wrapper reads them.

        The wrapper expects JSON with api_key, api_secret, account_id, and
        channel_id. TrueDialog issues those credentials, so in AWS the secret
        is created with empty placeholders and a person fills it in once
        after the first deploy (see the README). CloudFormation rewrites the
        stored value only when these placeholders change, so leave them
        alone or the hand-entered values are overwritten on the next deploy.

        On Floci the same secret is filled from the TRUEDIALOG_* environment
        at synth time (make local-deploy loads .env), so the sender exercises
        the Secrets Manager path it uses in AWS. Hotswap deploys ignore secret
        changes; after editing .env, run make local-reset.
        """
        values = {"api_key": "", "api_secret": "", "account_id": "", "channel_id": "22"}
        if self._database.local:
            values = {
                key: os.environ.get("TRUEDIALOG_" + key.upper(), default)
                for key, default in values.items()
            }
        secret = aws_secretsmanager.Secret(
            self,
            "TrueDialogCredentials",
            description="TrueDialog API credentials for the court reminder text sender",
            secret_object_value={
                key: SecretValue.unsafe_plain_text(value)
                for key, value in values.items()
            },
        )
        CfnOutput(
            self,
            "TrueDialogSecretArn",
            value=secret.secret_arn,
            description="Secret holding the TrueDialog credentials; fill it in with "
            "aws secretsmanager put-secret-value",
        )
        return secret

    def _sender_api_key(self) -> aws_secretsmanager.Secret:
        """The key developers must send as x-api-key to the sender's URL.

        Generated by CloudFormation in AWS (read it back with
        aws secretsmanager get-secret-value); a fixed value on Floci.
        """
        if self._database.local:
            value = {
                "secret_string_value": SecretValue.unsafe_plain_text(
                    LOCAL_SENDER_API_KEY
                )
            }
        else:
            value = {
                "generate_secret_string": aws_secretsmanager.SecretStringGenerator(
                    exclude_punctuation=True, password_length=40
                )
            }
        return aws_secretsmanager.Secret(
            self,
            "SenderApiKey",
            description="Key developers send as x-api-key to the text sender's URL",
            **value,
        )

    def _seed_database(self) -> None:
        """Load the schema and fixtures into the database during deploy.

        Follows the AWS "Use AWS CDK to initialize Amazon RDS instances"
        pattern: a Lambda inside the database VPC applies the seed scripts,
        and CloudFormation invokes it as a custom resource. The Lambda is the
        service token itself and answers CloudFormation directly, avoiding
        the CDK provider framework's extra Node function (which cannot reach
        Floci's HTTP endpoint). A hash of the scripts in the resource
        properties makes CloudFormation re-run the seed whenever they
        change; pass `-c reseed=<any new value>` to re-run it without
        changing them, for example to re-anchor the fixture dates.
        """
        loader = self._function(
            "CourtBotDatabaseLoader",
            "database_loader.py",
            timeout=Duration.minutes(5),
        )
        seed = CustomResource(
            self,
            "CourtDatabaseSeed",
            service_token=loader.function_arn,
            resource_type="Custom::CourtDatabaseSeed",
            properties={
                "SeedVersion": _seed_version(),
                "Reseed": self.node.try_get_context("reseed") or "",
            },
        )
        seed.node.add_dependency(self._database.database)
        # CloudFormation invokes the loader the moment this resource is
        # created, and the Lambda runtime creates its own log group on first
        # run. With useCdkManagedLogGroup the group is also a stack resource,
        # so without this dependency the two race and the deploy fails with
        # "The specified log group already exists".
        seed.node.add_dependency(loader.log_group)
        CfnOutput(
            self,
            "CourtDatabaseSeedHearings",
            value=seed.get_att_string("UpcomingHearings"),
            description="Reminder-query row count right after seeding; expect 11",
        )

    def _function(
        self, construct_id: str, index: str, in_vpc: bool = True, **overrides
    ) -> lp.PythonFunction:
        """A Lambda from lambda/<index>; in the database VPC unless told not."""
        function = lp.PythonFunction(
            self,
            construct_id,
            entry="lambda",
            runtime=aws_lambda.Runtime.PYTHON_3_12,
            index=index,
            handler="handler",
            **self._bundling(),
            **(self._database_placement() if in_vpc else {}),
            **overrides,
        )
        if in_vpc:
            self._database.credentials_secret.grant_read(function)
        return function

    def _database_placement(self) -> dict:
        """Constructor arguments that connect a Lambda to the court database."""
        database = self._database
        return {
            "vpc": database.vpc,
            "vpc_subnets": aws_ec2.SubnetSelection(
                subnet_type=aws_ec2.SubnetType.PRIVATE_ISOLATED
            ),
            "security_groups": [database.client_security_group],
            "environment": {
                "COURT_DB_ENGINE": database.engine,
                # SQL Server secrets carry no dbname; the seed creates this
                "COURT_DB_NAME": "courtdb",
                # The ARN, not the name: CDK derives names by parsing AWS's
                # random-suffix ARN format, which Floci's ARNs do not follow.
                "COURT_DB_SECRET_ID": database.credentials_secret.secret_arn,
            },
        }

    def _bundling(self) -> dict:
        """Constructor arguments about how the Lambda bundle is built."""
        if self._database.local:
            # Floci runs Lambdas on the host CPU architecture whatever the
            # function declares, so bundle native drivers to match it. (It
            # injects AWS_ENDPOINT_URL into the containers itself.)
            return {"architecture": _host_architecture()}
        return {}


def _host_architecture() -> aws_lambda.Architecture:
    if platform.machine().lower() in {"arm64", "aarch64"}:
        return aws_lambda.Architecture.ARM_64
    return aws_lambda.Architecture.X86_64


_SEED_ROOT = Path(__file__).resolve().parent.parent / "lambda" / "court_db" / "seed"


def _seed_version() -> str:
    """Short digest of every engine's seed scripts, so edits trigger a re-seed."""
    digest = hashlib.sha256()
    for script in sorted(_SEED_ROOT.glob("*/*.sql")):
        digest.update(str(script.relative_to(_SEED_ROOT)).encode())
        digest.update(script.read_bytes())
    return digest.hexdigest()[:12]

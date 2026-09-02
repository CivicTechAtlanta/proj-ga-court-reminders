import hashlib
import platform
from pathlib import Path

from constructs import Construct
from aws_cdk import (
    CfnOutput,
    CustomResource,
    Duration,
    Stack,
    aws_ec2,
    aws_lambda,
)
from aws_cdk import aws_lambda_python_alpha as lp

from database_stack import CourtDatabaseStack


class CourtReminderStack(Stack):
    """The reminder Lambdas, placed next to the court database.

    Every Lambda joins the database VPC and client security group and gets
    the COURT_DB_* settings the court_db wrapper reads: the engine the
    database stack chose (SQL Server in AWS, Postgres on Floci) and the
    Secrets Manager secret holding its credentials.
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

        self._function("CourtBotMain", "main.py")
        self._function("CourtBotMessageSender", "message_sender.py")
        self._function("CourtBotMessageResponse", "message_response.py")
        self._function("CourtBotMessageStatus", "message_status.py")
        self._seed_database()

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
        CfnOutput(
            self,
            "CourtDatabaseSeedHearings",
            value=seed.get_att_string("UpcomingHearings"),
            description="Reminder-query row count right after seeding; expect 11",
        )

    def _function(
        self, construct_id: str, index: str, **overrides
    ) -> lp.PythonFunction:
        function = lp.PythonFunction(
            self,
            construct_id,
            entry="lambda",
            runtime=aws_lambda.Runtime.PYTHON_3_12,
            index=index,
            handler="handler",
            **self._database_placement(),
            **overrides,
        )
        self._database.credentials_secret.grant_read(function)
        return function

    def _database_placement(self) -> dict:
        """Constructor arguments that connect a Lambda to the court database."""
        database = self._database
        placement = {
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
        if database.local:
            # Floci runs Lambdas on the host CPU architecture whatever the
            # function declares, so bundle native drivers to match it. (It
            # injects AWS_ENDPOINT_URL into the containers itself.)
            placement["architecture"] = _host_architecture()
        return placement


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

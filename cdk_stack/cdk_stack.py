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
    custom_resources,
)
from aws_cdk import aws_lambda_python_alpha as lp

from database_stack import CourtDatabaseStack


class CourtReminderStack(Stack):
    """The reminder Lambdas.

    Pass `database` to place every Lambda inside the court database VPC and
    point the court_db wrapper at RDS SQL Server. Leave it None for the local
    Floci stack, where the wrapper defaults to the Docker Postgres fixtures.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        database: CourtDatabaseStack | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._database = database

        self._function("CourtBotMain", "main.py")
        self._function("CourtBotMessageSender", "message_sender.py")
        self._function("CourtBotMessageResponse", "message_response.py")
        self._function("CourtBotMessageStatus", "message_status.py")

        if database is not None:
            self._seed_database()

    def _seed_database(self) -> None:
        """Load the schema and fixtures into the dev database during deploy.

        Follows the AWS "Use AWS CDK to initialize Amazon RDS instances"
        pattern: a Lambda inside the database VPC applies the T-SQL under
        lambda/court_db/seed/sqlserver/, and CloudFormation invokes it as a
        custom resource. A hash of the scripts in the resource properties
        makes CloudFormation re-run the seed whenever they change; pass
        `-c reseed=<any new value>` to re-run it without changing them, for
        example to re-anchor the fixture dates.
        """
        loader = self._function(
            "CourtBotDatabaseLoader",
            "database_loader.py",
            timeout=Duration.minutes(5),
        )
        provider = custom_resources.Provider(
            self, "CourtDatabaseSeedProvider", on_event_handler=loader
        )
        seed = CustomResource(
            self,
            "CourtDatabaseSeed",
            service_token=provider.service_token,
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
        if self._database is not None:
            self._database.database.secret.grant_read(function)
        return function

    def _database_placement(self) -> dict:
        """Constructor arguments that connect a Lambda to the court database.

        Without a database stack (the Floci deploy), the court_db wrapper
        targets the docker-compose Postgres fixtures. Floci runs Lambdas on
        the compose network, where that database is the `db` service.
        """
        if self._database is None:
            return {
                # Floci runs Lambdas on the host CPU architecture whatever the
                # function declares, so bundle native drivers to match it.
                "architecture": _host_architecture(),
                "environment": {
                    "COURT_DB_ENGINE": "postgres",
                    "COURT_DB_HOST": "db",
                    "COURT_DB_PORT": "5432",
                },
            }
        return {
            "vpc": self._database.vpc,
            "vpc_subnets": aws_ec2.SubnetSelection(
                subnet_type=aws_ec2.SubnetType.PRIVATE_ISOLATED
            ),
            "security_groups": [self._database.client_security_group],
            "environment": {
                "COURT_DB_ENGINE": "sqlserver",
                # SQL Server secrets carry no dbname; the loader creates this
                "COURT_DB_NAME": "courtdb",
                "COURT_DB_SECRET_NAME": self._database.database.secret.secret_name,
            },
        }


def _host_architecture() -> aws_lambda.Architecture:
    if platform.machine().lower() in {"arm64", "aarch64"}:
        return aws_lambda.Architecture.ARM_64
    return aws_lambda.Architecture.X86_64


_SEED_DIR = (
    Path(__file__).resolve().parent.parent
    / "lambda"
    / "court_db"
    / "seed"
    / "sqlserver"
)


def _seed_version() -> str:
    """Short digest of the seed scripts, so edits to them trigger a re-seed."""
    digest = hashlib.sha256()
    for script in sorted(_SEED_DIR.glob("*.sql")):
        digest.update(script.name.encode())
        digest.update(script.read_bytes())
    return digest.hexdigest()[:12]

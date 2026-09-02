import platform

from constructs import Construct
from aws_cdk import Duration, Stack, aws_ec2, aws_lambda
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
            # Seeds the dev database from inside its VPC; see make aws-db-load
            self._function(
                "CourtBotDatabaseLoader",
                "database_loader.py",
                timeout=Duration.minutes(5),
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

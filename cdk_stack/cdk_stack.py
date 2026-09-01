from constructs import Construct
from aws_cdk import Stack, aws_ec2, aws_lambda
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

    def _function(self, construct_id: str, index: str) -> lp.PythonFunction:
        function = lp.PythonFunction(
            self,
            construct_id,
            entry="lambda",
            runtime=aws_lambda.Runtime.PYTHON_3_12,
            index=index,
            handler="handler",
            **self._database_placement(),
        )
        if self._database is not None:
            self._database.database.secret.grant_read(function)
        return function

    def _database_placement(self) -> dict:
        """Constructor arguments that connect a Lambda to the database."""
        if self._database is None:
            return {}
        return {
            "vpc": self._database.vpc,
            "vpc_subnets": aws_ec2.SubnetSelection(
                subnet_type=aws_ec2.SubnetType.PRIVATE_ISOLATED
            ),
            "security_groups": [self._database.client_security_group],
            "environment": {
                "COURT_DB_ENGINE": "sqlserver",
                "COURT_DB_SECRET_NAME": self._database.database.secret.secret_name,
            },
        }

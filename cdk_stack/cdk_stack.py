from constructs import Construct
from aws_cdk import (
    Stack,
    aws_lambda,
)


class CourtReminderStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        func = aws_lambda.Function(
            self,
            "HelloHandler",
            code=aws_lambda.Code.from_asset("lambda"),
            runtime=aws_lambda.Runtime.PYTHON_3_12,
            handler="hello.handler",
        )

from constructs import Construct
from aws_cdk import Stack, aws_lambda
from aws_cdk import aws_lambda_python_alpha as lp


class CourtReminderStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        main_func = lp.PythonFunction(
            self,
            "CourtBotMain",
            entry="lambda",
            runtime=aws_lambda.Runtime.PYTHON_3_12,
            index="main.py",
            handler="handler",
        )

        message_sender_func = lp.PythonFunction(
            self,
            "CourtBotMessageSender",
            entry="lambda",
            runtime=aws_lambda.Runtime.PYTHON_3_12,
            index="message_sender.py",
            handler="handler",
        )

        message_response_func = lp.PythonFunction(
            self,
            "CourtBotMessageResponse",
            entry="lambda",
            runtime=aws_lambda.Runtime.PYTHON_3_12,
            index="message_response.py",
            handler="handler",
        )

        message_status_func = lp.PythonFunction(
            self,
            "CourtBotMessageStatus",
            entry="lambda",
            runtime=aws_lambda.Runtime.PYTHON_3_12,
            index="message_status.py",
            handler="handler",
        )
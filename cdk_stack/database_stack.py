from constructs import Construct
from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_ec2,
    aws_rds,
    CfnOutput,
)


class CourtDatabaseStack(Stack):
    """Placeholder RDS SQL Server matching the Odyssey-style court case DB.

    Sized for development: Express edition (no license cost), smallest
    supported instance, and destroyable so the stack can be torn down freely.
    Harden these settings before any production use.

    Exposes `vpc`, `database`, and `client_security_group` so other stacks
    can place Lambdas next to the database and reach it on its port.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Isolated subnets only: no NAT gateways to pay for, and the
        # database never needs a route to the internet.
        self.vpc = aws_ec2.Vpc(
            self,
            "CourtDatabaseVpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                aws_ec2.SubnetConfiguration(
                    name="database",
                    subnet_type=aws_ec2.SubnetType.PRIVATE_ISOLATED,
                )
            ],
        )

        # Isolated subnets have no route to AWS APIs, so Lambdas that read the
        # credentials secret need this endpoint to reach Secrets Manager.
        self.vpc.add_interface_endpoint(
            "SecretsManagerEndpoint",
            service=aws_ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
        )

        # Anything that should talk to the database joins this group. Owning
        # it here keeps the security-group reference one-directional between
        # stacks (a Lambda stack referencing this stack, never the reverse).
        self.client_security_group = aws_ec2.SecurityGroup(
            self,
            "CourtDatabaseClient",
            vpc=self.vpc,
            description="Members may connect to the court case database",
            allow_all_outbound=True,
        )

        self.database = aws_rds.DatabaseInstance(
            self,
            "CourtCaseDatabase",
            engine=aws_rds.DatabaseInstanceEngine.sql_server_ex(
                version=aws_rds.SqlServerEngineVersion.VER_16_00_4236_2_V1
            ),
            vpc=self.vpc,
            vpc_subnets=aws_ec2.SubnetSelection(
                subnet_type=aws_ec2.SubnetType.PRIVATE_ISOLATED
            ),
            instance_type=aws_ec2.InstanceType.of(
                aws_ec2.InstanceClass.T3, aws_ec2.InstanceSize.SMALL
            ),
            # Password generated into Secrets Manager; nothing stored in code
            credentials=aws_rds.Credentials.from_generated_secret("courtadmin"),
            allocated_storage=20,
            storage_encrypted=True,
            publicly_accessible=False,
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.database.connections.allow_default_port_from(
            self.client_security_group, "Court database clients"
        )

        CfnOutput(
            self,
            "CourtDatabaseEndpoint",
            value=self.database.db_instance_endpoint_address,
            description="Hostname of the court case SQL Server instance",
        )

        CfnOutput(
            self,
            "CourtDatabaseSecretName",
            value=self.database.secret.secret_name,
            description="Secrets Manager secret holding the database credentials",
        )

from constructs import Construct
from aws_cdk import (
    Stack,
    RemovalPolicy,
    SecretValue,
    aws_ec2,
    aws_rds,
    aws_secretsmanager,
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

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        local: bool = False,
        **kwargs,
    ) -> None:
        """Set `local` for the Floci emulator: Postgres instead of SQL Server
        (Floci's RDS cannot start SQL Server) and no default-security-group
        lockdown, whose custom resource needs an HTTPS EC2 endpoint Floci
        does not serve."""
        super().__init__(scope, construct_id, **kwargs)
        self.local = local
        self.engine = "postgres" if local else "sqlserver"

        # Isolated subnets only: no NAT gateways to pay for, and the
        # database never needs a route to the internet.
        self.vpc = aws_ec2.Vpc(
            self,
            "CourtDatabaseVpc",
            max_azs=2,
            nat_gateways=0,
            restrict_default_security_group=not local,
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

        if local:
            # Floci does not resolve {{resolve:secretsmanager:...}} dynamic
            # references (the database container starts with that literal
            # string as its password), so the local instance takes a plain
            # password and the secret below is written out by hand.
            credentials = aws_rds.Credentials.from_password(
                _USERNAME, SecretValue.unsafe_plain_text(_LOCAL_PASSWORD)
            )
        else:
            # Generated into Secrets Manager; nothing stored in code. RDS
            # attaches it after the instance exists, adding host, port, and
            # dbname to the username/password.
            self.credentials_secret = aws_rds.DatabaseSecret(
                self, "CourtCaseDatabaseCredentials", username=_USERNAME
            )
            credentials = aws_rds.Credentials.from_secret(self.credentials_secret)

        self.database = aws_rds.DatabaseInstance(
            self,
            "CourtCaseDatabase",
            **_ENGINES[self.engine](),
            vpc=self.vpc,
            vpc_subnets=aws_ec2.SubnetSelection(
                subnet_type=aws_ec2.SubnetType.PRIVATE_ISOLATED
            ),
            instance_type=aws_ec2.InstanceType.of(
                aws_ec2.InstanceClass.T3, aws_ec2.InstanceSize.SMALL
            ),
            credentials=credentials,
            allocated_storage=20,
            storage_encrypted=True,
            publicly_accessible=False,
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.database.connections.allow_default_port_from(
            self.client_security_group, "Court database clients"
        )

        if local:
            # Same JSON shape RDS writes into an attached secret, so the
            # court_db wrapper reads it identically in both environments.
            self.credentials_secret = aws_secretsmanager.Secret(
                self,
                "CourtCaseDatabaseCredentials",
                secret_object_value={
                    "engine": SecretValue.unsafe_plain_text(self.engine),
                    "host": SecretValue.unsafe_plain_text(
                        self.database.db_instance_endpoint_address
                    ),
                    "port": SecretValue.unsafe_plain_text(
                        self.database.db_instance_endpoint_port
                    ),
                    "dbname": SecretValue.unsafe_plain_text("courtdb"),
                    "username": SecretValue.unsafe_plain_text(_USERNAME),
                    "password": SecretValue.unsafe_plain_text(_LOCAL_PASSWORD),
                },
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
            value=self.credentials_secret.secret_name,
            description="Secrets Manager secret holding the database credentials",
        )


_USERNAME = "courtadmin"
# Local emulator only; matches the docker-compose fixture database defaults.
_LOCAL_PASSWORD = "court"


def _sqlserver() -> dict:
    """The production-shaped engine. SQL Server secrets carry no dbname; the
    seed Lambda creates the database itself."""
    return {
        "engine": aws_rds.DatabaseInstanceEngine.sql_server_ex(
            version=aws_rds.SqlServerEngineVersion.VER_16_00_4236_2_V1
        ),
    }


def _postgres() -> dict:
    """The engine for local Floci deployments, whose RDS emulation runs real
    Postgres, MySQL, and MariaDB containers but cannot start SQL Server."""
    return {
        "engine": aws_rds.DatabaseInstanceEngine.postgres(
            version=aws_rds.PostgresEngineVersion.VER_16
        ),
        "database_name": "courtdb",
    }


_ENGINES = {"sqlserver": _sqlserver, "postgres": _postgres}

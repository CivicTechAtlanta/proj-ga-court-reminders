"""Resolve TrueDialog settings for the current environment.

On a developer machine the TRUEDIALOG_* variables (see .template.env)
supply the API key, secret, account, and channel. When deployed,
TRUEDIALOG_SECRET_ID names (by ARN or name) a Secrets Manager secret whose
JSON keys api_key, api_secret, account_id, and channel_id override the env
values. Credentials have no safe defaults, so a missing value raises
TrueDialogConfigError instead of letting a send fail later.
"""

import json
import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.truedialog.com/api/v2.1"
# TrueDialog's own Power Platform connector documents channel 22 as "the
# default associated phone number". Override with TRUEDIALOG_CHANNEL_ID once
# the account has a dedicated long code or short code.
DEFAULT_CHANNEL_ID = "22"
DEFAULT_TIMEOUT_SECONDS = "10"


class TrueDialogConfigError(ValueError):
    """Raised when required TrueDialog settings are missing."""


@dataclass(frozen=True)
class TrueDialogConfig:
    api_key: str
    api_secret: str
    account_id: str
    channel_id: str = DEFAULT_CHANNEL_ID
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = float(DEFAULT_TIMEOUT_SECONDS)

    @classmethod
    def from_env(cls, environ=None, secret_loader=None):
        environ = os.environ if environ is None else environ
        secret_loader = secret_loader or _load_secrets_manager_json

        secret = {}
        secret_name = environ.get("TRUEDIALOG_SECRET_ID")
        if secret_name:
            secret = secret_loader(secret_name)

        def setting(key, default=None):
            value = secret.get(key) or environ.get("TRUEDIALOG_" + key.upper())
            return default if value in (None, "") else str(value)

        credentials = {
            key: setting(key) for key in ("api_key", "api_secret", "account_id")
        }
        missing = [key for key, value in credentials.items() if value is None]
        if missing:
            names = ", ".join("TRUEDIALOG_" + key.upper() for key in missing)
            raise TrueDialogConfigError(
                f"Missing TrueDialog settings: {names}. Set them in .env (see "
                ".template.env) or point TRUEDIALOG_SECRET_ID at a secret holding them."
            )

        return cls(
            **credentials,
            channel_id=setting("channel_id", DEFAULT_CHANNEL_ID),
            base_url=setting("base_url", DEFAULT_BASE_URL),
            timeout_seconds=float(setting("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
        )


def _load_secrets_manager_json(secret_name):
    # Imported lazily: boto3 ships in the Lambda runtime but is not a
    # project dependency, and local development never reaches this path.
    import boto3

    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])

"""Composition root: build the client for the current environment."""

from .client import TrueDialogClient
from .config import TrueDialogConfig


def truedialog_client(config: TrueDialogConfig | None = None) -> TrueDialogClient:
    """Build a client from `config`, or with no argument from the
    TRUEDIALOG_* environment variables and the Secrets Manager secret named
    by TRUEDIALOG_SECRET_ID."""
    return TrueDialogClient(config or TrueDialogConfig.from_env())

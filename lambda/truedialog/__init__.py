"""TrueDialog SMS access layer for the court reminder Lambdas.

Handlers should import only from this package root:

    from truedialog import truedialog_client

    result = truedialog_client().send_message("(404) 555-0142", "See you in court.")
    print(result.action_id, result.status)
"""

from .client import (
    TrueDialogApiError,
    TrueDialogClient,
    TrueDialogConnectionError,
    TrueDialogError,
)
from .config import TrueDialogConfig, TrueDialogConfigError
from .factory import truedialog_client
from .models import SmsResult
from .phone import normalize_us_phone

__all__ = [
    "SmsResult",
    "TrueDialogApiError",
    "TrueDialogClient",
    "TrueDialogConfig",
    "TrueDialogConfigError",
    "TrueDialogConnectionError",
    "TrueDialogError",
    "normalize_us_phone",
    "truedialog_client",
]

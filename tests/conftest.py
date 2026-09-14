import socket
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The Lambda bundle's root is the lambda/ directory, so make its packages
# importable the same way the deployed functions import them. The CDK app and
# the helper scripts likewise import their siblings by bare name.
for directory in ("lambda", "cdk_stack", "script_helpers"):
    sys.path.insert(0, str(REPO_ROOT / directory))

_LOOPBACK = {"127.0.0.1", "::1", "localhost", ""}
_real_connect = socket.socket.connect


@pytest.fixture(autouse=True)
def no_outbound_network(monkeypatch):
    """Fail any test that opens a connection off this machine.

    A test run must never reach an external service: it would be slow and
    flaky at best, and at worst it spends TrueDialog credit and texts a real
    person. Anything needing the live API belongs in
    scripts/truedialog_check.py, which somebody runs on purpose.

    Loopback stays open, because the court database runs in Floci and several
    tests exercise the HTTP client against a throwaway server on 127.0.0.1.
    """

    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else None
        if host is not None and host not in _LOOPBACK:
            raise AssertionError(
                f"a test tried to connect to {host}. Tests must not reach "
                "outside this machine; use a fake transport, or put it in "
                "scripts/truedialog_check.py if it genuinely needs the live API."
            )
        return _real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)

"""HTTP client for the TrueDialog v2.1 REST API.

Covers only what the reminder workflow needs: pushing an SMS action to one
or more phone numbers, plus two read-only calls that confirm the
credentials and account. Authentication is HTTP Basic with the API key as
the username and the secret as the password. The HTTP transport is a plain
callable, so tests substitute a fake and never open a socket.

Endpoint paths and field names follow the connector definition TrueDialog
publishes for Microsoft Power Platform (microsoft/PowerPlatformConnectors,
certified-connectors/TrueDialog SMS), which mirrors the reference at
https://api.truedialog.com/docs/.
"""

import base64
import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from .config import TrueDialogConfig
from .models import SmsResult
from .phone import mask, normalize_us_phone, redact

logger = logging.getLogger(__name__)


class TrueDialogError(Exception):
    """Base class for every failure raised by this package."""


class TrueDialogConnectionError(TrueDialogError):
    """TrueDialog could not be reached (DNS, TCP, TLS, or timeout)."""


class TrueDialogApiError(TrueDialogError):
    """TrueDialog answered with a non-2xx status."""

    def __init__(self, status: int, body, method: str, path: str):
        self.status = status
        # Redacted on the way in, so neither this object nor anything that
        # renders it can leak a phone number the provider echoed back.
        self.body = redact(body)
        self.method = method
        self.path = path
        super().__init__(
            f"TrueDialog {method} {path} failed with HTTP {status}: "
            f"{_summarize(self.body)}"
        )


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None
    timeout: float


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)


Transport = Callable[[HttpRequest], HttpResponse]


def urllib_transport(request: HttpRequest) -> HttpResponse:
    """Default transport: the standard library, so the Lambda bundle needs
    no extra dependency. Non-2xx answers come back as responses rather than
    exceptions; only failing to get an answer at all raises."""
    prepared = urllib.request.Request(
        request.url, data=request.body, headers=request.headers, method=request.method
    )
    try:
        with urllib.request.urlopen(prepared, timeout=request.timeout) as response:
            return HttpResponse(
                response.status, response.read(), dict(response.headers)
            )
    except urllib.error.HTTPError as error:
        return HttpResponse(error.code, error.read(), dict(error.headers))
    except OSError as error:  # URLError, refused connections, timeouts
        raise TrueDialogConnectionError(
            f"Could not reach TrueDialog at {request.url}: {error}"
        ) from error


class TrueDialogClient:
    def __init__(self, config: TrueDialogConfig, transport: Transport | None = None):
        self._config = config
        self._transport = transport or urllib_transport
        credentials = f"{config.api_key}:{config.api_secret}".encode()
        self._headers = {
            "Authorization": "Basic " + base64.b64encode(credentials).decode("ascii"),
            "Accept": "application/json",
        }

    def send_message(
        self,
        to: str | Iterable[str],
        message: str,
        *,
        channel_id: str | int | None = None,
        execute: bool = True,
        force_opt_in: bool = False,
        ignore_invalid_targets: bool = False,
        schedules: Iterable[str] | None = None,
        campaign_id: int = 0,
    ) -> SmsResult:
        """Push one SMS to every number in `to`; return what TrueDialog accepted.

        Numbers may be formatted any way people type them; they are
        normalized to E.164 first. Fails before any HTTP call when the
        message is blank or a number is not a US phone number.

        With `execute` True (the default) TrueDialog sends at once;
        `schedules` asks it to send later instead. `force_opt_in` re-sends
        to contacts who texted STOP, so leave it False unless consent has
        been tracked elsewhere. `ignore_invalid_targets` makes TrueDialog
        skip bad numbers instead of rejecting the whole action.
        """
        if not message or not message.strip():
            raise ValueError("message must not be empty")
        recipients = [to] if isinstance(to, str) else list(to)
        if not recipients:
            raise ValueError("at least one recipient is required")
        targets = [normalize_us_phone(number) for number in recipients]
        channel = str(self._config.channel_id if channel_id is None else channel_id)

        body = {
            "Channels": [channel],
            "Targets": targets,
            "Message": message,
            "CampaignId": campaign_id,
            "Execute": execute,
            "ForceOptIn": force_opt_in,
            "IgnoreInvalidTargets": ignore_invalid_targets,
        }
        if schedules:
            body["Schedules"] = list(schedules)

        payload = self._request(
            "POST", f"/account/{self._config.account_id}/action-pushcampaign", body
        )
        result = SmsResult.from_response(payload)
        # Neither the message text nor a full phone number belongs in logs.
        logger.info(
            "TrueDialog accepted action %s for %s over channel %s (status: %s)",
            result.action_id,
            ", ".join(mask(target) for target in targets),
            channel,
            result.status,
        )
        return result

    def user_info(self) -> dict:
        """The user the credentials belong to, as TrueDialog describes it."""
        return self._request("GET", "/userinfo")

    def account_info(self) -> dict:
        """The configured account, as TrueDialog describes it."""
        return self._request("GET", f"/account/{self._config.account_id}")

    def ping(self) -> bool:
        """True when TrueDialog accepts these credentials for this account.

        Asks for the configured account rather than /userinfo. An API key
        can be denied /userinfo while working perfectly for sending, so
        checking it would report a healthy account as broken. This also
        checks one thing more than credentials: 404 means the key is valid
        but the configured account id is not one it can see.

        False covers both of those; anything else, such as a 500 or an
        unreachable host, raises rather than being reported as a verdict.
        """
        try:
            self.account_info()
        except TrueDialogApiError as error:
            if error.status in (401, 403, 404):
                return False
            raise
        return True

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        headers = dict(self._headers)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = HttpRequest(
            method,
            self._config.base_url.rstrip("/") + path,
            headers,
            data,
            self._config.timeout_seconds,
        )

        response = self._transport(request)
        decoded = _decode(response.body)
        if not 200 <= response.status < 300:
            logger.error(
                "TrueDialog %s %s returned HTTP %s: %s",
                method,
                path,
                response.status,
                _summarize(redact(decoded)),
            )
            raise TrueDialogApiError(response.status, decoded, method, path)
        if decoded == "":
            return {}
        if not isinstance(decoded, dict):
            raise TrueDialogError(
                f"Unexpected response body from TrueDialog {method} {path}: "
                f"{_summarize(redact(decoded))}"
            )
        return decoded


def _decode(body: bytes):
    """JSON when the body parses, otherwise the text itself."""
    text = body.decode("utf-8", errors="replace").strip()
    try:
        return json.loads(text)
    except ValueError:
        return text


def _summarize(body) -> str:
    text = json.dumps(body) if isinstance(body, (dict, list)) else str(body)
    return text if len(text) <= 200 else text[:200] + "..."

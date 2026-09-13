"""Plain objects returned by the truedialog package.

Handlers work with these; TrueDialog's JSON never leaks past the package
boundary except through `raw`, which is kept for debugging.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SmsResult:
    """What TrueDialog reports after accepting a push-campaign action.

    `action_id` identifies the action in TrueDialog; delivery notices and
    the portal refer to it. `status` is TrueDialog's label for the action
    at the time of the response and `status_id` its numeric code.
    """

    action_id: int | None
    account_id: int | None
    status_id: int | None
    status: str | None
    targets: tuple[str, ...]
    created: str | None
    raw: dict = field(repr=False, compare=False)

    @classmethod
    def from_response(cls, payload: dict) -> "SmsResult":
        return cls(
            action_id=payload.get("id"),
            account_id=payload.get("accountId"),
            status_id=payload.get("statusId"),
            status=payload.get("status"),
            targets=tuple(payload.get("targets") or ()),
            created=payload.get("created"),
            raw=payload,
        )

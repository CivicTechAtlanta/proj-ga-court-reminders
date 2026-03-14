from datetime import datetime, timedelta, timezone

_EXIT_HINT = "\n\nText EXIT / FINISH / END to end the demo"

def now_plus(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def format_dt(s: str) -> str:
    return parse_dt(s).strftime("%I:%M %p %Z")

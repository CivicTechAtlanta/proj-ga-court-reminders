#!/usr/bin/env python3
"""
Demo flow harness — simulates realistic SMS conversations and prints them as chat logs.

Calls court_reminder logic directly (no HTTP server needed).

Usage:
    uv run python tests/harness.py
"""

from court_reminder.state import InMemoryStateStore
from court_reminder.twilio_handler import advance_scenario, handle_inbound_sms

PHONE = "+14045550000"

_last_system_msg: str = ""

# ANSI colors
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_CYAN   = "\033[96m"   # user texts
_GREEN  = "\033[92m"   # system replies
_YELLOW = "\033[93m"   # timed advance marker
_WHITE  = "\033[97m"


def _store():
    return InMemoryStateStore()


def _bubble(label: str, color: str, text: str):
    indent = "    "
    header = f"{_BOLD}{color}{label}{_RESET}"
    lines = text.splitlines()
    print(f"{indent}{header}")
    for line in lines:
        print(f"{indent}  {color}{line}{_RESET}")
    print()


def sms(store, body: str):
    global _last_system_msg
    _bubble("📱 You", _CYAN, body)
    for msg in handle_inbound_sms(PHONE, body, store):
        _bubble("💬 System", _GREEN, msg)
        _last_system_msg = msg


def advance(store):
    global _last_system_msg
    print(f"    {_DIM}{_YELLOW}⏱  [timed advance]{_RESET}\n")
    msgs = advance_scenario(PHONE, store)
    for msg in msgs:
        _bubble("💬 System", _GREEN, msg)
        _last_system_msg = msg


def flow(title: str):
    global _last_system_msg
    if _last_system_msg and "session has ended" not in _last_system_msg:
        print(f"    {_DIM}...{_RESET}\n")
    _last_system_msg = ""
    print(f"\n{_BOLD}{_WHITE}{'━' * 54}{_RESET}")
    print(f"{_BOLD}{_WHITE}  {title}{_RESET}")
    print(f"{_BOLD}{_WHITE}{'━' * 54}{_RESET}\n")
    return _store()


# ---------------------------------------------------------------------------
# Flow 1: Happy path — full 7-3-1 countdown
# ---------------------------------------------------------------------------
s = flow("Flow 1: Happy path — full countdown")
sms(s, "hello")
sms(s, "1")
advance(s)  # countdown_7min
advance(s)  # countdown_3min
advance(s)  # countdown_1min
advance(s)  # missed
advance(s)  # rescheduled countdown_7min
sms(s, "EXIT")

# ---------------------------------------------------------------------------
# Flow 2: User takes a few tries to pick a valid scenario
# ---------------------------------------------------------------------------
s = flow("Flow 2: User fumbles with scenario selection")
sms(s, "hey there")
sms(s, "what is this")
sms(s, "2")        # unavailable
sms(s, "banana")   # still not valid
sms(s, "1")
advance(s)

# ---------------------------------------------------------------------------
# Flow 3: User texts mid-countdown, then exits
# ---------------------------------------------------------------------------
s = flow("Flow 3: User texts mid-countdown, then exits")
sms(s, "1")
advance(s)  # countdown_7min
sms(s, "am I going to jail?")
sms(s, "hello??")
advance(s)  # countdown_3min
sms(s, "finish")

# ---------------------------------------------------------------------------
# Flow 4: Exit immediately from home, then re-enter
# ---------------------------------------------------------------------------
s = flow("Flow 4: Exit from home, then re-enter")
sms(s, "END")
sms(s, "1")
advance(s)

# ---------------------------------------------------------------------------
# Flow 5: Exit during countdown, re-enter fresh
# ---------------------------------------------------------------------------
s = flow("Flow 5: Exit mid-countdown, re-enter and restart")
sms(s, "1")
advance(s)  # countdown_7min
advance(s)  # countdown_3min
sms(s, "EXIT")
sms(s, "hello")   # back to welcome
sms(s, "1")       # fresh start, new court_datetime
advance(s)

if _last_system_msg and "session has ended" not in _last_system_msg:
    print(f"    {_DIM}...{_RESET}\n")

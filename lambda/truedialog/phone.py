"""Phone number normalization for TrueDialog targets.

TrueDialog expects US numbers in E.164 form with no formatting, for example
+15125453809, while the court database holds them as they were typed
("(404) 555-0101"). Normalize once, at the boundary.
"""

import re

_NON_DIGITS = re.compile(r"\D")


def normalize_us_phone(number: str) -> str:
    """Return `number` as +1NNNNNNNNNN, or raise ValueError.

    Accepts any punctuation and an optional leading 1 or +1. Rejects
    anything that is not ten digits with a valid area code and exchange
    (neither may start with 0 or 1), which also rules out non-US numbers.
    """
    digits = _NON_DIGITS.sub("", number or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] in "01" or digits[3] in "01":
        raise ValueError(f"Not a valid US phone number: {number!r}")
    return "+1" + digits

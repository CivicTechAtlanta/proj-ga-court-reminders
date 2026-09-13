"""Phone number normalization for TrueDialog targets.

TrueDialog expects US numbers in E.164 form with no formatting, for example
+15125453809, while the court database holds them as they were typed
("(404) 555-0101"). Normalize once, at the boundary.
"""

import re

_NON_DIGITS = re.compile(r"\D")
# Ten or eleven digits however they are punctuated: a US number, and not a
# TrueDialog action or campaign id, which are shorter.
_PHONE_SHAPED = re.compile(r"\+?\(?\d[\d\s().\-]{6,}\d")


def mask(number) -> str:
    """A phone number with only its last four digits left, for logs and for
    error text. Logs are kept for two years; numbers tie a person to a court
    case, so nothing here should carry a whole one."""
    text = str(number)
    return "***" + text[-4:] if len(text) > 4 else "***"


def redact(value):
    """The same masking applied through any decoded JSON, so a provider's
    error body cannot put a number in our logs or in a response. Anything
    that is not phone-shaped is left alone, which keeps action ids readable."""
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _PHONE_SHAPED.sub(_mask_match, value)
    return value


def _mask_match(match):
    digits = _NON_DIGITS.sub("", match.group())
    if len(digits) not in (10, 11):
        return match.group()
    return mask(digits)


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
        # Masked: this message reaches CloudWatch, which keeps it for years.
        raise ValueError(f"Not a valid US phone number: {mask(number)}")
    return "+1" + digits

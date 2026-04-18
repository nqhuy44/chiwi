"""
PII Masking middleware.

Strips account numbers, phone numbers, and sensitive identifiers
from request bodies before forwarding to any LLM agent.

Note: Patterns are designed to avoid masking VND amounts (which are
typically formatted with commas/dots or lack the prefix patterns of
real account numbers).
"""

import re


# Vietnamese bank account numbers: typically prefixed by "TK" / "STK" / "Acc"
# or appear after keywords like "tai khoan", "so the"
ACCOUNT_PATTERN = re.compile(
    r"(?:TK|STK|Acc|tai khoan|so the)[:\s]*(\d[\d\s\-]{8,18}\d)",
    re.IGNORECASE,
)

# Phone numbers: 0xx-xxx-xxxx format (10-11 digits starting with 0)
PHONE_PATTERN = re.compile(r"\b0\d{9,10}\b")

# Card numbers: 4 groups of 4 digits
CARD_PATTERN = re.compile(r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}\b")


def mask_pii(text: str) -> str:
    """Mask PII in text before sending to LLM.

    Preserves transaction amounts and dates while masking
    account numbers, phone numbers, and card numbers.
    """
    masked = ACCOUNT_PATTERN.sub(r"***ACCOUNT***", text)
    masked = CARD_PATTERN.sub("***CARD***", masked)
    masked = PHONE_PATTERN.sub("***PHONE***", masked)
    return masked

"""
PII Masking middleware.

Strips account numbers, phone numbers, and sensitive identifiers
from request bodies before forwarding to any LLM agent.
"""

import re


# Patterns to mask
ACCOUNT_NUMBER_PATTERN = re.compile(r"\b\d{10,16}\b")
PHONE_PATTERN = re.compile(r"\b0\d{9,10}\b")


def mask_pii(text: str) -> str:
    """Mask PII in text before sending to LLM."""
    masked = ACCOUNT_NUMBER_PATTERN.sub("***MASKED***", text)
    masked = PHONE_PATTERN.sub("***PHONE***", masked)
    return masked

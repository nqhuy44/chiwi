"""
Ingestion Agent (The Collector)

Parses raw bank notification text into structured transaction data
using Gemini 2.5 Flash. Handles diverse Vietnamese bank formats.
"""

import logging

from src.core.schemas import ParsedTransaction

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Vietnamese bank notification parser. Given a raw notification text,
extract structured financial data. Output JSON only.
Fields: amount, currency, direction, merchant_name, transaction_time, bank_name.
If the text is NOT a financial transaction, return {"is_transaction": false}.
"""


class IngestionAgent:
    """Parses bank notifications into structured transactions."""

    async def parse(self, raw_text: str) -> ParsedTransaction:
        """Parse a raw bank notification into structured data."""
        # TODO: Call Gemini Flash for extraction
        logger.info("Parsing notification: %s", raw_text[:80])
        return ParsedTransaction(
            is_transaction=False,
            raw_text=raw_text,
        )

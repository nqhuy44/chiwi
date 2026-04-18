"""
Ingestion Agent (The Collector)

Parses raw bank notification text into structured transaction data
using Gemini 2.5 Flash. Handles diverse Vietnamese bank formats.
"""

import logging
from datetime import datetime

from src.api.middleware.pii_mask import mask_pii
from src.core.config import settings
from src.core.schemas import ParsedTransaction
from src.services.gemini import GeminiService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Vietnamese bank notification parser. Given a raw notification text,
extract structured financial data. Output **valid JSON only**, no explanation.

Required JSON fields:
- "is_transaction": boolean — false if the text is NOT a financial transaction
- "amount": number — transaction amount (0 if not a transaction)
- "currency": string — default "VND"
- "direction": "inflow" | "outflow"
- "merchant_name": string | null — name of merchant/recipient
- "transaction_time": string | null — ISO 8601 datetime if detectable, else null
- "bank_name": string | null — name of the bank
- "confidence": "high" | "medium" | "low"

Vietnamese bank format hints:
- "GD: -500,000VND" means outflow of 500,000 VND
- "GD: +1,000,000VND" means inflow
- "SD/Balance:" line shows remaining balance (ignore for amount)
- "đ" is equivalent to "VND"
- Common banks: Vietcombank, Techcombank, MB Bank, VPBank, ACB, TPBank, MoMo (e-wallet)
"""


class IngestionAgent:
    """Parses bank notifications into structured transactions."""

    def __init__(self, gemini: GeminiService) -> None:
        self._gemini = gemini

    async def parse(self, raw_text: str) -> ParsedTransaction:
        """Parse a raw bank notification into structured data.

        PII is masked before sending to the LLM.
        """
        masked_text = mask_pii(raw_text) if settings.pii_mask_enabled else raw_text
        logger.info("Parsing notification (%d chars)", len(raw_text))

        result = await self._gemini.call_flash(SYSTEM_PROMPT, masked_text)

        if not result:
            logger.warning("Gemini returned empty result, treating as non-transaction")
            return ParsedTransaction(is_transaction=False, raw_text=raw_text)

        # Parse transaction_time if present
        txn_time = None
        if result.get("transaction_time"):
            try:
                txn_time = datetime.fromisoformat(result["transaction_time"])
            except (ValueError, TypeError):
                logger.warning(
                    "Could not parse transaction_time: %s",
                    result.get("transaction_time"),
                )

        return ParsedTransaction(
            is_transaction=result.get("is_transaction", False),
            amount=result.get("amount"),
            currency=result.get("currency", "VND"),
            direction=result.get("direction"),
            merchant_name=result.get("merchant_name"),
            transaction_time=txn_time,
            bank_name=result.get("bank_name"),
            raw_text=raw_text,
            confidence=result.get("confidence", "low"),
        )

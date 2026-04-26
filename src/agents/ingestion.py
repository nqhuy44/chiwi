"""
Ingestion Agent (The Collector)

Receives raw bank notification text forwarded from the Android app and
parses it into a structured ParsedTransaction. All AI parsing lives here
so the logic can be improved server-side without a mobile release.

Uses Gemini 2.5 Flash (cheap, deterministic extraction).
"""

import logging

from src.agents.prompts import load_prompt
from src.api.middleware.pii_mask import mask_pii
from src.core.config import settings
from src.core.schemas import ParsedTransaction
from src.services.gemini import GeminiService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = load_prompt("ingestion")


class IngestionAgent:
    """Parses raw bank notification text into a structured transaction."""

    def __init__(self, gemini: GeminiService) -> None:
        self._gemini = gemini

    async def parse(self, raw_text: str, bank_hint: str | None = None) -> ParsedTransaction:
        """Extract structured financial data from a raw notification string."""
        logger.info("Parsing notification text (len=%d)", len(raw_text))

        masked = mask_pii(raw_text) if settings.pii_mask_enabled else raw_text

        user_msg = f"Notification text: {masked}"
        if bank_hint:
            user_msg += f"\nBank hint: {bank_hint}"

        result = await self._gemini.call_flash(SYSTEM_PROMPT, user_msg)

        if not result:
            logger.warning("Gemini returned empty result for ingestion")
            return ParsedTransaction(is_transaction=False, raw_text=raw_text)

        return ParsedTransaction(raw_text=raw_text, **result)

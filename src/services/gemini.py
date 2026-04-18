"""Gemini LLM service wrapper."""

import logging

from src.core.config import settings

logger = logging.getLogger(__name__)


class GeminiService:
    """Wrapper for Google Gemini API calls."""

    def __init__(self):
        self.api_key = settings.gemini_api_key

    async def call_flash(
        self, system_prompt: str, user_message: str
    ) -> dict:
        """Call Gemini 2.5 Flash for fast parsing tasks."""
        # TODO: Implement with langchain-google-genai
        logger.info("Gemini Flash call (not yet implemented)")
        return {}

    async def call_pro(self, system_prompt: str, user_message: str) -> dict:
        """Call Gemini 2.5 Pro for reasoning tasks."""
        # TODO: Implement with langchain-google-genai
        logger.info("Gemini Pro call (not yet implemented)")
        return {}

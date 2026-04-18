"""Gemini LLM service wrapper using the official google-genai SDK."""

import asyncio
import json
import logging
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from src.core.config import settings

logger = logging.getLogger(__name__)

# Retry config for rate limit (429) errors
MAX_RETRIES = 5
BASE_DELAY_SECONDS = 2.0


class GeminiService:
    """Wrapper for Google Gemini API calls via google-genai SDK."""

    def __init__(self) -> None:
        self._client: genai.Client | None = None

    def initialize(self) -> None:
        """Create the Gemini client. Call after settings are loaded."""
        if not settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY not set — LLM calls will fail")
            return

        self._client = genai.Client(api_key=settings.gemini_api_key)
        logger.info(
            "Gemini client initialized (Flash: %s, Pro: %s)",
            settings.gemini_model_flash,
            settings.gemini_model_pro,
        )

    async def call_flash(
        self, system_prompt: str, user_message: str
    ) -> dict[str, Any]:
        """Call Gemini Flash for fast parsing tasks (JSON mode)."""
        return await self._invoke(
            settings.gemini_model_flash, system_prompt, user_message, temperature=0.1
        )

    async def call_pro(
        self, system_prompt: str, user_message: str
    ) -> dict[str, Any]:
        """Call Gemini Pro for reasoning tasks (JSON mode)."""
        return await self._invoke(
            settings.gemini_model_pro, system_prompt, user_message, temperature=0.3
        )

    async def _invoke(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float,
    ) -> dict[str, Any]:
        """Internal: invoke a model with forced JSON output.

        Retries with exponential backoff on 429 RESOURCE_EXHAUSTED errors.
        """
        if self._client is None:
            logger.error("Gemini client not initialized")
            return {}

        raw = ""
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                        response_mime_type="application/json",
                    ),
                )
                raw = (response.text or "").strip()
                return json.loads(raw) if raw else {}

            except ClientError as exc:
                if exc.code == 429:
                    delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "Gemini %s rate-limited (429), retry %d/%d in %.1fs",
                        model, attempt, MAX_RETRIES, delay,
                    )
                    last_error = exc
                    await asyncio.sleep(delay)
                    continue
                logger.exception("Gemini %s client error (%s)", model, exc.code)
                return {}

            except json.JSONDecodeError:
                logger.error("Gemini %s returned non-JSON: %s", model, raw[:200])
                return {}

            except Exception:
                logger.exception("Gemini %s call failed", model)
                return {}

        # Exhausted all retries
        logger.error(
            "Gemini %s: exhausted %d retries on rate limit", model, MAX_RETRIES
        )
        return {}

from __future__ import annotations
"""
Conversational Agent (The Interface)

Handles natural language interaction via Telegram. Resolves Vietnamese
temporal references, parses informal amounts, and detects user intent.
Uses Gemini 2.5 Pro.
"""

import logging
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, ValidationError

from src.agents.prompts import load_prompt
from src.api.middleware.pii_mask import mask_pii
from src.core.config import settings
from src.core.schemas import UserProfile
from src.services.gemini import GeminiService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = load_prompt("conversational")


class IntentResult(BaseModel):
    intent: Literal[
        "log_transaction",
        "delete_transaction",
        "ask_balance",
        "ask_spending_vs_avg",
        "ask_category",
        "request_report",
        "request_analysis",
        "set_budget",
        "ask_budget",
        "update_budget",
        "temp_increase_budget",
        "silence_budget",
        "disable_budget",
        "set_goal",
        "set_subscription",
        "list_subscriptions",
        "query_subscription",
        "mark_subscription_paid",
        "cancel_subscription",
        "update_subscription",
        "general_chat",
    ]
    payload: dict = Field(default_factory=dict)
    response_text: str | None = None


class ConversationalAgent:
    """Handles natural language chat and voice input."""

    def __init__(self, gemini: GeminiService) -> None:
        self._gemini = gemini

    async def process_message(
        self,
        message: str,
        chat_id: str,
        session_context: dict | None = None,
        user_timezone: str | None = None,
        profile: UserProfile | None = None,
    ) -> IntentResult:
        """Process a text message and determine intent."""
        logger.info("Processing message from chat_id=%s", chat_id)

        prompt = self._build_prompt(user_timezone, profile)

        masked = mask_pii(message) if settings.pii_mask_enabled else message
        user_msg = f"<user_message>\n{masked}\n</user_message>"
        if session_context:
            user_msg += f"\n<session_context>\n{session_context}\n</session_context>"

        result = await self._gemini.call_pro(prompt, user_msg)

        if not result:
            logger.warning("Gemini returned empty JSON for chat parsing")
            return IntentResult(
                intent="general_chat",
                response_text="Xin lỗi, mình chưa rõ ý bạn. Bạn có thể nói cụ thể hơn không?",
            )

        try:
            return IntentResult(**result)
        except ValidationError:
            logger.warning("Invalid intent schema from Gemini: %s", result)
            return IntentResult(
                intent="general_chat",
                response_text="Xin lỗi, mình không hiểu ý bạn. Bạn có thể nói lại không?",
            )

    async def process_voice(
        self,
        audio_bytes: bytes,
        audio_mime_type: str,
        chat_id: str,
        user_timezone: str | None = None,
        profile: UserProfile | None = None,
    ) -> IntentResult:
        """Process a voice message via Gemini native audio STT + intent extraction."""
        logger.info("Processing voice from chat_id=%s", chat_id)

        if not audio_bytes:
            return IntentResult(
                intent="general_chat",
                response_text="Xin lỗi, mình chưa nghe rõ. Bạn thử nhắn chữ nhé?",
            )

        prompt = self._build_prompt(user_timezone, profile)

        result = await self._gemini.call_flash_with_audio(prompt, audio_bytes, audio_mime_type)

        if not result:
            logger.warning("Gemini returned empty JSON for voice parsing")
            return IntentResult(
                intent="general_chat",
                response_text="Xin lỗi, mình chưa nghe rõ. Bạn thử nhắn chữ nhé?",
            )

        try:
            return IntentResult(**result)
        except ValidationError:
            logger.warning("Invalid intent schema from voice: %s", result)
            return IntentResult(
                intent="general_chat",
                response_text="Xin lỗi, mình không hiểu ý bạn. Bạn thử nhắn chữ nhé?",
            )

    def _build_prompt(self, user_timezone: str | None, profile: UserProfile | None) -> str:
        """Construct the system prompt with timezone, personality, and tone."""
        from src.core.profiles import build_personalized_prompt
        from zoneinfo import ZoneInfo
        
        tz = ZoneInfo(user_timezone or settings.business_timezone)
        now_iso = datetime.now(tz).isoformat()
        
        return build_personalized_prompt(
            template=SYSTEM_PROMPT_TEMPLATE,
            profile=profile or UserProfile(),
            current_timestamp=now_iso
        )

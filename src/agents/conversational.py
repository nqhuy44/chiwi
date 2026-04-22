"""
Conversational Agent (The Interface)

Handles natural language interaction via Telegram. Resolves Vietnamese
temporal references, parses informal amounts, and detects user intent.
Uses Gemini 2.5 Pro.
"""

import logging
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.agents.prompts import load_prompt
from src.services.gemini import GeminiService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = load_prompt("conversational")


class IntentResult(BaseModel):
    intent: Literal[
        "log_transaction",
        "ask_balance",
        "ask_category",
        "request_report",
        "request_analysis",
        "set_budget",
        "set_goal",
        "general_chat",
    ]
    payload: dict = Field(default_factory=dict)
    response_text: str | None = None


class ConversationalAgent:
    """Handles natural language chat and voice input."""

    def __init__(self, gemini: GeminiService) -> None:
        self._gemini = gemini

    async def process_message(
        self, message: str, chat_id: str, session_context: dict | None = None
    ) -> IntentResult:
        """Process a text message and determine intent."""
        logger.info("Processing message from chat_id=%s", chat_id)
        
        now_iso = datetime.now(UTC).isoformat()
        prompt = SYSTEM_PROMPT_TEMPLATE.replace("{{CURRENT_TIMESTAMP}}", now_iso)
        
        user_msg = f"User message: {message}"
        if session_context:
            user_msg += f"\nSession Context: {session_context}"
            
        result = await self._gemini.call_pro(prompt, user_msg)
        
        if not result:
            logger.warning("Gemini returned empty JSON for chat parsing")
            return IntentResult(
                intent="general_chat",
                response_text="Xin lỗi, mình chưa rõ ý bạn. Bạn có thể nói cụ thể hơn không?"
            )
            
        return IntentResult(**result)

    async def process_voice(
        self, voice_file_url: str, chat_id: str
    ) -> IntentResult:
        """Process a voice message via speech-to-text then intent parsing."""
        # TODO: Call Gemini Flash for STT, then Pro for intent
        logger.info("Processing voice from chat_id=%s", chat_id)
        return IntentResult(
            intent="general_chat",
            response_text="Xin lỗi, mình chưa xử lý được tin nhắn thoại.",
        )

"""
Conversational Agent (The Interface)

Handles natural language interaction via Telegram. Resolves Vietnamese
temporal references, parses informal amounts, and detects user intent.
Uses Gemini 2.5 Pro.
"""

import logging
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are ChiWi, a friendly Vietnamese personal finance assistant.
Parse spending messages into structured data. Resolve relative dates
using current_date. Handle Vietnamese slang for money.
If the user is asking a question (not logging a transaction), respond conversationally.
"""


class IntentResult(BaseModel):
    intent: Literal[
        "log_transaction",
        "ask_balance",
        "ask_category",
        "request_report",
        "set_budget",
        "set_goal",
        "general_chat",
    ]
    payload: dict = Field(default_factory=dict)
    response_text: str | None = None


class ConversationalAgent:
    """Handles natural language chat and voice input."""

    async def process_message(
        self, message: str, chat_id: str, session_context: dict | None = None
    ) -> IntentResult:
        """Process a text message and determine intent."""
        # TODO: Call Gemini Pro for intent classification + parsing
        logger.info("Processing message from chat_id=%s", chat_id)
        return IntentResult(
            intent="general_chat",
            response_text="Xin chào! Mình là ChiWi.",
        )

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

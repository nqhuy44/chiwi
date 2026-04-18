"""Telegram Bot service wrapper."""

import logging

from src.core.config import settings

logger = logging.getLogger(__name__)


class TelegramService:
    """Handles sending messages via Telegram Bot API."""

    def __init__(self):
        self.bot_token = settings.telegram_bot_token

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: dict | None = None,
    ) -> dict:
        """Send a message to a Telegram chat."""
        # TODO: Implement with python-telegram-bot or httpx
        logger.info("Sending message to chat_id=%s", chat_id)
        return {}

    async def send_silent_message(
        self,
        chat_id: str,
        text: str,
        reply_markup: dict | None = None,
    ) -> dict:
        """Send a silent notification message."""
        # TODO: Implement with disable_notification=True
        return await self.send_message(
            chat_id, text, reply_markup=reply_markup
        )

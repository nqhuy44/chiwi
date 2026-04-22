"""Telegram Bot service wrapper."""

import logging
from telegram import Bot
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

from src.core.config import settings

logger = logging.getLogger(__name__)


class TelegramService:
    """Handles sending messages via Telegram Bot API."""

    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        # Use HTTPXRequest for better async performance in v22+
        request = HTTPXRequest(connection_pool_size=8)
        self.bot = Bot(
            token=self.bot_token,
            request=request,
            get_updates_request=request
        ) if self.bot_token else None

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: dict | None = None,
    ) -> dict:
        """Send a message to a Telegram chat."""
        if not self.bot:
            logger.warning("Telegram bot token is not set")
            return {}
            
        try:
            message = await self.bot.send_message(
                chat_id=chat_id, 
                text=text, 
                parse_mode=ParseMode.HTML, 
            )
            logger.info("Message sent to chat_id=%s", chat_id)
            return {"message_id": message.message_id}
        except Exception as e:
            logger.error("Failed to send Telegram message: %s", e)
            return {}

    async def send_silent_message(
        self,
        chat_id: str | int,
        text: str,
        reply_markup: dict | None = None,
    ) -> dict:
        """Send a silent notification message."""
        if not self.bot:
            logger.warning("Telegram bot token is not set")
            return {}

        try:
            message = await self.bot.send_message(
                chat_id=chat_id, 
                text=text, 
                disable_notification=True
            )
            return {"message_id": message.message_id}
        except Exception as e:
            logger.error("Failed to send silent Telegram message: %s", e)
            return {}

"""Telegram Bot service wrapper."""

import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

from src.core.config import settings

logger = logging.getLogger(__name__)

_Keyboard = list[list[dict]]  # [[{"text": str, "callback_data": str}]]


def _build_markup(keyboard: _Keyboard) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"]) for btn in row]
        for row in keyboard
    ])


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

    async def send_message_with_keyboard(
        self,
        chat_id: str | int,
        text: str,
        keyboard: _Keyboard,
    ) -> dict:
        """Send a message with an inline keyboard."""
        if not self.bot:
            logger.warning("Telegram bot token is not set")
            return {}

        try:
            message = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=_build_markup(keyboard),
            )
            logger.info("Message with keyboard sent to chat_id=%s", chat_id)
            return {"message_id": message.message_id}
        except Exception as e:
            logger.error("Failed to send Telegram message with keyboard: %s", e)
            return {}

    async def edit_message_reply_markup(
        self,
        chat_id: str | int,
        message_id: int,
        keyboard: _Keyboard | None = None,
    ) -> None:
        """Replace the inline keyboard on an existing message."""
        if not self.bot:
            return

        try:
            markup = _build_markup(keyboard) if keyboard else None
            await self.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
            )
        except Exception as e:
            logger.warning("Failed to edit message reply markup: %s", e)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str = "",
    ) -> None:
        """Dismiss the loading indicator on an inline button tap."""
        if not self.bot:
            return

        try:
            await self.bot.answer_callback_query(
                callback_query_id=callback_query_id,
                text=text[:200] if text else "",
            )
        except Exception as e:
            logger.warning("Failed to answer callback query: %s", e)

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
                parse_mode=ParseMode.HTML,
                disable_notification=True,
            )
            return {"message_id": message.message_id}
        except Exception as e:
            logger.error("Failed to send silent Telegram message: %s", e)
            return {}

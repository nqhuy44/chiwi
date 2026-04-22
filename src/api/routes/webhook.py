"""Webhook routes for bank notifications and Telegram updates."""

import logging

from fastapi import APIRouter, Header, HTTPException

from src.core.config import settings
from src.core.dependencies import container
from src.core.schemas import NotificationPayload, WebhookResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook")


@router.post("/notification", response_model=WebhookResponse)
async def receive_notification(
    payload: NotificationPayload,
    x_user_id: str = Header(...),
) -> WebhookResponse:
    """Receive bank notification from MacroDroid/Tasker/iOS Shortcuts.

    Pipeline: PII Mask -> Orchestrator -> Ingestion -> Tagging -> Store.
    """
    if x_user_id not in settings.allowed_user_ids:
        raise HTTPException(status_code=401, detail="Unauthorized user")

    orchestrator = container.orchestrator

    event = {
        "source": payload.source,
        "notification_text": payload.notification_text,
        "user_id": x_user_id,
        "timestamp": payload.timestamp,
    }

    event_type = await orchestrator.classify_event(event)
    result = await orchestrator.route(event_type, {**event})

    return WebhookResponse(
        status=result.get("status", "error"),
        transaction_id=result.get("transaction_id"),
        parsed=result.get("parsed"),
    )


@router.post("/telegram")
async def telegram_webhook(update: dict) -> dict:
    """Receive Telegram Bot API webhook updates.

    Guards:
    1. Stale message filter — drops messages older than configured max age.
    2. Deduplication — skips already-processed update_ids (Redis SET with TTL).
    3. Rate limiting — caps messages per user per minute.
    """
    import time as _time

    update_id = update.get("update_id")
    logger.info("Telegram update received: %s", update_id)

    message = update.get("message", {})
    if not message:
        return {"ok": True}

    # --- Guard 1: Stale message filter ---
    message_date = message.get("date", 0)
    age_seconds = int(_time.time()) - message_date
    max_age = settings.telegram_message_max_age_seconds
    if age_seconds > max_age:
        logger.warning(
            "Dropping stale message update_id=%s, age=%ds (max=%ds)",
            update_id, age_seconds, max_age,
        )
        return {"ok": True}

    chat_id = str(message.get("chat", {}).get("id", ""))
    text = message.get("text", "")

    if not chat_id or not text:
        return {"ok": True}

    if chat_id not in settings.allowed_user_ids:
        logger.warning("Unauthorized telegram user: %s", chat_id)
        return {"ok": True}

    redis_client = container.redis

    # --- Guard 2: Deduplication via Redis ---
    if update_id and redis_client.is_connected:
        dedup_key = f"chiwi:telegram:update:{update_id}"
        already_seen = await redis_client._redis.set(
            dedup_key, "1", nx=True, ex=300  # 5 min TTL
        )
        if not already_seen:
            logger.warning("Duplicate update_id=%s, skipping", update_id)
            return {"ok": True}

    # --- Guard 3: Rate limiting ---
    if redis_client.is_connected:
        count = await redis_client.increment_rate_limit(chat_id, ttl=60)
        if count > settings.telegram_rate_limit_per_minute:
            logger.warning(
                "Rate limit exceeded for chat_id=%s (%d/min)",
                chat_id, count,
            )
            return {"ok": True}

    orchestrator = container.orchestrator
    telegram_service = container.telegram

    payload = {
        "source": "telegram",
        "message": text,
        "chat_id": chat_id,
        "user_id": chat_id,
    }

    event_type = await orchestrator.classify_event(payload)
    result = await orchestrator.route(event_type, payload)

    response_text = result.get("response_text")
    if response_text:
        await telegram_service.send_message(chat_id, response_text)

    return {"ok": True}

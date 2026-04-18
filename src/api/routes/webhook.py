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
    """Receive Telegram Bot API webhook updates."""
    # TODO: Route to Orchestrator (chat/voice/callback) — Phase 2
    logger.info("Telegram update received: %s", update.get("update_id"))
    return {"ok": True}

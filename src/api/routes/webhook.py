from fastapi import APIRouter, Header, HTTPException

from src.core.config import settings
from src.core.schemas import NotificationPayload, WebhookResponse

router = APIRouter(prefix="/api/webhook")


@router.post("/notification", response_model=WebhookResponse)
async def receive_notification(
    payload: NotificationPayload,
    x_user_id: str = Header(...),
) -> WebhookResponse:
    """Receive bank notification from MacroDroid/Tasker/iOS Shortcuts."""
    if x_user_id not in settings.allowed_user_ids:
        raise HTTPException(status_code=401, detail="Unauthorized user")

    # TODO: PII mask -> Orchestrator -> Ingestion -> Tagging -> Store
    return WebhookResponse(status="received")


@router.post("/telegram")
async def telegram_webhook(update: dict) -> dict:
    """Receive Telegram Bot API webhook updates."""
    # TODO: Route to Orchestrator (chat/voice/callback)
    return {"ok": True}

"""Webhook routes for bank notifications and Telegram updates."""

import logging

from fastapi import APIRouter, Header, HTTPException

from src.core.config import settings
from src.core.dependencies import container
from src.core.schemas import NotificationPayload, NotificationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook")

# Maps /nudge sub-command arg → nudge_type
_NUDGE_TYPES = {
    "spending": "spending_alert",
    "budget": "budget_warning",
    "goal": "goal_progress",
    "streak": "saving_streak",
    "sub": "subscription_reminder",
    "impulse": "impulse_detection",
}
_DEFAULT_NUDGE_TYPE = "spending_alert"

_HELP_TEXT = (
    "📋 <b>Các lệnh ChiWi hỗ trợ:</b>\n\n"
    "/nudge — Gửi nudge chi tiêu mặc định (spending_alert)\n"
    "/nudge spending — Cảnh báo chi tiêu bất thường\n"
    "/nudge budget — Cảnh báo ngân sách\n"
    "/nudge goal — Tiến độ mục tiêu tiết kiệm\n"
    "/nudge streak — Chuỗi ngày chi tốt\n"
    "/nudge sub — Nhắc phí định kỳ\n"
    "/nudge impulse — Cảnh báo mua sắm bốc đồng\n"
    "/help — Hiển thị danh sách lệnh này\n\n"
    "Hoặc nhắn bất kỳ để nói chuyện với Mai 💬"
)

_START_TEXT = (
    "Chào bạn! Mình là <b>ChiWi (Mai)</b> 👋\n"
    "Mình giúp bạn theo dõi chi tiêu và gửi nhắc nhở thông minh.\n\n"
    "Gõ /help để xem các lệnh, hoặc cứ nhắn tự nhiên nhé!"
)


async def _spending_summary(user_id: str) -> dict:
    """Return a lightweight spending summary for the current week.

    Used as `trigger_data` for manual /nudge commands so the LLM has
    real numbers even when Phase 3.2 trigger detection isn't wired yet.
    """
    from collections import defaultdict

    from src.core.utils import get_date_range

    start, end = get_date_range("this_week")
    if not start:
        return {}

    txns = await container.transaction_repo.find_by_user(
        user_id=user_id, start_date=start, end_date=end, limit=200
    )

    total_out = 0.0
    by_cat: dict[str, float] = defaultdict(float)
    for t in txns:
        if t.get("direction") == "outflow":
            amt = t.get("amount", 0)
            total_out += amt
            by_cat[t.get("category_id") or "Khác"] += amt

    top = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:3]
    return {
        "period": "this_week",
        "total_outflow": round(total_out),
        "transaction_count": len(txns),
        "top_categories": [{"cat": c, "total": round(v)} for c, v in top],
    }


async def _handle_command(
    command: str, args: list[str], chat_id: str, from_id: str
) -> None:
    """Dispatch a bot command. Sends reply directly via TelegramService."""
    telegram = container.telegram

    if command == "/start":
        await telegram.send_message(chat_id, _START_TEXT)
        return

    if command == "/help":
        await telegram.send_message(chat_id, _HELP_TEXT)
        return

    if command == "/nudge":
        nudge_type = (
            _NUDGE_TYPES.get(args[0], _DEFAULT_NUDGE_TYPE)
            if args
            else _DEFAULT_NUDGE_TYPE
        )
        trigger_data = await _spending_summary(from_id)
        trigger_data["source"] = "telegram"
        payload = {
            "user_id": from_id,
            "chat_id": chat_id,
            "nudge_type": nudge_type,
            "trigger_data": trigger_data,
        }
        orchestrator = container.orchestrator
        result = await orchestrator.route("scheduled", payload)
        status = result.get("status")
        if status == "blocked":
            reason = result.get("blocked_reason", "unknown")
            reason_map = {
                "quiet_hours": "Hiện đang trong giờ yên tĩnh (22:00–07:00). Mai sẽ nhắn sau nhé!",
                "daily_limit": "Hôm nay Mai đã gửi đủ nudge rồi. Hẹn gặp ngày mai! 😊",
                "duplicate_type_24h": "Loại nhắc nhở này Mai vừa gửi trong 24h qua rồi nha.",
                "user_disabled_nudges": "Bạn đã tắt nudge trong cài đặt profile.",
                "model_skipped": "Không có gì đáng nhắc lúc này. Tốt lắm! 🎉",
                "telegram_send_failed": "Gửi tin nhắn thất bại, thử lại sau nhé.",
            }
            await telegram.send_message(
                chat_id, reason_map.get(reason, f"Nudge bị chặn: {reason}")
            )
        return

    # Unknown command — silently ignore (don't confuse with chat)
    logger.info("Unknown command %s from chat_id=%s", command, chat_id)


@router.post("/notification", response_model=NotificationResponse)
async def receive_notification(
    payload: NotificationPayload,
    x_user_id: str = Header(...),
) -> NotificationResponse:
    """Receive a raw bank notification forwarded from the Android app.

    The Android app captures the notification text verbatim and posts it here.
    Backend handles all AI parsing (Ingestion Agent) and classification
    (Tagging Agent) so no mobile release is needed when parsing logic changes.

    Auth: X-User-Id header must be in the configured allow-list.
    """
    if x_user_id not in settings.allowed_user_ids:
        raise HTTPException(status_code=401, detail="Unauthorized user")

    orchestrator = container.orchestrator
    profile = container.orchestrator._get_user_chat_id(x_user_id)

    event = {
        "source": "android",
        "raw_text": payload.raw_text,
        "bank_hint": payload.bank_hint,
        "user_id": x_user_id,
        "chat_id": profile,
        "timestamp": payload.timestamp,
    }

    result = await orchestrator.route("notification", event)
    return NotificationResponse(
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
            update_id,
            age_seconds,
            max_age,
        )
        return {"ok": True}

    chat_id = str(message.get("chat", {}).get("id", ""))
    from_id = str(message.get("from", {}).get("id", "")) or chat_id
    text = message.get("text", "")

    if not chat_id or not text:
        return {"ok": True}

    if (
        chat_id not in settings.allowed_user_ids
        and from_id not in settings.allowed_user_ids
    ):
        logger.warning(
            "Unauthorized telegram user: chat_id=%s from_id=%s", chat_id, from_id
        )
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
                chat_id,
                count,
            )
            return {"ok": True}

    # --- Command routing ---
    if text.startswith("/"):
        parts = text.split()
        command = parts[0].split("@")[0].lower()  # strip @botname suffix
        args = parts[1:]
        await _handle_command(command, args, chat_id, from_id)
        return {"ok": True}

    # --- Conversational path ---
    orchestrator = container.orchestrator
    telegram_service = container.telegram

    payload = {
        "source": "telegram",
        "message": text,
        "chat_id": chat_id,
        "user_id": from_id,
    }

    event_type = await orchestrator.classify_event(payload)
    result = await orchestrator.route(event_type, payload)

    response_text = result.get("response_text")
    if response_text:
        await telegram_service.send_message(chat_id, response_text)

    return {"ok": True}

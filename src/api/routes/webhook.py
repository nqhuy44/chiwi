"""Webhook routes for bank notifications and Telegram updates."""

import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

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
    "📋 <b>ChiWi (Mai) hỗ trợ:</b>\n\n"
    "💬 <b>Nhắn tự nhiên (text hoặc voice):</b>\n"
    "• Ghi chi: <i>\"Ăn phở 60k hôm qua\"</i>\n"
    "• Ghi thu: <i>\"Nhận lương 10 triệu\"</i>\n"
    "• Số dư: <i>\"Tháng này chi bao nhiêu?\"</i>\n"
    "• So sánh TB: <i>\"Cafe tuần này so với bình thường?\"</i>\n"
    "• Báo cáo: <i>\"Báo cáo tuần này\"</i>\n"
    "• Phân tích: <i>\"So sánh tuần này với tuần trước\"</i>\n\n"
    "💰 <b>Ngân sách:</b>\n"
    "• <i>\"Đặt ngân sách ăn uống 3 triệu/tháng\"</i>\n"
    "• <i>\"Ngân sách của mình thế nào?\"</i>\n"
    "• <i>\"Tăng ngân sách mua sắm lên 2 triệu\"</i>\n"
    "• <i>\"Tăng tạm ngân sách 500k tháng này\"</i>\n"
    "• <i>\"Tắt cảnh báo ngân sách cafe\"</i>\n"
    "• <i>\"Xoá ngân sách ăn uống\"</i>\n\n"
    "🎯 <b>Mục tiêu tiết kiệm:</b>\n"
    "• <i>\"Mục tiêu tiết kiệm 20 triệu mua laptop\"</i>\n\n"
    "🔄 <b>Phí định kỳ:</b>\n"
    "• <i>\"Đăng ký Netflix 260k mỗi tháng\"</i>\n"
    "• <i>\"Danh sách đăng ký của mình\"</i>\n"
    "• <i>\"Netflix đã trả rồi\"</i>\n"
    "• <i>\"Huỷ Netflix\"</i>\n"
    "• <i>\"Netflix tăng giá lên 299k\"</i>\n\n"
    "🔔 <b>Lệnh nudge:</b>\n"
    "/nudge — Cảnh báo chi tiêu bất thường\n"
    "/nudge budget — Cảnh báo ngân sách\n"
    "/nudge goal — Tiến độ mục tiêu\n"
    "/nudge streak — Chuỗi ngày chi tốt\n"
    "/nudge sub — Nhắc phí định kỳ\n"
    "/nudge impulse — Cảnh báo mua bốc đồng\n"
    "/help — Danh sách này\n\n"
    "✏️ Sau mỗi giao dịch được ghi, bấm <b>Sửa danh mục</b> nếu phân loại chưa đúng."
)

_START_TEXT = (
    "Chào bạn! Mình là <b>ChiWi (Mai)</b> 👋\n"
    "Mình giúp bạn theo dõi chi tiêu và gửi nhắc nhở thông minh.\n\n"
    "Gõ /help để xem các lệnh, hoặc cứ nhắn tự nhiên (chữ hoặc voice) nhé!"
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
        if t.direction == "outflow":
            amt = t.amount
            total_out += amt
            by_cat[t.category_id or "Khác"] += amt

    top = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:3]
    return {
        "period": "this_week",
        "total_outflow": round(total_out),
        "transaction_count": len(txns),
        "top_categories": [{"cat": c, "total": round(v)} for c, v in top],
    }


def _category_keyboard(txn_id: str) -> list[list[dict]]:
    """Build a 2-column category selection keyboard for a given transaction."""
    from src.core.categories import load_categories

    categories = load_categories()
    buttons = [
        {"text": f"{cat.icon_emoji} {cat.name}", "callback_data": f"correct:{txn_id}:{cat.name}"}
        for cat in categories
    ]
    # 2 buttons per row
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return rows


async def _handle_callback_query(callback_query: dict) -> None:
    """Dispatch inline button callbacks: show category picker or apply correction."""
    cq_id = callback_query.get("id", "")
    cq_data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    from_id = str(callback_query.get("from", {}).get("id", "")) or chat_id
    message_id = message.get("message_id")

    if not chat_id or not cq_data:
        return

    user = await container.user_repo.find_by_chat_id(chat_id)
    if not user or not user.is_active:
        logger.warning("Unauthorized callback from chat_id=%s", chat_id)
        return
    
    internal_user_id = user.user_id

    telegram = container.telegram
    orchestrator = container.orchestrator

    if cq_data.startswith("cats:"):
        txn_id = cq_data.split(":", 1)[1]
        keyboard = _category_keyboard(txn_id)
        await telegram.answer_callback_query(cq_id)
        await telegram.edit_message_reply_markup(chat_id, message_id, keyboard)

    elif cq_data.startswith("correct:"):
        parts = cq_data.split(":", 2)
        if len(parts) != 3:
            await telegram.answer_callback_query(cq_id, text="Dữ liệu không hợp lệ.")
            return
        _, txn_id, new_category = parts
        from bson import ObjectId
        from bson.errors import InvalidId
        try:
            ObjectId(txn_id)
        except (InvalidId, TypeError):
            await telegram.answer_callback_query(cq_id, text="ID giao dịch không hợp lệ.")
            return
        from src.core.categories import category_names
        if new_category not in set(category_names()):
            await telegram.answer_callback_query(cq_id, text="Danh mục không hợp lệ.")
            return
        payload = {
            "user_id": internal_user_id,
            "transaction_id": txn_id,
            "new_category": new_category,
            "source": "telegram_callback",
        }
        result = await orchestrator.route("correction", payload)
        response_text = result.get("response_text", "✅ Đã cập nhật!")
        await telegram.answer_callback_query(cq_id, text=response_text)
        # Collapse the keyboard after correction
        await telegram.edit_message_reply_markup(chat_id, message_id, keyboard=None)

    elif cq_data.startswith("confirm_txn:"):
        txn_id = cq_data.split(":", 1)[1]
        from bson import ObjectId
        from bson.errors import InvalidId
        try:
            ObjectId(txn_id)
        except (InvalidId, TypeError):
            await telegram.answer_callback_query(cq_id, text="ID giao dịch không hợp lệ.")
            return
        txn = await container.transaction_repo.find_by_id(txn_id)
        if not txn or txn.user_id != internal_user_id:
            await telegram.answer_callback_query(cq_id, text="Không tìm thấy giao dịch.")
            return
        if txn.locked:
            await telegram.answer_callback_query(cq_id, text="🔒 Đã xác nhận rồi.")
            return
        await container.transaction_repo.lock(txn_id, internal_user_id)
        await telegram.answer_callback_query(cq_id, text="✅ Đã xác nhận và khoá giao dịch.")
        await telegram.edit_message_reply_markup(chat_id, message_id, keyboard=None)

    elif cq_data.startswith("delete_confirm:"):
        txn_id = cq_data.split(":", 1)[1]
        from bson import ObjectId
        from bson.errors import InvalidId
        try:
            ObjectId(txn_id)
        except (InvalidId, TypeError):
            await telegram.answer_callback_query(cq_id, text="ID giao dịch không hợp lệ.")
            return
        txn = await container.transaction_repo.find_by_id(txn_id)
        if not txn or txn.user_id != internal_user_id:
            await telegram.answer_callback_query(cq_id, text="Không tìm thấy giao dịch.")
            return
        if txn.locked:
            await telegram.answer_callback_query(cq_id, text="🔒 Giao dịch đã xác nhận, không thể xoá.")
            return
        await telegram.answer_callback_query(cq_id)
        confirm_keyboard = [[
            {"text": "✅ Xác nhận xoá", "callback_data": f"delete_ok:{txn_id}"},
            {"text": "❌ Giữ lại", "callback_data": f"delete_cancel:{txn_id}"},
        ]]
        await telegram.edit_message_reply_markup(chat_id, message_id, confirm_keyboard)

    elif cq_data.startswith("delete_ok:"):
        txn_id = cq_data.split(":", 1)[1]
        from bson import ObjectId
        from bson.errors import InvalidId
        try:
            ObjectId(txn_id)
        except (InvalidId, TypeError):
            await telegram.answer_callback_query(cq_id, text="ID giao dịch không hợp lệ.")
            return
        result = await orchestrator.route("delete_transaction", {
            "user_id": internal_user_id,
            "transaction_id": txn_id,
        })
        response_text = result.get("response_text", "✅ Đã xoá.")
        await telegram.answer_callback_query(cq_id, text=response_text[:200])
        await telegram.edit_message_reply_markup(chat_id, message_id, keyboard=None)

    elif cq_data.startswith("delete_cancel:"):
        await telegram.answer_callback_query(cq_id, text="Đã giữ lại giao dịch.")
        await telegram.edit_message_reply_markup(chat_id, message_id, keyboard=None)

    elif cq_data.startswith("sub_reg|"):
        parts = cq_data.split("|", 3)
        if len(parts) != 4:
            await telegram.answer_callback_query(cq_id, text="Dữ liệu không hợp lệ.")
            return
        _, merchant, amount_str, period = parts
        try:
            amount = float(amount_str)
        except ValueError:
            await telegram.answer_callback_query(cq_id, text="Dữ liệu không hợp lệ.")
            return
        if period not in {"weekly", "monthly", "yearly"}:
            await telegram.answer_callback_query(cq_id, text="Chu kỳ không hợp lệ.")
            return
        result = await orchestrator.handle_subscription_register({
            "user_id": internal_user_id,
            "name": merchant,
            "merchant_name": merchant,
            "amount": amount,
            "period": period,
        })
        response_text = result.get("response_text", "✅ Đã đăng ký theo dõi!")
        await telegram.answer_callback_query(cq_id, text=response_text[:200])
        await telegram.edit_message_reply_markup(chat_id, message_id, keyboard=None)


async def _handle_command(
    command: str, args: list[str], chat_id: str, real_user_id: str | None
) -> None:
    """Dispatch a bot command. Sends reply directly via TelegramService."""
    telegram = container.telegram

    if command == "/start":
        await telegram.send_message(chat_id, _START_TEXT)
        return

    if command == "/help":
        await telegram.send_message(chat_id, _HELP_TEXT)
        return

    if command == "/link":
        if not args:
            await telegram.send_message(chat_id, "Vui lòng nhập mã liên kết. Ví dụ: /link 123456\nBạn có thể lấy mã này trong phần Cài đặt trên ứng dụng Android.")
            return
        
        code = args[0]
        user = await container.user_repo.find_by_link_code(code)
        if not user:
            await telegram.send_message(chat_id, "Mã liên kết không hợp lệ hoặc đã hết hạn. Vui lòng lấy mã mới trên ứng dụng Android.")
            return
        
        user_id = user.user_id
        # Update user with telegram_id
        await container.user_repo.update_user(user_id, {
            "telegram_id": str(chat_id),
            "link_code": None,
            "link_code_expires": None
        })
        
        await telegram.send_message(chat_id, f"✅ Chúc mừng! Tài khoản Telegram đã được liên kết với người dùng <b>{user_id}</b>. Bây giờ bạn có thể nhắn tin cho Mai tại đây.")
        return

    if command == "/nudge":
        nudge_type = (
            _NUDGE_TYPES.get(args[0], _DEFAULT_NUDGE_TYPE)
            if args
            else _DEFAULT_NUDGE_TYPE
        )
        trigger_data = await _spending_summary(real_user_id)
        trigger_data["source"] = "telegram"
        payload = {
            "user_id": real_user_id,
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

    Auth: X-User-Id must belong to an active user account.
    """
    user = await container.user_repo.find_by_id(x_user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Unauthorized user")

    event = {
        "source": "android",
        "raw_text": payload.raw_text,
        "bank_hint": payload.bank_hint,
        "user_id": x_user_id,
        "timestamp": payload.timestamp,
    }

    result = await orchestrator.route("notification", event)
    return NotificationResponse(
        status=result.get("status", "error"),
        transaction_id=result.get("transaction_id"),
        parsed=result.get("parsed"),
    )


async def _handle_message_with_id(message: dict, update_id: int | None, real_user_id: str | None) -> None:
    """Process a Telegram text/voice message. Runs as a background task so
    the webhook handler can return HTTP 200 to Telegram immediately."""
    orchestrator = container.orchestrator
    telegram_service = container.telegram

    chat_id = str(message.get("chat", {}).get("id", ""))
    from_id = str(message.get("from", {}).get("id", "")) or chat_id
    text = message.get("text", "")
    voice = message.get("voice")

    # --- Command routing ---
    if text and text.startswith("/"):
        parts = text.split()
        command = parts[0].split("@")[0].lower()  # strip @botname suffix
        args = parts[1:]
        await _handle_command(command, args, chat_id, real_user_id)
        return

    # --- Voice message ---
    if voice:
        file_id = voice.get("file_id", "")
        mime_type = voice.get("mime_type", "audio/ogg")
        audio_bytes = b""
        try:
            tg_file = await telegram_service.bot.get_file(file_id)
            audio_bytes = bytes(await tg_file.download_as_bytearray())
        except Exception:
            logger.exception("Failed to download voice file_id=%s", file_id)
            await telegram_service.send_message(
                chat_id, "Xin lỗi, mình không tải được file âm thanh. Bạn thử nhắn chữ nhé?"
            )
            return

        payload = {
            "source": "telegram_voice",
            "audio_bytes": audio_bytes,
            "audio_mime_type": mime_type,
            "user_id": real_user_id,
        }
        result = await orchestrator.route("voice", payload)
        response_text = result.get("response_text")
        inline_keyboard = result.get("inline_keyboard")
        if response_text:
            if inline_keyboard:
                await telegram_service.send_message_with_keyboard(chat_id, response_text, inline_keyboard)
            else:
                await telegram_service.send_message(chat_id, response_text)
        return

    # --- Conversational path ---
    payload = {
        "source": "telegram",
        "message": text,
        "user_id": real_user_id,
    }

    event_type = await orchestrator.classify_event(payload)
    result = await orchestrator.route(event_type, payload)

    response_text = result.get("response_text")
    inline_keyboard = result.get("inline_keyboard")
    if response_text:
        if inline_keyboard:
            await telegram_service.send_message_with_keyboard(chat_id, response_text, inline_keyboard)
        else:
            await telegram_service.send_message(chat_id, response_text)


@router.post("/telegram")
async def telegram_webhook(
    update: dict,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    """Receive Telegram Bot API webhook updates.

    Guards run synchronously (fast Redis ops, ~2ms total) so Telegram always
    gets HTTP 200 quickly. Heavy processing (AI, DB) runs in a background task.

    Guards:
    0. Secret token validation — rejects requests without the registered secret.
    1. Stale message filter — drops messages older than configured max age.
    2. Deduplication — skips already-processed update_ids (Redis SET with TTL).
    3. Rate limiting — caps messages per user per minute.
    """
    import time as _time

    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            logger.warning("Telegram webhook rejected: invalid or missing secret token")
            raise HTTPException(status_code=403, detail="Forbidden")

    update_id = update.get("update_id")
    logger.info("Telegram update received: %s", update_id)

    # --- Inline button callback — background so answer_callback_query is fast ---
    callback_query = update.get("callback_query")
    if callback_query:
        background_tasks.add_task(_handle_callback_query, callback_query)
        return {"ok": True}

    message = update.get("message", {})
    if not message:
        return {"ok": True}

    # --- Guard 1: Stale message filter (pure arithmetic, no I/O) ---
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
    voice = message.get("voice")

    if not chat_id or (not text and not voice):
        return {"ok": True}

    # --- Authorization Check ---
    # 1. First, check if this chat_id is already linked to a user in DB
    user = await container.user_repo.find_by_chat_id(chat_id)
    real_user_id = user.user_id if user else None
    
    # 2. If not linked, check if it's a command (like /start, /help, /link)
    # Commands are allowed for anyone to facilitate onboarding/linking
    is_command = text and text.startswith("/")
    
    if not real_user_id and not is_command:
        # Fallback for migrated users: check if chat_id exists as a user_id
        legacy_user = await container.user_repo.find_by_id(chat_id)
        if legacy_user:
            real_user_id = chat_id
            # Auto-link for future lookups
            await container.user_repo.update_user(chat_id, {"telegram_id": chat_id})
        else:
            logger.warning("Unauthorized telegram user: chat_id=%s", chat_id)
            await container.telegram.send_message(chat_id, "Chào bạn! Hiện tại mình chỉ hỗ trợ người dùng đã đăng ký. Vui lòng tải ứng dụng Android và liên kết tài khoản nhé!")
            return {"ok": True}

    redis_client = container.redis

    # --- Guard 2: Deduplication via Redis (~1ms) ---
    if update_id and redis_client.is_connected:
        dedup_key = f"chiwi:telegram:update:{update_id}"
        already_seen = await redis_client._redis.set(
            dedup_key, "1", nx=True, ex=300  # 5 min TTL
        )
        if not already_seen:
            logger.warning("Duplicate update_id=%s, skipping", update_id)
            return {"ok": True}

    # --- Guard 3: Rate limiting (~1ms) ---
    if redis_client.is_connected:
        count = await redis_client.increment_rate_limit(chat_id, ttl=60)
        if count > settings.telegram_rate_limit_per_minute:
            logger.warning(
                "Rate limit exceeded for chat_id=%s (%d/min)",
                chat_id,
                count,
            )
            return {"ok": True}

    # All guards passed — hand off to background task
    # We need to pass the real_user_id we found
    background_tasks.add_task(_handle_message_with_id, message, update_id, real_user_id)
    return {"ok": True}

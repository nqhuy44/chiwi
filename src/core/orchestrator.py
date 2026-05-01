"""
Agent Orchestrator — Think-First routing pattern.

Classifies incoming events and dispatches to the appropriate agent pipeline.
"""

import logging
from datetime import UTC, datetime
from typing import Literal

from src.agents.analytics import AnalyticsAgent
from src.agents.behavioral import BehavioralAgent
from src.agents.conversational import ConversationalAgent
from src.agents.ingestion import IngestionAgent
from src.agents.reporting import ReportingAgent
from src.agents.tagging import TaggingAgent
from src.core.profiles import get_profile
from src.core.schemas import (AnalysisRequest, NudgeRequest, ParsedTransaction,
                              ReportRequest)
from src.db.models.budget import BudgetDocument, BudgetEventDocument
from src.db.models.correction import CorrectionDocument
from src.db.models.goal import GoalDocument
from src.db.models.subscription import SubscriptionDocument
from src.db.models.transaction import TransactionDocument
from src.db.repositories.budget_repo import BudgetEventRepository, BudgetRepository, effective_limit
from src.db.repositories.correction_repo import CorrectionRepository
from src.db.repositories.goal_repo import GoalRepository
from src.db.repositories.nudge_repo import NudgeRepository
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.db.repositories.transaction_repo import TransactionRepository
from src.services.gemini import GeminiService
from src.services.redis_client import RedisClient
from src.services.telegram import TelegramService

logger = logging.getLogger(__name__)


def _txn_keyboard(txn_id: str) -> list[list[dict]]:
    """Standard inline keyboard attached to every stored transaction message."""
    return [[
        {"text": "🗑️ Xoá", "callback_data": f"delete_confirm:{txn_id}"},
        {"text": "✅ Xác nhận", "callback_data": f"confirm_txn:{txn_id}"},
    ]]


EventType = Literal[
    "notification", "chat", "voice", "scheduled", "report", "analysis",
    "correction", "delete_transaction",
]


class Orchestrator:
    """Central orchestrator implementing Think-First routing."""

    def __init__(
        self,
        gemini: GeminiService,
        redis: RedisClient,
        telegram: TelegramService | None,
        transaction_repo: TransactionRepository,
        budget_repo: BudgetRepository,
        budget_event_repo: BudgetEventRepository,
        goal_repo: GoalRepository,
        correction_repo: CorrectionRepository,
        nudge_repo: NudgeRepository,
        subscription_repo: SubscriptionRepository,
    ) -> None:
        self._gemini = gemini
        self._redis = redis
        self._telegram = telegram
        self._transaction_repo = transaction_repo
        self._budget_repo = budget_repo
        self._budget_event_repo = budget_event_repo
        self._goal_repo = goal_repo
        self._correction_repo = correction_repo
        self._nudge_repo = nudge_repo
        self._subscription_repo = subscription_repo

        # Agents (initialized with shared services)
        self._ingestion = IngestionAgent(gemini)
        self._conversational = ConversationalAgent(gemini)
        self._reporting = ReportingAgent(gemini)
        self._analytics = AnalyticsAgent(gemini)
        self._tagging = TaggingAgent(gemini, redis, transaction_repo=transaction_repo)
        self._behavioral = BehavioralAgent(
            gemini=gemini, telegram=telegram, nudge_repo=nudge_repo
        )

    async def _get_user_chat_id(self, user_id: str) -> str:
        """Return the Telegram chat_id for a user, sourced from their profile."""
        profile = await get_profile(user_id)
        return profile.chat_id

    async def classify_event(self, event: dict) -> EventType:
        """Classify an incoming event to determine the agent pipeline."""
        source = event.get("source", "")

        if source == "android":
            return "notification"
        if source == "telegram_voice":
            return "voice"
        if source == "telegram_callback":
            return "correction"
        if source == "scheduled":
            return "scheduled"
        if source == "report_request":
            return "report"

        return "chat"

    async def route(self, event_type: EventType, payload: dict) -> dict:
        """Route event to the appropriate agent pipeline."""
        logger.info("Routing event_type=%s", event_type)

        match event_type:
            case "notification":
                return await self._handle_notification(payload)
            case "chat" | "voice":
                return await self._handle_chat(payload)
            case "scheduled":
                return await self._handle_scheduled(payload)
            case "report":
                return await self._handle_report(payload)
            case "analysis":
                return await self._handle_analysis(payload)
            case "correction":
                return await self._handle_correction(payload)
            case "delete_transaction":
                return await self._handle_delete_transaction(payload)
            case _:
                logger.warning("Unknown event type: %s", event_type)
                return {"status": "unknown_event"}

    async def _handle_notification(self, payload: dict) -> dict:
        """Pipeline: Ingestion Agent → Tagging Agent → Store.

        Called when the Android app forwards a raw bank notification.
        All parsing is done server-side so mobile releases are not needed
        to fix parsing bugs.
        """
        raw_text = payload.get("raw_text", "")
        bank_hint = payload.get("bank_hint")
        user_id = payload.get("user_id", "")
        chat_id = payload.get("chat_id", "")

        if not raw_text:
            return {"status": "empty_notification"}

        parsed: ParsedTransaction = await self._ingestion.parse(raw_text, bank_hint)

        if not parsed.is_transaction:
            logger.info("Non-transaction notification, skipping")
            return {"status": "not_transaction", "parsed": parsed.model_dump()}

        tags_result = await self._tagging.enrich(transaction=parsed, user_id=user_id)

        txn_doc = TransactionDocument(
            user_id=user_id,
            source="notification",
            amount=parsed.amount or 0.0,
            currency=parsed.currency,
            direction=parsed.direction or "outflow",
            raw_text=raw_text,
            merchant_name=parsed.merchant_name,
            category_id=tags_result.get("category_name"),
            tags=tags_result.get("tags", []),
            transaction_time=parsed.transaction_time or datetime.now(UTC),
            agent_confidence=parsed.confidence,
            ai_metadata={"bank_name": parsed.bank_name, "tagging_result": tags_result},
        )

        txn_id = await self._transaction_repo.insert(txn_doc)
        logger.info("Transaction stored from Android notification: %s", txn_id)
        await self._redis.invalidate_dashboard_cache(user_id)

        if txn_doc.direction == "inflow":
            await self._update_goal_progress(user_id, txn_doc.amount)

        if chat_id and parsed.merchant_name:
            await self._check_subscription_match(
                user_id, parsed.merchant_name, parsed.amount or 0.0,
                parsed.transaction_time or datetime.now(UTC), chat_id, txn_id,
            )

        await self._redis.set_last_transaction(user_id, txn_id)

        if chat_id:
            direction_icon = "➕" if txn_doc.direction == "inflow" else "➖"
            amount_str = f"{txn_doc.amount:,.0f}"
            category = tags_result.get("category_name", "Khác")
            parts = [f"✅ {direction_icon} {amount_str}đ", category]
            if parsed.merchant_name:
                parts.append(parsed.merchant_name)
            await self._telegram.send_message_with_keyboard(
                chat_id, " | ".join(parts), _txn_keyboard(txn_id)
            )

        return {
            "status": "stored",
            "transaction_id": txn_id,
            "parsed": parsed.model_dump(),
        }

    async def _handle_chat(self, payload: dict) -> dict:
        """Conversational Agent -> Tagging Agent -> Store."""
        user_id = payload.get("user_id", "")
        chat_id = payload.get("chat_id", "")
        source = payload.get("source", "")
        profile = await get_profile(user_id)
        user_tz = profile.timezone

        raw_text = payload.get("message", "")

        # Step 1: Parse intent (text or voice)
        if source == "telegram_voice":
            audio_bytes = payload.get("audio_bytes", b"")
            mime_type = payload.get("audio_mime_type", "audio/ogg")
            if not audio_bytes:
                return {"status": "error", "response_text": "Không nhận được file âm thanh."}
            intent_result = await self._conversational.process_voice(
                audio_bytes, mime_type, chat_id, user_timezone=user_tz
            )
        else:
            if not raw_text:
                return {"status": "empty_message"}
            intent_result = await self._conversational.process_message(
                message=raw_text, chat_id=chat_id, user_timezone=user_tz
            )

        if intent_result.intent == "request_report":
            return await self._handle_report(
                {
                    "user_id": user_id,
                    "period": intent_result.payload.get("period", "today"),
                    "user_timezone": user_tz,
                }
            )

        if intent_result.intent == "request_analysis":
            return await self._handle_analysis(
                {
                    "user_id": user_id,
                    "analysis_type": intent_result.payload.get(
                        "analysis_type", "compare"
                    ),
                    "period": intent_result.payload.get("period", "this_week"),
                    "compare_period": intent_result.payload.get("compare_period"),
                    "category_filter": intent_result.payload.get("category_filter"),
                    "user_timezone": user_tz,
                }
            )

        if intent_result.intent == "ask_spending_vs_avg":
            return await self._handle_ask_spending_vs_avg(
                {
                    "user_id": user_id,
                    "period": intent_result.payload.get("period", "this_week"),
                }
            )

        if intent_result.intent == "ask_balance":
            return await self._handle_ask_balance(
                {
                    "user_id": user_id,
                    "period": intent_result.payload.get("period", "this_month"),
                    "user_timezone": user_tz,
                }
            )

        if intent_result.intent == "ask_category":
            return await self._handle_ask_category({"user_id": user_id})

        if intent_result.intent == "set_budget":
            return await self._handle_set_budget(
                {
                    "user_id": user_id,
                    "category_name": intent_result.payload.get("category_name"),
                    "limit_amount": intent_result.payload.get("limit_amount"),
                    "budget_period": intent_result.payload.get("budget_period", "monthly"),
                    "user_timezone": user_tz,
                }
            )

        if intent_result.intent == "ask_budget":
            return await self._handle_ask_budget({"user_id": user_id})

        if intent_result.intent == "update_budget":
            return await self._handle_update_budget(
                {
                    "user_id": user_id,
                    "category_name": intent_result.payload.get("category_name"),
                    "new_limit": intent_result.payload.get("new_limit"),
                }
            )

        if intent_result.intent == "temp_increase_budget":
            return await self._handle_temp_increase_budget(
                {
                    "user_id": user_id,
                    "category_name": intent_result.payload.get("category_name"),
                    "temp_limit": intent_result.payload.get("temp_limit"),
                    "reason": intent_result.payload.get("budget_reason"),
                }
            )

        if intent_result.intent == "silence_budget":
            return await self._handle_silence_budget(
                {
                    "user_id": user_id,
                    "category_name": intent_result.payload.get("category_name"),
                }
            )

        if intent_result.intent == "disable_budget":
            return await self._handle_disable_budget(
                {
                    "user_id": user_id,
                    "category_name": intent_result.payload.get("category_name"),
                }
            )

        if intent_result.intent == "set_goal":
            return await self._handle_set_goal(
                {
                    "user_id": user_id,
                    "goal_name": intent_result.payload.get("goal_name"),
                    "target_amount": intent_result.payload.get("target_amount"),
                    "deadline": intent_result.payload.get("deadline"),
                }
            )

        if intent_result.intent == "set_subscription":
            return await self._handle_set_subscription(
                {
                    "user_id": user_id,
                    "name": intent_result.payload.get("subscription_name"),
                    "merchant_name": intent_result.payload.get("subscription_merchant"),
                    "amount": intent_result.payload.get("subscription_amount"),
                    "period": intent_result.payload.get("subscription_period", "monthly"),
                    "next_charge_date": intent_result.payload.get("subscription_next_date"),
                    "user_timezone": user_tz,
                }
            )

        if intent_result.intent == "list_subscriptions":
            return await self._handle_list_subscriptions({"user_id": user_id, "user_timezone": user_tz})

        if intent_result.intent == "query_subscription":
            return await self._handle_query_subscription(
                {
                    "user_id": user_id,
                    "merchant_name": intent_result.payload.get("subscription_merchant"),
                    "user_timezone": user_tz,
                }
            )

        if intent_result.intent == "mark_subscription_paid":
            return await self._handle_mark_subscription_paid(
                {
                    "user_id": user_id,
                    "merchant_name": intent_result.payload.get("subscription_merchant"),
                    "subscription_paid_date": intent_result.payload.get("subscription_paid_date"),
                    "user_timezone": user_tz,
                }
            )

        if intent_result.intent == "cancel_subscription":
            return await self._handle_cancel_subscription(
                {
                    "user_id": user_id,
                    "merchant_name": intent_result.payload.get("subscription_merchant"),
                    "user_timezone": user_tz,
                }
            )

        if intent_result.intent == "update_subscription":
            return await self._handle_update_subscription(
                {
                    "user_id": user_id,
                    "merchant_name": intent_result.payload.get("subscription_merchant"),
                    "new_amount": intent_result.payload.get("subscription_new_amount"),
                    "new_period": intent_result.payload.get("subscription_new_period"),
                    "new_next_date": intent_result.payload.get("subscription_new_date"),
                    "user_timezone": user_tz,
                }
            )

        if intent_result.intent == "delete_transaction":
            return await self._handle_delete_transaction({
                "user_id": user_id,
                "transaction_id": intent_result.payload.get("transaction_id"),
                "reference": intent_result.payload.get("reference", "last"),
            })

        if intent_result.intent != "log_transaction":
            return {
                "status": "chat_processed",
                "intent": intent_result.intent,
                "response_text": intent_result.response_text,
            }

        # Step 2: Extract payload to ParsedTransaction
        p_data = intent_result.payload
        try:
            # Handle possible ISO string format from LLM
            txn_time = (
                datetime.fromisoformat(p_data["transaction_time"])
                if p_data.get("transaction_time")
                else datetime.now(UTC)
            )
        except ValueError:
            txn_time = datetime.now(UTC)

        parsed = ParsedTransaction(
            is_transaction=True,
            amount=p_data.get("amount"),
            currency=p_data.get("currency", "VND"),
            direction=p_data.get("direction", "outflow"),
            merchant_name=p_data.get("merchant_name"),
            transaction_time=txn_time,
            raw_text=raw_text,
            confidence="high",  # Conversational parsing is usually high confidence
        )

        # Step 3: Enrich with Tagging Agent
        tags_result = await self._tagging.enrich(
            transaction=parsed,
            user_id=user_id,
        )

        # Step 4: Store in MongoDB
        txn_doc = TransactionDocument(
            user_id=user_id,
            source="chat",
            amount=parsed.amount or 0.0,
            currency=parsed.currency,
            direction=parsed.direction or "outflow",
            raw_text=raw_text,
            merchant_name=parsed.merchant_name,
            category_id=tags_result.get("category_name"),
            tags=tags_result.get("tags", []),
            transaction_time=parsed.transaction_time or datetime.now(UTC),
            agent_confidence=parsed.confidence,
            ai_metadata={
                "tagging_result": tags_result,
            },
        )

        txn_id = await self._transaction_repo.insert(txn_doc)
        logger.info("Transaction stored via chat: %s", txn_id)
        await self._redis.invalidate_dashboard_cache(user_id)

        await self._redis.set_last_transaction(user_id, txn_id)

        if txn_doc.direction == "inflow":
            await self._update_goal_progress(user_id, txn_doc.amount)

        if parsed.merchant_name:
            await self._check_subscription_match(
                user_id, parsed.merchant_name, parsed.amount or 0.0,
                parsed.transaction_time or datetime.now(UTC), chat_id, txn_id,
            )

        return {
            "status": "stored",
            "transaction_id": txn_id,
            "parsed": parsed.model_dump(),
            "response_text": intent_result.response_text or "Đã ghi nhận giao dịch của bạn!",
            "inline_keyboard": _txn_keyboard(txn_id),
        }

    async def _handle_scheduled(self, payload: dict) -> dict:
        """Behavioral Agent -> Nudge.

        Expects payload: {user_id, chat_id, nudge_type, trigger_data}.
        ``trigger_data`` is produced upstream by the trigger engine
        (Phase 3.2); for Phase 3.1 callers (e.g. the worker, manual tests)
        pass it directly.
        """
        user_id = payload.get("user_id")
        chat_id = payload.get("chat_id")
        nudge_type = payload.get("nudge_type")

        if not user_id or not nudge_type:
            return {
                "status": "error",
                "reason": "missing_fields",
                "required": ["user_id", "nudge_type"],
            }

        request = NudgeRequest(
            user_id=user_id,
            chat_id=chat_id,
            nudge_type=nudge_type,
            trigger_data=payload.get("trigger_data") or {},
        )
        result = await self._behavioral.analyze(request)
        return {
            "status": "sent" if result.sent else "blocked",
            "nudge_id": result.nudge_id,
            "blocked_reason": result.blocked_reason,
            "message": result.message,
        }

    async def _handle_report(self, payload: dict) -> dict:
        """Reporting Agent -> Dashboard."""
        from src.core.utils import resolve_date_range

        user_id = payload.get("user_id")
        period_str = payload.get("period", "today")
        profile = await get_profile(user_id or "")
        user_tz = payload.get("user_timezone") or profile.timezone

        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}

        start_date, end_date = resolve_date_range(
            period_str, payload.get("start_date"), payload.get("end_date"), user_tz
        )
        if not start_date:
            return {
                "status": "error",
                "response_text": f"Mai chưa hỗ trợ mốc thời gian '{period_str}' đâu ạ. Bạn thử 'hôm nay', 'hôm qua', 'tuần này' hoặc 'tháng này' nhé!",
            }

        transactions = [
            t.model_dump()
            for t in await self._transaction_repo.find_by_user(
                user_id=user_id, start_date=start_date, end_date=end_date, limit=100
            )
        ]

        request = ReportRequest(
            user_id=user_id, report_type="summary", period=period_str
        )

        result = await self._reporting.generate(
            request, transactions, user_timezone=user_tz
        )
        return {"status": result["status"], "response_text": result["report_text"]}

    async def _handle_analysis(self, payload: dict) -> dict:
        """Analytics Agent -> Complex analysis."""
        from src.core.utils import get_comparison_ranges, resolve_date_range

        user_id = payload.get("user_id")
        analysis_type = payload.get("analysis_type", "compare")
        period_str = payload.get("period", "this_week")
        compare_period = payload.get("compare_period")
        category_filter = payload.get("category_filter")
        profile = await get_profile(user_id or "")
        user_tz = payload.get("user_timezone") or profile.timezone
        start_iso = payload.get("start_date")
        end_iso = payload.get("end_date")

        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}

        # Fetch current period data
        if analysis_type == "compare":
            (cur_start, cur_end), (comp_start, comp_end) = get_comparison_ranges(
                period_str, compare_period, timezone=user_tz
            )

            if not cur_start or not comp_start:
                return {
                    "status": "error",
                    "response_text": "Mai chưa hỗ trợ mốc thời gian này để so sánh đâu ạ.",
                }

            current_txns = [
                t.model_dump()
                for t in await self._transaction_repo.find_by_user(
                    user_id=user_id, start_date=cur_start, end_date=cur_end, limit=200
                )
            ]
            comparison_txns = [
                t.model_dump()
                for t in await self._transaction_repo.find_by_user(
                    user_id=user_id, start_date=comp_start, end_date=comp_end, limit=200
                )
            ]
        elif analysis_type == "deep_dive":
            start_date, end_date = resolve_date_range(period_str, start_iso, end_iso, user_tz)
            if not start_date:
                return {
                    "status": "error",
                    "response_text": f"Mai chưa hỗ trợ mốc thời gian '{period_str}' để phân tích chi tiết.",
                }

            current_txns = [
                t.model_dump()
                for t in await self._transaction_repo.find_by_user(
                    user_id=user_id, start_date=start_date, end_date=end_date, limit=500
                )
            ]
            # Filter to the requested category when specified
            if category_filter:
                current_txns = [
                    t for t in current_txns
                    if (t.get("category_id") or "").lower() == category_filter.lower()
                ]
            comparison_txns = None

        else:
            # Trend: fetch current period only
            start_date, end_date = resolve_date_range(period_str, start_iso, end_iso, user_tz)
            if not start_date:
                return {
                    "status": "error",
                    "response_text": f"Mai chưa hỗ trợ mốc thời gian '{period_str}' để phân tích xu hướng.",
                }

            current_txns = [
                t.model_dump()
                for t in await self._transaction_repo.find_by_user(
                    user_id=user_id, start_date=start_date, end_date=end_date, limit=200
                )
            ]
            comparison_txns = None

        request = AnalysisRequest(
            user_id=user_id,
            analysis_type=analysis_type,
            period=period_str,
            compare_period=compare_period,
            category_filter=category_filter,
        )

        result = await self._analytics.analyze(
            request, current_txns, comparison_txns, user_timezone=user_tz
        )
        return {
            "status": result["status"],
            "response_text": result["report_text"],
        }

    async def _handle_ask_balance(self, payload: dict) -> dict:
        """Compute net inflow/outflow for a period and format a Vietnamese reply."""
        from src.core.utils import resolve_date_range

        user_id = payload.get("user_id")
        period_str = payload.get("period", "this_month")
        profile = await get_profile(user_id or "")
        user_tz = payload.get("user_timezone") or profile.timezone

        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}

        start_date, end_date = resolve_date_range(
            period_str, payload.get("start_date"), payload.get("end_date"), user_tz
        )
        if not start_date:
            return {
                "status": "error",
                "response_text": (
                    f"Mai chưa hỗ trợ mốc thời gian '{period_str}' đâu ạ. "
                    "Bạn thử 'hôm nay', 'tuần này', 'tháng này' nhé!"
                ),
            }

        transactions = await self._transaction_repo.find_by_user(
            user_id=user_id, start_date=start_date, end_date=end_date, limit=500
        )

        total_inflow = sum(
            t.amount for t in transactions if t.direction == "inflow"
        )
        total_outflow = sum(
            t.amount for t in transactions if t.direction == "outflow"
        )
        net = total_inflow - total_outflow

        period_labels = {
            "today": "hôm nay",
            "yesterday": "hôm qua",
            "this_week": "tuần này",
            "this_month": "tháng này",
            "last_week": "tuần trước",
            "last_month": "tháng trước",
        }
        if period_str == "custom":
            from src.core.config import settings as _s
            from zoneinfo import ZoneInfo as _ZI
            _tz = _ZI(user_tz or _s.business_timezone)
            _sd = start_date.replace(tzinfo=UTC).astimezone(_tz) if start_date else None
            _ed = end_date.replace(tzinfo=UTC).astimezone(_tz) if end_date else None
            period_label = (
                f"từ {_sd.strftime('%d/%m/%Y')} đến {_ed.strftime('%d/%m/%Y')}"
                if _sd and _ed else "khoảng thời gian đã chọn"
            )
        else:
            period_label = period_labels.get(period_str, period_str)

        if not transactions:
            response = (
                f"Chưa có giao dịch nào {period_label} cả. "
                "Bạn cứ nhắn Mai khi chi/thu nhé!"
            )
        else:
            response = (
                f"Cân đối {period_label}:\n"
                f"  Thu: <b>+{total_inflow:,.0f} VND</b>\n"
                f"  Chi: <b>-{total_outflow:,.0f} VND</b>\n"
                f"  Còn lại: <b>{net:,.0f} VND</b>"
            )

        return {"status": "success", "response_text": response}

    async def _handle_ask_spending_vs_avg(self, payload: dict) -> dict:
        """Compare current period spending (total + per-category) against historical average."""
        from src.core.spending_avg import compute_avg_all_categories

        user_id = payload.get("user_id")
        period = payload.get("period", "weekly")
        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}

        profile = await get_profile(user_id)
        period_map = {"today": "daily", "this_week": "weekly", "this_month": "monthly"}
        avg_period = period_map.get(period, "weekly")

        total, cat_results = await compute_avg_all_categories(
            self._transaction_repo, user_id,
            period=avg_period, timezone=profile.timezone,
        )

        period_label = {"daily": "hôm nay", "weekly": "tuần này", "monthly": "tháng này"}.get(
            avg_period, avg_period
        )
        baseline_label = {"daily": "14 ngày", "weekly": "4 tuần", "monthly": "3 tháng"}.get(
            avg_period, ""
        )

        if not total.has_baseline:
            return {
                "status": "success",
                "response_text": (
                    f"Chưa đủ lịch sử để tính trung bình {period_label}. "
                    f"Mai cần ít nhất {baseline_label} dữ liệu nhé!"
                ),
            }

        def _arrow(pct: float | None) -> str:
            if pct is None:
                return "—"
            if pct > 15:
                return f"▲ +{pct:.0f}% ⚠️"
            if pct < -15:
                return f"▼ {pct:.0f}% 👍"
            return f"→ {pct:+.0f}%"

        lines = [
            f"📊 <b>Chi tiêu {period_label} vs trung bình {baseline_label}:</b>\n",
            f"<b>Tổng:</b> {total.current:,.0f}đ / TB {total.average:,.0f}đ  {_arrow(total.pct_diff)}",
        ]

        if cat_results:
            lines.append("")
            for r in cat_results[:6]:  # top 6 categories by current spend
                lines.append(
                    f"  {r.scope}: {r.current:,.0f}đ / TB {r.average:,.0f}đ  {_arrow(r.pct_diff)}"
                )

        return {"status": "success", "response_text": "\n".join(lines)}

    async def _handle_ask_category(self, payload: dict) -> dict:
        """List the configured spending categories in Vietnamese."""
        from src.core.categories import load_categories

        categories = load_categories()
        lines = [
            f"{cat.icon_emoji} {cat.name}"
            for cat in categories
            if not cat.parent_category
        ]
        response = (
            "Các danh mục Mai đang phân loại:\n" + "\n".join(lines)
            if lines
            else "Hiện chưa có danh mục nào được cấu hình."
        )
        return {"status": "success", "response_text": response}

    async def _handle_set_budget(self, payload: dict) -> dict:
        """Create a budget for a category + period."""
        from src.core.utils import get_budget_window

        user_id = payload.get("user_id")
        category_name = payload.get("category_name")
        limit_amount = payload.get("limit_amount")
        budget_period = payload.get("budget_period", "monthly")
        profile = await get_profile(user_id or "")
        user_tz = payload.get("user_timezone") or profile.timezone

        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}

        if not category_name or not limit_amount:
            return {
                "status": "error",
                "response_text": (
                    "Mai cần biết danh mục và số tiền để đặt ngân sách nha. "
                    "Ví dụ: <i>'đặt ngân sách ăn uống 2 triệu tháng này'</i>."
                ),
            }

        start_date, end_date = get_budget_window(budget_period, timezone=user_tz)
        if not start_date:
            return {
                "status": "error",
                "response_text": (
                    f"Mai chưa hỗ trợ chu kỳ ngân sách '{budget_period}' đâu ạ. "
                    "Bạn thử 'tuần' (weekly) hoặc 'tháng' (monthly) nhé!"
                ),
            }

        budget = BudgetDocument(
            user_id=user_id,
            category_id=category_name,
            limit_amount=float(limit_amount),
            period=budget_period,
        )
        budget_id = await self._budget_repo.insert(budget)
        await self._budget_event_repo.insert(BudgetEventDocument(
            user_id=user_id,
            budget_id=budget_id,
            category_id=category_name,
            event_type="created",
            new_value={"limit_amount": float(limit_amount), "period": budget_period},
        ))
        logger.info("Budget stored: %s", budget_id)

        period_label = "tuần này" if budget_period == "weekly" else "tháng này"
        response = (
            f"Đã đặt ngân sách <b>{float(limit_amount):,.0f} VND</b> "
            f"cho <b>{category_name}</b> trong {period_label} nhé!"
        )
        return {
            "status": "success",
            "budget_id": budget_id,
            "response_text": response,
        }

    async def _find_budget_by_category(self, user_id: str, category_name: str) -> BudgetDocument | None:
        """Find an active budget matching the given category name."""
        budgets = await self._budget_repo.find_by_user(user_id)
        for b in budgets:
            if b.category_id.lower() == category_name.lower():
                return b
        return None

    async def _handle_ask_budget(self, payload: dict) -> dict:
        """Return current usage status for all active budgets."""
        from src.core.utils import get_budget_window

        user_id = payload.get("user_id")
        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}

        profile = await get_profile(user_id)
        tz_name = profile.timezone
        now = datetime.now(UTC).replace(tzinfo=None)

        budgets = await self._budget_repo.find_by_user(user_id)
        if not budgets:
            return {
                "status": "success",
                "response_text": (
                    "Bạn chưa đặt ngân sách nào. "
                    "Nhắn <i>'đặt ngân sách ăn uống 2 triệu tháng này'</i> để bắt đầu nhé!"
                ),
            }

        lines = []
        for b in budgets:
            category = b.category_id
            period = b.period
            start, end = get_budget_window(period, timezone=tz_name)
            if not start:
                continue

            txns = await self._transaction_repo.find_by_user(
                user_id=user_id, start_date=start, end_date=now, limit=200
            )
            spent = sum(
                t.amount for t in txns
                if t.direction == "outflow"
                and (t.category_id or "").lower() == category.lower()
            )
            limit = effective_limit(b, now)
            pct = min(round(spent / limit * 100), 999) if limit > 0 else 0
            bar = "🟩" * min(pct // 20, 5)
            bar = bar or "⬜"
            period_label = {"daily": "hôm nay", "weekly": "tuần", "monthly": "tháng"}.get(period, period)
            silence_tag = " 🔕" if b.is_silenced else ""
            temp_tag = f" *(tạm {limit:,.0f}đ)*" if b.temp_limit else ""
            lines.append(
                f"{bar} <b>{category}</b>{silence_tag} — "
                f"{spent:,.0f}/{limit:,.0f}đ ({pct}%) / {period_label}{temp_tag}"
            )

        return {
            "status": "success",
            "response_text": "📊 <b>Ngân sách hiện tại:</b>\n\n" + "\n".join(lines),
        }

    async def _handle_update_budget(self, payload: dict) -> dict:
        """Update the base limit of an existing budget and record the change event."""
        user_id = payload.get("user_id")
        category_name = payload.get("category_name")
        new_limit = payload.get("new_limit")

        if not user_id or not category_name or not new_limit:
            return {
                "status": "error",
                "response_text": (
                    "Mai cần biết danh mục và số tiền mới nha. "
                    "Ví dụ: <i>'tăng ngân sách ăn uống lên 3 triệu'</i>."
                ),
            }

        budget = await self._find_budget_by_category(user_id, category_name)
        if not budget:
            return {
                "status": "error",
                "response_text": f"Không tìm thấy ngân sách <b>{category_name}</b> đang hoạt động.",
            }

        budget_id = str(budget.id)
        old_limit = budget.limit_amount or 0.0
        await self._budget_repo.update_limit(budget_id, user_id, float(new_limit))
        await self._budget_event_repo.insert(BudgetEventDocument(
            user_id=user_id,
            budget_id=budget_id,
            category_id=budget.category_id,
            event_type="limit_updated",
            old_value={"limit_amount": old_limit},
            new_value={"limit_amount": float(new_limit)},
        ))

        direction = "tăng" if float(new_limit) > old_limit else "giảm"
        return {
            "status": "success",
            "response_text": (
                f"Đã {direction} ngân sách <b>{budget.category_id}</b> "
                f"từ {old_limit:,.0f}đ → <b>{float(new_limit):,.0f}đ</b> nhé!"
            ),
        }

    async def _handle_temp_increase_budget(self, payload: dict) -> dict:
        """Set a temporary limit override for the current cycle only."""
        from src.core.utils import get_budget_window

        user_id = payload.get("user_id")
        category_name = payload.get("category_name")
        temp_limit = payload.get("temp_limit")
        reason = payload.get("reason")

        if not user_id or not category_name or not temp_limit:
            return {
                "status": "error",
                "response_text": (
                    "Mai cần biết danh mục, số tiền tạm thời và lý do nha. "
                    "Ví dụ: <i>'tăng tạm cà phê tuần này lên 1 triệu vì có meeting'</i>."
                ),
            }

        budget = await self._find_budget_by_category(user_id, category_name)
        if not budget:
            return {
                "status": "error",
                "response_text": f"Không tìm thấy ngân sách <b>{category_name}</b> đang hoạt động.",
            }

        profile = await get_profile(user_id)
        period = budget.period
        _, expires_at = get_budget_window(period, timezone=profile.timezone)
        if not expires_at:
            return {"status": "error", "response_text": "Không thể tính ngày hết hạn tạm thời."}

        budget_id = str(budget.id)
        old_limit = budget.limit_amount or 0.0
        await self._budget_repo.set_temp_override(budget_id, user_id, float(temp_limit), expires_at, reason)
        await self._budget_event_repo.insert(BudgetEventDocument(
            user_id=user_id,
            budget_id=budget_id,
            category_id=budget.category_id,
            event_type="temp_override_set",
            old_value={"limit_amount": old_limit},
            new_value={"temp_limit": float(temp_limit), "expires_at": expires_at.isoformat()},
            reason=reason,
        ))

        period_label = {"daily": "hôm nay", "weekly": "tuần này", "monthly": "tháng này"}.get(period, period)
        expires_str = expires_at.strftime("%d/%m")
        return {
            "status": "success",
            "response_text": (
                f"Đã tăng tạm ngân sách <b>{budget.category_id}</b> "
                f"lên <b>{float(temp_limit):,.0f}đ</b> cho {period_label} "
                f"(hết hạn {expires_str}). "
                f"Ngân sách gốc {old_limit:,.0f}đ sẽ tự khôi phục sau đó nhé! 👍"
            ),
        }

    async def _handle_silence_budget(self, payload: dict) -> dict:
        """Silence notifications for a budget. System still tracks but won't nudge."""
        user_id = payload.get("user_id")
        category_name = payload.get("category_name")

        if not user_id or not category_name:
            return {
                "status": "error",
                "response_text": "Mai cần biết danh mục muốn im lặng nha.",
            }

        budget = await self._find_budget_by_category(user_id, category_name)
        if not budget:
            return {
                "status": "error",
                "response_text": f"Không tìm thấy ngân sách <b>{category_name}</b>.",
            }

        budget_id = str(budget.id)
        await self._budget_repo.silence(budget_id, user_id)
        await self._budget_event_repo.insert(BudgetEventDocument(
            user_id=user_id,
            budget_id=budget_id,
            category_id=budget.category_id,
            event_type="silenced",
            old_value={"is_silenced": False},
            new_value={"is_silenced": True},
        ))

        return {
            "status": "success",
            "response_text": (
                f"Đã tắt thông báo ngân sách <b>{budget.category_id}</b>. "
                "Mai vẫn theo dõi nhưng sẽ không nhắc nữa nhé. 🔕"
            ),
        }

    async def _handle_disable_budget(self, payload: dict) -> dict:
        """Deactivate a budget entirely — stops tracking and notifications."""
        user_id = payload.get("user_id")
        category_name = payload.get("category_name")

        if not user_id or not category_name:
            return {
                "status": "error",
                "response_text": "Mai cần biết danh mục muốn tắt nha.",
            }

        budget = await self._find_budget_by_category(user_id, category_name)
        if not budget:
            return {
                "status": "error",
                "response_text": f"Không tìm thấy ngân sách <b>{category_name}</b> đang hoạt động.",
            }

        budget_id = str(budget.id)
        await self._budget_repo.deactivate(budget_id, user_id)
        await self._budget_event_repo.insert(BudgetEventDocument(
            user_id=user_id,
            budget_id=budget_id,
            category_id=budget.category_id,
            event_type="disabled",
            old_value={"is_active": True},
            new_value={"is_active": False},
        ))

        return {
            "status": "success",
            "response_text": (
                f"Đã tắt ngân sách <b>{budget.category_id}</b>. "
                "Lịch sử chi tiêu vẫn được giữ lại nhé."
            ),
        }

    async def _handle_set_goal(self, payload: dict) -> dict:
        """Create a savings / financial goal."""
        user_id = payload.get("user_id")
        goal_name = payload.get("goal_name")
        target_amount = payload.get("target_amount")
        deadline_raw = payload.get("deadline")

        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}

        if not goal_name or not target_amount:
            return {
                "status": "error",
                "response_text": (
                    "Mai cần tên mục tiêu và số tiền nha. "
                    "Ví dụ: <i>'đặt mục tiêu tiết kiệm 20 triệu mua laptop'</i>."
                ),
            }

        deadline: datetime | None = None
        if deadline_raw:
            try:
                deadline = datetime.fromisoformat(deadline_raw)
            except (ValueError, TypeError):
                deadline = None

        goal = GoalDocument(
            user_id=user_id,
            name=goal_name,
            target_amount=float(target_amount),
            deadline=deadline,
        )
        goal_id = await self._goal_repo.insert(goal)
        logger.info("Goal stored: %s", goal_id)

        deadline_suffix = (
            f" trước <b>{deadline.strftime('%d/%m/%Y')}</b>" if deadline else ""
        )
        response = (
            f"Đã tạo mục tiêu <b>{goal_name}</b> với số tiền "
            f"<b>{float(target_amount):,.0f} VND</b>{deadline_suffix} nhé! "
            "Cố lên anh/chị ơi 💪"
        )
        return {
            "status": "success",
            "goal_id": goal_id,
            "response_text": response,
        }

    async def _handle_set_subscription(self, payload: dict) -> dict:
        """Register a recurring subscription for the user."""
        user_id = payload.get("user_id")
        name = payload.get("name")
        merchant_name = payload.get("merchant_name")
        amount = payload.get("amount")
        period = payload.get("period", "monthly")
        next_date_raw = payload.get("next_charge_date")

        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}
        if not name or not merchant_name or not amount:
            return {
                "status": "error",
                "response_text": (
                    "Mai cần tên dịch vụ, tên merchant và số tiền nha. "
                    "Ví dụ: <i>'đăng ký Netflix 260k mỗi tháng'</i>."
                ),
            }

        next_charge: datetime | None = None
        if next_date_raw:
            try:
                next_charge = datetime.fromisoformat(next_date_raw)
            except (ValueError, TypeError):
                next_charge = None
        if not next_charge:
            from dateutil.relativedelta import relativedelta as _rd
            _periods = {"weekly": dict(weeks=1), "yearly": dict(years=1)}
            next_charge = datetime.now(UTC) + (_rd(**_periods[period]) if period in _periods else _rd(months=1))

        sub = SubscriptionDocument(
            user_id=user_id,
            name=name,
            merchant_name=merchant_name,
            amount=float(amount),
            period=period,
            next_charge_date=next_charge,
            anchor_day=next_charge.day,
            source="manual",
        )
        sub_id = await self._subscription_repo.insert(sub)
        logger.info("Subscription registered: %s id=%s", name, sub_id)

        period_label = {"monthly": "tháng", "weekly": "tuần", "yearly": "năm"}.get(
            period, period
        )
        next_str = next_charge.strftime("%d/%m/%Y")
        return {
            "status": "success",
            "subscription_id": sub_id,
            "response_text": (
                f"Đã đăng ký theo dõi <b>{name}</b> "
                f"<b>{float(amount):,.0f} VND/{period_label}</b>. "
                f"Kỳ tới: <b>{next_str}</b> 🔄"
            ),
        }

    async def _handle_list_subscriptions(self, payload: dict) -> dict:
        """Return the user's active subscriptions as a formatted message."""
        user_id = payload.get("user_id")
        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}

        subs = await self._subscription_repo.find_by_user(user_id)
        if not subs:
            return {
                "status": "success",
                "response_text": (
                    "Bạn chưa đăng ký theo dõi phí định kỳ nào. "
                    "Nhắn <i>'đăng ký Netflix 260k mỗi tháng'</i> để bắt đầu nhé!"
                ),
            }

        period_label = {"monthly": "tháng", "weekly": "tuần", "yearly": "năm"}
        lines = []
        for s in subs:
            period_str = period_label.get(s.period, "tháng")
            next_date = s.next_charge_date
            next_str = next_date.strftime("%d/%m/%Y") if next_date else "?"
            lines.append(
                f"🔄 <b>{s.name}</b> — "
                f"{s.amount:,.0f}đ/{period_str} "
                f"(kỳ tới: {next_str})"
            )

        return {
            "status": "success",
            "response_text": "📋 <b>Phí định kỳ đang theo dõi:</b>\n\n" + "\n".join(lines),
        }

    async def _handle_query_subscription(self, payload: dict) -> dict:
        """Return payment status for a single named subscription."""
        from zoneinfo import ZoneInfo
        user_id = payload.get("user_id")
        merchant_name = payload.get("merchant_name")
        if not user_id or not merchant_name:
            return {"status": "error", "response_text": "Cho Mai biết tên dịch vụ muốn kiểm tra nha!"}

        sub = await self._subscription_repo.find_by_merchant(user_id, merchant_name)
        if not sub:
            return {
                "status": "success",
                "response_text": (
                    f"Mai không thấy đăng ký nào cho <b>{merchant_name}</b>. "
                    "Nhắn <i>'đăng ký Netflix 260k mỗi tháng'</i> để thêm nhé!"
                ),
            }

        from src.core.config import settings as _settings
        _tz_name = payload.get("user_timezone") or _settings.business_timezone
        local_tz = ZoneInfo(_tz_name)
        now_local = datetime.now(UTC).astimezone(local_tz)
        period_label = {"monthly": "tháng", "weekly": "tuần", "yearly": "năm"}
        period_str = period_label.get(sub.period, "tháng")

        # Determine whether this period has been paid.
        # A charge was recorded (last_charged_at is set) AND next_charge_date is still in the
        # future means mark_charged already advanced the date — i.e. the current cycle is paid.
        # This correctly handles cross-month charges (e.g. charged Apr 30, checked May 1).
        last_charged = sub.last_charged_at
        paid_this_period = False
        last_str = "Chưa có lần nào"
        if last_charged:
            if last_charged.tzinfo is None:
                last_charged = last_charged.replace(tzinfo=UTC)
            last_local = last_charged.astimezone(local_tz)
            last_str = last_local.strftime("%d/%m/%Y")

        ncd_for_check = sub.next_charge_date
        if ncd_for_check and ncd_for_check.tzinfo is None:
            ncd_for_check = ncd_for_check.replace(tzinfo=UTC)
        paid_this_period = last_charged is not None and ncd_for_check is not None and ncd_for_check > datetime.now(UTC)

        # Next charge display info (reuse the tz-aware ncd_for_check already computed above)
        ncd = ncd_for_check
        ncd_local = ncd.astimezone(local_tz) if ncd else None
        next_str = ncd_local.strftime("%d/%m/%Y") if ncd_local else "?"
        due_days = int((ncd - datetime.now(UTC)).total_seconds() / 86400) if ncd else None

        if paid_this_period:
            due_text = f"Kỳ tiếp: <b>{next_str}</b>"
            if due_days is not None:
                due_text += f" (còn {due_days} ngày)" if due_days >= 0 else f" (quá hạn {abs(due_days)} ngày rồi!)"
            text = (
                f"✅ <b>{sub.name}</b> — {sub.amount:,.0f}đ/{period_str}\n"
                f"Đã thanh toán: {last_str}\n"
                f"{due_text}"
            )
        else:
            if due_days is not None and due_days < 0:
                due_text = f"⚠️ Quá hạn {abs(due_days)} ngày (ngày hẹn: {next_str})"
            elif due_days is not None and due_days <= 3:
                due_text = f"⏰ Sắp đến hạn: <b>{next_str}</b> (còn {due_days} ngày)"
            else:
                due_text = f"Kỳ tới: <b>{next_str}</b>" + (f" (còn {due_days} ngày)" if due_days is not None else "")
            text = (
                f"🔄 <b>{sub.name}</b> — {sub.amount:,.0f}đ/{period_str}\n"
                f"Chưa thanh toán kỳ này\n"
                f"Lần cuối: {last_str}\n"
                f"{due_text}"
            )

        return {"status": "success", "response_text": text}

    async def _handle_mark_subscription_paid(self, payload: dict) -> dict:
        """Manually mark a subscription as paid for the current period."""
        user_id = payload.get("user_id")
        merchant_name = payload.get("merchant_name")

        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}
        if not merchant_name:
            return {
                "status": "error",
                "response_text": (
                    "Mai cần biết tên dịch vụ nào nha. "
                    "Ví dụ: <i>'Netflix đã trả rồi'</i>."
                ),
            }

        sub = await self._subscription_repo.find_by_merchant(user_id, merchant_name)
        if not sub:
            return {
                "status": "error",
                "response_text": (
                    f"Mai không tìm thấy đăng ký nào cho <b>{merchant_name}</b>. "
                    "Bạn đã đăng ký theo dõi chưa nhỉ?"
                ),
            }

        sub_id = str(sub.id)

        from src.db.repositories.subscription_repo import _advance_date
        from zoneinfo import ZoneInfo as _ZoneInfo
        from src.core.config import settings as _settings
        _tz_name = payload.get("user_timezone") or _settings.business_timezone
        _user_tz = _ZoneInfo(_tz_name)

        paid_date_raw = payload.get("subscription_paid_date")
        charged_at = datetime.now(UTC)
        if paid_date_raw:
            try:
                parsed = datetime.fromisoformat(paid_date_raw)
                # Gemini returns dates in the user's local time (no tz suffix) — treat as user midnight
                charged_at = parsed.replace(tzinfo=_user_tz).astimezone(UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
            except (ValueError, TypeError):
                pass

        await self._subscription_repo.mark_charged(sub_id, user_id, charged_at, user_timezone=_tz_name)

        next_date_advanced = _advance_date(charged_at, sub.period, sub.anchor_day, timezone=_tz_name)
        ncd_local = next_date_advanced.astimezone(_user_tz) if next_date_advanced else None
        next_str = ncd_local.strftime("%d/%m/%Y") if ncd_local else "?"

        logger.info("Subscription '%s' manually marked paid by user %s", merchant_name, user_id)
        return {
            "status": "success",
            "response_text": (
                f"Đã đánh dấu <b>{sub.name}</b> đã thanh toán kỳ này! "
                f"Kỳ tới: <b>{next_str}</b> 🔄"
            ),
        }

    async def _handle_cancel_subscription(self, payload: dict) -> dict:
        """Mark a subscription inactive. Past transactions remain linked and trackable."""
        user_id = payload.get("user_id")
        merchant_name = payload.get("merchant_name")

        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}
        if not merchant_name:
            return {
                "status": "error",
                "response_text": "Mai cần biết tên dịch vụ muốn huỷ nha. Ví dụ: <i>'huỷ Netflix'</i>.",
            }

        sub = await self._subscription_repo.find_by_merchant(user_id, merchant_name)
        if not sub:
            return {
                "status": "error",
                "response_text": (
                    f"Mai không tìm thấy đăng ký nào cho <b>{merchant_name}</b>. "
                    "Bạn đã đăng ký theo dõi chưa nhỉ?"
                ),
            }

        sub_id = str(sub.id)
        await self._subscription_repo.deactivate(sub_id, user_id, reason="manual")
        logger.info("Subscription '%s' cancelled by user %s", merchant_name, user_id)
        return {
            "status": "success",
            "response_text": (
                f"Đã huỷ theo dõi <b>{sub.name}</b>. "
                "Các giao dịch trước vẫn được lưu lại đầy đủ nhé."
            ),
        }

    async def _handle_update_subscription(self, payload: dict) -> dict:
        """Deactivate the old subscription and create a new one (marks old as 'replaced').

        All future charges will be linked to the new subscription.
        Past transactions remain linked to the old subscription_id for history.
        """
        from datetime import timedelta

        user_id = payload.get("user_id")
        merchant_name = payload.get("merchant_name")
        new_amount = payload.get("new_amount")
        new_period = payload.get("new_period")
        new_next_date_raw = payload.get("new_next_date")

        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}
        if not merchant_name or not new_amount:
            return {
                "status": "error",
                "response_text": (
                    "Mai cần biết tên dịch vụ và giá mới nha. "
                    "Ví dụ: <i>'Netflix tăng giá lên 300k từ tháng sau'</i>."
                ),
            }

        old_sub = await self._subscription_repo.find_by_merchant(user_id, merchant_name)
        if not old_sub:
            return {
                "status": "error",
                "response_text": (
                    f"Mai không tìm thấy đăng ký nào cho <b>{merchant_name}</b>. "
                    "Bạn đã đăng ký theo dõi chưa nhỉ?"
                ),
            }

        old_sub_id = str(old_sub.id)
        now = datetime.now(UTC)
        await self._subscription_repo.deactivate(old_sub_id, user_id, reason="replaced", cancelled_at=now)

        period = new_period or old_sub.period
        next_charge: datetime | None = None
        if new_next_date_raw:
            try:
                next_charge = datetime.fromisoformat(new_next_date_raw)
            except (ValueError, TypeError):
                pass
        if not next_charge:
            from dateutil.relativedelta import relativedelta as _rd
            _periods = {"weekly": dict(weeks=1), "yearly": dict(years=1)}
            next_charge = now + (_rd(**_periods[period]) if period in _periods else _rd(months=1))

        new_sub = SubscriptionDocument(
            user_id=user_id,
            name=old_sub.name or merchant_name,
            merchant_name=old_sub.merchant_name or merchant_name,
            amount=float(new_amount),
            period=period,
            next_charge_date=next_charge,
            anchor_day=next_charge.day,
            source=old_sub.source or "manual",
            replaces_id=old_sub_id,
        )
        new_sub_id = await self._subscription_repo.insert(new_sub)
        logger.info(
            "Subscription '%s' updated: old=%s new=%s", merchant_name, old_sub_id, new_sub_id
        )

        period_label = {"monthly": "tháng", "weekly": "tuần", "yearly": "năm"}.get(period, period)
        next_str = next_charge.strftime("%d/%m/%Y")
        return {
            "status": "success",
            "subscription_id": new_sub_id,
            "response_text": (
                f"Đã cập nhật <b>{new_sub.name}</b>: "
                f"<b>{float(new_amount):,.0f} VND/{period_label}</b>. "
                f"Kỳ tới: <b>{next_str}</b> 🔄\n"
                "Lịch sử giao dịch cũ vẫn được giữ nguyên nhé."
            ),
        }

    async def _check_subscription_match(
        self,
        user_id: str,
        merchant_name: str,
        amount: float,
        charged_at: datetime,
        chat_id: str,
        transaction_id: str | None = None,
    ) -> None:
        """After storing a transaction, check if it matches a subscription.

        - Registered subscription → mark paid, advance next_charge_date,
          and link the transaction to the subscription via subscription_id.
        - Unregistered but recurring pattern (2+ prior charges same merchant,
          similar amount, ~monthly interval) → ask user to register.
        """
        sub = await self._subscription_repo.find_by_merchant(user_id, merchant_name)
        if sub:
            sub_id = str(sub.id)
            await self._subscription_repo.mark_charged(sub_id, user_id, charged_at)
            if transaction_id:
                await self._transaction_repo.set_subscription_id(transaction_id, sub_id)
            logger.info(
                "Subscription '%s' marked charged for user %s", merchant_name, user_id
            )
            return

        # Check for unregistered recurring pattern
        history = await self._transaction_repo.find_by_merchant(
            user_id, merchant_name, limit=5
        )
        if self._is_recurring_pattern(history, amount):
            detected_period = self._detect_subscription_period(history)
            period_label = {"weekly": "tuần", "monthly": "tháng", "yearly": "năm"}.get(
                detected_period, "tháng"
            )
            # Encode merchant and amount in callback_data using | separator
            safe_merchant = merchant_name.replace("|", "_")
            keyboard = [[{
                "text": "✅ Đăng ký theo dõi",
                "callback_data": f"sub_reg|{safe_merchant}|{int(amount)}|{detected_period}",
            }]]
            if self._telegram:
                await self._telegram.send_message_with_keyboard(
                    chat_id=chat_id,
                    text=(
                        f"🔄 <b>{merchant_name}</b> có vẻ là phí định kỳ "
                        f"({amount:,.0f}đ/{period_label}). "
                        "Bấm nút để đăng ký và Mai sẽ nhắc trước kỳ trừ tiền!"
                    ),
                    keyboard=keyboard,
                )
            logger.info(
                "Recurring pattern detected for '%s' user=%s — prompted user",
                merchant_name,
                user_id,
            )

    @staticmethod
    def _detect_subscription_period(history: list[TransactionDocument]) -> str:
        """Infer weekly / monthly / yearly from average interval between outflow charges."""
        dates = sorted(
            h.transaction_time for h in history
            if h.direction == "outflow" and h.transaction_time
        )
        if len(dates) < 2:
            return "monthly"
        intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        avg_days = sum(intervals) / len(intervals)
        if avg_days <= 14:
            return "weekly"
        if avg_days <= 180:
            return "monthly"
        return "yearly"

    @staticmethod
    def _is_recurring_pattern(history: list[TransactionDocument], current_amount: float) -> bool:
        """Return True when history shows ≥2 prior outflow charges with similar
        amounts (~±30%) and intervals of 7–40 days (weekly/monthly cadence).
        """
        if len(history) < 2:
            return False

        outflow = [
            h for h in history
            if h.direction == "outflow" and h.amount > 0
        ]
        if len(outflow) < 2:
            return False

        # Amount similarity: all within ±30% of current_amount
        lo, hi = current_amount * 0.7, current_amount * 1.3
        similar = [h for h in outflow if lo <= h.amount <= hi]
        if len(similar) < 2:
            return False

        # Interval check: gaps between sorted charge dates 7–40 days
        dates = sorted(
            h.transaction_time for h in similar if h.transaction_time
        )
        if len(dates) < 2:
            return False

        for i in range(1, len(dates)):
            delta = (dates[i] - dates[i - 1]).days
            if not (7 <= delta <= 40):
                return False

        return True

    async def _handle_delete_transaction(self, payload: dict) -> dict:
        """Delete a transaction by id. Resolves 'last' reference from Redis session."""
        user_id = payload.get("user_id", "")
        transaction_id = payload.get("transaction_id")
        reference = payload.get("reference", "last")

        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}

        if not transaction_id and reference == "last":
            transaction_id = await self._redis.get_last_transaction(user_id)

        if not transaction_id:
            return {
                "status": "error",
                "response_text": (
                    "Không tìm thấy giao dịch để xoá. "
                    "Bạn thử bấm nút <b>🗑️ Xoá</b> trên tin nhắn giao dịch nhé!"
                ),
            }

        from bson import ObjectId
        from bson.errors import InvalidId
        try:
            ObjectId(transaction_id)
        except (InvalidId, TypeError):
            return {"status": "error", "response_text": "ID giao dịch không hợp lệ."}

        original = await self._transaction_repo.find_by_id(transaction_id)
        if not original or original.user_id != user_id:
            logger.warning("Delete ownership violation: user=%s txn=%s", user_id, transaction_id)
            return {"status": "error", "response_text": "Không tìm thấy giao dịch."}

        if original.locked:
            return {
                "status": "locked",
                "response_text": "🔒 Giao dịch này đã được xác nhận, không thể xoá.",
            }

        deleted = await self._transaction_repo.delete(transaction_id, user_id)
        if not deleted:
            return {"status": "error", "response_text": "Không xoá được giao dịch."}

        await self._redis.invalidate_dashboard_cache(user_id)
        amount = original.amount
        icon = "➕" if original.direction == "inflow" else "➖"
        merchant = original.merchant_name or ""
        summary = f"{icon} {amount:,.0f}đ"
        if merchant:
            summary += f" | {merchant}"
        logger.info("Transaction deleted: txn=%s user=%s", transaction_id, user_id)
        return {
            "status": "deleted",
            "response_text": f"🗑️ Đã xoá giao dịch <b>{summary}</b>.",
        }

    async def _handle_correction(self, payload: dict) -> dict:
        """Apply a user correction: update the transaction, invalidate
        the merchant cache, and record the override so tagging learns.
        """
        user_id = payload.get("user_id")
        transaction_id = payload.get("transaction_id")
        new_category = payload.get("new_category")

        if not user_id or not transaction_id or not new_category:
            return {
                "status": "error",
                "response_text": "Thiếu thông tin để cập nhật giao dịch.",
            }

        original = await self._transaction_repo.find_by_id(transaction_id)
        if not original:
            return {
                "status": "error",
                "response_text": "Không tìm thấy giao dịch để sửa.",
            }

        if original.user_id != user_id:
            logger.warning(
                "Correction ownership violation: user=%s attempted to update txn=%s owned by %s",
                user_id,
                transaction_id,
                original.user_id,
            )
            return {
                "status": "error",
                "response_text": "Không tìm thấy giao dịch để sửa.",
            }

        old_category = original.category_id
        merchant_name = original.merchant_name

        updated = await self._transaction_repo.update_category(
            transaction_id, new_category, user_id
        )
        if not updated:
            return {
                "status": "error",
                "response_text": "Không cập nhật được giao dịch.",
            }

        # Invalidate Redis: merchant cache (so next tagging re-evaluates) and
        # dashboard cache (so mobile app sees updated category immediately).
        if merchant_name:
            await self._redis.delete_merchant_cache(merchant_name, user_id)
        await self._redis.invalidate_dashboard_cache(user_id)

        # Record the correction for audit + future high-weight overrides.
        await self._correction_repo.insert(
            CorrectionDocument(
                user_id=user_id,
                transaction_id=transaction_id,
                merchant_name=merchant_name,
                old_category=old_category,
                new_category=new_category,
            )
        )
        logger.info(
            "Correction applied: txn=%s merchant=%s %s -> %s",
            transaction_id,
            merchant_name,
            old_category,
            new_category,
        )

        return {
            "status": "success",
            "transaction_id": transaction_id,
            "response_text": (
                f"Đã cập nhật danh mục thành <b>{new_category}</b> nhé! "
                "Mai sẽ nhớ cho lần sau."
            ),
        }

    async def handle_subscription_register(self, payload: dict) -> dict:
        """Public entry point for one-tap subscription registration from inline buttons."""
        return await self._handle_set_subscription(payload)

    async def _update_goal_progress(self, user_id: str, inflow_amount: float) -> None:
        """Add an inflow amount to all active goals and mark achieved ones."""
        try:
            goals = await self._goal_repo.find_by_user(user_id, status="active")
            for goal in goals:
                goal_id = str(goal.id)
                new_amount = (goal.current_amount or 0.0) + inflow_amount
                await self._goal_repo.update_progress(goal_id, user_id, new_amount)
                if new_amount >= goal.target_amount:
                    await self._goal_repo.set_status(goal_id, user_id, "achieved")
                    logger.info("Goal %s achieved for user %s", goal_id, user_id)
        except Exception:
            logger.exception("Failed to update goal progress for user %s", user_id)

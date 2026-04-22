"""
Agent Orchestrator — Think-First routing pattern.

Classifies incoming events and dispatches to the appropriate agent pipeline.
"""

import logging
from datetime import UTC, datetime
from typing import Literal

from src.agents.analytics import AnalyticsAgent
from src.agents.conversational import ConversationalAgent
from src.agents.ingestion import IngestionAgent
from src.agents.reporting import ReportingAgent
from src.agents.tagging import TaggingAgent
from src.core.schemas import AnalysisRequest, ParsedTransaction, ReportRequest
from src.db.models.transaction import TransactionDocument
from src.db.repositories.transaction_repo import TransactionRepository
from src.services.gemini import GeminiService
from src.services.redis_client import RedisClient

logger = logging.getLogger(__name__)

EventType = Literal[
    "notification", "chat", "voice", "scheduled", "report", "analysis", "correction"
]


class Orchestrator:
    """Central orchestrator implementing Think-First routing."""

    def __init__(
        self,
        gemini: GeminiService,
        redis: RedisClient,
        transaction_repo: TransactionRepository,
    ) -> None:
        self._gemini = gemini
        self._redis = redis
        self._transaction_repo = transaction_repo

        # Agents (initialized with shared services)
        self._ingestion = IngestionAgent(gemini)
        self._conversational = ConversationalAgent(gemini)
        self._reporting = ReportingAgent(gemini)
        self._analytics = AnalyticsAgent(gemini)
        self._tagging = TaggingAgent(
            gemini, redis, transaction_repo=transaction_repo
        )

    async def classify_event(self, event: dict) -> EventType:
        """Classify an incoming event to determine the agent pipeline."""
        source = event.get("source", "")

        if source in ("macrodroid", "tasker", "ios_shortcut"):
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
            case _:
                logger.warning("Unknown event type: %s", event_type)
                return {"status": "unknown_event"}

    async def _handle_notification(self, payload: dict) -> dict:
        """Pipeline: Ingestion Agent -> Tagging Agent -> Store."""
        raw_text = payload.get("notification_text", "")
        user_id = payload.get("user_id", "")

        if not raw_text:
            return {"status": "empty_notification"}

        # Step 1: Parse with Ingestion Agent
        parsed: ParsedTransaction = await self._ingestion.parse(raw_text)

        if not parsed.is_transaction:
            logger.info("Non-transaction notification, skipping")
            return {"status": "not_transaction", "parsed": parsed.model_dump()}

        # Step 2: Enrich with Tagging Agent
        tags_result = await self._tagging.enrich(
            transaction=parsed,
            user_id=user_id,
        )

        # Step 3: Store in MongoDB
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
            ai_metadata={
                "bank_name": parsed.bank_name,
                "tagging_result": tags_result,
            },
        )

        txn_id = await self._transaction_repo.insert(txn_doc)
        logger.info("Transaction stored: %s", txn_id)

        return {
            "status": "stored",
            "transaction_id": txn_id,
            "parsed": parsed.model_dump(),
        }

    async def _handle_chat(self, payload: dict) -> dict:
        """Conversational Agent -> Tagging Agent -> Store."""
        raw_text = payload.get("message", "")
        user_id = payload.get("user_id", "")
        chat_id = payload.get("chat_id", "")

        if not raw_text:
            return {"status": "empty_message"}

        # Step 1: Parse intent
        intent_result = await self._conversational.process_message(
            message=raw_text, chat_id=chat_id
        )

        if intent_result.intent == "request_report":
            return await self._handle_report({
                "user_id": user_id, 
                "period": intent_result.payload.get("period", "today")
            })

        if intent_result.intent == "request_analysis":
            return await self._handle_analysis({
                "user_id": user_id,
                "analysis_type": intent_result.payload.get("analysis_type", "compare"),
                "period": intent_result.payload.get("period", "this_week"),
                "compare_period": intent_result.payload.get("compare_period"),
                "category_filter": intent_result.payload.get("category_filter"),
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
            txn_time = datetime.fromisoformat(p_data["transaction_time"]) if p_data.get("transaction_time") else datetime.now(UTC)
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

        return {
            "status": "stored",
            "transaction_id": txn_id,
            "parsed": parsed.model_dump(),
            "response_text": intent_result.response_text or "Đã ghi nhận giao dịch của bạn!",
        }

    async def _handle_scheduled(self, payload: dict) -> dict:
        """Behavioral Agent -> Nudge."""
        # TODO: Implement Behavioral pipeline (Phase 3)
        return {"status": "not_implemented"}

    async def _handle_report(self, payload: dict) -> dict:
        """Reporting Agent -> Dashboard."""
        from src.core.utils import get_date_range

        user_id = payload.get("user_id")
        period_str = payload.get("period", "today")

        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}

        start_date, end_date = get_date_range(period_str)
        if not start_date:
            return {
                "status": "error",
                "response_text": f"Mai chưa hỗ trợ mốc thời gian '{period_str}' đâu ạ. Bạn thử 'hôm nay', 'tuần này' hoặc 'tháng này' nhé!"
            }

        transactions = await self._transaction_repo.find_by_user(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=100
        )

        request = ReportRequest(
            user_id=user_id,
            report_type="summary",
            period=period_str
        )

        result = await self._reporting.generate(request, transactions)
        return {
            "status": result["status"],
            "response_text": result["report_text"]
        }

    async def _handle_analysis(self, payload: dict) -> dict:
        """Analytics Agent -> Complex analysis."""
        from src.core.utils import get_comparison_ranges, get_date_range

        user_id = payload.get("user_id")
        analysis_type = payload.get("analysis_type", "compare")
        period_str = payload.get("period", "this_week")
        compare_period = payload.get("compare_period")
        category_filter = payload.get("category_filter")

        if not user_id:
            return {"status": "error", "response_text": "Không tìm thấy user_id."}

        # Fetch current period data
        if analysis_type == "compare":
            (cur_start, cur_end), (comp_start, comp_end) = get_comparison_ranges(
                period_str, compare_period
            )
            
            if not cur_start or not comp_start:
                return {
                    "status": "error",
                    "response_text": "Mai chưa hỗ trợ mốc thời gian này để so sánh đâu ạ."
                }
                
            current_txns = await self._transaction_repo.find_by_user(
                user_id=user_id, start_date=cur_start, end_date=cur_end, limit=200
            )
            comparison_txns = await self._transaction_repo.find_by_user(
                user_id=user_id, start_date=comp_start, end_date=comp_end, limit=200
            )
        else:
            # Trend: fetch current period only
            start_date, end_date = get_date_range(period_str)
            if not start_date:
                return {
                    "status": "error",
                    "response_text": f"Mai chưa hỗ trợ mốc thời gian '{period_str}' để phân tích xu hướng."
                }
                
            current_txns = await self._transaction_repo.find_by_user(
                user_id=user_id, start_date=start_date, end_date=end_date, limit=200
            )
            comparison_txns = None

        request = AnalysisRequest(
            user_id=user_id,
            analysis_type=analysis_type,
            period=period_str,
            compare_period=compare_period,
            category_filter=category_filter,
        )

        result = await self._analytics.analyze(request, current_txns, comparison_txns)
        return {
            "status": result["status"],
            "response_text": result["report_text"],
        }

    async def _handle_correction(self, payload: dict) -> dict:
        """Direct DB update + learn from correction."""
        # TODO: Implement correction pipeline (Phase 3)
        return {"status": "not_implemented"}

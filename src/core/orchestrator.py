"""
Agent Orchestrator — Think-First routing pattern.

Classifies incoming events and dispatches to the appropriate agent pipeline.
"""

import logging
from datetime import UTC, datetime
from typing import Literal

from src.agents.ingestion import IngestionAgent
from src.agents.tagging import TaggingAgent
from src.core.schemas import ParsedTransaction
from src.db.models.transaction import TransactionDocument
from src.db.repositories.transaction_repo import TransactionRepository
from src.services.gemini import GeminiService
from src.services.redis_client import RedisClient

logger = logging.getLogger(__name__)

EventType = Literal[
    "notification", "chat", "voice", "scheduled", "report", "correction"
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
        self._tagging = TaggingAgent(gemini, redis)

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
        # TODO: Implement Conversational -> Tagging pipeline (Phase 2)
        return {"status": "not_implemented"}

    async def _handle_scheduled(self, payload: dict) -> dict:
        """Behavioral Agent -> Nudge."""
        # TODO: Implement Behavioral pipeline (Phase 3)
        return {"status": "not_implemented"}

    async def _handle_report(self, payload: dict) -> dict:
        """Reporting Agent -> Dashboard."""
        # TODO: Implement Reporting pipeline (Phase 3)
        return {"status": "not_implemented"}

    async def _handle_correction(self, payload: dict) -> dict:
        """Direct DB update + learn from correction."""
        # TODO: Implement correction pipeline (Phase 3)
        return {"status": "not_implemented"}

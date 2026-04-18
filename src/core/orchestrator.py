"""
Agent Orchestrator — Think-First routing pattern.

Classifies incoming events and dispatches to the appropriate agent pipeline.
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

EventType = Literal[
    "notification", "chat", "voice", "scheduled", "report", "correction"
]


class Orchestrator:
    """Central orchestrator implementing Think-First routing."""

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
        """Ingestion Agent -> Tagging Agent -> Store."""
        # TODO: Implement Ingestion -> Tagging pipeline
        return {"status": "not_implemented"}

    async def _handle_chat(self, payload: dict) -> dict:
        """Conversational Agent -> Tagging Agent -> Store."""
        # TODO: Implement Conversational -> Tagging pipeline
        return {"status": "not_implemented"}

    async def _handle_scheduled(self, payload: dict) -> dict:
        """Behavioral Agent -> Nudge."""
        # TODO: Implement Behavioral pipeline
        return {"status": "not_implemented"}

    async def _handle_report(self, payload: dict) -> dict:
        """Reporting Agent -> Dashboard."""
        # TODO: Implement Reporting pipeline
        return {"status": "not_implemented"}

    async def _handle_correction(self, payload: dict) -> dict:
        """Direct DB update + learn from correction."""
        # TODO: Implement correction pipeline
        return {"status": "not_implemented"}

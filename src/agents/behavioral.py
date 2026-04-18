"""
Behavioral Agent (The Psychologist)

Analyzes spending patterns and generates personalized nudge messages.
Uses user profile (occupation, hobbies) for relatable analogies.
Uses Gemini 2.5 Pro. Triggered by scheduled cron.
"""

import logging

from src.core.schemas import NudgeRequest, NudgeResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a behavioral finance analyst for a Vietnamese user.
Given their spending data and personal profile, generate a short,
personalized nudge message in Vietnamese. Use their hobbies and interests
to create relatable analogies. Be encouraging, not judgmental.
Max 2 sentences.
"""

MAX_NUDGES_PER_DAY = 2
QUIET_HOURS = (22, 7)  # 22:00 - 07:00


class BehavioralAgent:
    """Analyzes spending behavior and generates nudges."""

    async def analyze(self, request: NudgeRequest) -> NudgeResult:
        """Run behavioral analysis and generate a nudge if warranted."""
        # TODO: Query transactions, compare patterns, generate nudge via Gemini Pro
        logger.info(
            "Analyzing behavior for user_id=%s, type=%s",
            request.user_id,
            request.nudge_type,
        )
        return NudgeResult(
            nudge_id="",
            message="",
            sent=False,
            blocked_reason="not_implemented",
        )

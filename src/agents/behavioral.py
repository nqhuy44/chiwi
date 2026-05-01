"""
Behavioral Agent (The Psychologist)

Generates personalized nudge messages from a trigger payload + the user's
personalization profile (occupation, hobbies, tone). Trigger detection
itself (Phase 3.2) is upstream — this agent renders the message, applies
anti-spam rules, sends it, and persists the audit trail.

Profiles are loaded from `config/user_profiles.json` via `src.core.profiles`
so the user can tune personalization without code changes.

Uses Gemini 2.5 Pro.
"""

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from src.agents.prompts import load_prompt
from src.core.config import settings
from src.core.profiles import get_profile
from src.core.schemas import NudgeRequest, NudgeResult, UserProfile
from src.core.toon import to_toon
from src.db.models.nudge import NudgeDocument
from src.db.repositories.nudge_repo import NudgeRepository
from src.services.gemini import GeminiService
from src.services.telegram import TelegramService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = load_prompt("behavioral")


class BehavioralAgent:
    """Renders and delivers behavioral nudges."""

    def __init__(
        self,
        gemini: GeminiService,
        telegram: TelegramService | None,
        nudge_repo: NudgeRepository,
    ) -> None:
        self._gemini = gemini
        self._telegram = telegram
        self._nudges = nudge_repo

    async def analyze(self, request: NudgeRequest) -> NudgeResult:
        """Render and (if allowed) send a single nudge."""
        logger.info(
            "Behavioral analyze user_id=%s type=%s",
            request.user_id,
            request.nudge_type,
        )

        profile = await get_profile(request.user_id)

        if profile.nudge_frequency == "off":
            return self._blocked("user_disabled_nudges")

        is_manual = request.trigger_data.get("source") == "telegram"

        # Check daily limits and anti-spam (unless manual trigger)
        if not is_manual:
            blocked_reason = await self._spam_check(request)
            if blocked_reason:
                return self._blocked(blocked_reason)

        # Generate message via Gemini
        prompt = self._build_user_msg(request, profile)
        result = await self._gemini.call_flash(SYSTEM_PROMPT, prompt)
        
        message = (result.get("message") or "").strip()
        should_send = result.get("should_send", True)
        llm_blocked_reason = result.get("blocked_reason")

        if not should_send:
            return self._blocked(llm_blocked_reason or "llm_skipped")

        if not message:
            return self._blocked("empty_message")

        # Build Title based on type
        title_map = {
            "spending_spike": "🔥 Cảnh báo chi tiêu!",
            "budget_warning": "⚠️ Sắp chạm trần ngân sách",
            "goal_milestone": "🎯 Chúc mừng bạn!",
            "subscription_reminder": "🔄 Nhắc lịch thanh toán",
            "impulse_check": "🤔 Suy nghĩ kỹ nhé",
            "saving_streak": "⭐ Phong độ tuyệt vời",
            "daily_analysis": "☀️ Phân tích chi tiêu hôm qua"
        }
        title = title_map.get(request.nudge_type, "ChiWi Insight")

        # Send via Telegram if available
        sent_tg = False
        chat_id = profile.extras.get("telegram_chat_id")
        if self._telegram and chat_id:
            send_result = await self._telegram.send_silent_message(
                chat_id=chat_id, text=message
            )
            sent_tg = bool(send_result)

        # Persist to DB for Mobile Notification History
        # All nudges are visible on Mobile regardless of TG delivery status
        doc = NudgeDocument(
            user_id=request.user_id,
            nudge_type=request.nudge_type,
            title=title,
            message=message,
            channel="both" if sent_tg else "android",
            metadata=request.trigger_data.get("metadata", {}),
            trigger_reason=str(request.trigger_data.get("reason", ""))
        )
        nudge_id = await self._nudges.insert(doc)

        return NudgeResult(
            nudge_id=nudge_id,
            message=message,
            sent=sent_tg,
        )

    # -- internals -------------------------------------------------------

    @staticmethod
    def _blocked(reason: str) -> NudgeResult:
        return NudgeResult(nudge_id="", message="", sent=False, blocked_reason=reason)

    async def _spam_check(self, request: NudgeRequest) -> str | None:
        """Return a blocked-reason string if the nudge should be suppressed."""
        tz = ZoneInfo(settings.business_timezone)
        local_now = datetime.now(tz)
        hour = local_now.hour
        start = settings.nudge_quiet_hour_start
        end = settings.nudge_quiet_hour_end
        # Quiet window crosses midnight (e.g. 22 → 7).
        in_quiet = (
            (hour >= start) or (hour < end) if start > end else (start <= hour < end)
        )
        if in_quiet:
            return "quiet_hours"

        local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        midnight_utc = local_midnight.astimezone(UTC).replace(tzinfo=None)
        count = await self._nudges.count_since(request.user_id, midnight_utc)
        if count >= settings.nudge_max_per_day:
            return "daily_limit"

        if await self._nudges.has_recent_type(
            request.user_id, request.nudge_type, hours=24
        ):
            return "duplicate_type_24h"

        return None

    @staticmethod
    def _build_user_msg(request: NudgeRequest, profile: UserProfile) -> str:
        payload: dict = {
            "nudge_type": request.nudge_type,
            "profile": profile.model_dump(exclude_defaults=False),
            "trigger": request.trigger_data,
        }
        return to_toon(payload)

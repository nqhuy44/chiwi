"""
Reporting Agent (The Strategist)

Generates periodic financial summaries with narrative insights.
Serves data to Telegram Mini App dashboard.
Uses Gemini 2.5 Flash.
"""

import logging

from src.agents.prompts import load_prompt
from src.api.middleware.pii_mask import mask_pii
from src.core.config import settings
from src.core.schemas import ReportRequest
from src.core.toon import to_toon
from src.services.gemini import GeminiService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = load_prompt("reporting")


class ReportingAgent:
    """Generates financial reports and insights."""

    def __init__(self, gemini: GeminiService) -> None:
        self._gemini = gemini

    async def generate(
        self,
        request: ReportRequest,
        transactions: list[dict],
        user_timezone: str = "Asia/Ho_Chi_Minh",
        profile: UserProfile | None = None,
    ) -> dict:
        """Generate a financial report for the given period."""
        from src.core.profiles import build_personalized_prompt, UserProfile
        
        logger.info(
            "Generating %s report for user_id=%s, period=%s with %d transactions",
            request.report_type,
            request.user_id,
            request.period,
            len(transactions),
        )

        total_outflow = sum(
            t.get("amount", 0) for t in transactions if t.get("direction") == "outflow"
        )
        total_inflow = sum(
            t.get("amount", 0) for t in transactions if t.get("direction") == "inflow"
        )

        payload: dict = {
            "report_type": request.report_type,
            "period": request.period,
            "user_timezone": user_timezone,
            "total_inflow": round(total_inflow),
            "total_outflow": round(total_outflow),
        }
        if transactions:
            payload["transactions"] = [
                {
                    "dir": t.get("direction", "outflow"),
                    "amount": round(t.get("amount", 0)),
                    "cat": t.get("category_id", "Khác"),
                    "merchant": t.get("merchant_name", "") or "",
                }
                for t in transactions
            ]

        raw_msg = to_toon(payload)
        user_msg = mask_pii(raw_msg) if settings.pii_mask_enabled else raw_msg

        prompt = build_personalized_prompt(
            template=SYSTEM_PROMPT,
            profile=profile or UserProfile()
        )

        result = await self._gemini.call_flash(prompt, user_msg)
        report_text = result.get("report_text", "Không thể tạo báo cáo lúc này.")

        return {
            "report_type": request.report_type,
            "period": request.period,
            "data": {
                "total_inflow": total_inflow,
                "total_outflow": total_outflow,
                "transaction_count": len(transactions),
            },
            "status": "success",
            "report_text": report_text,
        }

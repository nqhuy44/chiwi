"""
Reporting Agent (The Strategist)

Generates periodic financial summaries with narrative insights.
Serves data to Telegram Mini App dashboard.
Uses Gemini 2.5 Flash.
"""

import logging

from src.agents.prompts import load_prompt
from src.core.schemas import ReportRequest
from src.core.toon import to_toon
from src.services.gemini import GeminiService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = load_prompt("reporting")


class ReportingAgent:
    """Generates financial reports and insights."""

    def __init__(self, gemini: GeminiService) -> None:
        self._gemini = gemini

    async def generate(self, request: ReportRequest, transactions: list[dict]) -> dict:
        """Generate a financial report for the given period."""
        logger.info(
            "Generating %s report for user_id=%s, period=%s with %d transactions",
            request.report_type,
            request.user_id,
            request.period,
            len(transactions),
        )

        total_outflow = sum(t.get("amount", 0) for t in transactions if t.get("direction") == "outflow")
        total_inflow = sum(t.get("amount", 0) for t in transactions if t.get("direction") == "inflow")

        payload: dict = {
            "report_type": request.report_type,
            "period": request.period,
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

        user_msg = (
            to_toon(payload)
            + "\n\nHãy viết một báo cáo ngắn gọn, thân thiện bằng tiếng Việt."
            " Nếu không có giao dịch, hãy động viên nhẹ nhàng."
        )

        result = await self._gemini.call_flash(SYSTEM_PROMPT, user_msg)
        report_text = result.get("report_text", "Không thể tạo báo cáo lúc này.")

        return {
            "report_type": request.report_type,
            "period": request.period,
            "data": {
                "total_inflow": total_inflow,
                "total_outflow": total_outflow,
                "transaction_count": len(transactions)
            },
            "status": "success",
            "report_text": report_text,
        }

"""
Analytics Agent (The Analyst)

Handles complex financial analysis: period comparisons, trend detection,
category deep-dives, and anomaly identification.
Uses Gemini 2.5 Pro for reasoning-heavy workloads.
"""

import logging
from collections import defaultdict

from src.agents.prompts import load_prompt
from src.core.schemas import AnalysisRequest
from src.services.gemini import GeminiService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = load_prompt("analytics")


class AnalyticsAgent:
    """Performs complex financial analysis and comparisons."""

    def __init__(self, gemini: GeminiService) -> None:
        self._gemini = gemini

    async def analyze(
        self,
        request: AnalysisRequest,
        current_transactions: list[dict],
        comparison_transactions: list[dict] | None = None,
    ) -> dict:
        """Run the requested analysis and return a narrative result."""
        logger.info(
            "Running %s analysis for user_id=%s, period=%s",
            request.analysis_type,
            request.user_id,
            request.period,
        )

        current_summary = self._summarize_transactions(current_transactions)
        comparison_summary = (
            self._summarize_transactions(comparison_transactions)
            if comparison_transactions
            else None
        )

        user_msg = self._build_user_message(
            request, current_summary, comparison_summary
        )

        result = await self._gemini.call_pro(SYSTEM_PROMPT, user_msg)
        report_text = result.get("report_text", "Không thể phân tích dữ liệu lúc này.")

        return {
            "analysis_type": request.analysis_type,
            "period": request.period,
            "status": "success",
            "report_text": report_text,
        }

    def _summarize_transactions(self, transactions: list[dict]) -> dict:
        """Pre-aggregate transactions into a structured summary for LLM context."""
        total_outflow = 0.0
        total_inflow = 0.0
        by_category: dict[str, dict] = defaultdict(
            lambda: {"total": 0.0, "count": 0, "merchants": []}
        )

        for t in transactions:
            amt = t.get("amount", 0)
            direction = t.get("direction", "outflow")
            cat = t.get("category_id", "Khác")
            merchant = t.get("merchant_name", "")

            if direction == "outflow":
                total_outflow += amt
            else:
                total_inflow += amt

            by_category[cat]["total"] += amt
            by_category[cat]["count"] += 1
            if merchant and merchant not in by_category[cat]["merchants"]:
                by_category[cat]["merchants"].append(merchant)

        return {
            "total_outflow": total_outflow,
            "total_inflow": total_inflow,
            "transaction_count": len(transactions),
            "categories": dict(by_category),
        }

    def _build_user_message(
        self,
        request: AnalysisRequest,
        current: dict,
        comparison: dict | None,
    ) -> str:
        """Build the user message for the LLM based on analysis type."""
        lines = [
            f"Loại phân tích: {request.analysis_type}",
            f"Kỳ hiện tại: {request.period}",
            "",
            "=== KỲ HIỆN TẠI ===",
            f"Tổng chi: {current['total_outflow']:,.0f} VND",
            f"Tổng thu: {current['total_inflow']:,.0f} VND",
            f"Số giao dịch: {current['transaction_count']}",
            "",
        ]

        # Category breakdown for current period
        lines.append("Chi tiết theo danh mục (hiện tại):")
        for cat, data in sorted(
            current["categories"].items(),
            key=lambda x: x[1]["total"],
            reverse=True,
        ):
            merchants_str = ", ".join(data["merchants"][:3])
            lines.append(
                f"  - {cat}: {data['total']:,.0f} VND "
                f"({data['count']} giao dịch) [{merchants_str}]"
            )

        if comparison:
            lines.extend([
                "",
                f"=== KỲ SO SÁNH ({request.compare_period or 'trước đó'}) ===",
                f"Tổng chi: {comparison['total_outflow']:,.0f} VND",
                f"Tổng thu: {comparison['total_inflow']:,.0f} VND",
                f"Số giao dịch: {comparison['transaction_count']}",
                "",
            ])

            lines.append("Chi tiết theo danh mục (kỳ so sánh):")
            for cat, data in sorted(
                comparison["categories"].items(),
                key=lambda x: x[1]["total"],
                reverse=True,
            ):
                merchants_str = ", ".join(data["merchants"][:3])
                lines.append(
                    f"  - {cat}: {data['total']:,.0f} VND "
                    f"({data['count']} giao dịch) [{merchants_str}]"
                )

        lines.extend([
            "",
            "Hãy phân tích chi tiết, thân thiện bằng tiếng Việt.",
        ])

        if request.category_filter:
            lines.append(
                f"Tập trung vào danh mục: {request.category_filter}"
            )

        return "\n".join(lines)

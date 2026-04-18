"""
Reporting Agent (The Strategist)

Generates periodic financial summaries with narrative insights.
Serves data to Telegram Mini App dashboard.
Uses Gemini 2.5 Pro.
"""

import logging

from src.core.schemas import ReportRequest

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a financial reporting analyst for a Vietnamese user.
Given aggregated transaction data, generate a concise financial summary
in Vietnamese. Include: total income/expense, top categories, trends vs
previous period, and one actionable insight.
"""


class ReportingAgent:
    """Generates financial reports and insights."""

    async def generate(self, request: ReportRequest) -> dict:
        """Generate a financial report for the given period."""
        # TODO: Aggregate from MongoDB, generate narrative via Gemini Pro
        logger.info(
            "Generating %s report for user_id=%s, period=%s",
            request.report_type,
            request.user_id,
            request.period,
        )
        return {
            "report_type": request.report_type,
            "period": request.period,
            "data": {},
            "status": "not_implemented",
        }

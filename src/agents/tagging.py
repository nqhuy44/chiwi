"""
Context & Tagging Agent (The Classifier)

Maps merchants to categories and generates deep metadata tags.
Uses historical data for consistency and learns from user corrections.
Uses Gemini 2.5 Flash.
"""

import logging

from src.core.schemas import ParsedTransaction

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a transaction classifier for Vietnamese personal finance.
Given a parsed transaction with merchant name, assign:
1. A category from the predefined list
2. Relevant tags (temporal, behavioral, lifestyle)
Output JSON with fields: category_name, tags.
"""


class TaggingAgent:
    """Classifies transactions and generates metadata tags."""

    async def enrich(
        self,
        transaction: ParsedTransaction,
        user_id: str,
        historical_tags: dict | None = None,
    ) -> dict:
        """Enrich a parsed transaction with category and tags."""
        # TODO: Check merchant cache -> historical rules -> Gemini Flash
        logger.info(
            "Tagging transaction: merchant=%s", transaction.merchant_name
        )
        return {
            "category_name": "Uncategorized",
            "tags": [],
        }

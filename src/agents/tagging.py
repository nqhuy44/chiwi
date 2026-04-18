"""
Context & Tagging Agent (The Classifier)

Maps merchants to categories and generates deep metadata tags.
Uses historical data for consistency and learns from user corrections.
Uses Gemini 2.5 Flash.
"""

import logging

from src.core.schemas import ParsedTransaction
from src.services.gemini import GeminiService
from src.services.redis_client import RedisClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a transaction classifier for Vietnamese personal finance.
Given a parsed transaction with merchant name and amount, assign:
1. A category from this list: [
    "Ăn uống", "Cà phê / Trà sữa", "Di chuyển", "Mua sắm",
    "Giải trí", "Sức khỏe", "Giáo dục", "Hóa đơn & Tiện ích",
    "Chuyển khoản", "Thu nhập", "Tiết kiệm", "Đầu tư", "Khác"
]
2. Relevant tags (temporal, behavioral, lifestyle)

Output valid JSON only:
{"category_name": "...", "tags": ["...", "..."]}
"""


class TaggingAgent:
    """Classifies transactions and generates metadata tags."""

    def __init__(self, gemini: GeminiService, redis: RedisClient) -> None:
        self._gemini = gemini
        self._redis = redis

    async def enrich(
        self,
        transaction: ParsedTransaction,
        user_id: str,
        historical_tags: dict | None = None,
    ) -> dict:
        """Enrich a parsed transaction with category and tags.

        Priority: merchant cache -> Gemini Flash -> fallback.
        """
        merchant = transaction.merchant_name

        # Step 1: Check merchant cache in Redis
        if merchant:
            cached = await self._redis.get_merchant_cache(merchant)
            if cached:
                logger.info("Merchant cache hit: %s -> %s", merchant, cached)
                return {"category_name": cached, "tags": []}

        # Step 2: Call Gemini Flash for classification
        user_msg = (
            f"Merchant: {merchant or 'Unknown'}\n"
            f"Amount: {transaction.amount} {transaction.currency}\n"
            f"Direction: {transaction.direction}\n"
            f"Bank: {transaction.bank_name or 'Unknown'}"
        )
        result = await self._gemini.call_flash(SYSTEM_PROMPT, user_msg)

        category = result.get("category_name", "Khác")
        tags = result.get("tags", [])

        # Step 3: Cache the merchant -> category mapping
        if merchant and category != "Khác":
            await self._redis.set_merchant_cache(merchant, category)
            logger.info("Merchant cached: %s -> %s", merchant, category)

        return {"category_name": category, "tags": tags}

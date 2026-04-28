"""
Context & Tagging Agent (The Classifier)

Maps merchants to categories and generates deep metadata tags.
Uses historical data for consistency and learns from user corrections.
Uses Gemini 2.5 Flash.
"""

import json
import logging
import statistics
from collections import Counter

from src.agents.prompts import load_prompt
from src.core.categories import category_names
from src.core.schemas import ParsedTransaction
from src.core.toon import to_toon
from src.db.repositories.transaction_repo import TransactionRepository
from src.services.gemini import GeminiService
from src.services.redis_client import RedisClient

logger = logging.getLogger(__name__)

FALLBACK_CATEGORY = "Khác"
DEFAULT_HISTORY_LOOKBACK = 5
MAJORITY_MIN_COUNT = 2
AMOUNT_OUTLIER_RATIO = 3.0  # current amount vs history median


def _render_prompt() -> str:
    names = category_names()
    rendered = json.dumps(names, ensure_ascii=False)
    return load_prompt("tagging").replace("{{CATEGORIES}}", rendered)


SYSTEM_PROMPT = _render_prompt()


class TaggingAgent:
    """Classifies transactions and generates metadata tags.

    The agent has three layers of memory, tried in order:
    1. Redis merchant cache (hot, per-merchant).
    2. MongoDB historical memory — previous transactions for this
       user + merchant. A strong majority short-circuits the LLM,
       but only when the new transaction is *in-pattern* (same
       direction, amount within AMOUNT_OUTLIER_RATIO× history median).
       User-corrected history entries outweigh auto-tagged ones.
    3. Gemini Flash, called with the history as context so it can
       keep classifications consistent across similar transactions.
    """

    def __init__(
        self,
        gemini: GeminiService,
        redis: RedisClient,
        transaction_repo: TransactionRepository | None = None,
        history_lookback: int = DEFAULT_HISTORY_LOOKBACK,
    ) -> None:
        self._gemini = gemini
        self._redis = redis
        self._repo = transaction_repo
        self._history_lookback = history_lookback

    async def enrich(
        self,
        transaction: ParsedTransaction,
        user_id: str,
    ) -> dict:
        """Return {category_name, tags} for a parsed transaction."""
        merchant = transaction.merchant_name

        # Layer 1 — Redis merchant cache (keyed by user_id to prevent cross-user poisoning)
        if merchant:
            cached = await self._redis.get_merchant_cache(merchant, user_id)
            if cached:
                logger.info("Merchant cache hit: %s -> %s", merchant, cached)
                return {"category_name": cached, "tags": []}

        # Layer 2 — MongoDB historical memory
        history = await self._load_history(user_id, merchant)
        majority = self._majority_category(history, transaction)
        if majority is not None:
            logger.info(
                "Historical majority for %s -> %s (n=%d)",
                merchant,
                majority,
                len(history),
            )
            if merchant:
                await self._redis.set_merchant_cache(merchant, majority, user_id)
            return {
                "category_name": majority,
                "tags": self._merge_tags(history),
            }

        # Layer 3 — Gemini Flash, with history as context
        user_msg = self._build_user_msg(transaction, history)
        result = await self._gemini.call_flash(SYSTEM_PROMPT, user_msg)

        category = result.get("category_name", FALLBACK_CATEGORY)
        tags = result.get("tags", [])

        if merchant and category != FALLBACK_CATEGORY:
            await self._redis.set_merchant_cache(merchant, category, user_id)
            logger.info("Merchant cached: %s -> %s", merchant, category)

        return {"category_name": category, "tags": tags}

    async def _load_history(
        self, user_id: str, merchant: str | None
    ) -> list[dict]:
        if not merchant or self._repo is None:
            return []
        return await self._repo.find_by_merchant(
            user_id=user_id,
            merchant_name=merchant,
            limit=self._history_lookback,
        )

    @classmethod
    def _majority_category(
        cls, history: list[dict], transaction: ParsedTransaction
    ) -> str | None:
        """Return the winning category if history dominates AND the new
        transaction is in-pattern.

        Bails out when:
        - history has no usable categories
        - the new transaction's direction differs from the history majority
        - the new transaction's amount is an outlier vs history median
        - no category meets MAJORITY_MIN_COUNT + strict majority
        """
        if not history:
            return None

        # Pattern check: direction must match history's dominant direction.
        dir_counts = Counter(
            h.get("direction") for h in history if h.get("direction")
        )
        if dir_counts and transaction.direction:
            top_dir, _ = dir_counts.most_common(1)[0]
            if transaction.direction != top_dir:
                return None

        # Pattern check: amount within AMOUNT_OUTLIER_RATIO× history median.
        amounts = [
            h.get("amount") for h in history if isinstance(h.get("amount"), (int, float))
        ]
        if amounts and transaction.amount:
            median = statistics.median(amounts)
            if median > 0 and (
                transaction.amount > median * AMOUNT_OUTLIER_RATIO
                or transaction.amount < median / AMOUNT_OUTLIER_RATIO
            ):
                return None

        # Prefer user-corrected entries if any exist — user overrides win.
        corrected = [h for h in history if h.get("user_corrected")]
        pool = corrected if corrected else history

        counts = Counter(
            txn.get("category_id")
            for txn in pool
            if txn.get("category_id") and txn.get("category_id") != FALLBACK_CATEGORY
        )
        if not counts:
            return None

        top, top_count = counts.most_common(1)[0]

        # Single user correction is enough to win.
        if corrected:
            return top

        if top_count < MAJORITY_MIN_COUNT:
            return None
        if top_count * 2 <= len(pool):  # not a strict majority
            return None
        return top

    @staticmethod
    def _merge_tags(history: list[dict]) -> list[str]:
        seen: list[str] = []
        for txn in history:
            for tag in txn.get("tags") or []:
                if tag not in seen:
                    seen.append(tag)
        return seen

    @staticmethod
    def _build_user_msg(
        transaction: ParsedTransaction, history: list[dict]
    ) -> str:
        merchant_name = transaction.merchant_name or "Unknown"
        payload: dict = {
            "merchant": f"<merchant>{merchant_name}</merchant>",
            "amount": transaction.amount,
            "currency": transaction.currency,
            "direction": transaction.direction,
            "bank": transaction.bank_name or "Unknown",
        }
        if history:
            payload["history"] = [
                {
                    "category": txn.get("category_id") or "?",
                    "tags": ",".join(txn.get("tags") or []),
                    "corrected": bool(txn.get("user_corrected")),
                }
                for txn in history
            ]
        return to_toon(payload)

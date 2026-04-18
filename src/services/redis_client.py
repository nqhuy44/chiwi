"""Redis client for session and state management."""

import json
import logging

from src.core.config import settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "chiwi"


class RedisClient:
    """Async Redis client for session/state management."""

    def __init__(self):
        self._redis = None

    async def connect(self):
        """Initialize Redis connection."""
        import redis.asyncio as redis

        self._redis = redis.from_url(
            settings.redis_url, decode_responses=True
        )
        logger.info("Redis connected")

    async def close(self):
        if self._redis:
            await self._redis.close()

    def _key(self, *parts: str) -> str:
        return ":".join([KEY_PREFIX, *parts])

    async def get_session(self, chat_id: str) -> dict | None:
        raw = await self._redis.get(self._key("session", chat_id))
        return json.loads(raw) if raw else None

    async def set_session(
        self, chat_id: str, data: dict, ttl: int = 1800
    ) -> None:
        await self._redis.set(
            self._key("session", chat_id), json.dumps(data), ex=ttl
        )

    async def get_merchant_cache(self, merchant: str) -> str | None:
        return await self._redis.get(self._key("merchant_cache", merchant))

    async def set_merchant_cache(
        self, merchant: str, category: str, ttl: int = 604800
    ) -> None:
        await self._redis.set(
            self._key("merchant_cache", merchant), category, ex=ttl
        )

    async def increment_rate_limit(
        self, user_id: str, ttl: int = 60
    ) -> int:
        key = self._key("rate_limit", user_id)
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, ttl)
        return count

"""Redis client for session and state management."""

import json
import logging

from src.core.config import settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "chiwi"


class RedisClient:
    """Async Redis client for session/state management."""

    def __init__(self) -> None:
        self._redis = None

    @property
    def is_connected(self) -> bool:
        return self._redis is not None

    async def connect(self) -> None:
        """Initialize Redis connection."""
        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(
                settings.redis_url, decode_responses=True
            )
            # Verify connectivity
            await self._redis.ping()
            logger.info("Redis connected: %s", settings.redis_url)
        except Exception:
            logger.exception("Redis connection failed — caching disabled")
            self._redis = None

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            logger.info("Redis disconnected")

    def _key(self, *parts: str) -> str:
        return ":".join([KEY_PREFIX, *parts])

    async def get_session(self, chat_id: str) -> dict | None:
        if not self._redis:
            return None
        raw = await self._redis.get(self._key("session", chat_id))
        return json.loads(raw) if raw else None

    async def set_session(
        self, chat_id: str, data: dict, ttl: int = 1800
    ) -> None:
        if not self._redis:
            return
        await self._redis.set(
            self._key("session", chat_id), json.dumps(data), ex=ttl
        )

    async def get_merchant_cache(self, merchant: str) -> str | None:
        if not self._redis:
            return None
        return await self._redis.get(self._key("merchant_cache", merchant))

    async def set_merchant_cache(
        self, merchant: str, category: str, ttl: int = 604800
    ) -> None:
        if not self._redis:
            return
        await self._redis.set(
            self._key("merchant_cache", merchant), category, ex=ttl
        )

    async def delete_merchant_cache(self, merchant: str) -> None:
        """Invalidate a merchant's cached category — called on user corrections."""
        if not self._redis:
            return
        await self._redis.delete(self._key("merchant_cache", merchant))

    async def increment_rate_limit(
        self, user_id: str, ttl: int = 60
    ) -> int:
        if not self._redis:
            return 0
        key = self._key("rate_limit", user_id)
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, ttl)
        return count

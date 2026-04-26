"""Nudge repository for MongoDB operations.

Stores delivered behavioral nudges and powers anti-spam checks
(daily count, recent duplicate-type detection).
"""

import logging
from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.db.models.nudge import NudgeDocument

logger = logging.getLogger(__name__)


class NudgeRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["nudges"]

    async def insert(self, nudge: NudgeDocument) -> str:
        result = await self.collection.insert_one(nudge.model_dump())
        return str(result.inserted_id)

    async def count_since(self, user_id: str, since: datetime) -> int:
        return await self.collection.count_documents(
            {"user_id": user_id, "sent_at": {"$gte": since}}
        )

    async def find_recent(
        self, user_id: str, hours: int = 24, limit: int = 20
    ) -> list[dict]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cursor = (
            self.collection.find({"user_id": user_id, "sent_at": {"$gte": cutoff}})
            .sort("sent_at", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def has_recent_type(
        self, user_id: str, nudge_type: str, hours: int = 24
    ) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        doc = await self.collection.find_one(
            {
                "user_id": user_id,
                "nudge_type": nudge_type,
                "sent_at": {"$gte": cutoff},
            }
        )
        return doc is not None

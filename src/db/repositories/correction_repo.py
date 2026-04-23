"""Correction repository — records user overrides for tagging decisions."""

import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.db.models.correction import CorrectionDocument

logger = logging.getLogger(__name__)


class CorrectionRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["corrections"]

    async def insert(self, correction: CorrectionDocument) -> str:
        result = await self.collection.insert_one(correction.model_dump())
        return str(result.inserted_id)

    async def find_recent_for_merchant(
        self, user_id: str, merchant_name: str, limit: int = 3
    ) -> list[dict]:
        """Most recent user corrections for a merchant, newest first."""
        cursor = (
            self.collection.find(
                {"user_id": user_id, "merchant_name": merchant_name}
            )
            .sort("created_at", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)
